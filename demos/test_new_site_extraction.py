#!/usr/bin/env python3
"""测试新站点（从未爬过）的提取流程"""

import os
import sys

os.environ["PYTHONUNBUFFERED"] = "1"

from ai_crawler import SmartCrawlerRuntime, RuntimeOptions, RuntimeTask
from ai_crawler.extraction.template_based import (
    get_template,
    clear_templates,
)
from ai_crawler.extraction.template_based import UniversalExtractor


def test_extraction_only():
    """只测试提取部分，不运行完整爬虫"""
    site = "temu"
    query = "headphones"
    url = f"https://www.temu.com/search?search_key={query}"

    print(f"{'=' * 60}")
    print(f"测试 UniversalExtractor 在新站点上的表现")
    print(f"{'=' * 60}")
    print(f"站点: {site}")
    print(f"URL: {url}")
    print()

    clear_templates()

# 先用 Playwright 获取渲染后的 HTML（tier 4）
    print("1. 用 Playwright 获取渲染后的 HTML...")
    from ai_crawler.fetch import Fetcher
    from ai_crawler.core.types import CrawlTask, PagePattern, CrawlPolicy as CrawlStrategy

    task = CrawlTask.create_from_tier(
        url=url,
        site=site,
        page_pattern=PagePattern.SEARCH,
    )

    # 用 tier 4 (playwright) - 真实浏览器渲染
    strategy = CrawlStrategy.from_tier(4)

    fetcher = Fetcher()
    html, status_code, page = fetcher.fetch_with_strategy(task, strategy)

    print(f"   - status: {status_code}")
    print(f"   - html size: {len(html) if html else 0}")
    print()

    if not html:
        print("获取 HTML 失败，跳过提取测试")
        return

    # 测试 JSON-LD 提取
    print("2. 测试 JSON-LD 提取...")
    from ai_crawler.extraction.json_ld import JSONLDExtraction
    json_ld = JSONLDExtraction()
    json_ld_products = json_ld.extract(page, html, url)
    print(f"   - JSON-LD products: {len(json_ld_products)}")

    # 测试 AXTree 提取
    print("3. 测试 AXTree 提取...")
    from ai_crawler.extraction.axtree import AXTreeExtraction
    axtree = AXTreeExtraction()
    print(f"   - page is None: {page is None}")
    if page:
        # 测试 accessibility.snapshot
        try:
            snapshot_result = page.accessibility.snapshot(interesting_only=False)
            print(f"   - accessibility.snapshot success: {snapshot_result is not None}")
            if snapshot_result:
                print(f"   - snapshot keys: {list(snapshot_result.keys()) if isinstance(snapshot_result, dict) else 'not a dict'}")
        except Exception as e:
            print(f"   - accessibility.snapshot error: {e}")

        # 测试 CDP tree
        try:
            context = page.context
            cdp_session = context.new_cdp_session(page)
            result = cdp_session.send("DOMSnapshot.captureSnapshot", {})
            print(f"   - CDP snapshot success: {result is not None}")
            cdp_session.detach()
        except Exception as e:
            print(f"   - CDP snapshot error: {e}")

        axtree_products = axtree.extract(page, html, url)
        print(f"   - AXTree products: {len(axtree_products)}")
        if axtree_products:
            print("   成功通过 AXTree 提取到产品!")
            for i, p in enumerate(axtree_products[:3], 1):
                print(f"     {i}. {p.title[:50]}...")
    else:
        print("   - 无法测试 AXTree (page is None)")

    print()
    print("4. 测试 UniversalExtractor...")
    universal = UniversalExtractor()
    result = universal.extract(page, html, url, "search")

    print(f"   - strategy: {result.strategy}")
    print(f"   - method: {result.method}")
    print(f"   - products: {len(result.products)}")
    print()

    if result.products:
        print("   成功提取产品:")
        for i, p in enumerate(result.products[:3], 1):
            print(f"     {i}. {p.title[:50]}...")
            print(f"        URL: {p.url[:60]}...")
            print(f"        Price: {p.price}")
    else:
        print("   未能提取到产品")

    # 测试 LLM 生成模板
    if result.products:
        print()
        print("3. 测试 LLM 生成模板...")
        from ai_crawler.extraction.template_based import llm_generate_template

        template = llm_generate_template(site, "search", html, result.products, page)
        if template:
            print(f"   - css_selector: {template.css_selector}")
            print(f"   - js_selector: {template.js_selector}")
            print(f"   - is_valid: {template.is_valid}")

            # 保存并测试
            from ai_crawler.extraction.template_based import save_template
            save_template(template)
            print("   模板已保存!")

            # 用模板再次提取
            print()
            print("4. 用生成的模板再次提取...")
            saved_result = template.extract(page, html, url)
            print(f"   - products: {len(saved_result.products)}")
        else:
            print("   LLM 生成模板失败")


if __name__ == "__main__":
    test_extraction_only()
