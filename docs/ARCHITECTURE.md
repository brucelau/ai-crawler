# Crawler Architecture

## 设计原则

- **一等公民**：TaskEngine、Crawler、PolicyEngine、ExtractionEngine 是核心抽象
- **全局唯一组件**：PolicyEngine、ExtractionEngine、MemoryStore 全局唯一
- **Crawler 可多个**：并行执行提升吞吐
- **只读原则**：PolicyEngine 和 ExtractionEngine 只读 TaskContext
- **TaskContext 贯穿**：每个任务创建，TaskContext 记录执行过程

---

## 一等公民

| 一等公民 | 数量 | 职责 |
|----------|------|------|
| **TaskEngine** | 1 | 协调分发任务，收集结果 |
| **Crawler** | N | 执行任务，维护 TaskContext |
| **PolicyEngine** | 1 | 爬虫策略决策，只读 TaskContext |
| **ExtractionEngine** | 1 | 内容提取，只读 TaskContext |

---

## 全局组件

| 组件 | 数量 | 职责 |
|------|------|------|
| **MemoryStore** | 1 | 站点记忆存储 |

---

## 数据模型

### TaskContext

每个任务创建一个 TaskContext，执行完后销毁。

```python
@dataclass
class TaskContext:
    task: Task

    events: list[Event] = field(default_factory=list)
    tried_strategies: list[CrawlStrategy] = field(default_factory=list)
    attempt_count: int = 0
    result: CrawlResult = None

    @property
    def events(self) -> list[Event]: ...

    @property
    def tried_strategies(self) -> list[CrawlStrategy]: ...

    @property
    def attempt_count(self) -> int: ...

    def add_event(self, event: Event): ...

    def add_tried_strategy(self, strategy: CrawlStrategy): ...

    def increment_attempt(self): ...

    def set_result(self, result: CrawlResult): ...
```

### SiteMemory

```python
class SiteMemory:
    site: str
    successful_strategies: list[CrawlStrategy]
    failed_strategies: list[CrawlStrategy]
    best_render_type: RenderType
    best_proxy: ProxyType
    extraction_method_stats: dict[str, int]
    total_runs: int
    success_rate: float
```

---

## 架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TaskEngine                                   │
│                           (任务引擎 - 1个)                              │
│                                                                             │
│   run(tasks):                                                             │
│       for task in tasks:                                                  │
│           result = crawler.execute(task)                                   │
│           results.append(result)                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   │ task
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                               Crawler                                      │
│                            (爬虫 - N个)                                 │
│                                                                             │
│   execute(task) → CrawlResult                                            │
│       │                                                                     │
│       ├── TaskContext(task)  ←─── 创建                                    │
│       │                                                                     │
│       ├── policy_engine.ask(ctx)  ───────────────────────┐               │
│       │      │                                              │              │
│       │      │  只读: ctx.task                             │              │
│       │      ▼                                              │              │
│       │  ←── CrawlStrategy                                  │              │
│       │                                                      │              │
│       ├── fetcher.fetch(task, strategy)                      │              │
│       │      │                                              │              │
│       │      ▼                                              │              │
│       │  ←── Attempt                                   │              │
│       │                                                      │              │
│       ├── ctx.add_event(event)  ←─── 写入只属于 Crawler    │              │
│       │                                                      │              │
│       ├── if not success:                                  │              │
│       │      policy_engine.get_next(ctx)  ────────────────┤              │
│       │      │  只读: ctx.events, ctx.tried_strategies    │              │
│       │      ▼                                              │              │
│       │  ←── CrawlStrategy (下一个策略)                    │              │
│       │      retry...                                       │              │
│       │                                                      │              │
│       ├── ctx.result = extraction_engine.extract(ctx)  ─────┤              │
│       │      │  只读: ctx.task, ctx.result                 │              │
│       │      ▼                                              │              │
│       │  ←── ExtractionResult                               │              │
│       │                                                      │              │
│       └── return ctx.result                                          │              │
│                                                                     │              │
└──────────────────────────────────────────────────────────────┼──────────────┘
                                                                      │
                    ┌─────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PolicyEngine                                    │
│                        (爬虫策略引擎 - 1个)                              │
│                                                                             │
│   ask(ctx) → CrawlStrategy                                               │
│       │  只读: ctx.task                                                 │
│       │  读取 MemoryStore                                           │
│       ▼                                                                   │
│   get_next(ctx) → CrawlStrategy                                         │
│       │  只读: ctx.events, ctx.tried_strategies                          │
│       ▼                                                                   │
│   record(ctx) → 更新全局统计                                             │
│       │  只读: ctx.events, ctx.result                                   │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                          ExtractionEngine                                  │
│                        (提取引擎 - 1个)                                  │
│                                                                             │
│   extract(ctx) → ExtractionResult                                         │
│       │  只读: ctx.task, ctx.result                                     │
│       ▼                                                                   │
│       ├── analyzer.analyze(html) → PageFeatures                         │
│       │                                                                   │
│       └── extraction_policy.ask(ctx, features) → method_order            │
│           │  只读: ctx.task                                               │
│           ▼                                                               │
│       try methods in order → products                                    │
│                                                                             │
│   内部组件:                                                               │
│   ├── PageAnalyzer                                                       │
│   └── ExtractionPolicyEngine (内部实现)                                  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                          MemoryStore                                   │
│                       (站点记忆 - 1个)                                   │
│                                                                             │
│   get(site) → SiteMemory                                                 │
│   update(memory)                                                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 核心流程

### TaskEngine.run()

```python
class TaskEngine:
    def run(self, tasks: list[Task]) -> list[CrawlResult]:
        results = []
        for task in tasks:
            result = self.crawler.execute(task)
            results.append(result)
        return results
```

### Crawler.execute()

```python
class Crawler:
    def execute(self, task: Task) -> CrawlResult:
        ctx = TaskContext(task)

        strategy = self.policy_engine.ask(ctx)

        while ctx.attempt_count < max_attempts:
            attempt = self.fetcher.fetch(task, strategy)
            ctx.add_event(attempt.to_event())

            if attempt.success:
                break

            ctx.add_tried_strategy(strategy)
            strategy = self.policy_engine.get_next(ctx)
            ctx.increment_attempt()

        ctx.result = self.extraction_engine.extract(ctx)
        return ctx.result
```

### PolicyEngine

```python
class PolicyEngine:
    def ask(self, ctx: TaskContext) -> CrawlStrategy:
        memory = self.memory_store.get(ctx.task.site)
        return self._decide(ctx.task, memory)

    def get_next(self, ctx: TaskContext) -> CrawlStrategy:
        memory = self.memory_store.get(ctx.task.site)
        return self._decide_next(ctx.events, ctx.tried_strategies, memory)

    def record(self, ctx: TaskContext):
        for event in ctx.events:
            self.stats_store.record(event)
```

### ExtractionEngine.extract()

```python
class ExtractionEngine:
    def extract(self, ctx: TaskContext) -> ExtractionResult:
        html = ctx.result.html
        page = ctx.result.page

        features = self.analyzer.analyze(html, page)
        method_order = self.extraction_policy.ask(ctx.task, features)

        for method in method_order:
            result = self._try_extract(method, page, html, ctx.task.url)
            if result.products:
                return result

        return ExtractionResult(products=[])
```

---

## 只读原则

| 组件 | 对 TaskContext | 权限 |
|------|---------------|------|
| **Crawler** | 创建 + 修改 | 读写 |
| **PolicyEngine** | 阅读信息做决策 | 只读 |
| **ExtractionEngine** | 阅读信息做决策 | 只读 |
| **TaskEngine** | 获取最终结果 | 只读 |

---

## 线程安全

- **MemoryStore**：内部有锁，支持多 Crawler 并发
- **PolicyEngine**：无状态，record() 更新 MemoryStore 时有锁保护
- **Crawler**：每个任务一个 TaskContext，无竞争
- **TaskEngine**：可配置线程池并行执行多个 Crawler

```python
class TaskEngine:
    def __init__(self, num_crawlers: int = 3):
        self.crawlers = [Crawler(i) for i in range(num_crawlers)]

    def run(self, tasks: list[Task]) -> list[CrawlResult]:
        with ThreadPoolExecutor(max_workers=len(self.crawlers)) as executor:
            futures = [executor.submit(crawler.execute, task)
                      for task in tasks]
            return [f.result() for f in futures]
```

---

## 模块结构

```
ai_crawler/
├── core/
│   ├── engine/
│   │   ├── task_engine.py      # TaskEngine
│   │   ├── crawler.py          # Crawler
│   │   ├── policy_engine.py    # PolicyEngine
│   │   ├── site_memory.py      # SiteMemory, MemoryStore
│   │   └── context.py           # TaskContext
│   │
│   ├── extraction/
│   │   ├── engine.py           # ExtractionEngine
│   │   ├── analyzer.py         # PageAnalyzer
│   │   └── strategies/         # ExtractionStrategy 子类
│   │
│   └── types/
│       └── task.py             # Task, CrawlStrategy, CrawlResult
│
└── browser/
    └── fetcher.py              # Fetcher
```
