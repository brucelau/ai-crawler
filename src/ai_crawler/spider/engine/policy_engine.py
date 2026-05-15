from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ai_crawler.spider.engine.constants import (
    ANTI_BOT_PENALTIES, CONTEXTUAL_BONUSES, CONTEXTUAL_BONUSES_SUCCESS,
    CLOAKBROWSER_AMAZON_TARGET_BONUS, CLOUDERA_NON_ALLOWLIST_PENALTY,
    RENDER_COST, SCORE_WEIGHTS, UC_SEARCH_ALLOWLIST,
)
from ai_crawler.spider.engine.core.trace_store import AntiBotTrace, TraceStore
from ai_crawler.spider.runtime.crawl import CrawlPolicy, CrawlTask, PagePattern, RenderType


@dataclass(slots=True)
class CrawlPolicyCandidate:
    site: str
    page_pattern: str
    tier: int
    render: str
    proxy: str
    use_cookies: bool
    change_ua: bool
    use_human_scroll: bool
    use_interactive_search: bool = False
    source: str = "task"

    @classmethod
    def from_strategy(
        cls, task: CrawlTask, strategy: CrawlPolicy, source: str = "task"
    ) -> "PolicyCandidate":
        return cls(
            site=task.site,
            page_pattern=task.page_pattern.value,
            tier=getattr(strategy, "tier", 1),
            render=strategy.render.value,
            proxy=strategy.proxy.value,
            use_cookies=strategy.use_cookies,
            change_ua=strategy.change_ua,
            use_human_scroll=strategy.use_human_scroll,
            use_interactive_search=getattr(strategy, "use_interactive_search", False),
            source=source,
        )


@dataclass(slots=True)
class ConditionalStats:
    """Stats conditioned on encountering specific block signals"""
    block_type: str = ""
    waf_type: str = ""
    js_challenge: bool = False
    captcha_type: str = ""
    runs: int = 0
    successes: int = 0
    avg_latency_ms: float = 0.0
    avg_products: float = 0.0

    @property
    def success_rate(self) -> float:
        return self.successes / self.runs if self.runs else 0.0

    @property
    def key(self) -> str:
        """Composite key for dict storage: block_type:waf_type:js_challenge:captcha_type"""
        parts = [self.block_type, self.waf_type]
        parts.append("js" if self.js_challenge else "nojs")
        parts.append(self.captcha_type or "nocap")
        return ":".join(parts)

    @staticmethod
    def build_key(block_type: str, waf_type: str = "", js_challenge: bool = False, captcha_type: str = "") -> str:
        """Build a conditional key from components"""
        parts = [block_type, waf_type or ""]
        parts.append("js" if js_challenge else "nojs")
        parts.append(captcha_type or "nocap")
        return ":".join(parts)


@dataclass(slots=True)
class CrawlPolicyStats:
    site: str
    page_pattern: str
    render: str
    proxy: str
    runs: int = 0
    successes: int = 0
    avg_latency_ms: float = 0.0
    avg_products: float = 0.0
    http_timeout_count: int = 0
    captcha_count: int = 0
    cloudflare_count: int = 0
    bot_count: int = 0
    axtree_hits: int = 0
    anti_bot_vendors: dict[str, int] = field(default_factory=dict)
    anti_bot_mechanisms: dict[str, int] = field(default_factory=dict)
    conditional: dict[str, ConditionalStats] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        return self.successes / self.runs if self.runs else 0.0

    @property
    def http_timeout_rate(self) -> float:
        return self.http_timeout_count / self.runs if self.runs else 0.0

    @property
    def captcha_rate(self) -> float:
        return self.captcha_count / self.runs if self.runs else 0.0

    @property
    def cloudflare_rate(self) -> float:
        return self.cloudflare_count / self.runs if self.runs else 0.0

    @property
    def bot_rate(self) -> float:
        return self.bot_count / self.runs if self.runs else 0.0


@dataclass(slots=True)
class CrawlPolicyScore:
    candidate: CrawlPolicyCandidate
    total_score: float
    sample_count: int = 0
    success_rate: float = 0.0
    http_timeout_rate: float = 0.0
    captcha_rate: float = 0.0
    cloudflare_rate: float = 0.0
    success_score: float = 0.0
    yield_score: float = 0.0
    latency_penalty: float = 0.0
    block_penalty: float = 0.0
    anti_bot_penalty: float = 0.0
    cost_penalty: float = 0.0
    instability_penalty: float = 0.0
    order_bonus: float = 0.0
    contextual_bonus: float = 0.0
    reasons: list[str] = field(default_factory=list)


class CrawlPolicyStatsStore:
    def __init__(self, trace_store: TraceStore | None = None, max_trace_files: int = 20):
        self.trace_store = trace_store
        self.max_trace_files = max_trace_files
        self._stats: dict[tuple[str, str, str, str], CrawlPolicyStats] = {}
        self.refresh()

    def refresh(self) -> None:
        traces = self._load_traces()
        aggregated = self._aggregate_traces(traces)
        self._finalize_stats(aggregated)
        self._stats = aggregated

    def _load_traces(self) -> list[AntiBotTrace]:
        traces: list[AntiBotTrace] = []
        storage_dir = Path(self.trace_store.storage_dir) if self.trace_store else Path("traces")
        if self.trace_store:
            traces.extend(self.trace_store.get_all_traces())
        if storage_dir.exists():
            for trace_file in sorted(storage_dir.glob("session_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[: self.max_trace_files]:
                try:
                    loader = self.trace_store.load_from_disk if self.trace_store else TraceStore(str(storage_dir)).load_from_disk
                    traces.extend(loader(trace_file))
                except Exception:
                    continue
        return traces

    def _aggregate_traces(self, traces: list[AntiBotTrace]) -> dict[tuple[str, str, str, str], CrawlPolicyStats]:
        aggregated: dict[tuple[str, str, str, str], CrawlPolicyStats] = {}
        for trace in traces:
            key = (trace.site, trace.page_pattern, trace.strategy_render, trace.strategy_proxy)
            stats = aggregated.setdefault(key, CrawlPolicyStats(site=trace.site, page_pattern=trace.page_pattern, render=trace.strategy_render, proxy=trace.strategy_proxy))
            self._update_stats_from_trace(stats, trace)
        return aggregated

    def _update_stats_from_trace(self, stats: CrawlPolicyStats, trace: AntiBotTrace) -> None:
        stats.runs += 1
        stats.successes += trace.success
        stats.avg_latency_ms += trace.latency_ms
        stats.avg_products += trace.success
        block_type = trace.block_type
        if block_type:
            if block_type == "http_timeout": stats.http_timeout_count += 1
            elif block_type == "captcha": stats.captcha_count += 1
            elif block_type == "cloudflare": stats.cloudflare_count += 1
            elif block_type == "bot_detected": stats.bot_count += 1
        if trace.extraction_strategy == "axtree": stats.axtree_hits += 1
        if trace.anti_bot_fingerprint:
            vendor = trace.anti_bot_fingerprint.get("vendor")
            if vendor: stats.anti_bot_vendors[vendor] = stats.anti_bot_vendors.get(vendor, 0) + 1
            for mech in trace.anti_bot_fingerprint.get("mechanisms", []):
                stats.anti_bot_mechanisms[mech] = stats.anti_bot_mechanisms.get(mech, 0) + 1
        if block_type and block_type != "none":
            signals = getattr(trace, "block_signals", None) or {}
            cs = stats.conditional.setdefault(ConditionalStats.build_key(block_type, signals.get("waf_type", "") or getattr(trace, "waf_detected", "") or "", signals.get("js_challenge", False), signals.get("captcha_type", "") or ""), ConditionalStats(block_type=block_type, waf_type=signals.get("waf_type", ""), js_challenge=signals.get("js_challenge", False), captcha_type=signals.get("captcha_type", "") or ""))
            cs.runs += 1
            cs.successes += trace.success
            cs.avg_latency_ms += trace.latency_ms
            cs.avg_products += trace.success

    def _finalize_stats(self, aggregated: dict[tuple[str, str, str, str], CrawlPolicyStats]) -> None:
        for stats in aggregated.values():
            if stats.runs:
                stats.avg_latency_ms /= stats.runs
                stats.avg_products /= stats.runs
            for cs in stats.conditional.values():
                if cs.runs:
                    cs.avg_latency_ms /= cs.runs
                    cs.avg_products /= cs.runs

    def get(self, site: str, page_pattern: str, render: str, proxy: str) -> CrawlPolicyStats:
        return self._stats.get(
            (site, page_pattern, render, proxy),
            CrawlPolicyStats(site=site, page_pattern=page_pattern, render=render, proxy=proxy),
        )

    def get_conditional(
        self, site: str, page_pattern: str, render: str, proxy: str,
        block_type: str, waf_type: str = "", js_challenge: bool = False, captcha_type: str = ""
    ) -> ConditionalStats | None:
        stats = self._stats.get((site, page_pattern, render, proxy))
        if stats is None:
            return None

        keys_to_try = [
            ConditionalStats.build_key(block_type, waf_type, js_challenge, captcha_type),
            ConditionalStats.build_key(block_type, waf_type, js_challenge, ""),
            ConditionalStats.build_key(block_type, waf_type, False, ""),
            ConditionalStats.build_key(block_type, "", False, ""),
            block_type,
        ]

        for key in keys_to_try:
            if key in stats.conditional:
                return stats.conditional[key]
        return None


class CrawlPolicyScorer:
    def __init__(self, stats_store: CrawlPolicyStatsStore):
        self.stats_store = stats_store

    def rank_candidates(
        self,
        task: CrawlTask,
        candidates: list[CrawlPolicyCandidate],
        block_type: str | None = None,
        waf_type: str = "",
        js_challenge: bool = False,
        captcha_type: str = "",
        llm_bonuses: dict[str, float] | None = None,
    ) -> list[CrawlPolicyScore]:
        max_sample_count = 0
        for candidate in candidates:
            stats = self.stats_store.get(
                candidate.site,
                candidate.page_pattern,
                candidate.render,
                candidate.proxy,
            )
            if stats.runs > max_sample_count:
                max_sample_count = stats.runs

        llm_weight = 1.0 / (1.0 + max_sample_count)

        scores: list[CrawlPolicyScore] = []
        for index, candidate in enumerate(candidates):
            if self._is_blocked_by_gate(task, candidate):
                continue
            stats = self.stats_store.get(
                candidate.site,
                candidate.page_pattern,
                candidate.render,
                candidate.proxy,
            )
            conditional = None
            if block_type:
                conditional = self.stats_store.get_conditional(
                    candidate.site,
                    candidate.page_pattern,
                    candidate.render,
                    candidate.proxy,
                    block_type,
                    waf_type,
                    js_challenge,
                    captcha_type,
                )

            llm_bonus = 0.0
            if llm_bonuses:
                raw_bonus = llm_bonuses.get(candidate.render, 0.0)
                llm_bonus = raw_bonus * llm_weight

            scores.append(self._score_candidate(task, candidate, stats, index, conditional, llm_bonus))

        return sorted(scores, key=lambda score: score.total_score, reverse=True)

    def pick_initial(
        self, task: CrawlTask, candidates: list[CrawlPolicyCandidate]
    ) -> CrawlPolicyCandidate | None:
        ranked = self.rank_candidates(task, candidates)
        return ranked[0].candidate if ranked else None

    def should_consult_llm(self, ranked_scores: list[CrawlPolicyScore]) -> bool:
        if not ranked_scores:
            return False
        top = ranked_scores[0]
        if top.sample_count < 3:
            return True
        if len(ranked_scores) > 1 and abs(top.total_score - ranked_scores[1].total_score) < 10:
            return True
        if (
            top.success_rate < 0.7
            and max(top.http_timeout_rate, top.captcha_rate, top.cloudflare_rate) > 0.3
        ):
            return True
        return False

    def rank_candidates_for_failure(
        self,
        task: CrawlTask,
        candidates: list[CrawlPolicyCandidate],
        block_type: str,
        failed_render: str,
        waf_type: str = "",
        js_challenge: bool = False,
        captcha_type: str = "",
        llm_bonuses: dict[str, float] | None = None,
    ) -> list[CrawlPolicyScore]:
        return self.rank_candidates(
            task, candidates, block_type=block_type, waf_type=waf_type,
            js_challenge=js_challenge, captcha_type=captcha_type,
            llm_bonuses=llm_bonuses
        )

    def pick_minimal_sufficient(
        self,
        task: CrawlTask,
        candidates: list[CrawlPolicyCandidate],
        block_type: str | None = None,
        waf_type: str = "",
        js_challenge: bool = False,
        captcha_type: str = "",
        force_explore: bool = False,
    ) -> CrawlPolicyCandidate | None:
        all_candidates = []
        for candidate in candidates:
            if self._is_blocked_by_gate(task, candidate):
                continue
            cost = RENDER_COST.get(candidate.render, 5)
            all_candidates.append((cost, candidate))

        if not all_candidates:
            return None

        all_candidates.sort(key=lambda x: x[0])

        sufficient = []
        unexplored = []
        for cost, candidate in all_candidates:
            stats = self.stats_store.get(
                candidate.site,
                candidate.page_pattern,
                candidate.render,
                candidate.proxy,
            )
            conditional = None
            if block_type:
                conditional = self.stats_store.get_conditional(
                    candidate.site,
                    candidate.page_pattern,
                    candidate.render,
                    candidate.proxy,
                    block_type,
                    waf_type,
                    js_challenge,
                    captcha_type,
                )

            if conditional and conditional.runs >= 1 and conditional.success_rate > 0:
                sufficient.append((cost, candidate))
            elif conditional is None or conditional.runs == 0:
                unexplored.append((cost, candidate))

        if sufficient:
            sufficient.sort(key=lambda x: x[0])
            return sufficient[0][1]

        if unexplored:
            unexplored.sort(key=lambda x: x[0])
            if force_explore:
                return unexplored[0][1]
            return unexplored[0][1]

        return None

    def binary_search_minimal(
        self,
        task: CrawlTask,
        candidates: list[CrawlPolicyCandidate],
        block_type: str | None = None,
        waf_type: str = "",
        js_challenge: bool = False,
        captcha_type: str = "",
    ) -> CrawlPolicyCandidate | None:
        all_candidates = []
        for candidate in candidates:
            if self._is_blocked_by_gate(task, candidate):
                continue
            cost = RENDER_COST.get(candidate.render, 5)
            all_candidates.append((cost, candidate))

        if not all_candidates:
            return None

        all_candidates.sort(key=lambda x: x[0])

        def check_success(cost: int, candidate: CrawlPolicyCandidate) -> bool:
            stats = self.stats_store.get(
                candidate.site,
                candidate.page_pattern,
                candidate.render,
                candidate.proxy,
            )
            conditional = None
            if block_type:
                conditional = self.stats_store.get_conditional(
                    candidate.site,
                    candidate.page_pattern,
                    candidate.render,
                    candidate.proxy,
                    block_type,
                    waf_type,
                    js_challenge,
                    captcha_type,
                )
            if conditional:
                return conditional.runs >= 1 and conditional.success_rate > 0
            return stats.runs >= 1 and stats.success_rate > 0

        low = 0
        high = len(all_candidates) - 1
        result = None

        while low <= high:
            mid = (low + high) // 2
            mid_cost, mid_candidate = all_candidates[mid]

            if check_success(mid_cost, mid_candidate):
                result = mid_candidate
                high = mid - 1
            else:
                low = mid + 1

        return result

    def _score_candidate(
        self,
        task: CrawlTask,
        candidate: CrawlPolicyCandidate,
        stats: CrawlPolicyStats,
        index: int,
        conditional: ConditionalStats | None = None,
        llm_bonus: float = 0.0,
    ) -> CrawlPolicyScore:
        src = conditional if conditional else stats
        success_rate = src.success_rate
        avg_products = src.avg_products
        avg_latency = src.avg_latency_ms
        sample_count = src.runs
        cond_label = f"(cond:{conditional.block_type})" if conditional else ""

        success_score = success_rate * 100
        yield_score = avg_products * 3
        order_bonus = max(0, 20 - index * 2)
        contextual_bonus = self._contextual_bonus(task, candidate, stats)
        latency_penalty = (avg_latency / 1000) * 0.8
        block_penalty = stats.http_timeout_rate * 20 + stats.captcha_rate * 25 + stats.cloudflare_rate * 15 + stats.bot_rate * 15
        anti_bot_penalty = self._anti_bot_penalty(stats)
        cost_penalty = RENDER_COST.get(candidate.render, 5) * 2
        instability_penalty = 10 if sample_count >= 3 and src.successes == 0 else 0

        total = success_score + yield_score + order_bonus + contextual_bonus + llm_bonus - latency_penalty - block_penalty - anti_bot_penalty - cost_penalty - instability_penalty
        return CrawlPolicyScore(
            candidate=candidate, total_score=total, sample_count=sample_count,
            success_rate=success_rate, http_timeout_rate=stats.http_timeout_rate,
            captcha_rate=stats.captcha_rate, cloudflare_rate=stats.cloudflare_rate,
            success_score=success_score, yield_score=yield_score, order_bonus=order_bonus,
            latency_penalty=latency_penalty, block_penalty=block_penalty,
            anti_bot_penalty=anti_bot_penalty, cost_penalty=cost_penalty,
            instability_penalty=instability_penalty, contextual_bonus=contextual_bonus,
            reasons=[
                f"success_rate={success_rate:.2f}{cond_label}",
                f"avg_products={avg_products:.2f}",
                f"avg_latency_ms={avg_latency:.0f}",
                f"anti_bot_penalty={anti_bot_penalty:.1f}",
                f"contextual_bonus={contextual_bonus:.1f}",
            ],
        )

    @staticmethod
    def _anti_bot_penalty(stats: CrawlPolicyStats) -> float:
        if not stats.runs:
            return 0.0
        runs = stats.runs
        penalty = (
            stats.anti_bot_vendors.get("browser_error", 0) * 25 +
            stats.anti_bot_mechanisms.get("proxy_transport_error", 0) * 20 +
            stats.anti_bot_mechanisms.get("browser_transport_error", 0) * 15 +
            stats.anti_bot_mechanisms.get("js_challenge", 0) * 10 +
            stats.anti_bot_mechanisms.get("captcha_gate", 0) * 12 +
            stats.anti_bot_mechanisms.get("bot_score_gate", 0) * 10
        ) / runs
        return penalty

    @staticmethod
    def _contextual_bonus(task: CrawlTask, candidate: CrawlPolicyCandidate, stats: CrawlPolicyStats) -> float:
        if task.page_pattern.value != PagePattern.SEARCH.value:
            return 0.0
        key = (task.page_pattern.value, candidate.render)
        bonus = CONTEXTUAL_BONUSES.get(key, 0)
        bonus += CONTEXTUAL_BONUSES_SUCCESS.get(key, 0) if stats.successes > 0 else 0
        if candidate.render == RenderType.CLOAKBROWSER.value and task.site in {"amazon", "target"}:
            bonus += CLOAKBROWSER_AMAZON_TARGET_BONUS
        if candidate.render == RenderType.CLOUDERA.value:
            bonus = bonus if task.site in UC_SEARCH_ALLOWLIST else -CLOUDERA_NON_ALLOWLIST_PENALTY
        return bonus

    @staticmethod
    def _is_blocked_by_gate(task: CrawlTask, candidate: CrawlPolicyCandidate) -> bool:
        if task.page_pattern.value != PagePattern.SEARCH.value:
            return False
        if candidate.render != RenderType.CLOUDERA.value:
            return False
        return task.site not in UC_SEARCH_ALLOWLIST
