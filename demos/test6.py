#!/usr/bin/env python3
"""只测试 Tier 6，一次请求，成功/失败都结束"""

import os
import sys
import time

os.environ["PYTHONUNBUFFERED"] = "1"

from dotenv import load_dotenv

load_dotenv()

from ai_crawler.crawl.runner import Fetcher, ProxyProvider
from ai_crawler.core.types import CrawlPolicy as CrawlStrategy


def test_one(site: str) -> dict:
    t0 = time.time()

    url = f"https://www.{site}.com/search?q=chair"
    strategy = CrawlStrategy.from_tier(6)

    print(f"测试: {site}")
    print(f"URL: {url}")
    print(f"策略: {strategy.render.value}")

    proxy_provider = ProxyProvider("", "", disabled=True)
    fetcher = Fetcher(proxy_provider, {})

    try:
        html, status, page = fetcher.fetch_with_strategy(
            type("Task", (), {"url": url, "task_id": "test"})(), strategy
        )
        elapsed = time.time() - t0
        print(f"结果: status={status}, len={len(html)}, time={elapsed:.1f}s")
        return {
            "site": site,
            "success": status == 200 and len(html) > 1000,
            "status": status,
            "len": len(html),
            "time": elapsed,
        }
    except Exception as e:
        elapsed = time.time() - t0
        print(f"异常: {e}")
        return {"site": site, "success": False, "error": str(e)[:100], "time": elapsed}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"用法: {sys.argv[0]} <站点>")
        sys.exit(1)

    site = sys.argv[1]
    result = test_one(site)
    print(f"\n{'=' * 40}")
    print(f"{'✓ 成功' if result['success'] else '✗ 失败'}: {site}")
