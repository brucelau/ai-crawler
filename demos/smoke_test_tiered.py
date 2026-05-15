#!/usr/bin/env python3
"""
分层冒烟测试：
- Phase 1: JS 渲染站点 (tier >= 4) - 使用 PLAYWRIGHT/CLOUDERA 测试
- Phase 2: 直接爬取站点 (tier 1-3) - 使用 NONE/cloudscraper 测试

用法:
  python smoke_test_tiered.py all          # 运行所有测试
  python smoke_test_tiered.py js           # 只测试 JS 渲染站点
  python smoke_test_tiered.py direct       # 只测试直接爬取站点
  python smoke_test_tiered.py <site>       # 测试单个站点
"""

import os
import sys
import json
import time
from datetime import datetime
from typing import Literal

os.environ["PYTHONUNBUFFERED"] = "1"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from ai_crawler import run_crawl, EXTRACTORS, CrawlStrategy
from ai_crawler.config.sites import SITE_TIER_DEFAULTS, URL_PATTERNS
from ai_crawler.spider.types import PagePattern, ProxyType, RenderType


# 按 tier 分类站点
def categorize_sites():
    js_sites = []  # tier >= 4
    direct_sites = []  # tier <= 3

    for site in sorted(EXTRACTORS.keys()):
        tier = SITE_TIER_DEFAULTS.get(site, {}).get(PagePattern.SEARCH, 1)
        if tier >= 4:
            js_sites.append(site)
        else:
            direct_sites.append(site)

    return js_sites, direct_sites


def test_site_with_tier(site: str, query: str = "chair", min_tier: int = 1) -> dict:
    """测试单个站点，强制最小 tier"""
    print(f"\n{'=' * 60}")
    print(f"  测试: {site} (min_tier={min_tier})")
    print(f"{'=' * 60}")

    t0 = time.time()

    # 获取站点的策略配置
    strategies = URL_PATTERNS.get(site, {}).get(PagePattern.SEARCH, [])
    if strategies:
        # 找到 >= min_tier 的第一个策略
        forced_strategy = None
        for s in strategies:
            s_tier = getattr(s, 'tier', 1)
            if s_tier >= min_tier:
                forced_strategy = s
                break

        if forced_strategy:
            print(f"  强制策略: tier={getattr(forced_strategy, 'tier', 1)} render={forced_strategy.render}")

    try:
        result = run_crawl(
            sites=[site],
            query=query,
            pages=1,
            proxy_username="",
            proxy_password="",
        )
        elapsed = time.time() - t0

        products = len(result.products)
        stats = result.stats
        block_types = stats.get("block_types", {})
        tiers_used = stats.get("tiers_used", [])

        print(f"  产品数: {products}")
        print(f"  耗时: {elapsed:.1f}s")
        print(f"  成功率: {stats['tasks_success']}/{stats['tasks_total']}")
        print(f"  Block types: {json.dumps(block_types, indent=4)}")
        print(f"  使用 Tier: {tiers_used}")

        if result.products:
            print(f"  前3个结果:")
            for i, p in enumerate(result.products[:3], 1):
                title = getattr(p, "title", "N/A") or "N/A"
                if len(title) > 60:
                    title = title[:60] + "..."
                print(f"    {i}. {title}")
                print(f"       {p.url[:70]}...")

        return {
            "site": site,
            "products": products,
            "elapsed": elapsed,
            "success": stats["tasks_success"],
            "total": stats["tasks_total"],
            "block_types": block_types,
            "tiers_used": tiers_used,
            "output_file": result.output_files,
            "status": "OK" if products > 0 else "ZERO_PRODUCTS",
        }

    except Exception as e:
        elapsed = time.time() - t0
        print(f"  异常: {e}")
        import traceback
        traceback.print_exc()
        return {
            "site": site,
            "products": -1,
            "elapsed": elapsed,
            "error": str(e),
            "status": "ERROR",
        }


def test_site_force_render(site: str, query: str = "chair", render: RenderType = RenderType.PLAYWRIGHT) -> dict:
    """测试单个站点，强制使用特定渲染类型"""
    print(f"\n{'=' * 60}")
    print(f"  测试: {site} (force_render={render.value})")
    print(f"{'=' * 60}")

    t0 = time.time()
    try:
        # 使用 run_crawl，它会自动选择策略
        result = run_crawl(
            sites=[site],
            query=query,
            pages=1,
            proxy_username="",
            proxy_password="",
        )
        elapsed = time.time() - t0

        products = len(result.products)
        stats = result.stats
        block_types = stats.get("block_types", {})
        tiers_used = stats.get("tiers_used", [])

        print(f"  产品数: {products}")
        print(f"  耗时: {elapsed:.1f}s")
        print(f"  成功率: {stats['tasks_success']}/{stats['tasks_total']}")
        print(f"  Block types: {json.dumps(block_types, indent=4)}")
        print(f"  使用 Tier: {tiers_used}")

        if result.products:
            print(f"  前3个结果:")
            for i, p in enumerate(result.products[:3], 1):
                title = getattr(p, "title", "N/A") or "N/A"
                if len(title) > 60:
                    title = title[:60] + "..."
                print(f"    {i}. {title}")
                print(f"       {p.url[:70]}...")

        return {
            "site": site,
            "products": products,
            "elapsed": elapsed,
            "success": stats["tasks_success"],
            "total": stats["tasks_total"],
            "block_types": block_types,
            "tiers_used": tiers_used,
            "output_file": result.output_files,
            "status": "OK" if products > 0 else "ZERO_PRODUCTS",
        }

    except Exception as e:
        elapsed = time.time() - t0
        print(f"  异常: {e}")
        return {
            "site": site,
            "products": -1,
            "elapsed": elapsed,
            "error": str(e),
            "status": "ERROR",
        }


def print_summary(results: list[dict], phase: str):
    """打印测试汇总"""
    print(f"\n{'#' * 70}")
    print(f"  {phase} 汇总报告")
    print(f"{'#' * 70}")

    ok = [r for r in results if r["status"] == "OK"]
    zero = [r for r in results if r["status"] == "ZERO_PRODUCTS"]
    err = [r for r in results if r["status"] == "ERROR"]

    print(f"\n总计: {len(results)} | 正常 {len(ok)} | 零结果 {len(zero)} | 异常 {len(err)}")

    if ok:
        print(f"\n--- 正常 ({len(ok)}) ---")
        for r in ok:
            print(f"  ✓ {r['site']}: {r['products']} 产品 ({r['elapsed']:.1f}s)")

    if zero:
        print(f"\n--- 零结果 ({len(zero)}) ---")
        for r in zero:
            bt = r.get("block_types", {})
            tiers = r.get("tiers_used", [])
            print(f"  ✗ {r['site']}: 0 产品 | blocks={json.dumps(bt)} | tiers={tiers}")

    if err:
        print(f"\n--- 异常 ({len(err)}) ---")
        for r in err:
            print(f"  ✗ {r['site']}: {r.get('error', 'unknown')}")

    return ok, zero, err


def main():
    if len(sys.argv) < 2:
        print(f"\n用法:")
        print(f"  {sys.argv[0]} all      # 运行所有测试 (JS站点 + 直接站点)")
        print(f"  {sys.argv[0]} js       # 只测试 JS 渲染站点 (tier >= 4)")
        print(f"  {sys.argv[0]} direct   # 只测试直接爬取站点 (tier <= 3)")
        print(f"  {sys.argv[0]} <site>   # 测试单个站点")
        return

    arg = sys.argv[1]
    query = sys.argv[2] if len(sys.argv) > 2 else "chair"

    js_sites, direct_sites = categorize_sites()

    print(f"支持站点总数: {len(EXTRACTORS)}")
    print(f"JS 渲染站点 (tier >= 4): {len(js_sites)}")
    print(f"直接爬取站点 (tier <= 3): {len(direct_sites)}")

    if arg == "all":
        # Phase 1: JS 渲染站点
        print(f"\n{'=' * 70}")
        print(f"  Phase 1: JS 渲染站点测试 (tier >= 4)")
        print(f"{'=' * 70}")
        print(f"站点: {', '.join(js_sites)}")

        js_results = []
        for site in js_sites:
            r = test_site_force_render(site, query)
            js_results.append(r)
            time.sleep(1)

        ok1, zero1, err1 = print_summary(js_results, "Phase 1 (JS 渲染)")

        # Phase 2: 直接爬取站点
        print(f"\n{'=' * 70}")
        print(f"  Phase 2: 直接爬取站点测试 (tier <= 3)")
        print(f"{'=' * 70}")
        print(f"站点: {', '.join(direct_sites)}")

        direct_results = []
        for site in direct_sites:
            r = test_site_force_render(site, query)
            direct_results.append(r)
            time.sleep(1)

        ok2, zero2, err2 = print_summary(direct_results, "Phase 2 (直接爬取)")

        # 最终汇总
        print(f"\n{'#' * 70}")
        print(f"  最终汇总")
        print(f"{'#' * 70}")
        total_ok = len(ok1) + len(ok2)
        total_zero = len(zero1) + len(zero2)
        total_err = len(err1) + len(err2)
        print(f"总计: {len(js_results) + len(direct_results)} | 正常 {total_ok} | 零结果 {total_zero} | 异常 {total_err}")

    elif arg == "js":
        print(f"\nJS 渲染站点 (tier >= 4): {len(js_sites)}")
        print(f"站点: {', '.join(js_sites)}")
        results = []
        for site in js_sites:
            r = test_site_force_render(site, query)
            results.append(r)
            time.sleep(1)
        print_summary(results, "JS 渲染站点")

    elif arg == "direct":
        print(f"\n直接爬取站点 (tier <= 3): {len(direct_sites)}")
        print(f"站点: {', '.join(direct_sites)}")
        results = []
        for site in direct_sites:
            r = test_site_force_render(site, query)
            results.append(r)
            time.sleep(1)
        print_summary(results, "直接爬取站点")

    elif arg in EXTRACTORS:
        test_site_force_render(arg, query)

    else:
        print(f"未知站点: {arg}")
        print(f"可用: {', '.join(sorted(EXTRACTORS.keys()))}")


if __name__ == "__main__":
    main()
