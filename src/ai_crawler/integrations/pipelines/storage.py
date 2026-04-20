import csv
import json
from pathlib import Path

try:
    from itemadapter import ItemAdapter
except ModuleNotFoundError:

    class ItemAdapter:  # type: ignore[override]
        def __init__(self, item):
            self.item = item

        def get(self, key, default=None):
            return self.item.get(key, default)

        def __getitem__(self, key):
            return self.item[key]

        def __setitem__(self, key, value):
            self.item[key] = value

        def __iter__(self):
            return iter(self.item.items())

        def items(self):
            return self.item.items()

        def __len__(self):
            return len(self.item)


class DuplicatesPipeline:
    def __init__(self):
        self.seen_urls = set()
        self.seen_asins = {}

    def process_item(self, item):
        adapter = ItemAdapter(item)
        url = adapter.get("url", "")
        asin = adapter.get("asin", "")

        if url and url in self.seen_urls:
            return item

        if asin:
            site = adapter.get("source", "")
            key = f"{site}:{asin}"
            if key in self.seen_asins:
                return item
            self.seen_asins[key] = True

        if url:
            self.seen_urls.add(url)

        return item


class ProductValidationPipeline:
    def process_item(self, item):
        adapter = ItemAdapter(item)
        title = adapter.get("title", "")

        if not title or len(title) < 5:
            return item

        price = adapter.get("price", "")
        if price and not any(c.isdigit() for c in str(price)):
            adapter["price"] = ""

        return item


class ProductStoragePipeline:
    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._date_str = __import__("time").strftime("%Y-%m-%d")
        self._site_files: dict[str, tuple] = {}
        self._site_writers: dict[str, csv.DictWriter] = {}
        self._site_fields: dict[str, list[str]] = {}
        self.spider_name = "unknown"

    @classmethod
    def from_crawler(cls, crawler):
        output_dir = crawler.settings.get("OUTPUT_DIR", "output")
        instance = cls(output_dir=output_dir)
        instance._crawler = crawler
        return instance

    def open_spider(self, spider):
        pass

    def close_spider(self, spider):
        for site, (json_f, csv_f) in self._site_files.items():
            if hasattr(json_f, "close"):
                json_f.close()
            if hasattr(csv_f, "close"):
                csv_f.close()

    def process_item(self, item):
        adapter = ItemAdapter(item)
        data = dict(adapter)

        spider = getattr(self, "_crawler", None) and self._crawler.spider
        spider_name = getattr(spider, "name", "unknown") if spider else self.spider_name

        site = adapter.get("source", "") or spider_name

        if site not in self._site_files:
            json_file, csv_file = self._get_filepath(site)
            json_handle = open(json_file, "w", encoding="utf-8")
            csv_handle = open(csv_file, "w", newline="", encoding="utf-8")
            self._site_files[site] = (json_handle, csv_handle)

        json_handle, csv_handle = self._site_files[site]
        json_handle.write(json.dumps(data, ensure_ascii=False) + "\n")

        if site not in self._site_writers:
            fields = list(data.keys())
            self._site_fields[site] = fields
            writer = csv.DictWriter(csv_handle, fieldnames=fields)
            writer.writeheader()
            self._site_writers[site] = writer

        try:
            self._site_writers[site].writerow(data)
        except Exception:
            pass

        return item

    def _get_filepath(self, site: str) -> tuple[Path, Path]:
        json_file = self.output_dir / f"{site}_{self._date_str}.jsonl"
        csv_file = self.output_dir / f"{site}_{self._date_str}.csv"
        return json_file, csv_file
