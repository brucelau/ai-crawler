"""Tests for Planner WAF-aware strategy selection and the full crawl escalation flow.

Covers:
  - planner.ask() with WAF in site memory (waf_floor jump)
  - planner.get_next() with WAF type in failed event (jump_level)
  - planner.get_next() without WAF (block_jump via next_level)
  - Full escalation: waf_probe → ask → execute → get_next → ... → max
  - Planner record() with site memory update
"""

import pytest
from ai_crawler.crawl.planner import Planner
from ai_crawler.crawl.task_context import TaskContext, Event
from ai_crawler.crawl.queue import SiteMemory
from ai_crawler.core.types import CrawlPolicy, CrawlTask, PagePattern, RenderType


# ── Fixtures ──────────────────────────────────────────────────────────

def _make_task(site="ebay", page_pattern=PagePattern.SEARCH, url=None):
    if url is None:
        url = f"https://www.{site}.com/s?k=test"
    return CrawlTask(url=url, site=site, page_pattern=page_pattern)


def _add_failed_event(ctx, block_type, waf_type=""):
    ctx.add_event(Event(type="fetch", success=False,
                        block_type=block_type, waf_type=waf_type))
    ctx.increment_attempt()


# ── Planner.ask() with WAF memory ─────────────────────────────────────

class TestPlannerAskWafAware:
    def test_ask_starts_at_waf_floor_when_waf_known(self):
        """If site memory has a WAF type, ask() should start >= waf_floor."""
        planner = Planner()
        task = _make_task(site="ebay")
        task.site_memory = SiteMemory(site="ebay", page_pattern="search")
        task.site_memory.waf_type = "cloudflare"  # min_level=3

        ctx = TaskContext(task)
        strategy = planner.ask(ctx)

        assert task.current_level == 3  # waf_floor for cloudflare
        assert strategy.render == RenderType.CAMOUFOX

    def test_ask_starts_at_waf_floor_perimeterx(self):
        planner = Planner()
        task = _make_task(site="ebay")
        task.site_memory = SiteMemory(site="ebay", page_pattern="search")
        task.site_memory.waf_type = "perimeterx"  # min_level=2

        ctx = TaskContext(task)
        strategy = planner.ask(ctx)

        assert task.current_level == 2
        assert strategy.render == RenderType.PLAYWRIGHT

    def test_ask_starts_at_waf_floor_walmart(self):
        planner = Planner()
        task = _make_task(site="walmart",
                          url="https://www.walmart.com/search?q=test")
        task.site_memory = SiteMemory(site="walmart", page_pattern="search")
        task.site_memory.waf_type = "walmart"  # min_level=3

        ctx = TaskContext(task)
        strategy = planner.ask(ctx)

        assert task.current_level == 3
        assert strategy.render == RenderType.CAMOUFOX

    def test_ask_starts_at_level_0_without_waf(self):
        planner = Planner()
        task = _make_task(site="ebay")
        ctx = TaskContext(task)
        strategy = planner.ask(ctx)

        assert task.current_level == 0
        assert strategy.render == RenderType.NONE

    def test_ask_starts_at_level_0_with_empty_waf(self):
        planner = Planner()
        task = _make_task(site="ebay")
        task.site_memory = SiteMemory(site="ebay", page_pattern="search")
        task.site_memory.waf_type = ""  # empty

        ctx = TaskContext(task)
        strategy = planner.ask(ctx)

        assert task.current_level == 0

    def test_ask_uses_memory_strategy_over_waf_floor(self):
        """A stored successful strategy takes priority over WAF floor."""
        planner = Planner()
        task = _make_task(site="ebay")
        task.site_memory = SiteMemory(site="ebay", page_pattern="search")
        task.site_memory.waf_type = "cloudflare"  # floor=3
        best = CrawlPolicy(tier=2, render=RenderType.PLAYWRIGHT)
        task.site_memory.successful_strategies = [best]

        ctx = TaskContext(task)
        strategy = planner.ask(ctx)

        assert strategy == best

    def test_ask_downward_optimization(self):
        """When try_downward is set, try one level lower than last success."""
        planner = Planner()
        task = _make_task(site="ebay")
        task.site_memory = SiteMemory(site="ebay", page_pattern="search")
        task.site_memory.waf_type = "perimeterx"  # floor=2
        task.site_memory.try_downward = True
        task.site_memory.last_success_level = 3
        best = CrawlPolicy(tier=3, render=RenderType.CAMOUFOX)
        task.site_memory.successful_strategies = [best]

        ctx = TaskContext(task)
        strategy = planner.ask(ctx)

        assert task.current_level == 2  # 3-1 = 2, >= waf_floor=2
        assert strategy.render == RenderType.PLAYWRIGHT

    def test_ask_downward_not_below_waf_floor(self):
        """Downward optimization won't go below WAF floor."""
        planner = Planner()
        task = _make_task(site="ebay")
        task.site_memory = SiteMemory(site="ebay", page_pattern="search")
        task.site_memory.waf_type = "perimeterx"  # floor=2
        task.site_memory.try_downward = True
        task.site_memory.last_success_level = 2  # one level lower would be 1, < floor
        best = CrawlPolicy(tier=2, render=RenderType.PLAYWRIGHT)
        task.site_memory.successful_strategies = [best]

        ctx = TaskContext(task)
        strategy = planner.ask(ctx)

        # Should reuse the stored strategy, not try downward to level 1
        assert task.current_level > 1
        assert task.strategy == best


# ── Planner.get_next() with WAF jumps ─────────────────────────────────

class TestPlannerGetNextWafAware:
    def test_get_next_waf_jump_from_failed_event(self):
        """When the failed event has a WAF type, use jump_level."""
        planner = Planner()
        task = _make_task(site="ebay")
        ctx = TaskContext(task)
        planner.ask(ctx)  # sets level 0

        _add_failed_event(ctx, block_type="bot_detected", waf_type="cloudflare")
        strategy = planner.get_next(ctx)

        # cloudflare at level 0 → jump to 3
        assert task.current_level == 3
        assert strategy.render == RenderType.CAMOUFOX

    def test_get_next_waf_jump_perimeterx(self):
        planner = Planner()
        task = _make_task(site="ebay")
        ctx = TaskContext(task)
        planner.ask(ctx)
        task.current_level = 1  # simulate: level 1 failed

        _add_failed_event(ctx, block_type="bot_detected", waf_type="perimeterx")
        strategy = planner.get_next(ctx)

        assert task.current_level == 2  # perimeterx jump: 1→2
        assert strategy.render == RenderType.PLAYWRIGHT

    def test_get_next_waf_jump_walmart(self):
        planner = Planner()
        task = _make_task(site="walmart",
                          url="https://www.walmart.com/search?q=test")
        ctx = TaskContext(task)
        planner.ask(ctx)
        task.current_level = 1

        _add_failed_event(ctx, block_type="bot_detected", waf_type="walmart")
        strategy = planner.get_next(ctx)

        assert task.current_level == 3  # walmart jump: 1→3
        assert strategy.render == RenderType.CAMOUFOX

    def test_get_next_waf_jump_akamai(self):
        planner = Planner()
        task = _make_task(site="ebay")
        ctx = TaskContext(task)
        planner.ask(ctx)
        task.current_level = 1

        _add_failed_event(ctx, block_type="bot_detected", waf_type="akamai")
        strategy = planner.get_next(ctx)

        assert task.current_level == 2  # akamai jump: 1→2

    def test_get_next_no_waf_uses_block_jump(self):
        """Without WAF type, falls back to _BLOCK_JUMP via next_level."""
        planner = Planner()
        task = _make_task(site="ebay")
        ctx = TaskContext(task)
        planner.ask(ctx)

        _add_failed_event(ctx, block_type="bot_detected", waf_type="")
        strategy = planner.get_next(ctx)

        # bot_detected at level 0 → block jump to 2
        assert task.current_level == 2
        assert strategy.render == RenderType.PLAYWRIGHT

    def test_get_next_no_waf_cloudflare_block_jump(self):
        planner = Planner()
        task = _make_task(site="ebay")
        ctx = TaskContext(task)
        planner.ask(ctx)

        _add_failed_event(ctx, block_type="cloudflare", waf_type="")
        strategy = planner.get_next(ctx)

        assert task.current_level == 3  # cloudflare block jump: 0→3

    def test_get_next_uses_last_failed_event_waf(self):
        """Only the most recent failed event's WAF type matters."""
        planner = Planner()
        task = _make_task(site="ebay")
        ctx = TaskContext(task)
        planner.ask(ctx)

        # first failure: no WAF
        _add_failed_event(ctx, block_type="bot_detected", waf_type="")
        # second failure: has WAF
        _add_failed_event(ctx, block_type="bot_detected", waf_type="cloudflare")

        strategy = planner.get_next(ctx)
        assert task.current_level == 3  # uses the cloudflare WAF from last failed event

    def test_get_next_stores_waf_in_memory(self):
        """When WAF is detected in a failed event, store in site memory."""
        planner = Planner()
        task = _make_task(site="ebay")
        task.site_memory = SiteMemory(site="ebay", page_pattern="search")
        assert task.site_memory.waf_type == ""

        ctx = TaskContext(task)
        planner.ask(ctx)
        _add_failed_event(ctx, block_type="bot_detected", waf_type="cloudflare")
        planner.get_next(ctx)

        assert task.site_memory.waf_type == "cloudflare"

    def test_get_next_stays_at_max_level(self):
        """At max level with WAF, stays at max (no further escalation)."""
        planner = Planner()
        task = _make_task(site="ebay")
        ctx = TaskContext(task)
        task.current_level = 6
        task.strategy = CrawlPolicy(render=RenderType.CLOAKBROWSER)
        _add_failed_event(ctx, block_type="bot_detected", waf_type="cloudflare")

        result = planner.get_next(ctx)
        assert result is not None
        assert task.current_level == 6  # stays at max


# ── Full escalation sequence simulation ──────────────────────────────

class TestFullEscalationFlow:
    """Simulate the engine's escalation loop: ask → fail → get_next → fail → ..."""

    def test_full_escalation_no_waf(self):
        """Without WAF, escalate level by level using block jumps."""
        planner = Planner()
        task = _make_task(site="walmart",
                          url="https://www.walmart.com/search?q=test")
        ctx = TaskContext(task)

        strategy = planner.ask(ctx)
        assert task.current_level == 0

        levels_seen = [task.current_level]

        for _ in range(7):
            _add_failed_event(ctx, block_type="bot_detected", waf_type="")
            strategy = planner.get_next(ctx)
            if strategy is None:
                break
            levels_seen.append(task.current_level)

        # bot_detected: 0→2→3→4→5→6→None
        assert levels_seen == [0, 2, 3, 4, 5, 6]

    def test_full_escalation_with_waf_detected_mid_flow(self):
        """WAF gets detected on attempt 1, jump kicks in from attempt 2."""
        planner = Planner()
        task = _make_task(site="walmart",
                          url="https://www.walmart.com/search?q=test")
        task.site_memory = SiteMemory(site="walmart", page_pattern="search")
        ctx = TaskContext(task)

        strategy = planner.ask(ctx)
        assert task.current_level == 0

        levels_seen = [task.current_level]

        # Attempt 0: blocked, now WAF detected
        _add_failed_event(ctx, block_type="bot_detected", waf_type="perimeterx")
        strategy = planner.get_next(ctx)
        assert strategy is not None
        levels_seen.append(task.current_level)  # should be 2 (perimeterx jump)

        # Continue until max
        for _ in range(5):
            _add_failed_event(ctx, block_type="bot_detected", waf_type="perimeterx")
            strategy = planner.get_next(ctx)
            if strategy is None:
                break
            levels_seen.append(task.current_level)

        # 0 → 2 (perimeterx jump) → 3 → 4 → 5 → 6
        assert 2 in levels_seen
        assert max(levels_seen) == 6
        assert levels_seen == sorted(levels_seen)  # monotonically increasing

    def test_http_403_at_level_0_jumps_to_2(self):
        """http_403 at level 0 jumps to level 2 via _BLOCK_JUMP."""
        planner = Planner()
        task = _make_task(site="ebay")
        ctx = TaskContext(task)
        planner.ask(ctx)  # level 0

        _add_failed_event(ctx, block_type="http_403", waf_type="")
        strategy = planner.get_next(ctx)

        assert task.current_level == 2  # _BLOCK_JUMP: (0, http_403) → 2
        assert strategy.render == RenderType.PLAYWRIGHT

    def test_ip_blocked_no_waf_no_jump_entry_plus_1(self):
        """ip_blocked without WAF and no _BLOCK_JUMP entry → +1."""
        planner = Planner()
        task = _make_task(site="ebay")
        ctx = TaskContext(task)
        planner.ask(ctx)  # level 0

        _add_failed_event(ctx, block_type="ip_blocked", waf_type="")
        strategy = planner.get_next(ctx)

        assert task.current_level == 1  # no jump entry for ip_blocked
