from __future__ import annotations

import structlog

from ai_crawler.core.engine.policy_engine import PolicyCandidate, PolicyEngine, PolicyStatsStore
from ai_crawler.core.engine.queue import SiteMemory
from ai_crawler.core.strategy import CrawlStrategy, CrawlTask, PagePattern, get_site_tier


log = structlog.get_logger()


class TaskStrategyPlanner:
    def __init__(self, initial_tier_selector=None, trace_store=None, strategy_mode="optimal"):
        self.initial_tier_selector = initial_tier_selector
        self.policy_engine = PolicyEngine(PolicyStatsStore(trace_store))
        self.strategy_mode = strategy_mode
        self._llm_render_bonuses: dict[str, float] = {}

    def set_initial_tier_selector(self, selector) -> None:
        self.initial_tier_selector = selector

    def prepare(self, task: CrawlTask, memory: SiteMemory | None) -> SiteMemory | None:
        if task.current_index != 0:
            return memory

        self._llm_render_bonuses = {}

        if memory and memory.successful_strategies:
            best = memory.successful_strategies[0]
            if not task.strategies or task.strategies[0] != best:
                task.add_strategy_front(best)
            # Memory has explicit success - keep at front and skip reordering
            return memory

        ranked = self._apply_policy_order(task)

        if self.initial_tier_selector and self.policy_engine.should_consult_llm(ranked):
            memory = memory or SiteMemory(site=task.site, page_pattern=task.page_pattern.value)
            self._apply_llm_tier(task, memory)
            self._apply_policy_order(task)

        return memory

    def resolve(self, task: CrawlTask) -> CrawlStrategy | None:
        return task.current_strategy()

    def reprioritize_after_failure(
        self, task: CrawlTask, block_type: str, waf_type: str = "",
        js_challenge: bool = False, captcha_type: str = ""
    ) -> None:
        if task.current_index >= len(task.strategies) - 1:
            return
        failed_strategy = task.current_strategy()
        remaining = task.strategies[task.current_index + 1 :]
        candidates = [PolicyCandidate.from_strategy(task, strategy) for strategy in remaining]

        if self.strategy_mode == "minimal_sufficient":
            filtered = self.policy_engine.filter_candidates_for_reprioritization(
                task, candidates, block_type, waf_type, js_challenge, captcha_type
            )
            if not filtered:
                return
            filtered_strategies = []
            for fc in filtered:
                for strategy in remaining:
                    if strategy.render.value == fc.render and strategy.proxy.value == fc.proxy:
                        filtered_strategies.append(strategy)
                        break
            if not filtered_strategies:
                return
            task.strategies = task.strategies[: task.current_index + 1] + filtered_strategies
        else:
            ranked = self.policy_engine.rank_candidates_for_failure(
                task,
                candidates,
                block_type,
                failed_strategy.render.value if failed_strategy else "",
                waf_type,
                js_challenge,
                captcha_type,
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
                    getattr(strategy, "use_interactive_search", False),
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
                    score.candidate.use_interactive_search,
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
            self._llm_render_bonuses = self._tier_to_render_bonuses(llm_tier)
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
            self._llm_render_bonuses = self._tier_to_render_bonuses(cached_tier)
            task.strategies = CrawlStrategy.get_tier_strategies(cached_tier, end_tier=9)
            task.metadata["start_tier"] = cached_tier

    @staticmethod
    def _enforce_minimum_start_tier(task: CrawlTask, tier: int) -> int:
        tier5_sites = {"homedepot", "lowes", "wayfair", "walmart", "fivebelow", "acehardware"}
        if task.site in tier5_sites and task.page_pattern == PagePattern.SEARCH:
            return max(tier, 5)
        if task.site == "amazon" and task.page_pattern == PagePattern.SEARCH:
            return max(tier, get_site_tier(task.site, task.page_pattern))
        return tier

    def _tier_to_render_bonuses(self, recommended_tier: int) -> dict[str, float]:
        TIER_RENDER_MAP = {
            1: "none",
            2: "cloudscraper",
            3: "lightpand",
            4: "playwright",
            5: "camoufox",
            6: "cloudera",
            7: "cloakbrowser",
        }
        bonuses = {}
        base_bonus = 20.0
        recommended_render = TIER_RENDER_MAP.get(recommended_tier, "")

        for tier, render in TIER_RENDER_MAP.items():
            if tier == recommended_tier:
                bonuses[render] = base_bonus
            elif tier > recommended_tier:
                distance = tier - recommended_tier
                bonuses[render] = max(0, base_bonus - distance * 5)
            else:
                distance = recommended_tier - tier
                bonuses[render] = max(0, base_bonus - distance * 5)
        return bonuses

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

        if self.strategy_mode == "minimal_sufficient":
            picked = self.policy_engine.pick_minimal_sufficient(task, candidates, None)
            if picked is None:
                return []
            by_key = {
                (
                    getattr(strategy, "tier", 1),
                    strategy.render.value,
                    strategy.proxy.value,
                    strategy.use_cookies,
                    strategy.change_ua,
                    strategy.use_human_scroll,
                    getattr(strategy, "use_interactive_search", False),
                ): strategy
                for strategy in task.strategies
            }
            picked_strategy = by_key.get((
                picked.tier,
                picked.render,
                picked.proxy,
                picked.use_cookies,
                picked.change_ua,
                picked.use_human_scroll,
                picked.use_interactive_search,
            ))
            if picked_strategy:
                remaining = [s for s in task.strategies if s != picked_strategy]
                task.strategies = [picked_strategy] + remaining
            return []

        ranked = self.policy_engine.rank_candidates(
            task, candidates, llm_bonuses=self._llm_render_bonuses if self._llm_render_bonuses else None
        )
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
                getattr(strategy, "use_interactive_search", False),
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
                score.candidate.use_interactive_search,
            )
            strategy = by_key.get(key)
            if strategy is not None and strategy not in reordered:
                reordered.append(strategy)

        for strategy in task.strategies:
            if strategy not in reordered:
                reordered.append(strategy)
        task.strategies = reordered
        return ranked
