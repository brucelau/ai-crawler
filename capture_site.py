import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ai_crawler.browser.fetching import Fetcher
from ai_crawler.core.strategy import CrawlStrategy, RenderType, ProxyType, CrawlTask, PagePattern
from ai_crawler.core.runtime.proxying import ProxyProvider


def capture_site_html(site, url):
    print(f"--- 捕获 {site} 页面 HTML ---")

    proxy_provider = ProxyProvider(
        username=os.getenv("THORDATA_RESIDENTIAL_USERNAME"),
        password=os.getenv("THORDATA_RESIDENTIAL_PASSWORD"),
        disabled=False,
    )

    fetcher = Fetcher(proxy_provider=proxy_provider)
    fetcher.request_timeout = 60
    fetcher.page_load_timeout = 60

    strategy = CrawlStrategy(
        tier=4,
        render=RenderType.PLAYWRIGHT,
        proxy=ProxyType.THORDATA_DEDICATED,
        use_human_scroll=True,
    )

    task = CrawlTask(site=site, url=url, page_pattern=PagePattern.SEARCH, strategies=[strategy])

    try:
        html, status, page = fetcher.fetch_with_strategy(task, strategy)
        print(f"HTTP 状态码: {status}")

        if html:
            filename = f"{site}_debug.html"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"✅ HTML 已保存到 {filename}")
        else:
            print("❌ 未捕获到 HTML")
    except Exception as e:
        print(f"❌ 捕获异常: {str(e)}")
    finally:
        fetcher.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    capture_site_html(args.site, args.url)
