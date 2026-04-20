"""Core types - enums and CrawlStrategy dataclass.

This module contains the base types used across the crawler:
- ProxyType, RenderType, TierSystem enums
- CrawlStrategy dataclass with tier-based factory methods

Moved from strategy.py to break circular import with config/sites.py.
"""

from __future__ import annotations

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
    CLOUDSCRAPER = "cloudscraper"
    LIGHTPAND = "lightpand"
    PLAYWRIGHT = "playwright"
    CAMOUFOX = "camoufox"
    CLOAKBROWSER = "cloakbrowser"
    CLOUDERA = "cloudflare_uc"
    SELENIUMBASE = "seleniumbase"
    KAMELEO = "kameleo"


class TierSystem(Enum):
    TIER_1 = 1  # curl_cffi - fastest, simplest
    TIER_2 = 2  # cloudscraper - simple anti-bot
    TIER_3 = 3  # Lightpanda - lightweight browser, sub-100ms startup, JS rendering
    TIER_4 = 4  # Playwright - full browser
    TIER_5 = 5  # Camoufox - fingerprint-aware Firefox
    TIER_6 = 6  # undetected-chromedriver - Cloudflare specialist
    TIER_7 = 7  # SeleniumBase - maximum stealth
    TIER_8 = 8  # CloakBrowser - C++ patched Chromium, ultimate stealth
    TIER_9 = 9  # [DEPRECATED] Kameleo - fingerprint browser, highest tier


DEPRECATED_TIERS = {9}


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
        "render": RenderType.LIGHTPAND,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (2, 5),
        "use_human_scroll": True,
        "change_ua": False,
        "use_cookies": False,
    },
    4: {
        "render": RenderType.PLAYWRIGHT,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (3, 8),
        "use_human_scroll": True,
        "change_ua": False,
        "use_cookies": False,
    },
    5: {
        "render": RenderType.CAMOUFOX,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (3, 8),
        "use_human_scroll": True,
        "change_ua": True,
        "use_cookies": True,
    },
    6: {
        "render": RenderType.CLOUDERA,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (5, 10),
        "use_human_scroll": True,
        "change_ua": True,
        "use_cookies": True,
    },
    7: {
        "render": RenderType.SELENIUMBASE,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (5, 10),
        "use_human_scroll": True,
        "change_ua": True,
        "use_cookies": True,
    },
    8: {
        "render": RenderType.CLOAKBROWSER,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (5, 10),
        "use_human_scroll": True,
        "change_ua": True,
        "use_cookies": True,
    },
    9: {
        "render": RenderType.KAMELEO,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (8, 15),
        "use_human_scroll": True,
        "change_ua": True,
        "use_cookies": True,
    },
}


class PagePattern(Enum):
    SEARCH = "search"
    DETAIL = "detail"
    SELLER = "seller"
    REVIEW = "review"
    HOME = "home"
    UNKNOWN = "unknown"


@dataclass
class CrawlStrategy:
    tier: int = 1
    proxy: ProxyType = ProxyType.THORDATA_DEDICATED
    render: RenderType = RenderType.NONE
    delay_before: tuple[float, float] = (0, 0)
    delay_after: tuple[float, float] = (3.0, 8.0)
    use_cookies: bool = False
    use_human_scroll: bool = False
    use_interactive_search: bool = False
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
    def get_tier_strategies(cls, start_tier: int, end_tier: int = 9) -> list["CrawlStrategy"]:
        return [cls.from_tier(t) for t in range(start_tier, end_tier + 1)]


__all__ = [
    "ProxyType",
    "RenderType",
    "TierSystem",
    "DEPRECATED_TIERS",
    "TIER_CONFIGS",
    "PagePattern",
    "CrawlStrategy",
]
