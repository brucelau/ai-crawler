#!/usr/bin/env python3
"""用 Tier 1 (curl) 快速测试各站点"""

import os
import sys
import time

os.environ["PYTHONUNBUFFERED"] = "1"

from dotenv import load_dotenv

load_dotenv()

from ai_crawler.spider.runner import Fetcher, ProxyProvider
from ai_crawler.spider.strategy import CrawlStrategy


def test_tier1(site: str) -> dict:
    t0 = time.time()

    url = f"https://www.{site}.com/search?q=chair"
    strategy = CrawlStrategy.from_tier(1)
    strategy.change_ua = True

    print(f"测试: {site} | URL: {url}")

    proxy_provider = ProxyProvider("", "", disabled=True)
    fetcher = Fetcher(proxy_provider, {})

    try:
        html, status, page = fetcher.fetch_with_strategy(
            type("Task", (), {"url": url, "task_id": "test"})(), strategy
        )
        elapsed = time.time() - t0
        ok = status == 200 and len(html) > 1000
        print(f"  -> {status}, {len(html)} bytes, {elapsed:.1f}s, {'✓' if ok else '✗'}")
        return {"site": site, "success": ok, "status": status, "len": len(html), "time": elapsed}
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  -> 异常: {e}")
        return {"site": site, "success": False, "error": str(e)[:80], "time": elapsed}


if __name__ == "__main__":
    sites = ["costway", "temu", "fivebelow", "amazon", "walmart", "target", "ebay", "lowes"]

    if len(sys.argv) > 1:
        if sys.argv[1] == "all":
            targets = sites
        else:
            targets = [a for a in sys.argv[1:] if a]
    else:
        targets = sites

    print(f"测试 {len(targets)} 个站点 (Tier 1)")
    print("-" * 50)

    results = []
    for site in targets:
        r = test_tier1(site)
        results.append(r)

    print("-" * 50)
    success = sum(1 for r in results if r["success"])
    print(f"成功: {success}/{len(results)}")
