import sys
import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ai_crawler.runtime.orchestrator import SmartCrawlerRuntime, RuntimeOptions

FAILED_SITES = [
    "walmart",
    "homedepot",
    "bestbuy",
    "temu",
    "wayfair",
    "etsy",
    "kohls",
    "walmartmexico",
    "meijer",
    "samsclub",
    "bunnings",
    "dollargeneral",
    "action",
    "wowsports",
    "aosom",
    "familydollar",
    "menards",
    "acehardware",
    "qvc",
    "targetmexico",
    "costco",
]


def run_detailed_audit(sites):
    print(f"\033[1m开始深度摸排: 追踪 21 个失败站点的升级路径\033[0m")
    print("=" * 100)

    options = RuntimeOptions(
        concurrency=1,
        proxy_disabled=False,
        output_dir="output/detailed_audit",
        traces_dir="traces/detailed_audit",
    )

    runtime = SmartCrawlerRuntime(options)
    full_report = []

    for site in sites:
        print(f"\n[{site.upper(): <15}]", end=" ", flush=True)
        query = "lamp"

        try:
            tasks = runtime.build_search_tasks([site], query, pages=1)
            batch_result = runtime.crawl_tasks(tasks)

            task_res = batch_result.task_results[0] if batch_result.task_results else None
            final_success = task_res.success if task_res else False
            p_count = len(batch_result.products)

            core_res = getattr(task_res, "core_result", None)
            history_str = "未记录路径"

            if core_res:
                current_strat = core_res.strategy
                history_str = f"[Tier {current_strat.tier} {current_strat.render.value}]"

            print(f"{history_str} -> {'✅' if final_success else '❌'}")
            if final_success:
                print(f"    \033[32m最终结果: 成功 (抓取 {p_count} 个商品)\033[0m")
            else:
                b_type = getattr(core_res, "block_type", "unknown")
                print(f"    \033[31m最终结果: 失败 (Block: {b_type})\033[0m")

            full_report.append(
                {
                    "site": site,
                    "success": final_success,
                    "product_count": p_count,
                    "tier": current_strat.tier if core_res else "N/A",
                    "render": current_strat.render.value if core_res else "N/A",
                    "block_type": str(b_type) if core_res else "N/A",
                }
            )

        except Exception as e:
            print(f"\033[33m运行异常: {str(e)[:50]}\033[0m")

    with open("detailed_path_report.json", "w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 100)
    print(f"\033[1m摸排完成！路径报告已保存至: detailed_path_report.json\033[0m")


if __name__ == "__main__":
    run_detailed_audit(FAILED_SITES)
