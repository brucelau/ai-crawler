from __future__ import annotations

import asyncio
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Lock
from typing import Callable

import structlog

from ai_crawler.core.runtime.handler import AntiBotHandler, BlockDetector, BlockType
from ai_crawler.core.runtime.queue import CrawlQueue, SiteMemory
from ai_crawler.core.strategy import CrawlStrategy, CrawlTask, ProxyType, RenderType
from ai_crawler.core.runtime.trace_store import TraceStore, AntiBotTrace
from ai_crawler.core.extraction import ExtractionResult
from ai_crawler.spiders import Product


log = structlog.get_logger()


@dataclass
class CrawlResult:
    task: CrawlTask
    strategy: CrawlStrategy
    success: bool
    html: str = ""
    products: list[Product] = None
    block_type: str = BlockType.NONE
    error: str = ""


class ProxyProvider:
    PLACEHOLDER_VALUES = (
        "",
        "your_thordata_username",
        "your_thordata_password",
        "none",
        "null",
    )
    _verified_proxies: dict[str, tuple[bool, float]] = {}
    _verify_lock = Lock()
    _verify_timeout = 5

    def __init__(
        self,
        username: str,
        password: str,
        default_country: str = "us",
        verify_proxy: bool = True,
        disabled: bool = False,
    ):
        self.username = username
        self.password = password
        self.default_country = default_country
        self.verify_proxy = verify_proxy
        self.disabled = disabled
        self._enabled = bool(
            not disabled
            and username
            and password
            and username not in self.PLACEHOLDER_VALUES
            and password not in self.PLACEHOLDER_VALUES
        )

    def _verify_proxy_connection(self, proxy_url: str) -> bool:
        try:
            import requests

            resp = requests.get(
                "https://httpbin.org/ip",
                proxies={"http": proxy_url, "https": proxy_url},
                timeout=self._verify_timeout,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def _is_proxy_verified(self, proxy_url: str) -> bool:
        with self._verify_lock:
            if proxy_url not in self._verified_proxies:
                return False
            is_valid, timestamp = self._verified_proxies[proxy_url]
            if not is_valid:
                return False
            if time.time() - timestamp > 60:
                del self._verified_proxies[proxy_url]
                return False
            return True

    def _mark_proxy_verified(self, proxy_url: str, success: bool) -> None:
        with self._verify_lock:
            self._verified_proxies[proxy_url] = (success, time.time())

    def _get_thordata_manager(self, pt: ProxyType) -> ThorDataManager:
        import os
        from ai_crawler.proxy.thordata import ThorDataManager

        country = "us"
        city = None
        proxy_host = "pr.thordata.net"

        if pt == ProxyType.THORDATA_US_CITY:
            city = "new_york"
        elif pt == ProxyType.THORDATA_DEDICATED:
            from ai_crawler.config import config

            proxy_host = config.THORDATA_PROXY_HOST

        return ThorDataManager(
            username=self.username,
            password=self.password,
            country=country,
            city=city,
            proxy_host=proxy_host,
            pool_size=3,
            sticky=True,
            session_duration=180,
        )

    def proxy_url(self, strategy: CrawlStrategy) -> str | None:
        if not self._enabled:
            return None
        pt = strategy.proxy

        manager = self._get_thordata_manager(pt)
        proxy = manager.get_proxy_url()
        if not self.verify_proxy:
            return proxy
        if proxy and self._is_proxy_verified(proxy):
            return proxy
        if proxy and self._verify_proxy_connection(proxy):
            self._mark_proxy_verified(proxy, True)
            log.info("proxy_verified", proxy_host=proxy.split("@")[-1] if "@" in proxy else proxy)
            return proxy
        if proxy:
            self._mark_proxy_verified(proxy, False)
        return None

    def rotate_proxy(self, strategy: CrawlStrategy) -> str | None:
        if not self._enabled:
            return None
        pt = strategy.proxy

        manager = self._get_thordata_manager(pt)
        manager.rotate()
        return manager.get_proxy_url()


WAF_SIGNATURES = {
    "incapsula": ["incapsula", "incapsula_incident_id", "_incap_", "visid_incap_"],
    "cloudflare": ["cloudflare", "cf-ray", "__cf_chl_", "cloudflare-ray"],
    "imperva": ["imperva", "incapsula", "_Incapsula_Resource", "citrix_netscaler"],
    "akamai": ["akamai", "akamai-ghost", "akamai-x检测", "akamai-x-cache"],
    "aws_waf": ["aws-waf", "awswaf", "aws-waf-token"],
    "datadome": ["datadome", "datadome_cookie", "_datadome"],
    "perimeterx": ["perimeterx", "px-captcha", "_px3", "px人参"],
    "f5_asm": ["f5 asm", "ts攻击力=", "BIG-IP", "f5_bigip"],
    "sucuri": ["sucuri", "sucuri-cloudproxy", "_sucuri"],
    "reblaze": ["reblaze", "_rblz"],
    "fortiweb": ["fortiweb", "fortiweb-cloud"],
    "radware": ["radware", "al不平衡露头"],
    "的光芒": ["的光芒", "customcaptcha", "recaptcha"],
}

BLOCK_KEYWORDS = {
    "403": ["403 forbidden", "access denied", "403 denial", "forbidden"],
    "429": ["429 too many", "rate limit", "too many requests", "slow down"],
    "captcha": ["captcha", "prove you're not", "i am not a robot", "complete the captcha"],
    "cloudflare": ["checking your browser", "cloudflare", "ray id", "one more step"],
}


def _detect_waf(html: str, headers: dict) -> str:
    combined = (html + str(headers)).lower()
    for waf_name, signatures in WAF_SIGNATURES.items():
        for sig in signatures:
            if sig.lower() in combined:
                return waf_name
    return ""


def _detect_block_reason(html: str, status_code: int, waf_detected: str) -> str:
    reasons = []
    if status_code == 403:
        reasons.append("HTTP 403 Forbidden")
    elif status_code == 429:
        reasons.append("HTTP 429 Rate Limited")
    elif status_code >= 500:
        reasons.append(f"HTTP {status_code} Server Error")

    html_lower = html.lower()
    for block_type, keywords in BLOCK_KEYWORDS.items():
        if block_type == "cloudflare" and waf_detected == "cloudflare":
            reasons.append("Cloudflare Challenge")
        for kw in keywords:
            if kw in html_lower:
                if block_type == "403" and "403" not in str(reasons):
                    reasons.append(f"Detected: {kw}")
                elif block_type == "429" and "429" not in str(reasons):
                    reasons.append(f"Detected: {kw}")
                elif block_type == "captcha" and "captcha" not in str(reasons):
                    reasons.append(f"Captcha Challenge: {kw}")

    if not reasons:
        if len(html) < 1000:
            reasons.append(f"Empty/Minimal Response ({len(html)} bytes)")
        else:
            reasons.append(f"Generic Block ({status_code})")

    return "; ".join(reasons)


def _generate_human_summary(
    site: str,
    page_pattern: str,
    block_type: str,
    status_code: int,
    waf_detected: str,
    block_reason: str,
    tier: int,
    render_type: str,
    proxy_type: str,
    ip_rotation_count: int,
    latency_ms: float,
) -> str:
    summary_parts = [
        f"Site: {site} ({page_pattern})",
        f"Failed at Tier {tier} using {render_type} via {proxy_type}",
    ]
    if ip_rotation_count > 0:
        summary_parts.append(f"Tried {ip_rotation_count + 1} IPs before giving up")

    summary_parts.append(f"Result: {block_reason}")
    if waf_detected:
        summary_parts.append(f"WAF Detected: {waf_detected}")

    summary_parts.append(f"Response Time: {latency_ms:.0f}ms")

    if status_code:
        summary_parts.append(f"HTTP Status: {status_code}")

    return " | ".join(summary_parts)


def _extract_response_headers(page, status_code: int) -> dict:
    headers = {}
    try:
        if page is not None and hasattr(page, "response"):
            headers["content_type"] = page.response.get("content-type", "")
            headers["server"] = page.response.get("server", "")
            headers["set_cookie"] = str(page.response.get("set-cookie", ""))[:200]
        elif hasattr(page, "headers"):
            headers = dict(page.headers) if page.headers else {}
    except Exception:
        pass

    if status_code in (301, 302, 303, 307, 308):
        headers["redirect"] = "Location header present"
    elif status_code == 403:
        headers["cf_challenge"] = "Challenge page suspected"
    return headers


class Fetcher:
    def __init__(
        self,
        proxy_provider: ProxyProvider | None = None,
        dynamic_profile: dict | None = None,
        request_timeout: float | None = None,
        page_load_timeout: float | None = None,
    ):
        from ai_crawler.config import config

        self.proxy_provider = proxy_provider
        self._session_cookies: dict[str, list] = {}
        self.dynamic_profile = dynamic_profile or {}
        self.request_timeout = request_timeout or config.REQUEST_TIMEOUT
        self.page_load_timeout = page_load_timeout or config.PAGE_LOAD_TIMEOUT

    def _build_headers(self, strategy: CrawlStrategy) -> dict:
        if not strategy.change_ua:
            return {}

        ua = self.dynamic_profile.get(
            "user_agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        platform = self.dynamic_profile.get("sec_ch_ua_platform", '"macOS"')
        ch_ua = self.dynamic_profile.get(
            "sec_ch_ua", '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"'
        )

        return {
            "User-Agent": ua,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "sec-ch-ua": ch_ua,
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": platform,
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
        }

    def fetch_with_strategy(
        self, task: CrawlTask, strategy: CrawlStrategy
    ) -> tuple[str, int | None, any]:
        if strategy.render == RenderType.CAMOUFOX:
            return self._fetch_with_camoufox(task, strategy)
        if strategy.render == RenderType.CLOAKBROWSER:
            return self._fetch_with_cloakbrowser(task, strategy)
        if strategy.render == RenderType.PLAYWRIGHT:
            return self._fetch_with_playwright(task, strategy)
        if strategy.render == RenderType.CLOUDERA:
            return self._fetch_with_uc(task, strategy)
        if strategy.render == RenderType.CLOUDSCRAPER:
            return self._fetch_with_cloudscraper(task, strategy)
        if strategy.render == RenderType.SELENIUMBASE:
            return self._fetch_with_seleniumbase(task, strategy)
        if strategy.render == RenderType.KAMELEO:
            return self._fetch_with_kameleo(task, strategy)
        return self._fetch_with_httpx(task, strategy)

    def _fetch_with_httpx(
        self, task: CrawlTask, strategy: CrawlStrategy
    ) -> tuple[str, int | None, any]:
        from curl_cffi import requests

        proxy = None
        if self.proxy_provider:
            proxy = self.proxy_provider.proxy_url(strategy)
        proxies = {"http": proxy, "https": proxy} if proxy else None

        headers = self._build_headers(strategy)

        delay_min, delay_max = strategy.delay_before
        if delay_min > 0:
            time.sleep(random.uniform(delay_min, delay_max))

        cookies = {}
        domain = task.url.split("/")[2]
        if strategy.use_cookies and domain in self._session_cookies:
            cookies = {c["name"]: c["value"] for c in self._session_cookies[domain]}

        try:
            with requests.Session(
                impersonate=self.dynamic_profile.get("curl_impersonate_target", "chrome120"),
                proxies=proxies,
            ) as client:
                resp = client.get(
                    task.url,
                    headers=headers,
                    cookies=cookies,
                    timeout=self.request_timeout,
                    allow_redirects=True,
                )
                try:
                    page_cookies = client.cookies.get_dict()
                    self._session_cookies[domain] = [
                        {"name": n, "value": v} for n, v in page_cookies.items()
                    ]
                except Exception:
                    pass
                return resp.text, resp.status_code, None
        except Exception as e:
            log.warning("fetch_error", url=task.url, error=str(e))
            return "", None, None

    def _fetch_with_camoufox(
        self, task: CrawlTask, strategy: CrawlStrategy
    ) -> tuple[str, int | None, any]:
        delay_min, delay_max = strategy.delay_before
        if delay_min > 0:
            time.sleep(random.uniform(delay_min, delay_max))

        try:
            from camoufox import Camoufox
            from ai_crawler.browser.fingerprint_spoofer import get_fingerprint_script

            with Camoufox(headless=True) as browser:
                page = browser.new_page()
                page.set_default_timeout(self.page_load_timeout * 1000)

                languages = self.dynamic_profile.get("languages")
                if languages:
                    try:
                        import json

                        languages = json.loads(languages)
                    except Exception:
                        pass

                fp_params = {
                    "session_id": task.task_id,
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
                    "permissions_default": self.dynamic_profile.get(
                        "permissions_default", "default"
                    ),
                    "orientation_angle": self.dynamic_profile.get("orientation_angle", 0),
                    "orientation_type": self.dynamic_profile.get(
                        "orientation_type", "landscape-primary"
                    ),
                }
                page.add_init_script(get_fingerprint_script(**fp_params))

                resp = page.goto(task.url, timeout=self.page_load_timeout * 1000)
                page.wait_for_load_state("load", timeout=self.page_load_timeout * 1000 * 0.8)
                page.wait_for_timeout(8000)
                if strategy.use_human_scroll:
                    self._human_scroll(page)
                content = page.content()
                status = resp.status if resp else 200
                return content, status, page
        except Exception as e:
            log.warning("camoufox_error", url=task.url, error=str(e))
            return "", None, None

    def _fetch_with_playwright(
        self, task: CrawlTask, strategy: CrawlStrategy
    ) -> tuple[str, int | None, any]:
        delay_min, delay_max = strategy.delay_before
        if delay_min > 0:
            time.sleep(random.uniform(delay_min, delay_max))

        try:
            from playwright.sync_api import sync_playwright
            from playwright_stealth import Stealth

            with sync_playwright() as p:
                stealth_args = ["--disable-blink-features=AutomationControlled"]
                if self.dynamic_profile and self.dynamic_profile.get("stealth_args"):
                    import json

                    try:
                        args_list = json.loads(self.dynamic_profile["stealth_args"])
                        if isinstance(args_list, list):
                            stealth_args.extend(args_list)
                    except:
                        pass

                browser = p.chromium.launch(headless=True, args=stealth_args)

                proxy_server = None
                if self.proxy_provider:
                    proxy_server = self.proxy_provider.proxy_url(strategy)

                ctx_args = {
                    "locale": self.dynamic_profile.get("locale", "en-US"),
                    "timezone_id": self.dynamic_profile.get("timezone_id", "America/New_York"),
                    "viewport": {"width": 1920, "height": 1080},
                    "user_agent": self.dynamic_profile.get(
                        "user_agent",
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    ),
                }

                try:
                    vp_str = self.dynamic_profile.get("viewport")
                    if vp_str:
                        import json

                        vp = json.loads(vp_str)
                        if "width" in vp and "height" in vp:
                            ctx_args["viewport"] = vp
                except Exception:
                    pass

                if proxy_server:
                    ctx_args["proxy"] = {"server": proxy_server}

                ctx = browser.new_context(**ctx_args)
                page = ctx.new_page()
                Stealth().apply_stealth_sync(page)

                from ai_crawler.browser.fingerprint_spoofer import get_fingerprint_script

                languages = self.dynamic_profile.get("languages")
                if languages:
                    try:
                        import json

                        languages = json.loads(languages)
                    except Exception:
                        pass

                fp_params = {
                    "session_id": task.task_id,
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
                    "permissions_default": self.dynamic_profile.get(
                        "permissions_default", "default"
                    ),
                    "orientation_angle": self.dynamic_profile.get("orientation_angle", 0),
                    "orientation_type": self.dynamic_profile.get(
                        "orientation_type", "landscape-primary"
                    ),
                }
                page.add_init_script(get_fingerprint_script(**fp_params))

                resp = page.goto(task.url, timeout=self.page_load_timeout * 1000)
                page.wait_for_load_state("load", timeout=self.page_load_timeout * 1000 * 0.8)
                page.wait_for_timeout(8000)
                if strategy.use_human_scroll:
                    self._human_scroll(page)
                content = page.content()
                status = resp.status if resp else 200
                browser.close()
                return content, status, page
        except Exception as e:
            log.warning("playwright_error", url=task.url, error=str(e))
            return "", None, None

    def _fetch_with_uc(
        self, task: CrawlTask, strategy: CrawlStrategy
    ) -> tuple[str, int | None, any]:
        delay_min, delay_max = strategy.delay_before
        if delay_min > 0:
            time.sleep(random.uniform(delay_min, delay_max))

        try:
            import undetected_chromedriver as uc
            from selenium.webdriver.common.by import By

            options = uc.ChromeOptions()
            options.headless = True
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.page_load_strategy = "normal"

            proxy = None
            if self.proxy_provider:
                proxy = self.proxy_provider.proxy_url(strategy)
            if proxy:
                options.add_argument(f"--proxy-server={proxy}")

            driver = uc.Chrome(options=options, version_main=None)
            driver.set_page_load_timeout(30)
            driver.get(task.url)
            time.sleep(5)
            content = driver.page_source
            status = 200
            driver.quit()
            return content, status, None
        except Exception as e:
            log.warning("uc_error", url=task.url, error=str(e))
            return "", None, None

    def _fetch_with_cloudscraper(
        self, task: CrawlTask, strategy: CrawlStrategy
    ) -> tuple[str, int | None, any]:
        delay_min, delay_max = strategy.delay_before
        if delay_min > 0:
            time.sleep(random.uniform(delay_min, delay_max))

        try:
            import cloudscraper

            proxy = None
            if self.proxy_provider:
                proxy = self.proxy_provider.proxy_url(strategy)

            scraper = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "desktop": True},
                proxy=proxy,
            )
            resp = scraper.get(task.url, timeout=self.request_timeout)
            return resp.text, resp.status_code, None
        except Exception as e:
            log.warning("cloudscraper_error", url=task.url, error=str(e))
            return "", None, None

    def _fetch_with_seleniumbase(
        self, task: CrawlTask, strategy: CrawlStrategy
    ) -> tuple[str, int | None, any]:
        from ai_crawler.browser.seleniumbase_wrapper import SeleniumBaseWrapper

        delay_min, delay_max = strategy.delay_before
        if delay_min > 0:
            time.sleep(random.uniform(delay_min, delay_max))

        proxy = None
        if self.proxy_provider:
            proxy = self.proxy_provider.proxy_url(strategy)

        try:
            wrapper = SeleniumBaseWrapper(
                headless=True,
                proxy=proxy,
                undetected=True,
                wait_selector=strategy.wait_selector,
                wait_time=8.0 if strategy.extra_wait == 0 else strategy.extra_wait,
                human_scroll=strategy.use_human_scroll,
                dynamic_profile=self.dynamic_profile or {},
            )
            html = wrapper.fetch(task.url)
            return html, 200, None
        except Exception as e:
            log.warning("seleniumbase_error", url=task.url, error=str(e))
            return "", None, None

    def _fetch_with_kameleo(
        self, task: CrawlTask, strategy: CrawlStrategy
    ) -> tuple[str, int | None, any]:
        from ai_crawler.browser.kameleo_wrapper import KameleoWrapper

        delay_min, delay_max = strategy.delay_before
        if delay_min > 0:
            time.sleep(random.uniform(delay_min, delay_max))

        proxy = None
        if self.proxy_provider:
            proxy = self.proxy_provider.proxy_url(strategy)

        from ai_crawler.config import config

        api_url = config.KAMELEO_API_URL
        api_key = config.KAMELEO_API_KEY

        try:
            wrapper = KameleoWrapper(
                api_url=api_url,
                api_key=api_key,
                proxy=proxy,
                wait_time=8.0 if strategy.extra_wait == 0 else strategy.extra_wait,
                human_scroll=strategy.use_human_scroll,
                dynamic_profile=self.dynamic_profile or {},
            )
            html = wrapper.fetch(task.url)
            return html, 200, None
        except Exception as e:
            log.warning("kameleo_error", url=task.url, error=str(e))
            return "", None, None

    def _fetch_with_cloakbrowser(
        self, task: CrawlTask, strategy: CrawlStrategy
    ) -> tuple[str, int | None, any]:
        delay_min, delay_max = strategy.delay_before
        if delay_min > 0:
            time.sleep(random.uniform(delay_min, delay_max))

        proxy = None
        if self.proxy_provider:
            proxy = self.proxy_provider.proxy_url(strategy)

        try:
            from cloakbrowser import launch
            import json

            launch_kwargs = {
                "headless": True,
            }

            if proxy:
                launch_kwargs["proxy"] = proxy

            locale = self.dynamic_profile.get("locale", "en-US")
            timezone = self.dynamic_profile.get("timezone_id", "America/New_York")
            viewport_dict = self.dynamic_profile.get("viewport")
            if viewport_dict:
                try:
                    vp = json.loads(viewport_dict)
                    launch_kwargs["viewport"] = vp
                except Exception:
                    pass

            browser = launch(**launch_kwargs)
            page = browser.new_page()

            languages = self.dynamic_profile.get("languages")
            if languages:
                try:
                    languages = json.loads(languages)
                    page.set_extra_http_headers(
                        {
                            "Accept-Language": ",".join(languages)
                            if isinstance(languages, list)
                            else languages
                        }
                    )
                except Exception:
                    pass

            resp = page.goto(task.url, timeout=self.page_load_timeout * 1000)
            page.wait_for_load_state("load", timeout=self.page_load_timeout * 1000 * 0.8)
            page.wait_for_timeout(8000)

            if strategy.use_human_scroll:
                self._human_scroll(page)

            content = page.content()
            status = resp.status if resp else 200

            page.close()
            browser.close()

            return content, status, page
        except Exception as e:
            log.warning("cloakbrowser_error", url=task.url, error=str(e))
            return "", None, None

    def _human_scroll(self, page):
        try:
            from ai_crawler.browser.human_mouse import HumanMouseController
            import json

            viewport = page.viewport_size or {"width": 1920, "height": 1080}

            jitter_std = 2.5
            curve_intensity = 0.3
            try:
                bh_str = self.dynamic_profile.get("mouse_behavior")
                if bh_str:
                    bh = json.loads(bh_str)
                    jitter_std = bh.get("jitter_std", 2.5)
                    curve_intensity = bh.get("curve_intensity", 0.3)
            except Exception:
                pass

            controller = HumanMouseController(
                page, jitter_std=jitter_std, curve_intensity=curve_intensity
            )

            for _ in range(random.randint(2, 4)):
                x = random.randint(100, viewport["width"] - 100)
                y = random.randint(100, viewport["height"] - 100)
                controller.move_to(x, y)
                time.sleep(random.uniform(0.2, 0.6))

            for _ in range(random.randint(3, 6)):
                scroll_y = random.randint(300, 800)
                page.mouse.wheel(0, scroll_y)
                time.sleep(random.uniform(0.8, 2.5))

        except Exception as e:
            log.warning("human_scroll_error", error=str(e))
            pass


class CrawlRunner:
    IP_ROTATION_BLOCK_TYPES = {
        BlockType.HTTP_403,
        BlockType.HTTP_429,
        BlockType.HTTP_451,
        BlockType.HTTP_TIMEOUT,
        BlockType.BOT_DETECTED,
        BlockType.CLOUDFLARE,
        BlockType.EMPTY_RESPONSE,
    }

    def __init__(
        self,
        proxy_username: str,
        proxy_password: str,
        llm_api_key: str | None = None,
        concurrency: int = 3,
        trace_store: TraceStore | None = None,
        dspy_model=None,
        dynamic_profile: dict | None = None,
        captcha_solver=None,
        max_ip_retries: int = 3,
        proxy_disabled: bool = False,
    ):
        self.queue = CrawlQueue()
        self.proxy_provider = ProxyProvider(proxy_username, proxy_password, disabled=proxy_disabled)
        self.fetcher = Fetcher(self.proxy_provider, dynamic_profile)
        self.anti_bot = AntiBotHandler()
        self.block_detector = BlockDetector()
        self.executor = ThreadPoolExecutor(max_workers=concurrency)
        self._running = False
        self._results: list[CrawlResult] = []
        self._results_lock = Lock()
        self.trace_store = trace_store or TraceStore()
        self.dspy_model = dspy_model
        self.captcha_solver = captcha_solver
        self.max_ip_retries = max_ip_retries
        self._initial_tier_selector = None

        from ai_crawler.core.extraction import SITE_EXTRACTION_CHAINS

        self._extraction_chains = SITE_EXTRACTION_CHAINS

    def add_tasks(self, tasks: list[CrawlTask]):
        self.queue.enqueue(tasks)

    def set_initial_tier_selector(self, selector):
        self._initial_tier_selector = selector

    def _get_llm_tier(self, site: str, page_pattern: str, failure_history: str = "") -> int | None:
        if not self._initial_tier_selector:
            return None
        try:
            result = self._initial_tier_selector(
                site=site,
                page_pattern=page_pattern,
                failure_history=failure_history,
            )
            tier_str = str(result.start_tier).strip()
            tier = int(tier_str)
            if 1 <= tier <= 7:
                return tier
        except Exception:
            pass
        return None

    def _process_one(self, task: CrawlTask) -> CrawlResult:
        memory = self.queue.site_memory.get(task.site)

        if task.current_index == 0 and self._initial_tier_selector:
            if not memory:
                memory = self.queue.site_memory.setdefault(task.site, SiteMemory(site=task.site))
            cached_tier = memory.get_llm_tier(task.page_pattern.value)
            if cached_tier is None:
                failure_history = memory.get_failure_history_for_llm(task.page_pattern.value)
                llm_tier = self._get_llm_tier(task.site, task.page_pattern.value, failure_history)
                if llm_tier is not None:
                    memory.record_llm_tier(task.page_pattern.value, llm_tier)
                    task.strategies = CrawlStrategy.get_tier_strategies(llm_tier, end_tier=8)
                    task.metadata["start_tier"] = llm_tier
                    task.metadata["llm_tier"] = True
                    log.info(
                        "llm_tier_recommended",
                        site=task.site,
                        page_pattern=task.page_pattern.value,
                        tier=llm_tier,
                    )
            else:
                if cached_tier != task.metadata.get("start_tier"):
                    task.strategies = CrawlStrategy.get_tier_strategies(cached_tier, end_tier=8)
                    task.metadata["start_tier"] = cached_tier

        if memory and memory.successful_strategies and task.current_index == 0:
            best = memory.successful_strategies[0]
            if not task.strategies or task.strategies[0] != best:
                task.add_strategy_front(best)

        strategy = task.current_strategy()
        if not strategy:
            self.queue.on_failure(task, BlockType.UNKNOWN, "All strategies exhausted")
            return CrawlResult(
                task=task,
                strategy=task.strategies[-1],
                success=False,
                error="All strategies exhausted",
            )

        delay_min, delay_ms = strategy.delay_after
        time.sleep(random.uniform(delay_min, delay_ms))

        log.info(
            f"[CRAWL] site={task.site} url={task.url} "
            f"tier={getattr(strategy, 'tier', '?')} "
            f"render={strategy.render.value} "
            f"proxy={strategy.proxy.value} "
            f"change_ua={strategy.change_ua} "
            f"use_cookies={strategy.use_cookies} "
            f"human_scroll={strategy.use_human_scroll}"
        )

        t0 = time.time()
        html, status_code, page = self.fetcher.fetch_with_strategy(task, strategy)
        latency_ms = (time.time() - t0) * 1000

        cost_estimate = self._estimate_cost(strategy, latency_ms)

        blocked, block_type = self.anti_bot.is_blocked(status_code, html)
        self.anti_bot.record_attempt(task.url, strategy, block_type, blocked)

        log.info(
            f"[RESULT] site={task.site} url={task.url} "
            f"status={status_code} "
            f"blocked={blocked} "
            f"block_type={block_type.value if hasattr(block_type, 'value') else block_type} "
            f"latency_ms={latency_ms:.0f} "
            f"size={len(html)}"
        )

        attempt_index = task.current_index
        ip_rotation_count = 0

        if (
            blocked
            and block_type in self.IP_ROTATION_BLOCK_TYPES
            and not self.proxy_provider.disabled
        ):
            for ip_retry in range(self.max_ip_retries):
                log.info(
                    "ip_rotation_retry",
                    url=task.url,
                    block_type=block_type,
                    retry=ip_retry + 1,
                    max_retries=self.max_ip_retries,
                )

                new_proxy = self.proxy_provider.rotate_proxy(strategy)
                if not new_proxy:
                    log.warning("ip_rotation_failed_no_proxy", url=task.url)
                    break

                time.sleep(random.uniform(1.0, 3.0))
                ip_rotation_count += 1

                t0 = time.time()
                html, status_code, page = self.fetcher.fetch_with_strategy(task, strategy)
                latency_ms = (time.time() - t0) * 1000

                blocked, block_type = self.anti_bot.is_blocked(status_code, html)
                if not blocked:
                    log.info("ip_rotation_success", url=task.url, retry=ip_retry + 1)
                    break

            if blocked and ip_retry == self.max_ip_retries - 1:
                log.warning(
                    "ip_rotation_exhausted",
                    url=task.url,
                    block_type=block_type,
                    total_retries=self.max_ip_retries,
                )

        response_headers = _extract_response_headers(page, status_code or 0)
        waf_detected = _detect_waf(html, response_headers) if blocked else ""
        block_reason = _detect_block_reason(html, status_code or 0, waf_detected)
        fingerprint_profile = (
            self.fetcher.dynamic_profile if hasattr(self.fetcher, "dynamic_profile") else {}
        )

        trace_kwargs = {
            "task": task,
            "strategy": strategy,
            "block_type": block_type,
            "response_snippet": html[:500],
            "success": False,
            "latency_ms": latency_ms,
            "attempt_index": attempt_index,
            "cost_estimate": cost_estimate,
            "status_code": status_code or 0,
            "response_headers": response_headers,
            "full_html_size": len(html),
            "ip_rotation_count": ip_rotation_count,
            "fingerprint_profile": fingerprint_profile,
            "waf_detected": waf_detected,
            "human_friendly_summary": _generate_human_summary(
                task.site,
                task.page_pattern.value,
                block_type,
                status_code or 0,
                waf_detected,
                block_reason,
                getattr(strategy, "tier", 1),
                strategy.render.value,
                strategy.proxy.value,
                ip_rotation_count,
                latency_ms,
            )
            if blocked
            else "",
        }

        if blocked:
            if block_type == BlockType.CAPTCHA and self.captcha_solver:
                log.info("captcha_detected", url=task.url)
                captcha_solved = self._handle_captcha(task, html, strategy)
                if captcha_solved:
                    html, status_code, page = self.fetcher.fetch_with_strategy(task, strategy)
                    blocked, block_type = self.anti_bot.is_blocked(status_code, html)
                    if not blocked:
                        pass
                    else:
                        self.trace_store.record(**trace_kwargs)
                        needs_llm, new_strategy = self.queue.on_failure(task, block_type, html)
                        return CrawlResult(
                            task=task,
                            strategy=strategy,
                            success=False,
                            html=html,
                            block_type=block_type,
                        )

            self.trace_store.record(**trace_kwargs)

            needs_llm, new_strategy = self.queue.on_failure(task, block_type, html)

            if needs_llm:
                llm_decision = False
                if self.dspy_model:
                    dspy_result = self._try_dspy_strategy(task, block_type, html[:500])
                    if dspy_result:
                        task.add_strategy_front(dspy_result)
                        llm_decision = False
                        dspy_trace_kwargs = dict(trace_kwargs)
                        dspy_trace_kwargs["strategy"] = dspy_result
                        dspy_trace_kwargs["response_snippet"] = ""
                        dspy_trace_kwargs["success"] = False
                        dspy_trace_kwargs["latency_ms"] = 0
                        dspy_trace_kwargs["attempt_index"] = attempt_index + 1
                        dspy_trace_kwargs["cost_estimate"] = 0
                        dspy_trace_kwargs["llm_decision"] = False
                        self.trace_store.record(**dspy_trace_kwargs)

            return CrawlResult(
                task=task,
                strategy=strategy,
                success=False,
                html=html,
                block_type=block_type,
            )

        self.trace_store.record(
            task=task,
            strategy=strategy,
            block_type=BlockType.NONE,
            response_snippet="",
            success=True,
            latency_ms=latency_ms,
            attempt_index=attempt_index,
            cost_estimate=cost_estimate,
            status_code=status_code or 0,
            response_headers=response_headers,
            full_html_size=len(html),
            ip_rotation_count=ip_rotation_count,
            fingerprint_profile=fingerprint_profile,
            waf_detected="",
            human_friendly_summary=f"Site: {task.site} ({task.page_pattern.value}) | Tier {getattr(strategy, 'tier', 1)} {strategy.render.value} via {strategy.proxy.value} | Success | {latency_ms:.0f}ms",
        )

        self.queue.on_success(task, strategy)

        chain = self._extraction_chains.get(task.site)
        if chain:
            extraction_result = chain.extract(page, html, task.url)
        else:
            extraction_result = ExtractionResult(products=[], strategy="none", method="none")
        products = extraction_result.products
        products = extraction_result.products

        if not products and strategy.render in (
            RenderType.NONE,
            RenderType.PLAYWRIGHT,
            RenderType.CLOUDSCRAPER,
        ):
            upgrade_render = RenderType.CAMOUFOX
            if strategy.render == RenderType.NONE and "costway.com" in task.url:
                upgrade_render = RenderType.CLOUDSCRAPER

            upgrade = CrawlStrategy(
                proxy=strategy.proxy,
                render=upgrade_render,
                change_ua=True,
                use_human_scroll=True,
            )
            task.add_strategy_front(upgrade)
            self.queue.on_failure(task, "empty_content", html[:200])
            return CrawlResult(
                task=task,
                strategy=strategy,
                success=False,
                html=html,
                block_type="empty_content",
                products=[],
            )

        return CrawlResult(
            task=task,
            strategy=strategy,
            success=True,
            html=html,
            products=products,
        )

    def _estimate_cost(self, strategy: CrawlStrategy, latency_ms: float) -> float:
        proxy_gb_cost = 0.008
        render_cost_per_sec = 0.001
        delay_cost = (
            latency_ms / 1000 * render_cost_per_sec if strategy.render != RenderType.NONE else 0
        )
        return delay_cost

    def _handle_captcha(self, task: CrawlTask, html: str, strategy: CrawlStrategy) -> bool:
        """Attempt to solve CAPTCHA and return True if successful."""
        from ai_crawler.captcha import CaptchaDetector

        if not self.captcha_solver:
            return False

        detector = CaptchaDetector()
        detector._solver = self.captcha_solver

        detected, captcha_type, site_key, action = detector.detect(html)
        if not detected:
            log.warning("captcha_key_not_found", site=task.site, url=task.url)
            return False

        try:
            log.info(
                "solving_captcha",
                site=task.site,
                type=captcha_type,
                key=site_key,
                action=action if "v3" in captcha_type else None,
            )
            solution = detector.solve(captcha_type, site_key, task.url, action)
            log.info(
                "captcha_solved", site=task.site, solution_length=len(solution) if solution else 0
            )
            return bool(solution)
        except Exception as e:
            log.error("captcha_solve_failed", site=task.site, error=str(e))
            return False

    def _try_dspy_strategy(
        self, task: CrawlTask, block_type: str, snippet: str
    ) -> CrawlStrategy | None:
        if not self.dspy_model:
            return None
        try:
            result = self.dspy_model(
                site=task.site,
                page_pattern=task.page_pattern.value,
                block_type=block_type,
                response_snippet=snippet,
                attempt_history=[],
            )
            return self._dspy_result_to_strategy(result)
        except Exception:
            return None

    def _dspy_result_to_strategy(self, result) -> CrawlStrategy:
        proxy_map = {
            "thordata_us": ProxyType.THORDATA_US,
            "thordata_us_city": ProxyType.THORDATA_US_CITY,
            "thordata_any": ProxyType.THORDATA_ANY,
            "thordata_dedicated": ProxyType.THORDATA_DEDICATED,
        }
        render_map = {
            "none": RenderType.NONE,
            "playwright": RenderType.PLAYWRIGHT,
            "camoufox": RenderType.CAMOUFOX,
            "kameleo": RenderType.KAMELEO,
        }
        s = result.recommended_strategy
        return CrawlStrategy(
            proxy=proxy_map.get(s.get("proxy", "thordata_dedicated"), ProxyType.THORDATA_DEDICATED),
            render=render_map.get(s.get("render", "none"), RenderType.NONE),
            change_ua=s.get("change_ua", False),
            use_cookies=s.get("use_cookies", False),
            use_human_scroll=s.get("use_human_scroll", False),
        )

    def run(self, max_items: int = 100) -> list[CrawlResult]:
        self._running = True
        results = []

        while self._running:
            pending, running, failed = self.queue.size()
            if pending == 0 and running == 0:
                break

            task = self.queue.dequeue()
            if not task:
                time.sleep(0.5)
                continue

            if len(results) >= max_items:
                self._running = False
                break

            future = self.executor.submit(self._process_one, task)
            try:
                result = future.result(timeout=60)
                results.append(result)

                with self._results_lock:
                    self._results.append(result)

            except Exception as e:
                log.error("task_error", task_id=task.task_id, error=str(e))

        return results

    def run_async(self, max_items: int = 100) -> list[CrawlResult]:
        return self.run(max_items)

    def stop(self):
        self._running = False
        self.executor.shutdown(wait=False)
