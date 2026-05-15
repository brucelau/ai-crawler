from dataclasses import dataclass


RENDER_COST = {
    "none": 1,
    "cloudscraper": 2,
    "lightpanda": 3,
    "playwright": 4,
    "camoufox": 5,
    "cloudera": 6,
    "seleniumbase": 7,
    "cloakbrowser": 8,
    "kameleo": 9,
}


@dataclass(frozen=True)
class BrowserConfig:
    CAMOUFOX_POOL_CAP: int = 2
    UC_POOL_CAP: int = 2
    CAMOUFOX_MAX_LEASES: int = 5
    UC_MAX_LEASES: int = 2
    CAMOUFOX_IDLE_TTL: int = 300
    UC_IDLE_TTL: int = 120
    DEFAULT_WAIT_TIME: float = 2.0
    PAGE_LOAD_TIMEOUT: int = 30
    REQUEST_TIMEOUT: int = 30
    MOUSE_JITTER_STD: float = 2.5
    SCROLL_STEP_MIN: int = 100
    SCROLL_STEP_MAX: int = 800
    SCROLL_START_Y: int = 0
    SCROLL_END_Y: int = 1500
    DEFAULT_SCREEN_WIDTH: int = 1920
    DEFAULT_SCREEN_HEIGHT: int = 1080
    DEFAULT_DEVICE_PIXEL_RATIO: float = 2.0
    DEFAULT_DOWNLINK: int = 10
    DEFAULT_RTT: int = 50


@dataclass(frozen=True)
class RetryConfig:
    MAX_IP_RETRIES: int = 3
    MAX_CRAWL_ATTEMPTS: int = 5
    MAX_TRACE_FILES: int = 20
    CAPTCHA_POLLING_INTERVAL: int = 5
    CAPTCHA_TIMEOUT: int = 120


@dataclass(frozen=True)
class ConcurrencyConfig:
    INITIAL_WORKERS: int = 3
    MIN_WORKERS: int = 1
    MAX_WORKERS: int = 10
    FAILURE_THRESHOLD: float = 0.5


@dataclass(frozen=True)
class ExtractionConfig:
    MIN_TITLE_LENGTH: int = 5
    MIN_PRODUCTS_SUCCESS: int = 2
    GOOD_PRODUCTS_THRESHOLD: int = 20
    SEARCH_CONFIDENCE_THRESHOLD: float = 0.65
    SEARCH_ENTITY_COUNT_MIN: int = 2
    REVIEW_SIGNAL_MIN_HITS: int = 2


@dataclass(frozen=True)
class BlockDetectionConfig:
    BOT_DETECTION_REQUIRED_HITS: int = 2
    WAF_DETECTION_REQUIRED_HITS: int = 2
    LATENCY_SLOW_MS: int = 10000
    LATENCY_FAST_MS: int = 100
    HTML_SIZE_MIN: int = 500
    HTML_SIZE_MAX: int = 500000


@dataclass(frozen=True)
class BrowserSelectorConfig:
    RENDER_COST: dict = None
    CAMOUFOX_SEARCH_BONUS: float = 12.0
    CAMOUFOX_SEARCH_SUCCESS_BONUS: float = 8.0
    CLOAKBROWSER_SEARCH_BONUS: float = 14.0
    CLOAKBROWSER_SEARCH_SUCCESS_BONUS: float = 10.0
    CLOAKBROWSER_AMAZON_TARGET_BONUS: float = 8.0
    SELENIUMBASE_SEARCH_BONUS: float = 6.0
    SELENIUMBASE_SEARCH_SUCCESS_BONUS: float = 4.0
    CLOUDERA_SEARCH_ALLOWLIST_BONUS: float = 35.0
    CLOUDERA_NON_ALLOWLIST_PENALTY: float = 10.0

    def __post_init__(self):
        if self.RENDER_COST is None:
            object.__setattr__(self, 'RENDER_COST', RENDER_COST)


browser_config = BrowserConfig()
retry_config = RetryConfig()
concurrency_config = ConcurrencyConfig()
extraction_config = ExtractionConfig()
block_detection_config = BlockDetectionConfig()
browser_selector_config = BrowserSelectorConfig()
