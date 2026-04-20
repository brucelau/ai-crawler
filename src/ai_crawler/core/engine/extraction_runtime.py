from __future__ import annotations

from dataclasses import dataclass

from ai_crawler.core.extraction import ExtractionResult
from ai_crawler.core.strategy import CrawlStrategy, CrawlTask, RenderType


@dataclass(slots=True)
class ExtractionDecision:
    products: list
    should_retry: bool
    retry_reason: str | None = None
    strategy_name: str = "none"
    method: str = "none"
    metadata: dict | None = None


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
                return ExtractionDecision(
                    products=result.products,
                    should_retry=False,
                    strategy_name=template.site,
                    method=result.method,
                    metadata={"template_hit": True, "page_type": page_type},
                )
            invalidate_template(site, page_type)

        # 2. 无模板 或 模板失败 → UniversalExtractor 兜底
        universal = UniversalExtractor()
        result = universal.extract(
            page, html, task.url, page_type,
            intercepted_products=self._intercepted_products if self._intercepted_products else None,
        )

        if result.products:
            # 3. 兜底成功 → LLM 生成新模板
            new_template = llm_generate_template(site, page_type, html, result.products, page)
            if new_template:
                save_template(new_template)
            return ExtractionDecision(
                products=result.products,
                should_retry=False,
                strategy_name=result.strategy,
                method=result.method,
                metadata={"universal_hit": True, "page_type": page_type},
            )

        # 4. 兜底失败 → 升级渲染重试
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
            task.add_strategy_next(upgrade)
            return ExtractionDecision(
                products=[],
                should_retry=True,
                retry_reason="empty_content",
                strategy_name=result.strategy,
                method=result.method,
                metadata={"universal_failed": True, "page_type": page_type},
            )

        return ExtractionDecision(
            products=[],
            should_retry=False,
            strategy_name=result.strategy,
            method=result.method,
            metadata={"universal_failed": True, "page_type": page_type},
        )
