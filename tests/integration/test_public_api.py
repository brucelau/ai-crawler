from ai_crawler import run_crawl


def test_run_crawl_delegates_to_runtime(monkeypatch):
    captured = {}

    class FakeRuntime:
        def __init__(self, options):
            captured["options"] = options

        def crawl(self, sites, query, pages, storage_backend=None):
            captured["sites"] = sites
            captured["query"] = query
            captured["pages"] = pages
            captured["storage_backend"] = storage_backend
            return {"ok": True}

    monkeypatch.setattr("ai_crawler.SmartCrawlerRuntime", FakeRuntime)

    result = run_crawl(
        sites=["amazon"],
        query="chair",
        pages=2,
        proxy_username="user",
        proxy_password="pass",
        traces_dir="custom-traces",
    )

    assert result == {"ok": True}
    assert captured["sites"] == ["amazon"]
    assert captured["query"] == "chair"
    assert captured["pages"] == 2
    assert captured["options"].proxy_username == "user"
    assert captured["options"].traces_dir == "custom-traces"
