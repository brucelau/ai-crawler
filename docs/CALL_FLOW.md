# AI-Crawler 调用流程图

本文档详细描述了 AI-Crawler 从入口到执行完毕的完整调用链路，精确到模块函数级别。

---

## 1. 入口层 (Entry Point)

```
用户调用
   │
   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  src/ai_crawler/__init__.py:19                                            │
│  def run_crawl(                                                            │
│      sites: list[str],                                                    │
│      query: str,                                                          │
│      pages: int,                                                          │
│      proxy_username: str = "",                                            │
│      proxy_password: str = "",                                            │
│      llm_api_key: str | None = None,                                     │
│      captcha_api_key: str | None = None,                                 │
│      output_dir: str = "output",                                         │
│      traces_dir: str = "traces",                                          │
│      max_ip_retries: int = 3,                                            │
│      proxy_disabled: bool = False,                                       │
│  ) -> RuntimeBatchResult:                                                │
│                                                                             │
│    1. runtime = SmartCrawlerRuntime(RuntimeOptions(...))                   │
│    2. return runtime.crawl(sites, query, pages)                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

**入口函数**: `run_crawl()` 位于 `src/ai_crawler/__init__.py`

---

## 2. 编排层 (Orchestration)

### 2.1 SmartCrawlerRuntime.crawl()

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  src/ai_crawler/orchestration/orchestrator.py:53                           │
│  class SmartCrawlerRuntime:                                                 │
│                                                                             │
│  def crawl(self, sites: list[str], query: str, pages: int) ->             │
│             RuntimeBatchResult:                                            │
│    └─ return self.crawl_tasks(self.build_search_tasks(sites, query, pages))│
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 SmartCrawlerRuntime.crawl_tasks() ⭐ 自动策略生成

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  src/ai_crawler/orchestration/orchestrator.py:56                           │
│                                                                             │
│  def crawl_tasks(self, tasks: list[RuntimeTask]) -> RuntimeBatchResult:  │
│    │                                                                       │
│    ├─ setup_logging(log_level=..., log_dir=..., log_file=...)             │
│    │   └─ src/ai_crawler/config/__init__.py                               │
│    │                                                                       │
│    ├─ trace_store = TraceStore(storage_dir=self.options.traces_dir)       │
│    │   └─ src/ai_crawler/core/engine/trace_store.py                      │
│    │                                                                       │
│    ├─ runner = self._build_runner(trace_store)                            │
│    │   └─ 构建 CrawlRunner (见 3.1)                                       │
│    │                                                                       │
│    ├─ # 构建 CrawlTask (自动策略生成) ⭐                                  │
│    │  crawl_tasks = [self._to_crawl_task(task) for task in tasks]        │
│    │    └─ _to_crawl_task()                                              │
│    │        ├─ CrawlTask.create(url=task.url, site=task.site,             │
│    │        │              use_auto_strategies=True)  # 默认开启           │
│    │        │   └─ src/ai_crawler/core/strategy.py                        │
│    │        │                                                            │
│    │        │   # 自动策略生成流程:                                       │
│    │        │   ├─ PatternMatcher.detect(site, url) → pattern           │
│    │        │   ├─ StrategyGenerator.generate_candidates()                 │
│    │        │   │   └─ ~20-50 个候选策略组合                            │
│    │        │   │                                                        │
│    │        │   ├─ PolicyEngine.rank_candidates()                        │
│    │        │   │   └─ 基于历史 trace 打分排序                          │
│    │        │   │                                                        │
│    │        │   └─ 取 top-10 → task.strategies                           │
│    │        │                                                            │
│    │        ├─ crawl_task.task_id = task.id                               │
│    │        └─ crawl_task.metadata.update(task.metadata)                    │
│    │                                                                       │
│    ├─ runner.add_tasks(crawl_tasks)  # 入队                               │
│    │   └─ CrawlQueue.enqueue(tasks)                                       │
│    │                                                                       │
│    ├─ core_results = runner.run()  # ⭐ 执 行                             │
│    │   └─ 返回 list[CrawlResult]                                          │
│    │                                                                       │
│    ├─ # 转换结果                                                           │
│    │  task_results = [                                                     │
│    │      RuntimeTaskResult.from_core_result(task_by_id[result.task.task_id],│
│    │                                        result)                        │
│    │      for result in core_results                                       │
│    │      if result.task.task_id in task_by_id                             │
│    │  ]                                                                   │
│    │                                                                       │
│    ├─ output_files = ProductOutputWriter(self.options.output_dir)          │
│    │                      .write(task_results)                             │
│    │   └─ src/ai_crawler/orchestration/storage.py                        │
│    │                                                                       │
│    └─ return RuntimeBatchResult(                                           │
│            products=[p for r in task_results for p in r.products],         │
│            task_results=task_results,                                       │
│            stats=stats,                                                     │
│            output_files=output_files,                                       │
│            traces_file=str(trace_store._session_file),                      │
│        )                                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 SmartCrawlerRuntime._build_runner()

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  src/ai_crawler/orchestration/orchestrator.py:98                           │
│                                                                             │
│  def _build_runner(self, trace_store: TraceStore) -> CrawlRunner:          │
│    │                                                                       │
│    ├─ dynamic_profile = self._build_dynamic_profile(llm_api_key)          │
│    │   └─ ProfileGenerator()(system_facts=get_system_facts())             │
│    │       └─ src/ai_crawler/core/llm/dspy_model.py                        │
│    │                                                                       │
│    ├─ captcha_solver = self._build_captcha_solver(captcha_api_key)         │
│    │   └─ CaptchaSolver(captcha_api_key)                                   │
│    │       └─ src/ai_crawler/integrations/captcha/solver.py                │
│    │                                                                       │
│    └─ return CrawlRunner(                                                  │
│            proxy_username=self.options.proxy_username,                       │
│            proxy_password=self.options.proxy_password,                        │
│            llm_api_key=self.options.llm_api_key,                            │
│            concurrency=self.options.concurrency,                             │
│            trace_store=trace_store,                                         │
│            dynamic_profile=dynamic_profile,                                  │
│            captcha_solver=captcha_solver,                                   │
│            max_ip_retries=self.options.max_ip_retries,                      │
│            proxy_disabled=self.options.proxy_disabled,                       │
│        )                                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 运行器层 (Runner)

### 3.1 CrawlRunner.__init__()

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  src/ai_crawler/core/runner.py:29                                           │
│  class CrawlRunner:                                                         │
│                                                                             │
│  def __init__(self,                                                         │
│               proxy_username: str,                                          │
│               proxy_password: str,                                          │
│               llm_api_key: str | None = None,                              │
│               concurrency: int = 3,                                         │
│               trace_store: TraceStore | None = None,                        │
│               dspy_model=None,                                              │
│               dynamic_profile: dict | None = None,                           │
│               captcha_solver=None,                                          │
│               max_ip_retries: int = 3,                                      │
│               proxy_disabled: bool = False):                                │
│    │                                                                       │
│    ├─ self.queue = CrawlQueue()                                           │
│    │   └─ src/ai_crawler/core/engine/queue.py                              │
│    │                                                                       │
│    ├─ self.proxy_provider = ProxyProvider(                                  │
│    │       proxy_username, proxy_password, disabled=proxy_disabled)         │
│    │   └─ src/ai_crawler/core/engine/proxying.py                           │
│    │                                                                       │
│    ├─ self.fetcher = Fetcher(self.proxy_provider, dynamic_profile)         │
│    │   └─ src/ai_crawler/browser/fetching.py                               │
│    │                                                                       │
│    ├─ self.anti_bot = AntiBotHandler()                                     │
│    │   └─ src/ai_crawler/core/engine/handler.py                            │
│    │                                                                       │
│    ├─ self._captcha = CaptchaService(captcha_solver)                       │
│    │   └─ src/ai_crawler/core/engine/captcha.py                             │
│    │                                                                       │
│    ├─ self.executor = ThreadPoolExecutor(max_workers=concurrency)           │
│    │                                                                       │
│    ├─ self._planner = TaskStrategyPlanner(trace_store=trace_store)         │
│    │   └─ src/ai_crawler/core/engine/planner.py                             │
│    │                                                                       │
│    ├─ self._execution = TaskExecutionEngine(                               │
│    │       self.fetcher,                                                   │
│    │       self.anti_bot,                                                  │
│    │       self.proxy_provider,                                             │
│    │       max_ip_retries,                                                 │
│    │       self.IP_ROTATION_BLOCK_TYPES,                                    │
│    │   )                                                                   │
│    │   └─ src/ai_crawler/core/engine/execution.py                           │
│    │                                                                       │
│    ├─ self._recommender = DSPyStrategyRecommender(dspy_model)              │
│    │   └─ src/ai_crawler/core/engine/recommendation.py                      │
│    │                                                                       │
│    ├─ self._trace_recorder = TraceRecorder(self.trace_store)               │
│    │   └─ src/ai_crawler/core/engine/outcomes.py                            │
│    │                                                                       │
│    ├─ self._failure_handler = FailureOutcomeHandler(                        │
│    │       self.queue,                                                     │
│    │       self._recommender if dspy_model else None,                      │
│    │       self._trace_recorder,                                           │
│    │       planner=self._planner,                                           │
│    │   )                                                                   │
│    │   └─ src/ai_crawler/core/engine/outcomes.py                            │
│    │                                                                       │
│    ├─ self._extraction_chains = SITE_EXTRACTION_CHAINS                    │
│    │   └─ src/ai_crawler/core/extraction/__init__.py                        │
│    │                                                                       │
│    ├─ self._extraction = ExtractionRuntimeService(self._extraction_chains)│
│    │   └─ src/ai_crawler/core/engine/extraction_runtime.py                  │
│    │                                                                       │
│    └─ self._processor = TaskProcessor(                                     │
│            queue=self.queue,                                                │
│            planner=self._planner,                                           │
│            execution=self._execution,                                       │
│            captcha=self._captcha,                                          │
│            fetcher=self.fetcher,                                            │
│            anti_bot=self.anti_bot,                                         │
│            trace_recorder=self._trace_recorder,                             │
│            failure_handler=self._failure_handler,                            │
│            extraction=self._extraction,                                     │
│            captcha_solver=self.captcha_solver,                              │
│        )                                                                   │
│        └─ src/ai_crawler/core/engine/processing.py                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 CrawlRunner.run()

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  src/ai_crawler/core/runner.py:108                                          │
│                                                                             │
│  def run(self, max_items: int = 100) -> list[CrawlResult]:                 │
│    │                                                                       │
│    ├─ self._running = True                                                 │
│    ├─ results = []                                                          │
│    │                                                                       │
│    └─ while self._running:                                                 │
│        │                                                                   │
│        ├─ pending, running, failed = self.queue.size()                      │
│        ├─ if pending == 0 and running == 0: break  # 队列空则退出         │
│        │                                                                   │
│        ├─ task = self.queue.dequeue()  # 取出一个任务                      │
│        ├─ if not task:                                                     │
│        │   └─ time.sleep(0.5); continue                                   │
│        │                                                                   │
│        ├─ if len(results) >= max_items:                                    │
│        │   └─ self._running = False; break                                │
│        │                                                                   │
│        ├─ future = self.executor.submit(self._process_one, task)          │
│        │   └─ 提交到线程池执行                                              │
│        │                                                                   │
│        └─ result = future.result()  # 等待执行结果                         │
│            ├─ results.append(result)                                        │
│            └─ self._results.append(result)  # 带锁写入                      │
│                                                                             │
│    └─ return results                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 CrawlRunner._process_one()

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  src/ai_crawler/core/runner.py:105                                          │
│                                                                             │
│  def _process_one(self, task: CrawlTask) -> CrawlResult:                   │
│    └─ return self._processor.process(task)                                  │
│        └─ src/ai_crawler/core/engine/processing.py:38                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 处理器层 (TaskProcessor)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  src/ai_crawler/core/engine/processing.py:13                                │
│  class TaskProcessor:                                                        │
│                                                                             │
│  def process(self, task: CrawlTask) -> CrawlResult:                        │
│    │                                                                       │
│    ├─ # ═══════════════════════════════════════════════════════════════     │
│    │   # 阶段 1: 策略规划 (Strategy Planning)                              │
│    │   # ═══════════════════════════════════════════════════════════════     │
│    │                                                                       │
│    │   memory = self.queue.site_memory.get((task.site, task.page_pattern))  │
│    │       └─ CrawlQueue.site_memory  # (site, page_pattern) -> SiteMemory │
│    │                                                                       │
│    │   prepared_memory = self.planner.prepare(task, memory)                 │
│    │   │   └─ TaskStrategyPlanner.prepare()                                │
│    │   │       ├─ if memory and memory.successful_strategies:              │
│    │   │       │   └─ task.add_strategy_front(best)  # 成功策略优先       │
│    │   │       │                                                            │
│    │   │       ├─ ranked = self._apply_policy_order(task)                 │
│    │   │       │   └─ PolicyEngine.rank_candidates()                      │
│    │   │       │       └─ src/ai_crawler/core/engine/policy_engine.py     │
│    │   │       │                                                            │
│    │   │       └─ if self.initial_tier_selector and should_consult_llm:    │
│    │   │           └─ self._apply_llm_tier(task, memory)                  │
│    │   │               └─ InitialTierSelector() → LLM 决定初始 tier        │
│    │   │                                                            │
│    │   └─ if prepared_memory is not None:                                │
│    │       └─ self.queue.site_memory[(task.site, task.page_pattern)] = prepared_memory │
│    │                                                                   │
│    │   strategy = self.planner.resolve(task)                             │
│    │   │   └─ TaskStrategyPlanner.resolve()                              │
│    │   │       └─ return task.current_strategy()                         │
│    │   │                                                            │
│    │   └─ if not strategy:                                              │
│    │       ├─ self.queue.on_failure(task, BlockType.UNKNOWN,             │
│    │       │           "All strategies exhausted")                       │
│    │       └─ return CrawlResult(success=False, error="All strategies...")│
│    │                                                                   │
│    ├─ # ═══════════════════════════════════════════════════════════════     │
│    │   # 阶段 2: 执行Fetch (Execution) ⭐                                 │
│    │   # ═══════════════════════════════════════════════════════════════     │
│    │                                                                   │
│    │   attempt = self.execution.execute(task, strategy)                  │
│    │   │   └─ TaskExecutionEngine.execute() → FetchAttempt               │
│    │   │       (详细流程见第 5 节)                                        │
│    │   │                                                           │
│    │   └─ trace_kwargs = self.trace_recorder.failure_trace_kwargs(      │
│    │           task, strategy, attempt, attempt_index)                    │
│    │       └─ TraceRecorder.failure_trace_kwargs()                      │
│    │                                                           │
│    ├─ # ═══════════════════════════════════════════════════════════════     │
│    │   # 阶段 3: 阻塞检测与处理 (Block Detection & Handling)              │
│    │   # ═══════════════════════════════════════════════════════════════     │
│    │                                                                   │
│    │   if attempt.blocked:                                              │
│    │   │                                                           │
│    │   ├─ # 3.1 CAPTCHA 特殊处理                                       │
│    │   │   if attempt.block_type == BlockType.CAPTCHA:                 │
│    │   │   ├─ if self.captcha_solver:                                 │
│    │   │   │   ├─ captcha_solved = self.captcha.solve(task, attempt.html)│
│    │   │   │   │   └─ CaptchaService.solve()                         │
│    │   │   │   │       └─ src/ai_crawler/core/engine/captcha.py         │
│    │   │   │   │                                                   │
│    │   │   │   ├─ if captcha_solved:                                  │
│    │   │   │   │   ├─ self.fetcher.release_page(attempt.page)          │
│    │   │   │   │   ├─ html, status_code, page = self.fetcher          │
│    │   │   │   │       .fetch_with_strategy(task, strategy)           │
│    │   │   │   │   └─ # 重新检测                                        │
│    │   │   │   │       blocked, block_type = self.anti_bot.is_blocked(│
│    │   │   │   │           status_code, html, context)                 │
│    │   │   │   │                                                   │
│    │   │   │   └─ if not blocked:                                    │
│    │   │   │       └─ # CAPTCHA 解决成 功，更新 attempt                 │
│    │   │   │                                                           │
│    │   │   └─ else:  # 无 captcha_solver                               │
│    │   │       └─ attempt.blocked = True  # 保持 blocked              │
│    │   │                                                           │
│    │   └─ # 3.2 通用阻塞处理                                           │
│    │       if attempt.blocked:                                         │
│    │           ├─ self.failure_handler.handle_blocked(                 │
│    │           │       task, attempt, trace_kwargs, attempt_index)      │
│    │           │   └─ FailureOutcomeHandler.handle_blocked()           │
│    │           │       ├─ trace_recorder.record_failure(trace_kwargs) │
│    │           │       ├─ needs_llm, next = queue.on_failure(         │
│    │           │       │       task, block_type, snippet)              │
│    │           │       ├─ if needs_llm and recommender:               │
│    │           │       │   └─ recommender.recommend(task, block_type) │
│    │           │       └─ planner.reprioritize_after_failure(...)     │
│    │           │                                                       │
│    │           └─ return CrawlResult(success=False, block_type=...)    │
│    │                                                                   │
│    ├─ # ═══════════════════════════════════════════════════════════════     │
│    │   # 阶段 4: 内容提取 (Extraction) ⭐                                │
│    │   # ═══════════════════════════════════════════════════════════════     │
│    │                                                                   │
│    │   extraction_decision = self.extraction.extract(                   │
│    │           task, strategy, attempt.page, attempt.html)               │
│    │       └─ ExtractionRuntimeService.extract() → ExtractionDecision   │
│    │           (详细流程见第 6 节)                                       │
│    │                                                                   │
│    ├─ # ═══════════════════════════════════════════════════════════════     │
│    │   # 阶段 5: 提取失败处理                                           │
│    │   # ═══════════════════════════════════════════════════════════════     │
│    │                                                                   │
│    │   if extraction_decision.should_retry:                             │
│    │   │   ├─ self.failure_handler.handle_extraction_retry(              │
│    │   │   │       task, attempt.html, extraction_decision.retry_reason)│
│    │   │   │                                                            │
│    │   │   └─ return CrawlResult(                                       │
│    │   │           success=False,                                       │
│    │   │           block_type=extraction_decision.retry_reason,         │
│    │   │           products=[],                                         │
│    │   │           extraction_strategy=extraction_decision.strategy_name,│
│    │   │       )                                                        │
│    │   │                                                                │
│    │   └─ if not extraction_decision.products:                         │
│    │       ├─ self.failure_handler.handle_extraction_retry(             │
│    │       │       task, attempt.html, "empty_content")                │
│    │       └─ return CrawlResult(success=False, block_type="empty_content")│
│    │                                                                   │
│    ├─ # ═══════════════════════════════════════════════════════════════     │
│    │   # 阶段 6: 成功记录                                               │
│    │   # ═══════════════════════════════════════════════════════════════     │
│    │                                                                   │
│    │   self.trace_recorder.record_success(                              │
│    │       task,                                                         │
│    │       strategy,                                                     │
│    │       attempt,                                                      │
│    │       attempt_index,                                                │
│    │       extraction_strategy=extraction_decision.strategy_name,        │
│    │       extraction_method=extraction_decision.method,                │
│    │       extraction_metadata=extraction_decision.metadata,            │
│    │   )                                                                │
│    │   └─ TraceRecorder.record_success()                               │
│    │                                                                   │
│    │   self.queue.on_success(task, strategy)                            │
│    │   └─ CrawlQueue.on_success()                                     │
│    │       ├─ task.fail_count = 0                                      │
│    │       ├─ running.pop(task_id)                                     │
│    │       └─ site_memory.add_success(strategy)                         │
│    │                                                                   │
│    └─ return CrawlResult(                                               │
│            success=True,                                                 │
│            products=extraction_decision.products,                        │
│            extraction_strategy=extraction_decision.strategy_name,        │
│            ...                                                           │
│        )                                                                │
│                                                                        │
│    finally:                                                             │
│        └─ self.fetcher.release_page(attempt.page)  # 释放页面资源        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. 执行引擎层 (TaskExecutionEngine)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  src/ai_crawler/core/engine/execution.py:40                                │
│  class TaskExecutionEngine:                                                  │
│                                                                             │
│  def execute(self, task: CrawlTask, strategy: CrawlStrategy) ->          │
│             FetchAttempt:                                                    │
│    │                                                                       │
│    ├─ # 延迟                                                               │
│    │   delay_min, delay_ms = strategy.delay_after                         │
│    │   └─ time.sleep(random.uniform(delay_min, delay_ms))                  │
│    │                                                                       │
│    ├─ # ═══════════════════════════════════════════════════════════════     │
│    │   # 步骤 1: Fetch HTML ⭐                                             │
│    │   # ═══════════════════════════════════════════════════════════════     │
│    │   │                                                                   │
│    │   html, status_code, page, latency_ms = self._fetch(task, strategy)    │
│    │   │   └─ self.fetcher.fetch_with_strategy(task, strategy)             │
│    │   │       └─ Fetcher.fetch_with_strategy()                           │
│    │   │           (详细路由见 5.1)                                        │
│    │   │                                                                   │
│    │   └─ # ═══════════════════════════════════════════════════════════     │
│    │       # 步骤 2: 构建检测上下文                                        │
│    │       # ═══════════════════════════════════════════════════════════     │
│    │       │                                                               │
│    │       context = self._build_detection_context(task, page)             │
│    │       │   └─ BlockDetectionContext(                                   │
│    │       │         site=task.site,                                       │
│    │       │         page_pattern=task.page_pattern.value,                 │
│    │       │         goal=task.metadata.get("goal", ""),                  │
│    │       │         semantic_confirmation=build_axtree_semantic_           │
│    │       │             confirmation(page, task.url, task.page_pattern)    │
│    │       │       )                                                      │
│    │       │       └─ src/ai_crawler/core/extraction/axtree.py            │
│    │       │                                                               │
│    │       │                                                               │
│    │       │                                                               │
│    ├─ # ═══════════════════════════════════════════════════════════════     │
│    │   # 步骤 3: 阻塞检测 ⭐                                               │
│    │   # ═══════════════════════════════════════════════════════════════     │
│    │   │                                                                   │
│    │   blocked, block_type = self.anti_bot.is_blocked(                     │
│    │           status_code, html, context)                                 │
│    │   │   └─ AntiBotHandler.is_blocked()                                  │
│    │   │       └─ BlockDetector.detect()                                   │
│    │   │           (详细逻辑见第 8 节)                                     │
│    │   │                                                                   │
│    │   │                                                                   │
│    │   │                                                                   │
│    │   ├─ # UC 搜索质量检查 (Cloudflare UC 特殊逻辑)                       │
│    │   │   if (not blocked                                                 │
│    │   │       and strategy.render == RenderType.CLOUDERA                  │
│    │   │       and task.page_pattern == PagePattern.SEARCH                 │
│    │   │       and not self._has_minimum_search_quality(task, html)):     │
│    │   │       └─ blocked=True, block_type=BlockType.EMPTY_RESPONSE        │
│    │   │           └─ _has_minimum_search_quality()                       │
│    │   │               ├─ site_markers = SEARCH_QUALITY_MARKERS[task.site] │
│    │   │               ├─ marker_hits = sum(1 for m in site_markers...)   │
│    │   │               └─ return marker_hits >= 2 or generic_hits >= 2    │
│    │   │                                                                   │
│    │   └─ self.anti_bot.record_attempt(url, strategy, block_type, blocked) │
│    │       └─ AntiBotHandler.record_attempt()                             │
│    │                                                                       │
│    ├─ # ═══════════════════════════════════════════════════════════════     │
│    │   # 步骤 4: IP 轮换 (如果需要)                                        │
│    │   # ═══════════════════════════════════════════════════════════════     │
│    │   │                                                                   │
│    │   if (blocked                                                        │
│    │       and block_type in self.ip_rotation_block_types                  │
│    │       and not self.proxy_provider.disabled                           │
│    │       and not self._should_short_circuit_retry(task, strategy, html,  │
│    │                                                    block_type)):      │
│    │       │                                                               │
│    │       ├─ html, status_code, page, blocked, block_type, latency_ms,   │
│    │       │   ip_rotation_count = self._retry_with_proxy_rotation(       │
│    │       │           task, strategy, block_type)                        │
│    │       │   │                                                           │
│    │       │   └─ for ip_retry in range(self.max_ip_retries):             │
│    │       │       ├─ new_proxy = self.proxy_provider.rotate_proxy(      │
│    │       │       │       strategy)                                      │
│    │       │       │   └─ ProxyProvider.rotate_proxy()                   │
│    │       │       │       └─ src/ai_crawler/core/engine/proxying.py       │
│    │       │       │                                                       │
│    │       │       ├─ if not new_proxy: break                            │
│    │       │       │                                                       │
│    │       │       ├─ time.sleep(random.uniform(1.0, 3.0))               │
│    │       │       │                                                       │
│    │       │       ├─ html, status_code, page, _ = self._fetch(task, s)   │
│    │       │       │                                                       │
│    │       │       ├─ blocked, block_type = self.anti_bot.is_blocked(...)│
│    │       │       │                                                       │
│    │       │       └─ if not blocked: break  # 成功，退出轮换             │
│    │       │                                                           │
│    │       └─ ip_rotation_count += 1                                     │
│    │                                                                       │
│    ├─ # ═══════════════════════════════════════════════════════════════     │
│    │   # 步骤 5: WAF 检测 & 指纹推断                                      │
│    │   # ═══════════════════════════════════════════════════════════════     │
│    │   │                                                                   │
│    │   response_headers = extract_response_headers(page, status_code)      │
│    │   │   └─ src/ai_crawler/core/engine/telemetry.py                      │
│    │   │                                                                   │
│    │   waf_detected = detect_waf(html, response_headers) if blocked else "" │
│    │   │   └─ src/ai_crawler/core/engine/telemetry.py                      │
│    │   │                                                                   │
│    │   block_reason = detect_block_reason(html, status_code, waf_detected)│
│    │   │   └─ src/ai_crawler/core/engine/telemetry.py                      │
│    │   │                                                                   │
│    │   fingerprint_profile = self.fetcher.dynamic_profile                 │
│    │   │                                                                   │
│    │   anti_bot_fingerprint = self.fingerprinter.infer(                    │
│    │           html,                                                       │
│    │           response_headers,                                          │
│    │           status_code,                                                │
│    │           block_type,                                                 │
│    │           waf_detected,                                               │
│    │           block_reason,                                               │
│    │       ).to_dict()                                                     │
│    │   │   └─ AntiBotFingerprinter.infer()                               │
│    │   │       └─ src/ai_crawler/core/engine/fingerprinter.py              │
│    │   │                                                                   │
│    └─ return FetchAttempt(                                                  │
│            html=html,                                                       │
│            status_code=status_code,                                        │
│            page=page,                                                       │
│            blocked=blocked,                                                 │
│            block_type=block_type,                                           │
│            latency_ms=latency_ms,                                           │
│            cost_estimate=self._estimate_cost(strategy, latency_ms),         │
│            ip_rotation_count=ip_rotation_count,                            │
│            response_headers=response_headers,                               │
│            waf_detected=waf_detected,                                       │
│            block_reason=block_reason,                                       │
│            fingerprint_profile=fingerprint_profile,                         │
│            anti_bot_fingerprint=anti_bot_fingerprint,                       │
│        )                                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.1 Fetcher.fetch_with_strategy() 路由

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  src/ai_crawler/browser/fetching.py:586                                    │
│  class Fetcher:                                                             │
│                                                                             │
│  def fetch_with_strategy(self, task, strategy) -> (html, status_code, page)│
│    │                                                                       │
│    ├─ if strategy.render == RenderType.CAMOUFOX:                            │
│    │   └─ return self._fetch_with_camoufox(task, strategy)                 │
│    │       └─ src/ai_crawler/browser/camoufox_wrapper.py                    │
│    │                                                                           │
│    ├─ if strategy.render == RenderType.CLOAKBROWSER:                        │
│    │   └─ return self._fetch_with_cloakbrowser(task, strategy)            │
│    │       └─ src/ai_crawler/browser/cloakbrowser_wrapper.py               │
│    │                                                                           │
│    ├─ if strategy.render == RenderType.PLAYWRIGHT:                          │
│    │   └─ return self._fetch_with_playwright(task, strategy)              │
│    │       └─ src/ai_crawler/browser/playwright_wrapper.py                 │
│    │                                                                           │
│    ├─ if strategy.render == RenderType.CLOUDERA:  # undetected-chromedriver │
│    │   └─ return self._fetch_with_uc(task, strategy)                     │
│    │       └─ src/ai_crawler/browser/undetected_chromedriver_wrapper.py    │
│    │                                                                           │
│    ├─ if strategy.render == RenderType.CLOUDSCRAPER:                        │
│    │   └─ return self._fetch_with_cloudscraper(task, strategy)            │
│    │       └─ src/ai_crawler/browser/cloudscraper_wrapper.py               │
│    │                                                                           │
│    ├─ if strategy.render == RenderType.SELENIUMBASE:                       │
│    │   └─ return self._fetch_with_seleniumbase(task, strategy)            │
│    │       └─ src/ai_crawler/browser/seleniumbase_wrapper.py               │
│    │                                                                           │
│    ├─ if strategy.render == RenderType.KAMELEO:                            │
│    │   └─ return self._fetch_with_kameleo(task, strategy)                │
│    │       └─ src/ai_crawler/browser/kameleo_wrapper.py                   │
│    │                                                                           │
│    ├─ if strategy.render == RenderType.LIGHTPAND:                          │
│    │   └─ return self._fetch_with_lightpanda(task, strategy)             │
│    │       └─ src/ai_crawler/browser/lightpanda_wrapper.py                │
│    │                                                                           │
│    └─ else:  # RenderType.NONE                                              │
│        └─ return self._fetch_with_httpx(task, strategy)                    │
│            └─ curl_cffi requests                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. 提取服务层 (ExtractionRuntimeService)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  src/ai_crawler/core/engine/extraction_runtime.py:19                        │
│  class ExtractionRuntimeService:                                             │
│                                                                             │
│  def extract(self, task, strategy, page, html) -> ExtractionDecision:       │
│    │                                                                       │
│    ├─ # ═══════════════════════════════════════════════════════════════     │
│    │   # 步骤 1: 站点提取链 (Site Extraction Chain) ⭐                     │
│    │   # ═══════════════════════════════════════════════════════════════     │
│    │   │                                                                   │
│    │   chain = self.extraction_chains.get(task.site)                       │
│    │   page_type = self._resolve_page_type(task)                           │
│    │   │   └─ if page_pattern: return page_pattern.value                   │
│    │   │       elif goal == "reviews": return "review"                     │
│    │   │       else: return goal or "unknown"                              │
│    │   │                                                                   │
│    │   └─ extraction_result = chain.extract(page, html, task.url, page_type)│
│    │       └─ ExtractorChain.extract()                                     │
│    │           (详细流程见 6.1)                                             │
│    │                                                                       │
│    ├─ # 检查提取结果                                                        │
│    │   if extraction_result.products:                                       │
│    │       └─ return ExtractionDecision(                                    │
│    │               products=extraction_result.products,                     │
│    │               should_retry=False,                                      │
│    │               strategy_name=extraction_result.strategy,                │
│    │               method=extraction_result.method,                         │
│    │               metadata={"axtree_hit": strategy == "axtree"},            │
│    │           )                                                           │
│    │                                                                       │
│    ├─ # ═══════════════════════════════════════════════════════════════     │
│    │   # 步骤 2: LLM Fallback ⭐ (无产品时)                               │
│    │   # ═══════════════════════════════════════════════════════════════     │
│    │   │                                                                   │
│    │   if html:                                                            │
│    │       └─ llm_products = extract_with_llm_page(                       │
│    │               html,                                                    │
│    │               page,                                                    │
│    │               task.site,                                              │
│    │               self._resolve_page_type(task),                           │
│    │               task.url,                                                │
│    │           )                                                           │
│    │           └─ src/ai_crawler/core/llm/llm_extractor.py                 │
│    │               └─ DSPy LLM 提取                                        │
│    │                                                                       │
│    │       if not llm_products:                                            │
│    │           └─ # 强制重新生成                                           │
│    │               llm_products = extract_with_llm_page(                   │
│    │                       html, page, task.site, page_type, task.url,      │
│    │                       force_regenerate=True,                           │
│    │                   )                                                    │
│    │                                                                       │
│    │       if llm_products:                                                │
│    │           └─ return ExtractionDecision(                               │
│    │                   products=llm_products,                              │
│    │                   should_retry=False,                                 │
│    │                   strategy_name="llm_selector_fallback",              │
│    │                   method="llm_selector",                              │
│    │                   metadata={"axtree_hit": page is not None},          │
│    │               )                                                       │
│    │                                                                       │
│    ├─ # ═══════════════════════════════════════════════════════════════     │
│    │   # 步骤 3: 升级渲染 (Upgrade Render)                                 │
│    │   # ═══════════════════════════════════════════════════════════════     │
│    │   │                                                                   │
│    │   upgrade_render = self._get_upgrade_render(strategy)                  │
│    │   │   └─ upgrade_map = {                                              │
│    │   │         NONE → CLOUDSCRAPER,                                      │
│    │   │         CLOUDSCRAPER → LIGHTPAND,                                │
│    │   │         LIGHTPAND → PLAYWRIGHT,                                   │
│    │   │         PLAYWRIGHT → CAMOUFOX,                                    │
│    │   │         CAMOUFOX → CLOUDERA,                                     │
│    │   │         CLOUDERA → SELENIUMBASE,                                 │
│    │   │         SELENIUMBASE → CLOAKBROWSER,                             │
│    │   │     }                                                             │
│    │   │   └─ return upgrade_map.get(strategy.render)                      │
│    │   │                                                                   │
│    │   if upgrade_render:                                                  │
│    │       ├─ render_to_tier = {...}                                      │
│    │       ├─ upgrade_tier = render_to_tier.get(upgrade_render, 1)         │
│    │       ├─ upgrade = CrawlStrategy.from_tier(upgrade_tier)             │
│    │       │   └─ CrawlStrategy.from_tier()                               │
│    │       │       └─ src/ai_crawler/core/strategy.py                      │
│    │       │                                                                   │
│    │       ├─ task.add_strategy_next(upgrade)  # 添加升级策略到任务        │
│    │       │   └─ CrawlTask.add_strategy_next()                          │
│    │       │                                                                   │
│    │       └─ return ExtractionDecision(                                  │
│    │               products=[],                                            │
│    │               should_retry=True,                                      │
│    │               retry_reason="empty_content",                           │
│    │               strategy_name=extraction_result.strategy,               │
│    │               method=extraction_result.method,                         │
│    │           )                                                           │
│    │                                                                       │
│    └─ # 最终失败                                                            │
│        └─ return ExtractionDecision(                                       │
│                products=[],                                                │
│                should_retry=False,                                          │
│                strategy_name=extraction_result.strategy,                    │
│                method=extraction_result.method,                             │
│            )                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.1 ExtractorChain 提取链

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  src/ai_crawler/core/extraction/__init__.py                                 │
│  class ExtractorChain:                                                       │
│                                                                             │
│  def extract(self, page, html, url, page_type) -> ExtractionResult:        │
│    │                                                                       │
│    │   # 按顺序尝试 5 种提取器，直到获取产品                                │
│    │                                                                       │
│    ├─ # 1️⃣ JSON-LD 提取                                                   │
│    │   ├─ result = JSONLDExtraction.extract(page, html, url, page_type)    │
│    │   │   └─ src/ai_crawler/core/extraction/json_ld.py                    │
│    │   │       ├─ 查找 <script type="application/ld+json"> 标签           │
│    │   │       ├─ 解析 JSON-LD 结构化数据                                  │
│    │   │       └─ 提取 Product 对象                                        │
│    │   │                                                                   │
│    │   └─ if result.products: return result                                │
│    │                                                                       │
│    ├─ # 2️⃣ JS 注入提取                                                     │
│    │   ├─ result = JSEvaluateExtraction.extract(page, html, url, page_type)│
│    │   │   └─ src/ai_crawler/core/extraction/js_eval.py                     │
│    │   │       ├─ 执行页面 JavaScript 注入                                  │
│    │   │       ├─ 尝试从 DOM 中提取数据                                    │
│    │   │       └─ 站点特定 JS 模板 (amazon, walmart, etc.)                 │
│    │   │                                                                   │
│    │   └─ if result.products: return result                                │
│    │                                                                       │
│    ├─ # 3️⃣ API 拦截提取                                                    │
│    │   ├─ result = APIInterceptExtraction.extract(page, html, url, ...)    │
│    │   │   └─ src/ai_crawler/core/extraction/api_intercept.py              │
│    │   │       ├─ 拦截网络请求/API 响应                                   │
│    │   │       └─ 从 API 响应中提取产品数据                               │
│    │   │                                                                   │
│    │   └─ if result.products: return result                                │
│    │                                                                       │
│    ├─ # 4️⃣ AXTree 提取                                                     │
│    │   ├─ result = AXTreeExtraction.extract(page, html, url, page_type)   │
│    │   │   └─ src/ai_crawler/core/extraction/axtree.py                     │
│    │   │       ├─ 获取页面 Accessibility Tree                               │
│    │   │       ├─ 解析 AXTree 结构                                         │
│    │   │       └─ 提取产品信息                                             │
│    │   │                                                                   │
│    │   └─ if result.products: return result                                │
│    │                                                                       │
│    ├─ # 5️⃣ BS/CSS 提取 (兜底)                                             │
│    │   ├─ result = BSExtraction.extract(page, html, url, page_type)       │
│    │   │   └─ src/ai_crawler/core/extraction/bs_css.py                     │
│    │   │       ├─ 使用 BeautifulSoup 解析 HTML                             │
│    │   │       ├─ CSS 选择器提取                                          │
│    │   │       └─ 站点特定 CSS 选择器模板                                  │
│    │   │                                                                   │
│    │   └─ return result  # 返回最终结果 (无论是否有产品)                   │
│    │                                                                       │
│    └─ return ExtractionResult(products=[], strategy="none", method="none") │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. 阻塞检测流程 (Block Detection)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  src/ai_crawler/core/engine/handler.py                                     │
│  class AntiBotHandler:                                                       │
│                                                                             │
│  def is_blocked(self, status_code, html, context) -> (bool, BlockType):   │
│    └─ return BlockDetector.detect(status_code, html, len(html), context)   │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  src/ai_crawler/core/engine/handler.py                                     │
│  class BlockDetector:                                                        │
│                                                                             │
│  @classmethod                                                               │
│  def detect(cls, status_code, html, content_length, context) -> (bool, str)│
│    │                                                                       │
│    ├─ # ═══════════════════════════════════════════════════════════════     │
│    │   # 优先级 1: HTTP 状态码检查                                          │
│    │   # ═══════════════════════════════════════════════════════════════     │
│    │   │                                                                   │
│    │   if status_code == 403:   return True, BlockType.HTTP_403           │
│    │   if status_code == 429:   return True, BlockType.HTTP_429           │
│    │   if status_code == 451:   return True, BlockType.HTTP_451           │
│    │   if status_code >= 500:   return True, BlockType.HTTP_TIMEOUT        │
│    │   if status_code == 0 or status_code is None:                         │
│    │       return True, BlockType.EMPTY_RESPONSE                           │
│    │                                                                       │
│    ├─ # ═══════════════════════════════════════════════════════════════     │
│    │   # 优先级 2: 空响应检查                                               │
│    │   # ═══════════════════════════════════════════════════════════════     │
│    │   │                                                                   │
│    │   if content_length < 5000 or len(html) < 1000:                       │
│    │       # 需要语义确认来决定是否真正 blocked                             │
│    │       if context.semantic_confirmation and                             │
│    │          context.semantic_confirmation.get("confidence", 0) > 0.7:    │
│    │           └─ return False, BlockType.NONE  # 语义确认放行            │
│    │       └─ return True, BlockType.EMPTY_RESPONSE                        │
│    │                                                                       │
│    ├─ # ═══════════════════════════════════════════════════════════════     │
│    │   # 优先级 3: 强信号检查 (高置信度，直接 blocked)                      │
│    │   # ═══════════════════════════════════════════════════════════════     │
│    │   │                                                                   │
│    │   html_lower = html.lower()                                           │
│    │                                                                       │
│    │   ├─ # CAPTCHA 强信号                                                 │
│    │   │   if any(p in html_lower for p in STRONG_CAPTCHA_PATTERNS):      │
│    │   │       └─ return True, BlockType.CAPTCHA                           │
│    │   │       # "are you a robot", "prove you're not a robot", etc.       │
│    │   │                                                                   │
│    │   ├─ # Cloudflare 强信号                                              │
│    │   │   if any(p in html_lower for p in STRONG_CF_PATTERNS):           │
│    │   │       └─ return True, BlockType.CLOUDFLARE                        │
│    │   │       # "checking your browser", "cf-challenge", etc.             │
│    │   │                                                                   │
│    │   ├─ # Bot 检测强信号                                                 │
│    │   │   if any(p in html_lower for p in STRONG_BOT_PATTERNS):          │
│    │   │       └─ return True, BlockType.BOT_DETECTED                      │
│    │   │       # "blocked your ip", "unusual traffic", etc.                 │
│    │   │                                                                   │
│    │   └─ # 浏览器错误强信号                                               │
│    │       if any(p in html_lower for p in BROWSER_ERROR_PATTERNS):      │
│    │           └─ return True, BlockType.HTTP_TIMEOUT                       │
│    │           # "err_no_supported_proxies", "sorry! something went wrong" │
│    │                                                                       │
│    ├─ # ═══════════════════════════════════════════════════════════════     │
│    │   # 优先级 4: 弱信号检查 (需要语义确认)                               │
│    │   # ═══════════════════════════════════════════════════════════════     │
│    │   │                                                                   │
│    │   ├─ # Cloudflare 弱信号                                              │
│    │   │   if "cloudflare" in html_lower and not any(p in html_lower...): │
│    │   │       └─ # 需要语义确认                                           │
│    │   │           if semantic_confirmation and confidence > 0.7:          │
│    │   │               └─ return False, BlockType.NONE  # 放行             │
│    │   │           └─ return True, BlockType.CLOUDFLARE                    │
│    │   │                                                                   │
│    │   └─ # Bot 检测弱信号                                                 │
│    │       if any(p in html_lower for p in WEAK_BOT_PATTERNS):            │
│    │           └─ # 需要语义确认                                           │
│    │               └─ (同上)                                                │
│    │                                                                       │
│    ├─ # ═══════════════════════════════════════════════════════════════     │
│    │   # 优先级 5: 页面类型感知                                             │
│    │   # ═══════════════════════════════════════════════════════════════     │
│    │   │                                                                   │
│    │   └─ # search 页面更宽容，detail 页面更严格                           │
│    │       if context.page_pattern == "search":                             │
│    │           └─ # search 页面对短内容更宽容                               │
│    │       elif context.page_pattern == "detail":                          │
│    │           └─ # detail 页面需要更强的语义确认                           │
│    │                                                                       │
│    └─ # 默认: 未检测到阻塞                                                  │
│        └─ return False, BlockType.NONE                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. 失败处理流程 (Failure Handling)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  src/ai_crawler/core/engine/outcomes.py                                    │
│  class FailureOutcomeHandler:                                                │
│                                                                             │
│  def handle_blocked(self, task, attempt, trace_kwargs, attempt_index):    │
│    │                                                                       │
│    ├─ # 1. 记录失败 trace                                                   │
│    │   └─ self.trace_recorder.record_failure(trace_kwargs)                │
│    │       └─ TraceRecorder.record_failure()                               │
│    │                                                                       │
│    ├─ # 2. 队列处理                                                        │
│    │   needs_llm, next_strategy = self.queue.on_failure(                   │
│    │           task, attempt.block_type, html[:200])                       │
│    │       └─ CrawlQueue.on_failure()                                      │
│    │           │                                                           │
│    │           ├─ task.fail_count += 1                                    │
│    │           │                                                           │
│    │           ├─ task.current_index += 1  # 前进到下一策略               │
│    │           │                                                           │
│    │           ├─ if task.current_index < len(task.strategies):            │
│    │           │   └─ # 还有更多策略可用                                    │
│    │           │       └─ return False, task.current_strategy()            │
│    │           │                                                           │
│    │           └─ else:  # 策略耗尽                                        │
│    │               └─ task.status = "exhausted"                           │
│    │               └─ return True, None  # needs_llm=True                 │
│    │                                                                       │
│    ├─ # 3. LLM 推荐 (策略耗尽时)                                           │
│    │   if needs_llm and self.recommender:                                  │
│    │       └─ recommended = self.recommender.recommend(                    │
│    │               task, attempt.block_type, attempt.block_reason)          │
│    │           └─ DSPyStrategyRecommender.recommend()                      │
│    │               └─ src/ai_crawler/core/engine/recommendation.py          │
│    │                   └─ DSPy LLM 推理推荐新策略                          │
│    │                                                                       │
│    └─ # 4. 重排优先级 (基于条件统计) ⭐                                     │
│        └─ self.planner.reprioritize_after_failure(                        │
│                task, attempt.block_type)                                    │
│            └─ TaskStrategyPlanner.reprioritize_after_failure()             │
│                └─ PolicyEngine.rank_candidates_for_failure()                │
│                    │                                                       │
│                    ├─ 传入 block_type                                     │
│                    └─ PolicyEngine.rank_candidates(block_type=http_403)    │
│                        │                                                   │
│                        └─ 使用条件统计评分:                               │
│                             当遇到 HTTP_403 时，                          │
│                             选择历史上对 HTTP_403                          │
│                             成功率最高的策略                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  def handle_extraction_retry(self, task, html, retry_reason):              │
│    └─ self.queue.on_failure(task, retry_reason, html[:200])                │
│        └─ CrawlQueue.on_failure()  # 同上                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. 完整调用时序图

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  用户                                                                       │
│   │                                                                       │
│   ▼                                                                       │
│  run_crawl()                                                               │
│   │                                                                       │
│   ▼                                                                       │
│  SmartCrawlerRuntime.crawl()                                              │
│   │                                                                       │
│   ├──► build_search_tasks() ────► RuntimeTask[]                           │
│   │                                                                       │
│   ▼                                                                       │
│  SmartCrawlerRuntime.crawl_tasks() ⭐                                    │
│   │                                                                       │
│   ├─► setup_logging()                                                    │
│   │                                                                       │
│   ├─► TraceStore()                                                        │
│   │                                                                       │
│   ├─► _to_crawl_task()  # 自动策略生成 ⭐                               │
│   │    │                                                                   │
│   │    ├─► CrawlTask.create(url, site, use_auto_strategies=True)        │
│   │    │    │                                                            │
│   │    │    ├─► StrategyGenerator.generate_candidates()                 │
│   │    │    │    └─► ~20-50 个候选策略                                │
│   │    │    │                                                            │
│   │    │    ├─► PolicyEngine.rank_candidates()                          │
│   │    │    │    └─► 基于历史 trace 打分                            │
│   │    │    │                                                            │
│   │    │    └─► 取 top-10 → task.strategies                           │
│   │    │                                                                   │
│   ├─► _build_runner() ──────────────────────────┐                         │
│   │                                               │                         │
│   │   CrawlRunner.__init__()                     │                         │
│   │    ├─► CrawlQueue()                         │                         │
│   │    ├─► ProxyProvider()                      │                         │
│   │    ├─► Fetcher()                            │                         │
│   │    ├─► AntiBotHandler()                      │                         │
│   │    ├─► CaptchaService()                      │                         │
│   │    ├─► TaskStrategyPlanner()                 │                         │
│   │    ├─► TaskExecutionEngine()                  │                         │
│   │    ├─► DSPyStrategyRecommender()             │                         │
│   │    ├─► TraceRecorder()                       │                         │
│   │    ├─► FailureOutcomeHandler()               │                         │
│   │    ├─► ExtractionRuntimeService()            │                         │
│   │    └─► TaskProcessor()                       │                         │
│   │                                               │                         │
│   ├─► runner.run() ◄─────────────────────────────┘                         │
│   │    │                                                                 │
│   │    │  ┌──────────────────────────────────────────────────────────┐     │
│   │    │  │              ThreadPoolExecutor                           │     │
│   │    │  │                                                       │     │
│   │    ├──► executor.submit(_process_one, task)                   │     │
│   │    │  │                                                       │     │
│   │    │  ▼                                                       │     │
│   │    │  ┌────────────────────────────────────────────────────┐   │     │
│   │    │  │  TaskProcessor.process(task)                        │   │     │
│   │    │  │                                                     │   │     │
│   │    │  ├─► planner.prepare()                                 │   │     │
│   │    │  │    └─► TaskStrategyPlanner.prepare()                │   │     │
│   │    │  │         └─► PolicyEngine.rank_candidates()          │   │     │
│   │    │  │                                                     │   │     │
│   │    │  ├─► planner.resolve()                                 │   │     │
│   │    │  │    └─► task.current_strategy()                      │   │     │
│   │    │  │                                                     │   │     │
│   │    │  ├─► execution.execute()                               │   │     │
│   │    │  │    ├─► fetcher.fetch_with_strategy()               │   │     │
│   │    │  │    │    └─► [_fetch_with_xxx] ──► (html, code, page)│   │     │
│   │    │  │    │                                                 │   │     │
│   │    │  │    ├─► anti_bot.is_blocked()                        │   │     │
│   │    │  │    │    └─► BlockDetector.detect()                  │   │     │
│   │    │  │    │                                                 │   │     │
│   │    │  │    └─► [可选] proxy rotation                        │   │     │
│   │    │  │         └─► proxy_provider.rotate_proxy()          │   │     │
│   │    │  │                                                     │   │     │
│   │    │  ├─► extraction.extract()                              │   │     │
│   │    │  │    │                                                 │   │     │
│   │    │  │    ├─► chain.extract()                             │   │     │
│   │    │  │    │    ├─► JSONLDExtraction.extract()             │   │     │
│   │    │  │    │    ├─► JSEvaluateExtraction.extract()         │   │     │
│   │    │  │    │    ├─► APIInterceptExtraction.extract()       │   │     │
│   │    │  │    │    ├─► AXTreeExtraction.extract()            │   │     │
│   │    │  │    │    └─► BSExtraction.extract()                │   │     │
│   │    │  │    │                                                 │   │     │
│   │    │  │    └─► [fallback] extract_with_llm_page()         │   │     │
│   │    │  │         └─► DSPy LLM 提取                           │   │     │
│   │    │  │                                                     │   │     │
│   │    │  ├─► if blocked:                                      │   │     │
│   │    │  │    └─► failure_handler.handle_blocked()            │   │     │
│   │    │  │         ├─► queue.on_failure()                      │   │     │
│   │    │  │         └─► [DSPy recommend if needed]             │   │     │
│   │    │  │                                                     │   │     │
│   │    │  ├─► if should_retry:                                  │   │     │
│   │    │  │    └─► return FAILURE                               │   │     │
│   │    │  │                                                     │   │     │
│   │    │  └─► return SUCCESS + products                         │   │     │
│   │    │  └─► CrawlResult                                       │   │     │
│   │    │                                                       │     │
│   │    └─◄ result = future.result() ◄──────────────────────────┘     │
│   │         │                                                           │
│   │         ▼                                                           │
│   ├─► runner.run() 返回 list[CrawlResult]                               │
│   │                                                                       │
│   ▼                                                                       │
│  ProductOutputWriter.write(task_results)                                  │
│   │                                                                       │
│   ▼                                                                       │
│  RuntimeBatchResult ──► 返回给用户                                        │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. 自动策略生成 (StrategyGenerator)

### 10.1 背景

**旧方案问题**：`URL_PATTERNS` 硬编码策略列表
- 人工配置，维护成本高
- 无法适应站点反爬变化
- 新站点需要手动配置

**新方案**：`StrategyGenerator` 自动生成 + `PolicyEngine` 排序

### 10.2 核心逻辑

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  src/ai_crawler/core/engine/strategy_generator.py                           │
│  class StrategyGenerator:                                                   │
│                                                                             │
│  @classmethod                                                             │
│  def generate_candidates(cls, site, page_pattern) -> list[CrawlStrategy]:    │
│    │                                                                       │
│    │   # 1. 定义所有可能的策略维度                                         │
│    │   RENDER_ORDER = [NONE, CLOUDSCRAPER, LIGHTPAND, PLAYWRIGHT,       │
│    │                    CAMOUFOX, CLOUDERA, SELENIUMBASE, CLOAKBROWSER]   │
│    │                                                                       │
│    │   RENDER_CONFIGS = {                                                 │
│    │       NONE: {change_ua: [False], use_cookies: [False], ...},       │
│    │       PLAYWRIGHT: {change_ua: [False, True], use_cookies: [...], ...}│
│    │       ...                                                            │
│    │   }                                                                  │
│    │                                                                       │
│    │   # 2. 枚举所有有效组合                                              │
│    │   for render in RENDER_ORDER:                                        │
│    │       for proxy in PROXY_ORDER:                                      │
│    │           for config in RENDER_CONFIGS[render]:                      │
│    │               candidates.append(CrawlStrategy(...))                   │
│    │                                                                       │
│    │   # 3. 过滤无效组合                                                 │
│    │   #    - NONE 不能配合 human_scroll                                  │
│    │   #    - CLOUDERA 搜索页只允许 amazon                               │
│    │                                                                       │
│    └─ return candidates  # ~20-50 个候选策略                               │
│                                                                             │
│  @classmethod                                                             │
│  def get_optimal_strategies(cls, site, pattern, engine, top_n=10):        │
│    │                                                                       │
│    │   # 1. 生成候选策略                                                  │
│    │   candidates = cls.generate_candidates(site, pattern)                │
│    │                                                                       │
│    │   # 2. 转换为 PolicyCandidate                                        │
│    │   policy_candidates = [                                              │
│    │       PolicyCandidate.from_strategy(task, c, source="auto")          │
│    │       for c in candidates                                           │
│    │   ]                                                                  │
│    │                                                                       │
│    │   # 3. PolicyEngine 排序                                             │
│    │   ranked = engine.rank_candidates(task, policy_candidates)            │
│    │   │       └─ 基于历史 trace 打分:                                    │
│    │   │           + success_score  (成功率)                              │
│    │   │           + yield_score   (平均产品数)                           │
│    │   │           + order_bonus   (排在前面的奖励)                       │
│    │   │           + contextual_bonus (场景 bonus)                        │
│    │   │           - latency_penalty                                     │
│    │   │           - block_penalty   (阻塞率惩罚)                         │
│    │   │           - cost_penalty    (渲染成本惩罚)                       │
│    │   │                                                                       │
│    │   # 4. 取 top-N                                                     │
│    └─ return [c.to_strategy() for c in ranked[:top_n]]                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.3 CrawlTask.create() 改造

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  src/ai_crawler/core/strategy.py                                         │
│  class CrawlTask:                                                         │
│                                                                             │
│  @classmethod                                                             │
│  def create(cls, url, site, use_auto_strategies=True):                   │
│    │                                                                       │
│    ├─ pattern = PatternMatcher.detect(site, url)                           │
│    │                                                                       │
│    └─ if use_auto_strategies:  # 默认开启                                  │
│        │                                                                   │
│        ├─ stats_store = PolicyStatsStore()                                 │
│        ├─ engine = PolicyEngine(stats_store)                               │
│        │                                                                   │
│        └─ strategies = StrategyGenerator.get_optimal_strategies(          │
│                site, pattern.value, engine, top_n=10                       │
│            )                                                               │
│        │                                                                   │
│        └─ # 自动生成 10 个策略，基于历史成功率排序                         │
│                                                                             │
│        else:  # 兼容旧路径                                                  │
│        │                                                                   │
│        └─ strategies = URL_PATTERNS[site][pattern]                        │
│            └─ 硬编码策略列表                                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.4 策略生成示例

| 站点 | 模式 | 自动生成的 top-5 策略 |
|------|------|------------------------|
| amazon | SEARCH | 1. NONE+THORDATA 2. NONE+THORDATA_US 3. CLOUDSCRAPER 4. PLAYWRIGHT 5. PLAYWRIGHT+UA |
| unknownsite | UNKNOWN | 1. NONE+THORDATA 2. NONE+THORDATA_US 3. CLOUDSCRAPER 4. LIGHTPAND 5. PLAYWRIGHT |

### 10.5 与 PolicyEngine 协同

```
任务创建时:
    │
    ▼
StrategyGenerator.generate_candidates()
    │
    ▼
PolicyEngine.rank_candidates() ──── 从 trace/ 读取历史数据
    │
    ▼
策略按 total_score 降序排列
    │
    ▼
取 top-10 作为 task.strategies
    │
    ▼
执行时按顺序尝试，失败自动切换下一个
```

### 10.6 PolicyEngine 详细评分机制

#### 10.6.1 历史数据聚合 (PolicyStatsStore)

从 `traces/` 目录读取最近的 20 个 session 文件，聚合每个策略组合的历史表现：

```python
# 聚合维度: (site, page_pattern, render, proxy)
key = (trace.site, trace.page_pattern, trace.strategy_render, trace.strategy_proxy)

# 聚合指标
stats.runs += 1
stats.successes += 1 if trace.success else 0
stats.avg_latency_ms += trace.latency_ms
stats.http_timeout_count += 1 if trace.block_type == "http_timeout" else 0
stats.captcha_count += 1 if trace.block_type == "captcha" else 0
stats.cloudflare_count += 1 if trace.block_type == "cloudflare" else 0
stats.bot_count += 1 if trace.block_type == "bot_detected" else 0
stats.axtree_hits += 1 if trace.extraction_strategy == "axtree" else 0

# 条件统计: 针对特定 block_type 的成功率
if trace.block_type and trace.block_type != "none":
    stats.conditional[block_type].runs += 1
    stats.conditional[block_type].successes += 1 if trace.success else 0
```

**最终得到类似这样的统计：**

| 字段 | 说明 | 例子 |
|------|------|------|
| `runs` | 运行次数 | 15 |
| `successes` | 成功次数 | 3 |
| `success_rate` | 成功率 | 0.2 (20%) |
| `avg_latency_ms` | 平均延迟(毫秒) | 1500 |
| `http_timeout_count` | HTTP 超时次数 | 5 |
| `captcha_count` | CAPTCHA 出现次数 | 4 |
| `cloudflare_count` | Cloudflare 出现次数 | 2 |
| `bot_count` | Bot 检测次数 | 1 |
| `conditional` | 条件统计字典 | `{http_timeout: {runs:3, successes:2}}` |

#### 10.6.1.1 条件统计 (ConditionalStats)

针对特定错误类型的成功率统计：

```python
@dataclass
class ConditionalStats:
    block_type: str       # 错误类型: http_timeout, captcha, cloudflare, etc.
    runs: int = 0        # 遇到此错误后尝试次数
    successes: int = 0  # 成功次数
    avg_latency_ms: float = 0.0
    avg_products: float = 0.0

    @property
    def success_rate(self) -> float:
        return self.successes / self.runs if self.runs else 0.0
```

**条件统计示例：**

| 策略 | 整体成功率 | HTTP_403 时成功率 | CAPTCHA 时成功率 |
|------|-----------|------------------|-----------------|
| NONE + THORDATA | 20% | 0% | 5% |
| PLAYWRIGHT + THORDATA | 60% | 40% | 30% |
| CAMOUFOX + THORDATA | 75% | 60% | 50% |

这使得在遇到特定错误时，能选择历史上对该错误最有效的策略。

#### 10.6.2 评分公式 (total_score)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  total_score =                                                         │
│      + success_score       # 成功率得分 (0-100)                           │
│      + yield_score         # 产出得分 (产品数 × 3)                        │
│      + order_bonus         # 位置奖励 (20 - index × 2)                  │
│      + contextual_bonus     # 场景奖励 (根据页面类型定制)                 │
│      - latency_penalty     # 延迟惩罚 (秒 × 0.8)                        │
│      - block_penalty       # 阻塞惩罚                                     │
│      - anti_bot_penalty    # 反爬惩罚                                     │
│      - cost_penalty       # 渲染成本惩罚                                 │
│      - instability_penalty # 不稳定性惩罚                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 10.6.3 各项评分详解

**1. 成功率得分 (success_score)**

```python
success_score = success_rate * 100
```

| 成功率 | 得分 |
|--------|------|
| 100% | 100 |
| 50% | 50 |
| 20% | 20 |
| 0% | 0 |

**2. 产出得分 (yield_score)**

```python
yield_score = avg_products * 3
```

| 平均产品数 | 得分 |
|------------|------|
| 10 | 30 |
| 5 | 15 |
| 1 | 3 |
| 0 | 0 |

**3. 位置奖励 (order_bonus)**

```python
order_bonus = max(0, 20 - index * 2)
```

| 排名 | 奖励分 |
|------|--------|
| 0 | 20 |
| 1 | 18 |
| 2 | 16 |
| 3 | 14 |
| 5 | 10 |
| 10+ | 0 |

**4. 场景奖励 (contextual_bonus)**

```python
# SEARCH 页面专用奖励
if page_pattern == "SEARCH":
    if render == CAMOUFOX: bonus += 12
        if successes > 0: bonus += 8
    if render == CLOAKBROWSER: bonus += 14
        if successes > 0: bonus += 10
        if site in {amazon, target}: bonus += 8
    if render == SELENIUMBASE: bonus += 6
        if successes > 0: bonus += 4
    if render == CLOUDERA: bonus -= 10  # UC 不适合 SEARCH
```

| 组合 | 奖励分 |
|------|--------|
| SEARCH + CLOAKBROWSER + amazon | +32 (14+10+8) |
| SEARCH + CAMOUFOX + 有成功 | +20 (12+8) |
| SEARCH + CLOUDERA | -10 |

**5. 延迟惩罚 (latency_penalty)**

```python
latency_penalty = (avg_latency_ms / 1000) * 0.8
```

| 平均延迟 | 惩罚分 |
|---------|--------|
| 500ms | 0.4 |
| 1000ms | 0.8 |
| 3000ms | 2.4 |
| 5000ms | 4.0 |

**6. 阻塞惩罚 (block_penalty)**

```python
block_penalty = (
    http_timeout_rate * 20 +
    captcha_rate * 25 +
    cloudflare_rate * 15 +
    bot_rate * 15
)
```

| 阻塞类型 | 权重 | 30% 出现率时的惩罚 |
|----------|------|---------------------|
| HTTP Timeout | 20 | 6.0 |
| CAPTCHA | 25 | 6.25 |
| Cloudflare | 15 | 4.5 |
| Bot Detected | 15 | 4.5 |

**7. 反爬惩罚 (anti_bot_penalty)**

```python
browser_error_hits = anti_bot_vendors.get("browser_error", 0)
proxy_transport_hits = anti_bot_mechanisms.get("proxy_transport_error", 0)
browser_transport_hits = anti_bot_mechanisms.get("browser_transport_error", 0)
js_challenge_hits = anti_bot_mechanisms.get("js_challenge", 0)
captcha_hits = anti_bot_mechanisms.get("captcha_gate", 0)
bot_score_hits = anti_bot_mechanisms.get("bot_score_gate", 0)

penalty = (
    (browser_error_hits / runs) * 25 +
    (proxy_transport_hits / runs) * 20 +
    (browser_transport_hits / runs) * 15 +
    (js_challenge_hits / runs) * 10 +
    (captcha_hits / runs) * 12 +
    (bot_score_hits / runs) * 10
)
```

**8. 成本惩罚 (cost_penalty)**

```python
RENDER_COST = {
    NONE: 1,
    CLOUDSCRAPER: 2,
    LIGHTPAND: 3,
    PLAYWRIGHT: 4,
    CAMOUFOX: 5,
    CLOUDERA: 6,
    SELENIUMBASE: 7,
    CLOAKBROWSER: 8,
}
cost_penalty = RENDER_COST[render] * 2
```

| 渲染类型 | 成本惩罚 |
|----------|----------|
| NONE | 2 |
| PLAYWRIGHT | 8 |
| CLOAKBROWSER | 16 |

**9. 不稳定性惩罚 (instability_penalty)**

```python
instability_penalty = 10 if runs >= 3 and successes == 0 else 0
```

如果某个策略运行了 3 次以上但一次都没成功过，加 10 分惩罚。

#### 10.6.4 评分计算示例

**场景：amazon SEARCH，使用 NONE + THORDATA_DEDICATED 策略**

```python
# 假设历史统计
stats = {
    runs: 15,
    successes: 3,
    success_rate: 0.2,
    avg_latency_ms: 1500,
    http_timeout_rate: 0.33,  # 5/15
    captcha_rate: 0.27,       # 4/15
    cloudflare_rate: 0.13,     # 2/15
    bot_rate: 0.07,           # 1/15
    avg_products: 5,
}

# 1. success_score = 0.2 * 100 = 20
# 2. yield_score = 5 * 3 = 15
# 3. order_bonus = 20 (排名第 0)
# 4. contextual_bonus = 0 (NONE 无场景奖励)
# 5. latency_penalty = 1.5 * 0.8 = 1.2
# 6. block_penalty = 0.33*20 + 0.27*25 + 0.13*15 + 0.07*15 = 6.6 + 6.75 + 1.95 + 1.05 = 16.35
# 7. anti_bot_penalty = 假设 8.5
# 8. cost_penalty = 1 * 2 = 2
# 9. instability_penalty = 0 (有成功)

total = 20 + 15 + 20 + 0 - 1.2 - 16.35 - 8.5 - 2 - 0 = 26.95
```

#### 10.6.5 冷启动处理

**冷启动 vs 热启动：**

```
冷启动（无历史）→ SiteMemory 为空 → start_tier=1 从头探索
热启动（有历史）→ SiteMemory 有成功策略 → 成功策略直接置顶
```

**冷启动（无历史 trace 数据）：**

```python
# create_from_tier() 中
start_tier = 1  # 不使用 site.yaml tier 建议，完全交给 PolicyEngine 决定
strategies = CrawlStrategy.get_tier_strategies(start_tier, end_tier=9)

# 评分时
success_score = 0 * 100 = 0
block_penalty = 0
anti_bot_penalty = 0
instability_penalty = 0  # runs < 3，不触发

# 只有这些生效:
order_bonus = 20 - index * 2  # 按枚举顺序奖励
cost_penalty = RENDER_COST[render] * 2  # 越便宜越好
contextual_bonus = contextual_bonus()  # 场景奖励

# 冷启动时：成本低的 + 场景合适的 排在前面
# 不是随机，而是按成本和场景预设优先级
```

**热启动（有历史成功策略）：**

```python
def prepare(self, task: CrawlTask, memory: SiteMemory | None):
    # memory 有成功策略时，直接置顶，跳过 PolicyEngine 评分
    if memory and memory.successful_strategies:
        best = memory.successful_strategies[0]
        task.add_strategy_front(best)
        return memory  # 直接返回，不经过评分排序

    # 无历史时，才走 PolicyEngine 评分排序
    ranked = self._apply_policy_order(task)
    ...
```

**为什么热启动不用评分？**

热启动时 memory 已经记录了"对这个 site+page_pattern 有效的策略"，这是明确的成功信号。PolicyEngine 的评分需要 `block_type` 上下文才能发挥条件统计的优势，没有 block_type 时评分反而会因成本因素把 memory 中的成功策略排到后面。

#### 10.6.6 条件统计 (ConditionalStats)

**条件统计是什么？**

条件统计是针对**特定错误特征组合**的策略表现统计。例如：当遇到 `HTTP_403` + `datadome` + `js_challenge=True` + `captcha_type=recaptcha` 时，`PLAYWRIGHT` 策略的历史成功率可能是 70%，而 `NONE` 策略的成功率可能是 0%。

**多维度条件 key：**

```
block_type:waf_type:js_challenge:captcha_type
    ↓
HTTP_403:datadome:js:recaptcha    # Datadome + JS挑战 + reCAPTCHA
HTTP_403:cloudflare:js:nocap      # Cloudflare JS 挑战，无 CAPTCHA
HTTP_429::nojs:nocap              # 简单限速
```

**数据结构：**

```python
@dataclass
class ConditionalStats:
    block_type: str           # 错误类型，如 "HTTP_403"
    waf_type: str = ""        # WAF 类型，如 "datadome", "cloudflare"
    js_challenge: bool = False # 是否包含 JavaScript 挑战
    captcha_type: str = ""    # CAPTCHA 类型: recaptcha, hcaptcha, turnstile
    runs: int = 0            # 使用该策略处理此错误的次数
    successes: int = 0       # 成功的次数
    avg_latency_ms: float = 0.0    # 平均延迟
    avg_products: float = 0.0     # 平均产出
```

**存储位置：**

条件统计存储在 `PolicyStats.conditional` 字典中，key 格式为 `block_type:waf_type:js_challenge:captcha_type`：

```python
@dataclass
class PolicyStats:
    # ... 原有字段 ...
    conditional: dict[str, ConditionalStats] = field(default_factory=dict)
    # key 格式: "HTTP_403:datadome:js:recaptcha"
```

**分层回退查询：**

系统会尝试从最具体的条件开始匹配，逐层回退到更宽泛的条件：

```python
# 查询优先级（从具体到宽泛）
keys_to_try = [
    "HTTP_403:datadome:js:recaptcha",  # 最具体
    "HTTP_403:datadome:js:nocap",       # 同 WAF + JS，无 CAPTCHA
    "HTTP_403:datadome:nojs:nocap",     # 同 WAF，无 JS
    "HTTP_403::nojs:nocap",             # 同错误类型
    "HTTP_403",                          # 最宽泛
]
```

**查询条件统计：**

```python
# 获取针对特定错误类型和 WAF 类型的统计
conditional = stats.conditional.get("HTTP_403:datadome:js:recaptcha")
if conditional:
    print(f"HTTP_403 + datadome + JS + reCAPTCHA 条件下成功率: {conditional.successes / conditional.runs:.1%}")
```

**条件评分计算：**

当调用 `rank_candidates(block_type="HTTP_403", waf_type="datadome", js_challenge=True, captcha_type="recaptcha")` 时，系统会：

1. 首先尝试精确匹配 `HTTP_403:datadome:js:recaptcha`
2. 如果没有数据，回退到 `HTTP_403:datadome:js:nocap`
3. 继续回退直到找到历史数据

```python
# 条件评分 (conditional_score)
# 如果有针对当前错误类型和 WAF 类型的统计，增加额外分数
conditional = stats.conditional.get(f"{block_type}:{waf_type}")
if conditional and conditional.runs > 0:
    conditional_success_rate = conditional.successes / conditional.runs
    conditional_score = conditional_success_rate * 30  # 条件成功率权重 30
    total_score += conditional_score
```

**工作流程示例：**

```
遇到 HTTP_403 + datadome 错误，需要选择下一个策略
    ↓
查询所有策略的 (amazon, SEARCH, HTTP_403:datadome) 条件统计
    ↓
┌─────────────┬────────┬──────────┬─────────────┐
│ 策略        │ runs   │ successes │ 条件成功率  │
├─────────────┼────────┼──────────┼─────────────┤
│ PLAYWRIGHT  │ 10     │ 6        │ 60%         │
│ CLOUDSCRAPER│ 8      │ 3        │ 37.5%       │
│ NONE        │ 15     │ 2        │ 13.3%       │
└─────────────┴────────┴──────────┴─────────────┘
    ↓
条件评分 = 成功率 * 30
    PLAYWRIGHT: 0.6 * 30 = 18
    CLOUDSCRAPER: 0.375 * 30 = 11.25
    NONE: 0.133 * 30 = 4
    ↓
结合基础评分 + 条件评分，选择排名最高的策略
```

**为什么需要条件统计？**

1. **错误针对性**：某些策略对特定错误更有效。例如：
   - `PLAYWRIGHT` 对 `HTTP_403` 和 `JS_CHALLENGE` 效果更好
   - `CLOUDSCRAPER` 对 `CLOUDFLARE` 效果更好
   - `NONE` 对简单网站效果最好（成本最低）

2. **WAF 针对性**：不同 WAF 类型需要不同的应对策略：
   - `datadome` → 需要高级浏览器指纹（Camoufox/Playwright）
   - `cloudflare` → Cloudscraper 可能足够
   - 无 WAF → NONE 策略即可

3. **历史学习**：系统通过记录历史表现，自动学习"遇到 X 错误 + Y WAF 用 Z 策略"

4. **动态适应**：随着爬取进行，条件统计会不断更新，策略选择越来越准确

#### 10.6.7 LLM 融合评分 (LLM Fusion Scoring)

LLM 专家知识可以与历史数据评分融合，提升策略选择的准确性。

**Tier 到 Render 的 Bonus 映射：**

```python
TIER_RENDER_MAP = {
    1: "none",
    2: "cloudscraper",
    3: "lightpand",
    4: "playwright",
    5: "camoufox",
    6: "cloud era",
    7: "cloakbrowser",
}

def _tier_to_render_bonuses(llm_tier: int, candidates: list) -> dict[str, float]:
    """将 LLM tier 建议转换为 render 级别的 bonus 分数"""
    bonuse = {}
    target_render = TIER_RENDER_MAP.get(llm_tier)

    for candidate in candidates:
        render = candidate.strategy.render
        if render == target_render:
            bonuse[render] = 20.0  # LLM 推荐的首选
        else:
            # 按距离递减排 bonus
            tier_distance = abs(llm_tier - _get_tier_for_render(render))
            bonuse[render] = max(0, 20 - tier_distance * 4)
    return bonuse
```

**自适应 LLM 权重：**

```python
# LLM 权重随样本数量自适应调整
# 样本越多，历史数据越可靠，LLM 权重越低
max_sample_count = max(s.runs for s in stats_values)
llm_weight = 1.0 / (1.0 + max_sample_count)
```

| 样本数量 | LLM 权重 | 说明 |
|----------|----------|------|
| 0 | 1.0 | 纯冷启动，完全依赖 LLM |
| 5 | 0.17 | 少量数据，LLM 仍有较高权重 |
| 20 | 0.05 | 足够数据，历史统计为主 |
| 100+ | ~0.01 | 大量数据，LLM 影响很小 |

**评分公式（带 LLM Fusion）：**

```
total_score =
    + success_score              # 成功率得分 (0-100)
    + yield_score               # 产出得分 (产品数 × 3)
    + order_bonus               # 位置奖励 (20 - index × 2)
    + contextual_bonus          # 场景奖励
    + conditional_score          # 条件统计得分
    + llm_bonus * llm_weight    # LLM 专家奖励 (自适应权重)
    - latency_penalty            # 延迟惩罚 (秒 × 0.8)
    - block_penalty              # 阻塞惩罚
    - anti_bot_penalty           # 反爬惩罚
    - cost_penalty               # 渲染成本惩罚
    - instability_penalty         # 不稳定性惩罚
```

**融合示例：**

```python
# LLM 建议 tier=7 (cloakbrowser)，但历史数据显示：
# - cloakbrowser 成功率 40%，成本 16
# - camoufox 成功率 45%，成本 10

llm_tier = 7
candidates = [none, cloudscraper, playwright, camoufox, cloakerbrowser]

# Tier → Render bonus
bonuses = _tier_to_render_bonuses(llm_tier, candidates)
# => {"none": 0, "cloudscraper": 8, "playwright": 12, "camoufox": 12, "cloakbrowser": 20}

# 自适应权重
llm_weight = 1.0 / (1.0 + 50) = 0.02  # 假设有 50 个样本

# 最终 LLM 贡献
camoufox_llm_contribution = 12 * 0.02 = 0.24
cloakbrowser_llm_contribution = 20 * 0.02 = 0.40

# 由于历史数据权重很高，LLM 的影响被限制在很小范围
# 这防止了 LLM 完全主导策略选择，同时仍能提供有价值的参考
```

**为什么需要自适应权重？**

1. **冷启动阶段**：没有历史数据时，LLM 可以快速提供合理的初始策略
2. **数据积累后**：历史数据越来越可靠，LLM 的参考作用逐渐降低
3. **防止过度依赖**：避免 LLM 的错误建议导致糟糕的策略选择
4. **平衡点**：在探索新策略和利用历史知识之间取得平衡

---

## 10.7 策略模式：最优策略 vs 最小足够策略

### 10.7.1 两种策略选择模式

系统支持两种策略选择模式，通过 `RuntimeOptions.strategy_mode` 配置：

| 模式 | 值 | 描述 | 选择逻辑 |
|------|-----|------|----------|
| **最优策略** | `"optimal"` | 综合评分最高的策略 | 按总分排序（成功率、产出、成本等综合评分） |
| **最小足够策略** | `"minimal_sufficient"` | 成本最低的成功策略 | 在成功过的策略中选择成本最低的 |

### 10.7.2 最优策略 (optimal)

**原理**：综合考虑成功率、产出量、延迟、成本等多个维度，选择综合评分最高的策略。

**适用场景**：
- 需要最大产出量
- 愿意为更高成功率支付更高成本
- 追求整体最优而非成本控制

**代码路径**：`PolicyEngine.rank_candidates()` → `score_candidate()`

### 10.7.3 最小足够策略 (minimal_sufficient)

**原理**：在所有**曾经成功过**的策略中，选择**成本最低**的那个。

**核心思想**：如果一个简单的策略（低成本）已经能成功，就不需要使用更复杂的策略（高成本）。

**代码**：

```python
def pick_minimal_sufficient(
    self,
    task: CrawlTask,
    candidates: list[PolicyCandidate],
    block_type: str | None = None,
) -> PolicyCandidate | None:
    """
    选择最小足够策略：在成功过的策略中选择成本最低的。

    策略：不需要追求"最优"，只需要"刚好能工作"。
    如果 NONE 策略已经能成功，就不需要用 PLAYWRIGHT。
    """
    sufficient_candidates = []

    for candidate in candidates:
        stats = self._get_stats(task, candidate.strategy)

        # 检查这个策略是否曾经成功过
        if stats and stats.successes > 0:
            sufficient_candidates.append(candidate)

    if not sufficient_candidates:
        # 没有成功过的策略，退回最优策略
        return self.rank_candidates(task, candidates, block_type)[0] if candidates else None

    # 按成本排序，选择最低的
    sufficient_candidates.sort(key=lambda c: RENDER_COST[c.strategy.render])
    return sufficient_candidates[0]
```

**成本排序表**：

| 渲染类型 | 成本 | 说明 |
|----------|------|------|
| NONE | 1 | 无渲染，最便宜 |
| CLOUDSCRAPER | 2 | 基础代理 |
| LIGHTPAND | 3 | 轻量级渲染 |
| PLAYWRIGHT | 4 | 完整浏览器 |
| CAMOUFOX | 5 | 指纹浏览器 |
| CLOUDERA | 6 | 企业级 |
| SELENIUMBASE | 7 | Selenium 基础 |
| CLOAKBROWSER | 8 | 最大成本 |

**工作流程示例**：

```
场景：amazon SEARCH，遇到 HTTP_403

候选策略：[NONE, CLOUDSCRAPER, PLAYWRIGHT]

历史成功统计：
┌─────────────┬──────────┬────────────┐
│ 策略        │ successes │ 成本       │
├─────────────┼──────────┼────────────┤
│ NONE        │ 3        │ 1          │
│ CLOUDSCRAPER│ 8        │ 2          │
│ PLAYWRIGHT  │ 10       │ 4          │
└─────────────┴──────────┴────────────┘

最小足够策略选择：
1. 过滤出曾经成功过的策略：所有都是
2. 按成本排序：[NONE, CLOUDSCRAPER, PLAYWRIGHT]
3. 选择最低成本的：NONE

结果：选择 NONE 策略
理由：NONE 已经能成功（3次），不需要更贵的 PLAYWRIGHT（成本 4）
```

**适用场景**：
- 成本敏感业务
- 简单网站（`NONE` 策略就能成功）
- 追求最小成本而非最大产出

**与最优策略的对比**：

| 对比维度 | 最优策略 | 最小足够策略 |
|----------|----------|--------------|
| 目标 | 综合评分最高 | 成本最低的成功策略 |
| 考虑因素 | 成功率、产出、延迟、成本 | 只考虑成本（前提是能成功） |
| 可能选择 | 高成本高产出策略 | 低成本成功策略 |
| 适用场景 | 追求最大产出 | 成本控制优先 |

### 10.7.4 配置方式

**通过 RuntimeOptions 配置：**

```python
from ai_crawler import RuntimeOptions, run_crawl

# 最优策略（默认）
options = RuntimeOptions(strategy_mode="optimal")
result = run_crawl(tasks, options=options)

# 最小足够策略
options = RuntimeOptions(strategy_mode="minimal_sufficient")
result = run_crawl(tasks, options=options)
```

**通过爬虫任务配置：**

```python
from ai_crawler import RuntimeTask, RuntimeOptions, run_crawl

task = RuntimeTask(
    url="https://example.com",
    task_type="SEARCH",
    strategy_mode="minimal_sufficient",  # 这个任务使用最小足够策略
)
result = run_crawl([task])
```

---

## 10.8 策略引擎与条件统计的集成

### 10.8.1 完整评分流程

当 `strategy_mode="optimal"` 时，评分流程如下：

```
1. 获取候选策略列表
   ↓
2. 对每个策略获取 PolicyStats
   ↓
3. 计算基础评分 (score_candidate)
   ├─ success_score: 成功率 * 100
   ├─ yield_score: avg_products * 3
   ├─ order_bonus: 枚举顺序奖励
   ├─ contextual_bonus: 场景奖励
   ├─ latency_penalty: 延迟惩罚
   ├─ block_penalty: 阻塞类型惩罚
   ├─ anti_bot_penalty: 反爬惩罚
   ├─ cost_penalty: 成本惩罚
   └─ instability_penalty: 不稳定性惩罚
   ↓
4. 如果有 block_type，应用条件评分
   ├─ 获取 conditional_stats[block_type]
   └─ conditional_score: 条件成功率 * 30
   ↓
5. 排序并返回最高分策略
```

### 10.8.2 条件统计与最小足够策略的集成

当 `strategy_mode="minimal_sufficient"` 时，有两种选择算法：

**算法 1: 线性扫描 (pick_minimal_sufficient)**

```
1. 获取候选策略列表，按成本排序
   ↓
2. 遍历每个策略，检查历史成功率
   ↓
3. 返回第一个成功过的策略（成本最低）
```

**算法 2: 二叉搜索 (binary_search_minimal)**

```
策略列表：[NONE(1), CLOUDSCRAPER(2), LIGHTPAND(3), PLAYWRIGHT(4), CAMOUFOX(5), CLOAKBROWSER(8)]

已知：CLOAKBROWSER(8) 成功

二分查找找最低成功成本：
    ↓
第1轮：mid = (0+5)//2 = 2 → LIGHTPAND(3)
    检查 LIGHTPAND 成功？否 → low = 3
    ↓
第2轮：mid = (3+5)//2 = 4 → CAMOUFOX(5)
    检查 CAMOUFOX 成功？是 → result=CAMOUFOX, high = 3
    ↓
第3轮：mid = (3+3)//2 = 3 → PLAYWRIGHT(4)
    检查 PLAYWRIGHT 成功？是 → result=PLAYWRIGHT, high = 2
    ↓
low(3) > high(2)，停止
    ↓
结果：PLAYWRIGHT(4)
```

**两种算法的选择：**

| 场景 | 推荐算法 | 原因 |
|------|---------|------|
| 有历史数据 | 二叉搜索 | O(log n) 更高效 |
| 冷启动 | 线性扫描 | 无历史，只能遍历 |
| 数据稀疏 | 线性扫描 | 需要收集更多数据 |

**示例：多维度条件 + 最小足够策略**

```
场景：amazon SEARCH，遇到 HTTP_403 + datadome + JS挑战 + reCAPTCHA

候选策略：[NONE, CLOUDSCRAPER, PLAYWRIGHT]

多维度条件统计 (HTTP_403:datadome:js:recaptcha)：
┌─────────────┬──────────┬────────────┬──────────┐
│ 策略        │ runs     │ successes  │ 成本     │
├─────────────┼──────────┼────────────┼──────────┤
│ NONE        │ 10       │ 0          │ 1        │
│ CLOUDSCRAPER│ 5        │ 0          │ 2        │
│ PLAYWRIGHT  │ 8        │ 6          │ 4        │
└─────────────┴──────────┴────────────┴──────────┘

最小足够策略选择（多维度感知）：
1. 分层回退查询：
   - 查 HTTP_403:datadome:js:recaptcha → 无数据
   - 查 HTTP_403:datadome:js:nocap → 无数据
   - 查 HTTP_403:datadome:nojs:nocap → 无数据
   - 查 HTTP_403::nojs:nocap → 有数据！
2. 使用 HTTP_403 条件进行过滤：
   - NONE: 0/10 成功 → **不入选**
   - CLOUDSCRAPER: 0/5 成功 → **不入选**
   - PLAYWRIGHT: 6/8 成功 → **入选**
3. 按成本排序：[PLAYWRIGHT]
4. 选择最低成本：PLAYWRIGHT

结果：PLAYWRIGHT
理由：在 datadome + JS + reCAPTCHA 组合下，只有 PLAYWRIGHT 成功过。
```

### 10.8.3 策略模式选择指南

| 场景 | 推荐模式 | 原因 |
|------|---------|------|
| 简单网站，低反爬 | `minimal_sufficient` | `NONE` 策略就能成功，最省钱 |
| 复杂网站，高反爬 | `optimal` | 需要综合评分来选择最有效的策略 |
| 成本敏感业务 | `minimal_sufficient` | 优先控制成本 |
| 追求最大产出 | `optimal` | 愿意为高产出支付更高成本 |
| 未知网站探测 | `optimal` | 需要综合评分来判断 |
| 稳定运行的生产环境 | `minimal_sufficient` | 一旦找到有效策略，保持低成本 |

---

## 10.9 自动策略生成

### 10.9.1 策略生成器 (StrategyGenerator)

自动策略生成器根据站点和任务类型，生成候选策略列表。

**核心方法：**

```python
class StrategyGenerator:
    def generate_candidates(
        self,
        site: str,
        task_type: str,
        use_auto_strategies: bool = True,
        explicit_strategies: list[CrawlStrategy] | None = None,
    ) -> list[PolicyCandidate]:
        """
        生成候选策略列表。
        
        如果 use_auto_strategies=True，自动生成所有可能的策略组合；
        否则使用 explicit_strategies。
        """

    def get_optimal_strategies(
        self,
        candidates: list[PolicyCandidate],
        task: CrawlTask,
        limit: int = 10,
    ) -> list[PolicyCandidate]:
        """
        基于 PolicyEngine 排序，返回最优的 N 个策略。
        """
```

**自动生成逻辑：**

```python
# 生成所有策略组合
candidates = []

for render in RENDER_TYPES:
    for proxy in PROXY_TYPES:
        for extra in EXTRA_OPTIONS:
            strategy = CrawlStrategy(
                render=render,
                proxy=proxy,
                extra=extra,
            )
            candidates.append(PolicyCandidate(strategy=strategy))

# 然后通过 PolicyEngine 排序
sorted_candidates = policy_engine.rank_candidates(task, candidates)
```

### 10.9.2 自动策略与手动策略的对比

| 维度 | 自动策略 | 手动策略 |
|------|----------|----------|
| 来源 | `StrategyGenerator.generate_candidates()` | 用户在 `RuntimeTask.strategies` 中指定 |
| 数量 | 可能生成数十个组合 | 通常 1-5 个 |
| 排序 | 基于历史数据自动排序 | 按用户指定顺序 |
| 灵活性 | 高（覆盖所有可能性） | 低（用户决定） |
| 成本 | 可能选择非最优的 | 用户可控 |

### 10.9.3 使用场景

**自动策略适用场景：**
- 未知网站，需要全面探测
- 复杂反爬网站，需要多种策略尝试
- 开发测试阶段，快速验证

**手动策略适用场景：**
- 已知网站，固定策略
- 成本敏感，明确知道用什么策略
- 生产环境，避免不必要的策略尝试

---

## 11. 核心模块职责表

| 模块 | 文件路径 | 职责 | 关键方法 |
|------|----------|------|----------|
| **入口** | `__init__.py` | 对外 API 统一入口 | `run_crawl()` |
| **编排** | `orchestration/orchestrator.py` | 任务构建、结果聚合 | `crawl_tasks()`, `_build_runner()` |
| **运行器** | `core/runner.py` | 线程池管理、任务分发 | `run()`, `_process_one()` |
| **处理器** | `core/engine/processing.py` | 策略规划、流程编排 | `process()` |
| **执行** | `core/engine/execution.py` | 页面获取、阻塞检测、IP轮换 | `execute()`, `_fetch()` |
| **提取服务** | `core/engine/extraction_runtime.py` | 多级提取链、LLM fallback | `extract()` |
| **提取链** | `core/extraction/*.py` | 各层级提取实现 | `extract()` |
| **策略生成** | `core/engine/strategy_generator.py` | 自动生成策略池 + 排序 | `generate_candidates()`, `get_optimal_strategies()` |
| **策略引擎** | `core/engine/policy_engine.py` | 基于历史数据打分排序 | `rank_candidates()`, `score_candidate()` |
| **规划** | `core/engine/planner.py` | 策略排序、LLM tier 选择 | `prepare()`, `resolve()` |
| **检测** | `core/engine/handler.py` | 阻塞类型判断 | `detect()`, `is_blocked()` |
| **失败处理** | `core/engine/outcomes.py` | 失败记录、策略推荐 | `handle_blocked()` |
| **队列** | `core/engine/queue.py` | 任务队列、成功/失败追踪 | `enqueue()`, `on_success()`, `on_failure()` |
| **浏览器** | `browser/fetching.py` | 多浏览器路径获取 | `fetch_with_strategy()` |
| **指纹** | `core/engine/fingerprinter.py` | 反爬供应商/机制推断 | `infer()` |
| **遥测** | `core/engine/telemetry.py` | WAF 检测、响应头提取 | `detect_waf()`, `detect_block_reason()` |

---

## 12. 关键类型定义

| 类型 | 定义位置 | 说明 |
|------|----------|------|
| `RuntimeBatchResult` | `orchestration/models.py` | crawl_tasks() 返回结果聚合 |
| `RuntimeTask` | `orchestration/models.py` | 用户级任务描述 |
| `CrawlTask` | `core/strategy.py` | 运行时任务 (含策略列表) |
| `CrawlStrategy` | `core/types.py` | 单个抓取策略配置 |
| `CrawlResult` | `core/engine/results.py` | 单任务执行结果 |
| `FetchAttempt` | `core/engine/execution.py` | 单次 fetch 尝试结果 |
| `ExtractionDecision` | `core/engine/extraction_runtime.py` | 提取服务决策 |
| `ExtractionResult` | `core/extraction/base.py` | 提取器返回结果 |
| `BlockType` | `core/engine/handler.py` | 阻塞类型枚举 (含 IP_BLOCKED, HUMAN_BEHAVIOR, INTERACTIVE_FAILED) |
| `BlockSignals` | `core/engine/telemetry.py` | 增强的阻塞信号提取 |

---

## 13. 增强的阻塞信号提取 (BlockSignals)

### 13.1 BlockSignals 数据结构

```python
@dataclass
class BlockSignals:
    waf_type: str = ""              # WAF 类型: datadome, cloudflare, imperva
    waf_subtype: str = ""          # WAF 子类型: js_challenge, captcha_challenge
    js_challenge: bool = False     # 是否包含 JavaScript 挑战
    captcha_type: str = ""          # CAPTCHA 类型: recaptcha, hcaptcha, turnstile
    script_signals: list = []       # 检测到的脚本信号列表
    is_honeypot: bool = False      # 是否为蜜罐页面
    latency_anomaly: str = ""       # 延迟异常类型
    html_size_anomaly: str = ""     # HTML 大小异常类型
    header_features: dict = {}       # 响应头特征
    ip_blocked: bool = False        # 是否为 IP 被封
    human_behavior_detected: bool = False  # 是否检测到人类行为问题
    interactive_failed: bool = False  # 交互搜索是否失败
```

### 13.2 增强的失败原因检测

**1. IP_BLOCKED 检测**

```python
def detect_ip_blocked(status_code, latency_ms, latency_anomaly) -> bool:
    # HTTP 403/429 + 快速响应 (<500ms) → IP 被封
    if status_code in (403, 429) and latency_ms < 500:
        return True
    return False
```

**触发场景**：需要升级到使用代理

**2. HUMAN_BEHAVIOR 检测**

```python
def detect_human_behavior_failure(html, waf_subtype, waf_type, script_signals) -> bool:
    # Datadome / PerimeterX 等行为分析 WAF
    if waf_type == "datadome":
        return True
    if waf_subtype == "behavioral_analysis":
        return True
    # 包含人类验证关键词
    if "are you a robot" in html.lower():
        return True
    return False
```

**触发场景**：需要启用 human_scroll、cookies 等人类行为模拟

**3. INTERACTIVE_FAILED 检测**

```python
def detect_interactive_failed(html, block_type, waf_type, use_interactive_search) -> bool:
    # 如果使用了交互搜索但返回空结果
    if use_interactive_search and block_type == "none" and waf_type == "":
        if "no results found" in html.lower():
            return True
    return False
```

**触发场景**：交互搜索不适合当前页面，应切换到非交互模式

### 13.3 提取的信号维度

**1. WAF 类型和子类型**

```python
# WAF 类型
waf_type = "datadome" | "cloudflare" | "imperva" | "akamai" | ...

# Cloudflare 子类型
waf_subtype = "js_challenge" | "captcha_challenge" | "browser_check"

# Datadome 子类型
waf_subtype = "behavioral_analysis"
```

**2. JavaScript 挑战检测**

检测页面中是否包含 JS 挑战代码：

```python
JS_CHALLENGE_PATTERNS = [
    "eval(",
    "new Function",
    "setTimeout",
    "document.cookie",
    "__cf_chl",
    "chk_jschl",
    "challenge-platform",
    "hcaptcha",
    "g-recaptcha",
    "turnstile",
]
```

**3. 蜜罐检测**

检测页面是否包含隐藏元素（蜜罐）：

```python
HONEYPOT_PATTERNS = [
    "display:none",
    "visibility:hidden",
    "opacity:0",
    "pointer-events:none",
    "overflow:hidden",
    "position:absolute",
]
```

**4. 延迟异常检测**

```python
# 异常类型
latency_anomaly = "slow_page"          # 200 OK 但响应慢 (>10s)
latency_anomaly = "instant_reject"     # 立即拒绝 (<500ms)
latency_anomaly = "challenge_delay"    # 挑战延迟 (5-10s)
latency_anomaly = "suspiciously_fast"  # 可疑地快 (<100ms)
```

**5. HTML 大小异常检测**

```python
html_size_anomaly = "empty_page"          # 空页面 (<500 bytes)
html_size_anomaly = "oversized_page"     # 过大页面 (>500KB)
html_size_anomaly = "minimal_block_page" # 最小阻塞页面 (<1KB)
html_size_anomaly = "challenge_page_size"# 挑战页面大小 (1-5KB)
```

**6. 响应头特征**

```python
header_features = {
    "cf_ray": True,                    # Cloudflare Ray ID
    "cf_datacenter": "LAX",            # CF 数据中心
    "x_datadome": "...",               # Datadome 头
    "server_type": "nginx",            # 服务器类型
    "sets_cookie": True,               # 设置了 Cookie
    "has_correlation_id": True,        # 有请求追踪 ID
    "cf_cache_status": "HIT",          # CF 缓存状态
}
```

### 13.3 使用场景

```
遇到 403 错误
    ↓
extract_block_signals() 提取完整信号
    ↓
BlockSignals(
    waf_type="cloudflare",
    waf_subtype="js_challenge",
    js_challenge=True,
    script_signals=["cloudflare"],
    latency_anomaly="challenge_delay",
    html_size_anomaly="challenge_page_size",
    header_features={"cf_ray": True, "cf_datacenter": "SFO"}
)
    ↓
记录到 trace，供策略引擎学习：
- "遇到 Cloudflare JS 挑战时，用 PLAYWRIGHT 有效"
- "响应时间 8s 说明服务器端在执行挑战"
```

---

## 14. 环境变量配置点

| 变量 | 配置位置 | 说明 |
|------|----------|------|
| `OPENAI_API_KEY` | `config/__init__.py` | LLM API 密钥 |
| `MODEL_NAME` | `config/__init__.py` | LLM 模型名 |
| `2CAPTCHA_API_KEY` | `config/__init__.py` | CAPTCHA 解决服务 |
| `THORDATA_*` | `config/__init__.py` | 代理配置 |
| `KAMELEO_*` | `config/__init__.py` | Kameleo 浏览器配置 |
| `REQUEST_TIMEOUT` | `config/__init__.py` | 请求超时 |
| `PAGE_LOAD_TIMEOUT` | `config/__init__.py` | 页面加载超时 |
| `LOG_LEVEL` | `config/__init__.py` | 日志级别 |

---

## 14. 智能提取架构 (Smart Extraction)

### 14.1 设计原则

1. **高成功率**：优先使用 UniversalExtractor（API拦截 + JSON-LD + AXTree 组合）
2. **零配置**：新网站不需要人工配置提取模板
3. **自学习**：首次提取时自动生成模板并缓存
4. **模板失效自动恢复**：模板失败后自动重新生成
5. **多策略兜底**：JSON-LD → AXTree → API拦截，层层兜底

### 14.2 提取流程

```
extract()
    │
    ├─► 有模板 + 有效 → 用模板提取
    │                         ↓ 成功 → 返回
    │                         ↓ 失败 → 标记无效，继续
    │
    └─► 无模板 或 模板无效 → UniversalExtractor (API拦截 → JSON-LD → AXTree)
                                      ↓ 成功 → LLM 生成模板 → 保存 → 返回
                                      ↓ 失败 → 升级渲染重试
```

### 14.2.1 UniversalExtractor 内部流程

```
UniversalExtractor.extract(page, html, url, intercepted_products)
    │
    ├─► intercepted_products? → 直接返回（API 拦截数据优先）
    │
    ├─► JSON-LD（快，不需要渲染）
    │         ↓ 失败
    │
    ├─► AXTree（需要 Playwright 渲染）
    │         ↓ 失败
    │
    └─► 返回空结果
```

### 14.2.2 API 拦截（API Intercept）

API 拦截用于捕获页面加载时的 XHR/API 响应，适用于：
- SPA 动态加载的产品数据
- 使用动态 class 名的网站（如 Temu）
- accessibility tree 不完整的页面

**设置方式**：

```python
# ExtractionRuntimeService.setup_api_intercept(page)
page.on("response", handle_response)

# handle_response 逻辑
def handle_response(response):
    if any(k in response.url.lower() for k in ["product", "search", "item", "goods"]):
        if "json" in response.headers.get("content-type", ""):
            data = response.json()
            products = parse_products(data)
            intercepted_products.extend(products)
```

**支持的 API 响应格式**：

```python
# 格式 1: home_goods_list (Temu)
{
    "result": {
        "home_goods_list": [
            {"type": 0, "data": {"title": "...", "price_info": {...}, ...}},
            ...
        ]
    }
}

# 格式 2: 标准列表
{"products": [...]} / {"items": [...]} / {"results": [...]}

# 格式 3: data 数组
{"data": [...]}
```

### 14.3 核心组件

**ExtractionTemplate** - 缓存的提取模板：

```python
@dataclass
class ExtractionTemplate:
    site: str
    page_type: str  # "search", "detail", "review"...
    css_selector: str | None = None  # CSS 选择器
    js_selector: str | None = None   # JS 选择器
    is_valid: bool = True            # 模板是否有效
    success_count: int = 0          # 成功次数
    failure_count: int = 0          # 失败次数
```

**UniversalExtractor** - 高成功率解析器：

```python
class UniversalExtractor:
    """JSON-LD + AXTree + API拦截 组合，保证高成功率"""

    def extract(
        self,
        page,
        html,
        url,
        page_type,
        intercepted_products=None,
    ) -> ExtractionResult:
        # 0. 优先使用 API 拦截的产品数据
        if intercepted_products:
            return ExtractionResult(
                products=intercepted_products,
                strategy="api_intercept",
                method="network_intercept",
            )

        # 1. 先尝试 JSON-LD（快，不需要渲染）
        products = JSONLDExtraction().extract(page, html, url)
        if products:
            return ExtractionResult(products=products, strategy="json_ld", method="json_ld")

        # 2. JSON-LD 失败，用 AXTree（需要渲染）
        if page:
            products = AXTreeExtraction().extract(page, html, url)
            if products:
                return ExtractionResult(products=products, strategy="axtree", method="accessibility_tree")

        # 3. 都失败
        return ExtractionResult(products=[], strategy="none", method="none")

        # 3. 都失败
        return ExtractionResult(products=[], strategy="none", method="none")
```

### 14.4 模板管理

```python
# 模板存储
_extraction_templates: dict[tuple[str, str], ExtractionTemplate] = {}

# 获取模板
template = get_template(site, page_type)

# 保存模板
save_template(ExtractionTemplate(site=site, page_type=page_type, css_selector="li.product"))

# 标记模板无效
invalidate_template(site, page_type)  # 失败一次就无效
```

### 14.5 LLM 模板生成

当 UniversalExtractor 成功提取数据后，用 LLM 分析 HTML 结构生成模板：

```python
def llm_generate_template(site, page_type, html, products, page=None) -> ExtractionTemplate:
    """用 LLM 生成提取模板"""
    # 1. 获取 AXTree 语义样本
    semantic_sample = build_axtree_selector_sample(page, url, page_type)

    # 2. 调用 LLM 生成选择器
    selectors = llm_extractor.get_selectors(
        site=site,
        page_type=page_type,
        html_sample=html[:50000],
        semantic_sample=semantic_sample,
        force_regenerate=True,
    )

    # 3. 构建模板
    css_selector = selectors.get("product_selector")
    return ExtractionTemplate(
        site=site,
        page_type=page_type,
        css_selector=css_selector,
    )
```

### 14.6 各页面类型策略

| 页面类型 | 首次访问 | 后续访问 |
|----------|----------|----------|
| **search** | UniversalExtractor → LLM 生成模板 | 用模板提取 |
| **detail** | UniversalExtractor → LLM 生成模板 | 用模板提取 |
| **review** | UniversalExtractor → LLM 生成模板 | 用模板提取 |
| **home** | UniversalExtractor → LLM 生成模板 | 用模板提取 |

### 14.7 与旧架构对比

| 维度 | 旧架构 | 新架构 |
|------|--------|--------|
| 模板来源 | 人工配置（30 个站点） | 自动生成（所有站点） |
| 新站点支持 | 需要人工配置 | 自动学习 |
| 模板失效处理 | 人工更新 | 自动重新生成 |
| 维护成本 | 高 | 极低 |

### 14.8 文件位置

| 文件 | 说明 |
|------|------|
| `core/extraction/template_based.py` | ExtractionTemplate, UniversalExtractor, 模板管理 |
| `core/engine/extraction_runtime.py` | ExtractionRuntimeService，使用新提取逻辑 |