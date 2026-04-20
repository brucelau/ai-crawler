from ai_crawler.core.engine.processing import TaskProcessor
from ai_crawler.core.engine.results import CrawlResult
from ai_crawler.core.strategy import CrawlStrategy, CrawlTask, PagePattern


def test_task_processor_treats_empty_non_retry_extraction_as_failure():
    task = CrawlTask.create_from_tier(
        url="https://example.com/search?q=chair",
        site="target",
        page_pattern=PagePattern.SEARCH,
    )
    strategy = task.current_strategy()

    class FakeQueue:
        def __init__(self):
            self.site_memory = {}
            self.success_called = False
            self.failure_calls = []

        def on_failure(self, task, block_type, snippet):
            self.failure_calls.append(block_type)
            return False, None

        def on_success(self, task, strategy):
            self.success_called = True

    class FakePlanner:
        def prepare(self, task, memory):
            return memory

        def resolve(self, task):
            return strategy

    class FakeExecution:
        def execute(self, task, strategy):
            class Attempt:
                html = "<html></html>"
                status_code = 200
                page = None
                blocked = False
                block_type = "none"
                latency_ms = 1
                cost_estimate = 0
                response_headers = {}
                ip_rotation_count = 0
                fingerprint_profile = {}
                waf_detected = ""
                block_reason = ""
                anti_bot_fingerprint = {}

            return Attempt()

    class FakeTraceRecorder:
        def failure_trace_kwargs(self, task, strategy, attempt, attempt_index):
            return {}

        def record_success(self, *args, **kwargs):
            raise AssertionError("should not record success for empty extraction")

    class FakeFailureHandler:
        def __init__(self, queue):
            self.queue = queue

        def handle_blocked(self, task, attempt, trace_kwargs, attempt_index):
            raise AssertionError("should not hit blocked path")

        def handle_extraction_retry(self, task, html, retry_reason):
            self.queue.on_failure(task, retry_reason, html[:200])

    class FakeExtraction:
        def extract(self, task, strategy, page, html):
            class Decision:
                products = []
                should_retry = False
                strategy_name = "none"
                method = "none"
                metadata = {}

            return Decision()

    queue = FakeQueue()
    processor = TaskProcessor(
        queue=queue,
        planner=FakePlanner(),
        execution=FakeExecution(),
        captcha=None,
        fetcher=type("Fetcher", (), {"release_page": lambda self, page: None})(),
        anti_bot=None,
        trace_recorder=FakeTraceRecorder(),
        failure_handler=FakeFailureHandler(queue),
        extraction=FakeExtraction(),
        captcha_solver=None,
    )

    result = processor.process(task)

    assert isinstance(result, CrawlResult)
    assert result.success is False
    assert result.block_type == "empty_content"
    assert queue.success_called is False
    assert queue.failure_calls == ["empty_content"]
