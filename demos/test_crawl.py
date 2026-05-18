#!/usr/bin/env python3
"""顺序测试各个数据源站点，每个站点抓取10个产品"""

import os
import sys
import time
import json

os.environ["PYTHONUNBUFFERED"] = "1"

from dotenv import load_dotenv

load_dotenv()

from ai_crawler import run_crawl, EXTRACTORS


def test_site(site_name: str, query: str = "chair", use_proxy: bool = True) -> dict:
    print(f"\n{'=' * 60}")
    print(f"测试站点: {site_name}")
    print(f"代理: {'启用' if use_proxy else '禁用'}")
    print(f"{'=' * 60}")

    t0 = time.time()
    try:
        result = run_crawl(
            sites=[site_name],
            query=query,
            pages=1,
            proxy_username=os.getenv("SOAX_USERNAME", "") if use_proxy else "",
            proxy_password=os.getenv("SOAX_PASSWORD", "") if use_proxy else "",
            llm_api_key=os.getenv("OPENAI_API_KEY", ""),
            captcha_api_key=os.getenv("2CAPTCHA_API_KEY", ""),
            proxy_disabled=not use_proxy,
        )
        elapsed = time.time() - t0

        success_rate = f"{result.stats['tasks_success']}/{result.stats['tasks_total']}"
        block_types = result.stats.get("block_types", {})

        print(f"\n结果:")
        print(f"  产品数: {len(result.products)}")
        print(f"  成功率: {success_rate}")
        print(f"  耗时: {elapsed:.1f}s")
        if block_types:
            print(f"  Block types: {json.dumps(block_types, indent=4)}")
        print(f"  输出文件: {result.output_file}")

        if result.products:
            print(f"\n前3个产品:")
            for i, p in enumerate(result.products[:3], 1):
                title = getattr(p, "title", "N/A")[:50]
                price = getattr(p, "price", "N/A")
                print(f"    {i}. {title}... | ${price}")

        return {
            "site": site_name,
            "products": len(result.products),
            "success": result.stats["tasks_success"],
            "total": result.stats["tasks_total"],
            "block_types": block_types,
            "elapsed": elapsed,
            "output_file": result.output_file,
            "success_rate": success_rate,
        }
    except Exception as e:
        print(f"错误: {e}")
        import traceback

        traceback.print_exc()
        return {
            "site": site_name,
            "products": 0,
            "success": 0,
            "total": 0,
            "error": str(e),
        }


def main():
    sites = list(EXTRACTORS.keys())
    use_proxy = True

    if len(sys.argv) < 2:
        print(f"用法: {sys.argv[0]} <序号|站点名|all> [--no-proxy]")
        print(f"\n可用站点 ({len(sites)} 个):")
        for i, site in enumerate(sites, 1):
            print(f"  {i:2}. {site}")
        print(f"\n选项:")
        print(f"  --no-proxy   禁用代理，直接连接")
        return

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]

    if "--no-proxy" in flags:
        use_proxy = False

    if not args:
        print("请指定站点序号或名称")
        return

    arg = args[0]

    if arg == "all":
        results = []
        for site in sites:
            r = test_site(site, use_proxy=use_proxy)
            results.append(r)
            time.sleep(2)

        print(f"\n{'#' * 60}")
        print("汇总结果")
        print(f"{'#' * 60}")
        success_count = sum(1 for r in results if r.get("products", 0) > 0)
        print(f"成功站点: {success_count}/{len(results)}")
        print(f"\n{'站点':<20} {'产品数':>8} {'成功率':>12} {'耗时':>8}")
        print("-" * 52)
        for r in results:
            status = "✓" if r.get("products", 0) > 0 else "✗"
            products = r.get("products", 0)
            success_rate = r.get("success_rate", "N/A")
            elapsed = r.get("elapsed", 0)
            print(f"{status} {r['site']:<18} {products:>8} {success_rate:>12} {elapsed:>7.1f}s")

    elif arg.isdigit():
        idx = int(arg) - 1
        if 0 <= idx < len(sites):
            test_site(sites[idx], use_proxy=use_proxy)
        else:
            print(f"无效序号，有效范围: 1-{len(sites)}")

    elif arg in sites:
        test_site(arg, use_proxy=use_proxy)

    else:
        print(f"未知站点: {arg}")
        print(f"可用站点: {', '.join(sites)}")


if __name__ == "__main__":
    main()
