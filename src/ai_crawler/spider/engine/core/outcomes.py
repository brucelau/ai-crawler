from __future__ import annotations

from ai_crawler.spider.extraction.engine import ExtractionOutcomeType
from ai_crawler.spider.engine.anti_bot.handler import BlockType
from ai_crawler.spider.engine.telemetry import (
    detect_interactive_failed,
    generate_human_summary,
    extract_block_signals,
)


class TraceRecorder:
    def __init__(self, trace_store):
        self.trace_store = trace_store

    def failure_trace_kwargs(self, task, strategy, attempt, attempt_index: int) -> dict:
        block_signals_dict = {}
        if attempt.blocked:
            block_signals = extract_block_signals(
                html=attempt.html,
                headers=attempt.response_headers,
                status_code=attempt.status_code or 0,
                latency_ms=attempt.latency_ms,
                html_size=len(attempt.html),
                waf_detected=attempt.waf_detected,
            )
            use_interactive = getattr(strategy, "use_interactive_search", False)
            interactive_failed = detect_interactive_failed(
                attempt.html,
                attempt.block_type,
                block_signals.waf_type,
                use_interactive,
            )
            block_signals_dict = {
                "waf_type": block_signals.waf_type,
                "waf_subtype": block_signals.waf_subtype,
                "js_challenge": block_signals.js_challenge,
                "captcha_type": block_signals.captcha_type,
                "script_signals": block_signals.script_signals,
                "is_honeypot": block_signals.is_honeypot,
                "latency_anomaly": block_signals.latency_anomaly,
                "html_size_anomaly": block_signals.html_size_anomaly,
                "header_features": block_signals.header_features,
                "ip_blocked": block_signals.ip_blocked,
                "human_behavior_detected": block_signals.human_behavior_detected,
                "interactive_failed": interactive_failed,
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
        if self.planner is not None:
            self.planner.reprioritize_after_failure(
                task, attempt.block_type, attempt.waf_detected,
                attempt.js_challenge, attempt.captcha_type
            )
            if task.current_index >= len(task.strategies):
                task.current_index = max(0, len(task.strategies) - 1)
        needs_llm, _ = self.queue.on_failure(task, attempt.block_type, attempt.html)
        if needs_llm and self.recommender is not None:
            dspy_result = self.recommender.recommend(task, attempt.block_type, attempt.html[:500])
            if dspy_result:
                task.add_strategy_next(dspy_result)
                self.trace_recorder.record_dspy_recommendation(
                    trace_kwargs, dspy_result, attempt_index
                )

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

        if self.planner is not None and outcome_str not in ("no_more_strategies", "unknown"):
            self.planner.reprioritize_after_failure(
                task, block_type, "", False, ""
            )
            if task.current_index >= len(task.strategies):
                task.current_index = max(0, len(task.strategies) - 1)

        if outcome_str == "empty_content":
            if extraction_decision.retry_strategy:
                task.add_strategy_next(extraction_decision.retry_strategy)

        needs_llm, next_strategy = self.queue.on_failure(task, block_type, "")
        if next_strategy is not None:
            return True, block_type

        if outcome_str == "template_invalid":
            return False, "template_invalid"
        elif outcome_str == "partial_content":
            return False, "partial_content"
        elif outcome_str == "extraction_error":
            return False, "extraction_error"
        elif outcome_str == "no_more_strategies":
            self.queue.on_failure(task, BlockType.UNKNOWN, "all strategies exhausted")
            return False, BlockType.UNKNOWN

        return False, block_type

    def handle_extraction_retry(self, task, html: str, retry_reason: str) -> None:
        self.queue.on_failure(task, retry_reason, html[:200])
