#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from ai_crawler import run_crawl
from bs4 import BeautifulSoup


def analyze(site: str, query: str = "chair"):
    print(f"Analyzing: {site}")

    result = run_crawl(
        sites=[site],
        query=query,
        pages=1,
        proxy_username="",
        proxy_password="",
    )

    print(f"Products: {len(result.products)}")

    for f in result.output_files or []:
        if f.endswith('.html'):
            print(f"Analyzing HTML: {f}")
            with open(f) as hf:
                html = hf.read()
            soup = BeautifulSoup(html, 'html.parser')

            selectors = [
                '[data-item-id]',
                '[data-product-id]',
                '[data-pod-type]',
                '[data-testid*="product"]',
                '.product-card',
                '.product-pod',
                '.product-item',
                'li[class*="product"]',
                'article',
                '.search_result',
                '#search-results li',
                '.results li',
            ]

            for sel in selectors:
                items = soup.select(sel)
                if items:
                    print(f"\n  {sel}: {len(items)} items")
                    if len(items) > 0:
                        sample = items[0]
                        print(f"    First item preview: {str(sample)[:300]}...")

                        for tag in ['h2', 'h3', 'h4', '[class*="title"]', 'a[href]']:
                            el = sample.select_one(tag)
                            if el:
                                text = el.get_text(strip=True)[:60]
                                if text:
                                    print(f"    {tag}: {text}")
                                    break
                    if len(items) >= 5:
                        break


if __name__ == "__main__":
    site = sys.argv[1] if len(sys.argv) > 1 else "homedepot"
    analyze(site)
