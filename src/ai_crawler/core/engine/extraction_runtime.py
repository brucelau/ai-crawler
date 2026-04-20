from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ai_crawler.core.extraction import ExtractionResult
from ai_crawler.core.strategy import CrawlStrategy, CrawlTask, RenderType


class ExtractionOutcomeType(Enum):
    """提取结果类型枚举 - 区分成功与不同类型的失败"""
    SUCCESS = "success"                    # 提取成功，有产品
    EMPTY_CONTENT = "empty_content"        # 页面加载成功但无产品
    TEMPLATE_INVALID = "template_invalid"  # 模板失效，需重新生成
    PARTIAL_CONTENT = "partial_content"    # 部分产品，可能需要升级
    EXTRACTION_ERROR = "extraction_error"  # 提取过程出错
    NO_MORE_STRATEGIES = "no_more_strategies"  # 所有策略用尽


@dataclass(slots=True)
class ExtractionDecision:
    """提取决策 - 包含结果类型和详细信息"""
    products: list
    outcome: ExtractionOutcomeType
    strategy_name: str = "none"
    method: str = "none"
    metadata: dict | None = None
    retry_strategy: CrawlStrategy | None = None  # 可选的重试策略（如升级渲染)


class ExtractionRuntimeService:
    def __init__(self, extraction_chains: dict[str, any]):
        self.extraction_chains = extraction_chains
        self._intercepted_products: list = []

    @staticmethod
    def _resolve_page_type(task: CrawlTask) -> str:
        page_type = getattr(task.page_pattern, "value", "unknown")
        if page_type and page_type != "unknown":
            return page_type
        goal = str(task.metadata.get("goal", "") or "")
        if goal == "reviews":
            return "review"
        return goal or "unknown"

    def _get_upgrade_render(self, strategy: CrawlStrategy) -> RenderType | None:
        upgrade_map = {
            RenderType.NONE: RenderType.CLOUDSCRAPER,
            RenderType.CLOUDSCRAPER: RenderType.LIGHTPAND,
            RenderType.LIGHTPAND: RenderType.PLAYWRIGHT,
            RenderType.PLAYWRIGHT: RenderType.CAMOUFOX,
            RenderType.CAMOUFOX: RenderType.CLOUDERA,
            RenderType.CLOUDERA: RenderType.SELENIUMBASE,
            RenderType.SELENIUMBASE: RenderType.CLOAKBROWSER,
        }
        return upgrade_map.get(strategy.render)

    def setup_api_intercept(self, page) -> None:
        """设置 API 拦截，捕获产品相关的 API 响应"""
        self._intercepted_products = []

        def handle_response(response):
            try:
                url = response.url.lower()
                if any(k in url for k in ["product", "search", "item", "goods", "listing"]):
                    if "json" in response.headers.get("content-type", ""):
                        data = response.json()
                        if data:
                            products = self._parse_api_response(data)
                            if products:
                                self._intercepted_products.extend(products)
            except Exception:
                pass

        page.on("response", handle_response)

    def _parse_api_response(self, data: dict) -> list:
        """从 API 响应中解析产品"""
        from ai_crawler.models.product import Product

        products = []
        items = None

        if isinstance(data, dict):
            result = data.get("result", {})
            if isinstance(result, dict):
                if "home_goods_list" in result:
                    items = result["home_goods_list"]
                elif "data" in result:
                    items = result["data"]
            if not items:
                if "data" in data:
                    items = data["data"]
                elif "products" in data:
                    items = data["products"]
                elif "items" in data:
                    items = data["items"]
                elif "results" in data:
                    items = data["results"]

        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    if item.get("type") == 0:
                        goods = item.get("data", {})
                        if goods:
                            title = goods.get("title", "")
                            price_info = goods.get("price_info", {})
                            image = goods.get("image", {})
                            link = goods.get("link_url", "")
                            
                            price = ""
                            if isinstance(price_info, dict):
                                price = price_info.get("price", "")
                            elif isinstance(price_info, str):
                                price = price_info
                                
                            img_url = ""
                            if isinstance(image, dict):
                                img_url = image.get("url", "")
                            elif isinstance(image, str):
                                img_url = image
                                
                            link_url = "https://www.temu.com/" + link if link else ""
                            
                            if title:
                                products.append(Product(
                                    source="api_intercept",
                                    url=link_url,
                                    title=title,
                                    price=str(price) if price else "",
                                    images=[img_url] if img_url else [],
                                ))
                    else:
                        title = item.get("title") or item.get("name") or item.get("goods_name", "")
                        if title:
                            price = ""
                            offers = item.get("offers") or item.get("price") or {}
                            if isinstance(offers, dict):
                                price = offers.get("price") or offers.get("salePrice") or ""
                            elif isinstance(offers, str):
                                price = offers

                            url = item.get("url") or item.get("link") or item.get("goods_url", "")
                            image = item.get("image") or item.get("img") or item.get("goods_image", "")
                            if isinstance(image, list) and image:
                                image = image[0]
                            if isinstance(image, dict):
                                image = image.get("url") or image.get("src", "")

                            products.append(Product(
                                source="api_intercept",
                                url=url,
                                title=title,
                                price=str(price) if price else "",
                                images=[image] if image else [],
                            ))

        return products

    def extract(
        self, task: CrawlTask, strategy: CrawlStrategy, page, html: str
    ) -> ExtractionDecision:
        from ai_crawler.core.extraction.template_based import (
            UniversalExtractor,
            get_template,
            save_template,
            invalidate_template,
            llm_generate_template,
        )

        page_type = self._resolve_page_type(task)
        site = task.site

        # 1. 有模板 → 用模板提取
        template = get_template(site, page_type)
        if template and template.is_valid:
            result = template.extract(page, html, task.url)
            if result.products:
                if len(result.products) >= 2:
                    return ExtractionDecision(
                        products=result.products,
                        outcome=ExtractionOutcomeType.SUCCESS,
                        strategy_name=template.site,
                        method=result.method,
                        metadata={"template_hit": True, "page_type": page_type},
                    )
                else:
                    invalidate_template(site, page_type)
                    return ExtractionDecision(
                        products=result.products,
                        outcome=ExtractionOutcomeType.PARTIAL_CONTENT,
                        strategy_name=template.site,
                        method=result.method,
                        metadata={"template_hit": True, "page_type": page_type, "product_count": len(result.products)},
                    )
            invalidate_template(site, page_type)
            return ExtractionDecision(
                products=[],
                outcome=ExtractionOutcomeType.TEMPLATE_INVALID,
                strategy_name=template.site,
                method=result.method,
                metadata={"template_hit": True, "page_type": page_type, "template_invalidated": True},
            )

        # 2. 无模板 或 模板失败 → UniversalExtractor 兜底
        universal = UniversalExtractor()
        result = universal.extract(
            page, html, task.url, page_type,
            intercepted_products=self._intercepted_products if self._intercepted_products else None,
        )

        if result.products:
            if len(result.products) >= 2:
                new_template = llm_generate_template(site, page_type, html, result.products, page)
                if new_template:
                    save_template(new_template)
                return ExtractionDecision(
                    products=result.products,
                    outcome=ExtractionOutcomeType.SUCCESS,
                    strategy_name=result.strategy,
                    method=result.method,
                    metadata={"universal_hit": True, "page_type": page_type},
                )
            else:
                return ExtractionDecision(
                    products=result.products,
                    outcome=ExtractionOutcomeType.PARTIAL_CONTENT,
                    strategy_name=result.strategy,
                    method=result.method,
                    metadata={"universal_hit": True, "page_type": page_type, "product_count": len(result.products)},
                )

        upgrade_render = self._get_upgrade_render(strategy)
        if upgrade_render:
            render_to_tier = {
                RenderType.NONE: 1,
                RenderType.CLOUDSCRAPER: 2,
                RenderType.LIGHTPAND: 3,
                RenderType.PLAYWRIGHT: 4,
                RenderType.CAMOUFOX: 5,
                RenderType.CLOUDERA: 6,
                RenderType.SELENIUMBASE: 7,
                RenderType.CLOAKBROWSER: 8,
            }
            upgrade_tier = render_to_tier.get(upgrade_render, 1)
            upgrade = CrawlStrategy.from_tier(upgrade_tier)
            return ExtractionDecision(
                products=[],
                outcome=ExtractionOutcomeType.EMPTY_CONTENT,
                strategy_name=result.strategy,
                method=result.method,
                metadata={"universal_failed": True, "page_type": page_type},
                retry_strategy=upgrade,
            )

        if not task.exhausted():
            return ExtractionDecision(
                products=[],
                outcome=ExtractionOutcomeType.EXTRACTION_ERROR,
                strategy_name=result.strategy,
                method=result.method,
                metadata={"universal_failed": True, "page_type": page_type},
            )

        return ExtractionDecision(
            products=[],
            outcome=ExtractionOutcomeType.NO_MORE_STRATEGIES,
            strategy_name=result.strategy,
            method=result.method,
            metadata={"universal_failed": True, "page_type": page_type},
        )
