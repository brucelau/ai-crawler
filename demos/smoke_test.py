#!/usr/bin/env python3
"""
冒烟测试：跑所有数据源的搜索页，报告解析结果
"""

import os
import sys
import json
import time
from datetime import datetime

os.environ["PYTHONUNBUFFERED"] = "1"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from ai_crawler import run_crawl, EXTRACTORS


def test_site(site: str, query: str = "chair") -> dict:
    print(f"\n{'=' * 60}")
    print(f"  测试: {site}")
    print(f"{'=' * 60}")

    t0 = time.time()
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
        tier = stats.get("tiers_used", [])

        print(f"  产品数: {products}")
        print(f"  耗时: {elapsed:.1f}s")
        print(f"  成功率: {stats['tasks_success']}/{stats['tasks_total']}")
        print(f"  Block types: {json.dumps(block_types, indent=4)}")
        print(f"  使用 Tier: {tier}")

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
            "tiers_used": tier,
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


def main():
    sites = sorted(EXTRACTORS.keys())
    print(f"支持站点总数: {len(sites)}")
    print(f"站点列表: {', '.join(sites)}")

    if len(sys.argv) < 2:
        print(f"\n用法: {sys.argv[0]} <site|all> [query]")
        return

    arg = sys.argv[1]
    query = sys.argv[2] if len(sys.argv) > 2 else "chair"

    if arg == "all":
        print(f"\n冒烟测试: 所有 {len(sites)} 个站点, query={query}")
        print(f"开始时间: {datetime.now().isoformat()}")

        polluted = [s for s in sites if s not in ("amazon", "walmart")]
        clean = [s for s in ("amazon", "walmart") if s in sites]
        ordered = polluted + clean

        results = []
        for site in ordered:
            r = test_site(site, query)
            results.append(r)
            time.sleep(1)

        print(f"\n{'#' * 70}")
        print(f"  汇总报告")
        print(f"{'#' * 70}")
        ok = [r for r in results if r["status"] == "OK"]
        zero = [r for r in results if r["status"] == "ZERO_PRODUCTS"]
        err = [r for r in results if r["status"] == "ERROR"]

        print(f"\n总计: {len(results)} | 正常 {len(ok)} | 零结果 {len(zero)} | 异常 {len(err)}")

        print(f"\n--- 正常 ({len(ok)}) ---")
        for r in ok:
            print(f"  ✓ {r['site']}: {r['products']} 产品 ({r['elapsed']:.1f}s)")

        print(f"\n--- 零结果 ({len(zero)}) ---")
        for r in zero:
            bt = r.get("block_types", {})
            print(f"  ✗ {r['site']}: 0 产品 | blocks={json.dumps(bt)}")

        print(f"\n--- 异常 ({len(err)}) ---")
        for r in err:
            print(f"  ✗ {r['site']}: {r.get('error', 'unknown')}")

    elif arg in sites:
        test_site(arg, query)
    else:
        print(f"未知站点: {arg}")
        print(f"可用: {', '.join(sites)}")


if __name__ == "__main__":
    main()
