from ai_crawler.crawl.planner import Planner
from ai_crawler.crawl.task_context import TaskContext, Event
from ai_crawler.crawl.queue import SiteMemory
from ai_crawler.core.types import CrawlPolicy, CrawlTask, PagePattern, RenderType


def test_planner_ask_uses_memory_strategy():
    planner = Planner()
    task = CrawlTask(url="https://www.amazon.com/dp/B0123456", site="amazon",
                     page_pattern=PagePattern.DETAIL)
    best = CrawlPolicy(tier=2, render=RenderType.CLOUDSCRAPER)
    task.site_memory = SiteMemory(site="amazon", page_pattern=PagePattern.DETAIL.value)
    task.site_memory.successful_strategies = [best]

    ctx = TaskContext(task)
    strategy = planner.ask(ctx)

    assert strategy == best
    assert task.current_level > 0


def test_planner_ask_starts_at_level_0_without_memory():
    planner = Planner()
    task = CrawlTask(url="https://www.amazon.com/s?k=test", site="amazon",
                     page_pattern=PagePattern.SEARCH)
    ctx = TaskContext(task)
    strategy = planner.ask(ctx)

    assert strategy is not None
    assert task.current_level == 1
    assert strategy.render.value == "cloudscraper"


def test_planner_get_next_escalates_on_failure():
    planner = Planner()
    task = CrawlTask(url="https://www.amazon.com/s?k=test", site="amazon",
                     page_pattern=PagePattern.SEARCH)
    ctx = TaskContext(task)
    first = planner.ask(ctx)
    ctx.add_event(Event(type="fetch", success=False, block_type="cloudflare"))
    ctx.increment_attempt()

    second = planner.get_next(ctx)
    assert second is not None
    assert task.current_level > 0


def test_planner_get_next_returns_none_when_max_level():
    planner = Planner()
    task = CrawlTask(url="https://www.amazon.com/s?k=test", site="amazon",
                     page_pattern=PagePattern.SEARCH)
    task.current_level = 7  # max
    task.strategy = CrawlPolicy(render=RenderType.CLOAKBROWSER)
    ctx = TaskContext(task)
    ctx.add_event(Event(type="fetch", success=False, block_type="cloudflare"))

    result = planner.get_next(ctx)
    assert result is None


def test_planner_record_saves_to_site_memory():
    planner = Planner()
    task = CrawlTask(url="https://www.amazon.com/s?k=test", site="amazon",
                     page_pattern=PagePattern.SEARCH)
    task.site_memory = SiteMemory(site="amazon", page_pattern=PagePattern.SEARCH.value)
    ctx = TaskContext(task)
    planner.ask(ctx)

    ctx.set_result(type("Result", (), {"success": True})())
    planner.record(ctx)

    assert len(task.site_memory.successful_strategies) == 1
