# AI-Crawler 核心架构文档

> 本文档详细描述 ai-crawler 的核心架构、模块职责、数据流和关键逻辑。

---

## 1. 系统架构概览

```
CLI / API
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ai_crawler.run_crawl()                                                    │
│  └── SmartCrawlerRuntime.crawl() / crawl_tasks()                          │
│      └── CrawlRunner.run()                                                 │
│          ├── CrawlQueue (任务队列)                                          │
│          ├── TaskStrategyPlanner (策略规划)                                  │
│          ├── TaskExecutionEngine (执行引擎)                                  │
│          ├── AntiBotHandler (反爬检测)                                       │
│          ├── ExtractionRuntimeService (提取服务)                              │
│          └── TraceStore (轨迹存储)                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.1 核心目录结构

```
src/ai_crawler/
├── __init__.py                    # run_crawl() 入口
├── orchestration/                  # 对外运行时入口
│   ├── orchestrator.py            # SmartCrawlerRuntime
│   ├── models.py                  # RuntimeTask, RuntimeBatchResult
│   └── storage.py                 # ProductOutputWriter
├── core/
│   ├── runner.py                  # CrawlRunner (核心编排器)
│   ├── strategy.py                # CrawlTask, CrawlStrategy, PatternMatcher
│   ├── types.py                   # TierSystem, ProxyType, RenderType, PagePattern
│   ├── engine/                    # 内部运行时服务
│   │   ├── handler.py             # BlockDetector, AntiBotHandler, BlockType
│   │   ├── execution.py           # TaskExecutionEngine
│   │   ├── processing.py          # TaskProcessor
│   │   ├── planner.py             # TaskStrategyPlanner
│   │   ├── queue.py              # CrawlQueue
│   │   ├── extraction_runtime.py  # ExtractionRuntimeService
│   │   ├── policy_engine.py       # PolicyEngine, PolicyStatsStore
│   │   ├── strategy_generator.py   # StrategyGenerator
│   │   ├── proxying.py            # ProxyProvider
│   │   ├── captcha.py             # CaptchaService
│   │   ├── fingerprinter.py       # AntiBotFingerprinter
│   │   ├── trace_store.py         # TraceStore
│   │   ├── outcomes.py            # TraceRecorder, FailureOutcomeHandler
│   │   └── ...
│   └── extraction/                # 页面提取模块
│       ├── base.py                # ExtractionResult, ExtractionStrategy, ExtractorChain
│       ├── json_ld.py             # JSON-LD 提取
│       ├── bs_css.py              # BeautifulSoup CSS 选择器
│       ├── js_eval.py             # JavaScript 表达式提取
│       ├── axtree.py              # AXTree 可访问性树提取
│       ├── api_intercept.py       # API 拦截提取
│       ├── template_based.py      # 模板化提取
│       └── extraction.py           # 提取入口, SITE_EXTRACTION_CHAINS
├── config/
│   ├── sites.py                  # SUPPORTED_SITES, SITE_TIER_DEFAULTS, PATTERNS
│   └── sites.yaml                # 站点配置
├── browser/
│   └── fetching.py                # Fetcher (HTTP/浏览器抓取)
├── integrations/                  # 第三方集成
│   ├── captcha/                  # CaptchaSolver
│   ├── middlewares/              # Scrapy 中间件
│   └── scrapy/                   # Scrapy 适配
└── models/
    └── product.py                # Product 数据模型
```

---

## 2. 入口与编排层

### 2.1 run_crawl() 入口

```python
# src/ai_crawler/__init__.py
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
) -> RuntimeBatchResult:
```

**流程**:
1. 创建 `RuntimeOptions`
2. 创建 `SmartCrawlerRuntime`
3. 调用 `crawl(sites, query, pages)`

### 2.2 SmartCrawlerRuntime

```python
# src/ai_crawler/orchestration/orchestrator.py

class SmartCrawlerRuntime:
    def crawl(self, sites: list[str], query: str, pages: int) -> RuntimeBatchResult:
        # 1. 构建任务
        tasks = self.build_search_tasks(sites, query, pages)
        # 2. 执行任务
        return self.crawl_tasks(tasks)

    def crawl_tasks(self, tasks: list[RuntimeTask]) -> RuntimeBatchResult:
        # 1. 设置日志
        # 2. 创建 TraceStore
        # 3. 构建 CrawlRunner
        # 4. 转换任务: RuntimeTask -> CrawlTask
        # 5. 执行爬取
        # 6. 写入结果
        # 7. 返回统计信息
```

**关键组件**:
- `build_search_tasks()`: 根据站点和查询构建 URL 任务
- `_build_runner()`: 构建包含代理、动态profile、验证码解决器的执行器
- `_to_crawl_task()`: 将 RuntimeTask 转换为 CrawlTask（应用自动策略选择）

---

## 3. CrawlRunner 核心编排器

```python
# src/ai_crawler/core/runner.py

class CrawlRunner:
    def run(self) -> list[CrawlResult]:
        self._running = True
        futures = []
        while not self.queue.empty() and self._running:
            task = self.queue.dequeue()
            future = self.executor.submit(self._processor.process, task)
            futures.append(future)

        results = []
        for future in futures:
            results.append(future.result())
        return results
```

**组件初始化**:
```python
def __init__(self, ...):
    self.queue = CrawlQueue()
    self.proxy_provider = ProxyProvider(...)
    self.fetcher = Fetcher(...)
    self.anti_bot = AntiBotHandler()
    self._planner = TaskStrategyPlanner(...)
    self._execution = TaskExecutionEngine(...)
    self._extraction = ExtractionRuntimeService(...)
    self._processor = TaskProcessor(...)
```

---

## 4. 策略系统

### 4.1 Tier 系统 (TierSystem)

```python
# src/ai_crawler/core/types.py

class TierSystem(Enum):
    TIER_1 = 1  # curl_cffi - 最快，最简单
    TIER_2 = 2  # cloudscraper - 简单反爬
    TIER_3 = 3  # Lightpanda - 轻量浏览器，<100ms 启动
    TIER_4 = 4  # Playwright - 全功能浏览器
    TIER_5 = 5  # Camoufox - 指纹感知 Firefox
    TIER_6 = 6  # undetected-chromedriver - Cloudflare 专家
    TIER_7 = 7  # SeleniumBase - 最大隐匿
    TIER_8 = 8  # CloakBrowser - C++ 补丁 Chromium
    TIER_9 = 9  # [已废弃] Kameleo
```

### 4.2 RenderType 渲染类型

```python
class RenderType(Enum):
    NONE = "none"
    CLOUDSCRAPER = "cloudscraper"
    LIGHTPAND = "lightpand"
    PLAYWRIGHT = "playwright"
    CAMOUFOX = "camoufox"
    CLOAKBROWSER = "cloakbrowser"
    CLOUDERA = "cloudflare_uc"
    SELENIUMBASE = "seleniumbase"
    KAMELEO = "kameleo"
```

### 4.3 CrawlStrategy 数据类

```python
@dataclass
class CrawlStrategy:
    tier: int = 1
    proxy: ProxyType = ProxyType.THORDATA_DEDICATED
    render: RenderType = RenderType.NONE
    delay_before: tuple[float, float] = (0, 0)
    delay_after: tuple[float, float] = (3.0, 8.0)
    use_cookies: bool = False
    use_human_scroll: bool = False
    use_interactive_search: bool = False
    change_ua: bool = False
    wait_selector: str | None = None
    extra_wait: float = 0.0
    proxy_country: str | None = None
    proxy_city: str | None = None
```

### 4.4 CrawlTask 任务数据类

```python
# src/ai_crawler/core/strategy.py

@dataclass
class CrawlTask:
    url: str
    site: str
    page_pattern: PagePattern = PagePattern.UNKNOWN
    strategies: list[CrawlStrategy] = field(default_factory=list)
    current_index: int = 0
    fail_count: int = 0
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    query: str | None = None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def create(cls, url: str, site: str, use_auto_strategies: bool = True) -> "CrawlTask":
        # 1. 检测页面模式 (SEARCH, DETAIL, etc)
        # 2. 生成策略候选
        # 3. 返回配置好的 CrawlTask

    def current_strategy(self) -> CrawlStrategy | None:
        if self.current_index >= len(self.strategies):
            return None
        return self.strategies[self.current_index]

    def advance(self) -> None:
        self.current_index += 1
```

### 4.5 页面模式 (PagePattern)

```python
class PagePattern(Enum):
    SEARCH = "search"   # 搜索结果页
    DETAIL = "detail"  # 商品详情页
    SELLER = "seller"  # 卖家页
    REVIEW = "review"  # 评价页
    HOME = "home"      # 首页
    UNKNOWN = "unknown"
```

### 4.6 策略生成流程

```python
# src/ai_crawler/core/engine/strategy_generator.py

class StrategyGenerator:
    @classmethod
    def get_optimal_strategies(
        cls, site: str, pattern: str, engine: PolicyEngine, top_n: int = 10
    ) -> list[CrawlStrategy]:
        # 1. 生成 20-50 个候选策略组合
        # 2. PolicyEngine.rank_candidates() 打分排序
        # 3. 返回 top-n
```

---

## 5. 任务处理流程 (TaskProcessor)

```python
# src/ai_crawler/core/engine/processing.py

class TaskProcessor:
    def process(self, task: CrawlTask) -> CrawlResult:
        # 1. 获取站点记忆 (SiteMemory)
        memory_key = (task.site, task.page_pattern.value)
        memory = self.queue.site_memory.get(memory_key)

        # 2. 策略规划
        strategy = self.planner.resolve(task)
        if not strategy:
            return CrawlResult(success=False, error="All strategies exhausted")

        # 3. 执行
        attempt = self.execution.execute(task, strategy)

        # 4. 反爬检测
        if attempt.blocked:
            if attempt.block_type == BlockType.CAPTCHA:
                # 尝试解决验证码
                ...
            # 处理阻塞
            return self._handle_blocked(...)

        # 5. 提取
        decision = self.extraction.extract(task, attempt)

        # 6. 处理提取结果
        if decision.should_retry:
            # 重试或升级
            ...
        else:
            return CrawlResult(success=True, products=decision.products)
```

---

## 6. 反爬检测系统

### 6.1 BlockType 枚举

```python
# src/ai_crawler/core/engine/handler.py

class BlockType:
    NONE = "none"
    HTTP_403 = "http_403"
    HTTP_429 = "http_429"
    HTTP_451 = "http_451"
    HTTP_TIMEOUT = "http_timeout"
    CAPTCHA = "captcha"
    CLOUDFLARE = "cloudflare"
    BOT_DETECTED = "bot_detected"
    SOFT_SUSPICION = "soft_suspicion"
    EMPTY_RESPONSE = "empty_response"
    UNKNOWN = "unknown"
    IP_BLOCKED = "ip_blocked"
    HUMAN_BEHAVIOR = "human_behavior"
    INTERACTIVE_FAILED = "interactive_failed"
```

### 6.2 AntiBotHandler

```python
class AntiBotHandler:
    def is_blocked(
        self,
        status_code: int,
        html: str,
        context: BlockDetectionContext
    ) -> tuple[bool, BlockType]:
        # 检测逻辑:
        # 1. HTTP 状态码检查 (403, 429, 451, timeout)
        # 2. HTML 内容模式匹配
        #    - CAPTCHA 强模式: "are you a robot", "prove you're not a robot"
        #    - CAPTCHA 弱模式: "recaptcha", "hcaptcha"
        #    - Cloudflare 强模式: "checking your browser", "attention required!"
        #    - Bot 检测: "blocked your ip", "unusual traffic"
        #    - 浏览器错误: "err_no_supported_proxies", "chrome-error://"
        # 3. 语义确认 (使用 AXTree)
```

### 6.3 IP 轮换触发类型

```python
IP_ROTATION_BLOCK_TYPES = {
    BlockType.HTTP_403,
    BlockType.HTTP_429,
    BlockType.HTTP_451,
    BlockType.HTTP_TIMEOUT,
    BlockType.BOT_DETECTED,
    BlockType.CLOUDFLARE,
    BlockType.EMPTY_RESPONSE,
}
```

---

## 7. 提取系统 (Extraction)

### 7.1 提取结果结构

```python
# src/ai_crawler/core/extraction/base.py

@dataclass
class ExtractionResult:
    products: list[Product]
    strategy: str   # 策略名称
    method: str    # 方法 (beautifulsoup, js_eval, etc)
```

### 7.2 提取策略链

```python
# src/ai_crawler/core/extraction/extraction.py

SITE_EXTRACTION_CHAINS = {
    "amazon": ["js_eval", "axtree", "bs_css"],
    "default": ["json_ld", "js_eval", "api_intercept", "axtree", "bs_css"],
}

# 搜索页优先级重排
priority = {"js_eval": 0, "json_ld": 1, "api_intercept": 2, "bs_css": 3, "axtree": 4}
```

### 7.3 ExtractorChain 链式提取器

```python
class ExtractorChain:
    def extract(self, page, html, url, page_type="unknown") -> ExtractionResult:
        # 1. 按优先级尝试各提取策略
        # 2. 返回最大结果
        # 3. 最后尝试 GenericCSSFallback
```

### 7.4 提取策略详情

| 策略 | 文件 | 说明 |
|------|------|------|
| `json_ld` | `json_ld.py` | 解析 HTML 中的 JSON-LD 结构化数据 |
| `js_eval` | `js_eval.py` | 在浏览器中运行 JavaScript 提取 |
| `api_intercept` | `api_intercept.py` | 拦截 XHR/Fetch 响应获取数据 |
| `axtree` | `axtree.py` | 读取浏览器可访问性树 |
| `bs_css` | `bs_css.py` | BeautifulSoup CSS 选择器 |
| `template` | `template_based.py` | 站点模板匹配提取 |

### 7.5 ExtractionRuntimeService

```python
# src/ai_crawler/core/engine/extraction_runtime.py

class ExtractionRuntimeService:
    def setup_api_intercept(self, page) -> None:
        # 拦截 API 响应，捕获产品数据
        def handle_response(response):
            if any(k in response.url.lower() for k in ["product", "search", "item", "goods"]):
                data = response.json()
                products = self._parse_api_response(data)
                self._intercepted_products.extend(products)
        page.on("response", handle_response)

    def _parse_api_response(self, data: dict) -> list[Product]:
        # 支持多种响应格式:
        # - result.home_goods_list (Temu 格式)
        # - result.data
        # - data.items
        # - data.products
```

---

## 8. 执行引擎 (TaskExecutionEngine)

```python
# src/ai_crawler/core/engine/execution.py

class TaskExecutionEngine:
    def execute(self, task: CrawlTask, strategy: CrawlStrategy):
        # 1. 获取代理
        proxy = self.proxy_provider.get_proxy(strategy)

        # 2. 抓取
        html, status_code, page = self.fetcher.fetch_with_strategy(task, strategy)

        # 3. 反爬检测
        blocked, block_type = self.anti_bot.is_blocked(
            status_code, html,
            BlockDetectionContext(site=task.site, page_pattern=task.page_pattern.value)
        )

        return ExecutionResult(
            html=html,
            status_code=status_code,
            page=page,
            blocked=blocked,
            block_type=block_type,
            proxy_used=proxy,
        )
```

---

## 9. 策略规划 (TaskStrategyPlanner)

```python
# src/ai_crawler/core/engine/planner.py

class TaskStrategyPlanner:
    def resolve(self, task: CrawlTask) -> CrawlStrategy | None:
        # 1. 检查 SiteMemory 是否有成功策略
        # 2. 如果有，直接使用
        # 3. 如果没有，返回当前策略
        return task.current_strategy()

    def prepare(self, task: CrawlTask, memory: Any) -> Any:
        # 准备阶段：如有记忆，直接将成功策略置顶
        if memory and hasattr(memory, 'successful_strategy'):
            task.add_strategy_front(memory.successful_strategy)
        return memory
```

---

## 10. 代理系统 (ProxyProvider)

```python
# src/ai_crawler/core/engine/proxying.py

class ProxyProvider:
    def get_proxy(self, strategy: CrawlStrategy) -> str:
        # 根据策略选择代理
        # 支持: thordata_us, thordata_any, thordata_dedicated
```

---

## 11. 轨迹追踪 (TraceStore)

```python
# src/ai_crawler/core/engine/trace_store.py

class TraceStore:
    def record(self, trace: "CrawlTrace"):
        # 记录爬取轨迹

    def get_site_history(self, site: str) -> list["CrawlTrace"]:
        # 获取站点的历史轨迹

    def stats(self) -> dict:
        # 统计信息
```

---

## 12. 关键数据流

### 12.1 单任务执行流程

```
1. SmartCrawlerRuntime.crawl_tasks(tasks)
   │
   ├─► RuntimeTask -> CrawlTask (自动策略选择)
   │
   ├─► CrawlRunner.add_tasks(crawl_tasks)
   │
   └─► CrawlRunner.run()
           │
           ├─► TaskProcessor.process(task)
           │       │
           │       ├─► TaskStrategyPlanner.resolve(task)
           │       │       └─► 返回当前策略
           │       │
           │       ├─► TaskExecutionEngine.execute(task, strategy)
           │       │       ├─► Fetcher.fetch_with_strategy()
           │       │       └─► AntiBotHandler.is_blocked()
           │       │
           │       ├─► [如阻塞] FailureOutcomeHandler.handle()
           │       │       ├─► 重试或升级策略
           │       │       └─► 重新入队
           │       │
           │       └─► ExtractionRuntimeService.extract()
           │               └─► ExtractorChain.extract()
           │
           └─► CrawlResult(success, products, error)
```

### 12.2 策略升级流程

```
首次失败
    │
    ▼
是否触发 IP 轮换?
    │
    ├─► Yes -> 更换代理，重试当前 Tier
    │
    └─► No -> 升级 Tier
                │
                ▼
            Tier 1 -> Tier 2 -> Tier 3 -> ... -> Tier 8
           (curl)  (cloud) (light)         (cloak)
                │
                ▼
            所有 Tier 用尽
                │
                ▼
            标记失败，记录轨迹
```

### 12.3 提取优先级流程

```
提取请求
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  ExtractorChain.extract()                                    │
│                                                              │
│  1. [API 拦截] intercepted_products? → 直接返回              │
│                                                              │
│  2. [JSON-LD] 解析结构化数据                                 │
│     ✓ 成功且 >= 2 个产品 → 返回                              │
│     ✗ 失败或产品不足 → 继续                                   │
│                                                              │
│  3. [JS Eval] 浏览器执行 JavaScript                          │
│     ✓ 成功且 >= 2 个产品 → 返回                              │
│     ✗ 失败或产品不足 → 继续                                   │
│                                                              │
│  4. [API 拦截] 捕获 XHR 响应中的产品                         │
│     ✓ 成功且 >= 2 个产品 → 返回                              │
│     ✗ 失败或产品不足 → 继续                                   │
│                                                              │
│  5. [AXTree] 可访问性树提取                                   │
│     ✓ 成功且 >= 2 个产品 → LLM 生成模板                       │
│     ✗ 失败或产品不足 → 继续                                   │
│                                                              │
│  6. [BS CSS] BeautifulSoup CSS 选择器                        │
│     ✓ 成功 → 返回                                            │
│     ✗ 失败 → GenericCSSFallback                              │
│                                                              │
│  7. [GenericCSSFallback] 通用选择器 (最后兜底)               │
│     ✗ 失败 → 返回空结果                                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 13. 配置系统

### 13.1 站点配置 (config/sites.py)

```python
SUPPORTED_SITES = {
    "amazon": "https://www.amazon.com/s?k={query}",
    "walmart": "https://www.walmart.com/search?q={query}",
    "temu": "https://www.temu.com/search?q={query}",
    # ... 30+ sites
}

SITE_TIER_DEFAULTS = {
    "amazon": {PagePattern.SEARCH: 4, PagePattern.DETAIL: 3},
    "walmart": {PagePattern.SEARCH: 2, PagePattern.DETAIL: 2},
    # ...
}
```

### 13.2 Tier 配置 (TIER_CONFIGS)

```python
TIER_CONFIGS = {
    1: {"render": RenderType.NONE, "proxy": ProxyType.THORDATA_DEDICATED, ...},
    2: {"render": RenderType.CLOUDSCRAPER, ...},
    3: {"render": RenderType.LIGHTPAND, ...},
    4: {"render": RenderType.PLAYWRIGHT, ...},
    # ...
}
```

---

## 14. 输出结构

### 14.1 RuntimeBatchResult

```python
@dataclass
class RuntimeBatchResult:
    products: list[Product]           # 所有产品
    task_results: list[RuntimeTaskResult]  # 每个任务的结果
    stats: dict                     # 统计信息
    output_files: list[str]         # 输出文件路径
    traces_file: str                # 轨迹文件
```

### 14.2 Product 模型

```python
@dataclass
class Product:
    source: str           # 站点名称
    url: str             # 产品 URL
    title: str           # 标题
    price: str           # 价格
    images: list[str]     # 图片列表
    rating: str | None = None
    reviews: str | None = None
    brand: str | None = None
    description: str | None = None
    availability: str | None = None
    sku: str | None = None
    currency: str | None = None
```

---

## 15. LLM 集成 (可选)

### 15.1 动态 Profile 生成

```python
# src/ai_crawler/core/llm/dspy_model.py

class ProfileGenerator:
    def generate(self, system_facts: dict) -> DynamicProfile:
        # 使用 LLM 生成浏览器指纹配置
        # - user_agent
        # - sec_ch_ua_platform
        # - timezone_id
        # - locale
        # - viewport
        # - mouse_behavior
```

### 15.2 初始 Tier 选择

```python
class InitialTierSelector:
    def predict(self, site: str, url: str, goal: str) -> int:
        # 使用 LLM 预测最佳初始 Tier
```

---

## 16. 关键文件索引

| 文件 | 类/函数 | 职责 |
|------|---------|------|
| `__init__.py` | `run_crawl()` | 主入口 |
| `orchestration/orchestrator.py` | `SmartCrawlerRuntime` | 运行时编排 |
| `orchestration/models.py` | `RuntimeTask`, `RuntimeBatchResult` | 数据模型 |
| `core/runner.py` | `CrawlRunner` | 核心执行器 |
| `core/strategy.py` | `CrawlTask`, `CrawlStrategy`, `PatternMatcher` | 策略定义 |
| `core/types.py` | `TierSystem`, `RenderType`, `ProxyType`, `PagePattern` | 类型枚举 |
| `core/engine/handler.py` | `BlockDetector`, `AntiBotHandler`, `BlockType` | 反爬检测 |
| `core/engine/execution.py` | `TaskExecutionEngine` | 任务执行 |
| `core/engine/processing.py` | `TaskProcessor` | 任务处理主循环 |
| `core/engine/planner.py` | `TaskStrategyPlanner` | 策略规划 |
| `core/engine/queue.py` | `CrawlQueue` | 任务队列 |
| `core/engine/extraction_runtime.py` | `ExtractionRuntimeService` | 提取服务 |
| `core/engine/policy_engine.py` | `PolicyEngine` | 策略评分 |
| `core/engine/strategy_generator.py` | `StrategyGenerator` | 策略生成 |
| `core/engine/proxying.py` | `ProxyProvider` | 代理管理 |
| `core/engine/captcha.py` | `CaptchaService` | 验证码服务 |
| `core/engine/trace_store.py` | `TraceStore` | 轨迹存储 |
| `core/engine/outcomes.py` | `TraceRecorder`, `FailureOutcomeHandler` | 结果处理 |
| `core/extraction/base.py` | `ExtractionResult`, `ExtractorChain` | 提取基类 |
| `core/extraction/json_ld.py` | `JSONLDExtractor` | JSON-LD 提取 |
| `core/extraction/bs_css.py` | `BSCSSExtractor` | CSS 选择器提取 |
| `core/extraction/js_eval.py` | `JSEvalExtractor` | JS 执行提取 |
| `core/extraction/axtree.py` | `AXTreeExtractor` | AXTree 提取 |
| `core/extraction/api_intercept.py` | `APIInterceptExtractor` | API 拦截提取 |
| `core/extraction/template_based.py` | `ExtractionTemplate`, `UniversalExtractor` | 模板提取 |
| `browser/fetching.py` | `Fetcher` | 抓取入口 |
| `config/sites.py` | `SUPPORTED_SITES`, `SITE_TIER_DEFAULTS` | 站点配置 |

---

*文档版本: 2026-04-20*
*对应分支: gpt*
