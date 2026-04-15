from ai_crawler.core.runtime.planner import TaskStrategyPlanner
from ai_crawler.core.runtime.queue import SiteMemory
from ai_crawler.core.runtime.telemetry import detect_block_reason, detect_waf
from ai_crawler.core.strategy import CrawlStrategy, CrawlTask, PagePattern
from ai_crawler.models.product import Product
from ai_crawler.spiders import EXTRACTORS, Product as ExportedProduct


def test_task_strategy_planner_prefers_successful_strategy():
    planner = TaskStrategyPlanner()
    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/dp/B0123456",
        site="amazon",
        page_pattern=PagePattern.DETAIL,
    )
    best = CrawlStrategy.from_tier(3)

    memory = type(
        "Memory", (), {"successful_strategies": [best], "get_llm_tier": lambda *_: None}
    )()
    prepared = planner.prepare(task, memory)

    assert prepared is memory
    assert task.current_strategy() == best


def test_task_strategy_planner_clamps_amazon_search_llm_tier_to_minimum():
    planner = TaskStrategyPlanner(lambda **kwargs: type("Result", (), {"start_tier": "5"})())
    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/s?k=chair",
        site="amazon",
        page_pattern=PagePattern.SEARCH,
    )
    memory = SiteMemory(site="amazon")

    planner.prepare(task, memory)

    assert task.metadata["start_tier"] == 7
    assert memory.get_llm_tier(PagePattern.SEARCH.value) == 7


def test_task_strategy_planner_reorders_strategies_with_policy_engine():
    planner = TaskStrategyPlanner()
    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/s?k=chair",
        site="amazon",
        page_pattern=PagePattern.SEARCH,
    )
    first = task.strategies[0]
    second = task.strategies[1]

    planner.policy_engine.rank_candidates = lambda task, candidates: [
        type("Score", (), {"candidate": candidates[1]})(),
        type("Score", (), {"candidate": candidates[0]})(),
        *[type("Score", (), {"candidate": c})() for c in candidates[2:]],
    ]

    planner.prepare(task, None)

    assert task.strategies[0] == second
    assert task.strategies[1] == first


def test_task_strategy_planner_uses_llm_only_when_policy_low_confidence(monkeypatch):
    planner = TaskStrategyPlanner(lambda **kwargs: type("Result", (), {"start_tier": "7"})())
    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/s?k=chair",
        site="amazon",
        page_pattern=PagePattern.SEARCH,
    )

    planner._apply_llm_tier = lambda task, memory: task.metadata.__setitem__("llm_called", True)
    planner.policy_engine.should_consult_llm = lambda ranked: False

    planner.prepare(task, SiteMemory(site="amazon"))

    assert task.metadata.get("llm_called") is None


def test_task_strategy_planner_calls_llm_when_policy_low_confidence(monkeypatch):
    planner = TaskStrategyPlanner(lambda **kwargs: type("Result", (), {"start_tier": "7"})())
    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/s?k=chair",
        site="amazon",
        page_pattern=PagePattern.SEARCH,
    )

    planner._apply_llm_tier = lambda task, memory: task.metadata.__setitem__("llm_called", True)
    planner.policy_engine.should_consult_llm = lambda ranked: True

    planner.prepare(task, SiteMemory(site="amazon"))

    assert task.metadata["llm_called"] is True


def test_task_strategy_planner_reprioritizes_remaining_after_failure():
    planner = TaskStrategyPlanner()
    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/s?k=chair",
        site="amazon",
        page_pattern=PagePattern.SEARCH,
    )
    original_first = task.strategies[0]
    original_second = task.strategies[1]
    original_third = task.strategies[2]
    task.current_index = 0

    planner.policy_engine.rank_candidates_for_failure = (
        lambda task, candidates, block_type, failed_render: [
            type("Score", (), {"candidate": candidates[1]})(),
            type("Score", (), {"candidate": candidates[0]})(),
            *[type("Score", (), {"candidate": c})() for c in candidates[2:]],
        ]
    )

    planner.reprioritize_after_failure(task, "http_timeout")

    assert task.strategies[0] == original_first
    assert task.strategies[1] == original_third
    assert task.strategies[2] == original_second


def test_telemetry_helpers_classify_waf_and_reason():
    html = "<html>Checking your browser before accessing shop. cf-ray present.</html>"
    headers = {"server": "cloudflare", "cf-ray": "abc"}

    waf = detect_waf(html, headers)
    reason = detect_block_reason(html, 403, waf)

    assert waf == "cloudflare"
    assert "HTTP 403" in reason


def test_spiders_package_can_be_imported_without_scrapy_runtime():
    assert ExportedProduct is Product
    assert "amazon" in EXTRACTORS
