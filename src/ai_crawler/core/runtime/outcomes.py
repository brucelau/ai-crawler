from __future__ import annotations

from ai_crawler.core.runtime.handler import BlockType
from ai_crawler.core.runtime.telemetry import generate_human_summary


class TraceRecorder:
    def __init__(self, trace_store):
        self.trace_store = trace_store

    def failure_trace_kwargs(self, task, strategy, attempt, attempt_index: int) -> dict:
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
            self.planner.reprioritize_after_failure(task, attempt.block_type)
        needs_llm, _ = self.queue.on_failure(task, attempt.block_type, attempt.html)
        if needs_llm and self.recommender is not None:
            dspy_result = self.recommender.recommend(task, attempt.block_type, attempt.html[:500])
            if dspy_result:
                task.add_strategy_next(dspy_result)
                self.trace_recorder.record_dspy_recommendation(
                    trace_kwargs, dspy_result, attempt_index
                )

    def handle_extraction_retry(self, task, html: str, retry_reason: str) -> None:
        self.queue.on_failure(task, retry_reason, html[:200])
