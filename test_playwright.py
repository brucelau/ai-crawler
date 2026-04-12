from ai_crawler.browser.playwright_wrapper import PlaywrightWrapper
import json

wrapper = PlaywrightWrapper(headless=True, wait_time=2.0, human_scroll=True)
html, status = wrapper.fetch("https://www.ebay.com/sch/i.html?_nkw=inflatable")
with open("/tmp/ebay_result.html", "w") as f:
    f.write(html)
print(f"Status: {status}, HTML Length: {len(html)}")
