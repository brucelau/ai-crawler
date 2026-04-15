# AI-Crawler 架构设计文档

> 状态：已与当前 `gpt` 分支实现对齐。
>
> 适用范围：整体系统架构、运行时分层、模块职责、主调用链。
>
> 相关文档：
>
> - `docs/TIER_SYSTEM.md`
> - `docs/BLOCK_DETECTOR.md`
> - `docs/ANTI_BOT_FINGERPRINTER.md`
> - `docs/LLM_SYSTEM.md`

## 当前实现状态（gpt 分支重构后）

> 下文保留原始设计说明，但当前代码主路径已经调整为 **浏览器优先运行时 + Scrapy 辅助适配层**。

### 当前主路径

```text
CLI / API
  -> ai_crawler.run_crawl()
  -> runtime/SmartCrawlerRuntime
  -> core/runner.CrawlRunner
  -> core/runtime/* 运行时服务
  -> browser/fetching.py
  -> output/traces
```

### 当前职责划分

- `src/ai_crawler/runtime/`
  - 面向外部的智能爬虫运行时入口
- `src/ai_crawler/core/runtime/`
  - 内部运行时服务：规划、执行、验证码、提取、推荐、结果处理、流程编排、反爬指纹识别
- `src/ai_crawler/browser/fetching.py`
  - 浏览器与 HTTP 抓取分发层（含 Playwright / Camoufox / CloakBrowser 池化、UC 小型预热池、广告脚本拦截、抓取层观测指标）
- `src/ai_crawler/core/runtime/proxying.py`
  - 代理选择与轮换
- `src/ai_crawler/adapters/scrapy/`
  - Scrapy 适配层，仅用于辅助调度和 pipeline 集成
- `src/ai_crawler/models/`
  - 与 Scrapy 解耦的领域模型

### Scrapy 的当前定位

Scrapy 不再作为智能爬虫决策中心，而是作为：

- 辅助调度入口
- pipeline / item 输出集成层
- 兼容已有 spider 工作流的 adapter

也就是说，反爬策略、浏览器执行、失败恢复、提取升级等逻辑现在都应优先落在 runtime 路径中，而不是 Scrapy middleware/spider 中。

### 当前解析链路（AXTree 已接入）

当前页面提取不是单一路径，而是按站点配置的多级回退链：

```text
json_ld -> js_eval -> api_intercept -> axtree -> bs_css
```

特殊情况：

- `amazon`：`js_eval -> axtree -> bs_css`
- 默认链路（无站点专属配置时）：`json_ld -> js_eval -> axtree -> bs_css`

其中：

- `json_ld`：优先使用结构化商品数据
- `js_eval`：在真实浏览器页上运行站点级 DOM 提取 JavaScript
- `api_intercept`：接口型提取路径
- `axtree`：读取浏览器可访问性树，作为 DOM-first 提取的语义增强回退层
- `bs_css`：最终 BeautifulSoup / 站点级 CSS 选择器回退

AXTree 的设计目标不是替代 DOM，而是在 DOM 结构脆弱、但可访问语义仍然存在时提供一个更稳定的补充视角。

当前 runtime 结果和统计中也会暴露提取命中信息：

- `extraction_strategy`
- `extraction_method`
- `axtree_hit`
- 批量统计中的 `task_extraction_strategies` / `task_axtree_hits`

当前 LLM selector 生成也已经开始采用混合采样思路：

- HTML 片段负责提供 CSS selector 所需的 DOM 线索
- AXTree 语义采样负责补充页面骨架和可见产品语义

## 1. 系统概览

AI-Crawler 是一个智能电商爬虫系统，通过 8 层爬取策略自动应对各类反爬机制。系统融合了 DSPy 机器学习、LLM 决策、Pydantic 校验等多种技术实现隐匿爬取。

### 1.1 核心特性

| 特性 | 描述 |
|------|------|
| 8 层爬取策略 | Tier 1-8，从 HTTP 到指纹浏览器，逐级升级 |
| 动态指纹生成 | DSPy ProfileGenerator 生成匹配主机的浏览器指纹 |
| LLM 策略决策 | DSPy + Pydantic 做推理和校验 |
| WAF 检测 | 自动识别 Incapsula、Cloudflare、Akamai 等 |
| 多级解析链 | JSON-LD / JS / API / AXTree / BS CSS 多级回退 |
| 40+ 站点支持 | Amazon, Walmart, Target 等电商平台 |

### 1.2 架构分层

```
CLI 入口 (__main__.py)
        ↓
Scrapy Spider 层
  spiders/
    base.py              # EcommerceSpider (统一 LLM extraction)
    amazon.py, walmart.py, target.py, ...  # 30 个站点 spider
    multi.py             # MultiSiteSpider
        ↓
Scrapy Middleware 管道
  tier_strategy.py       # Tier 策略选择/升级
  proxy.py              # 代理分配
  captcha.py            # CAPTCHA 求解
  memory.py             # 站点记忆
        ↓
Browser Wrappers
  camoufox_wrapper.py
  cloakbrowser_wrapper.py
  seleniumbase_wrapper.py
  kameleo_wrapper.py
        ↓
LLM / DSPy 层
  dspy_model.py          # DSPy Signatures + Modules
  validators.py           # Pydantic 校验
  llm_extractor.py        # CSS Selector 生成
  llm_block_detector.py  # Block 检测
  dynamic_thresholds.py   # 动态阈值
  llm_url_discovery.py    # URL 发现
  human_mouse.py          # 人类行为
```

## 2. LLM 系统

### 2.1 三层架构

```
DSPy (推理) → Pydantic (校验) → 业务逻辑
```

### 2.2 DSPy 模块

| 模块 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `SelectorExtractor` | CSS Selector 生成 | site, page_type, html_sample | list_container, product_selector... |
| `BlockDetector` | Block 类型检测 | site, status_code, response_text | block_type, reasoning |
| `ThresholdOptimizer` | 动态阈值优化 | site, metrics, html_sample | request_timeout, delay_after |
| `URLDiscoverer` | URL 格式发现 | site, homepage_html | search_url_pattern, page_param |
| `HumanBehaviorGenerator` | 人类行为生成 | site, page_type | scroll_strategy, scroll_phases |
| `ProfileGenerator` | 浏览器指纹生成 | system_facts | user_agent, viewport, locale... |
| `StrategySelector` | 策略选择 | site, block_type, attempt_history | recommended_strategy |
| `InitialTierSelector` | 初始 Tier 选择 | site, page_pattern | start_tier |

### 2.3 Pydantic 校验

| Validator | 输出模型 |
|-----------|----------|
| `validate_selector()` | `SelectorResult` |
| `validate_block()` | `BlockResult` |
| `validate_threshold()` | `ThresholdResult` |
| `validate_url_discovery()` | `URLDiscoveryResult` |
| `validate_human_behavior()` | `HumanBehaviorResult` |

### 2.4 缓存策略

| 模块 | 缓存 TTL | 缓存粒度 |
|------|----------|----------|
| `SelectorExtractor` | 24 小时 | site:page_type |
| `BlockDetector` | 5 分钟 | status_code + text_hash |
| `ThresholdOptimizer` | 24 小时 | site:page_type |
| `URLDiscoverer` | 24 小时 | site |
| `HumanBehaviorGenerator` | 1 小时 | 全局 |
| `InitialTierSelector` | 24 小时 | site:page_type |

### 2.5 DSPy 训练

每个模块独立训练，通过 DSPyScheduler 后台进程：

```bash
python -m ai_crawler.core.dspy_scheduler --status
python -m ai_crawler.core.dspy_scheduler --train-once --module selector_extractor
```

## 3. 策略系统

### 3.1 RenderType 枚举

| 枚举值 | 渲染引擎 |
|--------|----------|
| `NONE` | 纯 HTTP 请求 |
| `CLOUDSCRAPER` | cloudscraper |
| `PLAYWRIGHT` | Playwright |
| `CAMOUFOX` | Camoufox |
| `SELENIUMBASE` | SeleniumBase |
| `CLOAKBROWSER` | CloakBrowser |
| `KAMELEO` | Kameleo |

### 3.2 ProxyType

| 枚举值 | 代理类型 |
|--------|----------|
| `THORDATA_US` | ThorData 美国代理 |
| `THORDATA_US_CITY` | ThorData 美国城市级代理 |
| `THORDATA_ANY` | ThorData 任意国家代理 |
| `THORDATA_DEDICATED` | ThorData 独享代理 |

### 3.3 Tier 层级配置

| Tier | Render | Proxy | Human Scroll | Change UA | Cookies |
|------|--------|-------|--------------|-----------|---------|
| 1 | NONE | THORDATA_DEDICATED | ❌ | ❌ | ❌ |
| 2 | CLOUDSCRAPER | THORDATA_DEDICATED | ❌ | ❌ | ✅ |
| 3 | PLAYWRIGHT | THORDATA_DEDICATED | ✅ | ❌ | ❌ |
| 4 | CAMOUFOX | THORDATA_DEDICATED | ✅ | ✅ | ✅ |
| 5 | CLOUDERA | THORDATA_DEDICATED | ✅ | ✅ | ✅ |
| 6 | SELENIUMBASE | THORDATA_DEDICATED | ✅ | ✅ | ✅ |
| 7 | CLOAKBROWSER | THORDATA_DEDICATED | ✅ | ✅ | ✅ |
| 8 | KAMELEO | THORDATA_DEDICATED | ✅ | ✅ | ✅ |

## 4. Spider 系统

### 4.1 站点列表 (40+ 个)

| 站点 | Spider 类 | 搜索 URL |
|------|----------|---------|
| Amazon | `AmazonSpider` | `amazon.com/s?k={query}` |
| Walmart | `WalmartSpider` | `walmart.com/search?q={query}` |
| Target | `TargetSpider` | `target.com/s?searchTerm={query}` |
| eBay | `EbaySpider` | `ebay.com/sch/i.html?_nkw={query}` |
| Best Buy | `BestbuySpider` | `bestbuy.com/site/search?search={query}` |
| Lowe's | `LowesSpider` | `lowes.com/search?searchTerm={query}` |
| Home Depot | `HomedepotSpider` | `homedepot.com/search?text={query}` |
| Ace Hardware | `AcehardwareSpider` | `acehardware.com/search?query={query}` |
| Wayfair | `WayfairSpider` | `wayfair.com/keyword.php?keyword={query}` |
| Michaels | `MichaelsSpider` | `michaels.com/search?search={query}` |
| Temu | `TemuSpider` | `temu.com/search?search_key={query}` |
| Etsy | `EtsySpider` | `etsy.com/search?q={query}` |
| Costco | `CostcoSpider` | `costco.com/search?search={query}` |
| QVC | `QvcSpider` | `qvc.com/forms/search/results?...&search={query}` |
| Kohl's | `KohlsSpider` | `kohls.com/search.jsp?search={query}` |
| Mercado Libre | `MercadolibreSpider` | `mercadolibre.com.mx/{query}` |
| Walmart Mexico | `WalmartmexicoSpider` | `walmartmexico.com.mx/search?term={query}` |
| Intexcorp | `IntexcorpSpider` | `intexcorp.com/search?q={query}` |
| Meijer | `MeijerSpider` | `meijer.com/shopping/search/{query}` |
| Five Below | `FivebelowSpider` | `fivebelow.com/search?q={query}` |
| Sam's Club | `SamsclubSpider` | `samsclub.com/search?query={query}` |
| Bunnings | `BunningsSpider` | `bunnings.com.au/search?query={query}` |
| Dollar General | `DollargeneralSpider` | `dollargeneral.com/search?text={query}` |
| Action | `ActionSpider` | `action.com/search?q={query}` |
| Academy | `AcademySpider` | `academy.com/shop/search?q={query}` |
| WOW Sports | `WowsportsSpider` | `wowsports.com/search?q={query}` |
| Coppel | `CoppelSpider` | `coppel.com/search?term={query}` |
| Aosom | `AosomSpider` | `aosom.com/search?q={query}` |
| Family Dollar | `FamilydollarSpider` | `familydollar.com/search?q={query}` |
| Costway | `CostwaySpider` | `costway.com/search?q={query}` |

### 4.2 Spider 基类

```python
class EcommerceSpider(Spider):
    name = "ecommerce"
    
    SITE_DOMAINS = {
        "amazon": ["amazon.com", ...],
        "walmart": ["walmart.com"],
        ...
    }
    
    def parse(self, response):
        site = self._detect_site(response.url)
        page_type = self._detect_page_type(response.url)
        products = llm_extractor.extract(response.text, site, page_type, response.url)
        for product in products:
            yield product_to_item(product)
```

### 4.3 MultiSiteSpider

支持一次爬取多个站点：

```bash
scrapy crawl multi -a sites="amazon,walmart,target" -a query="chair" -a pages=3
```

## 5. 配置

### 5.1 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENAI_API_KEY` | LLM API Key | - |
| `OPENAI_BASE_URL` | LLM API Base URL | https://api.openai.com/v1 |
| `MODEL_NAME` | 模型名称 | gpt-4o |
| `THORDATA_PROXY_HOST` | ThorData 代理主机 | - |
| `THORDATA_RESIDENTIAL_USERNAME` | ThorData 用户名 | - |
| `THORDATA_RESIDENTIAL_PASSWORD` | ThorData 密码 | - |
| `THORDATA_DEDICATED_HOST` | ThorData 独享代理主机 | - |
| `REQUEST_TIMEOUT` | 请求超时 | 30 |
| `PAGE_LOAD_TIMEOUT` | 页面加载超时 | 30 |
| `DSPY_MODEL_DIR` | DSPy 模型目录 | models |
| `DSPY_TRAIN_INTERVAL` | 训练检查间隔 | 3600 |
| `DSPY_MIN_TRACES` | 开始训练的最小 trace 数 | 50 |

## 6. 文件结构

```
ai-crawler/
├── demos/                  # 测试脚本
│   ├── crawl.sh
│   ├── test_*.py
│   └── ...
├── docs/                   # 文档
│   ├── ARCHITECTURE.md
│   ├── LLM_SYSTEM.md
│   └── TIER_SYSTEM.md
├── scripts/               # Shell 脚本
│   ├── os_spoofing.sh
│   └── os_spoofing_mac.sh
├── src/ai_crawler/
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py          # 统一配置
│   ├── settings.py
│   │
│   ├── core/
│   │   ├── dspy_model.py         # DSPy Signatures + Modules
│   │   ├── validators.py          # Pydantic Models
│   │   ├── dspy_scheduler.py     # 后台训练调度器
│   │   ├── llm_extractor.py      # CSS Selector 生成
│   │   ├── llm_block_detector.py # Block 检测
│   │   ├── dynamic_thresholds.py  # 动态阈值
│   │   ├── llm_url_discovery.py  # URL 发现
│   │   ├── handler.py           # BlockType, AntiBotHandler
│   │   ├── trace_store.py       # TraceStore
│   │   ├── queue.py             # CrawlQueue
│   │   └── strategy.py          # Tier, Render, Proxy 枚举
│   │
│   ├── browser/
│   │   ├── camoufox_wrapper.py
│   │   ├── cloakbrowser_wrapper.py
│   │   ├── seleniumbase_wrapper.py
│   │   ├── kameleo_wrapper.py
│   │   ├── fingerprint_spoofer.py
│   │   └── human_mouse.py
│   │
│   ├── middlewares/
│   │   ├── tier_strategy.py
│   │   ├── proxy.py
│   │   ├── captcha.py
│   │   └── memory.py
│   │
│   ├── spiders/
│   │   ├── __init__.py
│   │   ├── base.py              # EcommerceSpider
│   │   ├── amazon.py
│   │   ├── walmart.py
│   │   ├── target.py
│   │   ├── ebay.py
│   │   └── ... (30 个站点)
│   │   └── multi.py             # MultiSiteSpider
│   │
│   ├── proxy/
│   │   └── thordata.py         # ThorData 代理
│   │
│   ├── captcha/
│   │   └── solver.py
│   │
│   └── pipelines/
│       └── storage.py
```

## 7. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | - | 初始架构 |
| 1.1 | - | 添加 CloakBrowserWrapper |
| 1.2 | - | 统一 RenderMiddleware |
| 1.3 | - | 添加 CLOUDSCRAPER 渲染支持 |
| 1.4 | - | DSPy + Pydantic 统一 LLM 系统 |
| 1.5 | - | Per-module DSPy 训练调度器 |
| 1.6 | - | 配置统一到 config.py，移除 SOAX |
| 1.7 | - | 30+ 站点统一 Spider 架构 |
| 1.8 | 2026-04-11 | 模板学习系统，BlockDetector 24h 缓存，文档一致性修复 |
