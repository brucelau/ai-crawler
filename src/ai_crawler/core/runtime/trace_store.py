from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock

from ai_crawler.core.strategy import CrawlStrategy, CrawlTask


@dataclass
class AntiBotTrace:
    trace_id: str
    timestamp: str
    site: str
    page_pattern: str
    url: str
    block_type: str
    response_snippet: str
    response_headers: dict
    status_code: int
    full_html_size: int
    strategy_tier: int
    strategy_proxy: str
    strategy_render: str
    strategy_change_ua: bool
    strategy_use_cookies: bool
    strategy_use_human_scroll: bool
    strategy_delay_after: tuple
    success: bool
    latency_ms: float
    cost_estimate: float
    attempt_index: int
    llm_decision: bool = False
    ip_rotation_count: int = 0
    fingerprint_profile: dict = None
    waf_detected: str = ""
    human_friendly_summary: str = ""

    def __post_init__(self):
        if self.fingerprint_profile is None:
            self.fingerprint_profile = {}

    def to_dict(self) -> dict:
        d = asdict(self)
        d["strategy_delay_after"] = list(self.strategy_delay_after)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "AntiBotTrace":
        d["strategy_delay_after"] = tuple(d["strategy_delay_after"])
        if "response_headers" not in d:
            d["response_headers"] = {}
        if "status_code" not in d:
            d["status_code"] = 0
        if "full_html_size" not in d:
            d["full_html_size"] = 0
        if "strategy_tier" not in d:
            d["strategy_tier"] = 1
        if "ip_rotation_count" not in d:
            d["ip_rotation_count"] = 0
        if "fingerprint_profile" not in d:
            d["fingerprint_profile"] = {}
        if "waf_detected" not in d:
            d["waf_detected"] = ""
        if "human_friendly_summary" not in d:
            d["human_friendly_summary"] = ""
        return cls(**d)


class TraceStore:
    def __init__(self, storage_dir: str = "traces"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._traces: list[AntiBotTrace] = []
        self._lock = Lock()
        self._session_file = self.storage_dir / f"session_{int(time.time())}.jsonl"

    def record(
        self,
        task: CrawlTask,
        strategy: CrawlStrategy,
        block_type: str,
        response_snippet: str,
        success: bool,
        latency_ms: float,
        attempt_index: int,
        llm_decision: bool = False,
        cost_estimate: float = 0.0,
        status_code: int = 0,
        response_headers: dict = None,
        full_html_size: int = 0,
        ip_rotation_count: int = 0,
        fingerprint_profile: dict = None,
        waf_detected: str = "",
        human_friendly_summary: str = "",
    ) -> AntiBotTrace:
        trace = AntiBotTrace(
            trace_id=str(uuid.uuid4())[:12],
            timestamp=datetime.utcnow().isoformat(),
            site=task.site,
            page_pattern=task.page_pattern.value,
            url=task.url,
            block_type=block_type,
            response_snippet=response_snippet[:2000],
            response_headers=response_headers or {},
            status_code=status_code,
            full_html_size=full_html_size,
            strategy_tier=getattr(strategy, "tier", 1),
            strategy_proxy=strategy.proxy.value,
            strategy_render=strategy.render.value,
            strategy_change_ua=strategy.change_ua,
            strategy_use_cookies=strategy.use_cookies,
            strategy_use_human_scroll=strategy.use_human_scroll,
            strategy_delay_after=strategy.delay_after,
            success=success,
            latency_ms=latency_ms,
            cost_estimate=cost_estimate,
            attempt_index=attempt_index,
            llm_decision=llm_decision,
            ip_rotation_count=ip_rotation_count,
            fingerprint_profile=fingerprint_profile or {},
            waf_detected=waf_detected,
            human_friendly_summary=human_friendly_summary,
        )

        with self._lock:
            self._traces.append(trace)
            self._append_to_disk(trace)

        return trace

    def _append_to_disk(self, trace: AntiBotTrace) -> None:
        with open(self._session_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(trace.to_dict(), ensure_ascii=False) + "\n")

    def load_from_disk(self, file_path: str | Path) -> list[AntiBotTrace]:
        traces = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    traces.append(AntiBotTrace.from_dict(json.loads(line)))
        return traces

    def get_all_traces(self) -> list[AntiBotTrace]:
        with self._lock:
            return list(self._traces)

    def get_failed_traces(self) -> list[AntiBotTrace]:
        return [t for t in self._traces if not t.success]

    def get_successful_strategies(self, site: str, page_pattern: str) -> list[dict]:
        results = []
        for t in self._traces:
            if t.site == site and t.page_pattern == page_pattern and t.success:
                results.append(
                    {
                        "proxy": t.strategy_proxy,
                        "render": t.strategy_render,
                        "change_ua": t.strategy_change_ua,
                        "use_cookies": t.strategy_use_cookies,
                        "use_human_scroll": t.strategy_use_human_scroll,
                        "cost_estimate": t.cost_estimate,
                    }
                )
        return results

    def stats(self) -> dict:
        total = len(self._traces)
        success = sum(1 for t in self._traces if t.success)
        failed = total - success
        llm_decisions = sum(1 for t in self._traces if t.llm_decision)
        total_cost = sum(t.cost_estimate for t in self._traces)
        sites = set(t.site for t in self._traces)
        patterns = set(t.page_pattern for t in self._traces)
        block_types = {}
        for t in self._traces:
            block_types[t.block_type] = block_types.get(t.block_type, 0) + 1

        return {
            "total": total,
            "success": success,
            "failed": failed,
            "success_rate": f"{success / total * 100:.1f}%" if total > 0 else "N/A",
            "llm_decisions": llm_decisions,
            "total_cost_estimate": f"${total_cost:.4f}",
            "sites": list(sites),
            "patterns": list(patterns),
            "block_types": block_types,
        }

    def export_for_dspy(self) -> list[dict]:
        examples = []
        for t in self._traces:
            if t.success:
                examples.append(
                    {
                        "site": t.site,
                        "page_pattern": t.page_pattern,
                        "block_type": t.block_type,
                        "response_snippet": t.response_snippet,
                        "attempt_history": [],
                        "recommended_strategy": {
                            "proxy": t.strategy_proxy,
                            "render": t.strategy_render,
                            "change_ua": t.strategy_change_ua,
                            "use_cookies": t.strategy_use_cookies,
                            "use_human_scroll": t.strategy_use_human_scroll,
                        },
                        "confidence": "high" if t.attempt_index == 0 else "medium",
                        "reasoning": f"Succeeded on {t.site}/{t.page_pattern} with {t.strategy_proxy} + {t.strategy_render}",
                    }
                )
        return examples
