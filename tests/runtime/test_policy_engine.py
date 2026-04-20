from ai_crawler.core.engine.policy_engine import (
    ConditionalStats,
    PolicyCandidate,
    PolicyEngine,
    PolicyScore,
    PolicyStats,
    PolicyStatsStore,
)
from ai_crawler.core.engine.trace_store import AntiBotTrace
from ai_crawler.core.strategy import CrawlStrategy, CrawlTask, PagePattern, RenderType


def test_policy_engine_gates_uc_for_known_bad_search_sites():
    task = CrawlTask.create_from_tier(
        url="https://www.target.com/s?searchTerm=chair",
        site="target",
        page_pattern=PagePattern.SEARCH,
    )
    engine = PolicyEngine(PolicyStatsStore())
    candidate = PolicyCandidate.from_strategy(task, CrawlStrategy(render=RenderType.CLOUDERA))

    assert engine._is_blocked_by_gate(task, candidate) is True


def test_policy_engine_keeps_uc_available_for_amazon_search():
    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/s?k=chair",
        site="amazon",
        page_pattern=PagePattern.SEARCH,
    )
    engine = PolicyEngine(PolicyStatsStore())
    candidate = PolicyCandidate.from_strategy(task, CrawlStrategy(render=RenderType.CLOUDERA))

    assert engine._is_blocked_by_gate(task, candidate) is False


def test_policy_engine_does_not_gate_uc_for_non_search_pages():
    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/dp/B07NWR7HKD",
        site="target",
        page_pattern=PagePattern.DETAIL,
    )
    engine = PolicyEngine(PolicyStatsStore())
    candidate = PolicyCandidate.from_strategy(task, CrawlStrategy(render=RenderType.CLOUDERA))

    assert engine._is_blocked_by_gate(task, candidate) is False


def test_policy_engine_prefers_higher_stats_score():
    store = PolicyStatsStore()
    store._stats = {
        ("amazon", "search", "camoufox", "thordata_dedicated"): PolicyStats(
            site="amazon",
            page_pattern="search",
            render="camoufox",
            proxy="thordata_dedicated",
            runs=10,
            successes=8,
            avg_latency_ms=2000,
            avg_products=20,
        ),
        ("amazon", "search", "playwright", "thordata_dedicated"): PolicyStats(
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
    engine = PolicyEngine(store)
    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/s?k=chair",
        site="amazon",
        page_pattern=PagePattern.SEARCH,
    )
    candidates = [
        PolicyCandidate.from_strategy(
            task, CrawlStrategy(render=RenderType.PLAYWRIGHT), source="task"
        ),
        PolicyCandidate.from_strategy(
            task, CrawlStrategy(render=RenderType.CAMOUFOX), source="task"
        ),
    ]

    ranked = engine.rank_candidates(task, candidates)

    assert ranked[0].candidate.render == "camoufox"


def test_policy_engine_uses_conditional_stats_for_ranking():
    store = PolicyStatsStore()
    cloudflare_stats = PolicyStats(
        site="amazon",
        page_pattern="search",
        render="cloudflare_uc",
        proxy="thordata_dedicated",
        runs=5,
        successes=4,
        avg_latency_ms=1000,
        avg_products=10,
    )
    cloudflare_stats.conditional["http_timeout"] = ConditionalStats(
        block_type="http_timeout",
        runs=3,
        successes=0,
        avg_latency_ms=500,
        avg_products=0,
    )

    camoufox_stats = PolicyStats(
        site="amazon",
        page_pattern="search",
        render="camoufox",
        proxy="thordata_dedicated",
        runs=5,
        successes=3,
        avg_latency_ms=2000,
        avg_products=8,
    )
    camoufox_stats.conditional["http_timeout"] = ConditionalStats(
        block_type="http_timeout",
        runs=3,
        successes=3,
        avg_latency_ms=2000,
        avg_products=6,
    )

    store._stats = {
        ("amazon", "search", "cloudflare_uc", "thordata_dedicated"): cloudflare_stats,
        ("amazon", "search", "camoufox", "thordata_dedicated"): camoufox_stats,
    }
    engine = PolicyEngine(store)
    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/s?k=chair",
        site="amazon",
        page_pattern=PagePattern.SEARCH,
    )
    candidates = [
        PolicyCandidate.from_strategy(
            task, CrawlStrategy(render=RenderType.CLOUDERA), source="task"
        ),
        PolicyCandidate.from_strategy(
            task, CrawlStrategy(render=RenderType.CAMOUFOX), source="task"
        ),
    ]

    ranked = engine.rank_candidates_for_failure(
        task, candidates, "http_timeout", "cloudflare_uc"
    )

    assert ranked[0].candidate.render == "camoufox"


def test_policy_engine_pick_minimal_sufficient():
    store = PolicyStatsStore()
    none_stats = PolicyStats(
        site="amazon",
        page_pattern="search",
        render="none",
        proxy="thordata_dedicated",
        runs=10,
        successes=1,
    )

    cloudscraper_stats = PolicyStats(
        site="amazon",
        page_pattern="search",
        render="cloudscraper",
        proxy="thordata_dedicated",
        runs=10,
        successes=3,
    )

    playwright_stats = PolicyStats(
        site="amazon",
        page_pattern="search",
        render="playwright",
        proxy="thordata_dedicated",
        runs=10,
        successes=5,
    )

    store._stats = {
        ("amazon", "search", "none", "thordata_dedicated"): none_stats,
        ("amazon", "search", "cloudscraper", "thordata_dedicated"): cloudscraper_stats,
        ("amazon", "search", "playwright", "thordata_dedicated"): playwright_stats,
    }
    engine = PolicyEngine(store)
    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/s?k=chair",
        site="amazon",
        page_pattern=PagePattern.SEARCH,
    )
    candidates = [
        PolicyCandidate.from_strategy(task, CrawlStrategy(render=RenderType.NONE), source="task"),
        PolicyCandidate.from_strategy(task, CrawlStrategy(render=RenderType.CLOUDSCRAPER), source="task"),
        PolicyCandidate.from_strategy(task, CrawlStrategy(render=RenderType.PLAYWRIGHT), source="task"),
    ]

    picked = engine.pick_minimal_sufficient(task, candidates, None)

    assert picked is not None
    assert picked.render == "none"


def test_policy_engine_pick_minimal_sufficient_conditional():
    store = PolicyStatsStore()

    none_stats = PolicyStats(
        site="amazon",
        page_pattern="search",
        render="none",
        proxy="thordata_dedicated",
        runs=10,
        successes=1,
    )
    none_stats.conditional["http_403"] = ConditionalStats(
        block_type="http_403",
        runs=5,
        successes=0,
    )

    cloudscraper_stats = PolicyStats(
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

    playwright_stats = PolicyStats(
        site="amazon",
        page_pattern="search",
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
    engine = PolicyEngine(store)
    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/s?k=chair",
        site="amazon",
        page_pattern=PagePattern.SEARCH,
    )
    candidates = [
        PolicyCandidate.from_strategy(task, CrawlStrategy(render=RenderType.NONE), source="task"),
        PolicyCandidate.from_strategy(task, CrawlStrategy(render=RenderType.CLOUDSCRAPER), source="task"),
        PolicyCandidate.from_strategy(task, CrawlStrategy(render=RenderType.PLAYWRIGHT), source="task"),
    ]

    picked = engine.pick_minimal_sufficient(task, candidates, "http_403")

    assert picked is not None
    assert picked.render == "cloudscraper"


def test_policy_engine_requests_llm_when_samples_are_low():
    store = PolicyStatsStore()
    engine = PolicyEngine(store)
    score = PolicyScore(
        candidate=PolicyCandidate(
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
    store = PolicyStatsStore()
    engine = PolicyEngine(store)
    top = PolicyScore(
        candidate=PolicyCandidate(
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
    second = PolicyScore(candidate=top.candidate, total_score=50, sample_count=10, success_rate=0.5)

    assert engine.should_consult_llm([top, second]) is False


def test_policy_engine_applies_secondary_fingerprinter_penalty():
    store = PolicyStatsStore()
    store._stats = {
        ("amazon", "search", "playwright", "thordata_dedicated"): PolicyStats(
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
        ("amazon", "search", "camoufox", "thordata_dedicated"): PolicyStats(
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
    engine = PolicyEngine(store)
    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/s?k=chair",
        site="amazon",
        page_pattern=PagePattern.SEARCH,
    )
    candidates = [
        PolicyCandidate.from_strategy(
            task, CrawlStrategy(render=RenderType.PLAYWRIGHT), source="task"
        ),
        PolicyCandidate.from_strategy(
            task, CrawlStrategy(render=RenderType.CAMOUFOX), source="task"
        ),
    ]

    ranked = engine.rank_candidates(task, candidates)

    assert ranked[0].candidate.render == "camoufox"
    assert ranked[1].anti_bot_penalty > 0


def test_policy_engine_gives_camoufox_contextual_bonus_on_search_pages():
    store = PolicyStatsStore()
    store._stats = {
        ("target", "search", "camoufox", "thordata_dedicated"): PolicyStats(
            site="target",
            page_pattern="search",
            render="camoufox",
            proxy="thordata_dedicated",
            runs=5,
            successes=3,
            avg_latency_ms=2000,
            avg_products=8,
        ),
        ("target", "search", "seleniumbase", "thordata_dedicated"): PolicyStats(
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
    engine = PolicyEngine(store)
    task = CrawlTask.create_from_tier(
        url="https://www.target.com/s?searchTerm=chair",
        site="target",
        page_pattern=PagePattern.SEARCH,
    )
    candidates = [
        PolicyCandidate.from_strategy(
            task, CrawlStrategy(render=RenderType.SELENIUMBASE), source="task"
        ),
        PolicyCandidate.from_strategy(
            task, CrawlStrategy(render=RenderType.CAMOUFOX), source="task"
        ),
    ]

    ranked = engine.rank_candidates(task, candidates)

    assert ranked[0].candidate.render == "camoufox"
    assert ranked[0].contextual_bonus > ranked[1].contextual_bonus


def test_policy_engine_gives_cloakbrowser_priority_on_amazon_target_search():
    store = PolicyStatsStore()
    store._stats = {
        ("amazon", "search", "cloakbrowser", "thordata_dedicated"): PolicyStats(
            site="amazon",
            page_pattern="search",
            render="cloakbrowser",
            proxy="thordata_dedicated",
            runs=3,
            successes=2,
            avg_latency_ms=3000,
            avg_products=12,
        ),
        ("amazon", "search", "camoufox", "thordata_dedicated"): PolicyStats(
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
    engine = PolicyEngine(store)
    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/s?k=chair",
        site="amazon",
        page_pattern=PagePattern.SEARCH,
    )
    candidates = [
        PolicyCandidate.from_strategy(
            task, CrawlStrategy(render=RenderType.CAMOUFOX), source="task"
        ),
        PolicyCandidate.from_strategy(
            task, CrawlStrategy(render=RenderType.CLOAKBROWSER), source="task"
        ),
    ]

    ranked = engine.rank_candidates(task, candidates)

    assert ranked[0].candidate.render == "cloakbrowser"
    assert ranked[0].contextual_bonus > ranked[1].contextual_bonus


def test_policy_stats_store_aggregates_anti_bot_vendor_and_mechanism_counts(tmp_path):
    from ai_crawler.core.engine.trace_store import TraceStore

    store = TraceStore(storage_dir=str(tmp_path))
    trace = AntiBotTrace(
        trace_id="t1",
        timestamp="2026-01-01T00:00:00",
        site="amazon",
        page_pattern="search",
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

    stats_store = PolicyStatsStore(store)
    stats = stats_store.get("amazon", "search", "playwright", "thordata_dedicated")

    assert stats.anti_bot_vendors["cloudflare"] == 1
    assert stats.anti_bot_mechanisms["js_challenge"] == 1
