"""SeleniumPageAdapter — wraps a Selenium WebDriver to expose a Playwright-like page API.

Used by BrowserOperator so it can drive Selenium-based backends (seleniumbase,
undetected_chromedriver) with the same command interface as Playwright backends.
"""

from __future__ import annotations


class SeleniumPageAdapter:
    """Wraps a SeleniumBase/undetected-chromedriver driver to expose Playwright-like page API.

    Only implements the subset of methods that BrowserOperator actually uses.
    """

    def __init__(self, driver):
        self._driver = driver

    @property
    def url(self):
        return self._driver.current_url

    def content(self) -> str:
        return self._driver.page_source

    def goto(self, url: str, wait_until: str = "domcontentloaded", timeout: int = 30000):
        self._driver.get(url)
        from selenium.webdriver.support.ui import WebDriverWait
        try:
            if wait_until == "domcontentloaded":
                WebDriverWait(self._driver, timeout / 1000).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
        except Exception:
            pass
        return _SeleniumResponse(self._driver.current_url, 200)

    def click(self, selector: str, timeout: int = 10000):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        el = WebDriverWait(self._driver, timeout / 1000).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
        )
        el.click()

    def evaluate(self, js: str):
        return self._driver.execute_script(f"return {js}")

    def wait_for_selector(self, selector: str, timeout: int = 15000):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        WebDriverWait(self._driver, timeout / 1000).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )

    def wait_for_function(self, js: str, timeout: int = 15000):
        from selenium.webdriver.support.ui import WebDriverWait
        WebDriverWait(self._driver, timeout / 1000).until(
            lambda d: d.execute_script(f"return {js}")
        )

    def screenshot(self, path: str | None = None):
        return self._driver.save_screenshot(path)

    def route(self, _pattern: str, _handler):
        pass

    def unroute(self, _pattern: str):
        pass

    @property
    def keyboard(self):
        return self

    def type(self, char: str):
        from selenium.webdriver.common.action_chains import ActionChains
        ActionChains(self._driver).send_keys(char).perform()

    def press(self, key: str):
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.action_chains import ActionChains
        key_map = {
            "Enter": Keys.ENTER, "Escape": Keys.ESCAPE, "Tab": Keys.TAB,
            "ArrowDown": Keys.ARROW_DOWN, "ArrowUp": Keys.ARROW_UP,
            "ArrowLeft": Keys.ARROW_LEFT, "ArrowRight": Keys.ARROW_RIGHT,
            "PageDown": Keys.PAGE_DOWN, "PageUp": Keys.PAGE_UP,
            "Backspace": Keys.BACKSPACE, "Delete": Keys.DELETE,
            "Home": Keys.HOME, "End": Keys.END,
        }
        k = key_map.get(key, key)
        ActionChains(self._driver).send_keys(k).perform()

    def close(self):
        try:
            self._driver.quit()
        except Exception:
            pass


class _SeleniumResponse:
    """Minimal response-like object returned by goto()."""
    def __init__(self, url: str, status: int):
        self.url = url
        self.status = status
