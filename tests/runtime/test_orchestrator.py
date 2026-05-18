from ai_crawler.crawl.runner import CrawlResult
from ai_crawler.core.types import CrawlPolicy, CrawlTask, PagePattern, MemoryStore
from ai_crawler.core.types import Product
from ai_crawler.crawl.orchestrator import RuntimeOptions, SmartCrawlerRuntime
from ai_crawler.core.types import RuntimeTask


def test_build_search_tasks_uses_supported_sites():
    runtime = SmartCrawlerRuntime(RuntimeOptions())

    tasks = runtime.build_search_tasks(["amazon", "unknown"], "pool float", 2)

    assert len(tasks) == 2
    assert tasks[0].site == "amazon"
    assert tasks[0].goal == "search"
    assert tasks[0].url == "https://www.amazon.com/s?k=pool+float"
    assert tasks[1].url.endswith("&page=2")


def test_menards_search_url_uses_query_param():
    runtime = SmartCrawlerRuntime(RuntimeOptions())

    url = runtime.build_search_url("menards", "outdoor chair", 1)

    assert url == "https://www.menards.com/main/search.html?query=outdoor+chair"


def test_crawl_tasks_returns_runtime_batch_result(monkeypatch, tmp_path):
    runtime = SmartCrawlerRuntime(
        RuntimeOptions(output_dir=str(tmp_path / "output"), traces_dir=str(tmp_path / "traces"))
    )

    class FakeRunner:
        def __init__(self):
            self.tasks = []
            self.memory_store = MemoryStore()

        def add_tasks(self, tasks):
            self.tasks.extend(tasks)

        def run(self):
            task = self.tasks[0]
            return [
                CrawlResult(
                    task=task,
                    strategy=task.strategy or CrawlPolicy(),
                    success=True,
                    html="<html></html>",
                    products=[Product(source=task.site, url=task.url, title="Chair")],
                    extraction_strategy="axtree",
                    extraction_method="accessibility_tree",
                    extraction_metadata={"axtree_hit": True},
                    anti_bot_fingerprint={"vendor": "cloudflare", "mechanisms": ["js_challenge"]},
                )
            ]

    monkeypatch.setattr(runtime, "_build_runner", lambda trace_store, storage_backend=None: FakeRunner())
    monkeypatch.setattr(
        "ai_crawler.crawl.orchestrator.ProductOutputWriter.write",
        lambda self, task_results: [str(tmp_path / "output" / "amazon.jsonl")],
    )

    batch = runtime.crawl_tasks(
        [RuntimeTask(id="amazon-search-1", site="amazon", url="https://example.com", goal="search")]
    )

    assert len(batch.products) == 1
    assert batch.task_results[0].signal.type == "ok"
    assert batch.task_results[0].artifacts["axtree_hit"] is True
    assert batch.task_results[0].artifacts["anti_bot_fingerprint"]["vendor"] == "cloudflare"
    assert batch.stats["tasks_total"] == 1
    assert batch.stats["task_axtree_hits"] == 1
    assert batch.stats["task_extraction_strategies"]["axtree"] == 1
    assert batch.output_files == [str(tmp_path / "output" / "amazon.jsonl")]


def test_crawl_runner_waits_for_completed_task_without_hardcoded_timeout(monkeypatch):
    from ai_crawler.crawl.runner import CrawlRunner
    from ai_crawler.crawl.results import CrawlResult
    from ai_crawler.core.types import CrawlPolicy, CrawlTask

    runner = CrawlRunner(proxy_username="", proxy_password="", proxy_disabled=True)
    task = CrawlTask(url="https://example.com", site="amazon", page_pattern=PagePattern.UNKNOWN)
    task.task_id = "amazon-search-1"
    runner.add_tasks([task])

    class FakeFuture:
        def result(self, timeout=None):
            return CrawlResult(
                task=task, strategy=CrawlPolicy(), success=True, html="<html></html>"
            )

    def fake_run(tasks):
        return [FakeFuture().result() for _ in tasks]

    runner._coordinator.run = fake_run

    results = runner.run(max_items=1)

    assert len(results) == 1
    assert results[0].success is True
    runner.stop()

