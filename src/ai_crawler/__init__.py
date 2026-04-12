from dataclasses import dataclass, field
import json
import time
from pathlib import Path

from ai_crawler.config import setup_logging
from ai_crawler.core import (
    CrawlRunner,
    CrawlTask,
    CrawlStrategy,
    ProxyType,
    RenderType,
    TraceStore,
)
from ai_crawler.spiders import EXTRACTORS, Product
from ai_crawler.core.runner import CrawlResult


@dataclass
class ProductsResult:
    products: list[Product]
    results: list[CrawlResult]
    stats: dict
    output_files: list[str]
    traces_file: str


def run_crawl(
    sites: list[str],
    query: str,
    pages: int,
    proxy_username: str = "",
    proxy_password: str = "",
    llm_api_key: str | None = None,
    captcha_api_key: str | None = None,
    output_dir: str = "output",
    traces_dir: str = "traces",
    max_ip_retries: int = 3,
    proxy_disabled: bool = False,
) -> ProductsResult:

    from ai_crawler.config import config

    setup_logging(log_level=config.LOG_LEVEL, log_dir=config.LOG_DIR, log_file=config.LOG_FILE)

    from ai_crawler.core.runtime.introspection import get_system_facts

    system_facts = get_system_facts()

    dynamic_profile = {}
    if llm_api_key:
        import os
        from ai_crawler.core.llm.dspy_model import ProfileGenerator

        try:
            profile_gen = ProfileGenerator()
            res = profile_gen(system_facts=system_facts)
            dynamic_profile = {
                "user_agent": res.user_agent,
                "sec_ch_ua_platform": res.sec_ch_ua_platform,
                "sec_ch_ua": res.sec_ch_ua,
                "stealth_args": res.stealth_args,
                "curl_impersonate_target": res.curl_impersonate_target,
                "timezone_id": res.timezone_id,
                "locale": res.locale,
                "viewport": res.viewport,
                "mouse_behavior": res.mouse_behavior,
            }
            print(
                f"[Introspection] LLM applied profile for: {dynamic_profile['sec_ch_ua_platform']}"
            )
        except Exception as e:
            print(f"[Introspection] LLM profile generation failed, using defaults: {e}")

    tasks = []
    for site in sites:
        if site not in EXTRACTORS:
            continue
        for page in range(1, pages + 1):
            url = _build_url(site, query, page)
            tasks.append(CrawlTask.create_from_tier(url=url, site=site))

    trace_store = TraceStore(storage_dir=traces_dir)

    captcha_solver = None
    if captcha_api_key:
        from ai_crawler.captcha import CaptchaSolver

        captcha_solver = CaptchaSolver(captcha_api_key)

    runner = CrawlRunner(
        proxy_username=proxy_username,
        proxy_password=proxy_password,
        llm_api_key=llm_api_key,
        concurrency=1,
        trace_store=trace_store,
        dynamic_profile=dynamic_profile,
        captcha_solver=captcha_solver,
        max_ip_retries=max_ip_retries,
        proxy_disabled=proxy_disabled,
    )

    if llm_api_key:
        from ai_crawler.core.llm.dspy_model import InitialTierSelector

        try:
            tier_selector = InitialTierSelector()
            runner.set_initial_tier_selector(tier_selector)
            print("[LLM] Initial tier selector enabled")
        except Exception as e:
            print(f"[LLM] Failed to initialize tier selector: {e}")

    runner.add_tasks(tasks)
    results = runner.run()

    all_products = []
    for r in results:
        if r.products:
            all_products.extend(r.products)

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    date_str = time.strftime("%Y-%m-%d")

    site_products: dict[str, list[Product]] = {}
    for r in results:
        if r.products:
            site_products.setdefault(r.site, []).extend(r.products)

    output_files = []
    for site, products in site_products.items():
        jsonl_file = out_path / f"{site}_{date_str}.jsonl"
        with open(jsonl_file, "w", encoding="utf-8") as f:
            for p in products:
                f.write(json.dumps(p.to_dict(), ensure_ascii=False) + "\n")
        output_files.append(str(jsonl_file))

    traces_file = str(trace_store._session_file)

    stats = trace_store.stats()
    stats["products_crawled"] = len(all_products)
    stats["tasks_total"] = len(results)
    stats["tasks_success"] = sum(1 for r in results if r.success)

    return ProductsResult(
        products=all_products,
        results=results,
        stats=stats,
        output_files=output_files,
        traces_file=traces_file,
    )


def _build_url(site: str, query: str, page: int) -> str:
    q = query.replace(" ", "+")
    base = {
        "amazon": f"https://www.amazon.com/s?k={q}",
        "walmart": f"https://www.walmart.com/search?q={q}",
        "target": f"https://www.target.com/s?searchTerm={q}",
        "ebay": f"https://www.ebay.com/sch/i.html?_nkw={q}",
        "menards": f"https://www.menards.com/main/search.html?search={q}",
        "lowes": f"https://www.lowes.com/search?searchTerm={q}",
        "homedepot": f"https://www.homedepot.com/search?text={q}",
        "acehardware": f"https://www.acehardware.com/search?query={q}",
        "wayfair": f"https://www.wayfair.com/keyword.php?keyword={q}",
        "michaels": f"https://www.michaels.com/search?search={q}",
        "temu": f"https://www.temu.com/search?search_key={q}",
        "etsy": f"https://www.etsy.com/search?q={q}",
        "bestbuy": f"https://www.bestbuy.com/site/search?search={q}",
        "costco": f"https://www.costco.com/search?search={q}",
        "qvc": f"https://www.qvc.com/forms/search/results?baseCountry=us&language=en-US&search={q}",
        "kohls": f"https://www.kohls.com/search.jsp?search={q}",
        "mercadolibre": f"https://listado.mercadolibre.com.mx/{q}",
        "walmartmexico": f"https://www.walmartmexico.com.mx/search?term={q}",
        "intexcorp": f"https://www.intexcorp.com/search?q={q}",
        "meijer": f"https://www.meijer.com/shopping/search/{q}",
        "fivebelow": f"https://www.fivebelow.com/search?q={q}",
        "samsclub": f"https://www.samsclub.com/search?query={q}",
        "bunnings": f"https://www.bunnings.com.au/search?query={q}",
        "dollargeneral": f"https://www.dollargeneral.com/search?text={q}",
        "action": f"https://www.action.com/search?q={q}",
        "academy": f"https://www.academy.com/shop/search?q={q}",
        "wowsports": f"https://wowsports.com/search?q={q}",
        "coppel": f"https://www.coppel.com/search?term={q}",
        "aosom": f"https://www.aosom.com/search?q={q}",
        "familydollar": f"https://www.familydollar.com/search?q={q}",
        "costway": f"https://www.costway.com/search?q={q}",
    }
    url = base.get(site, "")
    if page > 1 and url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}page={page}"
    return url


__all__ = [
    "CrawlRunner",
    "CrawlTask",
    "CrawlStrategy",
    "ProxyType",
    "RenderType",
    "TraceStore",
    "CrawlResult",
    "ProductsResult",
    "EXTRACTORS",
    "Product",
    "run_crawl",
    "setup_logging",
]
