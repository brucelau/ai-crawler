"""Configuration — env loading, settings singleton, and dataclass configs.

Merged from config/__init__.py + config/settings.py + config/crawler_config.py.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ═══════════════════════════════════════════════════════════════════
# Dataclass config objects (from config/crawler_config.py)
# ═══════════════════════════════════════════════════════════════════

RENDER_COST_MAP = {
    "none": 1,
    "cloudscraper": 2,
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
            object.__setattr__(self, 'RENDER_COST', RENDER_COST_MAP)


browser_config = BrowserConfig()
retry_config = RetryConfig()
concurrency_config = ConcurrencyConfig()
extraction_config = ExtractionConfig()
block_detection_config = BlockDetectionConfig()
browser_selector_config = BrowserSelectorConfig()


# ═══════════════════════════════════════════════════════════════════
# Settings (from config/settings.py)
# ═══════════════════════════════════════════════════════════════════

BOT_NAME = "ai_crawler"
SPIDER_MODULES = []
NEWSPIDER_MODULE = ""
EXTENSIONS = {}
DOWNLOADER_MIDDLEWARES = {}
SPIDER_MIDDLEWARES = {}
DOWNLOAD_DELAY = 5
RANDOMIZE_DOWNLOAD_DELAY = True
CONCURRENT_REQUESTS_PER_DOMAIN = 2
RETRY_TIMES = 0
RETRY_ENABLED = False
COOKIES_ENABLED = True
ITEM_PIPELINES = {}
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 3
AUTOTHROTTLE_MAX_DELAY = 60
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
FEEDS = {}
LOG_FILE = "logs/scrapy.log"
RENDER_ENGINE = "runtime"
TRACE_DIR = "traces"
OUTPUT_DIR = "output"
MAX_IP_RETRIES = 3
RUNTIME_CONCURRENCY = 1


# ═══════════════════════════════════════════════════════════════════
# Config singleton (from config/__init__.py)
# ═══════════════════════════════════════════════════════════════════

class Config:
    _instance: Optional["Config"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True

        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        self.OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o")

        self.TWO_CAPTCHA_API_KEY = os.getenv("2CAPTCHA_API_KEY", "")

        self.THORDATA_PROXY_HOST = os.getenv("THORDATA_PROXY_HOST", "pr.thordata.net")
        self.THORDATA_PROXY_PORT = int(os.getenv("THORDATA_PROXY_PORT", "9999"))
        self.THORDATA_RESIDENTIAL_USERNAME = os.getenv("THORDATA_RESIDENTIAL_USERNAME", "")
        self.THORDATA_RESIDENTIAL_PASSWORD = os.getenv("THORDATA_RESIDENTIAL_PASSWORD", "")
        self.THORDATA_MOBILE_USERNAME = os.getenv("THORDATA_MOBILE_USERNAME", "")
        self.THORDATA_MOBILE_PASSWORD = os.getenv("THORDATA_MOBILE_PASSWORD", "")
        self.THORDATA_COUNTRY = os.getenv("THORDATA_COUNTRY", "us")
        self.THORDATA_CITY = os.getenv("THORDATA_CITY", "")

        self.KAMELEO_API_URL = os.getenv("KAMELEO_API_URL", "http://localhost:5050")
        self.KAMELEO_API_KEY = os.getenv("KAMELEO_API_KEY", "")

        self.REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
        self.PAGE_LOAD_TIMEOUT = int(os.getenv("PAGE_LOAD_TIMEOUT", "30"))

        self.PROXY_DISABLED = os.getenv("PROXY_DISABLED", "false").lower() in (
            "true",
            "1",
            "yes",
        )

        self.LLM_HUMAN_BEHAVIOR_CACHE_TTL = float(os.getenv("LLM_HUMAN_BEHAVIOR_CACHE_TTL", "3600"))

        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_DIR = os.getenv("LOG_DIR", "logs")
        self.LOG_FILE = os.getenv("LOG_FILE", "crawler.log")

        self.DSPY_MODEL_DIR = os.getenv("DSPY_MODEL_DIR", "models")
        self.DSPY_TRAIN_INTERVAL = int(os.getenv("DSPY_TRAIN_INTERVAL", "3600"))
        self.DSPY_MIN_TRACES = int(os.getenv("DSPY_MIN_TRACES", "50"))
        self.DSPY_MIN_NEW_TRACES = int(os.getenv("DSPY_MIN_NEW_TRACES", "10"))

    def has_llm(self) -> bool:
        return bool(self.OPENAI_API_KEY)

    def has_thordata(self) -> bool:
        return bool(self.THORDATA_RESIDENTIAL_USERNAME and self.THORDATA_RESIDENTIAL_PASSWORD)

    def has_kameleo(self) -> bool:
        return bool(self.KAMELEO_API_KEY)


config = Config()


# ═══════════════════════════════════════════════════════════════════
# Logging setup (from config/__init__.py)
# ═══════════════════════════════════════════════════════════════════

def setup_logging(
    log_level: str = "INFO", log_dir: str = "logs", log_file: str = "crawler.log"
) -> None:
    """Configure logging to output to both console and file."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    log_file_path = log_path / log_file

    detailed_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    simple_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    file_handler.setFormatter(detailed_formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    console_handler.setFormatter(simple_formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    try:
        import structlog

        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.LogfmtRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    except ImportError:
        pass

    logging.info(f"Logging configured: level={log_level}, file={log_file_path}")


__all__ = [
    "config",
    "Config",
    "setup_logging",
    "browser_config",
    "retry_config",
    "concurrency_config",
    "extraction_config",
    "block_detection_config",
    "browser_selector_config",
    "BrowserConfig",
    "RetryConfig",
    "ConcurrencyConfig",
    "ExtractionConfig",
    "BlockDetectionConfig",
    "BrowserSelectorConfig",
    "BOT_NAME",
    "DOWNLOAD_DELAY",
    "RANDOMIZE_DOWNLOAD_DELAY",
    "CONCURRENT_REQUESTS_PER_DOMAIN",
    "RETRY_TIMES",
    "RETRY_ENABLED",
    "COOKIES_ENABLED",
    "AUTOTHROTTLE_ENABLED",
    "AUTOTHROTTLE_START_DELAY",
    "AUTOTHROTTLE_MAX_DELAY",
    "AUTOTHROTTLE_TARGET_CONCURRENCY",
    "RENDER_ENGINE",
    "TRACE_DIR",
    "OUTPUT_DIR",
    "MAX_IP_RETRIES",
    "RUNTIME_CONCURRENCY",
]
