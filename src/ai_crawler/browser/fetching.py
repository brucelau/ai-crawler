from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import random
import time
from collections import OrderedDict
from threading import RLock
from urllib.parse import urlparse

import structlog

from ai_crawler.core.strategy import CrawlStrategy, CrawlTask, RenderType


log = structlog.get_logger()


class Fetcher:
    AD_SCRIPT_HOST_MARKERS = (
        "doubleclick.net",
        "googlesyndication.com",
        "adservice.google.com",
        "googleadservices.com",
        "adnxs.com",
        "criteo.com",
        "criteo.net",
        "taboola.com",
        "outbrain.com",
        "ads-twitter.com",
        "amazon-adsystem.com",
        "adsrvr.org",
    )

    def __init__(
        self,
        proxy_provider=None,
        dynamic_profile: dict | None = None,
        request_timeout: float | None = None,
        page_load_timeout: float | None = None,
    ):
        from ai_crawler.config import config

        self.proxy_provider = proxy_provider
        self._session_cookies: dict[str, list] = {}
        self.dynamic_profile = dynamic_profile or {}
        self.request_timeout = request_timeout or config.REQUEST_TIMEOUT
        self.page_load_timeout = page_load_timeout or config.PAGE_LOAD_TIMEOUT
        self._pool_lock = RLock()
        self._playwright_runtime = None
        self._playwright_browsers: dict[str, any] = {}
        self._playwright_contexts: dict[str, any] = {}
        self._camoufox_launchers: dict[str, any] = {}
        self._camoufox_browsers: dict[str, any] = {}
        self._camoufox_browser_meta: dict[str, dict[str, float | int]] = {}
        self._uc_proxy_bridges: dict[str, any] = {}
        self._uc_drivers: OrderedDict[str, any] = OrderedDict()
        self._uc_driver_meta: dict[str, dict[str, float | int]] = {}
        self._cloak_browsers: dict[str, any] = {}
        self._camoufox_pool_cap = 2
        self._camoufox_max_leases = 5
        self._camoufox_idle_ttl_seconds = 300
        self._uc_pool_cap = 2
        self._uc_max_leases = 2
        self._uc_idle_ttl_seconds = 120
        self._stats = {
            "playwright_runtime_created": 0,
            "playwright_browser_created": 0,
            "playwright_browser_reused": 0,
            "playwright_context_created": 0,
            "playwright_context_reused": 0,
            "camoufox_browser_created": 0,
            "camoufox_browser_reused": 0,
            "camoufox_browser_evicted": 0,
            "camoufox_healthcheck_failed": 0,
            "uc_browser_created": 0,
            "uc_browser_reused": 0,
            "uc_browser_evicted": 0,
            "uc_healthcheck_failed": 0,
            "uc_reset_failed": 0,
            "cloak_browser_created": 0,
            "cloak_browser_reused": 0,
            "pages_opened": 0,
            "pages_released": 0,
            "ad_block_handlers_installed": 0,
            "ad_scripts_blocked": 0,
        }

    def _build_headers(self, strategy: CrawlStrategy) -> dict:
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

    @staticmethod
    def _stable_key(payload: dict) -> str:
        return json.dumps(payload, sort_keys=True, default=str)

    @staticmethod
    def _structured_proxy_settings(proxy: str | None) -> dict | None:
        if not proxy:
            return None
        parsed = urlparse(proxy)
        if not parsed.scheme or not parsed.hostname or not parsed.port:
            return {"server": proxy}
        settings = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
        if parsed.username:
            settings["username"] = parsed.username
        if parsed.password:
            settings["password"] = parsed.password
        return settings

    @staticmethod
    def _browser_error_html(title: str, message: str) -> str:
        return f"<html><head><title>{title}</title></head><body>{message}</body></html>"

    def _should_block_script(self, url: str) -> bool:
        lowered = url.lower()
        return any(marker in lowered for marker in self.AD_SCRIPT_HOST_MARKERS)

    def _increment_stat(self, key: str, amount: int = 1) -> None:
        with self._pool_lock:
            self._stats[key] = self._stats.get(key, 0) + amount

    def stats_snapshot(self) -> dict:
        with self._pool_lock:
            snapshot = dict(self._stats)
            snapshot.update(
                {
                    "active_playwright_browsers": len(self._playwright_browsers),
                    "active_playwright_contexts": len(self._playwright_contexts),
                    "active_camoufox_browsers": len(self._camoufox_browsers),
                    "active_uc_proxy_bridges": len(self._uc_proxy_bridges),
                    "active_uc_browsers": len(self._uc_drivers),
                    "active_cloak_browsers": len(self._cloak_browsers),
                }
            )
            return snapshot

    def _install_ad_script_blocking(self, page) -> None:
        if not hasattr(page, "route"):
            return

        def handler(route):
            try:
                request = route.request
                if request.resource_type == "script" and self._should_block_script(request.url):
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
        context_key = self._stable_key({"browser": browser_key, "context": ctx_args})
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

    def _wait_for_page_ready(self, page, strategy: CrawlStrategy) -> None:
        wait_ms = int((8.0 if strategy.extra_wait == 0 else strategy.extra_wait) * 1000)
        if strategy.wait_selector:
            try:
                page.wait_for_selector(strategy.wait_selector, timeout=wait_ms)
                return
            except Exception:
                pass
        page.wait_for_timeout(wait_ms)

    def _navigation_timeout_ms(self, task: CrawlTask, strategy: CrawlStrategy) -> int:
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

    def _build_uc_options(self, strategy: CrawlStrategy, proxy: str | None):
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

    def _get_uc_driver(self, driver_key: str, strategy: CrawlStrategy, proxy: str | None):
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
        from ai_crawler.proxy.uc_bridge import UCProxyBridge

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

    def fetch_with_strategy(
        self, task: CrawlTask, strategy: CrawlStrategy
    ) -> tuple[str, int | None, any]:
        if strategy.render == RenderType.CAMOUFOX:
            return self._fetch_with_camoufox(task, strategy)
        if strategy.render == RenderType.CLOAKBROWSER:
            return self._fetch_with_cloakbrowser(task, strategy)
        if strategy.render == RenderType.PLAYWRIGHT:
            return self._fetch_with_playwright(task, strategy)
        if strategy.render == RenderType.CLOUDERA:
            return self._fetch_with_uc(task, strategy)
        if strategy.render == RenderType.CLOUDSCRAPER:
            return self._fetch_with_cloudscraper(task, strategy)
        if strategy.render == RenderType.SELENIUMBASE:
            return self._fetch_with_seleniumbase(task, strategy)
        if strategy.render == RenderType.KAMELEO:
            return self._fetch_with_kameleo(task, strategy)
        if strategy.render == RenderType.LIGHTPAND:
            return self._fetch_with_lightpanda(task, strategy)
        return self._fetch_with_httpx(task, strategy)

    def _fetch_with_httpx(
        self, task: CrawlTask, strategy: CrawlStrategy
    ) -> tuple[str, int | None, any]:
        from curl_cffi import requests

        proxy = self.proxy_provider.proxy_url(strategy) if self.proxy_provider else None
        proxies = {"http": proxy, "https": proxy} if proxy else None
        headers = self._build_headers(strategy)

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
        self, task: CrawlTask, strategy: CrawlStrategy
    ) -> tuple[str, int | None, any]:
        delay_min, delay_max = strategy.delay_before
        if delay_min > 0:
            time.sleep(random.uniform(delay_min, delay_max))
        browser = None
        browser_key = ""
        try:
            from ai_crawler.browser.fingerprint_spoofer import get_fingerprint_script
            from ai_crawler.browser.camoufox_wrapper import _sync_launch as camoufox_sync_launch

            proxy = self.proxy_provider.proxy_url(strategy) if self.proxy_provider else None
            proxy_settings = self._structured_proxy_settings(proxy)
            launch_kwargs = {"headless": True}
            if proxy_settings:
                launch_kwargs["proxy"] = proxy_settings
            browser_key = self._stable_key(launch_kwargs)
            browser = self._get_camoufox_browser(browser_key, launch_kwargs)

            page = browser.new_page()
            self._increment_stat("pages_opened")
            self._install_ad_script_blocking(page)
            page.set_default_timeout(self.page_load_timeout * 1000)

            languages = self.dynamic_profile.get("languages")
            if languages:
                try:
                    languages = json.loads(languages)
                except Exception:
                    pass

            fp_params = {
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
                "orientation_type": self.dynamic_profile.get(
                    "orientation_type", "landscape-primary"
                ),
            }
            page.add_init_script(get_fingerprint_script(**fp_params))
            resp = page.goto(
                task.url,
                wait_until="domcontentloaded",
                timeout=self._navigation_timeout_ms(task, strategy),
            )
            self._wait_for_page_ready(page, strategy)
            if strategy.use_human_scroll:
                self._human_scroll(page)
            content = page.content()
            self._release_camoufox_browser(browser_key, browser, healthy=True)
            return content, resp.status if resp else 200, page
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
        self, task: CrawlTask, strategy: CrawlStrategy
    ) -> tuple[str, int | None, any]:
        delay_min, delay_max = strategy.delay_before
        if delay_min > 0:
            time.sleep(random.uniform(delay_min, delay_max))
        try:
            from playwright_stealth import Stealth
            from ai_crawler.browser.fingerprint_spoofer import get_fingerprint_script

            stealth_args = ["--disable-blink-features=AutomationControlled"]
            if self.dynamic_profile and self.dynamic_profile.get("stealth_args"):
                try:
                    args_list = json.loads(self.dynamic_profile["stealth_args"])
                    if isinstance(args_list, list):
                        stealth_args.extend(args_list)
                except Exception:
                    pass

            proxy_server = self.proxy_provider.proxy_url(strategy) if self.proxy_provider else None
            browser_key = self._stable_key({"proxy": proxy_server, "args": stealth_args})
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

            languages = self.dynamic_profile.get("languages")
            if languages:
                try:
                    languages = json.loads(languages)
                except Exception:
                    pass
            fp_params = {
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
                "orientation_type": self.dynamic_profile.get(
                    "orientation_type", "landscape-primary"
                ),
            }
            page.add_init_script(get_fingerprint_script(**fp_params))
            resp = page.goto(
                task.url,
                wait_until="domcontentloaded",
                timeout=self._navigation_timeout_ms(task, strategy),
            )
            self._wait_for_page_ready(page, strategy)
            if strategy.use_human_scroll:
                self._human_scroll(page)
            content = page.content()
            status = resp.status if resp else 200
            return content, status, page
        except Exception as exc:
            log.warning("playwright_error", url=task.url, error=str(exc))
            return "", None, None

    def _fetch_with_uc(
        self, task: CrawlTask, strategy: CrawlStrategy
    ) -> tuple[str, int | None, any]:
        delay_min, delay_max = strategy.delay_before
        if delay_min > 0:
            time.sleep(random.uniform(delay_min, delay_max))
        driver = None
        driver_key = ""
        try:
            proxy = self.proxy_provider.proxy_url(strategy) if self.proxy_provider else None
            proxy_settings = self._structured_proxy_settings(proxy)
            if proxy_settings and (
                proxy_settings.get("username") or proxy_settings.get("password")
            ):
                bridge = self._get_uc_proxy_bridge(proxy)
                local_proxy_url = bridge.local_proxy_url()
                proxy_settings = self._structured_proxy_settings(local_proxy_url)
            driver_key = self._stable_key(
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
        self, task: CrawlTask, strategy: CrawlStrategy
    ) -> tuple[str, int | None, any]:
        delay_min, delay_max = strategy.delay_before
        if delay_min > 0:
            time.sleep(random.uniform(delay_min, delay_max))
        try:
            import cloudscraper

            proxy = self.proxy_provider.proxy_url(strategy) if self.proxy_provider else None
            scraper = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "desktop": True},
                proxy=proxy,
            )
            resp = scraper.get(task.url, timeout=self.request_timeout)
            return resp.text, resp.status_code, None
        except Exception as exc:
            log.warning("cloudscraper_error", url=task.url, error=str(exc))
            return "", None, None

    def _fetch_with_lightpanda(
        self, task: CrawlTask, strategy: CrawlStrategy
    ) -> tuple[str, int | None, any]:
        from ai_crawler.browser.lightpanda_wrapper import LightpandaWrapper

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
        self, task: CrawlTask, strategy: CrawlStrategy
    ) -> tuple[str, int | None, any]:
        from ai_crawler.browser.seleniumbase_wrapper import SeleniumBaseWrapper

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
        self, task: CrawlTask, strategy: CrawlStrategy
    ) -> tuple[str, int | None, any]:
        from ai_crawler.browser.kameleo_wrapper import KameleoWrapper
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
        self, task: CrawlTask, strategy: CrawlStrategy
    ) -> tuple[str, int | None, any]:
        delay_min, delay_max = strategy.delay_before
        if delay_min > 0:
            time.sleep(random.uniform(delay_min, delay_max))
        proxy = self.proxy_provider.proxy_url(strategy) if self.proxy_provider else None
        try:
            from ai_crawler.browser.cloakbrowser_wrapper import _sync_fetch as cloak_sync_fetch

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
            proxy_settings = self._structured_proxy_settings(proxy)
            if proxy_settings:
                launch_kwargs["proxy"] = proxy_settings
            viewport_dict = self.dynamic_profile.get("viewport")
            browser_key = self._stable_key({"proxy": proxy_settings, "launch": launch_kwargs})
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
            resp = page.goto(
                task.url,
                wait_until="domcontentloaded",
                timeout=self._navigation_timeout_ms(task, strategy),
            )
            self._wait_for_page_ready(page, strategy)
            if strategy.use_human_scroll:
                self._human_scroll(page)
            content = page.content()
            status = resp.status if resp else 200
            return content, status, page
        except ModuleNotFoundError:
            return (
                self._browser_error_html(
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
            from ai_crawler.browser.human_mouse import HumanMouseController
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
