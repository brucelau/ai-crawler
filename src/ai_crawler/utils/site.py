"""Site inference utilities for ai-crawler."""

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
