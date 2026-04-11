import asyncio
import json
import random
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from ai_crawler.browser import CamoufoxWrapper, FingerprintConfig, HumanMouseController
from ai_crawler.captcha import CaptchaSolver, CaptchaType
from ai_crawler.proxy import ThorDataManager, ThorDataPool
from ai_crawler.spiders import EXTRACTORS, Product

log = structlog.get_logger()


class CrawlerConfig:
    def __init__(
        self,
        thordata_username: str,
        thordata_password: str,
        captcha_api_key: str,
        country: str = "us",
        request_delay: tuple[float, float] = (5.0, 15.0),
        max_retries: int = 3,
        headless: bool = True,
    ):
        self.thordata_username = thordata_username
        self.thordata_password = thordata_password
        self.captcha_api_key = captcha_api_key
        self.country = country
        self.request_delay = request_delay
        self.max_retries = max_retries
        self.headless = headless


class ECrawler:
    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.pool = ThorDataPool(
            username=config.thordata_username,
            password=config.thordata_password,
            country=config.country,
            pool_size=3,
            sticky=True,
            session_duration=180,
        )
        self.proxy_mgr = ThorDataManager(self.pool)
        self.captcha = CaptchaSolver(config.captcha_api_key)
        self.results: list[Product] = []
        self._session_cookies: dict[str, Any] = {}

    def _random_delay(self) -> None:
        delay = random.uniform(*self.config.request_delay)
        time.sleep(delay)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _fetch_page(self, url: str, wait_selector: str | None = None) -> str:
        proxy = self.proxy_mgr.get_proxy()
        fp = FingerprintConfig()

        wrapper = CamoufoxWrapper(
            fp=fp,
            headless=self.config.headless,
            proxy=proxy,
        )

        with wrapper.stealth_page() as page:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                self._human_scroll_page(page)
                if wait_selector:
                    page.wait_for_selector(wait_selector, timeout=10000)
                time.sleep(random.uniform(1, 3))
                html = page.content()
                self._save_cookies(url, page)
                return html
            except Exception as e:
                log.warning("fetch_failed", url=url, proxy=proxy, error=str(e))
                self.proxy_mgr.rotate_now()
                raise

    def _human_scroll_page(self, page) -> None:
        mouse = HumanMouseController(page)
        for y in range(0, 1500, random.randint(100, 200)):
            mouse.move_to(random.randint(200, 800), y)
            time.sleep(random.uniform(0.05, 0.15))

    def _save_cookies(self, url: str, page) -> None:
        domain = url.split("/")[2]
        try:
            cookies = page.context.cookies()
            self._session_cookies[domain] = cookies
        except Exception:
            pass

    def _detect_captcha(self, html: str) -> tuple[bool, str]:
        captcha_indicators = [
            ("captcha", "captcha detected"),
            ("robot", "robot check detected"),
            ("blocked", "blocked detected"),
            ("cf-challenge", "cloudflare challenge"),
            ("access denied", "access denied"),
        ]
        html_lower = html.lower()
        for indicator, msg in captcha_indicators:
            if indicator in html_lower:
                return True, msg
        return False, ""

    def crawl_search_results(self, site: str, query: str, pages: int = 3) -> list[Product]:
        extractor = EXTRACTORS.get(site)
        if not extractor:
            raise ValueError(f"Unknown site: {site}")

        search_urls = {
            "amazon": f"https://www.amazon.com/s?k={query.replace(' ', '+')}",
            "walmart": f"https://www.walmart.com/search?q={query.replace(' ', '+')}",
            "target": f"https://www.target.com/s?searchTerm={query.replace(' ', '+')}",
            "ebay": f"https://www.ebay.com/sch/i.html?_nkw={query.replace(' ', '+')}",
        }

        url = search_urls.get(site)
        if not url:
            raise ValueError(f"No search URL for {site}")

        site_products = []
        for page_num in range(1, pages + 1):
            page_url = f"{url}&page={page_num}" if page_num > 1 else url
            log.info("crawling_page", site=site, page=page_num, url=page_url)

            html = self._fetch_page(page_url)
            is_captcha, msg = self._detect_captcha(html)
            if is_captcha:
                log.warning("captcha_blocked", site=site, page=page_num, reason=msg)
                self._handle_captcha(site, html, page_url)
                html = self._fetch_page(page_url)

            products = extractor["list"](html, page_url)
            site_products.extend(products)
            log.info("extracted_products", site=site, page=page_num, count=len(products))
            self._random_delay()

        self.results.extend(site_products)
        return site_products

    def crawl_product_detail(self, site: str, url: str) -> Product:
        extractor = EXTRACTORS.get(site)
        if not extractor:
            raise ValueError(f"Unknown site: {site}")

        html = self._fetch_page(url)
        is_captcha, msg = self._detect_captcha(html)
        if is_captcha:
            log.warning("captcha_on_detail", site=site, url=url, reason=msg)
            self._handle_captcha(site, html, url)
            html = self._fetch_page(url)

        product = extractor["detail"](html, url)
        self.results.append(product)
        return product

    def _handle_captcha(self, site: str, html: str, url: str) -> None:
        if "cf-challenge" in html.lower() or "cloudflare" in html.lower():
            log.warning("cloudflare_challenge", site=site)
            time.sleep(random.uniform(10, 20))
            return

        site_key = self._extract_site_key(site, html)
        if site_key:
            log.info("solving_captcha", site=site, type=site_key[0])
            try:
                captcha_type, key = site_key
                solution = self.captcha.solve(captcha_type, key, url)
                log.info("captcha_solved", site=site)
            except Exception as e:
                log.error("captcha_failed", site=site, error=str(e))

    def _extract_site_key(self, site: str, html: str) -> tuple[CaptchaType, str] | None:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")

        if site == "amazon":
            site_key = soup.select_one("[data-sitekey], [data-captcha-sitekey]")
            if site_key:
                return CaptchaType.RECAPTCHA_V2, site_key.get("data-sitekey", "")
        elif site == "walmart":
            site_key = soup.select_one("[data-sitekey]")
            if site_key:
                return CaptchaType.HCAPTCHA, site_key.get("data-sitekey", "")

        return None

    def save_results(self, output_dir: str = "output") -> None:
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)

        out_file = path / f"crawl_{int(time.time())}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump([p.to_dict() for p in self.results], f, ensure_ascii=False, indent=2)

        csv_file = path / f"crawl_{int(time.time())}.csv"
        import csv

        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            if self.results:
                writer = csv.DictWriter(f, fieldnames=self.results[0].to_dict().keys())
                writer.writeheader()
                for p in self.results:
                    writer.writerow(p.to_dict())

        log.info("results_saved", json=str(out_file), csv=str(csv_file), total=len(self.results))
