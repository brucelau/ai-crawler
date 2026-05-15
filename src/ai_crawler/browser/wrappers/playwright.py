"""PlaywrightWrapper - Tier 3: full JavaScript rendering with Playwright."""

import random
import time
from typing import Optional

from playwright.sync_api import sync_playwright

from ai_crawler.browser.base import BaseWrapper
from ai_crawler.browser.human.fingerprint import get_fingerprint_script


class PlaywrightWrapper(BaseWrapper):
    def __init__(
        self,
        proxy: Optional[str] = None,
        headless: bool = True,
        wait_time: float = 2.0,
        human_scroll: bool = False,
        dynamic_profile: Optional[dict] = None,
    ):
        self.proxy = proxy
        self.headless = headless
        self.wait_time = wait_time
        self.human_scroll = human_scroll
        self.dynamic_profile = dynamic_profile or {}

    def fetch(self, url: str) -> tuple[str, int]:
        try:
            with sync_playwright() as p:
                args = [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--window-size=1920,1080",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                ]

                profile = self.dynamic_profile or {}

                if profile.get("stealth_args"):
                    s_args = profile["stealth_args"]
                    if isinstance(s_args, str):
                        try:
                            import json

                            s_args = json.loads(s_args)
                        except Exception:
                            s_args = []
                    if isinstance(s_args, list):
                        args.extend(s_args)

                browser = p.chromium.launch(headless=self.headless, args=args)

                context_args = {
                    "ignore_https_errors": True,
                    "viewport": {"width": 1920, "height": 1080},
                    "has_touch": False,
                }

                if self.proxy:
                    context_args["proxy"] = {"server": self.proxy}

                if profile.get("user_agent"):
                    context_args["user_agent"] = profile["user_agent"]

                if profile.get("locale"):
                    context_args["locale"] = profile["locale"]

                if profile.get("timezone_id"):
                    context_args["timezone_id"] = profile["timezone_id"]

                context = browser.new_context(**context_args)

                script = get_fingerprint_script(
                    **{
                        k: v
                        for k, v in profile.items()
                        if k
                        in ["gpu_vendor", "gpu_renderer", "platform_string", "device_pixel_ratio"]
                    }
                )
                context.add_init_script(script)

                page = context.new_page()
                page.goto(url, timeout=45000)

                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass

                if self.wait_time > 0:
                    time.sleep(self.wait_time)

                if self.human_scroll:
                    self._human_scroll(page)

                html = page.content()
                status = 200

                browser.close()
                return html, status
        except Exception as e:
            raise e

    def _human_scroll(self, page):
        for _ in range(random.randint(2, 5)):
            page.evaluate(f"window.scrollBy(0, {random.randint(200, 500)})")
            time.sleep(random.uniform(0.5, 1.5))

    def __repr__(self) -> str:
        return f"PlaywrightWrapper(proxy={self.proxy}, headless={self.headless})"
