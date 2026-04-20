from __future__ import annotations

import structlog

from ai_crawler.core.strategy import CrawlTask


log = structlog.get_logger()


class CaptchaService:
    def __init__(self, solver=None):
        self.solver = solver

    def solve(self, task: CrawlTask, html: str) -> bool:
        if not self.solver:
            return False

        from ai_crawler.integrations.captcha import CaptchaDetector

        detector = CaptchaDetector()
        detector._solver = self.solver

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
        except Exception as exc:
            log.error("captcha_solve_failed", site=task.site, error=str(exc))
            return False
