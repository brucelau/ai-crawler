# 验证指南

> 状态：已与当前 `gpt` 分支实现对齐。
>
> 适用范围：代码修改后的验证流程、分层测试策略、真实运行冒烟验证。
>
> 相关文档：
>
> - `docs/ARCHITECTURE.md`
> - `docs/TIER_SYSTEM.md`
> - `docs/BLOCK_DETECTOR.md`
> - `docs/LLM_SYSTEM.md`

---

## 1. 为什么需要分层验证

当前系统已经不是一个单一爬虫脚本，而是一个由多层组成的运行时系统，包括：

- 浏览器优先运行时
- 多级 Tier 升级策略
- 多种浏览器/HTTP 抓取路径
- 多级提取链（`json_ld -> js_eval -> api_intercept -> axtree -> bs_css`）
- BlockDetector / AXTree 语义确认
- Scrapy 辅助适配层

因此，不能再只靠“跑一次 pytest 全绿”来判断改动是否安全。

正确做法是：

## **分层验证 + 定向验证 + 真实冒烟验证**

---

## 2. 验证总原则

### 2.1 先静态，再单测，再真实运行

建议顺序：

1. 静态校验
2. 核心单测 / 集成测试
3. 模块定向测试
4. 真实运行冒烟测试

### 2.2 改哪层，就重点验证哪层

例如：

- 改 `browser/fetching.py`：重点跑 runtime 基础设施测试 + 真实浏览器冒烟
- 改 `core/engine/handler.py`：重点跑 block detector / runtime 测试
- 改 `core/extraction/extraction.py`：重点跑 extraction / AXTree / selector 相关测试

### 2.3 不把重依赖测试和核心回归混在一起

带重依赖的路径应单独验证：

- Scrapy adapter
- 浏览器 wrapper
- LLM / DSPy 路径

---

## 3. 静态校验

### 3.1 代码 / 测试 / 文档编译校验

```bash
PYTHONPATH=src python -m compileall src tests docs
```

用途：

- 快速发现语法错误
- 快速发现明显导入问题
- 对文档目录做轻量检查

### 3.2 Ruff（如果环境可用）

```bash
python -m ruff check src tests
```

用途：

- 统一代码风格
- 发现未使用导入、明显坏味道

---

## 4. 核心回归测试

这是当前最推荐的主回归集。

```bash
PYTHONPATH=src pytest tests/runtime tests/strategy tests/integration
```

用途：

- 验证运行时主链没有被破坏
- 验证 Tier / strategy 规则没有被破坏
- 验证公共 API 入口仍然可用

这组测试应该是：

## **每次中大型重构后的默认回归集**

---

## 5. 模块定向验证

### 5.1 BlockDetector / runtime 判断链

适用场景：

- 修改 `core/engine/handler.py`
- 修改 `core/engine/execution.py`
- 修改 `core/engine/processing.py`
- 修改 AXTree 语义确认参与 block 判断的逻辑

推荐命令：

```bash
PYTHONPATH=src pytest \
  tests/runtime/test_block_detector.py \
  tests/runtime/test_outcomes.py \
  tests/runtime/test_orchestrator.py
```

---

### 5.2 AXTree / extraction 路径

适用场景：

- 修改 `core/extraction/extraction.py`
- 修改 `AXTreeExtraction`
- 修改 `LLMExtractor` 的 AXTree 语义采样逻辑

推荐命令：

```bash
PYTHONPATH=src pytest \
  tests/extraction/test_axtree_extraction.py \
  tests/extraction/test_llm_extractor.py
```

> 注：`test_llm_extractor.py` 在缺少 `bs4` 的环境下会自动跳过。

---

### 5.3 浏览器池化 / fetcher / observability

适用场景：

- 修改 `browser/fetching.py`
- 修改浏览器池化逻辑
- 修改 fetcher stats / ad-blocking / release/close 行为

推荐命令：

```bash
PYTHONPATH=src pytest \
  tests/runtime/test_infrastructure.py \
  tests/runtime/test_runner_observability.py
```

---

### 5.4 Tier / strategy 规则

适用场景：

- 修改 `core/strategy.py`
- 修改 site 起始 Tier
- 修改 render / proxy 升级逻辑

推荐命令：

```bash
PYTHONPATH=src pytest tests/strategy/test_strategy.py
```

---

### 5.5 Public API / 运行时入口

适用场景：

- 修改 `run_crawl()`
- 修改 `runtime/orchestrator.py`
- 修改公共入口返回结构

推荐命令：

```bash
PYTHONPATH=src pytest tests/integration/test_public_api.py
```

---

### 5.6 Browser / Adapter / LLM 依赖型测试

适用场景：

- 修改 Scrapy 适配层
- 修改 browser wrapper
- 修改 DSPy / LLM 相关模块

推荐命令：

```bash
PYTHONPATH=src pytest tests/adapters tests/browser tests/llm
```

说明：

这组测试通常依赖外部环境、可选依赖或更重的运行条件，不建议和主回归集混在一起。

---

## 6. 真实运行冒烟验证

代码测试通过后，仍然建议至少跑两类真实任务。

### 6.1 轻量站点冒烟

```bash
PYTHONPATH=src python -m ai_crawler --sites target --query "chair" --pages 1
```

### 6.2 强反爬站点冒烟

```bash
PYTHONPATH=src python -m ai_crawler --sites amazon --query "inflatable" --pages 1
```

### 6.3 推荐观察指标

运行后至少关注：

- `tasks_success`
- `tasks_total`
- `block_types`
- `task_extraction_strategies`
- `task_axtree_hits`
- `fetcher_stats`

这些指标可以帮助判断：

- 是否出现误判增多
- 是否发生不必要的 Tier 升级
- 是否某条浏览器路径复用异常
- 是否 AXTree / JS / BS 提取链路有异常偏移

---

## 7. 推荐的三套固定命令

如果你平时只记三套命令，建议记这三套。

### 7.1 快速主回归

```bash
PYTHONPATH=src pytest tests/runtime tests/strategy tests/integration
```

### 7.2 全量轻量校验

```bash
PYTHONPATH=src python -m compileall src tests docs
```

### 7.3 真实冒烟

```bash
PYTHONPATH=src python -m ai_crawler --sites amazon --query "chair" --pages 1
```

---

## 8. 按修改类型选择验证策略

| 修改类型 | 最少应跑什么 |
|---|---|
| 文档修改 | `python -m compileall docs` |
| 小型运行时逻辑改动 | `tests/runtime` + `tests/strategy` |
| BlockDetector 改动 | `test_block_detector.py` + runtime 主回归 |
| AXTree / extraction 改动 | `test_axtree_extraction.py` + `test_llm_extractor.py` + runtime 主回归 |
| 浏览器池化 / fetcher 改动 | `test_infrastructure.py` + `test_runner_observability.py` + 真实冒烟 |
| Tier 规则改动 | `test_strategy.py` + 真实冒烟 |
| 公共 API / orchestrator 改动 | `test_public_api.py` + runtime 主回归 |
| Scrapy adapter 改动 | `tests/adapters` 单独跑 |

---

## 9. 为什么不能只看 pytest 全绿

因为当前系统里有几类测试并不总适合每次一起跑：

- 依赖浏览器环境
- 依赖可选依赖包
- 依赖外部服务配置

而且还有一些风险，单靠单测看不出来：

- 浏览器池复用是否异常
- block detector 是否让真实页面误升 Tier
- AXTree 语义确认是否在真实页面上跑偏
- 浏览器 fetch 路径是否因为环境问题退化

所以：

## **测试通过 ≠ 真实运行安全**

必须补真实冒烟。

---

## 10. 建议的团队验证规范

如果后续多人协作，建议统一成：

### 小改动

至少执行：

```bash
PYTHONPATH=src python -m compileall src tests docs
PYTHONPATH=src pytest tests/runtime tests/strategy tests/integration
```

### 中型改动

在小改动基础上，加：

- 对应模块定向测试

### 底层改动（浏览器、提取、block 判断、tier）

在上面基础上再加：

- 一次真实冒烟运行

---

## 11. 维护建议

如果未来测试结构或运行入口变化，请同步更新：

- 本文档 `docs/VERIFICATION.md`
- `README.md`
- 相关专题文档（如 `TIER_SYSTEM.md`、`BLOCK_DETECTOR.md`）

这份文档应该作为：

## **当前项目验证流程的正式入口文档**
