import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ai_crawler.core.runner import CrawlRunner
from ai_crawler.core.strategy import CrawlTask, CrawlStrategy, RenderType, ProxyType, PagePattern


def test_etsy_interactive():
    print("--- 验证 Etsy 首页交互搜索流程 ---")

    runner = CrawlRunner(
        proxy_username=os.getenv("THORDATA_RESIDENTIAL_USERNAME"),
        proxy_password=os.getenv("THORDATA_RESIDENTIAL_PASSWORD"),
        proxy_disabled=False,
        concurrency=1,
    )

    site = "etsy"
    query = "jewelry"
    url = "https://www.etsy.com/search?q=jewelry"

    interactive_strat = CrawlStrategy(
        tier=4,
        render=RenderType.PLAYWRIGHT,
        proxy=ProxyType.THORDATA_DEDICATED,
        use_interactive_search=True,
        use_human_scroll=True,
    )

    task = CrawlTask(
        url=url,
        site=site,
        page_pattern=PagePattern.SEARCH,
        strategies=[interactive_strat],
        query=query,
    )

    print(f"正在启动 {site} 的交互搜索测试，关键词: {query}...")

    result = runner._process_one(task)

    print(f"\n测试完成！")
    print(f"抓取结果: {'成功' if result.success else '失败'}")

    if result.products is not None:
        print(f"抓取到的商品数量: {len(result.products)}")
        if len(result.products) > 0:
            print("✅ 成功通过首页交互抓取到数据！")
            for i, p in enumerate(result.products[:3]):
                print(f"  {i + 1}. {p.title[:50]}... | {p.price}")
    else:
        print("❌ 未能抓取到商品列表。")

    runner.stop()


if __name__ == "__main__":
    try:
        test_etsy_interactive()
    except KeyboardInterrupt:
        pass
