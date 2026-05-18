#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from ai_crawler.browser.cloakbrowser_wrapper import CloakBrowserWrapper
from ai_crawler.core.types import ProxyType


def fetch_and_save(site: str, query: str = "chair"):
    print(f"Fetching {site} with cloakbrowser...")

    url = f"https://www.{site}.com/s/{query.replace(' ', '+')}"

    browser = CloakBrowserWrapper(
        wait_time=5.0,
        human_scroll=True,
    )

    html, status = browser.fetch(
        url,
        wait_time=5.0,
        human_scroll=True,
    )

    print(f"Status: {status}")
    print(f"HTML size: {len(html)}")

    if html and len(html) > 5000:
        html_path = f"debug_{site}_cloakbrowser.html"
        with open(html_path, 'w') as f:
            f.write(html)
        print(f"Saved to: {html_path}")
        analyze(html)
    else:
        print("HTML too small")


def analyze(html: str):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, 'html.parser')

    selectors = [
        '[data-item-id]',
        '[data-product-id]',
        '[data-pod-type]',
        '[data-testid*="product"]',
        '[data-testid*="Product"]',
        '.product-card',
        '.product-pod',
        '.product-item',
        '.product-card__container',
        '[class*="product-card"]',
        '[class*="product__card"]',
        'li[class*="product"]',
        'article[class*="product"]',
        'article[class*="Product"]',
        '[itemtype*="Product"]',
        '.search-results li',
        '#search-results li',
        '[class*="results"] li',
        '[class*="listing"]',
        '[class*="product"]',
    ]

    print("\nSelector analysis:")
    for sel in selectors:
        items = soup.select(sel)
        if items:
            print(f"\n  {sel}: {len(items)} items")
            if len(items) > 0:
                sample = items[0]
                text = sample.get_text(' ', strip=True)[:100].replace('\n', ' ')
                print(f"    Text preview: {text}...")

                for tag in ['h2', 'h3', 'h4', 'a[href]', '[class*="title"]']:
                    el = sample.select_one(tag)
                    if el:
                        t = el.get_text(strip=True)[:60]
                        if t:
                            print(f"    {tag}: {t}")
                            break

            if len(items) >= 3:
                break

    print("\n\nLooking for specific patterns in HTML:")
    html_lower = html.lower()
    patterns = [
        'product-card',
        'data-item',
        'product__title',
        'product-title',
        'pod-type',
        'search-result',
    ]
    for p in patterns:
        count = html_lower.count(p)
        if count > 0:
            print(f"  '{p}': {count} occurrences")


if __name__ == "__main__":
    site = sys.argv[1] if len(sys.argv) > 1 else "homedepot"
    fetch_and_save(site)
