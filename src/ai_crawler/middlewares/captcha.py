from scrapy import Spider, Request
from scrapy.http import Response
from scrapy.http import HtmlResponse

from ai_crawler.captcha import CaptchaDetector


class CaptchaMiddleware:
    def __init__(self, api_key: str = None):
        self._detector = CaptchaDetector(api_key)

    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        api_key = settings.get("CAPTCHA_API_KEY") or None
        return cls(api_key=api_key)

    def process_response(self, request: Request, response: Response, spider: Spider):
        if not isinstance(response, HtmlResponse):
            return response

        detected, captcha_type, site_key, action = self._detector.detect(
            response.text, response.status
        )
        if not detected:
            return response

        spider.logger.info(f"CAPTCHA detected: {captcha_type} on {request.url}")

        try:
            solution = self._detector.solve(captcha_type, site_key, request.url, action)
            spider.logger.info(f"CAPTCHA solved for {request.url}")

            new_request = request.copy()
            new_request.meta["captcha_solution"] = solution
            new_request.dont_filter = True
            return new_request

        except Exception as e:
            spider.logger.error(f"CAPTCHA solving failed: {e}")
            return response

    def process_request(self, request: Request, spider: Spider):
        return None

    def process_exception(self, request: Request, exception, spider: Spider):
        return None
