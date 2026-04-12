import traceback
from ai_crawler.browser.playwright_wrapper import PlaywrightWrapper

try:
    wrapper = PlaywrightWrapper(headless=True, wait_time=2.0, human_scroll=True)
    html, status = wrapper.fetch("https://www.ebay.com/sch/i.html?_nkw=test")
    print(f"Success: {status}")
except Exception:
    traceback.print_exc()
