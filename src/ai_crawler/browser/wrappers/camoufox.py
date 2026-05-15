"""Camoufox browser wrapper with human-like mouse and fingerprint spoofing."""

from __future__ import annotations

import asyncio
import random
import time
from contextlib import contextmanager
from typing import Any, Generator
from urllib.parse import urlparse

try:
    import camoufox
except ImportError:
    camoufox = None

CookieJar = Any

from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext

from ai_crawler.browser.human.mouse import HumanMouseController


class FingerprintConfig:
    def __init__(
        self,
        locale: str = "en-US",
        timezone: str = "America/New_York",
        viewport: tuple[int, int] = (1920, 1080),
        user_agent: str | None = None,
        do_not_track: bool = True,
        platform: str = "Win32",
        vendor: str = "Google Inc.",
        webgl_vendor: str = "Intel Inc.",
        webgl_renderer: str = "Intel Iris OpenGL Engine",
    ):
        self.locale = locale
        self.timezone = timezone
        self.viewport = viewport
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.do_not_track = do_not_track
        self.platform = platform
        self.vendor = vendor
        self.webgl_vendor = webgl_vendor
        self.webgl_renderer = webgl_renderer


from ai_crawler.browser.base import BaseWrapper


class CamoufoxWrapper(BaseWrapper):
    def __init__(
        self,
        proxy: str | None = None,
        headless: bool = True,
        wait_time: float = 2.0,
        human_scroll: bool = False,
        dynamic_profile: dict | None = None,
        fp: FingerprintConfig | None = None,
        cookie_jar: CookieJar | None = None,
    ):
        super().__init__(proxy, headless, wait_time, human_scroll, dynamic_profile)

        if fp is None:
            profile = dynamic_profile or {}
            v_raw = profile.get("viewport", (1920, 1080))
            if isinstance(v_raw, tuple):
                v_final = v_raw
            elif isinstance(v_raw, dict):
                v_final = (v_raw.get("width", 1920), v_raw.get("height", 1080))
            else:
                v_final = (1920, 1080)

            self.fp = FingerprintConfig(
                locale=profile.get("locale", "en-US"),
                timezone=profile.get("timezone_id", "America/New_York"),
                viewport=v_final,
                user_agent=profile.get("user_agent"),
                platform=profile.get("platform_string", "Win32"),
                webgl_vendor=profile.get("gpu_vendor", "Intel Inc."),
                webgl_renderer=profile.get("gpu_renderer", "Intel Iris OpenGL Engine"),
            )
        else:
            self.fp = fp

        self.cookie_jar = cookie_jar
        self._mouse = None
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._mouse_controller: HumanMouseController | None = None

    def _setup_context(self, context: BrowserContext) -> None:
        context.set_extra_http_headers(
            {
                "Accept-Language": f"{self.fp.locale},en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "document",
                "sec-fetch-mode": "navigate",
                "sec-fetch-site": "none",
                "sec-fetch-user": "?1",
                "upgrade-insecure-requests": "1",
            }
        )

    def _playwright_proxy_settings(self) -> dict | None:
        if not self.proxy:
            return None
        parsed = urlparse(self.proxy)
        if not parsed.scheme or not parsed.hostname or not parsed.port:
            return {"server": self.proxy}

        settings = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
        if parsed.username:
            settings["username"] = parsed.username
        if parsed.password:
            settings["password"] = parsed.password
        return settings

    @contextmanager
    def launch(self) -> Generator[Page, None, None]:
        with sync_playwright() as p:
            args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-gpu",
                "--window-size=1920,1080",
            ]
            launch_kwargs = {
                "headless": self.headless,
                "args": args,
            }
            proxy_settings = self._playwright_proxy_settings()
            if proxy_settings:
                launch_kwargs["proxy"] = proxy_settings

            browser = p.chromium.launch(**launch_kwargs)
            context = browser.new_context(
                viewport={"width": self.fp.viewport[0], "height": self.fp.viewport[1]},
                user_agent=self.fp.user_agent,
                locale=self.fp.locale,
                timezone_id=self.fp.timezone,
                permissions=["geolocation"],
                ignore_https_errors=True,
            )
            self._setup_context(context)

            if self.cookie_jar:
                for cookie in self.cookie_jar:
                    context.add_cookies([cookie])

            page = context.new_page()
            self._mouse = HumanMouseController(page)

            yield page

            page.close()
            context.close()
            browser.close()

    @contextmanager
    def stealth_page(self) -> Generator[Page, None, None]:
        with self.launch() as page:
            self._add_stealth_js(page)
            yield page

    def _add_stealth_js(self, page: Page) -> None:
        page.evaluate(
            """() => {
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                window.chrome = { runtime: {} };
                const getParameter = Object.getOwnPropertyDescriptor(HTMLCanvasElement.prototype, 'getContext')?.get;
                if (getParameter) {
                    HTMLCanvasElement.prototype.getContext = function(type, attributes) {
                        const context = getParameter.call(this, type, attributes);
                        if (type === '2d') {
                            const originalGetImageData = context.getImageData;
                            context.getImageData = function(sx, sy, sw, sh) {
                                if (Math.random() > 0.5) {
                                    return originalGetImageData.call(this, sx, sy, sw, sh);
                                }
                                const imageData = originalGetImageData.call(this, sx, sy, sw, sh);
                                for (let i = 0; i < imageData.data.length; i += 4) {
                                    imageData.data[i] ^= Math.random() > 0.5 ? 1 : 0;
                                    imageData.data[i+1] ^= Math.random() > 0.5 ? 1 : 0;
                                    imageData.data[i+2] ^= Math.random() > 0.5 ? 1 : 0;
                                }
                                return imageData;
                            };
                        }
                        return context;
                    };
                }
            }"""
        )

    def mouse(self) -> HumanMouseController:
        if self._mouse is None:
            raise RuntimeError("Browser not launched. Use 'with wrapper.stealth_page() as page:'")
        return self._mouse

    def fetch(self, url: str) -> tuple[str, int]:
        try:
            with self.stealth_page() as page:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                if self.wait_time > 0:
                    time.sleep(self.wait_time)
                if self.human_scroll:
                    mouse = HumanMouseController(page)
                    for _ in range(random.randint(2, 5)):
                        mouse.move_to(random.randint(100, 500), random.randint(200, 500))
                        time.sleep(random.uniform(0.5, 1.5))
                return page.content(), 200
        except Exception as e:
            raise e


async def async_launch(
    url: str,
    proxy: str | None = None,
    wait_selector: str | None = None,
    wait_time: float = 2.0,
    human_scroll: bool = True,
) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _sync_launch, url, proxy, wait_selector, wait_time, human_scroll
    )


def _sync_launch(
    url: str,
    proxy: str | None,
    wait_selector: str | None,
    wait_time: float,
    human_scroll: bool,
) -> str:
    wrapper = CamoufoxWrapper(headless=True, proxy=proxy)
    with wrapper.stealth_page() as page:
        page.goto(url, wait_until="domcontentloaded")
        time.sleep(wait_time)
        if wait_selector:
            try:
                page.wait_for_selector(wait_selector, timeout=10000)
            except Exception:
                pass
        if human_scroll:
            mouse = HumanMouseController(page)
            for y in range(0, 2000, 150):
                mouse.move_to(random.randint(100, 500), y)
        return page.content()
