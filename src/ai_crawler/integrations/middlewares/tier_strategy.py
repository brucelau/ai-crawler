from scrapy import Spider, Request
from scrapy.http import HtmlResponse, Response
from twisted.internet import defer

from ai_crawler.core.types import (
    CrawlStrategy,
    CrawlTask,
    ProxyType,
    RenderType,
    PagePattern,
)
from ai_crawler.config.sites import get_site_tier
from ai_crawler.core.engine.handler import BlockDetector, BlockType
from ai_crawler.core.engine.trace_store import TraceStore, AntiBotTrace
from ai_crawler.core.engine.introspection import get_system_facts


WAF_SIGNATURES = {
    "incapsula": ["incapsula", "incapsula_incident_id", "_incap_", "visid_incap_"],
    "cloudflare": ["cloudflare", "cf-ray", "__cf_chl_", "cloudflare-ray"],
    "imperva": ["imperva", "incapsula", "_Incapsula_Resource", "citrix_netscaler"],
    "akamai": ["akamai", "akamai-ghost", "akamai-x-cache"],
    "datadome": ["datadome", "datadome_cookie", "_datadome"],
    "perimeterx": ["perimeterx", "px-captcha", "_px3"],
    "f5_asm": ["f5 asm", "BIG-IP", "f5_bigip"],
}


class TierStrategyMiddleware:
    def __init__(
        self, llm_api_key: str = None, trace_dir: str = "traces", model_dir: str = "models"
    ):
        self.detector = BlockDetector()
        self._llm_api_key = llm_api_key
        self._profile_generator = None
        self._tier_selector = None
        self._strategy_selector = None
        self._trace_store = TraceStore(storage_dir=trace_dir)
        self._model_dir = model_dir
        self._current_model_version = 0
        self._ip_rotation_count = 0
        self._attempt_index = 0
        self._attempt_history = {}
        self._initial_tier_cache: dict[str, tuple[int, float]] = {}
        self._initial_tier_cache_ttl: float = 86400.0
        self._successful_tier_cache: dict[str, tuple[int, float]] = {}
        self._successful_tier_cache_ttl: float = 86400.0

    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        llm_api_key = settings.get("LLM_API_KEY") or settings.get("OPENAI_API_KEY") or None
        trace_dir = settings.get("TRACE_DIR", "traces")
        model_dir = settings.get("MODEL_DIR", "models")
        instance = cls(llm_api_key=llm_api_key, trace_dir=trace_dir, model_dir=model_dir)
        instance._crawler = crawler
        return instance

    def _detect_waf(self, response: Response) -> str:
        if not isinstance(response, HtmlResponse):
            return ""
        combined = (response.text + str(response.headers)).lower()
        for waf_name, signatures in WAF_SIGNATURES.items():
            for sig in signatures:
                if sig.lower() in combined:
                    return waf_name
        return ""

    def _get_profile_generator(self):
        if not self._llm_api_key:
            return None
        if self._profile_generator is None:
            try:
                from ai_crawler.core.llm.dspy_model import ProfileGenerator

                self._profile_generator = ProfileGenerator()
            except Exception:
                pass
        return self._profile_generator

    def _get_tier_selector(self):
        if not self._llm_api_key:
            return None
        if self._tier_selector is None:
            try:
                from ai_crawler.core.llm.dspy_model import InitialTierSelector

                self._tier_selector = InitialTierSelector()
            except Exception:
                pass
        return self._tier_selector

    def _get_strategy_selector(self):
        if not self._llm_api_key:
            return None

        try:
            import json
            from pathlib import Path

            version_file = Path(self._model_dir) / "strategy_selector_version.json"
            model_file = Path(self._model_dir) / "strategy_selector.pkl"

            if version_file.exists() and model_file.exists():
                with open(version_file, "r") as f:
                    version_info = json.load(f)
                current_version = version_info.get("version", 0)

                if current_version > self._current_model_version:
                    import pickle

                    with open(model_file, "rb") as f:
                        self._strategy_selector = pickle.load(f)
                    self._current_model_version = current_version
                    logger = logging.getLogger(__name__)
                    logger.info(f"Hot-reloaded trained StrategySelector: v{current_version}")
                    return self._strategy_selector

            if self._strategy_selector is None:
                from ai_crawler.core.llm.dspy_model import StrategySelector

                self._strategy_selector = StrategySelector()

        except Exception:
            if self._strategy_selector is None:
                try:
                    from ai_crawler.core.llm.dspy_model import StrategySelector

                    self._strategy_selector = StrategySelector()
                except Exception:
                    pass

        return self._strategy_selector

    def _generate_fingerprint(self, spider):
        generator = self._get_profile_generator()
        if not generator:
            return self._get_default_fingerprint()
        try:
            import json

            system_facts = get_system_facts()
            result = generator(system_facts=json.dumps(system_facts))
            fp = {
                "user_agent": result.user_agent,
                "sec_ch_ua_platform": result.sec_ch_ua_platform,
                "sec_ch_ua": result.sec_ch_ua,
                "stealth_args": result.stealth_args,
                "curl_impersonate_target": result.curl_impersonate_target,
                "timezone_id": result.timezone_id,
                "locale": result.locale,
                "viewport": result.viewport,
                "mouse_behavior": result.mouse_behavior,
                "gpu_vendor": result.gpu_vendor,
                "gpu_renderer": result.gpu_renderer,
                "device_pixel_ratio": result.device_pixel_ratio,
                "platform_string": result.platform_string,
                "connection_type": result.connection_type,
                "downlink": result.downlink,
                "rtt": result.rtt,
                "plugins": result.plugins,
                "usb": result.usb,
                "media_devices": result.media_devices,
                "battery": result.battery,
                "webdriver_value": result.webdriver_value,
                "permissions_default": result.permissions_default,
                "orientation_angle": result.orientation_angle,
                "orientation_type": result.orientation_type,
                "screen_width": 1920,
                "screen_height": 1080,
                "languages": [result.locale] if result.locale else ["en-US"],
            }
            return fp
        except Exception as e:
            spider.logger.warning(f"Fingerprint generation failed: {e}")
            return self._get_default_fingerprint()

    def _get_default_fingerprint(self) -> dict:
        return {
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "sec_ch_ua_platform": '"macOS"',
            "sec_ch_ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "stealth_args": "[]",
            "curl_impersonate_target": "chrome120",
            "timezone_id": "America/New_York",
            "locale": "en-US",
            "viewport": {"width": 1920, "height": 1080},
            "mouse_behavior": {"jitter_std": 0.5, "curve_intensity": 1.0, "scroll_pause_mean": 0.8},
            "gpu_vendor": "Apple",
            "gpu_renderer": "Apple M4",
            "device_pixel_ratio": 2.0,
            "platform_string": "MacIntel",
            "connection_type": "wifi",
            "downlink": 10,
            "rtt": 50,
            "screen_width": 1920,
            "screen_height": 1080,
            "languages": ["en-US"],
            "plugins": "[]",
            "usb": "{}",
            "media_devices": "[]",
            "battery": "{}",
            "webdriver_value": "undefined",
            "permissions_default": "default",
            "orientation_angle": 0,
            "orientation_type": "landscape-primary",
        }

    def _initial_tier_cache_key(self, site: str, page_type: str) -> str:
        return f"{site}:{page_type}"

    def _is_initial_tier_cache_valid(self, site: str, page_type: str) -> bool:
        import time

        key = self._initial_tier_cache_key(site, page_type)
        if key not in self._initial_tier_cache:
            return False
        _, cached_time = self._initial_tier_cache[key]
        return (time.time() - cached_time) < self._initial_tier_cache_ttl

    def _select_initial_tier(self, site: str, page_pattern, spider) -> int:
        import time

        page_type = page_pattern.value if page_pattern else "unknown"
        successful_key = self._initial_tier_cache_key(site, page_type)
        if successful_key in self._successful_tier_cache:
            cached_tier, cached_time = self._successful_tier_cache[successful_key]
            if (time.time() - cached_time) < self._successful_tier_cache_ttl:
                spider.logger.info(f"Using successful tier: {cached_tier} for {site}:{page_type}")
                return cached_tier

        if self._is_initial_tier_cache_valid(site, page_type):
            cached_tier, _ = self._initial_tier_cache[successful_key]
            spider.logger.info(f"Using cached initial tier: {cached_tier} for {site}:{page_type}")
            return cached_tier

        selector = self._get_tier_selector()
        if not selector:
            return get_site_tier(site, page_pattern)
        try:
            result = selector(site=site, page_pattern=page_type)
            tier = int(result.start_tier)
            self._initial_tier_cache[successful_key] = (tier, time.time())
            spider.logger.info(f"LLM selected initial tier: {tier} for {site}:{page_type}")
            return tier
        except Exception as e:
            spider.logger.warning(f"Tier selection failed: {e}")
            return get_site_tier(site, page_pattern)

    def _record_attempt_history(
        self, url: str, strategy: CrawlStrategy, blocked: bool, block_type: str
    ) -> None:
        history = self._attempt_history.setdefault(url, [])
        history.append(
            {
                "strategy": {
                    "proxy": strategy.proxy.value,
                    "render": strategy.render.value,
                    "delay_after": list(strategy.delay_after),
                    "use_cookies": strategy.use_cookies,
                    "change_ua": strategy.change_ua,
                    "use_human_scroll": strategy.use_human_scroll,
                },
                "block_type": block_type,
                "blocked": blocked,
            }
        )
        if len(history) > 20:
            history[:] = history[-20:]

    def _select_strategy_after_block(
        self, task_info, block_type, response_snippet, history, spider
    ):
        selector = self._get_strategy_selector()
        if not selector:
            return None

        try:
            import json

            result = selector(
                site=task_info.get("site", ""),
                page_pattern=task_info.get("page_pattern", ""),
                block_type=block_type,
                response_snippet=response_snippet[:500],
                attempt_history=json.dumps(history[-5:]) if history else "[]",
            )
            spider.logger.info(f"DSPy strategy: {result.recommended_strategy}")
            return result.recommended_strategy
        except Exception as e:
            spider.logger.warning(f"DSPy strategy failed: {e}")
            return None

    def _get_start_tier(self, request: Request, spider: Spider) -> int:
        site = request.meta.get("site", "")
        if not site:
            url = request.url
            for s in ["amazon", "walmart", "target", "ebay", "bestbuy", "costco"]:
                if s in url:
                    site = s
                    break
        pattern = request.meta.get("page_pattern", PagePattern.UNKNOWN)
        return self._select_initial_tier(site, pattern, spider)

    def _get_strategies(self, start_tier: int) -> list[CrawlStrategy]:
        return CrawlStrategy.get_tier_strategies(start_tier, end_tier=9)

    def _is_render_needed(self, strategy: CrawlStrategy) -> bool:
        return strategy.render in (
            RenderType.CAMOUFOX,
            RenderType.CLOAKBROWSER,
            RenderType.CLOUDSCRAPER,
            RenderType.PLAYWRIGHT,
            RenderType.SELENIUMBASE,
            RenderType.CLOUDERA,
            RenderType.KAMELEO,
        )

    def _create_task(self, request: Request) -> CrawlTask:
        site = request.meta.get("site", "")
        for s in ["amazon", "walmart", "target", "ebay", "bestbuy", "costco"]:
            if s in request.url:
                site = s
                break
        task = CrawlTask(url=request.url, site=site)
        task.page_pattern = PagePattern.UNKNOWN
        return task

    def _record_trace(
        self,
        request: Request,
        response: Response,
        strategy: CrawlStrategy,
        blocked: bool,
        block_type: str,
        latency_ms: float,
    ):
        import time

        task = self._create_task(request)
        waf = self._detect_waf(response) if isinstance(response, HtmlResponse) else ""
        fp = request.meta.get("fingerprint", {})

        if not blocked:
            site = task.site
            page_pattern = task.page_pattern
            page_type = page_pattern.value if page_pattern else "unknown"
            tier = strategy.tier if hasattr(strategy, "tier") else 1
            key = self._initial_tier_cache_key(site, page_type)
            self._successful_tier_cache[key] = (tier, time.time())

        try:
            self._trace_store.record(
                task=task,
                strategy=strategy,
                block_type=block_type,
                response_snippet=response.text[:2000] if hasattr(response, "text") else "",
                success=not blocked,
                latency_ms=latency_ms,
                attempt_index=self._attempt_index,
                llm_decision=False,
                status_code=response.status if hasattr(response, "status") else 0,
                response_headers=dict(response.headers) if hasattr(response, "headers") else {},
                full_html_size=len(response.body) if hasattr(response, "body") else 0,
                ip_rotation_count=self._ip_rotation_count,
                fingerprint_profile=fp,
                waf_detected=waf,
            )
        except Exception:
            pass

    def process_start_requests(self, start_requests, spider: Spider):
        for request in start_requests:
            if not request.meta.get("fingerprint"):
                fp = self._generate_fingerprint(spider)
                if fp:
                    request.meta["fingerprint"] = fp
                    request.meta["dynamic_profile"] = fp
            yield request

    def process_request(self, request: Request, response=None):
        crawler_spider = (
            getattr(self, "_crawler", None).spider
            if hasattr(self, "_crawler") and self._crawler
            else None
        )
        spider = request.meta.get("spider") or crawler_spider
        if not request.meta.get("tier_strategies"):
            if not request.meta.get("fingerprint"):
                fp = (
                    self._generate_fingerprint(spider)
                    if spider
                    else self._get_default_fingerprint()
                )
                if fp:
                    request.meta["fingerprint"] = fp
                    request.meta["dynamic_profile"] = fp

            start_tier = self._get_start_tier(request, spider)
            strategies = self._get_strategies(start_tier)
            request.meta["tier_index"] = 0
            request.meta["tier_strategies"] = strategies
            request.meta["tier_start"] = start_tier

        strategies = request.meta.get("tier_strategies", [])
        current_index = request.meta.get("tier_index", 0)
        if current_index >= len(strategies):
            return None

        strategy = strategies[current_index]
        request.meta["current_strategy"] = strategy
        request.meta["tier_index"] = current_index

        if self._is_render_needed(strategy):
            request.meta["render_js"] = True
            request.meta["render_wait_time"] = strategy.delay_after[1]

        if (
            spider
            and hasattr(spider, "crawler")
            and spider.crawler
            and hasattr(spider.crawler, "stats")
        ):
            request.meta["start_time"] = spider.crawler.stats.get_value("start_time", 0)

        if spider and hasattr(spider, "logger"):
            spider.logger.info(
                f"[REQUEST START] url={request.url} "
                f"tier={strategy.tier} "
                f"render={strategy.render.value} "
                f"proxy={strategy.proxy.value} "
                f"delay={strategy.delay_after} "
                f"change_ua={strategy.change_ua} "
                f"use_cookies={strategy.use_cookies} "
                f"human_scroll={strategy.use_human_scroll}"
            )

        return None

    def process_response(self, request: Request, response: Response):
        strategies = request.meta.get("tier_strategies", [])
        if not strategies:
            return response

        strategy = request.meta.get("current_strategy")
        if not strategy:
            return response

        crawler_spider = (
            getattr(self, "_crawler", None).spider
            if hasattr(self, "_crawler") and self._crawler
            else None
        )
        spider = request.meta.get("spider") or crawler_spider
        blocked, block_type = self._detect_block(response)
        latency_ms = 0
        if (
            spider
            and hasattr(spider, "crawler")
            and spider.crawler
            and hasattr(spider.crawler, "stats")
        ):
            latency_ms = (spider.crawler.stats.get_value("elapsed_time_secs", 0) or 0) * 1000
        status_code = response.status if hasattr(response, "status") else 0

        if spider and hasattr(spider, "logger"):
            spider.logger.info(
                f"[RESPONSE] url={request.url} "
                f"status={status_code} "
                f"blocked={blocked} "
                f"block_type={block_type} "
                f"latency_ms={latency_ms:.0f} "
                f"size={len(response.body) if hasattr(response, 'body') else 0}"
            )

        self._record_trace(request, response, strategy, blocked, block_type, latency_ms)
        self._record_attempt_history(request.url, strategy, blocked, block_type)

        if not blocked:
            if spider and hasattr(spider, "logger"):
                spider.logger.info(f"[SUCCESS] url={request.url} tier={strategy.tier}")
            return response

        current_index = request.meta.get("tier_index", 0)

        if current_index + 1 >= len(strategies):
            if spider and hasattr(spider, "logger"):
                spider.logger.warning(
                    f"[ALL TIERS EXHAUSTED] url={request.url} "
                    f"tiers_tried={current_index + 1} "
                    f"final_block={block_type}"
                )
            return response

        task_info = {
            "site": request.meta.get("site", ""),
            "page_pattern": request.meta.get("page_pattern", ""),
            "url": request.url,
        }

        history = self._attempt_history.get(request.url, [])
        llm_strategy = self._select_strategy_after_block(
            task_info, block_type, response.text[:500], history, spider
        )

        if llm_strategy and isinstance(llm_strategy, dict):
            next_strategy = CrawlStrategy(
                proxy=ProxyType(llm_strategy.get("proxy", "thordata_dedicated")),
                render=RenderType(llm_strategy.get("render", "playwright")),
                delay_after=tuple(llm_strategy.get("delay_after", [3, 8])),
                use_cookies=llm_strategy.get("use_cookies", True),
                change_ua=llm_strategy.get("change_ua", True),
                use_human_scroll=llm_strategy.get("use_human_scroll", True),
            )
            if spider and hasattr(spider, "logger"):
                spider.logger.info(
                    f"[BLOCK] url={request.url} block_type={block_type} LLM_strategy={llm_strategy}"
                )
        else:
            next_index = current_index + 1
            next_strategy = strategies[next_index]
            if spider and hasattr(spider, "logger"):
                spider.logger.info(
                    f"[BLOCK] url={request.url} "
                    f"block_type={block_type} "
                    f"escalating_tier={next_index + 1} "
                    f"render={next_strategy.render.value} "
                    f"proxy={next_strategy.proxy.value}"
                )

        self._attempt_index = current_index + 1
        request.meta["tier_index"] = current_index + 1
        request.meta["current_strategy"] = next_strategy
        request.meta["render_js"] = self._is_render_needed(next_strategy)

        if spider and hasattr(spider, "logger"):
            spider.logger.info(
                f"[RETRY] url={request.url} "
                f"attempt={current_index + 2} "
                f"new_tier={next_strategy.tier if hasattr(next_strategy, 'tier') else current_index + 2} "
                f"new_render={next_strategy.render.value} "
                f"new_proxy={next_strategy.proxy.value}"
            )

        retry_request = request.copy()
        retry_request.dont_filter = True
        return retry_request

    def process_exception(self, request: Request, exception):
        strategies = request.meta.get("tier_strategies", [])
        if not strategies:
            return None

        if request.meta.get("exception_processed"):
            return None
        request.meta["exception_processed"] = True

        crawler_spider = (
            getattr(self, "_crawler", None).spider
            if hasattr(self, "_crawler") and self._crawler
            else None
        )
        spider = request.meta.get("spider") or crawler_spider
        strategy = request.meta.get("current_strategy")
        if strategy:
            task = self._create_task(request)
            self._trace_store.record(
                task=task,
                strategy=strategy,
                block_type="exception",
                response_snippet=str(exception)[:500],
                success=False,
                latency_ms=0,
                attempt_index=self._attempt_index,
                llm_decision=False,
            )

        current_index = request.meta.get("tier_index", 0)

        if current_index + 1 >= len(strategies):
            if spider and hasattr(spider, "logger"):
                spider.logger.error(f"All tiers exhausted due to exception: {exception}")
            return None

        next_index = current_index + 1
        next_strategy = strategies[next_index]

        self._attempt_index = current_index + 1
        request.meta["tier_index"] = next_index
        request.meta["current_strategy"] = next_strategy
        request.meta["render_js"] = self._is_render_needed(next_strategy)

        tier_start = request.meta.get("tier_start", 1)
        if spider and hasattr(spider, "logger"):
            spider.logger.info(
                f"Tier upgrade: {tier_start + current_index} -> {tier_start + next_index} for {request.url}"
            )

        retry_request = request.copy()
        retry_request.dont_filter = True
        if "exception_processed" in retry_request.meta:
            del retry_request.meta["exception_processed"]
        return retry_request

    def _detect_block(self, response: Response) -> tuple[bool, str]:
        if response.status in (403, 429, 451):
            return True, f"http_{response.status}"
        if response.status >= 500:
            return True, "http_5xx"
        if response.status == 999:
            return True, "http_999"
        if isinstance(response, HtmlResponse):
            blocked, block_type = self.detector.detect(
                response.status, response.text, len(response.text)
            )
            return blocked, block_type
        return False, ""


class RenderMiddleware:
    RENDER_PRIORITY = 600

    def __init__(self):
        pass

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    async def process_request(self, request: Request, response=None):
        if not request.meta.get("render_js"):
            return None

        render_type = request.meta.get("current_strategy")
        if render_type:
            if isinstance(render_type, CrawlStrategy):
                render_type = render_type.render
            elif not isinstance(render_type, RenderType):
                return None
        else:
            return None

        if not render_type or render_type == RenderType.NONE:
            return None

        import asyncio

        spider = request.meta.get("spider")
        wait_selector = request.meta.get("wait_selector")
        render_timeout = 60.0

        class RenderTimeoutException(Exception):
            pass

        try:
            html, status = await asyncio.wait_for(
                asyncio.to_thread(self._sync_render, request, spider, wait_selector),
                timeout=render_timeout,
            )
        except asyncio.TimeoutError:
            if spider and hasattr(spider, "logger"):
                spider.logger.warning(f"Render timeout for {request.url} after {render_timeout}s")
            raise RenderTimeoutException(f"Render timeout for {request.url}") from None
        except Exception as e:
            if spider and hasattr(spider, "logger"):
                spider.logger.error(f"Render error for {request.url}: {e}")
            raise RenderTimeoutException(f"Render error for {request.url}: {e}") from None

        if html and status:
            return HtmlResponse(
                url=request.url,
                body=html.encode("utf-8"),
                encoding="utf-8",
                request=request,
                status=status,
            )
        return HtmlResponse(
            url=request.url,
            body=html.encode("utf-8") if html else b"",
            encoding="utf-8",
            request=request,
            status=500,
        )

    def _sync_render(
        self, request: Request, spider: Spider, wait_selector: str = None
    ) -> tuple[str, int]:
        import time

        strategy = request.meta.get("current_strategy")
        if not strategy or not isinstance(strategy, CrawlStrategy):
            return "", 0

        render_type = strategy.render
        proxy = request.meta.get("proxy")
        wait_time = request.meta.get("render_wait_time", 5.0)
        human_scroll = strategy.use_human_scroll
        dynamic_profile = request.meta.get("dynamic_profile", {})

        if render_type == RenderType.CAMOUFOX:
            from ai_crawler.browser.camoufox_wrapper import CamoufoxWrapper

            wrapper = CamoufoxWrapper(
                proxy=proxy,
                headless=True,
                wait_time=wait_time,
                human_scroll=human_scroll,
                dynamic_profile=dynamic_profile,
            )
            return wrapper.fetch(request.url)

        elif render_type == RenderType.CLOAKBROWSER:
            from ai_crawler.browser.cloakbrowser_wrapper import CloakBrowserWrapper

            wrapper = CloakBrowserWrapper(
                proxy=proxy,
                headless=True,
                wait_time=wait_time,
                human_scroll=human_scroll,
                dynamic_profile=dynamic_profile,
            )
            return wrapper.fetch(request.url)

        elif render_type == RenderType.PLAYWRIGHT:
            from ai_crawler.browser.playwright_wrapper import PlaywrightWrapper

            wrapper = PlaywrightWrapper(
                proxy=proxy,
                headless=True,
                wait_time=wait_time,
                human_scroll=human_scroll,
                dynamic_profile=dynamic_profile,
            )
            return wrapper.fetch(request.url)

        elif render_type == RenderType.SELENIUMBASE:
            from ai_crawler.browser.seleniumbase_wrapper import SeleniumBaseWrapper

            wrapper = SeleniumBaseWrapper(
                proxy=proxy,
                headless=True,
                wait_time=wait_time,
                human_scroll=human_scroll,
                dynamic_profile=dynamic_profile,
            )
            return wrapper.fetch(request.url)

        elif render_type == RenderType.CLOUDERA:
            from ai_crawler.browser.undetected_chromedriver_wrapper import (
                UndetectedChromedriverWrapper,
            )

            wrapper = UndetectedChromedriverWrapper(
                proxy=proxy,
                headless=True,
                wait_time=wait_time,
                human_scroll=human_scroll,
                dynamic_profile=dynamic_profile,
            )
            return wrapper.fetch(request.url)

        elif render_type == RenderType.KAMELEO:
            from ai_crawler.browser.kameleo_wrapper import KameleoWrapper

            wrapper = KameleoWrapper(proxy=proxy, headless=True, wait_time=wait_time)
            return wrapper.fetch(request.url)

        elif render_type == RenderType.CLOUDSCRAPER:
            from ai_crawler.browser.cloudscraper_wrapper import CloudScraperWrapper

            wrapper = CloudScraperWrapper(proxy=proxy)
            return wrapper.fetch(request.url)

        return "", 0

    def process_response(self, request: Request, response: Response):
        return response
