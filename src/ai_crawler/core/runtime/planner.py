from __future__ import annotations

import structlog

from ai_crawler.core.runtime.policy_engine import PolicyCandidate, PolicyEngine, PolicyStatsStore
from ai_crawler.core.runtime.queue import SiteMemory
from ai_crawler.core.strategy import CrawlStrategy, CrawlTask, PagePattern, get_site_tier


log = structlog.get_logger()


class TaskStrategyPlanner:
    def __init__(self, initial_tier_selector=None, trace_store=None):
        self.initial_tier_selector = initial_tier_selector
        self.policy_engine = PolicyEngine(PolicyStatsStore(trace_store))

    def set_initial_tier_selector(self, selector) -> None:
        self.initial_tier_selector = selector

    def prepare(self, task: CrawlTask, memory: SiteMemory | None) -> SiteMemory | None:
        if task.current_index != 0:
            return memory

        if memory and memory.successful_strategies:
            best = memory.successful_strategies[0]
            if not task.strategies or task.strategies[0] != best:
                task.add_strategy_front(best)

        ranked = self._apply_policy_order(task)

        if self.initial_tier_selector and self.policy_engine.should_consult_llm(ranked):
            memory = memory or SiteMemory(site=task.site)
            self._apply_llm_tier(task, memory)
            self._apply_policy_order(task)

        return memory

    def resolve(self, task: CrawlTask) -> CrawlStrategy | None:
        return task.current_strategy()

    def reprioritize_after_failure(self, task: CrawlTask, block_type: str) -> None:
        if task.current_index >= len(task.strategies) - 1:
            return
        failed_strategy = task.current_strategy()
        remaining = task.strategies[task.current_index + 1 :]
        candidates = [PolicyCandidate.from_strategy(task, strategy) for strategy in remaining]
        ranked = self.policy_engine.rank_candidates_for_failure(
            task,
            candidates,
            block_type,
            failed_strategy.render.value if failed_strategy else "",
        )
        if not ranked:
            return

        by_key = {
            (
                getattr(strategy, "tier", 1),
                strategy.render.value,
                strategy.proxy.value,
                strategy.use_cookies,
                strategy.change_ua,
                strategy.use_human_scroll,
            ): strategy
            for strategy in remaining
        }
        reordered: list[CrawlStrategy] = []
        for score in ranked:
            key = (
                score.candidate.tier,
                score.candidate.render,
                score.candidate.proxy,
                score.candidate.use_cookies,
                score.candidate.change_ua,
                score.candidate.use_human_scroll,
            )
            strategy = by_key.get(key)
            if strategy is not None and strategy not in reordered:
                reordered.append(strategy)

        for strategy in remaining:
            if strategy not in reordered:
                reordered.append(strategy)

        task.strategies = task.strategies[: task.current_index + 1] + reordered

    def _apply_llm_tier(self, task: CrawlTask, memory: SiteMemory) -> None:
        cached_tier = memory.get_llm_tier(task.page_pattern.value)
        if cached_tier is None:
            failure_history = memory.get_failure_history_for_llm(task.page_pattern.value)
            llm_tier = self._get_llm_tier(task.site, task.page_pattern.value, failure_history)
            if llm_tier is None:
                return
            llm_tier = self._enforce_minimum_start_tier(task, llm_tier)
            memory.record_llm_tier(task.page_pattern.value, llm_tier)
            task.strategies = CrawlStrategy.get_tier_strategies(llm_tier, end_tier=9)
            task.metadata["start_tier"] = llm_tier
            task.metadata["llm_tier"] = True
            log.info(
                "llm_tier_recommended",
                site=task.site,
                page_pattern=task.page_pattern.value,
                tier=llm_tier,
            )
            return

        if cached_tier != task.metadata.get("start_tier"):
            cached_tier = self._enforce_minimum_start_tier(task, cached_tier)
            task.strategies = CrawlStrategy.get_tier_strategies(cached_tier, end_tier=9)
            task.metadata["start_tier"] = cached_tier

    @staticmethod
    def _enforce_minimum_start_tier(task: CrawlTask, tier: int) -> int:
        # Force these sites to start from tier 5 to avoid lightpand (tier 3) bug
        tier5_sites = {"homedepot", "lowes", "wayfair", "walmart", "fivebelow", "acehardware"}
        if task.site in tier5_sites and task.page_pattern == PagePattern.SEARCH:
            return max(tier, 5)
        if task.site == "amazon" and task.page_pattern == PagePattern.SEARCH:
            return max(tier, get_site_tier(task.site, task.page_pattern))
        return tier

    def _get_llm_tier(self, site: str, page_pattern: str, failure_history: str = "") -> int | None:
        if not self.initial_tier_selector:
            return None
        try:
            result = self.initial_tier_selector(
                site=site,
                page_pattern=page_pattern,
                failure_history=failure_history,
            )
            tier = int(str(result.start_tier).strip())
            if 1 <= tier <= 7:
                return tier
        except Exception:
            return None
        return None

    def _apply_policy_order(self, task: CrawlTask):
        candidates = [PolicyCandidate.from_strategy(task, strategy) for strategy in task.strategies]
        ranked = self.policy_engine.rank_candidates(task, candidates)
        if not ranked:
            return []

        by_key = {
            (
                getattr(strategy, "tier", 1),
                strategy.render.value,
                strategy.proxy.value,
                strategy.use_cookies,
                strategy.change_ua,
                strategy.use_human_scroll,
            ): strategy
            for strategy in task.strategies
        }
        reordered: list[CrawlStrategy] = []
        for score in ranked:
            key = (
                score.candidate.tier,
                score.candidate.render,
                score.candidate.proxy,
                score.candidate.use_cookies,
                score.candidate.change_ua,
                score.candidate.use_human_scroll,
            )
            strategy = by_key.get(key)
            if strategy is not None and strategy not in reordered:
                reordered.append(strategy)

        for strategy in task.strategies:
            if strategy not in reordered:
                reordered.append(strategy)
        task.strategies = reordered
        return ranked
