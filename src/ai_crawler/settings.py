from ai_crawler.config import config

BOT_NAME = "ai_crawler"

SPIDER_MODULES = ["ai_crawler.scrapy_spiders"]
NEWSPIDER_MODULE = "ai_crawler.scrapy_spiders"

DOWNLOADER_MIDDLEWARES = {
    "ai_crawler.middlewares.proxy.ProxyMiddleware": 100,
    "ai_crawler.middlewares.tier_strategy.TierStrategyMiddleware": 200,
    "ai_crawler.middlewares.captcha.CaptchaMiddleware": 250,
    "ai_crawler.middlewares.proxy.HumanBehaviorMiddleware": 400,
    "ai_crawler.middlewares.memory.SiteMemoryMiddleware": 450,
}

SPIDER_MIDDLEWARES = {
    "ai_crawler.middlewares.proxy.HumanBehaviorMiddleware": 543,
    "ai_crawler.middlewares.memory.CrawlQueueMiddleware": 550,
}

DOWNLOAD_DELAY = 5
RANDOMIZE_DOWNLOAD_DELAY = True
CONCURRENT_REQUESTS_PER_DOMAIN = 2
RETRY_TIMES = 3
COOKIES_ENABLED = True

ITEM_PIPELINES = {
    "ai_crawler.pipelines.storage.DuplicatesPipeline": 100,
    "ai_crawler.pipelines.storage.ProductValidationPipeline": 200,
    "ai_crawler.pipelines.storage.ProductStoragePipeline": 300,
}

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 3
AUTOTHROTTLE_MAX_DELAY = 60
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0

FEEDS = {
    "output/products_%(time)s.jsonl": {
        "format": "jsonlines",
        "encoding": "utf-8",
    },
    "output/products_%(time)s.csv": {
        "format": "csv",
        "encoding": "utf-8",
    },
}

LOG_LEVEL = config.LOG_LEVEL

REQUEST_TIMEOUT = config.REQUEST_TIMEOUT
PAGE_LOAD_TIMEOUT = config.PAGE_LOAD_TIMEOUT

RENDER_ENGINE = "playwright"

LLM_API_KEY = config.OPENAI_API_KEY
LLM_PROVIDER = "openai"

CAPTCHA_API_KEY = config.TWO_CAPTCHA_API_KEY

TRACE_DIR = "traces"

PROXY_DISABLED = config.PROXY_DISABLED
