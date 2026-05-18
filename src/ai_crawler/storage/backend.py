from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Protocol

from ai_crawler.core.types import RuntimeTaskResult
from ai_crawler.core.types import Product


class StorageBackend(Protocol):
    """Minimal storage abstraction so output can target local disk or a Mirage Workspace."""

    def makedirs(self, path: str) -> None: ...
    def write_text(self, path: str, content: str) -> None: ...
    def append_text(self, path: str, content: str) -> None: ...
    def read_text(self, path: str) -> str: ...
    def exists(self, path: str) -> bool: ...


class LocalStorageBackend:
    """Thin wrapper around local filesystem — same behaviour as before."""

    def makedirs(self, path: str) -> None:
        os.makedirs(path, exist_ok=True)

    def write_text(self, path: str, content: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def append_text(self, path: str, content: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)

    def read_text(self, path: str) -> str:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def exists(self, path: str) -> bool:
        return os.path.exists(path)


class ProductOutputWriter:
    def __init__(self, output_dir: str = "output", backend: StorageBackend | None = None):
        self.output_dir = output_dir
        self.backend = backend or LocalStorageBackend()
        self.backend.makedirs(output_dir)

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
            file_name = f"{site}_{date_str}.jsonl"
            file_path = os.path.join(self.output_dir, file_name)
            lines = "".join(
                json.dumps(product.to_dict(), ensure_ascii=False) + "\n"
                for product in products
            )
            self.backend.write_text(file_path, lines)
            output_files.append(file_path)
        return output_files
