"""Scrapy integration (DEPRECATED - use ai_crawler.orchestration instead).

This adapter provides a Scrapy-based crawling path using SmartCrawlerRuntime.
The primary crawling path is via ai_crawler.orchestration.SmartCrawlerRuntime.
"""

from ai_crawler.integrations.scrapy.bridge import ScrapyRuntimeBridge

__all__ = ["ScrapyRuntimeBridge"]
