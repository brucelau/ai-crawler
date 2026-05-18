#!/usr/bin/env python3
"""测试每个站点的 Tier 6 策略，不优化，不跳过"""

import os
import sys
import time

os.environ["PYTHONUNBUFFERED"] = "1"

sb_drivers = (
    "/Users/cyberway/ocworkspace/ai-crawler/.venv/lib/python3.14/site-packages/seleniumbase/drivers"
)
os.environ["PATH"] = sb_drivers + ":" + os.environ.get("PATH", "")
os.environ["UC_DRIVER_BASE_DIR"] = sb_drivers

from dotenv import load_dotenv

load_dotenv()

from ai_crawler.crawl.runner import Fetcher, ProxyProvider
from ai_crawler.core.types import CrawlPolicy as CrawlStrategy


class FakeTask:
    def __init__(self, url):
        self.url = url
        self.task_id = "test"


def test_tier6(site: str) -> dict:
    t0 = time.time()

    url = f"https://www.{site}.com/search?q=chair"
    strategy = CrawlStrategy.from_tier(6)

    print(f"\n{'=' * 50}")
    print(f"测试: {site}")
    print(f"URL: {url}")
    print(f"Render: {strategy.render.value}")
    print(f"Proxy: {strategy.proxy.value}")
    print(f"{'=' * 50}")

    proxy_provider = ProxyProvider("", "", disabled=True)
    fetcher = Fetcher(proxy_provider, {})

    try:
        html, status, page = fetcher.fetch_with_strategy(FakeTask(url), strategy)
        elapsed = time.time() - t0

        print(f"状态码: {status}")
        print(f"HTML长度: {len(html)}")
        print(f"耗时: {elapsed:.1f}秒")

        if status == 200 and len(html) > 1000:
            print(f"✓ 成功!")
            return {
                "site": site,
                "success": True,
                "status": status,
                "html_len": len(html),
                "time": elapsed,
            }
        else:
            print(f"✗ 失败")
            return {
                "site": site,
                "success": False,
                "status": status,
                "html_len": len(html),
                "time": elapsed,
            }

    except Exception as e:
        elapsed = time.time() - t0
        print(f"✗ 异常: {e}")
        return {"site": site, "success": False, "error": str(e)[:100], "time": elapsed}


if __name__ == "__main__":
    sites = [
        "amazon",
        "walmart",
        "target",
        "ebay",
        "menards",
        "lowes",
        "homedepot",
        "acehardware",
        "wayfair",
        "michaels",
        "temu",
        "etsy",
        "bestbuy",
        "costco",
        "qvc",
        "kohls",
        "mercadolibre",
        "walmartmexico",
        "intexcorp",
        "meijer",
        "fivebelow",
        "samsclub",
        "bunnings",
        "dollargeneral",
        "action",
        "academy",
        "wowsports",
        "coppel",
        "aosom",
        "familydollar",
        "costway",
    ]

    if len(sys.argv) > 1:
        if sys.argv[1] == "all":
            targets = sites
        elif sys.argv[1].isdigit():
            idx = int(sys.argv[1]) - 1
            targets = [sites[idx]] if idx < len(sites) else []
        elif sys.argv[1] in sites:
            targets = [sys.argv[1]]
        else:
            targets = [a for a in sys.argv[1:] if a in sites]
    else:
        print(f"用法: {sys.argv[0]} <站点名|all|序号>")
        print(f"可用站点 ({len(sites)} 个):")
        for i, s in enumerate(sites, 1):
            print(f"  {i:2}. {s}")
        sys.exit(1)

    print(f"\n测试 {len(targets)} 个站点，每个站点用 Tier 6")
    print("这可能需要很长时间，请耐心等待...")

    results = []
    for site in targets:
        r = test_tier6(site)
        results.append(r)
        print(f"\n下一个站点休息 2 秒...")
        time.sleep(2)

    print(f"\n{'=' * 60}")
    print("汇总结果")
    print(f"{'=' * 60}")
    success = sum(1 for r in results if r.get("success"))
    print(f"成功: {success}/{len(results)}")
    print(f"\n{'站点':<20} {'状态':>8} {'HTML长度':>12} {'耗时':>10}")
    print("-" * 55)
    for r in results:
        mark = "✓" if r.get("success") else "✗"
        stat = str(r.get("status", r.get("error", "ERR")[:8]))
        html_len = r.get("html_len", 0)
        elapsed = r.get("time", 0)
        print(f"{mark} {r['site']:<18} {stat:>8} {html_len:>12} {elapsed:>9.1f}s")
