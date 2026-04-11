from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from enum import Enum


class ProxyType(Enum):
    THORDATA_US = "thordata_us"
    THORDATA_US_CITY = "thordata_us_city"
    THORDATA_ANY = "thordata_any"
    THORDATA_DEDICATED = "thordata_dedicated"


class RenderType(Enum):
    NONE = "none"
    PLAYWRIGHT = "playwright"
    CAMOUFOX = "camoufox"
    CLOAKBROWSER = "cloakbrowser"
    CLOUDERA = "cloudflare_uc"
    CLOUDSCRAPER = "cloudscraper"
    SELENIUMBASE = "seleniumbase"
    KAMELEO = "kameleo"


class TierSystem(Enum):
    TIER_1 = 1  # curl_cffi - fastest, simplest
    TIER_2 = 2  # cloudscraper - simple anti-bot
    TIER_3 = 3  # Playwright - full browser
    TIER_4 = 4  # Camoufox - fingerprint-aware Firefox
    TIER_5 = 5  # undetected-chromedriver - Cloudflare specialist
    TIER_6 = 6  # SeleniumBase - maximum stealth
    TIER_7 = 7  # CloakBrowser - C++ patched Chromium, ultimate stealth
    TIER_8 = 8  # Kameleo - fingerprint browser, highest tier


TIER_CONFIGS: dict[int, dict] = {
    1: {
        "render": RenderType.NONE,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (2, 5),
        "use_human_scroll": False,
        "change_ua": False,
        "use_cookies": False,
    },
    2: {
        "render": RenderType.CLOUDSCRAPER,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (3, 6),
        "use_human_scroll": False,
        "change_ua": False,
        "use_cookies": True,
    },
    3: {
        "render": RenderType.PLAYWRIGHT,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (3, 8),
        "use_human_scroll": True,
        "change_ua": False,
        "use_cookies": False,
    },
    4: {
        "render": RenderType.CAMOUFOX,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (3, 8),
        "use_human_scroll": True,
        "change_ua": True,
        "use_cookies": True,
    },
    5: {
        "render": RenderType.CLOUDERA,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (5, 10),
        "use_human_scroll": True,
        "change_ua": True,
        "use_cookies": True,
    },
    6: {
        "render": RenderType.SELENIUMBASE,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (5, 10),
        "use_human_scroll": True,
        "change_ua": True,
        "use_cookies": True,
    },
    7: {
        "render": RenderType.CLOAKBROWSER,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (5, 10),
        "use_human_scroll": True,
        "change_ua": True,
        "use_cookies": True,
    },
    8: {
        "render": RenderType.KAMELEO,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (8, 15),
        "use_human_scroll": True,
        "change_ua": True,
        "use_cookies": True,
    },
}


@dataclass
class CrawlStrategy:
    tier: int = 1
    proxy: ProxyType = ProxyType.THORDATA_DEDICATED
    render: RenderType = RenderType.NONE
    delay_before: tuple[float, float] = (0, 0)
    delay_after: tuple[float, float] = (3.0, 8.0)
    use_cookies: bool = False
    use_human_scroll: bool = False
    change_ua: bool = False
    wait_selector: str | None = None
    extra_wait: float = 0.0
    proxy_country: str | None = None
    proxy_city: str | None = None

    @classmethod
    def from_tier(cls, tier: int, **overrides) -> "CrawlStrategy":
        resolved_tier = tier if tier in TIER_CONFIGS else 1
        config = TIER_CONFIGS[resolved_tier]
        return cls(
            tier=resolved_tier,
            proxy=config["proxy"],
            render=config["render"],
            delay_after=config["delay_after"],
            use_human_scroll=config["use_human_scroll"],
            change_ua=config["change_ua"],
            use_cookies=config["use_cookies"],
            **overrides,
        )

    @classmethod
    def get_tier_strategies(cls, start_tier: int, end_tier: int = 6) -> list["CrawlStrategy"]:
        return [cls.from_tier(t) for t in range(start_tier, end_tier + 1)]


class PagePattern(Enum):
    SEARCH = "search"
    DETAIL = "detail"
    SELLER = "seller"
    REVIEW = "review"
    HOME = "home"
    UNKNOWN = "unknown"


SITE_TIER_DEFAULTS: dict[str, dict[PagePattern, int]] = {
    "amazon": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 3,
        PagePattern.REVIEW: 3,
    },
    "walmart": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 3,
    },
    "target": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 2,
    },
    "ebay": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 2,
    },
    "menards": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 3,
    },
    "lowes": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 2,
    },
    "homedepot": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 2,
    },
    "acehardware": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 2,
    },
    "wayfair": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 2,
    },
    "michaels": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 2,
    },
    "temu": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 1,
    },
    "etsy": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 2,
    },
    "bestbuy": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 2,
    },
    "costco": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 2,
    },
    "qvc": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 2,
    },
    "kohls": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 2,
    },
    "mercadolibre": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 2,
    },
    "walmartmexico": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 2,
    },
    "intexcorp": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 2,
    },
    "meijer": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 2,
    },
    "fivebelow": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 1,
    },
    "samsclub": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 2,
    },
    "bunnings": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 2,
    },
    "dollargeneral": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 1,
    },
    "action": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 1,
    },
    "academy": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 2,
    },
    "wowsports": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 1,
    },
    "coppel": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 2,
    },
    "aosom": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 1,
    },
    "familydollar": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 1,
    },
    "costway": {
        PagePattern.SEARCH: 6,
        PagePattern.DETAIL: 1,
    },
}


def get_site_tier(site: str, page_pattern: PagePattern) -> int:
    if site in SITE_TIER_DEFAULTS:
        site_tiers = SITE_TIER_DEFAULTS[site]
        if page_pattern in site_tiers:
            return site_tiers[page_pattern]
        if PagePattern.UNKNOWN in site_tiers:
            return site_tiers[PagePattern.UNKNOWN]
    return 1


URL_PATTERNS: dict[str, dict[PagePattern, list[CrawlStrategy]]] = {
    "amazon": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.CLOUDERA,
                use_cookies=True,
                change_ua=True,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(8, 15)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                change_ua=True,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.CAMOUFOX,
                use_cookies=True,
                change_ua=True,
                use_human_scroll=True,
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.SELLER: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.REVIEW: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 6)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "walmart": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.CLOUDERA,
                use_cookies=True,
                change_ua=True,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, use_cookies=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
        ],
    },
    "target": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.SELENIUMBASE,
                use_cookies=True,
                change_ua=True,
                use_human_scroll=True,
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
        ],
    },
    "ebay": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 6)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.SELENIUMBASE,
                use_cookies=True,
                change_ua=True,
                use_human_scroll=True,
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 4)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
        ],
    },
    "menards": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "lowes": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "homedepot": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "acehardware": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "wayfair": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "michaels": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "temu": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "etsy": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "bestbuy": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "costco": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "qvc": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "kohls": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "mercadolibre": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "walmartmexico": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "intexcorp": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "meijer": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "fivebelow": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "samsclub": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "bunnings": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "dollargeneral": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "action": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "academy": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "wowsports": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "coppel": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "aosom": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "familydollar": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "costway": {
        PagePattern.SEARCH: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlStrategy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlStrategy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
}


class PatternMatcher:
    PATTERNS: dict[str, dict[PagePattern, list[str]]] = {
        "amazon": {
            PagePattern.SEARCH: [r"/s\?", r"/s/\?", r"/gp/search", r"/hw/shop"],
            PagePattern.DETAIL: [r"/dp/[A-Z0-9]{10}", r"/gp/product/", r"/dp/"],
            PagePattern.SELLER: [r"/stores/", r"/sp/", r"/sell/"],
            PagePattern.REVIEW: [r"/product-reviews/", r"/gp/aw/review/", r"/hz/r/cr/"],
        },
        "walmart": {
            PagePattern.SEARCH: [r"/search\?", r"/search\.php"],
            PagePattern.DETAIL: [r"/ip/[A-Za-z0-9\-]+/\d+", r"/-/ip/"],
            PagePattern.SELLER: [r"/seller/", r"/store/"],
        },
        "target": {
            PagePattern.SEARCH: [r"/s\?", r"/search\?"],
            PagePattern.DETAIL: [r"/-/A-", r"/p/", r"/A-"],
            PagePattern.SELLER: [r"/store/", r"/sl/"],
        },
        "ebay": {
            PagePattern.SEARCH: [r"/sch/i\.html", r"/sch/"],
            PagePattern.DETAIL: [r"/itm/\d+", r"/itm/[A-Za-z0-9\-]+\d{9,}"],
            PagePattern.SELLER: [r"/str/", r"/usr/", r"/seller/"],
        },
        "menards": {
            PagePattern.SEARCH: [r"/search\.html", r"/search\.php"],
            PagePattern.DETAIL: [r"/p/", r"/-/p/"],
        },
        "lowes": {
            PagePattern.SEARCH: [r"/search\?", r"/search\.html"],
            PagePattern.DETAIL: [r"/p/", r"/product/"],
        },
        "homedepot": {
            PagePattern.SEARCH: [r"/search\?", r"/search\.html", r"/catalog/search"],
            PagePattern.DETAIL: [r"/p/", r"/ip/"],
        },
        "acehardware": {
            PagePattern.SEARCH: [r"/search\?", r"/search\.html"],
            PagePattern.DETAIL: [r"/product/", r"/p/"],
        },
        "wayfair": {
            PagePattern.SEARCH: [r"/keyword\.php", r"/a/s/", r"/search"],
            PagePattern.DETAIL: [r"/a/s/", r"/p/"],
        },
        "michaels": {
            PagePattern.SEARCH: [r"/search\?", r"/search\.html"],
            PagePattern.DETAIL: [r"/p/", r"/product/"],
        },
        "temu": {
            PagePattern.SEARCH: [r"/search\?", r"/goods/"],
            PagePattern.DETAIL: [r"/p/", r"/goods/"],
        },
        "etsy": {
            PagePattern.SEARCH: [r"/search\?", r"/listing/"],
            PagePattern.DETAIL: [r"/listing/"],
        },
        "bestbuy": {
            PagePattern.SEARCH: [r"/site/.*search\?", r"/search\?"],
            PagePattern.DETAIL: [r"/site/.*\.p\?"],
        },
        "costco": {
            PagePattern.SEARCH: [r"\.costco\.com/.*search", r"\.costco\.com/c/"],
            PagePattern.DETAIL: [r"\.costco\.com/.*product\.html"],
        },
        "qvc": {
            PagePattern.SEARCH: [r"\.qvc\.com/[^/]*\?.*search", r"\.qvc\.com/[^/]*/search"],
            PagePattern.DETAIL: [r"\.qvc\.com/[^/]*/p/"],
        },
        "kohls": {
            PagePattern.SEARCH: [r"\.kohls\.com/search\.jhtml", r"\.kohls\.com/catalog/"],
            PagePattern.DETAIL: [r"\.kohls\.com/p/"],
        },
        "mercadolibre": {
            PagePattern.SEARCH: [
                r"\.mercadolibre\.com\.\w+/search",
                r"\.mercadolibre\.com\.\w+/juguetes",
            ],
            PagePattern.DETAIL: [r"\.mercadolibre\.com\.\w+/p/"],
        },
        "walmartmexico": {
            PagePattern.SEARCH: [
                r"\.walmartmexico\.com\.mx/.*search",
                r"\.walmartmexico\.com\.mx/c/",
            ],
            PagePattern.DETAIL: [r"\.walmartmexico\.com\.mx/.*p/"],
        },
        "intexcorp": {
            PagePattern.SEARCH: [r"\.intexcorp\.com/.*search", r"\.intexcorp\.com/store"],
            PagePattern.DETAIL: [r"\.intexcorp\.com/.*product/"],
        },
        "meijer": {
            PagePattern.SEARCH: [r"\.meijer\.com/.*search", r"\.meijer\.com/shop"],
            PagePattern.DETAIL: [r"\.meijer\.com/p/"],
        },
        "fivebelow": {
            PagePattern.SEARCH: [r"\.fivebelow\.com/.*search", r"\.fivebelow\.com/collections"],
            PagePattern.DETAIL: [r"\.fivebelow\.com/p/"],
        },
        "samsclub": {
            PagePattern.SEARCH: [r"\.samsclub\.com/.*search", r"\.samsclub\.com/c/"],
            PagePattern.DETAIL: [r"\.samsclub\.com/p/"],
        },
        "bunnings": {
            PagePattern.SEARCH: [
                r"\.bunnings\.com\.au/.*search",
                r"\.bunnings\.com\.au/.*products",
            ],
            PagePattern.DETAIL: [r"\.bunnings\.com\.au/product/"],
        },
        "dollargeneral": {
            PagePattern.SEARCH: [
                r"\.dollargeneral\.com/.*search",
                r"\.dollargeneral\.com/.*products",
            ],
            PagePattern.DETAIL: [r"\.dollargeneral\.com/p/"],
        },
        "action": {
            PagePattern.SEARCH: [r"\.action\.com/.*search", r"\.action\.com/.*products"],
            PagePattern.DETAIL: [r"\.action\.com/product/"],
        },
        "academy": {
            PagePattern.SEARCH: [r"\.academy\.com/.*search", r"\.academy\.com/.*products"],
            PagePattern.DETAIL: [r"\.academy\.com/p/"],
        },
        "wowsports": {
            PagePattern.SEARCH: [r"wowsports\.com/.*search", r"wowsports\.com/.*products"],
            PagePattern.DETAIL: [r"wowsports\.com/.*product/"],
        },
        "coppel": {
            PagePattern.SEARCH: [r"\.coppel\.com/.*search", r"\.coppel\.com/.*products"],
            PagePattern.DETAIL: [r"\.coppel\.com/product/"],
        },
        "aosom": {
            PagePattern.SEARCH: [r"\.aosom\.com/.*search", r"\.aosom\.com/.*products"],
            PagePattern.DETAIL: [r"\.aosom\.com/.*product/"],
        },
        "familydollar": {
            PagePattern.SEARCH: [
                r"\.familydollar\.com/.*search",
                r"\.familydollar\.com/.*products",
            ],
            PagePattern.DETAIL: [r"\.familydollar\.com/p/"],
        },
        "costway": {
            PagePattern.SEARCH: [r"\.costway\.com/.*search", r"\.costway\.com/.*products"],
            PagePattern.DETAIL: [r"\.costway\.com/.*product/"],
        },
    }

    @classmethod
    def detect(cls, site: str, url: str) -> PagePattern:
        site_patterns = cls.PATTERNS.get(site, {})
        for pattern_enum, regex_list in site_patterns.items():
            for regex in regex_list:
                if re.search(regex, url, re.IGNORECASE):
                    return pattern_enum
        return PagePattern.UNKNOWN


@dataclass
class CrawlTask:
    url: str
    site: str
    page_pattern: PagePattern = PagePattern.UNKNOWN
    strategies: list[CrawlStrategy] = field(default_factory=list)
    current_index: int = 0
    fail_count: int = 0
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    metadata: dict = field(default_factory=dict)

    @classmethod
    def create(cls, url: str, site: str) -> "CrawlTask":
        pattern = PatternMatcher.detect(site, url)
        strategies = URL_PATTERNS.get(site, {}).get(
            pattern, URL_PATTERNS.get(site, {}).get(PagePattern.UNKNOWN, [])
        )
        if not strategies:
            strategies = [CrawlStrategy()]
        return cls(url=url, site=site, page_pattern=pattern, strategies=list(strategies))

    @classmethod
    def create_from_tier(
        cls,
        url: str,
        site: str,
        page_pattern: PagePattern | None = None,
    ) -> "CrawlTask":
        if page_pattern is None:
            page_pattern = PatternMatcher.detect(site, url)
        start_tier = get_site_tier(site, page_pattern)
        strategies = CrawlStrategy.get_tier_strategies(start_tier, end_tier=8)
        return cls(
            url=url,
            site=site,
            page_pattern=page_pattern,
            strategies=strategies,
            metadata={"start_tier": start_tier, "page_pattern": page_pattern.value},
        )

    def current_strategy(self) -> CrawlStrategy | None:
        if self.current_index >= len(self.strategies):
            return None
        return self.strategies[self.current_index]

    def exhausted(self) -> bool:
        return self.current_index >= len(self.strategies)

    def advance(self) -> None:
        self.current_index += 1

    def add_strategy_front(self, strategy: CrawlStrategy) -> None:
        if self.current_index > 0:
            self.strategies.insert(self.current_index, strategy)
        else:
            self.strategies.insert(0, strategy)

    def reset(self) -> None:
        self.current_index = 0
        self.fail_count = 0

    def attempt_summary(self) -> dict:
        return {
            "task_id": self.task_id,
            "url": self.url,
            "site": self.site,
            "pattern": self.page_pattern.value,
            "current_index": self.current_index,
            "total_strategies": len(self.strategies),
            "fail_count": self.fail_count,
        }
