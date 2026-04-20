import sys
import os
import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent / "src"))

from ai_crawler.runtime.orchestrator import SmartCrawlerRuntime, RuntimeOptions


async def test_bestbuy_autoupgrade():
    print("--- 验证 Best Buy 自动升级策略 ---")

    options = RuntimeOptions(
        concurrency=1,
        proxy_disabled=False,
        output_dir="output/autoupgrade",
        traces_dir="traces/autoupgrade",
    )

    runtime = SmartCrawlerRuntime(options)

    site = "bestbuy"
    query = "laptop"

    print(f"正在启动 {site} 任务...")

    tasks = runtime.build_search_tasks([site], query, pages=1)

    result = runtime.crawl_tasks(tasks)

    print(f"\n任务结束状态: {'成功' if result.stats.get('tasks_success', 0) > 0 else '失败'}")
    print(f"抓取到的商品数量: {len(result.products)}")

    if result.products:
        for i, p in enumerate(result.products[:3]):
            print(f"  {i + 1}. {p.title[:50]}... | {p.price}")
    else:
        print("提示: 若依然失败，说明该站点的反爬强度超过了当前 Tier 8 配置。")


if __name__ == "__main__":
    try:
        asyncio.run(test_bestbuy_autoupgrade())
    except KeyboardInterrupt:
        pass
