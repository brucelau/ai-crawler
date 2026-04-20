from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ai_crawler.core.engine.trace_store import AntiBotTrace, TraceStore
from ai_crawler.core.strategy import CrawlStrategy, CrawlTask, PagePattern, RenderType


@dataclass(slots=True)
class PolicyCandidate:
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
        cls, task: CrawlTask, strategy: CrawlStrategy, source: str = "task"
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
class PolicyStats:
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
class PolicyScore:
    candidate: PolicyCandidate
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


class PolicyStatsStore:
    def __init__(self, trace_store: TraceStore | None = None, max_trace_files: int = 20):
        self.trace_store = trace_store
        self.max_trace_files = max_trace_files
        self._stats: dict[tuple[str, str, str, str], PolicyStats] = {}
        self.refresh()

    def refresh(self) -> None:
        traces: list[AntiBotTrace] = []
        if self.trace_store is not None:
            traces.extend(self.trace_store.get_all_traces())
            storage_dir = Path(self.trace_store.storage_dir)
        else:
            storage_dir = Path("traces")

        if storage_dir.exists():
            trace_files = sorted(
                storage_dir.glob("session_*.jsonl"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )[: self.max_trace_files]
            for trace_file in trace_files:
                try:
                    loader = (
                        self.trace_store.load_from_disk
                        if self.trace_store
                        else TraceStore(str(storage_dir)).load_from_disk
                    )
                    traces.extend(loader(trace_file))
                except Exception:
                    continue

        aggregated: dict[tuple[str, str, str, str], PolicyStats] = {}
        for trace in traces:
            key = (trace.site, trace.page_pattern, trace.strategy_render, trace.strategy_proxy)
            stats = aggregated.setdefault(
                key,
                PolicyStats(
                    site=trace.site,
                    page_pattern=trace.page_pattern,
                    render=trace.strategy_render,
                    proxy=trace.strategy_proxy,
                ),
            )
            stats.runs += 1
            stats.successes += 1 if trace.success else 0
            stats.avg_latency_ms += trace.latency_ms
            stats.avg_products += 1 if trace.success else 0
            stats.http_timeout_count += 1 if trace.block_type == "http_timeout" else 0
            stats.captcha_count += 1 if trace.block_type == "captcha" else 0
            stats.cloudflare_count += 1 if trace.block_type == "cloudflare" else 0
            stats.bot_count += 1 if trace.block_type == "bot_detected" else 0
            stats.axtree_hits += 1 if trace.extraction_strategy == "axtree" else 0
            vendor = (
                trace.anti_bot_fingerprint.get("vendor") if trace.anti_bot_fingerprint else None
            )
            if vendor:
                stats.anti_bot_vendors[vendor] = stats.anti_bot_vendors.get(vendor, 0) + 1
            mechanisms = (
                trace.anti_bot_fingerprint.get("mechanisms", [])
                if trace.anti_bot_fingerprint
                else []
            )
            for mechanism in mechanisms:
                stats.anti_bot_mechanisms[mechanism] = (
                    stats.anti_bot_mechanisms.get(mechanism, 0) + 1
                )

            if trace.block_type and trace.block_type != "none":
                block_signals = getattr(trace, "block_signals", None) or {}
                waf_type = block_signals.get("waf_type", "") or getattr(trace, "waf_detected", "") or ""
                js_challenge = block_signals.get("js_challenge", False)
                captcha_type = block_signals.get("captcha_type", "") or ""

                cond_key = ConditionalStats.build_key(trace.block_type, waf_type, js_challenge, captcha_type)
                if cond_key not in stats.conditional:
                    stats.conditional[cond_key] = ConditionalStats(
                        block_type=trace.block_type,
                        waf_type=waf_type,
                        js_challenge=js_challenge,
                        captcha_type=captcha_type,
                    )
                cs = stats.conditional[cond_key]
                cs.runs += 1
                cs.successes += 1 if trace.success else 0
                cs.avg_latency_ms += trace.latency_ms
                cs.avg_products += 1 if trace.success else 0

        for stats in aggregated.values():
            if stats.runs:
                stats.avg_latency_ms /= stats.runs
                stats.avg_products /= stats.runs
            for cs in stats.conditional.values():
                if cs.runs:
                    cs.avg_latency_ms /= cs.runs
                    cs.avg_products /= cs.runs

        self._stats = aggregated

    def get(self, site: str, page_pattern: str, render: str, proxy: str) -> PolicyStats:
        return self._stats.get(
            (site, page_pattern, render, proxy),
            PolicyStats(site=site, page_pattern=page_pattern, render=render, proxy=proxy),
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


class PolicyEngine:
    RENDER_COST = {
        RenderType.NONE.value: 1,
        RenderType.CLOUDSCRAPER.value: 2,
        RenderType.LIGHTPAND.value: 3,
        RenderType.PLAYWRIGHT.value: 4,
        RenderType.CAMOUFOX.value: 5,
        RenderType.CLOUDERA.value: 6,
        RenderType.SELENIUMBASE.value: 7,
        RenderType.CLOAKBROWSER.value: 8,
        RenderType.KAMELEO.value: 9,
    }
    UC_SEARCH_ALLOWLIST = {"amazon"}

    def __init__(self, stats_store: PolicyStatsStore):
        self.stats_store = stats_store

    def rank_candidates(
        self,
        task: CrawlTask,
        candidates: list[PolicyCandidate],
        block_type: str | None = None,
        waf_type: str = "",
        js_challenge: bool = False,
        captcha_type: str = "",
        llm_bonuses: dict[str, float] | None = None,
    ) -> list[PolicyScore]:
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

        scores: list[PolicyScore] = []
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
        self, task: CrawlTask, candidates: list[PolicyCandidate]
    ) -> PolicyCandidate | None:
        ranked = self.rank_candidates(task, candidates)
        return ranked[0].candidate if ranked else None

    def should_consult_llm(self, ranked_scores: list[PolicyScore]) -> bool:
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
        candidates: list[PolicyCandidate],
        block_type: str,
        failed_render: str,
        waf_type: str = "",
        js_challenge: bool = False,
        captcha_type: str = "",
        llm_bonuses: dict[str, float] | None = None,
    ) -> list[PolicyScore]:
        return self.rank_candidates(
            task, candidates, block_type=block_type, waf_type=waf_type,
            js_challenge=js_challenge, captcha_type=captcha_type,
            llm_bonuses=llm_bonuses
        )

    def pick_minimal_sufficient(
        self,
        task: CrawlTask,
        candidates: list[PolicyCandidate],
        block_type: str | None = None,
        waf_type: str = "",
        js_challenge: bool = False,
        captcha_type: str = "",
        force_explore: bool = False,
    ) -> PolicyCandidate | None:
        all_candidates = []
        for candidate in candidates:
            if self._is_blocked_by_gate(task, candidate):
                continue
            cost = self.RENDER_COST.get(candidate.render, 5)
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
        candidates: list[PolicyCandidate],
        block_type: str | None = None,
        waf_type: str = "",
        js_challenge: bool = False,
        captcha_type: str = "",
    ) -> PolicyCandidate | None:
        all_candidates = []
        for candidate in candidates:
            if self._is_blocked_by_gate(task, candidate):
                continue
            cost = self.RENDER_COST.get(candidate.render, 5)
            all_candidates.append((cost, candidate))

        if not all_candidates:
            return None

        all_candidates.sort(key=lambda x: x[0])

        def check_success(cost: int, candidate: PolicyCandidate) -> bool:
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
        candidate: PolicyCandidate,
        stats: PolicyStats,
        index: int,
        conditional: ConditionalStats | None = None,
        llm_bonus: float = 0.0,
    ) -> PolicyScore:
        if conditional:
            success_rate = conditional.success_rate
            avg_products = conditional.avg_products
            avg_latency = conditional.avg_latency_ms
            sample_count = conditional.runs
            conditional_label = f"(cond:{conditional.block_type})"
        else:
            success_rate = stats.success_rate
            avg_products = stats.avg_products
            avg_latency = stats.avg_latency_ms
            sample_count = stats.runs
            conditional_label = ""

        success_score = success_rate * 100
        yield_score = avg_products * 3
        latency_penalty = (avg_latency / 1000) * 0.8
        block_penalty = (
            stats.http_timeout_rate * 20
            + stats.captcha_rate * 25
            + stats.cloudflare_rate * 15
            + stats.bot_rate * 15
        )
        anti_bot_penalty = self._anti_bot_penalty(stats)
        cost_penalty = self.RENDER_COST.get(candidate.render, 5) * 2
        instability_penalty = 10 if sample_count >= 3 and (conditional or stats).successes == 0 else 0
        order_bonus = max(0, 20 - index * 2)
        contextual_bonus = self._contextual_bonus(task, candidate, stats)

        total = (
            success_score
            + yield_score
            + order_bonus
            + contextual_bonus
            + llm_bonus
            - latency_penalty
            - block_penalty
            - anti_bot_penalty
            - cost_penalty
            - instability_penalty
        )
        reasons = [
            f"success_rate={success_rate:.2f}{conditional_label}",
            f"avg_products={avg_products:.2f}",
            f"avg_latency_ms={avg_latency:.0f}",
            f"anti_bot_penalty={anti_bot_penalty:.1f}",
            f"contextual_bonus={contextual_bonus:.1f}",
        ]
        return PolicyScore(
            candidate=candidate,
            total_score=total,
            sample_count=sample_count,
            success_rate=success_rate,
            http_timeout_rate=stats.http_timeout_rate,
            captcha_rate=stats.captcha_rate,
            cloudflare_rate=stats.cloudflare_rate,
            success_score=success_score,
            yield_score=yield_score,
            latency_penalty=latency_penalty,
            block_penalty=block_penalty,
            anti_bot_penalty=anti_bot_penalty,
            cost_penalty=cost_penalty,
            instability_penalty=instability_penalty,
            order_bonus=order_bonus,
            contextual_bonus=contextual_bonus,
            reasons=reasons,
        )

    @staticmethod
    def _anti_bot_penalty(stats: PolicyStats) -> float:
        if not stats.runs:
            return 0.0

        penalty = 0.0
        browser_error_hits = stats.anti_bot_vendors.get("browser_error", 0)
        if browser_error_hits:
            penalty += (browser_error_hits / stats.runs) * 25

        proxy_transport_hits = stats.anti_bot_mechanisms.get("proxy_transport_error", 0)
        if proxy_transport_hits:
            penalty += (proxy_transport_hits / stats.runs) * 20

        browser_transport_hits = stats.anti_bot_mechanisms.get("browser_transport_error", 0)
        if browser_transport_hits:
            penalty += (browser_transport_hits / stats.runs) * 15

        js_challenge_hits = stats.anti_bot_mechanisms.get("js_challenge", 0)
        if js_challenge_hits:
            penalty += (js_challenge_hits / stats.runs) * 10

        captcha_hits = stats.anti_bot_mechanisms.get("captcha_gate", 0)
        if captcha_hits:
            penalty += (captcha_hits / stats.runs) * 12

        bot_score_hits = stats.anti_bot_mechanisms.get("bot_score_gate", 0)
        if bot_score_hits:
            penalty += (bot_score_hits / stats.runs) * 10

        return penalty

    @staticmethod
    def _contextual_bonus(task: CrawlTask, candidate: PolicyCandidate, stats: PolicyStats) -> float:
        bonus = 0.0
        if task.page_pattern.value == PagePattern.SEARCH.value:
            if candidate.render == RenderType.CAMOUFOX.value:
                bonus += 12.0
                if stats.successes > 0:
                    bonus += 8.0
            if candidate.render == RenderType.CLOAKBROWSER.value:
                bonus += 14.0
                if stats.successes > 0:
                    bonus += 10.0
                if task.site in {"amazon", "target"}:
                    bonus += 8.0
            if candidate.render == RenderType.SELENIUMBASE.value:
                bonus += 6.0
                if stats.successes > 0:
                    bonus += 4.0
            if candidate.render == RenderType.CLOUDERA.value:
                bonus -= 10.0
        return bonus

    @staticmethod
    def _is_blocked_by_gate(task: CrawlTask, candidate: PolicyCandidate) -> bool:
        if task.page_pattern.value != PagePattern.SEARCH.value:
            return False
        if candidate.render != RenderType.CLOUDERA.value:
            return False
        return task.site not in PolicyEngine.UC_SEARCH_ALLOWLIST
