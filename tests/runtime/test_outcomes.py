from types import SimpleNamespace

from ai_crawler.crawl.outcomes import FailureOutcomeHandler, TraceRecorder
from ai_crawler.crawl.recommendation import DSPyStrategyRecommender
from ai_crawler.core.types import CrawlPolicy, CrawlTask, PagePattern, RenderType


class DummyTraceStore:
    def __init__(self):
        self.records = []

    def record(self, **kwargs):
        self.records.append(kwargs)


class DummyQueue:
    def __init__(self, exhausted=False):
        self.failures = []
        self.exhausted = exhausted

    def on_failure(self, task, block_type, snippet):
        self.failures.append((task.task_id, block_type, snippet))
        return self.exhausted


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
    strategy = DSPyStrategyRecommender._result_to_strategy(result)
    assert strategy.render.value == "camoufox"
    assert strategy.proxy.value == "thordata_us"


def test_failure_handler_records_failure():
    task = CrawlTask(url="https://www.amazon.com/s?k=chair", site="amazon",
                     page_pattern=PagePattern.SEARCH)
    task.strategy = CrawlPolicy(render=RenderType.NONE)
    trace_store = DummyTraceStore()
    recorder = TraceRecorder(trace_store)
    queue = DummyQueue(exhausted=False)
    handler = FailureOutcomeHandler(queue, None, recorder)

    attempt = make_attempt()
    trace_kwargs = recorder.failure_trace_kwargs(task, task.strategy, attempt, 0)
    handler.handle_blocked(task, attempt, trace_kwargs, 0)

    assert len(trace_store.records) == 1
    assert queue.failures[0][1] == "captcha"
    assert trace_store.records[0]["anti_bot_fingerprint"]["vendor"] == "cloudflare"


def test_failure_handler_extraction_retry_pushes_queue_failure():
    queue = DummyQueue(exhausted=False)
    handler = FailureOutcomeHandler(queue, None, TraceRecorder(DummyTraceStore()))
    task = CrawlTask(url="https://www.amazon.com/s?k=chair", site="amazon",
                     page_pattern=PagePattern.SEARCH)

    handler.handle_extraction_retry(task, "<html></html>", "empty_content")

    assert queue.failures == [(task.task_id, "empty_content", "<html></html>")]
