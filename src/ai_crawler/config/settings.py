from ai_crawler.config import config

BOT_NAME = "ai_crawler"

SPIDER_MODULES = ["ai_crawler.integrations.scrapy.spiders"]
NEWSPIDER_MODULE = "ai_crawler.integrations.scrapy.spiders"

EXTENSIONS = {
    "ai_crawler.extensions.DSPyLMExtension": 0,
}

DOWNLOADER_MIDDLEWARES = {}

SPIDER_MIDDLEWARES = {}

DOWNLOAD_DELAY = 5
RANDOMIZE_DOWNLOAD_DELAY = True
CONCURRENT_REQUESTS_PER_DOMAIN = 2
RETRY_TIMES = 0
RETRY_ENABLED = False
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

FEEDS = {}

LOG_LEVEL = config.LOG_LEVEL
LOG_FILE = "logs/scrapy.log"

REQUEST_TIMEOUT = config.REQUEST_TIMEOUT
PAGE_LOAD_TIMEOUT = config.PAGE_LOAD_TIMEOUT

RENDER_ENGINE = "runtime"

LLM_API_KEY = config.OPENAI_API_KEY
LLM_PROVIDER = "openai"

CAPTCHA_API_KEY = config.TWO_CAPTCHA_API_KEY

TRACE_DIR = "traces"
OUTPUT_DIR = "output"
MAX_IP_RETRIES = 3
RUNTIME_CONCURRENCY = 1

PROXY_DISABLED = config.PROXY_DISABLED
