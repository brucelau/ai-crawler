"""Planner — picks the next strategy, adapts on failure, optimizes downward.

Uses WAF detection to skip ineffective render levels, site memory to remember
the minimal working strategy, and downward optimization to reduce cost over time.
"""

from __future__ import annotations

import structlog

from ai_crawler.crawl.strategy import build_policy, level_for_render
from ai_crawler.crawl.task_context import TaskContext
from ai_crawler.crawl.waf import min_level_for_waf, jump_level
from ai_crawler.core.types import CrawlPolicy

log = structlog.get_logger()


class Planner:
    def __init__(self, memory_store=None, strategy_mode="optimal"):
        self.memory_store = memory_store
        self.strategy_mode = strategy_mode

    def ask(self, ctx: TaskContext) -> CrawlPolicy:
        task = ctx.task

        # Existing pre-set strategy
        if task.strategy is not None:
            return task.strategy

        memory = task.site_memory

        # Reuse successful strategy from memory
        if memory and memory.successful_strategies:
            best = memory.successful_strategies[0]

            # Downward optimization: try one level lower than last success
            if memory.try_downward and memory.last_success_level is not None and memory.last_success_level > 0:
                candidate = memory.last_success_level - 1
                waf_floor = min_level_for_waf(memory.waf_type) if memory.waf_type else 0
                if candidate >= waf_floor:
                    memory.try_downward = False
                    policy = build_policy(candidate)
                    task.current_level = candidate
                    task.strategy = policy
                    log.info("planner_downward_attempt", site=task.site,
                             level=candidate, last_success=memory.last_success_level)
                    return policy

            level = level_for_render(best.render, best.use_human_scroll)
            task.current_level = level
            task.strategy = best
            return best

        # Determine start level: max of adapter hint, WAF floor
        start_level = _get_adapter_start_level(task)
        waf_floor = 0
        if memory and memory.waf_type:
            waf_floor = min_level_for_waf(memory.waf_type)

        start_level = max(start_level, waf_floor)
        start_level = min(start_level, 6)

        policy = build_policy(start_level)
        task.current_level = start_level
        task.strategy = policy
        log.info("planner_start", site=task.site, level=start_level,
                 waf_floor=waf_floor, waf_type=memory.waf_type if memory else "")
        return policy

    def get_next(self, ctx: TaskContext) -> CrawlPolicy | None:
        task = ctx.task
        block_type = ""
        waf_type = ""

        # Extract block info from recent failed events
        for event in reversed(ctx.events):
            if not event.success and event.block_type:
                block_type = event.block_type
                waf_type = event.waf_type
                break

        current = task.current_level

        # Store detected WAF in site memory for future runs
        if waf_type:
            memory = task.site_memory
            if memory and not memory.waf_type:
                memory.waf_type = waf_type
                log.info("planner_waf_detected", site=task.site, waf_type=waf_type)

        # WAF-aware jump: skip levels that can't work
        if waf_type:
            nxt = jump_level(current, waf_type)
        else:
            from ai_crawler.crawl.strategy import next_level
            nxt = next_level(current, block_type, ip_retries_remaining=0)

        if nxt is None:
            return None

        if nxt <= current and nxt < 6:
            nxt = current + 1

        if nxt > 6:
            return None

        policy = build_policy(nxt)
        task.current_level = nxt
        task.strategy = policy
        log.info("strategy_escalated", site=task.site, block_type=block_type,
                 waf_type=waf_type, from_level=current, to_level=nxt)
        return policy

    def record(self, ctx: TaskContext) -> None:
        task = ctx.task
        if ctx.result and ctx.result.success and task.strategy:
            policy = build_policy(task.current_level)
            task.strategy = policy
            if task.site_memory:
                task.site_memory.record_success(policy)
                # After success, flag downward optimization for next run
                task.site_memory.try_downward = True
            log.info("strategy_success_recorded", site=task.site,
                     level=task.current_level, render=policy.render.value,
                     min_working=task.site_memory.min_working_level if task.site_memory else None)


def _get_adapter_start_level(task) -> int:
    """Read the adapter's start_level hint, or 0."""
    try:
        from ai_crawler.sites.registry import get_command
        pattern = getattr(task.page_pattern, 'value', 'unknown')
        cls = get_command(task.site, pattern)
        if cls is not None and cls.start_level > 0:
            return cls.start_level
    except Exception:
        pass
    return 0
