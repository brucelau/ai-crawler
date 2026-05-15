"""SeleniumBase browser wrapper with anti-detection capabilities."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Generator, Any

from ai_crawler.browser.base import BaseWrapper


class SeleniumBaseWrapper(BaseWrapper):
    """Wrapper for SeleniumBase with anti-detection features."""

    def __init__(
        self,
        proxy: str | None = None,
        headless: bool = True,
        wait_time: float = 2.0,
        human_scroll: bool = True,
        dynamic_profile: dict | None = None,
        browser: str = "chrome",
        undetected: bool = False,
        wait_selector: str | None = None,
    ):
        super().__init__(proxy, headless, wait_time, human_scroll, dynamic_profile)
        self.browser = browser
        self.undetected = undetected
        self.wait_selector = wait_selector
        self._driver = None

    def create_driver(self):
        """Create and return a SeleniumBase driver without owning its full fetch lifecycle."""
        from seleniumbase import Driver

        driver = Driver(
            browser=self.browser,
            headless=self.headless,
            uc=self.undetected,
        )
        self._driver = driver
        return driver

    def close_driver(self, driver) -> None:
        """Close a managed driver safely."""
        try:
            driver.quit()
        except Exception:
            pass
        if self._driver is driver:
            self._driver = None

    @contextmanager
    def launch(self) -> Generator[Any, None, None]:
        """Launch SeleniumBase browser and yield the driver."""
        driver = self.create_driver()

        try:
            yield driver
        finally:
            self.close_driver(driver)

    @contextmanager
    def stealth_page(self) -> Generator[Any, None, None]:
        """Launch browser with stealth settings and yield the driver."""
        with self.launch() as driver:
            self._add_stealth_js(driver)
            yield driver

    def _add_stealth_js(self, driver) -> None:
        """Add stealth JavaScript to mask automation fingerprints."""
        try:
            from ai_crawler.browser.human.fingerprint import get_fingerprint_script
            import json

            languages = self.dynamic_profile.get("languages")
            if languages:
                try:
                    languages = json.loads(languages)
                except Exception:
                    pass

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
            driver.execute_script(get_fingerprint_script(**fp_params))
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
        with self.stealth_page() as driver:
            return self.fetch_with_driver(
                driver,
                url,
                wait_selector=wait_selector,
                wait_time=wait_time,
                human_scroll=human_scroll,
            )

    def fetch_with_driver(
        self,
        driver,
        url: str,
        wait_selector: str | None = None,
        wait_time: float | None = None,
        human_scroll: bool | None = None,
    ) -> tuple[str, int]:
        """Fetch a URL using an externally managed SeleniumBase driver."""
        wait_time = wait_time if wait_time is not None else self.wait_time
        human_scroll = human_scroll if human_scroll is not None else self.human_scroll
        wait_selector = wait_selector or self.wait_selector

        try:
            driver.get(url)

            if wait_time > 0:
                time.sleep(wait_time)

            if wait_selector:
                try:
                    from selenium.webdriver.support.ui import WebDriverWait
                    from selenium.webdriver.support import expected_conditions as EC
                    from selenium.webdriver.common.by import By

                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
                    )
                except Exception:
                    pass

            if human_scroll:
                self._human_scroll(driver, url)

            return driver.page_source, 200
        except Exception as e:
            raise e

    def _human_scroll(self, driver, url: str) -> None:
        try:
            from ai_crawler.browser.human.mouse import (
                SeleniumMouseAdapter,
                UnifiedHumanBehavior,
                CachedLLMHumanBehavior,
            )
            from ai_crawler.config import config

            adapter = SeleniumMouseAdapter(driver)
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
    undetected: bool = True,
    dynamic_profile: dict | None = None,
) -> tuple[str, int]:
    wrapper = SeleniumBaseWrapper(
        headless=True,
        proxy=proxy,
        undetected=undetected,
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
    undetected: bool = True,
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
        undetected,
        dynamic_profile,
    )
