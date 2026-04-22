from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import structlog

from ai_crawler import run_crawl
from ai_crawler.api.crawler import CrawlerConfig

log = structlog.get_logger()


class CrawlJob:
    def __init__(self, name: str, site: str, query: str, pages: int = 3, enabled: bool = True):
        self.name = name
        self.site = site
        self.query = query
        self.pages = pages
        self.enabled = enabled


class Scheduler:
    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.scheduler = AsyncIOScheduler()
        self._jobs: dict[str, CrawlJob] = {}

    def add_cron_job(
        self,
        job_id: str,
        name: str,
        site: str,
        query: str,
        pages: int = 3,
        hour: int = 2,
        minute: int = 0,
    ) -> None:
        job = CrawlJob(name=name, site=site, query=query, pages=pages)
        self._jobs[job_id] = job

        async def _run():
            if not job.enabled:
                return
            log.info("job_started", job=job_id, name=job.name)
            try:
                run_crawl(
                    sites=[job.site],
                    query=job.query,
                    pages=job.pages,
                    proxy_username=self.config.thordata_username,
                    proxy_password=self.config.thordata_password,
                    captcha_api_key=self.config.captcha_api_key,
                )
            except Exception as e:
                log.error("job_failed", job=job_id, name=job.name, error=str(e))

        self.scheduler.add_job(
            _run,
            trigger=CronTrigger(hour=hour, minute=minute),
            id=job_id,
            name=name,
            replace_existing=True,
        )

    def add_interval_job(
        self,
        job_id: str,
        name: str,
        site: str,
        query: str,
        pages: int = 3,
        hours: int = 6,
    ) -> None:
        job = CrawlJob(name=name, site=site, query=query, pages=pages)
        self._jobs[job_id] = job

        async def _run():
            if not job.enabled:
                return
            log.info("job_started", job=job_id, name=job.name)
            try:
                run_crawl(
                    sites=[job.site],
                    query=job.query,
                    pages=job.pages,
                    proxy_username=self.config.thordata_username,
                    proxy_password=self.config.thordata_password,
                    captcha_api_key=self.config.captcha_api_key,
                )
            except Exception as e:
                log.error("job_failed", job=job_id, name=job.name, error=str(e))

        self.scheduler.add_job(
            _run,
            trigger=IntervalTrigger(hours=hours),
            id=job_id,
            name=name,
            replace_existing=True,
        )

    def start(self) -> None:
        self.scheduler.start()
        log.info("scheduler_started", jobs=len(self._jobs))

    def stop(self) -> None:
        self.scheduler.shutdown(wait=False)
        log.info("scheduler_stopped")
