from __future__ import annotations

import structlog

from ai_crawler.core.extraction import build_axtree_semantic_confirmation
from ai_crawler.core.runtime.handler import BlockDetectionContext, BlockType
from ai_crawler.core.runtime.results import CrawlResult


log = structlog.get_logger()


class TaskProcessor:
    def __init__(
        self,
        queue,
        planner,
        execution,
        captcha,
        fetcher,
        anti_bot,
        trace_recorder,
        failure_handler,
        extraction,
        captcha_solver=None,
    ):
        self.queue = queue
        self.planner = planner
        self.execution = execution
        self.captcha = captcha
        self.fetcher = fetcher
        self.anti_bot = anti_bot
        self.trace_recorder = trace_recorder
        self.failure_handler = failure_handler
        self.extraction = extraction
        self.captcha_solver = captcha_solver

    def process(self, task):
        attempt = None
        memory = self.queue.site_memory.get(task.site)
        prepared_memory = self.planner.prepare(task, memory)
        if prepared_memory is not None and task.site not in self.queue.site_memory:
            self.queue.site_memory[task.site] = prepared_memory

        strategy = self.planner.resolve(task)
        if not strategy:
            self.queue.on_failure(task, BlockType.UNKNOWN, "All strategies exhausted")
            return CrawlResult(
                task=task,
                strategy=task.strategies[-1],
                success=False,
                error="All strategies exhausted",
            )

        attempt_index = task.current_index
        try:
            attempt = self.execution.execute(task, strategy)
            trace_kwargs = self.trace_recorder.failure_trace_kwargs(
                task, strategy, attempt, attempt_index
            )

            if attempt.blocked:
                if attempt.block_type == BlockType.CAPTCHA and self.captcha_solver:
                    log.info("captcha_detected", url=task.url)
                    captcha_solved = self.captcha.solve(task, attempt.html)
                    if captcha_solved:
                        self.fetcher.release_page(attempt.page)
                        html, status_code, page = self.fetcher.fetch_with_strategy(task, strategy)
                        blocked, block_type = self.anti_bot.is_blocked(
                            status_code,
                            html,
                            BlockDetectionContext(
                                site=task.site,
                                page_pattern=task.page_pattern.value,
                                goal=str(task.metadata.get("goal", "") or ""),
                                semantic_confirmation=build_axtree_semantic_confirmation(
                                    page, task.url, task.page_pattern.value
                                )
                                if page is not None
                                else None,
                            ),
                        )
                        if not blocked:
                            attempt.html = html
                            attempt.status_code = status_code
                            attempt.page = page
                            attempt.blocked = False
                            attempt.block_type = block_type
                            attempt.response_headers = {}
                            attempt.waf_detected = ""
                            attempt.block_reason = ""
                            trace_kwargs = self.trace_recorder.failure_trace_kwargs(
                                task, strategy, attempt, attempt_index
                            )
                        else:
                            attempt.html = html
                            attempt.status_code = status_code
                            attempt.page = page
                            attempt.blocked = True
                            attempt.block_type = block_type
                            trace_kwargs = self.trace_recorder.failure_trace_kwargs(
                                task, strategy, attempt, attempt_index
                            )
                            self.failure_handler.handle_blocked(
                                task, attempt, trace_kwargs, attempt_index
                            )
                            return CrawlResult(
                                task=task,
                                strategy=strategy,
                                success=False,
                                html=attempt.html,
                                block_type=attempt.block_type,
                                extraction_metadata={},
                                anti_bot_fingerprint=attempt.anti_bot_fingerprint,
                            )

                if attempt.blocked:
                    self.failure_handler.handle_blocked(task, attempt, trace_kwargs, attempt_index)
                    return CrawlResult(
                        task=task,
                        strategy=strategy,
                        success=False,
                        html=attempt.html,
                        block_type=attempt.block_type,
                        extraction_metadata={},
                        anti_bot_fingerprint=attempt.anti_bot_fingerprint,
                    )

            extraction_decision = self.extraction.extract(
                task, strategy, attempt.page, attempt.html
            )
            if extraction_decision.should_retry:
                self.failure_handler.handle_extraction_retry(
                    task, attempt.html, extraction_decision.retry_reason or "empty_content"
                )
                return CrawlResult(
                    task=task,
                    strategy=strategy,
                    success=False,
                    html=attempt.html,
                    block_type=extraction_decision.retry_reason or "empty_content",
                    products=[],
                    extraction_strategy=extraction_decision.strategy_name,
                    extraction_method=extraction_decision.method,
                    extraction_metadata=extraction_decision.metadata or {},
                    anti_bot_fingerprint=attempt.anti_bot_fingerprint,
                )

            if not extraction_decision.products:
                self.failure_handler.handle_extraction_retry(task, attempt.html, "empty_content")
                return CrawlResult(
                    task=task,
                    strategy=strategy,
                    success=False,
                    html=attempt.html,
                    block_type="empty_content",
                    products=[],
                    extraction_strategy=extraction_decision.strategy_name,
                    extraction_method=extraction_decision.method,
                    extraction_metadata=extraction_decision.metadata or {},
                    anti_bot_fingerprint=attempt.anti_bot_fingerprint,
                )

            self.trace_recorder.record_success(
                task,
                strategy,
                attempt,
                attempt_index,
                extraction_strategy=extraction_decision.strategy_name,
                extraction_method=extraction_decision.method,
                extraction_metadata=extraction_decision.metadata or {},
            )
            self.queue.on_success(task, strategy)

            return CrawlResult(
                task=task,
                strategy=strategy,
                success=True,
                html=attempt.html,
                products=extraction_decision.products,
                extraction_strategy=extraction_decision.strategy_name,
                extraction_method=extraction_decision.method,
                extraction_metadata=extraction_decision.metadata or {},
                anti_bot_fingerprint=attempt.anti_bot_fingerprint,
            )
        finally:
            if attempt is not None:
                self.fetcher.release_page(attempt.page)
