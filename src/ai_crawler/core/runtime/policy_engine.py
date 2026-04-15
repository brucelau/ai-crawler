from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ai_crawler.core.runtime.trace_store import AntiBotTrace, TraceStore
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
            source=source,
        )


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

        for stats in aggregated.values():
            if stats.runs:
                stats.avg_latency_ms /= stats.runs
                stats.avg_products /= stats.runs

        self._stats = aggregated

    def get(self, site: str, page_pattern: str, render: str, proxy: str) -> PolicyStats:
        return self._stats.get(
            (site, page_pattern, render, proxy),
            PolicyStats(site=site, page_pattern=page_pattern, render=render, proxy=proxy),
        )


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
        self, task: CrawlTask, candidates: list[PolicyCandidate]
    ) -> list[PolicyScore]:
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
            scores.append(self._score_candidate(task, candidate, stats, index))

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
    ) -> list[PolicyScore]:
        base_ranked = self.rank_candidates(task, candidates)
        adjusted: list[PolicyScore] = []
        for score in base_ranked:
            penalty = self._failure_penalty(score.candidate, block_type, failed_render)
            adjusted.append(
                PolicyScore(
                    candidate=score.candidate,
                    total_score=score.total_score - penalty,
                    success_score=score.success_score,
                    yield_score=score.yield_score,
                    latency_penalty=score.latency_penalty,
                    block_penalty=score.block_penalty,
                    cost_penalty=score.cost_penalty,
                    instability_penalty=score.instability_penalty + penalty,
                    order_bonus=score.order_bonus,
                    reasons=[*score.reasons, f"failure_penalty={penalty:.1f}"],
                )
            )
        return sorted(adjusted, key=lambda score: score.total_score, reverse=True)

    def pick_next(
        self,
        task: CrawlTask,
        candidates: list[PolicyCandidate],
        block_type: str,
        failed_render: str,
    ) -> PolicyCandidate | None:
        ranked = self.rank_candidates_for_failure(task, candidates, block_type, failed_render)
        return ranked[0].candidate if ranked else None

    def _score_candidate(
        self, task: CrawlTask, candidate: PolicyCandidate, stats: PolicyStats, index: int
    ) -> PolicyScore:
        success_score = stats.success_rate * 100
        yield_score = stats.avg_products * 3
        latency_penalty = (stats.avg_latency_ms / 1000) * 0.8
        block_penalty = (
            stats.http_timeout_rate * 20
            + stats.captcha_rate * 25
            + stats.cloudflare_rate * 15
            + stats.bot_rate * 15
        )
        anti_bot_penalty = self._anti_bot_penalty(stats)
        cost_penalty = self.RENDER_COST.get(candidate.render, 5) * 2
        instability_penalty = 10 if stats.runs >= 3 and stats.successes == 0 else 0
        order_bonus = max(0, 20 - index * 2)
        contextual_bonus = self._contextual_bonus(task, candidate, stats)

        total = (
            success_score
            + yield_score
            + order_bonus
            + contextual_bonus
            - latency_penalty
            - block_penalty
            - anti_bot_penalty
            - cost_penalty
            - instability_penalty
        )
        reasons = [
            f"success_rate={stats.success_rate:.2f}",
            f"avg_products={stats.avg_products:.2f}",
            f"avg_latency_ms={stats.avg_latency_ms:.0f}",
            f"anti_bot_penalty={anti_bot_penalty:.1f}",
            f"contextual_bonus={contextual_bonus:.1f}",
        ]
        return PolicyScore(
            candidate=candidate,
            total_score=total,
            sample_count=stats.runs,
            success_rate=stats.success_rate,
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

    @staticmethod
    def _failure_penalty(candidate: PolicyCandidate, block_type: str, failed_render: str) -> float:
        penalty = 0.0
        if candidate.render == failed_render:
            penalty += 40.0
        if block_type == "http_timeout":
            if candidate.render == RenderType.CLOUDERA.value:
                penalty += 30.0
            elif candidate.render == RenderType.NONE.value:
                penalty += 20.0
        elif block_type == "captcha":
            if candidate.render in {RenderType.NONE.value, RenderType.CLOUDSCRAPER.value}:
                penalty += 35.0
        elif block_type == "cloudflare":
            if candidate.render in {RenderType.NONE.value, RenderType.CLOUDSCRAPER.value}:
                penalty += 30.0
        elif block_type == "bot_detected":
            if candidate.render in {RenderType.NONE.value, RenderType.PLAYWRIGHT.value}:
                penalty += 20.0
        return penalty
