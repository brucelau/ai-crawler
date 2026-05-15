from pydantic import BaseModel, Field


class SelectorResult(BaseModel):
    site: str = ""
    page_type: str = "search"
    list_container: str = Field(default="", description="CSS selector for product list container")
    product_selector: str = Field(
        default="", description="CSS selector for individual product items"
    )
    title_selector: str = Field(default="", description="CSS selector for product title")
    price_selector: str = Field(
        default="", description="CSS selector for product price (integer part)"
    )
    price_fraction_selector: str = Field(
        default="", description="CSS selector for price decimal/fraction part"
    )
    image_selector: str = Field(default="", description="CSS selector for product image")
    rating_selector: str = Field(default="", description="CSS selector for rating")
    review_count_selector: str = Field(default="", description="CSS selector for review count")
    link_selector: str = Field(default="", description="CSS selector for product link")
    product_id_attribute: str = Field(
        default="", description="Attribute name containing product ID if any"
    )


class BlockResult(BaseModel):
    block_type: str = Field(
        default="unknown",
        description="none, http_403, http_429, http_451, http_timeout, captcha, cloudflare, bot_detected, empty_response, unknown",
    )
    reasoning: str = Field(default="", description="1-2 sentences explaining the classification")
    suggested_action: str = Field(
        default="retry_same",
        description="retry_same, retry_with_different_proxy, retry_with_browser, skip, escalate",
    )


class ThresholdResult(BaseModel):
    request_timeout: float = Field(
        default=30.0, description="Recommended request timeout in seconds"
    )
    page_load_timeout: float = Field(
        default=30.0, description="Recommended page load timeout in seconds"
    )
    delay_after: list[float] = Field(
        default=[3, 8], description="[min, max] delay between requests in seconds"
    )
    reasoning: str = Field(default="", description="Explanation for the recommended values")


class URLDiscoveryResult(BaseModel):
    site: str = ""
    search_url_pattern: str = Field(
        default="", description="Full search URL pattern with {query} placeholder"
    )
    search_param: str = Field(default="q", description="Search parameter name")
    page_param: str = Field(default="page", description="Pagination parameter name")
    product_url_pattern: str = Field(
        default="", description="Product URL pattern with {id} placeholder"
    )
    uses_js_rendering: bool = Field(
        default=True, description="Whether search results use JavaScript rendering"
    )


class HumanBehaviorResult(BaseModel):
    scroll_strategy: str = Field(default="mixed", description="gradual, burst, or mixed")
    scroll_phases: list[dict] = Field(
        default=[],
        description="List of scroll phases with start_y, end_y, speed, pause_after, optional hover",
    )
    reasoning: str = Field(default="", description="Why a human would browse this way")


def validate_selector(raw: dict) -> SelectorResult:
    try:
        return SelectorResult(**raw)
    except Exception:
        return SelectorResult(site=raw.get("site", ""))


def validate_block(raw: dict) -> BlockResult:
    try:
        return BlockResult(**raw)
    except Exception:
        return BlockResult(
            block_type=raw.get("block_type", "unknown"),
            reasoning=raw.get("reasoning", ""),
            suggested_action=raw.get("suggested_action", "retry_same"),
        )


def validate_threshold(raw: dict) -> ThresholdResult:
    try:
        delay = raw.get("delay_after", [3, 8])
        if isinstance(delay, str):
            import json

            delay = json.loads(delay)
        return ThresholdResult(
            request_timeout=float(raw.get("request_timeout", 30.0)),
            page_load_timeout=float(raw.get("page_load_timeout", 30.0)),
            delay_after=list(delay) if delay else [3, 8],
            reasoning=raw.get("reasoning", ""),
        )
    except Exception:
        return ThresholdResult()


def validate_url_discovery(raw: dict) -> URLDiscoveryResult:
    try:
        return URLDiscoveryResult(**raw)
    except Exception:
        return URLDiscoveryResult(
            site=raw.get("site", ""),
            search_url_pattern=raw.get("search_url_pattern", ""),
            search_param=raw.get("search_param", "q"),
            page_param=raw.get("page_param", "page"),
            product_url_pattern=raw.get("product_url_pattern", ""),
            uses_js_rendering=raw.get("uses_js_rendering", True),
        )


def validate_human_behavior(raw: dict) -> HumanBehaviorResult:
    try:
        phases = raw.get("scroll_phases", [])
        if isinstance(phases, str):
            import json

            phases = json.loads(phases)
        return HumanBehaviorResult(
            scroll_strategy=raw.get("scroll_strategy", "mixed"),
            scroll_phases=phases if isinstance(phases, list) else [],
            reasoning=raw.get("reasoning", ""),
        )
    except Exception:
        return HumanBehaviorResult()
