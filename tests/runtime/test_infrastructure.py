import sys
import types

from ai_crawler.fetch import Fetcher
from ai_crawler.browser import SeleniumBaseWrapper, utils
from ai_crawler.antidetect.proxy.uc_bridge import UCProxyBridge
from ai_crawler.crawl.runner import Fetcher as RunnerFetcher, ProxyProvider as RunnerProxyProvider
from ai_crawler.antidetect.proxy import ProxyProvider
from ai_crawler.core.types import CrawlPolicy, PagePattern, ProxyType


def test_runner_reexports_extracted_infrastructure_classes():
    assert RunnerFetcher is Fetcher
    assert RunnerProxyProvider is ProxyProvider


def test_proxy_provider_returns_none_when_disabled():
    provider = ProxyProvider(username="", password="", disabled=True)

    assert provider.proxy_url(CrawlPolicy()) is None
    assert provider.rotate_proxy(CrawlPolicy()) is None


def test_proxy_provider_caches_manager_per_proxy_type(monkeypatch):
    provider = ProxyProvider(username="user", password="pass", verify_proxy=False, disabled=False)
    created = []

    class FakeManager:
        def __init__(self, **kwargs):
            created.append(kwargs)

        def get_proxy_url(self):
            return "http://user:pass@proxy.example:8080"

        def rotate(self):
            return None

    monkeypatch.setattr(
        "ai_crawler.antidetect.proxy.thordata.ThorDataManager",
        FakeManager,
    )

    manager1 = provider._get_thordata_manager(ProxyType.THORDATA_DEDICATED)
    manager2 = provider._get_thordata_manager(ProxyType.THORDATA_DEDICATED)

    assert manager1 is manager2
    assert len(created) == 1


def test_fetcher_builds_headers_from_dynamic_profile():
    fetcher = Fetcher(
        dynamic_profile={
            "user_agent": "UA",
            "sec_ch_ua_platform": '"Linux"',
            "sec_ch_ua": '"Chromium";v="120"',
        }
    )

    headers = fetcher._build_headers(CrawlPolicy(change_ua=True))

    assert headers["User-Agent"] == "UA"
    assert headers["sec-ch-ua-platform"] == '"Linux"'


def test_fetcher_structures_authenticated_proxy_settings():
    settings = utils.structured_proxy_settings("http://user:pass@proxy.example:8080")

    assert settings == {
        "server": "http://proxy.example:8080",
        "username": "user",
        "password": "pass",
    }


def test_uc_returns_explicit_error_for_authenticated_proxy(monkeypatch):
    fetcher = Fetcher()
    task = type(
        "Task",
        (),
        {
            "url": "https://example.com",
            "site": "amazon",
            "page_pattern": PagePattern.UNKNOWN,
        },
    )()
    strategy = CrawlPolicy()


    monkeypatch.setattr(
        fetcher,
        "_get_cloak_browser",
        lambda *args, **kwargs: (_ for _ in ()).throw(ModuleNotFoundError("cloakbrowser")),
    )

    html, status, page = fetcher._fetch_with_cloakbrowser(task, strategy)

    assert status == 200
    assert "RUNTIME_MISSING_MODULE cloakbrowser" in html
    assert page is None


def test_cloakbrowser_uses_threaded_sync_fetch_inside_event_loop(monkeypatch):
    fetcher = Fetcher()
    task = type(
        "Task",
        (),
        {
            "url": "https://example.com",
            "site": "amazon",
            "page_pattern": PagePattern.UNKNOWN,
        },
    )()
    strategy = CrawlPolicy()

    class FakeFuture:
        def result(self):
            return "<html>cloak</html>", 200

    class FakeExecutor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def submit(self, fn, *args):
            return FakeFuture()

    monkeypatch.setattr(fetcher, "_is_running_inside_event_loop", lambda: True)
    monkeypatch.setattr(
        "ai_crawler.fetch.fetcher.ThreadPoolExecutor",
        lambda max_workers=1: FakeExecutor(),
    )
    monkeypatch.setattr(
        "ai_crawler.browser.wrappers.cloakbrowser._sync_fetch",
        lambda *args, **kwargs: ("<html>cloak</html>", 200),
    )

    html, status, page = fetcher._fetch_with_cloakbrowser(task, strategy)

    assert html == "<html>cloak</html>"
    assert status == 200
    assert page is None


def test_fetcher_blocks_only_ad_scripts():
    assert utils.should_block_script(
        "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js"
    )
    assert not utils.should_block_script("https://cdn.example.com/assets/app.js")


def test_fetcher_installs_ad_blocking_handler():
    fetcher = Fetcher()
    captured = {}

    class FakePage:
        def route(self, pattern, handler):
            captured["pattern"] = pattern
            captured["handler"] = handler

    fetcher._install_ad_script_blocking(FakePage())

    class FakeRequest:
        def __init__(self, url, resource_type):
            self.url = url
            self.resource_type = resource_type

    class FakeRoute:
        def __init__(self, request):
            self.request = request
            self.aborted = False
            self.continued = False

        def abort(self):
            self.aborted = True

        def continue_(self):
            self.continued = True

    ad_route = FakeRoute(
        FakeRequest(
            "https://securepubads.g.doubleclick.net/tag/js/gpt.js",
            "script",
        )
    )
    captured["handler"](ad_route)
    assert ad_route.aborted is True

    app_route = FakeRoute(FakeRequest("https://cdn.example.com/app.js", "script"))
    captured["handler"](app_route)
    assert app_route.continued is True


def test_fetcher_release_page_closes_open_page():
    fetcher = Fetcher()

    class FakePage:
        def __init__(self):
            self.closed = False

        def is_closed(self):
            return self.closed

        def close(self):
            self.closed = True

    page = FakePage()
    fetcher.release_page(page)

    assert page.closed is True


def test_fetcher_stats_snapshot_includes_pool_and_block_metrics():
    fetcher = Fetcher()
    fetcher._increment_stat("playwright_browser_created")
    fetcher._increment_stat("camoufox_browser_created")
    fetcher._increment_stat("uc_browser_created")
    fetcher._increment_stat("playwright_context_reused", 2)
    fetcher._increment_stat("ad_scripts_blocked", 3)
    fetcher._playwright_browsers["b1"] = object()
    fetcher._playwright_contexts["c1"] = object()
    fetcher._camoufox_browsers["cx1"] = object()
    fetcher._uc_drivers["uc1"] = object()
    fetcher._cloak_browsers["k1"] = object()

    snapshot = fetcher.stats_snapshot()

    assert snapshot["playwright_browser_created"] == 1
    assert snapshot["camoufox_browser_created"] == 1
    assert snapshot["uc_browser_created"] == 1
    assert snapshot["playwright_context_reused"] == 2
    assert snapshot["ad_scripts_blocked"] == 3
    assert snapshot["active_playwright_browsers"] == 1
    assert snapshot["active_playwright_contexts"] == 1
    assert snapshot["active_camoufox_browsers"] == 1
    assert snapshot["active_uc_browsers"] == 1
    assert snapshot["active_cloak_browsers"] == 1


def test_get_camoufox_browser_reuses_browser_instance(monkeypatch):
    fetcher = Fetcher()

    class FakeBrowser:
        def __init__(self):
            self.closed = False
            self.connected = True

        def close(self):
            self.closed = True

        def is_connected(self):
            return self.connected

    class FakeCamoufox:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.browser = FakeBrowser()

        def start(self):
            return self.browser

    monkeypatch.setitem(sys.modules, "camoufox", types.SimpleNamespace(Camoufox=FakeCamoufox))

    browser1 = fetcher._get_camoufox_browser("shared", {"headless": True})
    browser2 = fetcher._get_camoufox_browser("shared", {"headless": True})

    assert browser1 is browser2
    snapshot = fetcher.stats_snapshot()
    assert snapshot["camoufox_browser_created"] == 1
    assert snapshot["camoufox_browser_reused"] == 1


def test_release_camoufox_browser_evicts_unhealthy_browser():
    fetcher = Fetcher()

    class FakeBrowser:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    browser = FakeBrowser()
    fetcher._camoufox_browsers["bad"] = browser
    fetcher._camoufox_browser_meta["bad"] = {"leases": 0, "last_used": 0.0}
    fetcher._camoufox_launchers["bad"] = object()

    fetcher._release_camoufox_browser("bad", browser, healthy=False)

    assert browser.closed is True
    assert "bad" not in fetcher._camoufox_browsers


def test_get_camoufox_browser_evicts_stale_browser(monkeypatch):
    fetcher = Fetcher()

    class FakeBrowser:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

        def is_connected(self):
            return True

    class FakeCamoufox:
        def __init__(self, **kwargs):
            self.browser = FakeBrowser()

        def start(self):
            return self.browser

    monkeypatch.setitem(sys.modules, "camoufox", types.SimpleNamespace(Camoufox=FakeCamoufox))

    old = FakeBrowser()
    fetcher._camoufox_browsers["shared"] = old
    fetcher._camoufox_launchers["shared"] = object()
    fetcher._camoufox_browser_meta["shared"] = {"leases": 0, "last_used": 0.0}
    fetcher._camoufox_idle_ttl_seconds = 0

    new_browser = fetcher._get_camoufox_browser("shared", {"headless": True})

    assert new_browser is not old
    assert old.closed is True


def test_get_uc_driver_reuses_healthy_driver(monkeypatch):
    fetcher = Fetcher()

    class FakeOptions:
        def __init__(self):
            self.args = []
            self.headless = False
            self.page_load_strategy = "normal"

        def add_argument(self, arg):
            self.args.append(arg)

    class FakeDriver:
        def __init__(self):
            self.quit_called = False
            self.window_handles = ["w1"]
            self.current_window_handle = "w1"
            self.page_source = "<html></html>"

        def set_page_load_timeout(self, timeout):
            self.timeout = timeout

        def execute_script(self, script):
            return 1

        def get(self, url):
            self.url = url

        def delete_all_cookies(self):
            return None

        def quit(self):
            self.quit_called = True

    created = []

    def fake_chrome(options=None, version_main=None):
        driver = FakeDriver()
        created.append(driver)
        return driver

    monkeypatch.setitem(
        sys.modules,
        "undetected_chromedriver",
        types.SimpleNamespace(Chrome=fake_chrome, ChromeOptions=FakeOptions),
    )

    strategy = CrawlPolicy(change_ua=True)
    driver1 = fetcher._get_uc_driver("uc-key", strategy, None)
    fetcher._release_uc_driver("uc-key", driver1, healthy=True)
    driver2 = fetcher._get_uc_driver("uc-key", strategy, None)

    assert driver1 is driver2
    snapshot = fetcher.stats_snapshot()
    assert snapshot["uc_browser_created"] == 1
    assert snapshot["uc_browser_reused"] == 1
    assert fetcher._uc_max_leases == 2
    assert fetcher._uc_idle_ttl_seconds == 120


def test_release_uc_driver_evicts_unhealthy_driver(monkeypatch):
    fetcher = Fetcher()

    class FakeDriver:
        def __init__(self):
            self.quit_called = False

        def quit(self):
            self.quit_called = True

    driver = FakeDriver()
    fetcher._uc_drivers["bad"] = driver
    fetcher._uc_driver_meta["bad"] = {"leases": 0, "last_used": 0.0}

    fetcher._release_uc_driver("bad", driver, healthy=False)

    assert driver.quit_called is True
    assert "bad" not in fetcher._uc_drivers


def test_uc_can_salvage_large_non_error_html():
    fetcher = Fetcher()
    html = "<html><body>" + ("product " * 10000) + "</body></html>"

    assert fetcher._can_salvage_uc_html(html) is True


def test_uc_does_not_salvage_known_error_page():
    fetcher = Fetcher()
    html = "<html><body>ERR_NO_SUPPORTED_PROXIES" + ("x" * 100000) + "</body></html>"

    assert fetcher._can_salvage_uc_html(html) is False


def test_uc_salvages_partial_page_source_on_renderer_timeout(monkeypatch):
    fetcher = Fetcher()
    task = type(
        "Task",
        (),
        {
            "url": "https://example.com",
            "site": "amazon",
            "page_pattern": PagePattern.UNKNOWN,
        },
    )()
    strategy = CrawlPolicy(change_ua=True)

    class FakeDriver:
        page_source = "<html><body>" + ("product " * 10000) + "</body></html>"

        def get(self, url):
            raise RuntimeError("Timed out receiving message from renderer")

    fetcher.proxy_provider = type("Proxy", (), {"proxy_url": lambda self, strategy: None})()
    fetcher._get_uc_driver = lambda driver_key, strategy, proxy: FakeDriver()
    fetcher._release_uc_driver = lambda driver_key, driver, healthy: None
    fetcher._reset_uc_driver = lambda driver: True

    html, status, page = fetcher._fetch_with_uc(task, strategy)

    assert status == 200
    assert "product" in html
    assert page is None


def test_camoufox_sync_loop_error_uses_async_fallback(monkeypatch):
    fetcher = Fetcher()
    strategy = CrawlPolicy()
    task = type("Task", (), {"url": "https://example.com", "task_id": "t1"})()

    monkeypatch.setattr(
        fetcher,
        "_get_camoufox_browser",
        lambda *_: (_ for _ in ()).throw(
            RuntimeError("It looks like you are using Playwright Sync API inside the asyncio loop.")
        ),
    )
    monkeypatch.setattr(fetcher, "_install_ad_script_blocking", lambda page: None)
    monkeypatch.setattr(
        "ai_crawler.browser.human.fingerprint.generate_fingerprint_script",
        lambda **kwargs: "script",
    )

    class FakeFuture:
        def result(self):
            return "<html>fallback</html>"

    class FakeExecutor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def submit(self, fn, *args):
            return FakeFuture()

    monkeypatch.setattr(
        "ai_crawler.browser.wrappers.camoufox._sync_launch",
        lambda *args, **kwargs: "<html>fallback</html>",
    )
    monkeypatch.setattr(
        "ai_crawler.fetch.fetcher.ThreadPoolExecutor",
        lambda max_workers=1: FakeExecutor(),
    )

    html, status, page = fetcher._fetch_with_camoufox(task, strategy)

    assert html == "<html>fallback</html>"
    assert status == 200
    assert page is None


def test_seleniumbase_falls_back_to_non_uc_mode(monkeypatch):
    fetcher = Fetcher()
    task = type("Task", (), {"url": "https://example.com"})()
    strategy = CrawlPolicy()
    calls = []

    class FakeWrapper:
        def __init__(self, **kwargs):
            calls.append(kwargs["undetected"])
            self.undetected = kwargs["undetected"]

        def create_driver(self):
            if self.undetected:
                raise RuntimeError(
                    "session not created: cannot connect to chrome at 127.0.0.1:9222"
                )
            return object()

        def _add_stealth_js(self, driver):
            return None

        def fetch_with_driver(
            self, driver, url, wait_selector=None, wait_time=None, human_scroll=None
        ):
            return "<html>ok</html>", 200

        def close_driver(self, driver):
            return None

    monkeypatch.setattr(
        "ai_crawler.browser.wrappers.seleniumbase.SeleniumBaseWrapper",
        FakeWrapper,
    )

    html, status, page = fetcher._fetch_with_seleniumbase(task, strategy)

    assert calls == [True, False]
    assert html == "<html>ok</html>"
    assert status == 200
    assert page is None


def test_uc_proxy_bridge_snapshot_tracks_requests_and_errors():
    bridge = UCProxyBridge("http://user:pass@proxy.example:8080")

    bridge._record_request()
    bridge._record_error("upstream_connect_failed")
    snapshot = bridge.snapshot()

    assert snapshot["request_count"] == 1
    assert snapshot["error_count"] == 1
    assert snapshot["last_error"] == "upstream_connect_failed"


def test_uc_proxy_bridge_start_stop_updates_health():
    bridge = UCProxyBridge("http://user:pass@proxy.example:8080")

    assert bridge.healthy() is False
    bridge.start()
    try:
        assert bridge.healthy() is True
        assert bridge.local_proxy_url().startswith("http://127.0.0.1:")
    finally:
        bridge.stop()
    assert bridge.healthy() is False


def test_seleniumbase_wrapper_fetch_with_driver_reuses_external_driver():
    wrapper = SeleniumBaseWrapper(wait_time=0, human_scroll=False)

    class FakeDriver:
        def __init__(self):
            self.page_source = "<html>ok</html>"
            self.visited = []

        def get(self, url):
            self.visited.append(url)

    driver = FakeDriver()
    html, status = wrapper.fetch_with_driver(driver, "https://example.com", wait_time=0)

    assert html == "<html>ok</html>"
    assert status == 200
    assert driver.visited == ["https://example.com"]


def test_seleniumbase_wrapper_close_driver_clears_owner():
    wrapper = SeleniumBaseWrapper()

    class FakeDriver:
        def __init__(self):
            self.quit_called = False

        def quit(self):
            self.quit_called = True

    driver = FakeDriver()
    wrapper._driver = driver
    wrapper.close_driver(driver)

    assert driver.quit_called is True
    assert wrapper._driver is None


def test_wait_for_page_ready_prefers_wait_selector():
    fetcher = Fetcher()
    strategy = CrawlPolicy(wait_selector=".product-card", extra_wait=0)
    calls = []

    class FakePage:
        def wait_for_selector(self, selector, timeout):
            calls.append(("selector", selector, timeout))

        def wait_for_timeout(self, timeout):
            calls.append(("timeout", timeout))

    fetcher._wait_for_page_ready(FakePage(), strategy)

    assert calls == [("selector", ".product-card", 8000)]


def test_wait_for_page_ready_falls_back_to_timeout_when_selector_wait_fails():
    fetcher = Fetcher()
    strategy = CrawlPolicy(wait_selector=".product-card", extra_wait=1.5)
    calls = []

    class FakePage:
        def wait_for_selector(self, selector, timeout):
            calls.append(("selector", selector, timeout))
            raise RuntimeError("no match")

        def wait_for_timeout(self, timeout):
            calls.append(("timeout", timeout))

    fetcher._wait_for_page_ready(FakePage(), strategy)

    assert calls == [("selector", ".product-card", 1500), ("timeout", 1500)]


def test_navigation_timeout_budget_is_higher_for_search_pages():
    fetcher = Fetcher()
    task = type(
        "Task", (), {"site": "target", "page_pattern": PagePattern.SEARCH}
    )()

    timeout = fetcher._navigation_timeout_ms(task, CrawlPolicy())

    assert timeout == 30000


def test_navigation_timeout_budget_respects_extra_wait():
    fetcher = Fetcher()
    task = type(
        "Task", (), {"site": "unknown", "page_pattern": PagePattern.SEARCH}
    )()
    strategy = CrawlPolicy(extra_wait=12.0)

    timeout = fetcher._navigation_timeout_ms(task, strategy)

    assert timeout == 24000
