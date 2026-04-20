"""自动策略生成器 - 基于历史数据动态生成策略池

不再依赖 URL_PATTERNS 硬编码，而是动态生成所有可能的策略组合，
然后通过 PolicyEngine 基于历史 trace 打分排序，取 top-N 作为预置策略。
"""

from __future__ import annotations

from typing import Iterator

from ai_crawler.core.types import CrawlStrategy, ProxyType, RenderType
from ai_crawler.core.strategy import PagePattern
from ai_crawler.core.engine.policy_engine import PolicyCandidate, PolicyEngine, PolicyStatsStore


class StrategyGenerator:
    """自动策略生成器"""

    RENDER_ORDER = [
        RenderType.NONE,
        RenderType.CLOUDSCRAPER,
        RenderType.LIGHTPAND,
        RenderType.PLAYWRIGHT,
        RenderType.CAMOUFOX,
        RenderType.CLOUDERA,
        RenderType.SELENIUMBASE,
        RenderType.CLOAKBROWSER,
    ]

    PROXY_ORDER = [
        ProxyType.THORDATA_DEDICATED,
        ProxyType.THORDATA_US,
        ProxyType.THORDATA_US_CITY,
        ProxyType.THORDATA_ANY,
    ]

    RENDER_CONFIGS = {
        RenderType.NONE: {
            "change_ua": [False],
            "use_cookies": [False],
            "use_human_scroll": [False],
        },
        RenderType.CLOUDSCRAPER: {
            "change_ua": [False],
            "use_cookies": [True],
            "use_human_scroll": [False],
        },
        RenderType.LIGHTPAND: {
            "change_ua": [False],
            "use_cookies": [False],
            "use_human_scroll": [True],
        },
        RenderType.PLAYWRIGHT: {
            "change_ua": [False, True],
            "use_cookies": [False, True],
            "use_human_scroll": [True],
        },
        RenderType.CAMOUFOX: {
            "change_ua": [True],
            "use_cookies": [True],
            "use_human_scroll": [True],
        },
        RenderType.CLOUDERA: {
            "change_ua": [True],
            "use_cookies": [True],
            "use_human_scroll": [True],
        },
        RenderType.SELENIUMBASE: {
            "change_ua": [True],
            "use_cookies": [True],
            "use_human_scroll": [True],
        },
        RenderType.CLOAKBROWSER: {
            "change_ua": [True],
            "use_cookies": [True],
            "use_human_scroll": [True],
        },
    }

    RENDER_DELAYS = {
        RenderType.NONE: (2, 5),
        RenderType.CLOUDSCRAPER: (3, 6),
        RenderType.LIGHTPAND: (2, 5),
        RenderType.PLAYWRIGHT: (3, 8),
        RenderType.CAMOUFOX: (3, 8),
        RenderType.CLOUDERA: (5, 10),
        RenderType.SELENIUMBASE: (5, 10),
        RenderType.CLOAKBROWSER: (5, 10),
    }

    UC_SEARCH_ALLOWLIST = {"amazon"}

    @classmethod
    def generate_candidates(
        cls, site: str, page_pattern: str
    ) -> list[CrawlStrategy]:
        """生成所有可能的策略组合"""
        candidates = []

        for render in cls.RENDER_ORDER:
            configs = cls.RENDER_CONFIGS.get(render, {})

            change_ua_options = configs.get("change_ua", [False])
            use_cookies_options = configs.get("use_cookies", [False])
            use_human_scroll_options = configs.get("use_human_scroll", [False])

            for proxy in cls.PROXY_ORDER:
                for change_ua in change_ua_options:
                    for use_cookies in use_cookies_options:
                        for use_human_scroll in use_human_scroll_options:
                            if render == RenderType.NONE and use_human_scroll:
                                continue

                            if render == RenderType.CLOUDERA and page_pattern == "search":
                                if site not in cls.UC_SEARCH_ALLOWLIST:
                                    continue

                            candidates.append(
                                CrawlStrategy(
                                    render=render,
                                    proxy=proxy,
                                    change_ua=change_ua,
                                    use_cookies=use_cookies,
                                    use_human_scroll=use_human_scroll,
                                    delay_after=cls.RENDER_DELAYS.get(render, (3, 8)),
                                )
                            )

        return candidates

    @classmethod
    def _candidate_to_strategy(cls, candidate: PolicyCandidate) -> CrawlStrategy:
        """将 PolicyCandidate 转换为 CrawlStrategy"""
        proxy_map = {
            "thordata_dedicated": ProxyType.THORDATA_DEDICATED,
            "thordata_us": ProxyType.THORDATA_US,
            "thordata_us_city": ProxyType.THORDATA_US_CITY,
            "thordata_any": ProxyType.THORDATA_ANY,
        }
        render_map = {r.value: r for r in RenderType}

        return CrawlStrategy(
            tier=candidate.tier,
            proxy=proxy_map.get(candidate.proxy, ProxyType.THORDATA_DEDICATED),
            render=render_map.get(candidate.render, RenderType.NONE),
            change_ua=candidate.change_ua,
            use_cookies=candidate.use_cookies,
            use_human_scroll=candidate.use_human_scroll,
            use_interactive_search=candidate.use_interactive_search,
        )

    @classmethod
    def get_optimal_strategies(
        cls,
        site: str,
        page_pattern: str,
        policy_engine: PolicyEngine,
        top_n: int = 10,
    ) -> list[CrawlStrategy]:
        """基于 PolicyEngine 历史数据获取最优策略顺序"""

        candidates = cls.generate_candidates(site, page_pattern)

        class _FakeTask:
            def __init__(self):
                self.site = site
                self.page_pattern = type(
                    "PagePattern", (), {"value": page_pattern}
                )()

        fake_task = _FakeTask()
        policy_candidates = [
            PolicyCandidate.from_strategy(fake_task, c, source="auto")
            for c in candidates
        ]

        ranked = policy_engine.rank_candidates(fake_task, policy_candidates)

        return [cls._candidate_to_strategy(c.candidate) for c in ranked[:top_n]]

    @classmethod
    def get_default_strategies(
        cls, site: str, page_pattern: str
    ) -> list[CrawlStrategy]:
        """获取默认策略顺序（不依赖历史数据，按成本优先）"""

        candidates = cls.generate_candidates(site, page_pattern)

        def sort_key(s: CrawlStrategy) -> tuple[int, int]:
            render_order = cls.RENDER_ORDER.index(s.render)
            proxy_order = cls.PROXY_ORDER.index(s.proxy)
            return (render_order, proxy_order)

        return sorted(candidates, key=sort_key)


def policy_candidate_to_strategy(candidate: PolicyCandidate) -> CrawlStrategy:
    """将 PolicyCandidate 转换为 CrawlStrategy 的便捷函数"""
    return StrategyGenerator._candidate_to_strategy(candidate)
