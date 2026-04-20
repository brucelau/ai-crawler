import time
import random
import structlog
from typing import Optional

log = structlog.get_logger()


class InteractiveSearcher:
    def __init__(self, page, site_config: dict):
        self.page = page
        self.site_config = site_config

    def perform_search(self, query: str) -> bool:
        homepage_url = self.site_config.get("homepage_url")
        input_selector = self.site_config.get("search_input_selector")
        button_selector = self.site_config.get("search_button_selector")

        if not homepage_url or not input_selector:
            log.warning("interactive_search_missing_config", site=self.site_config.get("site"))
            return False

        try:
            log.info(
                "interactive_search_start", site=self.site_config.get("site"), url=homepage_url
            )

            self.page.goto(homepage_url, wait_until="domcontentloaded", timeout=45000)
            self.page.wait_for_selector(input_selector, timeout=10000)
            self.page.click(input_selector)
            time.sleep(random.uniform(0.5, 1.2))

            log.info("interactive_search_typing", query=query)
            for char in query:
                self.page.keyboard.type(char)
                time.sleep(random.uniform(0.05, 0.25))

            time.sleep(random.uniform(0.8, 1.5))

            if button_selector and random.random() > 0.3:
                log.info("interactive_search_click_button")
                self.page.click(button_selector)
            else:
                log.info("interactive_search_press_enter")
                self.page.keyboard.press("Enter")

            time.sleep(2)
            return True
        except Exception as e:
            log.error("interactive_search_failed", site=self.site_config.get("site"), error=str(e))
            return False
