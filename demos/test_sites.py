#!/usr/bin/env python3
"""测试各个数据源站点"""

import os
import sys

os.environ["PYTHONUNBUFFERED"] = "1"

from ai_crawler import run_crawl, EXTRACTORS


def test_site(site_name: str, query: str = "laptop") -> dict:
    """测试单个站点"""
    print(f"\n{'=' * 50}")
    print(f"测试站点: {site_name}")
    print(f"{'=' * 50}")

    result = run_crawl(
        sites=[site_name],
        query=query,
        pages=1,
        proxy_username="",
        proxy_password="",
    )

    print(f"产品数: {len(result.products)}")
    print(f"成功率: {result.stats['tasks_success']}/{result.stats['tasks_total']}")
    print(f"Block types: {result.stats.get('block_types', {})}")
    print(f"输出文件: {result.output_file}")

    if result.products:
        print(f"\n前3个产品:")
        for i, p in enumerate(result.products[:3], 1):
            print(f"  {i}. {p.url[:60]}...")

    return {
        "site": site_name,
        "products": len(result.products),
        "success": result.stats["tasks_success"],
        "total": result.stats["tasks_total"],
        "block_types": result.stats.get("block_types", {}),
        "output_file": result.output_file,
    }


def main():
    sites = list(EXTRACTORS.keys())

    if len(sys.argv) < 2:
        print(f"用法: {sys.argv[0]} <序号|站点名|all>")
        print(f"\n可用站点 ({len(sites)} 个):")
        for i, site in enumerate(sites, 1):
            print(f"  {i:2}. {site}")
        return

    arg = sys.argv[1]

    if arg == "all":
        # 测试所有站点
        results = []
        for site in sites:
            try:
                r = test_site(site)
                results.append(r)
            except Exception as e:
                print(f"错误: {e}")
                results.append({"site": site, "error": str(e)})

        # 汇总
        print(f"\n{'#' * 50}")
        print("汇总结果")
        print(f"{'#' * 50}")
        success_count = sum(1 for r in results if r.get("products", 0) > 0)
        print(f"成功站点: {success_count}/{len(results)}")
        for r in results:
            status = "✓" if r.get("products", 0) > 0 else "✗"
            print(f"  {status} {r['site']}: {r.get('products', 0)} 产品")

    elif arg.isdigit():
        idx = int(arg) - 1
        if 0 <= idx < len(sites):
            test_site(sites[idx])
        else:
            print(f"无效序号，有效范围: 1-{len(sites)}")

    elif arg in sites:
        test_site(arg)

    else:
        print(f"未知站点: {arg}")
        print(f"可用站点: {', '.join(sites)}")


if __name__ == "__main__":
    main()
