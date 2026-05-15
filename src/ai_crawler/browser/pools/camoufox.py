import asyncio
import json
import time
import random
from concurrent.futures import ThreadPoolExecutor
import structlog
from ai_crawler.spider.runtime.crawl import CrawlPolicy, CrawlTask
from ai_crawler.browser import utils
from ai_crawler.browser.pools.state import PoolState


log = structlog.get_logger()


class CamoufoxPool:
    def __init__(
        self,
        state: PoolState,
        proxy_provider=None,
        dynamic_profile: dict | None = None,
        page_load_timeout: float = 30.0,
    ):
        self._state = state
        self.proxy_provider = proxy_provider
        self.dynamic_profile = dynamic_profile or {}
        self.page_load_timeout = page_load_timeout

    def fetch(self, task: CrawlTask, strategy: CrawlPolicy) -> tuple[str, int | None, any]:
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
            self._state.increment_stat("pages_opened")
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

            if strategy.use_interactive_search and getattr(task, "query", None):
                from ai_crawler.browser.interaction import InteractiveSearcher
                from ai_crawler.spider.extraction.templates.template_store import template_store

                site_config = template_store.load(task.site, "search")
                interactor = InteractiveSearcher(page, site_config)
                success = interactor.perform_search(task.query)
                if not success:
                    resp = page.goto(
                        task.url,
                        wait_until="domcontentloaded",
                        timeout=self._navigation_timeout_ms(task, strategy),
                    )
                else:
                    resp = None
            else:
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

    def _is_running_inside_event_loop(self) -> bool:
        try:
            asyncio.get_running_loop()
            return True
        except RuntimeError:
            return False

    def _get_camoufox_browser(self, browser_key: str, launch_kwargs: dict):
        with self._state._pool_lock:
            browser = self._state._camoufox_browsers.get(browser_key)
            if browser is not None:
                meta = self._state._camoufox_browser_meta.get(browser_key, {})
                idle = time.time() - float(meta.get("last_used", time.time()))
                leases = int(meta.get("leases", 0))
                if idle > self._state._camoufox_idle_ttl_seconds or leases >= self._state._camoufox_max_leases:
                    self._evict_camoufox_browser(browser_key)
                    browser = None
                elif self._is_camoufox_browser_healthy(browser):
                    self._state.increment_stat("camoufox_browser_reused")
                    log.info("camoufox_browser_reused", browser_key=browser_key)
                    return browser
                else:
                    self._evict_camoufox_browser(browser_key)
                    browser = None

            self._trim_camoufox_pool()

            if browser is not None:
                self._state.increment_stat("camoufox_browser_reused")
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

            self._state._camoufox_launchers[browser_key] = launcher
            self._state._camoufox_browsers[browser_key] = browser
            self._state._camoufox_browser_meta[browser_key] = {"leases": 0, "last_used": time.time()}
            self._state.increment_stat("camoufox_browser_created")
            log.info("camoufox_browser_created", browser_key=browser_key)
            return browser

    def _is_camoufox_browser_healthy(self, browser) -> bool:
        try:
            if hasattr(browser, "is_connected") and not browser.is_connected():
                self._state.increment_stat("camoufox_healthcheck_failed")
                return False
            _ = getattr(browser, "contexts", None)
            return True
        except Exception:
            self._state.increment_stat("camoufox_healthcheck_failed")
            return False

    def _evict_camoufox_browser(self, browser_key: str) -> None:
        browser = self._state._camoufox_browsers.pop(browser_key, None)
        launcher = self._state._camoufox_launchers.pop(browser_key, None)
        self._state._camoufox_browser_meta.pop(browser_key, None)
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
        self._state.increment_stat("camoufox_browser_evicted")
        log.info("camoufox_browser_evicted", browser_key=browser_key)

    def _trim_camoufox_pool(self) -> None:
        while len(self._state._camoufox_browsers) >= self._state._camoufox_pool_cap:
            oldest_key = min(
                self._state._camoufox_browser_meta,
                key=lambda key: float(self._state._camoufox_browser_meta[key].get("last_used", 0.0)),
            )
            self._evict_camoufox_browser(oldest_key)

    def _release_camoufox_browser(self, browser_key: str, browser, healthy: bool) -> None:
        with self._state._pool_lock:
            if not healthy:
                self._evict_camoufox_browser(browser_key)
                return
            meta = self._state._camoufox_browser_meta.setdefault(
                browser_key, {"leases": 0, "last_used": time.time()}
            )
            meta["leases"] = int(meta.get("leases", 0)) + 1
            meta["last_used"] = time.time()
            self._state._camoufox_browsers[browser_key] = browser

    def _install_ad_script_blocking(self, page) -> None:
        if not hasattr(page, "route"):
            return

        def handler(route):
            try:
                request = route.request
                if request.resource_type == "script" and utils.should_block_script(request.url):
                    self._state.increment_stat("ad_scripts_blocked")
                    route.abort()
                    return
            except Exception:
                pass
            route.continue_()

        try:
            page.route("**/*", handler)
            self._state.increment_stat("ad_block_handlers_installed")
        except Exception as exc:
            log.warning("ad_block_install_error", error=str(exc))

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

    def _human_scroll(self, page):
        try:
            if not hasattr(page, "viewport"):
                return
            viewport = page.viewport_size or {"width": 1920, "height": 1080}
            from ai_crawler.browser.human.mouse import HumanMouseController

            controller = HumanMouseController(page)
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
