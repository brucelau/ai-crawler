from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from threading import Lock

from ai_crawler.core.types import CrawlPolicy, CrawlTask


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
    extraction_strategy: str = "none"
    extraction_method: str = "none"
    extraction_metadata: dict = field(default_factory=dict)
    anti_bot_fingerprint: dict = field(default_factory=dict)
    block_signals: dict = field(default_factory=dict)

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
        if "extraction_strategy" not in d:
            d["extraction_strategy"] = "none"
        if "extraction_method" not in d:
            d["extraction_method"] = "none"
        if "extraction_metadata" not in d:
            d["extraction_metadata"] = {}
        if "anti_bot_fingerprint" not in d:
            d["anti_bot_fingerprint"] = {}
        return cls(**d)


class TraceStore:
    def __init__(self, storage_dir: str = "traces", max_age_hours: int = 24, backend: "StorageBackend | None" = None):
        from ai_crawler.storage.backend import LocalStorageBackend

        self.storage_dir = storage_dir
        self.backend = backend or LocalStorageBackend()
        self.backend.makedirs(storage_dir)
        self._traces: list[AntiBotTrace] = []
        self._lock = Lock()
        self._session_file = f"{storage_dir}/session_{int(time.time())}.jsonl"
        self._max_age_seconds = max_age_hours * 3600
        self._last_cleanup = time.time()
        self._cleanup_interval = 300

    def record(
        self,
        task: CrawlTask,
        strategy: CrawlPolicy,
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
        extraction_strategy: str = "none",
        extraction_method: str = "none",
        extraction_metadata: dict | None = None,
        anti_bot_fingerprint: dict | None = None,
        block_signals: dict | None = None,
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
            extraction_strategy=extraction_strategy,
            extraction_method=extraction_method,
            extraction_metadata=extraction_metadata or {},
            anti_bot_fingerprint=anti_bot_fingerprint or {},
            block_signals=block_signals or {},
        )

        with self._lock:
            self._traces.append(trace)
            self._append_to_disk(trace)
            self._cleanup_old_traces()

        return trace

    def _cleanup_old_traces(self) -> None:
        if time.time() - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = time.time()
        cutoff = time.time() - self._max_age_seconds
        before = len(self._traces)
        self._traces = [
            t for t in self._traces
            if datetime.fromisoformat(t.timestamp.replace("Z", "+00:00")).timestamp() > cutoff
        ]
        removed = before - len(self._traces)
        if removed > 0:
            self._compact_session_file()

    def _compact_session_file(self) -> None:
        if not self._traces:
            return
        lines = "".join(
            json.dumps(t.to_dict(), ensure_ascii=False) + "\n" for t in self._traces
        )
        self.backend.write_text(self._session_file, lines)

    def _append_to_disk(self, trace: AntiBotTrace) -> None:
        self.backend.append_text(
            self._session_file,
            json.dumps(trace.to_dict(), ensure_ascii=False) + "\n",
        )

    def load_from_disk(self, file_path: str) -> list[AntiBotTrace]:
        content = self.backend.read_text(file_path)
        traces = []
        for line in content.splitlines():
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
        extraction_strategies = {}
        axtree_hits = 0
        anti_bot_vendors = {}
        for t in self._traces:
            block_types[t.block_type] = block_types.get(t.block_type, 0) + 1
            extraction_strategies[t.extraction_strategy] = (
                extraction_strategies.get(t.extraction_strategy, 0) + 1
            )
            if t.extraction_strategy == "axtree":
                axtree_hits += 1
            vendor = t.anti_bot_fingerprint.get("vendor", "unknown")
            anti_bot_vendors[vendor] = anti_bot_vendors.get(vendor, 0) + 1

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
            "extraction_strategies": extraction_strategies,
            "axtree_hits": axtree_hits,
            "anti_bot_vendors": anti_bot_vendors,
        }

    def trajectory_report(self, site: str | None = None) -> dict:
        traces = [t for t in self._traces if site is None or t.site == site]
        if not traces:
            return {"error": "No traces found"}

        traces_by_key: dict[tuple, list] = {}
        for t in traces:
            key = (t.site, t.page_pattern)
            if key not in traces_by_key:
                traces_by_key[key] = []
            traces_by_key[key].append(t)

        report = {
            "total_traces": len(traces),
            "sites_analyzed": list(set(t.site for t in traces)),
            "by_site_pattern": {},
        }

        for (site, pattern), site_traces in traces_by_key.items():
            site_traces.sort(key=lambda t: t.timestamp if hasattr(t, 'timestamp') else "")
            attempts = []
            for i, t in enumerate(site_traces):
                attempts.append({
                    "attempt_index": i + 1,
                    "strategy": f"Tier {t.strategy_tier}/{t.strategy_render}",
                    "proxy": t.strategy_proxy,
                    "success": t.success,
                    "block_type": t.block_type,
                    "latency_ms": t.latency_ms,
                    "cost": t.cost_estimate,
                    "extraction": t.extraction_method,
                })

            successes = sum(1 for t in site_traces if t.success)
            total_cost = sum(t.cost_estimate for t in site_traces)
            block_distribution = {}
            for t in site_traces:
                block_distribution[t.block_type] = block_distribution.get(t.block_type, 0) + 1

            report["by_site_pattern"][f"{site}/{pattern}"] = {
                "total_attempts": len(site_traces),
                "successes": successes,
                "success_rate": f"{successes / len(site_traces) * 100:.1f}%",
                "total_cost": f"${total_cost:.4f}",
                "block_distribution": block_distribution,
                "attempt_trajectory": attempts,
            }

        return report

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
