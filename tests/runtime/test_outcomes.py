from types import SimpleNamespace

from ai_crawler.spider.engine.core.outcomes import FailureOutcomeHandler, TraceRecorder
from ai_crawler.spider.engine.recommendation import DSPyStrategyRecommender
from ai_crawler.spider.runtime.crawl import CrawlPolicy, CrawlTask, PagePattern


class DummyTraceStore:
    def __init__(self):
        self.records = []

    def record(self, **kwargs):
        self.records.append(kwargs)


class DummyQueue:
    def __init__(self, needs_llm=True):
        self.failures = []
        self.needs_llm = needs_llm

    def on_failure(self, task, block_type, snippet):
        self.failures.append((task.task_id, block_type, snippet))
        return self.needs_llm, None


def make_attempt(blocked=True, block_type="captcha"):
    return SimpleNamespace(
        html="<html>blocked</html>",
        status_code=403,
        blocked=blocked,
        block_type=block_type,
        latency_ms=12.0,
        cost_estimate=0.1,
        response_headers={"server": "cloudflare"},
        ip_rotation_count=1,
        fingerprint_profile={},
        anti_bot_fingerprint={"vendor": "cloudflare", "mechanisms": ["js_challenge"]},
        waf_detected="cloudflare",
        block_reason="HTTP 403 Forbidden",
    )


def test_dspy_recommender_maps_result_to_strategy():
    result = SimpleNamespace(
        recommended_strategy={
            "proxy": "thordata_us",
            "render": "camoufox",
            "change_ua": True,
            "use_cookies": True,
            "use_human_scroll": True,
        }
    )
    recommender = DSPyStrategyRecommender(lambda **_: result)
    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/s?k=chair",
        site="amazon",
        page_pattern=PagePattern.SEARCH,
    )

    strategy = recommender.recommend(task, "captcha", "snippet")

    assert strategy is not None
    assert strategy.render.value == "camoufox"
    assert strategy.proxy.value == "thordata_us"


def test_failure_handler_records_failure_and_dspy_recommendation():
    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/s?k=chair",
        site="amazon",
        page_pattern=PagePattern.UNKNOWN,
    )
    trace_store = DummyTraceStore()
    recorder = TraceRecorder(trace_store)
    queue = DummyQueue(needs_llm=True)
    recommended = CrawlPolicy.from_tier(4)
    recommender = SimpleNamespace(recommend=lambda *_: recommended)
    handler = FailureOutcomeHandler(queue, recommender, recorder)

    attempt = make_attempt()
    trace_kwargs = recorder.failure_trace_kwargs(task, task.current_strategy(), attempt, 0)
    handler.handle_blocked(task, attempt, trace_kwargs, 0)

    assert len(trace_store.records) == 2
    assert queue.failures[0][1] == "captcha"
    assert recommended in task.strategies
    assert trace_store.records[0]["anti_bot_fingerprint"]["vendor"] == "cloudflare"


def test_failure_handler_extraction_retry_pushes_queue_failure():
    queue = DummyQueue(needs_llm=False)
    handler = FailureOutcomeHandler(queue, None, TraceRecorder(DummyTraceStore()))
    task = CrawlTask.create_from_tier(
        url="https://www.amazon.com/s?k=chair",
        site="amazon",
        page_pattern=PagePattern.SEARCH,
    )

    handler.handle_extraction_retry(task, "<html></html>", "empty_content")

    assert queue.failures == [(task.task_id, "empty_content", "<html></html>")]
