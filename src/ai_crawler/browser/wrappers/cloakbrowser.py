"""CloakBrowser wrapper with anti-detection and human-like behavior."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from typing import Any, Generator
from urllib.parse import urlparse

from ai_crawler.browser.base import BaseWrapper
from ai_crawler.browser.human.fingerprint import get_fingerprint_script


class CloakBrowserWrapper(BaseWrapper):
    """Wrapper for CloakBrowser with anti-detection features."""

    def __init__(
        self,
        proxy: str | None = None,
        headless: bool = True,
        wait_time: float = 2.0,
        human_scroll: bool = True,
        dynamic_profile: dict | None = None,
        wait_selector: str | None = None,
    ):
        super().__init__(proxy, headless, wait_time, human_scroll, dynamic_profile)
        self.wait_selector = wait_selector
        self._browser = None
        self._page = None

    @contextmanager
    def launch(self) -> Generator[Any, None, None]:
        """Launch CloakBrowser and yield the page."""
        from cloakbrowser import launch

        import os
        launch_kwargs = {
            "headless": os.environ.get("CRAWL_HEADLESS", "true").lower() != "false",
            "timezone": self.dynamic_profile.get("timezone_id", "America/New_York"),
            "locale": self.dynamic_profile.get("locale", "en-US"),
            "geoip": True,
            "humanize": True,
        }
        viewport = None

        if self.proxy:
            parsed = urlparse(self.proxy)
            if parsed.scheme and parsed.hostname and parsed.port:
                launch_kwargs["proxy"] = {
                    "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
                    **({"username": parsed.username} if parsed.username else {}),
                    **({"password": parsed.password} if parsed.password else {}),
                }
            else:
                launch_kwargs["proxy"] = self.proxy

        viewport_raw = self.dynamic_profile.get("viewport")
        if viewport_raw:
            if isinstance(viewport_raw, str):
                try:
                    viewport = json.loads(viewport_raw)
                except Exception:
                    viewport = {"width": 1920, "height": 1080}
            else:
                viewport = viewport_raw

        browser = launch(**launch_kwargs)
        self._browser = browser

        try:
            page = browser.new_page()
            if viewport and hasattr(page, "set_viewport_size"):
                try:
                    page.set_viewport_size(viewport)
                except Exception:
                    pass

            # Set languages header
            languages = self.dynamic_profile.get("languages")
            if languages:
                if isinstance(languages, str):
                    try:
                        languages = json.loads(languages)
                    except Exception:
                        languages = [languages]
                if isinstance(languages, list):
                    page.set_extra_http_headers({"Accept-Language": ",".join(languages)})

            fp_params = {
                "session_id": None,
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

            self._page = page
            yield page
        finally:
            try:
                if self._page is not None:
                    self._page.close()
            except Exception:
                pass
            try:
                if self._browser is not None:
                    self._browser.close()
            except Exception:
                pass

    def fetch(
        self,
        url: str,
        wait_selector: str | None = None,
        wait_time: float | None = None,
        human_scroll: bool | None = None,
    ) -> tuple[str, int]:
        """Fetch a URL and return (page_source, status_code)."""
        wait_time = wait_time if wait_time is not None else self.wait_time
        human_scroll = human_scroll if human_scroll is not None else self.human_scroll
        wait_selector = wait_selector or self.wait_selector

        try:
            with self.launch() as page:
                resp = page.goto(url, wait_until="commit", timeout=30000)
                status = resp.status if resp else 200
                page.wait_for_selector("body", timeout=15000)

                if wait_time > 0:
                    time.sleep(wait_time)

                if wait_selector:
                    try:
                        page.wait_for_selector(wait_selector, timeout=10000)
                    except Exception:
                        pass

                if human_scroll:
                    self._human_scroll(page, url)

                return page.content(), status
        except Exception as e:
            raise e

    def _human_scroll(self, page, url: str) -> None:
        try:
            from ai_crawler.browser.human.mouse import (
                CloakBrowserMouseAdapter,
                UnifiedHumanBehavior,
                CachedLLMHumanBehavior,
            )
            from ai_crawler.core.config import config

            adapter = CloakBrowserMouseAdapter(page)
            site = self._extract_site(url)

            if config.has_llm():
                try:
                    llm_behavior = CachedLLMHumanBehavior()
                    llm_behavior.human_scroll(adapter, site, "search")
                    return
                except Exception:
                    pass

            behavior = UnifiedHumanBehavior(adapter)
            behavior.human_scroll(0, 1500)
        except Exception:
            pass

    def _extract_site(self, url: str) -> str:
        try:
            from urllib.parse import urlparse

            netloc = urlparse(url).netloc
            parts = netloc.replace(".com", "").replace(".co", "").replace(".org", "").split(".")
            return parts[-1] if parts else "unknown"
        except Exception:
            return "unknown"


def _sync_fetch(
    url: str,
    proxy: str | None = None,
    wait_selector: str | None = None,
    wait_time: float = 2.0,
    human_scroll: bool = True,
    dynamic_profile: dict | None = None,
) -> tuple[str, int]:
    wrapper = CloakBrowserWrapper(
        headless=True,
        proxy=proxy,
        wait_selector=wait_selector,
        wait_time=wait_time,
        human_scroll=human_scroll,
        dynamic_profile=dynamic_profile or {},
    )
    return wrapper.fetch(url)


async def async_fetch(
    url: str,
    proxy: str | None = None,
    wait_selector: str | None = None,
    wait_time: float = 2.0,
    human_scroll: bool = True,
    dynamic_profile: dict | None = None,
) -> tuple[str, int]:
    import asyncio

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        _sync_fetch,
        url,
        proxy,
        wait_selector,
        wait_time,
        human_scroll,
        dynamic_profile,
    )
