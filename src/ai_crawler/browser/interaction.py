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

            self.page.goto(homepage_url, wait_until="commit", timeout=45000)
            self.page.wait_for_selector("body", timeout=15000)
            time.sleep(random.uniform(1.0, 2.0))

            # Find and focus the search input
            self.page.wait_for_selector(input_selector, timeout=15000)
            self.page.click(input_selector)
            time.sleep(random.uniform(0.5, 1.2))

            # Clear any existing text and type query
            self.page.keyboard.press("Control+a")
            time.sleep(0.1)
            log.info("interactive_search_typing", query=query)
            for char in query:
                self.page.keyboard.type(char)
                time.sleep(random.uniform(0.05, 0.25))
            time.sleep(random.uniform(0.8, 1.5))

            # Submit: try button click first, fall back to Enter
            submitted = False
            if button_selector:
                try:
                    self.page.click(button_selector, timeout=5000)
                    log.info("interactive_search_click_button")
                    submitted = True
                except Exception:
                    pass
            if not submitted:
                log.info("interactive_search_press_enter")
                self.page.keyboard.press("Enter")

            # Wait for results page to load
            time.sleep(random.uniform(3.0, 5.0))
            try:
                self.page.wait_for_selector("body", timeout=15000)
            except Exception:
                pass
            return True
        except Exception as e:
            log.error("interactive_search_failed", site=self.site_config.get("site"), error=str(e))
            return False
