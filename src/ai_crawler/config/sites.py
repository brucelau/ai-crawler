"""Site configuration data - extracted from strategy.py and orchestrator.py.

This module provides site-specific configuration for the crawler:
- SUPPORTED_SITES: URL templates for each supported site
- TIER_CONFIGS: Tier-level CrawlPolicy defaults
- SITE_TIER_DEFAULTS: Default tier per site/pattern
- URL_PATTERNS: Full CrawlPolicy chains per site/pattern
- PATTERNS: Regex patterns for URL matching

The configuration data is kept in Python for flexibility with complex objects.
For future migration to YAML, a _load_from_yaml() function is provided.
"""

from ai_crawler.spider.runtime.crawl import CrawlPolicy, PagePattern, ProxyType, RenderType


SUPPORTED_SITES: dict[str, str] = {
    "amazon": "https://www.amazon.com/s?k={query}",
    "walmart": "https://www.walmart.com/search?q={query}",
    "target": "https://www.target.com/s?searchTerm={query}",
    "ebay": "https://www.ebay.com/sch/i.html?_nkw={query}",
    "menards": "https://www.menards.com/main/search.html?query={query}",
    "lowes": "https://www.lowes.com/search?searchTerm={query}",
    "homedepot": "https://www.homedepot.com/s/?keyword={query}",
    "acehardware": "https://www.acehardware.com/search?query={query}",
    "wayfair": "https://www.wayfair.com/keyword.php?keyword={query}",
    "michaels": "https://www.michaels.com/search?search={query}",
    "temu": "https://www.temu.com/search?search_key={query}",
    "etsy": "https://www.etsy.com/search?q={query}",
    "bestbuy": "https://www.bestbuy.com/site/search?search={query}",
    "costco": "https://www.costco.com/search?search={query}",
        "qvc": "https://www.qvc.com/catalog/psearch.html?keyword={query}&sa=submit",
    "kohls": "https://www.kohls.com/search.jsp?search={query}",
    "mercadolibre": "https://listado.mercadolibre.com.mx/{query}",
    "walmartmexico": "https://www.walmartmexico.com.mx/search?term={query}",
    "intexcorp": "https://www.intexcorp.com/search?q={query}",
    "meijer": "https://www.meijer.com/shopping/search/{query}",
    "fivebelow": "https://www.fivebelow.com/search?q={query}",
    "samsclub": "https://www.samsclub.com/search?query={query}",
    "bunnings": "https://www.bunnings.com.au/search?query={query}",
    "dollargeneral": "https://www.dollargeneral.com/search?text={query}",
    "action": "https://www.action.com/search?q={query}",
    "academy": "https://www.academy.com/shop/search?q={query}",
    "wowsports": "https://wowsports.com/search?q={query}",
    "coppel": "https://www.coppel.com/search?term={query}",
    "aosom": "https://www.aosom.com/search?q={query}",
    "familydollar": "https://www.familydollar.com/search?q={query}",
    "costway": "https://www.costway.com/search?q={query}",
}


TIER_CONFIGS: dict[int, dict] = {
    1: {
        "render": RenderType.NONE,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (2, 5),
        "use_human_scroll": False,
        "change_ua": False,
        "use_cookies": False,
    },
    2: {
        "render": RenderType.CLOUDSCRAPER,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (3, 6),
        "use_human_scroll": False,
        "change_ua": False,
        "use_cookies": True,
    },
    3: {
        "render": RenderType.LIGHTPAND,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (2, 5),
        "use_human_scroll": True,
        "change_ua": False,
        "use_cookies": False,
    },
    4: {
        "render": RenderType.PLAYWRIGHT,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (3, 8),
        "use_human_scroll": True,
        "change_ua": False,
        "use_cookies": False,
    },
    5: {
        "render": RenderType.CAMOUFOX,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (3, 8),
        "use_human_scroll": True,
        "change_ua": True,
        "use_cookies": True,
    },
    6: {
        "render": RenderType.CLOUDERA,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (5, 10),
        "use_human_scroll": True,
        "change_ua": True,
        "use_cookies": True,
    },
    7: {
        "render": RenderType.SELENIUMBASE,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (5, 10),
        "use_human_scroll": True,
        "change_ua": True,
        "use_cookies": True,
    },
    8: {
        "render": RenderType.CLOAKBROWSER,
        "proxy": ProxyType.THORDATA_DEDICATED,
        "delay_after": (5, 10),
        "use_human_scroll": True,
        "change_ua": True,
        "use_cookies": True,
    },
}


SITE_TIER_DEFAULTS: dict[str, dict[PagePattern, int]] = {
    "amazon": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 4,
        PagePattern.REVIEW: 4,
    },
    "walmart": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 4,
    },
    "target": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 3,
    },
    "ebay": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 3,
    },
    "menards": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 4,
    },
    "lowes": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 3,
    },
    "homedepot": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 3,
    },
    "acehardware": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 3,
    },
    "wayfair": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 3,
    },
    "michaels": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 3,
    },
    "temu": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 1,
    },
    "etsy": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 3,
    },
    "bestbuy": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 3,
    },
    "costco": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 3,
    },
    "qvc": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 3,
    },
    "kohls": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 3,
    },
    "mercadolibre": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 3,
    },
    "walmartmexico": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 3,
    },
    "intexcorp": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 3,
    },
    "meijer": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 3,
    },
    "fivebelow": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 1,
    },
    "samsclub": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 3,
    },
    "bunnings": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 3,
    },
    "dollargeneral": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 1,
    },
    "action": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 1,
    },
    "academy": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 3,
    },
    "wowsports": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 1,
    },
    "coppel": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 3,
    },
    "aosom": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 1,
    },
    "familydollar": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 1,
    },
    "costway": {
        PagePattern.SEARCH: 7,
        PagePattern.DETAIL: 1
    }
}

def get_site_tier(site: str, page_pattern: PagePattern) -> int:
    """获取站点-页面模式对应的默认层级"""
    return SITE_TIER_DEFAULTS.get(site, {}).get(page_pattern, 1)


URL_PATTERNS: dict[str, dict[PagePattern, list[CrawlPolicy]]] = {
    "amazon": {
        PagePattern.SEARCH: [
            CrawlPolicy(
                tier=8,
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_interactive_search=True,
                use_human_scroll=True,
            ),
            CrawlPolicy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.CLOUDERA,
                use_cookies=True,
                change_ua=True,
                use_human_scroll=True,
            ),
            CrawlPolicy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlPolicy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(8, 15)
            ),
            CrawlPolicy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlPolicy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                change_ua=True,
                use_human_scroll=True,
            ),
            CrawlPolicy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.CAMOUFOX,
                use_cookies=True,
                change_ua=True,
                use_human_scroll=True,
            ),
        ],
        PagePattern.DETAIL: [
            CrawlPolicy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlPolicy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlPolicy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
        ],
        PagePattern.SELLER: [
            CrawlPolicy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlPolicy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.REVIEW: [
            CrawlPolicy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 6)
            ),
            CrawlPolicy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
        PagePattern.UNKNOWN: [
            CrawlPolicy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
            CrawlPolicy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
        ],
    },
    "walmart": {
        PagePattern.SEARCH: [
            CrawlPolicy(
                tier=4,
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_interactive_search=True,
                use_human_scroll=True,
            ),
            CrawlPolicy(
                tier=6,
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.CLOUDERA,
                use_cookies=True,
                change_ua=True,
                use_human_scroll=True,
            ),
            CrawlPolicy(
                tier=1,
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(3, 8)
            ),
            CrawlPolicy(
                tier=4,
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlPolicy(
                tier=5,
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, use_cookies=True
            ),
        ],
        PagePattern.DETAIL: [
            CrawlPolicy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlPolicy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlPolicy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
        ],
    },
    "target": {
        PagePattern.SEARCH: [
            CrawlPolicy(
                tier=4,
                render=RenderType.PLAYWRIGHT,
                proxy=ProxyType.THORDATA_DEDICATED,
                use_interactive_search=True,
                use_human_scroll=True,
            ),
            CrawlPolicy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlPolicy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.CAMOUFOX, change_ua=True
            ),
            CrawlPolicy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.SELENIUMBASE,
                use_cookies=True,
                change_ua=True,
                use_human_scroll=True,
            ),
        ],
        PagePattern.DETAIL: [
            CrawlPolicy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 5)
            ),
            CrawlPolicy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlPolicy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
        ],
    },
    "ebay": {
        PagePattern.SEARCH: [
            CrawlPolicy(
                tier=4,
                render=RenderType.PLAYWRIGHT,
                proxy=ProxyType.THORDATA_DEDICATED,
                use_interactive_search=True,
                use_human_scroll=True,
            ),
            CrawlPolicy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.PLAYWRIGHT,
                use_human_scroll=True,
            ),
            CrawlPolicy(
                proxy=ProxyType.THORDATA_DEDICATED,
                render=RenderType.SELENIUMBASE,
                use_cookies=True,
                change_ua=True,
                use_human_scroll=True,
            ),
        ],
        PagePattern.DETAIL: [
            CrawlPolicy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(2, 4)
            ),
            CrawlPolicy(proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.PLAYWRIGHT),
        ],
        PagePattern.UNKNOWN: [
            CrawlPolicy(
                proxy=ProxyType.THORDATA_DEDICATED, render=RenderType.NONE, delay_after=(5, 10)
            ),
        ],
    },
}


PATTERNS: dict[str, dict[PagePattern, list[str]]] = {
    "amazon": {
        PagePattern.SEARCH: [r"/s\?", r"/s/\?", r"/gp/search", r"/hw/shop"],
        PagePattern.DETAIL: [r"/dp/[A-Z0-9]{10}", r"/gp/product/", r"/dp/"],
        PagePattern.SELLER: [r"/stores/", r"/sp/", r"/sell/"],
        PagePattern.REVIEW: [r"/product-reviews/", r"/gp/aw/review/", r"/hz/r/cr/"],
    },
    "walmart": {
        PagePattern.SEARCH: [r"/search\?", r"/search\.php"],
        PagePattern.DETAIL: [r"/ip/[A-Za-z0-9\-]+/\d+", r"/-/ip/"],
        PagePattern.SELLER: [r"/seller/", r"/store/"],
    },
    "target": {
        PagePattern.SEARCH: [r"/s\?", r"/search\?"],
        PagePattern.DETAIL: [r"/-/A-", r"/p/", r"/A-"],
        PagePattern.SELLER: [r"/store/", r"/sl/"],
    },
    "ebay": {
        PagePattern.SEARCH: [r"/sch/i\.html", r"/sch/"],
        PagePattern.DETAIL: [r"/itm/\d+", r"/itm/[A-Za-z0-9\-]+\d{9,}"],
        PagePattern.SELLER: [r"/str/", r"/usr/", r"/seller/"],
    },
    "homedepot": {
        PagePattern.SEARCH: [r"/search\?", r"/search\.html", r"/catalog/search"],
        PagePattern.DETAIL: [r"/p/", r"/ip/"],
    },
    "lowes": {
        PagePattern.SEARCH: [r"/search\?", r"/search\.html"],
        PagePattern.DETAIL: [r"/p/", r"/product/"],
    },
    "bestbuy": {
        PagePattern.SEARCH: [r"/site/.*search\?", r"/search\?"],
        PagePattern.DETAIL: [r"/site/.*\.p\?"],
    },
    "costco": {
        PagePattern.SEARCH: [r"\.costco\.com/.*search", r"\.costco\.com/c/"],
        PagePattern.DETAIL: [r"\.costco\.com/.*product\.html"],
    },
}


def _load_from_yaml() -> dict:
    """Load site configuration from YAML file.

    This is a future migration path. Currently returns empty dict.
    Requires complete YAML serialization of all config including URL_PATTERNS.
    """
    try:
        import yaml
        from pathlib import Path

        yaml_path = Path(__file__).parent / "sites.yaml"
        if yaml_path.exists():
            with open(yaml_path) as f:
                return yaml.safe_load(f)
    except ImportError:
        pass
    return {}


DOMAIN_TO_SITE: dict[str, str] = {
    "amazon.": "amazon",
    "walmart.": "walmart",
    "target.": "target",
    "ebay.": "ebay",
    "wowsports.": "wowsports",
    "costway.": "costway",
    "wayfair.": "wayfair",
    "homedepot.": "homedepot",
    "lowes.": "lowes",
    "bestbuy.": "bestbuy",
    "costco.": "costco",
    "temu.": "temu",
    "etsy.": "etsy",
    "menards.": "menards",
    "kohls.": "kohls",
    "qvc.": "qvc",
    "michaels.": "michaels",
    "samsclub.": "samsclub",
    "bunnings.": "bunnings",
    "mercadolibre.": "mercadolibre",
    "acehardware.": "acehardware",
    "intexcorp.": "intexcorp",
    "meijer.": "meijer",
    "fivebelow.": "fivebelow",
    "dollargeneral.": "dollargeneral",
    "action.": "action",
    "academy.": "academy",
    "coppel.": "coppel",
    "aosom.": "aosom",
    "familydollar.": "familydollar",
}


def infer_site_from_url(url: str) -> str:
    for domain, site in DOMAIN_TO_SITE.items():
        if domain in url:
            return site
    return "unknown"


def infer_site_from_url_or_empty(url: str) -> str:
    for domain, site in DOMAIN_TO_SITE.items():
        if domain in url:
            return site
    return ""


__all__ = [
    "SUPPORTED_SITES",
    "TIER_CONFIGS",
    "SITE_TIER_DEFAULTS",
    "URL_PATTERNS",
    "PATTERNS",
    "DOMAIN_TO_SITE",
    "infer_site_from_url",
    "infer_site_from_url_or_empty",
]
