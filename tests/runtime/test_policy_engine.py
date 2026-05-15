from ai_crawler.spider.engine.policy_engine import (
    ConditionalStats,
    CrawlPolicyCandidate,
    CrawlPolicyScorer,
    CrawlPolicyScore,
    CrawlPolicyStats,
    CrawlPolicyStatsStore,
)
from ai_crawler.spider.engine.core.trace_store import AntiBotTrace
from ai_crawler.spider.runtime.crawl import CrawlPolicy, CrawlTask, PagePattern, RenderType


def test_policy_engine_gates_uc_for_known_bad_search_sites():
    task = CrawlTask.create_from_tier(
        url="https://www.target.com/s?searchTerm=chair",
        site="target",
        page_pattern=PagePattern.SEARCH,
    )
    engine = CrawlPolicyScorer(CrawlPolicyStatsStore())
    candidate = CrawlPolicyCandidate.from_strategy(task, CrawlPolicy(render=RenderType.CLOUDERA))

    assert engine._is_blocked_by_gate(task, candidate) is True


def test_policy_engine_keeps_uc_available_for_amazon_search():
    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/s?k=chair",
        site="amazon",
        page_pattern=PagePattern.SEARCH,
    )
    engine = CrawlPolicyScorer(CrawlPolicyStatsStore())
    candidate = CrawlPolicyCandidate.from_strategy(task, CrawlPolicy(render=RenderType.CLOUDERA))

    assert engine._is_blocked_by_gate(task, candidate) is False


def test_policy_engine_does_not_gate_uc_for_non_search_pages():
    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/dp/B07NWR7HKD",
        site="target",
        page_pattern=PagePattern.DETAIL,
    )
    engine = CrawlPolicyScorer(CrawlPolicyStatsStore())
    candidate = CrawlPolicyCandidate.from_strategy(task, CrawlPolicy(render=RenderType.CLOUDERA))

    assert engine._is_blocked_by_gate(task, candidate) is False


def test_policy_engine_prefers_higher_stats_score():
    store = CrawlPolicyStatsStore()
    store._stats = {
        ("amazon", "search", "camoufox", "thordata_dedicated"): CrawlPolicyStats(
            site="amazon",
            page_pattern="search",
            render="camoufox",
            proxy="thordata_dedicated",
            runs=10,
            successes=8,
            avg_latency_ms=2000,
            avg_products=20,
        ),
        ("amazon", "search", "playwright", "thordata_dedicated"): CrawlPolicyStats(
            site="amazon",
            page_pattern="search",
            render="playwright",
            proxy="thordata_dedicated",
            runs=10,
            successes=3,
            avg_latency_ms=1000,
            avg_products=5,
            http_timeout_count=5,
        ),
    }
    engine = CrawlPolicyScorer(store)
    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/s?k=chair",
        site="amazon",
        page_pattern=PagePattern.UNKNOWN,
    )
    candidates = [
        CrawlPolicyCandidate.from_strategy(task, CrawlPolicy(render=RenderType.NONE), source="task"),

        CrawlPolicyCandidate.from_strategy(task, CrawlPolicy(render=RenderType.CLOUDSCRAPER), source="task"),
        CrawlPolicyCandidate.from_strategy(task, CrawlPolicy(render=RenderType.PLAYWRIGHT), source="task"),
    ]

    picked = engine.pick_minimal_sufficient(task, candidates, None)

    assert picked is not None
    assert picked.render == "none"


def test_policy_engine_pick_minimal_sufficient_conditional():
    store = CrawlPolicyStatsStore()

    none_stats = CrawlPolicyStats(
            site="amazon",
            page_pattern="unknown",
            render="camoufox",
            proxy="thordata_dedicated",
            runs=10,

        successes=1,
    )
    none_stats.conditional["http_403"] = ConditionalStats(
        block_type="http_403",
        runs=5,
        successes=0,
    )

    cloudscraper_stats = CrawlPolicyStats(
        site="amazon",
        page_pattern="search",
        render="cloudscraper",
        proxy="thordata_dedicated",
        runs=10,
        successes=3,
    )
    cloudscraper_stats.conditional["http_403"] = ConditionalStats(
        block_type="http_403",
        runs=5,
        successes=4,
    )

    playwright_stats = CrawlPolicyStats(
            site="amazon",
            page_pattern="unknown",
            render="playwright",
            proxy="thordata_dedicated",
            runs=10,

        successes=5,
    )
    playwright_stats.conditional["http_403"] = ConditionalStats(
        block_type="http_403",
        runs=3,
        successes=2,
    )

    store._stats = {
        ("amazon", "search", "none", "thordata_dedicated"): none_stats,
        ("amazon", "search", "cloudscraper", "thordata_dedicated"): cloudscraper_stats,
        ("amazon", "search", "playwright", "thordata_dedicated"): playwright_stats,
    }
    engine = CrawlPolicyScorer(store)
    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/s?k=chair",
        site="amazon",
        page_pattern=PagePattern.SEARCH,
    )
    candidates = [
        CrawlPolicyCandidate.from_strategy(task, CrawlPolicy(render=RenderType.NONE), source="task"),
        CrawlPolicyCandidate.from_strategy(task, CrawlPolicy(render=RenderType.CLOUDSCRAPER), source="task"),
        CrawlPolicyCandidate.from_strategy(task, CrawlPolicy(render=RenderType.PLAYWRIGHT), source="task"),
    ]

    picked = engine.pick_minimal_sufficient(task, candidates, "http_403")

    assert picked is not None
    assert picked.render == "cloudscraper"


def test_policy_engine_requests_llm_when_samples_are_low():
    store = CrawlPolicyStatsStore()
    engine = CrawlPolicyScorer(store)
    score = CrawlPolicyScore(
        candidate=CrawlPolicyCandidate(
            site="amazon",
            page_pattern="search",
            tier=6,
            render="seleniumbase",
            proxy="thordata_dedicated",
            use_cookies=True,
            change_ua=True,
            use_human_scroll=True,
        ),
        total_score=10,
        sample_count=1,
    )

    assert engine.should_consult_llm([score]) is True


def test_policy_engine_skips_llm_when_top_score_is_clear_and_sampled():
    store = CrawlPolicyStatsStore()
    engine = CrawlPolicyScorer(store)
    top = CrawlPolicyScore(
        candidate=CrawlPolicyCandidate(
            site="amazon",
            page_pattern="search",
            tier=6,
            render="seleniumbase",
            proxy="thordata_dedicated",
            use_cookies=True,
            change_ua=True,
            use_human_scroll=True,
        ),
        total_score=80,
        sample_count=10,
        success_rate=0.9,
    )
    second = CrawlPolicyScore(candidate=top.candidate, total_score=50, sample_count=10, success_rate=0.5)

    assert engine.should_consult_llm([top, second]) is False


def test_policy_engine_applies_secondary_fingerprinter_penalty():
    store = CrawlPolicyStatsStore()
    store._stats = {
        ("amazon", "search", "playwright", "thordata_dedicated"): CrawlPolicyStats(
            site="amazon",
            page_pattern="search",
            render="playwright",
            proxy="thordata_dedicated",
            runs=10,
            successes=8,
            avg_latency_ms=1000,
            avg_products=10,
            anti_bot_vendors={"browser_error": 5},
            anti_bot_mechanisms={"proxy_transport_error": 5},
        ),
        ("amazon", "search", "camoufox", "thordata_dedicated"): CrawlPolicyStats(
            site="amazon",
            page_pattern="search",
            render="camoufox",
            proxy="thordata_dedicated",
            runs=10,
            successes=8,
            avg_latency_ms=1000,
            avg_products=10,
        ),
    }
    engine = CrawlPolicyScorer(store)
    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/s?k=chair",
        site="amazon",
        page_pattern=PagePattern.SEARCH,
    )
    candidates = [
        CrawlPolicyCandidate.from_strategy(
            task, CrawlPolicy(render=RenderType.PLAYWRIGHT), source="task"
        ),
        CrawlPolicyCandidate.from_strategy(
            task, CrawlPolicy(render=RenderType.CAMOUFOX), source="task"
        ),
    ]

    ranked = engine.rank_candidates(task, candidates)
    assert len(ranked) == 2


def test_policy_engine_gives_camoufox_contextual_bonus_on_search_pages():
    store = CrawlPolicyStatsStore()
    store._stats = {
        ("target", "search", "camoufox", "thordata_dedicated"): CrawlPolicyStats(
            site="target",
            page_pattern="search",
            render="camoufox",
            proxy="thordata_dedicated",
            runs=5,
            successes=3,
            avg_latency_ms=2000,
            avg_products=8,
        ),
        ("target", "search", "seleniumbase", "thordata_dedicated"): CrawlPolicyStats(
            site="target",
            page_pattern="search",
            render="seleniumbase",
            proxy="thordata_dedicated",
            runs=5,
            successes=3,
            avg_latency_ms=2000,
            avg_products=8,
        ),
    }
    engine = CrawlPolicyScorer(store)
    task = CrawlTask.create_from_tier(
        url="https://www.target.com/s?searchTerm=chair",
        site="target",
        page_pattern=PagePattern.SEARCH,
    )
    candidates = [
        CrawlPolicyCandidate.from_strategy(
            task, CrawlPolicy(render=RenderType.SELENIUMBASE), source="task"
        ),
        CrawlPolicyCandidate.from_strategy(
            task, CrawlPolicy(render=RenderType.CAMOUFOX), source="task"
        ),
    ]

    ranked = engine.rank_candidates(task, candidates)
    assert len(ranked) == 2


def test_policy_engine_gives_cloakbrowser_priority_on_amazon_target_search():
    store = CrawlPolicyStatsStore()
    store._stats = {
        ("amazon", "search", "cloakbrowser", "thordata_dedicated"): CrawlPolicyStats(
            site="amazon",
            page_pattern="search",
            render="cloakbrowser",
            proxy="thordata_dedicated",
            runs=3,
            successes=2,
            avg_latency_ms=3000,
            avg_products=12,
        ),
        ("amazon", "search", "camoufox", "thordata_dedicated"): CrawlPolicyStats(
            site="amazon",
            page_pattern="search",
            render="camoufox",
            proxy="thordata_dedicated",
            runs=3,
            successes=2,
            avg_latency_ms=3000,
            avg_products=12,
        ),
    }
    engine = CrawlPolicyScorer(store)
    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/s?k=chair",
        site="amazon",
        page_pattern=PagePattern.SEARCH,
    )
    candidates = [
        CrawlPolicyCandidate.from_strategy(
            task, CrawlPolicy(render=RenderType.CAMOUFOX), source="task"
        ),


        CrawlPolicyCandidate.from_strategy(
            task, CrawlPolicy(render=RenderType.CLOAKBROWSER), source="task"
        ),
    ]

    ranked = engine.rank_candidates(task, candidates)
    assert len(ranked) == 2


def test_policy_stats_store_aggregates_anti_bot_vendor_and_mechanism_counts(tmp_path):
    from ai_crawler.spider.engine.core.trace_store import TraceStore

    store = TraceStore(storage_dir=str(tmp_path))
    trace = AntiBotTrace(
        trace_id="t1",
        timestamp="2026-01-01T00:00:00",
        site="amazon",
        page_pattern="unknown",
        url="https://example.com",
        block_type="cloudflare",
        response_snippet="",
        response_headers={},
        status_code=403,
        full_html_size=100,
        strategy_tier=3,
        strategy_proxy="thordata_dedicated",
        strategy_render="playwright",
        strategy_change_ua=True,
        strategy_use_cookies=True,
        strategy_use_human_scroll=True,
        strategy_delay_after=(1, 2),
        success=False,
        latency_ms=100.0,
        cost_estimate=0.1,
        attempt_index=0,
        anti_bot_fingerprint={"vendor": "cloudflare", "mechanisms": ["js_challenge"]},
    )
    store._traces = [trace]

    stats_store = CrawlPolicyStatsStore(store)
    stats = stats_store.get("amazon", "unknown", "playwright", "thordata_dedicated")

    assert stats.anti_bot_vendors.get("cloudflare") == 1
    assert stats.anti_bot_mechanisms.get("js_challenge") == 1
