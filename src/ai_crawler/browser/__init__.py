from ai_crawler.browser.base import BaseWrapper, BrowserConfig
from ai_crawler.browser.human_mouse import (
    HumanMouseController,
    generate_human_curve,
    UnifiedHumanBehavior,
    MouseAdapter,
    PlaywrightMouseAdapter,
    SeleniumMouseAdapter,
    CloakBrowserMouseAdapter,
    LLMHumanBehavior,
    CachedLLMHumanBehavior,
)

try:
    from ai_crawler.browser.camoufox_wrapper import CamoufoxWrapper, FingerprintConfig, async_launch
    from ai_crawler.browser.cloakbrowser_wrapper import (
        CloakBrowserWrapper,
        async_fetch as async_cloak_fetch,
    )
    from ai_crawler.browser.cloudscraper_wrapper import CloudScraperWrapper
    from ai_crawler.browser.curl_wrapper import CurlWrapper
    from ai_crawler.browser.kameleo_wrapper import KameleoWrapper
    from ai_crawler.browser.playwright_wrapper import PlaywrightWrapper
    from ai_crawler.browser.seleniumbase_wrapper import SeleniumBaseWrapper, async_fetch
    from ai_crawler.browser.undetected_chromedriver_wrapper import UndetectedChromedriverWrapper
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
    "BaseWrapper",
    "BrowserConfig",
    "CamoufoxWrapper",
    "CloakBrowserWrapper",
    "CloudScraperWrapper",
    "CurlWrapper",
    "FingerprintConfig",
    "HumanMouseController",
    "generate_human_curve",
    "UnifiedHumanBehavior",
    "MouseAdapter",
    "PlaywrightMouseAdapter",
    "SeleniumMouseAdapter",
    "CloakBrowserMouseAdapter",
    "LLMHumanBehavior",
    "async_launch",
    "SeleniumBaseWrapper",
    "async_fetch",
    "async_cloak_fetch",
    "KameleoWrapper",
    "PlaywrightWrapper",
    "UndetectedChromedriverWrapper",
]
