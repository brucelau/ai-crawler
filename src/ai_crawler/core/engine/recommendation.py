from __future__ import annotations

from ai_crawler.core.types import CrawlStrategy, CrawlTask, ProxyType, RenderType


class DSPyStrategyRecommender:
    def __init__(self, dspy_model=None):
        self.dspy_model = dspy_model

    def recommend(self, task: CrawlTask, block_type: str, snippet: str) -> CrawlStrategy | None:
        if not self.dspy_model:
            return None
        try:
            result = self.dspy_model(
                site=task.site,
                page_pattern=task.page_pattern.value,
                block_type=block_type,
                response_snippet=snippet,
                attempt_history=[],
            )
            return self._result_to_strategy(result)
        except Exception:
            return None

    @staticmethod
    def _result_to_strategy(result) -> CrawlStrategy:
        proxy_map = {
            "thordata_us": ProxyType.THORDATA_US,
            "thordata_us_city": ProxyType.THORDATA_US_CITY,
            "thordata_any": ProxyType.THORDATA_ANY,
            "thordata_dedicated": ProxyType.THORDATA_DEDICATED,
        }
        render_map = {
            "none": RenderType.NONE,
            "playwright": RenderType.PLAYWRIGHT,
            "camoufox": RenderType.CAMOUFOX,
            "kameleo": RenderType.KAMELEO,
        }
        recommended = result.recommended_strategy
        return CrawlStrategy(
            proxy=proxy_map.get(
                recommended.get("proxy", "thordata_dedicated"), ProxyType.THORDATA_DEDICATED
            ),
            render=render_map.get(recommended.get("render", "none"), RenderType.NONE),
            change_ua=recommended.get("change_ua", False),
            use_cookies=recommended.get("use_cookies", False),
            use_human_scroll=recommended.get("use_human_scroll", False),
        )
