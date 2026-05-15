"""UndetectedChromedriverWrapper - Tier 5: undetected-chromedriver for anti-detection."""

import random
import time

import undetected_chromedriver as uc

from ai_crawler.browser.base import BaseWrapper


class UndetectedChromedriverWrapper(BaseWrapper):
    def __init__(
        self,
        proxy: str | None = None,
        headless: bool = True,
        wait_time: float = 2.0,
        human_scroll: bool = False,
        dynamic_profile: dict | None = None,
    ):
        super().__init__(proxy, headless, wait_time, human_scroll, dynamic_profile)

    def fetch(self, url: str) -> tuple[str, int]:
        try:
            options = uc.ChromeOptions()
            options.headless = self.headless
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.page_load_strategy = "normal"

            if self.proxy:
                options.add_argument(f"--proxy-server={self.proxy}")

            if self.dynamic_profile.get("user_agent"):
                options.add_argument(f"--user-agent={self.dynamic_profile['user_agent']}")

            driver = uc.Chrome(options=options)
            driver.get(url)

            if self.wait_time > 0:
                time.sleep(self.wait_time)

            if self.human_scroll:
                self._human_scroll(driver)

            html = driver.page_source
            driver.quit()
            return html, 200
        except Exception as e:
            if "driver" in locals() and driver:
                try:
                    driver.quit()
                except Exception:
                    pass
            raise e

    def _human_scroll(self, driver):
        for _ in range(random.randint(2, 5)):
            driver.execute_script(f"window.scrollBy(0, {random.randint(200, 500)})")
            time.sleep(random.uniform(0.5, 1.5))

    def __repr__(self) -> str:
        return f"UndetectedChromedriverWrapper(proxy={self.proxy}, headless={self.headless})"
