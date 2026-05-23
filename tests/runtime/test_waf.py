"""Tests for WAF detection and jump logic (crawl/waf.py)."""

import pytest
from ai_crawler.crawl.waf import min_level_for_waf, jump_level, WAF_MIN_LEVEL, MAX_LEVEL


class TestMinLevelForWaf:
    def test_known_waf_returns_min_level(self):
        assert min_level_for_waf("cloudflare") == 3
        assert min_level_for_waf("perimeterx") == 2
        assert min_level_for_waf("akamai") == 2
        assert min_level_for_waf("datadome") == 2
        assert min_level_for_waf("imperva") == 2
        assert min_level_for_waf("walmart") == 3

    def test_lightweight_wafs_return_level_1(self):
        for waf in ("aws_waf", "f5_asm", "sucuri", "reblaze", "fortiweb", "radware", "incapsula"):
            assert min_level_for_waf(waf) == 1, f"{waf} should be level 1"

    def test_unknown_waf_returns_0(self):
        assert min_level_for_waf("") == 0
        assert min_level_for_waf("unknown_vendor") == 0

    def test_all_defined_wafs_have_min_level(self):
        for waf_name in WAF_MIN_LEVEL:
            level = min_level_for_waf(waf_name)
            assert 0 <= level <= MAX_LEVEL


class TestJumpLevel:
    def test_cloudflare_jumps_from_low_levels(self):
        assert jump_level(0, "cloudflare") == 3
        assert jump_level(1, "cloudflare") == 3
        assert jump_level(2, "cloudflare") == 3

    def test_cloudflare_above_jump_threshold_goes_plus_1(self):
        assert jump_level(3, "cloudflare") == 4
        assert jump_level(4, "cloudflare") == 5

    def test_perimeterx_jumps_from_low_levels(self):
        assert jump_level(0, "perimeterx") == 2
        assert jump_level(1, "perimeterx") == 2

    def test_perimeterx_above_jump_threshold_goes_plus_1(self):
        assert jump_level(2, "perimeterx") == 3
        assert jump_level(3, "perimeterx") == 4

    def test_akamai_jumps_from_low_levels(self):
        assert jump_level(0, "akamai") == 2
        assert jump_level(1, "akamai") == 2

    def test_akamai_above_threshold_goes_plus_1(self):
        assert jump_level(2, "akamai") == 3

    def test_datadome_jumps(self):
        assert jump_level(0, "datadome") == 2
        assert jump_level(1, "datadome") == 2

    def test_imperva_jumps(self):
        assert jump_level(0, "imperva") == 2
        assert jump_level(1, "imperva") == 2

    def test_walmart_jumps(self):
        assert jump_level(0, "walmart") == 3
        assert jump_level(1, "walmart") == 3
        assert jump_level(2, "walmart") == 3

    def test_walmart_above_threshold_goes_plus_1(self):
        assert jump_level(3, "walmart") == 4
        assert jump_level(4, "walmart") == 5

    def test_at_max_level_stays_at_max(self):
        assert jump_level(MAX_LEVEL, "cloudflare") == MAX_LEVEL
        assert jump_level(MAX_LEVEL, "perimeterx") == MAX_LEVEL

    def test_no_explicit_jump_goes_plus_1(self):
        """WAF types without explicit jump entries fall back to +1."""
        assert jump_level(0, "aws_waf") == 1
        assert jump_level(3, "aws_waf") == 4

    def test_unknown_waf_plus_1(self):
        assert jump_level(0, "") == 1
        assert jump_level(2, "custom_waf") == 3
