import sys
import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ai_crawler.runtime.orchestrator import SmartCrawlerRuntime, RuntimeOptions

SITES = [
    "amazon",
    "walmart",
    "target",
    "ebay",
    "menards",
    "lowes",
    "homedepot",
    "acehardware",
    "wayfair",
    "michaels",
    "temu",
    "etsy",
    "bestbuy",
    "costco",
    "qvc",
    "kohls",
    "mercadolibre",
    "walmartmexico",
    "intexcorp",
    "meijer",
    "fivebelow",
    "samsclub",
    "bunnings",
    "dollargeneral",
    "action",
    "academy",
    "wowsports",
    "coppel",
    "aosom",
    "familydollar",
    "costway",
]


def run_audit_batch(start_idx, count):
    end_idx = min(start_idx + count, len(SITES))
    batch_sites = SITES[start_idx:end_idx]

    print(
        f"\033[1m开始摸排批次: {start_idx + 1} 到 {end_idx} (共 {len(batch_sites)} 个站点)\033[0m"
    )
    print("-" * 80)

    options = RuntimeOptions(
        concurrency=1, proxy_disabled=False, output_dir="output/audit", traces_dir="traces/audit"
    )

    runtime = SmartCrawlerRuntime(options)
    results = []

    for site in batch_sites:
        print(f"[{site: <15}] 正在测试... ", end="", flush=True)
        query = "lamp" if site not in ["wowsports", "academy"] else "tent"

        start_time = time.time()
        try:
            tasks = runtime.build_search_tasks([site], query, pages=1)
            batch_result = runtime.crawl_tasks(tasks)

            duration = time.time() - start_time
            task_res = batch_result.task_results[0] if batch_result.task_results else None
            success = task_res.success if task_res else False
            p_count = len(batch_result.products)
            tier = task_res.strategy.tier if task_res and task_res.strategy else "N/A"

            status = "✅ 成功" if success and p_count > 0 else "❌ 失败"
            print(f"{status} | Tier: {tier} | 商品数: {p_count} | 耗时: {duration:.1f}s")

            results.append(
                {
                    "site": site,
                    "success": success,
                    "tier": tier,
                    "product_count": p_count,
                    "duration": duration,
                    "error": task_res.error if task_res else "No task result",
                }
            )
        except Exception as e:
            print(f"❌ 异常: {str(e)[:30]}")
            results.append(
                {
                    "site": site,
                    "success": False,
                    "tier": "Error",
                    "product_count": 0,
                    "error": str(e),
                }
            )

    return results


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=5)
    args = parser.parse_args()

    batch_results = run_audit_batch(args.start, args.count)

    report_path = Path("audit_results_batch.json")
    all_data = []
    if report_path.exists():
        try:
            all_data = json.loads(report_path.read_text())
        except:
            pass

    all_data.extend(batch_results)
    report_path.write_text(json.dumps(all_data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
