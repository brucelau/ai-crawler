import hashlib
from pathlib import Path
import json
import csv

from itemadapter import ItemAdapter, is_item
from scrapy.pipelines.files import FilesPipeline


class DuplicatesPipeline:
    def __init__(self):
        self.seen_urls = set()
        self.seen_asins = {}

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        url = adapter.get("url", "")
        asin = adapter.get("asin", "")

        if url and url in self.seen_urls:
            spider.logger.debug(f"Duplicate URL: {url}")
            return item

        if asin:
            site = adapter.get("source", "")
            key = f"{site}:{asin}"
            if key in self.seen_asins:
                spider.logger.debug(f"Duplicate ASIN: {key}")
                return item
            self.seen_asins[key] = True

        if url:
            self.seen_urls.add(url)

        return item


class ProductValidationPipeline:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        title = adapter.get("title", "")

        if not title or len(title) < 5:
            spider.logger.warning(
                f"Item rejected: no title or title too short - {adapter.get('url')}"
            )
            return item

        price = adapter.get("price", "")
        if price and not any(c.isdigit() for c in str(price)):
            adapter["price"] = ""

        return item


class ProductStoragePipeline:
    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.json_file = self.output_dir / f"products_{int(__import__('time').time())}.jsonl"
        self.csv_file = self.output_dir / f"products_{int(__import__('time').time())}.csv"
        self._csv_written = False
        self._fields: list[str] = []

    def open_spider(self, spider):
        self.json_handle = open(self.json_file, "w", encoding="utf-8")
        self.csv_handle = open(self.csv_file, "w", newline="", encoding="utf-8")
        spider.logger.info(f"Storage opened: {self.json_file}, {self.csv_file}")

    def close_spider(self, spider):
        self.json_handle.close()
        self.csv_handle.close()
        spider.logger.info(f"Storage closed: {self.json_file}, {self.csv_file}")

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        data = dict(adapter)

        self.json_handle.write(json.dumps(data, ensure_ascii=False) + "\n")

        if not self._csv_written:
            self._fields = list(data.keys())
            self._writer = csv.DictWriter(self.csv_handle, fieldnames=self._fields)
            self._writer.writeheader()
            self._csv_written = True

        try:
            self._writer.writerow(data)
        except Exception:
            pass

        return item
