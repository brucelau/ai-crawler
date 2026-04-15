from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

from ai_crawler.runtime.models import RuntimeTaskResult
from ai_crawler.models.product import Product


class ProductOutputWriter:
    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write(self, task_results: list[RuntimeTaskResult]) -> list[str]:
        grouped: dict[str, list[Product]] = defaultdict(list)
        for result in task_results:
            if result.products:
                grouped[result.task.site].extend(result.products)

        return self.write_products(grouped)

    def write_products(self, grouped: dict[str, list[Product]]) -> list[str]:

        date_str = time.strftime("%Y-%m-%d")
        output_files: list[str] = []
        for site, products in grouped.items():
            jsonl_file = self.output_dir / f"{site}_{date_str}.jsonl"
            with open(jsonl_file, "w", encoding="utf-8") as handle:
                for product in products:
                    handle.write(json.dumps(product.to_dict(), ensure_ascii=False) + "\n")
            output_files.append(str(jsonl_file))
        return output_files
