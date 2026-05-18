from __future__ import annotations

from ai_crawler.extraction import ExtractionOutcomeType
from ai_crawler.antidetect.handler import BlockType, BlockAnalyzer
from ai_crawler.crawl.telemetry import generate_human_summary


class TraceRecorder:
    def __init__(self, trace_store):
        self.trace_store = trace_store

    def failure_trace_kwargs(self, task, strategy, attempt, attempt_index: int) -> dict:
        block_signals_dict = {}
        if attempt.blocked:
            analysis = BlockAnalyzer.analyze(
                html=attempt.html,
                status_code=attempt.status_code or 0,
                headers=attempt.response_headers,
                latency_ms=attempt.latency_ms,
                use_interactive_search=getattr(strategy, "use_interactive_search", False),
            )
            block_signals_dict = {
                "waf_type": analysis.waf_type,
                "waf_subtype": analysis.waf_subtype,
                "js_challenge": analysis.js_challenge,
                "captcha_type": analysis.captcha_type,
                "script_signals": analysis.script_signals,
                "is_honeypot": analysis.is_honeypot,
                "latency_anomaly": analysis.latency_anomaly,
                "html_size_anomaly": analysis.html_size_anomaly,
                "header_features": analysis.header_features,
                "ip_blocked": analysis.ip_blocked,
                "human_behavior_detected": analysis.human_behavior_detected,
                "interactive_failed": analysis.interactive_failed,
            }
        else:
            block_signals_dict = {}

        return {
            "task": task,
            "strategy": strategy,
            "block_type": attempt.block_type,
            "response_snippet": attempt.html[:500],
            "success": False,
            "latency_ms": attempt.latency_ms,
            "attempt_index": attempt_index,
            "cost_estimate": attempt.cost_estimate,
            "status_code": attempt.status_code or 0,
            "response_headers": attempt.response_headers,
            "full_html_size": len(attempt.html),
            "ip_rotation_count": attempt.ip_rotation_count,
            "fingerprint_profile": attempt.fingerprint_profile,
            "anti_bot_fingerprint": attempt.anti_bot_fingerprint,
            "waf_detected": attempt.waf_detected,
            "block_signals": block_signals_dict,
            "human_friendly_summary": generate_human_summary(
                task.site,
                task.page_pattern.value,
                attempt.block_type,
                attempt.status_code or 0,
                attempt.waf_detected,
                attempt.block_reason,
                getattr(strategy, "tier", 1),
                strategy.render.value,
                strategy.proxy.value,
                attempt.ip_rotation_count,
                attempt.latency_ms,
            )
            if attempt.blocked
            else "",
        }

    def record_failure(self, **trace_kwargs) -> None:
        self.trace_store.record(**trace_kwargs)

    def record_dspy_recommendation(self, trace_kwargs: dict, strategy, attempt_index: int) -> None:
        dspy_trace_kwargs = dict(trace_kwargs)
        dspy_trace_kwargs.update(
            {
                "strategy": strategy,
                "response_snippet": "",
                "success": False,
                "latency_ms": 0,
                "attempt_index": attempt_index + 1,
                "cost_estimate": 0,
                "llm_decision": False,
            }
        )
        self.trace_store.record(**dspy_trace_kwargs)

    def record_success(
        self,
        task,
        strategy,
        attempt,
        attempt_index: int,
        extraction_strategy: str = "none",
        extraction_method: str = "none",
        extraction_metadata: dict | None = None,
    ) -> None:
        self.trace_store.record(
            task=task,
            strategy=strategy,
            block_type=BlockType.NONE,
            response_snippet="",
            success=True,
            latency_ms=attempt.latency_ms,
            attempt_index=attempt_index,
            cost_estimate=attempt.cost_estimate,
            status_code=attempt.status_code or 0,
            response_headers=attempt.response_headers,
            full_html_size=len(attempt.html),
            ip_rotation_count=attempt.ip_rotation_count,
            fingerprint_profile=attempt.fingerprint_profile,
            anti_bot_fingerprint=attempt.anti_bot_fingerprint,
            waf_detected="",
            human_friendly_summary=f"Site: {task.site} ({task.page_pattern.value}) | Tier {getattr(strategy, 'tier', 1)} {strategy.render.value} via {strategy.proxy.value} | Success | {attempt.latency_ms:.0f}ms",
            extraction_strategy=extraction_strategy,
            extraction_method=extraction_method,
            extraction_metadata=extraction_metadata or {},
        )


class FailureOutcomeHandler:
    def __init__(self, queue, recommender, trace_recorder: TraceRecorder, planner=None):
        self.queue = queue
        self.recommender = recommender
        self.trace_recorder = trace_recorder
        self.planner = planner

    def handle_blocked(self, task, attempt, trace_kwargs: dict, attempt_index: int) -> None:
        self.trace_recorder.record_failure(**trace_kwargs)
        self.queue.on_failure(task, attempt.block_type, attempt.html)

    def handle_extraction_failure(
        self,
        task,
        outcome,
        extraction_decision,
        attempt,
    ) -> tuple[bool, str]:
        outcome_str = outcome.value if hasattr(outcome, 'value') else str(outcome)
        if outcome_str == "success":
            return False, BlockType.NONE

        block_type = outcome_str
        self.queue.on_failure(task, block_type, "")

        if outcome_str == "template_invalid":
            return False, "template_invalid"
        elif outcome_str == "partial_content":
            return False, "partial_content"
        elif outcome_str == "extraction_error":
            return False, "extraction_error"
        elif outcome_str == "no_more_strategies":
            return False, BlockType.UNKNOWN

        return False, block_type

    def handle_extraction_retry(self, task, html: str, retry_reason: str) -> None:
        self.queue.on_failure(task, retry_reason, html[:200])
