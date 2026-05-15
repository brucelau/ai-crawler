from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from ai_crawler.config.crawler_config import (
    browser_config,
    retry_config,
    concurrency_config,
    extraction_config,
    block_detection_config,
    browser_selector_config,
    BrowserConfig,
    RetryConfig,
    ConcurrencyConfig,
    ExtractionConfig,
    BlockDetectionConfig,
    BrowserSelectorConfig,
)


def setup_logging(
    log_level: str = "INFO", log_dir: str = "logs", log_file: str = "crawler.log"
) -> None:
    """Configure logging to output to both console and file."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    log_file_path = log_path / log_file

    # Create formatters
    detailed_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    simple_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # File handler - detailed logs
    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    file_handler.setFormatter(detailed_formatter)

    # Console handler - simpler format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    console_handler.setFormatter(simple_formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Also configure structlog if available
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


__all__ = [
    "config", "Config",
    "browser_config", "retry_config", "concurrency_config",
    "extraction_config", "block_detection_config", "browser_selector_config",
    "BrowserConfig", "RetryConfig", "ConcurrencyConfig",
    "ExtractionConfig", "BlockDetectionConfig", "BrowserSelectorConfig",
]
