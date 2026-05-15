"""Tests for CrawlStrategy and tier configuration."""

import pytest
from ai_crawler.spider.runtime.crawl import (
    CrawlPolicy,
    CrawlTask,
    PagePattern,
    ProxyType,
    RenderType,
    TierSystem,
    TIER_CONFIGS,
)
from ai_crawler.config.sites import SITE_TIER_DEFAULTS, get_site_tier


class TestRenderTypeEnum:
    """RenderType enum should have all expected values."""

    def test_render_types_defined(self):
        """All expected RenderType values exist."""
        assert RenderType.NONE.value == "none"
        assert RenderType.CLOUDSCRAPER.value == "cloudscraper"
        assert RenderType.LIGHTPAND.value == "lightpand"
        assert RenderType.PLAYWRIGHT.value == "playwright"
        assert RenderType.CAMOUFOX.value == "camoufox"
        assert RenderType.CLOAKBROWSER.value == "cloakbrowser"
        assert RenderType.CLOUDERA.value == "cloudflare_uc"
        assert RenderType.SELENIUMBASE.value == "seleniumbase"
        assert RenderType.KAMELEO.value == "kameleo"

    def test_render_types_count(self):
        """All 9 RenderType values are defined."""
        assert len(RenderType) == 9


class TestProxyTypeEnum:
    """ProxyType enum should have all expected values."""

    def test_proxy_types_defined(self):
        """All expected ProxyType values exist."""
        assert ProxyType.THORDATA_US.value == "thordata_us"
        assert ProxyType.THORDATA_US_CITY.value == "thordata_us_city"
        assert ProxyType.THORDATA_ANY.value == "thordata_any"
        assert ProxyType.THORDATA_DEDICATED.value == "thordata_dedicated"


class TestTierSystemEnum:
    """TierSystem enum should document all 9 tiers."""

    def test_tier_count(self):
        """All 9 tiers are defined."""
        assert len(TierSystem) == 9

    def test_tier_values(self):
        """Each tier has correct integer value."""
        assert TierSystem.TIER_1.value == 1
        assert TierSystem.TIER_2.value == 2
        assert TierSystem.TIER_3.value == 3
        assert TierSystem.TIER_4.value == 4
        assert TierSystem.TIER_5.value == 5
        assert TierSystem.TIER_6.value == 6
        assert TierSystem.TIER_7.value == 7
        assert TierSystem.TIER_8.value == 8
        assert TierSystem.TIER_9.value == 9


class TestTierConfigs:
    """TIER_CONFIGS should define all 8 active tiers correctly."""

    def test_all_tiers_defined(self):
        """All 9 active tiers have configurations."""
        assert len(TIER_CONFIGS) == 9

    def test_tier_1_config(self):
        """Tier 1 is NONE render with THORDATA_DEDICATED proxy."""
        cfg = TIER_CONFIGS[1]
        assert cfg["render"] == RenderType.NONE
        assert cfg["proxy"] == ProxyType.THORDATA_DEDICATED
        assert cfg["use_human_scroll"] is False
        assert cfg["change_ua"] is False
        assert cfg["use_cookies"] is False

    def test_tier_2_config(self):
        """Tier 2 is CLOUDSCRAPER render."""
        cfg = TIER_CONFIGS[2]
        assert cfg["render"] == RenderType.CLOUDSCRAPER
        assert cfg["proxy"] == ProxyType.THORDATA_DEDICATED
        assert cfg["use_cookies"] is True

    def test_tier_3_config(self):
        """Tier 3 is LIGHTPAND render."""
        cfg = TIER_CONFIGS[3]
        assert cfg["render"] == RenderType.LIGHTPAND
        assert cfg["proxy"] == ProxyType.THORDATA_DEDICATED
        assert cfg["use_human_scroll"] is True

    def test_tier_4_config(self):
        """Tier 4 is PLAYWRIGHT render."""
        cfg = TIER_CONFIGS[4]
        assert cfg["render"] == RenderType.PLAYWRIGHT
        assert cfg["proxy"] == ProxyType.THORDATA_DEDICATED
        assert cfg["use_human_scroll"] is True

    def test_tier_5_config(self):
        """Tier 5 is CAMOUFOX render."""
        cfg = TIER_CONFIGS[5]
        assert cfg["render"] == RenderType.CAMOUFOX
        assert cfg["proxy"] == ProxyType.THORDATA_DEDICATED
        assert cfg["change_ua"] is True

    def test_tier_6_config(self):
        """Tier 6 is CLOUDERA render."""
        cfg = TIER_CONFIGS[6]
        assert cfg["render"] == RenderType.CLOUDERA
        assert cfg["proxy"] == ProxyType.THORDATA_DEDICATED

    def test_tier_7_config(self):
        """Tier 7 is SELENIUMBASE render."""
        cfg = TIER_CONFIGS[7]
        assert cfg["render"] == RenderType.SELENIUMBASE
        assert cfg["proxy"] == ProxyType.THORDATA_DEDICATED

    def test_tier_8_config(self):
        """Tier 8 is CLOAKBROWSER render."""
        cfg = TIER_CONFIGS[8]
        assert cfg["render"] == RenderType.CLOAKBROWSER
        assert cfg["proxy"] == ProxyType.THORDATA_DEDICATED

    def test_all_tiers_have_delay(self):
        """All active tiers have delay_after configured (tier 9 deprecated)."""
        for tier in range(1, 9):
            assert "delay_after" in TIER_CONFIGS[tier]
            assert isinstance(TIER_CONFIGS[tier]["delay_after"], tuple)
            assert len(TIER_CONFIGS[tier]["delay_after"]) == 2


class TestCrawlStrategyFromTier:
    """CrawlStrategy.from_tier() should create correct strategy from tier config."""

    def test_from_tier_1(self):
        """Tier 1 strategy has correct defaults."""
        strategy = CrawlPolicy.from_tier(1)
        assert strategy.tier == 1
        assert strategy.render == RenderType.NONE
        assert strategy.proxy == ProxyType.THORDATA_DEDICATED

    def test_from_tier_4(self):
        """Tier 4 strategy has human scroll."""
        strategy = CrawlPolicy.from_tier(4)
        assert strategy.tier == 4
        assert strategy.render == RenderType.PLAYWRIGHT
        assert strategy.use_human_scroll is True

    def test_from_tier_8(self):
        """Tier 8 strategy is CloakBrowser."""
        strategy = CrawlPolicy.from_tier(8)
        assert strategy.tier == 8
        assert strategy.render == RenderType.CLOAKBROWSER
        assert strategy.use_human_scroll is True
        assert strategy.change_ua is True
        assert strategy.use_cookies is True

    def test_from_tier_with_overrides(self):
        """from_tier accepts overrides for any field."""
        strategy = CrawlPolicy.from_tier(3, wait_selector=".product")
        assert strategy.tier == 3
        assert strategy.render == RenderType.LIGHTPAND
        assert strategy.wait_selector == ".product"

    def test_from_tier_invalid_falls_back_to_1(self):
        """Invalid tier number falls back to tier 1 config."""
        strategy = CrawlPolicy.from_tier(99)
        assert strategy.tier == 1
        assert strategy.render == RenderType.NONE


class TestCrawlStrategyGetTierStrategies:
    """CrawlStrategy.get_tier_strategies() should return range of strategies."""

    def test_get_tier_strategies_single(self):
        """get_tier_strategies(3, 3) returns single strategy."""
        strategies = CrawlPolicy.get_tier_strategies(3, 3)
        assert len(strategies) == 1
        assert strategies[0].tier == 3

    def test_get_tier_strategies_range(self):
        """get_tier_strategies(3, 5) returns 3 strategies."""
        strategies = CrawlPolicy.get_tier_strategies(3, 5)
        assert len(strategies) == 3
        assert [s.tier for s in strategies] == [3, 4, 5]

    def test_get_tier_strategies_all_9(self):
        """get_tier_strategies(1, 9) returns all 9 strategies."""
        strategies = CrawlPolicy.get_tier_strategies(1, 9)
        assert len(strategies) == 9
        assert [s.tier for s in strategies] == [1, 2, 3, 4, 5, 6, 7, 8, 9]


class TestSiteTierDefaults:
    """SITE_TIER_DEFAULTS should define tiers for major e-commerce sites."""

    def test_amazon_defined(self):
        """Amazon has tier defaults."""
        assert "amazon" in SITE_TIER_DEFAULTS
        assert PagePattern.SEARCH in SITE_TIER_DEFAULTS["amazon"]
        assert PagePattern.DETAIL in SITE_TIER_DEFAULTS["amazon"]

    def test_amazon_search_uses_tier_7(self):
        """Amazon SEARCH defaults to tier 7."""
        assert SITE_TIER_DEFAULTS["amazon"][PagePattern.SEARCH] == 7

    def test_amazon_detail_uses_tier_4(self):
        """Amazon DETAIL defaults to tier 4."""
        assert SITE_TIER_DEFAULTS["amazon"][PagePattern.DETAIL] == 4

    def test_walmart_search_uses_tier_7(self):
        """Walmart SEARCH defaults to tier 7."""
        assert SITE_TIER_DEFAULTS["walmart"][PagePattern.SEARCH] == 7

    def test_target_detail_uses_tier_3(self):
        """Target DETAIL defaults to tier 3."""
        assert SITE_TIER_DEFAULTS["target"][PagePattern.DETAIL] == 3

    def test_multiple_sites_defined(self):
        """Multiple e-commerce sites are configured."""
        expected_sites = [
            "amazon",
            "walmart",
            "target",
            "ebay",
            "homedepot",
            "lowes",
            "menards",
            "bestbuy",
            "costco",
        ]
        for site in expected_sites:
            assert site in SITE_TIER_DEFAULTS, f"{site} should be in SITE_TIER_DEFAULTS"


class TestGetSiteTier:
    """get_site_tier() should return correct tier for site/pattern."""

    def test_known_site_search(self):
        """Known site + SEARCH returns correct tier."""
        tier = get_site_tier("amazon", PagePattern.SEARCH)
        assert tier == 7

    def test_known_site_detail(self):
        """Known site + DETAIL returns correct tier."""
        tier = get_site_tier("amazon", PagePattern.DETAIL)
        assert tier == 4

    def test_unknown_site_returns_1(self):
        """Unknown site returns tier 1."""
        tier = get_site_tier("unknownsite", PagePattern.SEARCH)
        assert tier == 1

    def test_unknown_pattern_falls_back_to_unknown(self):
        """Pattern not in site defaults may fall back to UNKNOWN tier if defined."""
        # If a site has UNKNOWN pattern defined, use it
        if PagePattern.UNKNOWN in SITE_TIER_DEFAULTS.get("amazon", {}):
            tier = get_site_tier("amazon", PagePattern.UNKNOWN)
            assert tier == SITE_TIER_DEFAULTS["amazon"][PagePattern.UNKNOWN]


class TestPagePatternEnum:
    """PagePattern enum should have all expected values."""

    def test_pattern_values(self):
        """All expected PagePattern values exist."""
        assert PagePattern.SEARCH.value == "search"
        assert PagePattern.DETAIL.value == "detail"
        assert PagePattern.SELLER.value == "seller"
        assert PagePattern.REVIEW.value == "review"
        assert PagePattern.HOME.value == "home"
        assert PagePattern.UNKNOWN.value == "unknown"


class TestCrawlStrategyDataclass:
    """CrawlStrategy dataclass should store all strategy parameters."""

    def test_default_strategy(self):
        """Default CrawlStrategy has sensible defaults."""
        strategy = CrawlPolicy()
        assert strategy.tier == 1
        assert strategy.proxy == ProxyType.THORDATA_DEDICATED
        assert strategy.render == RenderType.NONE
        assert strategy.use_human_scroll is False
        assert strategy.change_ua is False

    def test_strategy_with_all_params(self):
        """Strategy can be created with all parameters."""
        strategy = CrawlPolicy(
            tier=5,
            proxy=ProxyType.THORDATA_ANY,
            render=RenderType.CLOUDERA,
            delay_before=(1, 3),
            delay_after=(5, 10),
            use_cookies=True,
            use_human_scroll=True,
            change_ua=True,
            wait_selector=".product",
            extra_wait=2.0,
        )
        assert strategy.tier == 5
        assert strategy.proxy == ProxyType.THORDATA_ANY
        assert strategy.render == RenderType.CLOUDERA
        assert strategy.use_cookies is True
        assert strategy.wait_selector == ".product"
