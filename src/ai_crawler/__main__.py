import dspy

from ai_crawler import run_crawl
from ai_crawler.config import config


def _configure_dspy_lm():
    if not config.OPENAI_API_KEY:
        return

    base_url = config.OPENAI_BASE_URL
    model = config.MODEL_NAME

    if "api.openai.com" not in base_url and not model.startswith("openai/"):
        model_str = f"openai/{model}"
    else:
        model_str = model

    lm = dspy.LM(model_str, api_key=config.OPENAI_API_KEY, base_url=base_url)
    dspy.settings.configure(lm=lm)


_configure_dspy_lm()


ALL_SITES = [
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


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--sites", nargs="+", default=ALL_SITES[:3])
    parser.add_argument("--query", default="inflatable")
    parser.add_argument("--pages", type=int, default=1)
    args = parser.parse_args()

    result = run_crawl(
        sites=args.sites,
        query=args.query,
        pages=args.pages,
        proxy_username=config.THORDATA_RESIDENTIAL_USERNAME,
        proxy_password=config.THORDATA_RESIDENTIAL_PASSWORD,
        llm_api_key=config.OPENAI_API_KEY,
        captcha_api_key=config.TWO_CAPTCHA_API_KEY,
    )

    print(f"Products: {len(result.products)}")
    print(f"Success: {result.stats['tasks_success']}/{result.stats['tasks_total']}")
    print(f"Output: {result.output_file}")
    print(f"Traces: {result.traces_file}")
    print(f"Block types: {result.stats.get('block_types', [])}")


if __name__ == "__main__":
    main()
