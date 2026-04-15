from ai_crawler.core.runner import CrawlRunner


def test_runner_stop_logs_fetcher_stats(monkeypatch):
    runner = CrawlRunner(proxy_username="", proxy_password="", proxy_disabled=True)
    stats = {"playwright_browser_created": 1, "ad_scripts_blocked": 4}
    captured = {}

    monkeypatch.setattr(runner.fetcher, "stats_snapshot", lambda: stats)
    monkeypatch.setattr(runner.fetcher, "close", lambda: captured.setdefault("closed", True))
    monkeypatch.setattr(
        runner.executor, "shutdown", lambda wait=False: captured.setdefault("shutdown", wait)
    )

    class FakeLogger:
        def info(self, event, **kwargs):
            captured["event"] = event
            captured["kwargs"] = kwargs

    monkeypatch.setattr("ai_crawler.core.runner.log", FakeLogger())

    runner.stop()

    assert captured["event"] == "fetcher_stats"
    assert captured["kwargs"] == stats
    assert captured["closed"] is True
