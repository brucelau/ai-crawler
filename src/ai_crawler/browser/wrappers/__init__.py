try:
    from ai_crawler.browser.wrappers.camoufox import CamoufoxWrapper, FingerprintConfig, async_launch
    from ai_crawler.browser.wrappers.cloakbrowser import CloakBrowserWrapper, async_fetch as async_cloak_fetch
    from ai_crawler.browser.wrappers.cloudscraper import CloudScraperWrapper
    from ai_crawler.browser.wrappers.curl import CurlWrapper
    from ai_crawler.browser.wrappers.kameleo import KameleoWrapper
    from ai_crawler.browser.wrappers.playwright import PlaywrightWrapper
    from ai_crawler.browser.wrappers.seleniumbase import SeleniumBaseWrapper, async_fetch
    from ai_crawler.browser.wrappers.undetected_chromedriver import UndetectedChromedriverWrapper
except ModuleNotFoundError:
    CamoufoxWrapper = None
    FingerprintConfig = None
    async_launch = None
    CloakBrowserWrapper = None
    async_cloak_fetch = None
    CloudScraperWrapper = None
    CurlWrapper = None
    KameleoWrapper = None
    PlaywrightWrapper = None
    SeleniumBaseWrapper = None
    async_fetch = None
    UndetectedChromedriverWrapper = None


__all__ = [
    "CamoufoxWrapper",
    "CloakBrowserWrapper",
    "CloudScraperWrapper",
    "CurlWrapper",
    "FingerprintConfig",
    "async_launch",
    "async_cloak_fetch",
    "SeleniumBaseWrapper",
    "async_fetch",
    "KameleoWrapper",
    "PlaywrightWrapper",
    "UndetectedChromedriverWrapper",
]