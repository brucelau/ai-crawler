# 爬虫系统架构

## 核心原则

- **一等公民**: Crawler、PolicyScorer、ExtractionEngine 是核心抽象
- **全局唯一组件**: PolicyScorer、ExtractionEngine、MemoryStore 全局唯一
- **Crawler 可多个**: 并行执行提升吞吐
- **只读原则**: PolicyScorer 和 ExtractionEngine 只读 TaskContext
- **TaskContext 贯穿**: 每个任务创建，TaskContext 记录执行过程

## 核心组件

| 组件 | 数量 | 职责 |
|------|------|------|
| SmartCrawlerRuntime | 1 | API 入口，任务构建和结果汇总 |
| CrawlRunner | 1 | 运行时协调，代理/验证码/并发管理 |
| CrawlCoordinator | 1 | 多 Crawler 并行执行协调 |
| Crawler | N | 单任务执行，维护 TaskContext |
| CrawlPolicyScorer | 1 | 爬虫策略决策 |
| ExtractionEngine | 1 | 内容提取 |

## 系统流程

```
┌─────────────────────────────────────────────────────────────────────┐
│                        入口                                         │
│  run_crawl(sites, query, pages)                                   │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 SmartCrawlerRuntime                                  │
│  1. build_search_tasks() → List[RuntimeTask]                      │
│  2. crawl_tasks() → 启动 CrawlRunner                              │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      CrawlRunner                                    │
│                                                                       │
│  - Concurrency: 并发数动态调整 (1-10)                               │
│  - CaptchaService: CAPTCHA 检测和解决                                │
│  - FetchEngineer: 反爬处理                                          │
│  - ProxyProvider: 代理管理                                          │
│  - TraceStore: 追踪数据存储                                         │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     CrawlCoordinator                                 │
│                                                                       │
│  多线程执行多个 Crawler                                             │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│  Crawler 0  │       │  Crawler 1  │       │  Crawler N  │
└──────┬──────┘       └──────┬──────┘       └──────┬──────┘
       │                      │                      │
       └──────────────────────┼──────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Planner                                        │
│                                                                       │
│  职责: 策略生成 + 策略选择                                           │
│                                                                       │
│  ask(ctx)           → 首次选择策略                                   │
│  get_next(ctx)      → 失败后获取下一个策略                           │
│  prepare(task, mem) → 初始化任务策略队列                             │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  CrawlPolicyScorer                                   │
│                  (原 PolicyEngine)                                   │
│                                                                       │
│  根据历史数据对策略打分排序                                           │
│                                                                       │
│  rank_candidates()      → 对候选策略评分                             │
│  pick_initial()         → 选择初始策略                               │
│  should_consult_llm()   → 是否需要 LLM 辅助                         │
│  rank_candidates_for_failure() → 失败后重新排序                      │
│                                                                       │
│  数据: CrawlPolicyStatsStore (基于 TraceStore)                     │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 CrawlPolicyGenerator                                 │
│               (原 StrategyGenerator)                                 │
│                                                                       │
│  动态生成策略候选池                                                   │
│                                                                       │
│  generate_candidates()       → 生成所有可能的策略组合                 │
│  get_optimal_strategies()    → 获取最优 N 个策略                     │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Fetcher                                       │
│                    (browser/fetching.py)                             │
│                                                                       │
│  根据 CrawlPolicy 执行页面抓取                                       │
│                                                                       │
│  策略注册模式: _FETCH_STRATEGIES[render_type]()                     │
│                                                                       │
│  _fetch_with_camoufox()                                             │
│  _fetch_with_playwright()                                            │
│  _fetch_with_uc()                                                   │
│  _fetch_with_cloakbrowser()                                         │
│  _fetch_with_seleniumbase()                                          │
│  _fetch_with_cloudscraper()                                          │
│  ...                                                                │
│                                                                       │
│  每个方法:                                                           │
│  1. 获取/创建浏览器                                                   │
│  2. 应用指纹配置                                                     │
│  3. 设置代理                                                         │
│  4. 拦截广告脚本                                                     │
│  5. 人类行为模拟                                                     │
│  6. 导航到目标 URL                                                   │
│  7. 返回 AttemptResult                                               │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ExtractionEngine                                   │
│              (spider/extraction/engine/)                             │
│                                                                       │
│  从 HTML 中提取产品数据                                               │
│                                                                       │
│  提取流程:                                                           │
│  1. 模板提取 (TemplateStore) → 站点特定规则                         │
│  2. 页面分析 (PageAnalyzer) → 检测页面特征                         │
│  3. 策略选择 (ExtractionPolicyEngine) → 选择提取器                 │
│  4. 依次尝试各提取器直到成功                                         │
│                                                                       │
│  提取器 (extractors/):                                              │
│  ┌──────────────────────┬────────────┬────────────────────────────┐ │
│  │ 提取器               │ 方法        │ 说明                      │ │
│  ├──────────────────────┼────────────┼────────────────────────────┤ │
│  │ JSONLDExtractor     │ beautifulsoup │ 解析 JSON-LD 结构数据   │ │
│  │ JSEvaluateExtractor  │ page_evaluate │ 执行 JS 提取           │ │
│  │ BSExtractor         │ beautifulsoup │ 站点特定 CSS 选择器     │ │
│  │ AXTreeExtractor      │ accessibility_tree │ 辅助树提取          │ │
│  │ APIInterceptExtractor│ api_intercept │ API 响应拦截            │ │
│  │ GenericCSSFallback   │ beautifulsoup │ 通用 CSS 兜底          │ │
│  └──────────────────────┴────────────┴────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

## 核心概念

### CrawlPolicy (爬取策略)

定义如何抓取一个页面:

```python
@dataclass
class CrawlPolicy:
    tier: int                           # 策略层级 (1-9)
    proxy: ProxyType                   # 代理类型
    render: RenderType                 # 渲染引擎
    delay_before: tuple[float, float]  # 请求前延迟
    delay_after: tuple[float, float]   # 请求后延迟
    use_cookies: bool                  # 是否使用 Cookie
    use_human_scroll: bool              # 是否模拟人类滚动
    use_interactive_search: bool        # 是否执行交互式搜索
    change_ua: bool                    # 是否更换 User-Agent
    wait_selector: str | None          # 等待元素选择器
    extra_wait: float                  # 额外等待时间
    proxy_country: str | None          # 代理国家
    proxy_city: str | None             # 代理城市
```

### 相关类

| 类名 | 说明 |
|------|------|
| CrawlPolicyCandidate | 从 CrawlPolicy 转换的统计用对象 |
| CrawlPolicyScore | 策略评分结果 |
| CrawlPolicyStats | 历史表现统计 |
| CrawlPolicyStatsStore | 策略统计存储 |

### RenderType (渲染引擎)

```python
class RenderType(Enum):
    NONE            # 无渲染 (直接请求)
    CLOUDSCRAPER   # CloudScraper
    LIGHTPAND       # LightPanda
    PLAYWRIGHT      # Playwright
    CAMOUFOX        # Camoufox
    CLOUDERA        # CloudEra
    SELENIUMBASE    # SeleniumBase
    CLOAKBROWSER    # CloakBrowser
    KAMELEO         # Kameleo
    UNDETECTED      # Undetected ChromeDriver
```

### ProxyType (代理类型)

```python
class ProxyType(Enum):
    NONE
    THORDATA_DEDICATED  # ThorData 独享代理
    THORDATA_US         # ThorData 美国代理
    THORDATA_US_CITY    # ThorData 美国城市代理
    THORDATA_ANY        # ThorData 任意代理
```

## 策略分层 (TIER_CONFIGS)

```
Tier 1: 最简单/最快
  - render: NONE
  - proxy: THORDATA_DEDICATED
  - delay: (0, 0)

Tier 5: 中等复杂度
  - render: PLAYWRIGHT
  - proxy: THORDATA_US
  - delay: (1, 3)
  - use_cookies: true
  - use_human_scroll: true

Tier 9: 最复杂/最慢 (兜底)
  - render: CLOAKBROWSER
  - proxy: THORDATA_ANY
  - delay: (3, 8)
  - use_cookies: true
  - change_ua: true
  - use_human_scroll: true
```

## 执行流程详解

### 1. 任务创建

```
CrawlTask.create(url, site)
    │
    ├─► 推断 PagePattern (SEARCH / DETAIL / etc.)
    │
    ├─► 生成初始策略队列
    │       │
    │       ├─► 使用历史成功策略 (如果有)
    │       │
    │       └─► 使用 CrawlPolicyGenerator 生成候选
    │               │
    │               └─► CrawlPolicyScorer 评分排序
    │
    └─► 返回 CrawlTask (含策略队列)
```

### 2. 策略选择 (Planner)

```
Planner.ask(ctx)
    │
    ├─► 首次调用?
    │       │
    │       ├─► YES: prepare()
    │       │       │
    │       │       ├─► 有历史成功策略? → 直接使用
    │       │       │
    │       │       └─► 生成并排序候选策略
    │       │               │
    │       │               └─► 需要 LLM 辅助? → 调用 LLM
    │       │
    │       └─► NO: resolve()
    │               │
    │               └─► 返回 task.current_strategy()
    │
    └─► 返回选中的 CrawlPolicy
```

### 3. 页面抓取 (Fetcher)

```
Fetcher.fetch(task, strategy)
    │
    ├─► 获取浏览器 (根据 render type)
    │
    ├─► 应用指纹和隐身配置
    │
    ├─► 设置代理
    │
    ├─► 拦截广告脚本
    │
    ├─► 执行人类行为模拟 (可选)
    │       │
    │       └─► 交互式搜索 (如果启用)
    │
    ├─► 导航到目标 URL
    │
    └─► 返回 AttemptResult
            │
            ├─► html: str
            ├─► page: Any (浏览器页面对象)
            ├─► blocked: bool
            ├─► block_type: str
            └─► latency_ms: float
```

### 4. 产品提取 (ExtractionEngine)

```
ExtractionEngine.extract(task, page, html)
    │
    ├─► 1. 模板提取
    │       │
    │       └─► TemplateStore 查找站点模板
    │               │
    │               └─► 有模板? → 使用模板提取
    │
    ├─► 2. 页面分析
    │       │
    │       └─► PageAnalyzer.analyze()
    │               │
    │               └─► 返回 PageFeatures
    │
    ├─► 3. 获取提取器顺序
    │       │
    │       └─► ExtractionPolicyEngine.get_order()
    │
    └─► 4. 依次尝试提取器
            │
            for extractor_name in order:
                │
                ├─► JSONLDExtractor
                ├─► JSEvaluateExtractor
                ├─► BSExtractor
                ├─► AXTreeExtractor
                └─► ...
                        │
                        └─► 成功 (>=2 产品)? → 返回结果
```

### 5. 失败重试 (Planner.get_next)

```
Planner.get_next(ctx)
    │
    ├─► 检查是否还有未尝试策略
    │
    ├─► 分析失败原因
    │
    ├─► 重新排序剩余策略
    │       │
    │       └─► CrawlPolicyScorer.rank_candidates_for_failure()
    │               │
    │               ├─► 考虑 block_type 细分统计
    │               └─► 考虑 js_challenge, captcha_type 等
    │
    ├─► task.advance()
    │
    └─► 返回下一个策略
```

## 评分公式

```
total_score =
    success_rate * 100           # 成功率
  + avg_products * 3             # 产量
  + order_bonus                  # 顺序加成
  + contextual_bonus            # 上下文加成
  + llm_bonus                   # LLM 加成
  - latency_penalty             # 延迟惩罚
  - block_penalty               # 阻塞惩罚
  - anti_bot_penalty            # 反爬惩罚
  - cost_penalty                # 成本惩罚
  - instability_penalty          # 不稳定性惩罚
```

## 模块依赖

```
api/
├── crawler.py          # SmartCrawlerRuntime 入口
├── orchestrator.py     # 编排层
└── models.py          # API 模型

spider/
├── runner.py          # CrawlRunner (并发控制, CAPTCHA)
├── coordinator.py     # CrawlCoordinator (多线程协调)
├── runtime/
│   ├── crawl.py       # CrawlTask, CrawlPolicy, RenderType 等
│   └── task_context.py # 任务执行上下文
└── engine/
    ├── core/
    │   ├── crawl_engine.py  # Crawler (单任务执行器)
    │   ├── planner.py      # Planner (策略管理)
    │   ├── queue.py        # Queue, SiteCircuitBreaker
    │   ├── results.py      # CrawlResult
    │   ├── trace_store.py   # TraceStore
    │   └── outcomes.py     # FailureOutcomeHandler
    ├── crawl_policy_generator.py  # CrawlPolicyGenerator
    ├── policy_engine.py    # CrawlPolicyScorer
    ├── captcha/           # CAPTCHA 检测和解决
    ├── anti_bot/          # 反爬检测和处理
    ├── proxy/             # 代理管理
    └── extraction/
        ├── engine/
        │   ├── extraction_engine.py  # ExtractionEngine
        │   ├── policy_engine.py     # ExtractionPolicyEngine
        │   └── registry.py          # 提取器注册表
        ├── extractors/      # 具体提取器实现
        ├── templates/       # 模板提取
        └── analysis/       # 页面分析

browser/
├── fetching.py          # Fetcher (页面抓取)
├── base.py             # 浏览器基类
├── pools/              # 浏览器池 (存在但未使用)
├── wrappers/           # 浏览器封装
└── human/              # 人类行为模拟
```

## 状态管理

### TaskContext

记录单个任务执行过程中的事件:

```python
class TaskContext:
    task: CrawlTask
    events: list[Event]           # 所有事件
    attempt_count: int           # 尝试次数
    tried_strategies: set        # 已尝试的策略

    def add_event(event)
    def add_tried_strategy(strategy)
    def increment_attempt()
    def set_result(result)
```

### SiteMemory

站点级记忆，记住成功的策略:

```python
class SiteMemory:
    site: str
    page_pattern: str
    successful_strategies: list[CrawlPolicy]  # 按成功率排序
    total_runs: int
    total_successes: int
```
