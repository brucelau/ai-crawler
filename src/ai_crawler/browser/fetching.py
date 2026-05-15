from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import random
import time
from collections import OrderedDict
from threading import RLock
from typing import Callable
from urllib.parse import urlparse

import structlog

from ai_crawler.spider.runtime.crawl import CrawlPolicy, CrawlTask, RenderType
from ai_crawler.browser.pools import PoolState, PlaywrightPool, CamoufoxPool, UCPool, CloakBrowserPool
from ai_crawler.browser import utils


log = structlog.get_logger()


class Fetcher:
    def __init__(
        self,
        proxy_provider=None,
        dynamic_profile: dict | None = None,
        request_timeout: float | None = None,
        page_load_timeout: float | None = None,
    ):
        from ai_crawler.config import config

        self.proxy_provider = proxy_provider
        self.dynamic_profile = dynamic_profile or {}
        self.request_timeout = request_timeout or config.REQUEST_TIMEOUT
        self.page_load_timeout = page_load_timeout or config.PAGE_LOAD_TIMEOUT

        self._state = PoolState()
        self._playwright_pool = PlaywrightPool(
            self._state, proxy_provider, self.dynamic_profile, self.page_load_timeout
        )
        self._camoufox_pool = CamoufoxPool(
            self._state, proxy_provider, self.dynamic_profile, self.page_load_timeout
        )
        self._uc_pool = UCPool(
            self._state, proxy_provider, self.dynamic_profile, self.page_load_timeout
        )
        self._cloak_pool = CloakBrowserPool(
            self._state, proxy_provider, self.dynamic_profile, self.page_load_timeout
        )

    @property
    def _pool_lock(self):
        return self._state._pool_lock

    @property
    def _stats(self):
        return self._state._stats

    @property
    def _session_cookies(self):
        return self._state._session_cookies

    @property
    def _playwright_runtime(self):
        return self._state._playwright_runtime

    @_playwright_runtime.setter
    def _playwright_runtime(self, value):
        self._state._playwright_runtime = value

    @property
    def _playwright_browsers(self):
        return self._state._playwright_browsers

    @property
    def _playwright_contexts(self):
        return self._state._playwright_contexts

    @property
    def _camoufox_browsers(self):
        return self._state._camoufox_browsers

    @property
    def _camoufox_browser_meta(self):
        return self._state._camoufox_browser_meta

    @property
    def _camoufox_launchers(self):
        return self._state._camoufox_launchers

    @property
    def _uc_drivers(self):
        return self._state._uc_drivers

    @property
    def _uc_driver_meta(self):
        return self._state._uc_driver_meta

    @property
    def _cloak_browsers(self):
        return self._state._cloak_browsers

    @property
    def _uc_proxy_bridges(self):
        return self._state._uc_proxy_bridges

    @property
    def _camoufox_max_leases(self):
        return self._state._camoufox_max_leases

    @property
    def _camoufox_idle_ttl_seconds(self):
        return self._state._camoufox_idle_ttl_seconds

    @_camoufox_idle_ttl_seconds.setter
    def _camoufox_idle_ttl_seconds(self, value):
        self._state._camoufox_idle_ttl_seconds = value

    @property
    def _uc_max_leases(self):
        return self._state._uc_max_leases

    @property
    def _uc_idle_ttl_seconds(self):
        return self._state._uc_idle_ttl_seconds

    @property
    def _camoufox_pool_cap(self):
        return self._state._camoufox_pool_cap

    @property
    def _uc_pool_cap(self):
        return self._state._uc_pool_cap

    def _build_headers(self, strategy: CrawlPolicy) -> dict:
        if not strategy.change_ua:
            return {}

        ua = self.dynamic_profile.get(
            "user_agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        platform = self.dynamic_profile.get("sec_ch_ua_platform", '"macOS"')
        ch_ua = self.dynamic_profile.get(
            "sec_ch_ua", '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"'
        )

        return {
            "User-Agent": ua,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "sec-ch-ua": ch_ua,
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": platform,
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
        }

    def _build_fingerprint_params(self, task: CrawlTask) -> dict:
        languages = self.dynamic_profile.get("languages")
        if languages:
            try:
                languages = json.loads(languages)
            except Exception:
                pass
        return {
            "session_id": task.task_id,
            "gpu_vendor": self.dynamic_profile.get("gpu_vendor"),
            "gpu_renderer": self.dynamic_profile.get("gpu_renderer"),
            "screen_width": self.dynamic_profile.get("screen_width", 1920),
            "screen_height": self.dynamic_profile.get("screen_height", 1080),
            "device_pixel_ratio": self.dynamic_profile.get("device_pixel_ratio", 2.0),
            "platform_string": self.dynamic_profile.get("platform_string", "MacIntel"),
            "cores": self.dynamic_profile.get("cores", 8),
            "memory": self.dynamic_profile.get("memory", 8),
            "languages": languages,
            "connection_type": self.dynamic_profile.get("connection_type", "4g"),
            "downlink": self.dynamic_profile.get("downlink", 10),
            "rtt": self.dynamic_profile.get("rtt", 50),
            "plugins": self.dynamic_profile.get("plugins"),
            "usb": self.dynamic_profile.get("usb"),
            "media_devices": self.dynamic_profile.get("media_devices"),
            "battery": self.dynamic_profile.get("battery"),
            "webdriver_value": self.dynamic_profile.get("webdriver_value"),
            "permissions_default": self.dynamic_profile.get("permissions_default", "default"),
            "orientation_angle": self.dynamic_profile.get("orientation_angle", 0),
            "orientation_type": self.dynamic_profile.get("orientation_type", "landscape-primary"),
        }

    def _increment_stat(self, key: str, amount: int = 1) -> None:
        self._state.increment_stat(key, amount)

    def _navigate_page(self, page, task: CrawlTask, strategy: CrawlPolicy):
        if strategy.use_interactive_search and getattr(task, "query", None):
            from ai_crawler.browser.interaction import InteractiveSearcher
            from ai_crawler.spider.extraction.template_store import template_store

            site_config = template_store.load(task.site, "search")
            interactor = InteractiveSearcher(page, site_config)
            success = interactor.perform_search(task.query)
            if not success:
                return page.goto(
                    task.url,
                    wait_until="domcontentloaded",
                    timeout=self._navigation_timeout_ms(task, strategy),
                )
            return None
        return page.goto(
            task.url,
            wait_until="domcontentloaded",
            timeout=self._navigation_timeout_ms(task, strategy),
        )

    def _run_wrapper_with_fallback(
        self, run_wrapper: Callable[[bool], tuple[str, int | None, any]]
    ) -> tuple[str, int | None, any]:
        try:
            return run_wrapper(False)
        except Exception:
            try:
                return run_wrapper(True)
            except Exception:
                return "", None, None

    def stats_snapshot(self) -> dict:
        return self._state.stats_snapshot()

    def _install_ad_script_blocking(self, page) -> None:
        if not hasattr(page, "route"):
            return

        def handler(route):
            try:
                request = route.request
                if request.resource_type == "script" and utils.should_block_script(request.url):
                    self._increment_stat("ad_scripts_blocked")
                    route.abort()
                    return
            except Exception:
                pass
            route.continue_()

        try:
            page.route("**/*", handler)
            self._increment_stat("ad_block_handlers_installed")
        except Exception as exc:
            log.warning("ad_block_install_error", error=str(exc))

    def release_page(self, page) -> None:
        if page is None:
            return
        try:
            if hasattr(page, "is_closed") and page.is_closed():
                return
        except Exception:
            pass
        try:
            if hasattr(page, "close"):
                page.close()
                self._increment_stat("pages_released")
        except Exception:
            pass

    def close(self) -> None:
        with self._pool_lock:
            for context in self._playwright_contexts.values():
                try:
                    context.close()
                except Exception:
                    pass
            self._playwright_contexts.clear()

            for browser in self._playwright_browsers.values():
                try:
                    browser.close()
                except Exception:
                    pass
            self._playwright_browsers.clear()

            for browser in self._camoufox_browsers.values():
                try:
                    browser.close()
                except Exception:
                    pass
            for launcher in self._camoufox_launchers.values():
                try:
                    if hasattr(launcher, "__exit__"):
                        launcher.__exit__(None, None, None)
                except Exception:
                    pass
            self._camoufox_browsers.clear()
            self._camoufox_launchers.clear()
            self._camoufox_browser_meta.clear()

            for key in list(self._uc_drivers.keys()):
                self._evict_uc_driver(key)
            self._uc_drivers.clear()
            self._uc_driver_meta.clear()
            for bridge in self._uc_proxy_bridges.values():
                try:
                    bridge.stop()
                except Exception:
                    pass
            self._uc_proxy_bridges.clear()

            for browser in self._cloak_browsers.values():
                try:
                    browser.close()
                except Exception:
                    pass
            self._cloak_browsers.clear()

            if self._playwright_runtime is not None:
                try:
                    self._playwright_runtime.stop()
                except Exception:
                    pass
                self._playwright_runtime = None

    def _get_playwright_runtime(self):
        with self._pool_lock:
            if self._playwright_runtime is None:
                from playwright.sync_api import sync_playwright

                self._playwright_runtime = sync_playwright().start()
                self._stats["playwright_runtime_created"] += 1
                log.info("playwright_runtime_created")
            return self._playwright_runtime

    def _get_playwright_browser(
        self, browser_key: str, proxy_server: str | None, stealth_args: list[str]
    ):
        with self._pool_lock:
            browser = self._playwright_browsers.get(browser_key)
            if browser is not None:
                self._stats["playwright_browser_reused"] += 1
                log.info("playwright_browser_reused", browser_key=browser_key)
                return browser

            runtime = self._get_playwright_runtime()
            launch_kwargs = {"headless": True, "args": stealth_args}
            if proxy_server:
                launch_kwargs["proxy"] = {"server": proxy_server}
            browser = runtime.chromium.launch(**launch_kwargs)
            self._playwright_browsers[browser_key] = browser
            self._stats["playwright_browser_created"] += 1
            log.info("playwright_browser_created", browser_key=browser_key)
            return browser

    def _get_playwright_context(self, browser_key: str, browser, ctx_args: dict):
        context_key = utils.stable_key({"browser": browser_key, "context": ctx_args})
        with self._pool_lock:
            context = self._playwright_contexts.get(context_key)
            if context is not None:
                self._stats["playwright_context_reused"] += 1
                log.info("playwright_context_reused", context_key=context_key)
                return context
            context = browser.new_context(**ctx_args)
            self._playwright_contexts[context_key] = context
            self._stats["playwright_context_created"] += 1
            log.info("playwright_context_created", context_key=context_key)
            return context

    def _get_cloak_browser(self, browser_key: str, launch_kwargs: dict):
        with self._pool_lock:
            browser = self._cloak_browsers.get(browser_key)
            if browser is not None:
                self._stats["cloak_browser_reused"] += 1
                log.info("cloak_browser_reused", browser_key=browser_key)
                return browser

            from cloakbrowser import launch

            browser = launch(**launch_kwargs)
            self._cloak_browsers[browser_key] = browser
            self._stats["cloak_browser_created"] += 1
            log.info("cloak_browser_created", browser_key=browser_key)
            return browser

    def _wait_for_page_ready(self, page, strategy: CrawlPolicy) -> None:
        wait_ms = int((8.0 if strategy.extra_wait == 0 else strategy.extra_wait) * 1000)
        if strategy.wait_selector:
            try:
                page.wait_for_selector(strategy.wait_selector, timeout=wait_ms)
                return
            except Exception:
                pass
        page.wait_for_timeout(wait_ms)

    def _navigation_timeout_ms(self, task: CrawlTask, strategy: CrawlPolicy) -> int:
        base = int(self.page_load_timeout * 1000)
        page_pattern = getattr(task.page_pattern, "value", "unknown")
        if page_pattern == "search":
            base = max(base, 20000)
        if task.site in {"target", "amazon"} and page_pattern == "search":
            base = max(base, 30000)
        if strategy.extra_wait > 0:
            base = max(base, int(strategy.extra_wait * 1000) * 2)
        return base

    @staticmethod
    def _is_running_inside_event_loop() -> bool:
        try:
            asyncio.get_running_loop()
            return True
        except RuntimeError:
            return False

    def _get_camoufox_browser(self, browser_key: str, launch_kwargs: dict):
        with self._pool_lock:
            browser = self._camoufox_browsers.get(browser_key)
            if browser is not None:
                meta = self._camoufox_browser_meta.get(browser_key, {})
                idle = time.time() - float(meta.get("last_used", time.time()))
                leases = int(meta.get("leases", 0))
                if idle > self._camoufox_idle_ttl_seconds or leases >= self._camoufox_max_leases:
                    self._evict_camoufox_browser(browser_key)
                    browser = None
                elif self._is_camoufox_browser_healthy(browser):
                    self._stats["camoufox_browser_reused"] += 1
                    log.info("camoufox_browser_reused", browser_key=browser_key)
                    return browser
                else:
                    self._evict_camoufox_browser(browser_key)
                    browser = None

            self._trim_camoufox_pool()

            if browser is not None:
                self._stats["camoufox_browser_reused"] += 1
                log.info("camoufox_browser_reused", browser_key=browser_key)
                return browser

            from camoufox import Camoufox

            launcher = Camoufox(**launch_kwargs)
            if hasattr(launcher, "start"):
                browser = launcher.start()
            elif hasattr(launcher, "__enter__"):
                browser = launcher.__enter__()
            else:
                raise RuntimeError("Camoufox launcher does not support reusable lifecycle")

            self._camoufox_launchers[browser_key] = launcher
            self._camoufox_browsers[browser_key] = browser
            self._camoufox_browser_meta[browser_key] = {"leases": 0, "last_used": time.time()}
            self._stats["camoufox_browser_created"] += 1
            log.info("camoufox_browser_created", browser_key=browser_key)
            return browser

    def _is_camoufox_browser_healthy(self, browser) -> bool:
        try:
            if hasattr(browser, "is_connected") and not browser.is_connected():
                self._increment_stat("camoufox_healthcheck_failed")
                return False
            _ = getattr(browser, "contexts", None)
            return True
        except Exception:
            self._increment_stat("camoufox_healthcheck_failed")
            return False

    def _evict_camoufox_browser(self, browser_key: str) -> None:
        browser = self._camoufox_browsers.pop(browser_key, None)
        launcher = self._camoufox_launchers.pop(browser_key, None)
        self._camoufox_browser_meta.pop(browser_key, None)
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        if launcher is not None:
            try:
                if hasattr(launcher, "__exit__"):
                    launcher.__exit__(None, None, None)
            except Exception:
                pass
        self._increment_stat("camoufox_browser_evicted")
        log.info("camoufox_browser_evicted", browser_key=browser_key)

    def _trim_camoufox_pool(self) -> None:
        while len(self._camoufox_browsers) >= self._camoufox_pool_cap:
            oldest_key = min(
                self._camoufox_browser_meta,
                key=lambda key: float(self._camoufox_browser_meta[key].get("last_used", 0.0)),
            )
            self._evict_camoufox_browser(oldest_key)

    def _release_camoufox_browser(self, browser_key: str, browser, healthy: bool) -> None:
        with self._pool_lock:
            if not healthy:
                self._evict_camoufox_browser(browser_key)
                return
            meta = self._camoufox_browser_meta.setdefault(
                browser_key, {"leases": 0, "last_used": time.time()}
            )
            meta["leases"] = int(meta.get("leases", 0)) + 1
            meta["last_used"] = time.time()
            self._camoufox_browsers[browser_key] = browser

    def _is_uc_driver_healthy(self, driver) -> bool:
        try:
            handles = getattr(driver, "window_handles", None)
            if not handles:
                return False
            _ = driver.current_window_handle
            if hasattr(driver, "execute_script"):
                driver.execute_script("return 1")
            return True
        except Exception:
            self._increment_stat("uc_healthcheck_failed")
            return False

    def _evict_uc_driver(self, driver_key: str) -> None:
        driver = self._uc_drivers.pop(driver_key, None)
        self._uc_driver_meta.pop(driver_key, None)
        if driver is None:
            return
        try:
            driver.quit()
        except Exception:
            pass
        self._increment_stat("uc_browser_evicted")
        log.info("uc_browser_evicted", driver_key=driver_key)

    def _trim_uc_pool(self) -> None:
        while len(self._uc_drivers) >= self._uc_pool_cap:
            oldest_key = next(iter(self._uc_drivers))
            self._evict_uc_driver(oldest_key)

    def _reset_uc_driver(self, driver) -> bool:
        try:
            if hasattr(driver, "delete_all_cookies"):
                driver.delete_all_cookies()
            driver.get("about:blank")
            if hasattr(driver, "execute_script"):
                driver.execute_script(
                    "try { localStorage.clear(); sessionStorage.clear(); } catch (e) {}"
                )
            return self._is_uc_driver_healthy(driver)
        except Exception:
            self._increment_stat("uc_reset_failed")
            return False

    def _build_uc_options(self, strategy: CrawlPolicy, proxy: str | None):
        import undetected_chromedriver as uc

        options = uc.ChromeOptions()
        options.headless = True
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.page_load_strategy = "eager"
        if proxy:
            options.add_argument(f"--proxy-server={proxy}")
        user_agent = self.dynamic_profile.get("user_agent")
        if strategy.change_ua and user_agent:
            options.add_argument(f"--user-agent={user_agent}")
        return options

    def _get_uc_driver(self, driver_key: str, strategy: CrawlPolicy, proxy: str | None):
        import undetected_chromedriver as uc

        with self._pool_lock:
            driver = self._uc_drivers.get(driver_key)
            if driver is not None:
                meta = self._uc_driver_meta.get(driver_key, {})
                idle = time.time() - float(meta.get("last_used", time.time()))
                leases = int(meta.get("leases", 0))
                if idle > self._uc_idle_ttl_seconds or leases >= self._uc_max_leases:
                    self._evict_uc_driver(driver_key)
                    driver = None
                elif self._is_uc_driver_healthy(driver):
                    self._uc_drivers.move_to_end(driver_key)
                    self._stats["uc_browser_reused"] += 1
                    log.info("uc_browser_reused", driver_key=driver_key)
                    return driver
                else:
                    self._evict_uc_driver(driver_key)
                    driver = None

            self._trim_uc_pool()
            options = self._build_uc_options(strategy, proxy)
            driver = uc.Chrome(options=options, version_main=None)
            driver.set_page_load_timeout(20)
            try:
                driver.set_script_timeout(20)
            except Exception:
                pass
            self._uc_drivers[driver_key] = driver
            self._uc_driver_meta[driver_key] = {"leases": 0, "last_used": time.time()}
            self._stats["uc_browser_created"] += 1
            log.info("uc_browser_created", driver_key=driver_key)
            return driver

    def _get_uc_proxy_bridge(self, upstream_proxy_url: str):
        from ai_crawler.spider.engine.proxy.uc_bridge import UCProxyBridge

        with self._pool_lock:
            bridge = self._uc_proxy_bridges.get(upstream_proxy_url)
            if bridge is not None and bridge.healthy():
                return bridge
            if bridge is not None:
                try:
                    bridge.stop()
                except Exception:
                    pass
            bridge = UCProxyBridge(upstream_proxy_url)
            bridge.start()
            self._uc_proxy_bridges[upstream_proxy_url] = bridge
            return bridge

    def _release_uc_driver(self, driver_key: str, driver, healthy: bool) -> None:
        with self._pool_lock:
            if not healthy:
                self._evict_uc_driver(driver_key)
                return
            meta = self._uc_driver_meta.setdefault(
                driver_key, {"leases": 0, "last_used": time.time()}
            )
            meta["leases"] = int(meta.get("leases", 0)) + 1
            meta["last_used"] = time.time()
            self._uc_drivers[driver_key] = driver
            self._uc_drivers.move_to_end(driver_key)

    @staticmethod
    def _can_salvage_uc_html(html: str) -> bool:
        lowered = (html or "").lower()
        if len(html or "") < 50000:
            return False
        hard_error_markers = [
            "err_no_supported_proxies",
            "this site can't be reached",
            "chrome-error://",
            "sorry! something went wrong!",
            "we couldn't process your request",
        ]
        return not any(marker in lowered for marker in hard_error_markers)

    _FETCH_STRATEGIES: dict = None

    @classmethod
    def _register_strategies(cls):
        if cls._FETCH_STRATEGIES is not None:
            return
        cls._FETCH_STRATEGIES = {
            RenderType.OPENCLI: cls._fetch_with_opencli,
            RenderType.CAMOUFOX: cls._fetch_with_camoufox,
            RenderType.CLOAKBROWSER: cls._fetch_with_cloakbrowser,
            RenderType.PLAYWRIGHT: cls._fetch_with_playwright,
            RenderType.CLOUDERA: cls._fetch_with_uc,
            RenderType.CLOUDSCRAPER: cls._fetch_with_cloudscraper,
            RenderType.SELENIUMBASE: cls._fetch_with_seleniumbase,
            RenderType.KAMELEO: cls._fetch_with_kameleo,
            RenderType.LIGHTPAND: cls._fetch_with_lightpanda,
            RenderType.NONE: cls._fetch_with_httpx,
        }

    def fetch_with_strategy(
        self, task: CrawlTask, strategy: CrawlPolicy
    ) -> tuple[str, int | None, any]:
        self._register_strategies()
        fetcher = self._FETCH_STRATEGIES.get(strategy.render, self._fetch_with_httpx)
        return fetcher(self, task, strategy)

    def _fetch_with_opencli(
        self, task: CrawlTask, strategy: CrawlPolicy
    ) -> tuple[str, int | None, any]:
        from ai_crawler.browser.wrappers.opencli import fetch_and_intercept
        from ai_crawler.browser.wrappers.opencli import search as opencli_search

        delay_min, delay_max = strategy.delay_before
        if delay_min > 0:
            time.sleep(random.uniform(delay_min, delay_max))
        try:
            wait = 8.0 + strategy.extra_wait
            profile = task.metadata.get("opencli_profile")
            session_id = f"crawl-{task.task_id}"

            # Interactive search: type query into search box like a human,
            # matching the same behaviour as Playwright/Camoufox InteractiveSearcher.
            if strategy.use_interactive_search and task.query:
                html, status = opencli_search(
                    task.url,
                    task.query,
                    session=session_id,
                    profile=profile,
                    timeout=30,
                )
                return html, status, None

            # Single navigation: capture API endpoints AND page HTML in one shot.
            html, status, raw_endpoints = fetch_and_intercept(
                task.url,
                session=session_id,
                profile=profile,
                wait_time=wait,
                wait_selector=strategy.wait_selector,
            )

            # Filter out data: URIs, tracking/analytics, and static resources.
            # Only keep entries that could be useful for Tier 1+ direct API calls.
            _tracking_domains = {
                "amazon-adsystem.com", "doubleclick.net", "google-analytics.com",
                "googletagmanager.com", "facebook.com/tr", "bat.bing.com",
                "analytics.twitter.com", "ads.linkedin.com",
            }
            entries = [
                e for e in raw_endpoints
                if isinstance(e, dict)
                and not e.get("url", "").startswith("data:")
                and not any(d in e.get("url", "") for d in _tracking_domains)
            ]

            if entries:
                from ai_crawler.data.endpoints_store import save_endpoints

                page_pattern = task.page_pattern.value if task.page_pattern else "search"
                try:
                    save_endpoints(task.site, entries, page_pattern)
                    log.info(
                        "opencli_endpoints_saved",
                        site=task.site,
                        count=len(entries),
                    )
                except Exception as save_exc:
                    log.warning("opencli_save_endpoints_failed", error=str(save_exc))
            else:
                log.info(
                    "opencli_no_endpoints",
                    site=task.site,
                    raw_len=len(raw_endpoints),
                )

            return html, status, None
        except Exception as exc:
            log.warning("opencli_error", url=task.url, error=str(exc))
            return "", None, None

    def _fetch_with_httpx(
        self, task: CrawlTask, strategy: CrawlPolicy
    ) -> tuple[str, int | None, any]:
        from curl_cffi import requests

        proxy = self.proxy_provider.proxy_url(strategy) if self.proxy_provider else None
        proxies = {"http": proxy, "https": proxy} if proxy else None
        headers = self._build_headers(strategy)

        # Try saved API endpoint first — faster than parsing HTML.
        # Endpoints are discovered by Tier 0 (OpenCLI network_intercept) and
        # persisted to data/<site>/endpoints.json.
        try:
            from ai_crawler.data.endpoints_store import get_best_endpoint

            page_pattern = task.page_pattern.value if task.page_pattern else "search"
            ep = get_best_endpoint(task.site, page_pattern)
            if ep:
                api_url = ep["url"]
                if task.query:
                    import urllib.parse as urlparse
                    parsed = urlparse.urlparse(api_url)
                    params = dict(urlparse.parse_qsl(parsed.query))
                    for key in params:
                        if key.lower() in ("q", "query", "keyword", "search", "term", "keywords"):
                            params[key] = task.query
                            break
                    api_url = urlparse.urlunparse(parsed._replace(query=urlparse.urlencode(params)))

                delay_min, delay_max = strategy.delay_before
                if delay_min > 0:
                    time.sleep(random.uniform(delay_min, delay_max))

                try:
                    with requests.Session(
                        impersonate=self.dynamic_profile.get("curl_impersonate_target", "chrome120"),
                        proxies=proxies,
                    ) as client:
                        resp = client.get(
                            api_url,
                            headers=headers,
                            timeout=self.request_timeout,
                            allow_redirects=True,
                        )
                        if resp.status_code == 200 and len(resp.text) > 500:
                            log.info("httpx_endpoint_hit", site=task.site, url=api_url[:120])
                            return resp.text, resp.status_code, None
                except Exception:
                    pass
        except Exception:
            pass

        delay_min, delay_max = strategy.delay_before
        if delay_min > 0:
            time.sleep(random.uniform(delay_min, delay_max))

        cookies = {}
        domain = task.url.split("/")[2]
        if strategy.use_cookies and domain in self._session_cookies:
            cookies = {c["name"]: c["value"] for c in self._session_cookies[domain]}

        try:
            with requests.Session(
                impersonate=self.dynamic_profile.get("curl_impersonate_target", "chrome120"),
                proxies=proxies,
            ) as client:
                resp = client.get(
                    task.url,
                    headers=headers,
                    cookies=cookies,
                    timeout=self.request_timeout,
                    allow_redirects=True,
                )
                try:
                    page_cookies = client.cookies.get_dict()
                    self._session_cookies[domain] = [
                        {"name": n, "value": v} for n, v in page_cookies.items()
                    ]
                except Exception:
                    pass
                return resp.text, resp.status_code, None
        except Exception as exc:
            log.warning("fetch_error", url=task.url, error=str(exc))
            return "", None, None

    def _fetch_with_camoufox(
        self, task: CrawlTask, strategy: CrawlPolicy
    ) -> tuple[str, int | None, any]:
        delay_min, delay_max = strategy.delay_before
        if delay_min > 0:
            time.sleep(random.uniform(delay_min, delay_max))
        browser = None
        browser_key = ""
        try:
            from ai_crawler.browser.human.fingerprint import get_fingerprint_script
            from ai_crawler.browser.wrappers.camoufox import _sync_launch as camoufox_sync_launch

            proxy = self.proxy_provider.proxy_url(strategy) if self.proxy_provider else None
            proxy_settings = utils.structured_proxy_settings(proxy)
            launch_kwargs = {"headless": True}
            if proxy_settings:
                launch_kwargs["proxy"] = proxy_settings
            browser_key = utils.stable_key(launch_kwargs)
            browser = self._get_camoufox_browser(browser_key, launch_kwargs)

            page = browser.new_page()
            self._increment_stat("pages_opened")
            self._install_ad_script_blocking(page)
            page.set_default_timeout(self.page_load_timeout * 1000)

            page.add_init_script(get_fingerprint_script(**self._build_fingerprint_params(task)))

            resp = self._navigate_page(page, task, strategy)

            self._wait_for_page_ready(page, strategy)
            if strategy.use_human_scroll:
                self._human_scroll(page)
            content = page.content()
            self._release_camoufox_browser(browser_key, browser, healthy=True)
            from ai_crawler.browser.operator import BrowserOperator
            from ai_crawler.browser.human.mouse import PlaywrightMouseAdapter
            return content, resp.status if resp else 200, BrowserOperator(page, PlaywrightMouseAdapter(page))
        except Exception as exc:
            if browser is not None and browser_key:
                self._release_camoufox_browser(
                    browser_key, browser, healthy=self._is_camoufox_browser_healthy(browser)
                )
            if "Playwright Sync API inside the asyncio loop" in str(exc):
                try:
                    with ThreadPoolExecutor(max_workers=1) as fallback_executor:
                        html = fallback_executor.submit(
                            camoufox_sync_launch,
                            task.url,
                            proxy,
                            strategy.wait_selector,
                            8.0 if strategy.extra_wait == 0 else strategy.extra_wait,
                            strategy.use_human_scroll,
                        ).result()
                    return html, 200, None
                except Exception as fallback_exc:
                    log.warning(
                        "camoufox_async_fallback_error",
                        url=task.url,
                        error=str(fallback_exc),
                    )
            log.warning("camoufox_error", url=task.url, error=str(exc))
            return "", None, None

    def _fetch_with_playwright(
        self, task: CrawlTask, strategy: CrawlPolicy
    ) -> tuple[str, int | None, any]:
        delay_min, delay_max = strategy.delay_before
        if delay_min > 0:
            time.sleep(random.uniform(delay_min, delay_max))
        try:
            from playwright_stealth import Stealth
            from ai_crawler.browser.human.fingerprint import get_fingerprint_script

            stealth_args = ["--disable-blink-features=AutomationControlled"]
            if self.dynamic_profile and self.dynamic_profile.get("stealth_args"):
                try:
                    args_list = json.loads(self.dynamic_profile["stealth_args"])
                    if isinstance(args_list, list):
                        stealth_args.extend(args_list)
                except Exception:
                    pass

            proxy_server = self.proxy_provider.proxy_url(strategy) if self.proxy_provider else None
            browser_key = utils.stable_key({"proxy": proxy_server, "args": stealth_args})
            browser = self._get_playwright_browser(browser_key, proxy_server, stealth_args)

            ctx_args = {
                "locale": self.dynamic_profile.get("locale", "en-US"),
                "timezone_id": self.dynamic_profile.get("timezone_id", "America/New_York"),
                "viewport": {"width": 1920, "height": 1080},
                "user_agent": self.dynamic_profile.get(
                    "user_agent",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                ),
            }
            try:
                vp_str = self.dynamic_profile.get("viewport")
                if vp_str:
                    vp = json.loads(vp_str)
                    if "width" in vp and "height" in vp:
                        ctx_args["viewport"] = vp
            except Exception:
                pass

            ctx = self._get_playwright_context(browser_key, browser, ctx_args)
            page = ctx.new_page()
            self._increment_stat("pages_opened")
            self._install_ad_script_blocking(page)
            Stealth().apply_stealth_sync(page)

            page.add_init_script(get_fingerprint_script(**self._build_fingerprint_params(task)))

            resp = self._navigate_page(page, task, strategy)

            self._wait_for_page_ready(page, strategy)
            if strategy.use_human_scroll:
                self._human_scroll(page)
            content = page.content()
            status = resp.status if resp else 200
            from ai_crawler.browser.operator import BrowserOperator
            from ai_crawler.browser.human.mouse import PlaywrightMouseAdapter
            return content, status, BrowserOperator(page, PlaywrightMouseAdapter(page))
        except Exception as exc:
            log.warning("playwright_error", url=task.url, error=str(exc))
            return "", None, None

    def _fetch_with_uc(
        self, task: CrawlTask, strategy: CrawlPolicy
    ) -> tuple[str, int | None, any]:
        delay_min, delay_max = strategy.delay_before
        if delay_min > 0:
            time.sleep(random.uniform(delay_min, delay_max))
        driver = None
        driver_key = ""
        try:
            proxy = self.proxy_provider.proxy_url(strategy) if self.proxy_provider else None
            proxy_settings = utils.structured_proxy_settings(proxy)
            if proxy_settings and (
                proxy_settings.get("username") or proxy_settings.get("password")
            ):
                bridge = self._get_uc_proxy_bridge(proxy)
                local_proxy_url = bridge.local_proxy_url()
                proxy_settings = utils.structured_proxy_settings(local_proxy_url)
            driver_key = utils.stable_key(
                {
                    "proxy": proxy_settings.get("server") if proxy_settings else None,
                    "site": task.site,
                    "headless": True,
                    "change_ua": strategy.change_ua,
                    "user_agent": self.dynamic_profile.get("user_agent")
                    if strategy.change_ua
                    else None,
                }
            )
            driver = self._get_uc_driver(
                driver_key,
                strategy,
                proxy_settings.get("server") if proxy_settings else None,
            )
            driver.get(task.url)
            time.sleep(5)
            content = driver.page_source
            self._release_uc_driver(driver_key, driver, healthy=self._reset_uc_driver(driver))
            return content, 200, None
        except Exception as exc:
            salvaged_html = ""
            try:
                if driver is not None:
                    salvaged_html = driver.page_source or ""
            except Exception:
                salvaged_html = ""

            if self._can_salvage_uc_html(salvaged_html):
                if driver is not None and driver_key:
                    self._release_uc_driver(
                        driver_key,
                        driver,
                        healthy=self._reset_uc_driver(driver),
                    )
                return salvaged_html, 200, None

            if driver is not None and driver_key:
                self._release_uc_driver(driver_key, driver, healthy=False)
            log.warning("uc_error", url=task.url, error=str(exc))
            return "", None, None

    def _fetch_with_cloudscraper(
        self, task: CrawlTask, strategy: CrawlPolicy
    ) -> tuple[str, int | None, any]:
        delay_min, delay_max = strategy.delay_before
        if delay_min > 0:
            time.sleep(random.uniform(delay_min, delay_max))
        try:
            import cloudscraper

            scraper = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "desktop": True},
            )
            proxy = self.proxy_provider.proxy_url(strategy) if self.proxy_provider else None
            kwargs = {"timeout": self.request_timeout}
            if proxy:
                kwargs["proxies"] = {"http": proxy, "https": proxy}
            resp = scraper.get(task.url, **kwargs)
            return resp.text, resp.status_code, None
        except Exception as exc:
            log.warning("cloudscraper_error", url=task.url, error=str(exc))
            return "", None, None

    def _fetch_with_lightpanda(
        self, task: CrawlTask, strategy: CrawlPolicy
    ) -> tuple[str, int | None, any]:
        from ai_crawler.browser.wrappers.lightpanda import LightpandaWrapper

        delay_min, delay_max = strategy.delay_before
        if delay_min > 0:
            time.sleep(random.uniform(delay_min, delay_max))
        proxy = self.proxy_provider.proxy_url(strategy) if self.proxy_provider else None

        def run_wrapper(undetected: bool) -> tuple[str, int | None, any]:
            wrapper = LightpandaWrapper(
                headless=True,
                proxy=proxy,
                wait_time=8.0 if strategy.extra_wait == 0 else strategy.extra_wait,
                human_scroll=strategy.use_human_scroll,
                dynamic_profile=self.dynamic_profile or {},
            )
            with wrapper.launch():
                html, status = wrapper.fetch(task.url)
                if strategy.use_human_scroll and wrapper.human_scroll:
                    try:
                        from playwright.sync_api import sync_playwright

                        with sync_playwright() as p:
                            browser = p.chromium.connect_over_cdp(wrapper._cdp_url)
                            page = browser.new_page()
                            wrapper._human_scroll(page)
                            page.close()
                            browser.close()
                    except Exception:
                        pass
                return html, status, None

        return self._run_wrapper_with_fallback(run_wrapper)

    def _fetch_with_seleniumbase(
        self, task: CrawlTask, strategy: CrawlPolicy
    ) -> tuple[str, int | None, any]:
        from ai_crawler.browser.wrappers.seleniumbase import SeleniumBaseWrapper

        delay_min, delay_max = strategy.delay_before
        if delay_min > 0:
            time.sleep(random.uniform(delay_min, delay_max))
        proxy = self.proxy_provider.proxy_url(strategy) if self.proxy_provider else None

        def run_wrapper(undetected: bool) -> tuple[str, int | None, any]:
            wrapper = SeleniumBaseWrapper(
                headless=True,
                proxy=proxy,
                undetected=undetected,
                wait_selector=strategy.wait_selector,
                wait_time=8.0 if strategy.extra_wait == 0 else strategy.extra_wait,
                human_scroll=strategy.use_human_scroll,
                dynamic_profile=self.dynamic_profile or {},
            )
            driver = wrapper.create_driver()
            try:
                wrapper._add_stealth_js(driver)
                html, status = wrapper.fetch_with_driver(
                    driver,
                    task.url,
                    wait_selector=strategy.wait_selector,
                    wait_time=8.0 if strategy.extra_wait == 0 else strategy.extra_wait,
                    human_scroll=strategy.use_human_scroll,
                )
                return html, status, None
            finally:
                wrapper.close_driver(driver)

        try:
            return run_wrapper(True)
        except Exception as exc:
            if "cannot connect to chrome at 127.0.0.1:9222" in str(
                exc
            ) or "session not created" in str(exc):
                try:
                    return run_wrapper(False)
                except Exception as fallback_exc:
                    log.warning(
                        "seleniumbase_fallback_error",
                        url=task.url,
                        error=str(fallback_exc),
                    )
            log.warning("seleniumbase_error", url=task.url, error=str(exc))
            return "", None, None

    def _fetch_with_kameleo(
        self, task: CrawlTask, strategy: CrawlPolicy
    ) -> tuple[str, int | None, any]:
        from ai_crawler.browser.wrappers.kameleo import KameleoWrapper
        from ai_crawler.config import config

        delay_min, delay_max = strategy.delay_before
        if delay_min > 0:
            time.sleep(random.uniform(delay_min, delay_max))
        proxy = self.proxy_provider.proxy_url(strategy) if self.proxy_provider else None
        try:
            wrapper = KameleoWrapper(
                api_url=config.KAMELEO_API_URL,
                api_key=config.KAMELEO_API_KEY,
                proxy=proxy,
                wait_time=8.0 if strategy.extra_wait == 0 else strategy.extra_wait,
                human_scroll=strategy.use_human_scroll,
                dynamic_profile=self.dynamic_profile or {},
            )
            return wrapper.fetch(task.url), 200, None
        except Exception as exc:
            log.warning("kameleo_error", url=task.url, error=str(exc))
            return "", None, None

    def _fetch_with_cloakbrowser(
        self, task: CrawlTask, strategy: CrawlPolicy
    ) -> tuple[str, int | None, any]:
        delay_min, delay_max = strategy.delay_before
        if delay_min > 0:
            time.sleep(random.uniform(delay_min, delay_max))
        proxy = self.proxy_provider.proxy_url(strategy) if self.proxy_provider else None
        try:
            from ai_crawler.browser.wrappers.cloakbrowser import _sync_fetch as cloak_sync_fetch

            if self._is_running_inside_event_loop():
                with ThreadPoolExecutor(max_workers=1) as fallback_executor:
                    html, status = fallback_executor.submit(
                        cloak_sync_fetch,
                        task.url,
                        proxy,
                        strategy.wait_selector,
                        8.0 if strategy.extra_wait == 0 else strategy.extra_wait,
                        strategy.use_human_scroll,
                        self.dynamic_profile or {},
                    ).result()
                return html, status, None

            launch_kwargs = {"headless": True}
            proxy_settings = utils.structured_proxy_settings(proxy)
            if proxy_settings:
                launch_kwargs["proxy"] = proxy_settings
            viewport_dict = self.dynamic_profile.get("viewport")
            browser_key = utils.stable_key({"proxy": proxy_settings, "launch": launch_kwargs})
            browser = self._get_cloak_browser(browser_key, launch_kwargs)
            page = browser.new_page()
            self._increment_stat("pages_opened")
            self._install_ad_script_blocking(page)
            if viewport_dict and hasattr(page, "set_viewport_size"):
                try:
                    viewport = (
                        json.loads(viewport_dict)
                        if isinstance(viewport_dict, str)
                        else viewport_dict
                    )
                    page.set_viewport_size(viewport)
                except Exception:
                    pass
            languages = self.dynamic_profile.get("languages")
            if languages:
                try:
                    languages = json.loads(languages)
                    page.set_extra_http_headers(
                        {
                            "Accept-Language": ",".join(languages)
                            if isinstance(languages, list)
                            else languages
                        }
                    )
                except Exception:
                    pass

            resp = self._navigate_page(page, task, strategy)

            self._wait_for_page_ready(page, strategy)
            if strategy.use_human_scroll:
                self._human_scroll(page)
            content = page.content()
            status = resp.status if resp else 200
            from ai_crawler.browser.operator import BrowserOperator
            from ai_crawler.browser.human.mouse import CloakBrowserMouseAdapter
            return content, status, BrowserOperator(page, CloakBrowserMouseAdapter(page))
        except ModuleNotFoundError:
            return (
                utils.browser_error_html(
                    "CloakBrowser Unavailable",
                    "RUNTIME_MISSING_MODULE cloakbrowser browser path unavailable",
                ),
                200,
                None,
            )
        except Exception as exc:
            if "Playwright Sync API inside the asyncio loop" in str(exc):
                try:
                    with ThreadPoolExecutor(max_workers=1) as fallback_executor:
                        html, status = fallback_executor.submit(
                            cloak_sync_fetch,
                            task.url,
                            proxy,
                            strategy.wait_selector,
                            8.0 if strategy.extra_wait == 0 else strategy.extra_wait,
                            strategy.use_human_scroll,
                            self.dynamic_profile or {},
                        ).result()
                    return html, status, None
                except Exception as fallback_exc:
                    log.warning(
                        "cloakbrowser_async_fallback_error",
                        url=task.url,
                        error=str(fallback_exc),
                    )
            log.warning("cloakbrowser_error", url=task.url, error=str(exc))
            return "", None, None

    def _human_scroll(self, page):
        try:
            from ai_crawler.browser.human.mouse import HumanMouseController
            import json

            viewport = page.viewport_size or {"width": 1920, "height": 1080}
            jitter_std = 2.5
            curve_intensity = 0.3
            try:
                bh_str = self.dynamic_profile.get("mouse_behavior")
                if bh_str:
                    bh = json.loads(bh_str)
                    jitter_std = bh.get("jitter_std", 2.5)
                    curve_intensity = bh.get("curve_intensity", 0.3)
            except Exception:
                pass

            controller = HumanMouseController(
                page, jitter_std=jitter_std, curve_intensity=curve_intensity
            )
            for _ in range(random.randint(2, 4)):
                x = random.randint(100, viewport["width"] - 100)
                y = random.randint(100, viewport["height"] - 100)
                controller.move_to(x, y)
                time.sleep(random.uniform(0.2, 0.6))
            for _ in range(random.randint(3, 6)):
                scroll_y = random.randint(300, 800)
                page.mouse.wheel(0, scroll_y)
                time.sleep(random.uniform(0.8, 2.5))
        except Exception as exc:
            log.warning("human_scroll_error", error=str(exc))
