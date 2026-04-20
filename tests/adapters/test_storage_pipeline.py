import time

from ai_crawler.integrations.pipelines.storage import ProductStoragePipeline


def test_product_storage_pipeline_writes_separate_site_files(tmp_path):
    pipeline = ProductStoragePipeline(output_dir=str(tmp_path))

    pipeline.process_item({"source": "amazon", "title": "Chair", "url": "https://a.example"})
    pipeline.process_item({"source": "walmart", "title": "Table", "url": "https://w.example"})
    pipeline.close_spider(None)

    date_str = time.strftime("%Y-%m-%d")
    assert (tmp_path / f"amazon_{date_str}.jsonl").exists()
    assert (tmp_path / f"amazon_{date_str}.csv").exists()
    assert (tmp_path / f"walmart_{date_str}.jsonl").exists()
    assert (tmp_path / f"walmart_{date_str}.csv").exists()
