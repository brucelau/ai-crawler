from scrapy import Spider, Request
from scrapy.http import Response
from scrapy.http import HtmlResponse

from ai_crawler.core.types import CrawlTask, CrawlStrategy, SiteMemory, StrategyAttempt
from ai_crawler.core.engine.queue import Queue


class CrawlQueueMiddleware:
    def __init__(self):
        self._queue = CrawlQueue()

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def process_request(self, request: Request):
        url = request.url
        history = self._queue.site_memory.get(request.meta.get("site", ""))
        if history:
            successful = history.successful_strategies
            if successful:
                best = successful[0]
                spider = request.meta.get("spider")
                if spider and hasattr(spider, "logger"):
                    spider.logger.debug(
                        f"Using remembered strategy for {request.meta.get('site')}: "
                        f"render={best.render.value}"
                    )
        return None

    def process_response(self, request: Request, response: Response):
        strategy = request.meta.get("current_strategy")
        if not strategy:
            return response

        site = request.meta.get("site", "")
        url = request.url
        task = CrawlTask(url=url, site=site)

        blocked, _ = self._detect_block(response)
        spider = request.meta.get("spider")
        if spider and hasattr(spider, "logger"):
            if blocked:
                spider.logger.info(f"Failure recorded for {site}: {strategy.render.value}")
            else:
                spider.logger.info(f"Success recorded for {site}: {strategy.render.value}")

        return response

    def process_exception(self, request: Request, exception):
        return None

    def _detect_block(self, response: Response) -> tuple[bool, str]:
        if response.status in (403, 429, 451):
            return True, f"http_{response.status}"
        if response.status >= 500:
            return True, "http_5xx"
        if isinstance(response, HtmlResponse) and len(response.text) < 1000:
            return True, "empty_response"
        return False, ""

    def get_queue(self) -> Queue:
        return self._queue

    def get_site_stats(self) -> dict:
        stats = {}
        for site, memory in self._queue.site_memory.items():
            stats[site] = {
                "successful_strategies": len(memory.successful_strategies),
                "attempt_count": len(memory.attempt_log),
            }
        return stats


class SiteMemoryMiddleware:
    def __init__(self):
        self._memory = {}

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def process_response(self, request: Request, response: Response):
        site = request.meta.get("site", "")
        if not site:
            return response

        strategy = request.meta.get("current_strategy")
        if not strategy:
            return response

        memory = self._memory.setdefault(site, SiteMemory(site=site))

        blocked, block_type = self._detect_block(response)
        if blocked:
            attempt = StrategyAttempt(
                task_id=request.meta.get("task_id", ""),
                url=request.url,
                site=site,
                strategy=strategy,
                block_type=block_type,
                response_snippet=response.text[:500] if hasattr(response, "text") else "",
                success=False,
            )
            memory.attempt_log.append(attempt)
        else:
            memory.record_success(strategy)

        return response

    def _detect_block(self, response: Response) -> tuple[bool, str]:
        if response.status in (403, 429, 451):
            return True, f"http_{response.status}"
        if response.status >= 500:
            return True, "http_5xx"
        if isinstance(response, HtmlResponse) and len(response.text) < 1000:
            return True, "empty_response"
        return False, ""

    def get_memory(self, site: str) -> SiteMemory:
        return self._memory.get(site)

    def get_all_memory(self) -> dict:
        return self._memory
