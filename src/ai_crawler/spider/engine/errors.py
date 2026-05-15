from typing import Optional


class CrawlerError(Exception):
    pass


class FetchError(CrawlerError):
    pass


class BlockDetectedError(FetchError):
    def __init__(self, block_type: str, message: str = ""):
        self.block_type = block_type
        super().__init__(message or block_type)


class ProxyError(CrawlerError):
    pass


class ProxyAuthError(ProxyError):
    pass


class BrowserError(CrawlerError):
    pass


class BrowserLaunchError(BrowserError):
    pass


class ExtractionError(CrawlerError):
    pass


class CaptchaError(CrawlerError):
    pass


class CaptchaSolveError(CaptchaError):
    pass
