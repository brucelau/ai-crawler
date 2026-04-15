from ai_crawler.core.runtime.execution import TaskExecutionEngine
from ai_crawler.core.strategy import CrawlStrategy, CrawlTask, PagePattern, RenderType


def test_uc_search_timeout_short_circuits_retry():
    engine = TaskExecutionEngine(
        fetcher=None,
        anti_bot=None,
        proxy_provider=type("Proxy", (), {"disabled": False})(),
        max_ip_retries=3,
        ip_rotation_block_types={"http_timeout"},
    )
    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/s?k=chair",
        site="amazon",
        page_pattern=PagePattern.SEARCH,
    )
    strategy = CrawlStrategy(render=RenderType.CLOUDERA)

    assert engine._should_short_circuit_retry(task, strategy, "", "http_timeout") is True


def test_uc_detail_timeout_does_not_short_circuit_without_browser_error_signature():
    engine = TaskExecutionEngine(
        fetcher=None,
        anti_bot=None,
        proxy_provider=type("Proxy", (), {"disabled": False})(),
        max_ip_retries=3,
        ip_rotation_block_types={"http_timeout"},
    )
    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/dp/B07NWR7HKD",
        site="amazon",
        page_pattern=PagePattern.DETAIL,
    )
    strategy = CrawlStrategy(render=RenderType.CLOUDERA)

    assert engine._should_short_circuit_retry(task, strategy, "", "http_timeout") is False


def test_uc_browser_error_signature_short_circuits_even_without_search_pattern():
    engine = TaskExecutionEngine(
        fetcher=None,
        anti_bot=None,
        proxy_provider=type("Proxy", (), {"disabled": False})(),
        max_ip_retries=3,
        ip_rotation_block_types={"http_timeout"},
    )
    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/dp/B07NWR7HKD",
        site="amazon",
        page_pattern=PagePattern.DETAIL,
    )
    strategy = CrawlStrategy(render=RenderType.CLOUDERA)

    assert (
        engine._should_short_circuit_retry(
            task,
            strategy,
            "Sorry! Something went wrong! We couldn't process your request.".lower(),
            "http_timeout",
        )
        is True
    )


def test_uc_search_quality_check_rejects_low_quality_target_page():
    engine = TaskExecutionEngine(
        fetcher=None,
        anti_bot=None,
        proxy_provider=type("Proxy", (), {"disabled": False})(),
        max_ip_retries=3,
        ip_rotation_block_types={"http_timeout"},
    )
    task = CrawlTask.create_from_tier(
        url="https://www.target.com/s?searchTerm=chair",
        site="target",
        page_pattern=PagePattern.SEARCH,
    )

    html = "<html><body><title>Target</title><div>Welcome</div></body></html>"

    assert engine._has_minimum_search_quality(task, html) is False


def test_uc_search_quality_check_accepts_amazon_result_markers():
    engine = TaskExecutionEngine(
        fetcher=None,
        anti_bot=None,
        proxy_provider=type("Proxy", (), {"disabled": False})(),
        max_ip_retries=3,
        ip_rotation_block_types={"http_timeout"},
    )
    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/s?k=chair",
        site="amazon",
        page_pattern=PagePattern.SEARCH,
    )

    html = '<html><body><div class="s-search-results"></div><div data-asin="B001"></div><span class="a-price"></span></body></html>'

    assert engine._has_minimum_search_quality(task, html) is True
