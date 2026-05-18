#!/usr/bin/env python3
"""测试 QVC 站点的自动升级策略和页面解析功能"""

import os
import sys

os.environ["PYTHONUNBUFFERED"] = "1"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from ai_crawler import SmartCrawlerRuntime, RuntimeOptions, RuntimeTask
from ai_crawler.extraction.template_based import UniversalExtractor


def test_qvc_extraction():
    site = "qvc"
    query = "chair"
    url = f"https://www.qvc.com/catalog/psearch.html?keyword={query}&sa=submit"

    print(f"{'=' * 60}")
    print(f"测试 QVC 站点的自动升级策略和页面解析")
    print(f"{'=' * 60}")
    print(f"站点: {site}")
    print(f"URL: {url}")
    print()

    # Step 1: 用 Playwright 获取渲染后的 HTML（tier 4）
    print("1. 用 Playwright (tier 4) 获取渲染后的 HTML...")
    from ai_crawler.fetch import Fetcher
    from ai_crawler.core.types import CrawlTask, PagePattern, CrawlPolicy as CrawlStrategy

    task = CrawlTask.create_from_tier(
        url=url,
        site=site,
        page_pattern=PagePattern.SEARCH,
    )

    strategy = CrawlStrategy.from_tier(4)
    fetcher = Fetcher()
    html, status_code, page = fetcher.fetch_with_strategy(task, strategy)

    print(f"   - status: {status_code}")
    print(f"   - html size: {len(html) if html else 0}")
    print()

    if not html:
        print("获取 HTML 失败，跳过提取测试")
        return

    # Step 2: 测试 JSON-LD 提取
    print("2. 测试 JSON-LD 提取...")
    from ai_crawler.extraction.json_ld import JSONLDExtraction
    json_ld = JSONLDExtraction()
    json_ld_products = json_ld.extract(page, html, url)
    print(f"   - JSON-LD products: {len(json_ld_products)}")

    # Step 3: 测试 AXTree 提取
    print("3. 测试 AXTree 提取...")
    from ai_crawler.extraction.axtree import AXTreeExtraction
    axtree = AXTreeExtraction()
    print(f"   - page is None: {page is None}")
    if page:
        try:
            snapshot_result = page.accessibility.snapshot(interesting_only=False)
            print(f"   - accessibility.snapshot success: {snapshot_result is not None}")
        except Exception as e:
            print(f"   - accessibility.snapshot error: {e}")

        axtree_products = axtree.extract(page, html, url)
        print(f"   - AXTree products: {len(axtree_products)}")
        if axtree_products:
            print("   通过 AXTree 提取到产品!")
            for i, p in enumerate(axtree_products[:3], 1):
                print(f"     {i}. {p.title[:50]}...")
    else:
        print("   无法测试 AXTree (page is None)")

    # Step 4: 测试 UniversalExtractor
    print()
    print("4. 测试 UniversalExtractor...")
    universal = UniversalExtractor()
    result = universal.extract(page, html, url, "search")

    print(f"   - strategy: {result.strategy}")
    print(f"   - method: {result.method}")
    print(f"   - products: {len(result.products)}")
    print()

    if result.products:
        print("成功提取产品:")
        for i, p in enumerate(result.products[:3], 1):
            print(f"   {i}. {p.title[:60]}...")
            print(f"      URL: {p.url[:60]}...")
            if hasattr(p, 'price') and p.price:
                print(f"      Price: {p.price}")
    else:
        print("未能提取到产品，尝试更高 tier...")

        # 尝试 tier 6
        print()
        print("5. 尝试更高 tier (tier 6 - camoufox)...")
        strategy6 = CrawlStrategy.from_tier(6)
        html6, status6, page6 = fetcher.fetch_with_strategy(task, strategy6)
        print(f"   - status: {status6}")
        print(f"   - html size: {len(html6) if html6 else 0}")

        if html6:
            result6 = universal.extract(page6, html6, url, "search")
            print(f"   - products: {len(result6.products)}")
            if result6.products:
                print("成功提取产品:")
                for i, p in enumerate(result6.products[:3], 1):
                    print(f"   {i}. {p.title[:60]}...")


def test_qvc_full_crawl():
    print()
    print("=" * 60)
    print("运行完整爬虫测试 (SmartCrawlerRuntime)")
    print("=" * 60)

    # 从 .env 加载代理凭证
    from dotenv import load_dotenv
    load_dotenv()

    import os
    thordata_username = os.getenv("THORDATA_RESIDENTIAL_USERNAME", "")
    thordata_password = os.getenv("THORDATA_RESIDENTIAL_PASSWORD", "")

    options = RuntimeOptions(
        proxy_username=thordata_username,
        proxy_password=thordata_password,
        output_dir="output/qvc_test",
        traces_dir="traces/qvc_test",
        concurrency=1,
        strategy_mode="minimal_sufficient",
    )

    runtime = SmartCrawlerRuntime(options)
    tasks = runtime.build_search_tasks(["qvc"], "chair", pages=1)

    print(f"任务数: {len(tasks)}")
    print(f"任务 URL: {tasks[0].url}")

    result = runtime.crawl_tasks(tasks)

    print()
    print(f"成功: {result.stats['tasks_success']}/{result.stats['tasks_total']}")
    print(f"产品数: {result.stats['products_crawled']}")
    print(f"Block types: {result.stats.get('block_types', {})}")
    print(f"输出文件: {result.output_files}")


if __name__ == "__main__":
    test_qvc_extraction()
    test_qvc_full_crawl()