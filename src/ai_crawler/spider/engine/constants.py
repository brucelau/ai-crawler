from ai_crawler.spider.runtime.crawl import PagePattern, RenderType


RENDER_COST = {
    RenderType.NONE.value: 1,
    RenderType.CLOUDSCRAPER.value: 2,
    RenderType.LIGHTPAND.value: 3,
    RenderType.PLAYWRIGHT.value: 4,
    RenderType.CAMOUFOX.value: 5,
    RenderType.CLOUDERA.value: 6,
    RenderType.SELENIUMBASE.value: 7,
    RenderType.CLOAKBROWSER.value: 8,
    RenderType.KAMELEO.value: 9,
}

UC_SEARCH_ALLOWLIST = {"amazon", "walmart"}

ANTI_BOT_PENALTIES = {
    ("vendors", "browser_error"): 25,
    ("mechanisms", "proxy_transport_error"): 20,
    ("mechanisms", "browser_transport_error"): 15,
    ("mechanisms", "js_challenge"): 10,
    ("mechanisms", "captcha_gate"): 12,
    ("mechanisms", "bot_score_gate"): 10,
}

SCORE_WEIGHTS = {
    "success": 100,
    "yield": 3,
    "order_base": 20,
    "order_decay": 2,
    "latency_per_sec": 0.8,
    "http_timeout_rate": 20,
    "captcha_rate": 25,
    "cloudflare_rate": 15,
    "bot_rate": 15,
    "cost_multiplier": 2,
    "instability_threshold": 3,
    "instability_penalty": 10,
}

CONTEXTUAL_BONUSES = {
    (PagePattern.SEARCH.value, RenderType.CAMOUFOX.value): 12,
    (PagePattern.SEARCH.value, RenderType.CLOAKBROWSER.value): 14,
    (PagePattern.SEARCH.value, RenderType.SELENIUMBASE.value): 6,
    (PagePattern.SEARCH.value, RenderType.CLOUDERA.value): 35,
}
CONTEXTUAL_BONUSES_SUCCESS = {
    (PagePattern.SEARCH.value, RenderType.CAMOUFOX.value): 8,
    (PagePattern.SEARCH.value, RenderType.CLOAKBROWSER.value): 10,
    (PagePattern.SEARCH.value, RenderType.SELENIUMBASE.value): 4,
}
CLOAKBROWSER_AMAZON_TARGET_BONUS = 8
CLOUDERA_NON_ALLOWLIST_PENALTY = 10
