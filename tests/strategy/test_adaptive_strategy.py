"""Tests for adaptive strategy escalation engine."""

import pytest
from ai_crawler.crawl.strategy import build_policy, next_level, level_for_render, escalate_dimension, MAX_LEVEL
from ai_crawler.core.types import RenderType, ProxyType


class TestBuildPolicy:
    def test_level_0_is_cheapest(self):
        p = build_policy(0)
        assert p.render == RenderType.NONE
        assert p.use_human_scroll is False
        assert p.use_cookies is False
        assert p.change_ua is False
        assert p.proxy == ProxyType.THORDATA_DEDICATED

    def test_level_3_has_human_scroll(self):
        p = build_policy(3)
        assert p.render == RenderType.CAMOUFOX
        assert p.use_human_scroll is True

    def test_max_level_is_strongest(self):
        p = build_policy(MAX_LEVEL)
        assert p.render == RenderType.CLOAKBROWSER
        assert p.use_human_scroll is True
        assert p.use_cookies is True
        assert p.change_ua is True

    def test_out_of_range_clamps(self):
        assert build_policy(-1).render == RenderType.NONE
        assert build_policy(99).render == RenderType.CLOAKBROWSER

    def test_each_level_has_higher_cost(self):
        """Each level should use a render with >= cost."""
        costs = {RenderType.NONE.value: 1, RenderType.CLOUDSCRAPER.value: 2,
                 RenderType.PLAYWRIGHT.value: 4, RenderType.CAMOUFOX.value: 5,
                 RenderType.CLOUDERA.value: 6, RenderType.SELENIUMBASE.value: 7,
                 RenderType.CLOAKBROWSER.value: 8}
        prev_cost = 0
        for level in range(MAX_LEVEL + 1):
            p = build_policy(level)
            cost = costs.get(p.render.value, 0)
            assert cost >= prev_cost, f"Level {level} cost {cost} < prev {prev_cost}"
            prev_cost = cost


class TestLevelForRender:
    def test_none_is_level_0(self):
        assert level_for_render(RenderType.NONE) == 0

    def test_cloudscraper_is_level_1(self):
        assert level_for_render(RenderType.CLOUDSCRAPER) == 1

    def test_cloakbrowser_is_max_level(self):
        assert level_for_render(RenderType.CLOAKBROWSER) == MAX_LEVEL

    def test_unknown_returns_0(self):
        assert level_for_render(RenderType.KAMELEO) == 0


class TestEscalateDimension:
    def test_ip_block_is_proxy(self):
        assert escalate_dimension("ip_blocked") == "proxy"

    def test_cloudflare_is_render(self):
        assert escalate_dimension("cloudflare") == "render"

    def test_captcha_is_render(self):
        assert escalate_dimension("captcha") == "render"

    def test_soft_suspicion_is_behavior(self):
        assert escalate_dimension("soft_suspicion") == "behavior"

    def test_unknown_is_render(self):
        assert escalate_dimension("unknown_block") == "render"


class TestNextLevel:
    def test_proxy_block_with_retries_stays_same(self):
        assert next_level(0, "ip_blocked", ip_retries_remaining=3) == 0

    def test_render_block_escalates(self):
        assert next_level(0, "cloudflare", ip_retries_remaining=0) == 1

    def test_max_level_returns_none(self):
        assert next_level(MAX_LEVEL, "cloudflare", ip_retries_remaining=0) is None

    def test_escalates_even_with_retries_for_non_proxy_blocks(self):
        assert next_level(2, "captcha", ip_retries_remaining=5) == 3
