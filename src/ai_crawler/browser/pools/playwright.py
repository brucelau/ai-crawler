import json
import random
import time
import structlog
from ai_crawler.core.types import CrawlPolicy, CrawlTask
from ai_crawler.browser import utils
from ai_crawler.browser.pools.state import PoolState


log = structlog.get_logger()


class PlaywrightPool:
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
            self._state.increment_stat("pages_opened")
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

            if strategy.use_interactive_search and getattr(task, "query", None):
                from ai_crawler.browser.interaction import InteractiveSearcher
                from ai_crawler.extraction.templates.template_store import template_store

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
            status = resp.status if resp else 200
            return content, status, page
        except Exception as exc:
            log.warning("playwright_error", url=task.url, error=str(exc))
            return "", None, None

    def _get_playwright_runtime(self):
        with self._state._pool_lock:
            if self._state._playwright_runtime is None:
                from playwright.sync_api import sync_playwright

                self._state._playwright_runtime = sync_playwright().start()
                self._state.increment_stat("playwright_runtime_created")
                log.info("playwright_runtime_created")
            return self._state._playwright_runtime

    def _get_playwright_browser(
        self, browser_key: str, proxy_server: str | None, stealth_args: list[str]
    ):
        with self._state._pool_lock:
            browser = self._state._playwright_browsers.get(browser_key)
            if browser is not None:
                self._state.increment_stat("playwright_browser_reused")
                log.info("playwright_browser_reused", browser_key=browser_key)
                return browser

            runtime = self._get_playwright_runtime()
            launch_kwargs = {"headless": True, "args": stealth_args}
            if proxy_server:
                launch_kwargs["proxy"] = {"server": proxy_server}
            browser = runtime.chromium.launch(**launch_kwargs)
            self._state._playwright_browsers[browser_key] = browser
            self._state.increment_stat("playwright_browser_created")
            log.info("playwright_browser_created", browser_key=browser_key)
            return browser

    def _get_playwright_context(self, browser_key: str, browser, ctx_args: dict):
        context_key = utils.stable_key({"browser": browser_key, "context": ctx_args})
        with self._state._pool_lock:
            context = self._state._playwright_contexts.get(context_key)
            if context is not None:
                self._state.increment_stat("playwright_context_reused")
                log.info("playwright_context_reused", context_key=context_key)
                return context
            context = browser.new_context(**ctx_args)
            self._state._playwright_contexts[context_key] = context
            self._state.increment_stat("playwright_context_created")
            log.info("playwright_context_created", context_key=context_key)
            return context

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
