# AI-Crawler

AI-Crawler 是一个面向电商站点的智能爬虫系统，核心目标是：

- 在强反爬环境下逐级升级抓取策略
- 以浏览器优先运行时为中心组织抓取流程
- 在保证提取质量的同时控制浏览器成本
- 通过多级提取链（`json_ld -> js_eval -> api_intercept -> axtree -> bs_css`）提高页面解析成功率

---

## 1. 当前架构概览

当前代码主路径已经调整为：

```text
CLI / API
  -> ai_crawler.run_crawl()
  -> orchestration/SmartCrawlerRuntime
  -> core/runner.CrawlRunner
  -> core/engine/* 运行时服务
  -> browser/fetching.py
  -> output/traces
```

Scrapy 当前仅作为（已移至 `integrations/`）：

- 辅助调度入口
- pipeline / item 输出集成层
- 兼容旧 spider 工作流的适配层

不再作为智能反爬决策中心。

---

## 2. 核心能力

### 2.1 反爬升级系统

- 8 层 Tier 策略
- 从轻量 HTTP 到高成本指纹浏览器逐级升级
- 当前已支持多种浏览器路径的池化 / 预热池 / 观测指标

### 2.2 浏览器优先运行时

- Playwright / Camoufox / UC / CloakBrowser 等抓取路径
- 浏览器上下文复用
- 广告脚本拦截（按当前策略仅限部分路径）
- Fetcher 级运行指标与统计

### 2.3 多级提取链

- `json_ld`
- `js_eval`
- `api_intercept`
- `axtree`
- `bs_css`

### 2.4 BlockDetector 误判抑制

- 强 / 弱信号分离
- 页面类型感知（search / detail / review）
- AXTree 语义确认辅助放行

---

## 3. 目录概览

```text
src/ai_crawler/
├─ orchestration/           # 对外运行时入口
│   ├─ orchestrator.py    # SmartCrawlerRuntime
│   ├─ models.py          # RuntimeTask, RuntimeBatchResult
│   ├─ storage.py         # ProductOutputWriter
│   └─ crawler.py         # ECrawler
├─ core/
│   ├─ engine/            # 内部运行时引擎
│   │   ├─ execution.py
│   │   ├─ processing.py
│   │   ├─ queue.py
│   │   ├─ planner.py
│   │   └─ ...
│   ├─ extraction/        # 提取链与 AXTree 提取
│   ├─ llm/              # DSPy/LLM 推理
│   ├─ runner.py         # CrawlRunner
│   ├─ strategy.py       # 策略与站点配置
│   └─ types.py         # 核心类型定义
├─ browser/                # 浏览器抓取与 wrapper
│   ├─ fetching.py
│   ├─ interaction.py
│   └─ wrappers/         # playwright, cloudscraper, etc.
├─ config/                  # 配置
│   ├─ __init__.py       # 环境变量配置
│   ├─ settings.py       # Scrapy 设置
│   ├─ sites.py          # 站点配置数据
│   └─ sites.yaml       # YAML 配置框架
├─ integrations/          # Scrapy 集成层 (DEPRECATED)
│   ├─ scrapy/          # Scrapy 适配
│   ├─ middlewares/      # Scrapy 中间件
│   ├─ pipelines/        # Scrapy 管道
│   ├─ captcha/          # 验证码
│   ├─ proxy/            # 代理管理
│   └─ scheduler/        # 任务调度
├─ spiders/              # 爬虫定义
├─ models/               # 数据模型
├─ utils/               # 工具函数
└─ templates/            # 模板
```

---

## 4. 安装

### 4.1 Python 版本

- Python `>= 3.11`

### 4.2 安装依赖

```bash
pip install -e .
```

如果需要开发依赖：

```bash
pip install -e .[dev]
```

---

## 5. 环境变量

常用配置位于：

- `src/ai_crawler/config/__init__.py` (环境变量配置)
- `src/ai_crawler/config/sites.py` (站点配置数据)
- `src/ai_crawler/config/settings.py` (Scrapy 设置)

常见环境变量：

```bash
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4o

2CAPTCHA_API_KEY=

THORDATA_PROXY_HOST=pr.thordata.net
THORDATA_PROXY_PORT=9999
THORDATA_RESIDENTIAL_USERNAME=
THORDATA_RESIDENTIAL_PASSWORD=

KAMELEO_API_URL=http://localhost:5050
KAMELEO_API_KEY=

REQUEST_TIMEOUT=30
PAGE_LOAD_TIMEOUT=30
PROXY_DISABLED=false

LOG_LEVEL=INFO
LOG_DIR=logs
LOG_FILE=crawler.log
```

---

## 6. 运行方式

### 6.1 CLI 运行

入口文件：

- `src/ai_crawler/__main__.py`

示例：

```bash
PYTHONPATH=src python -m ai_crawler --sites amazon walmart target --query "inflatable" --pages 1
```

输出包括：

- 商品数量
- 成功任务数
- 输出文件路径
- traces 文件路径
- block type 统计

### 6.2 通过 Python API 调用

```python
from ai_crawler import run_crawl

result = run_crawl(
    sites=["amazon", "walmart"],
    query="chair",
    pages=1,
)

print(len(result.products))
print(result.stats)
```

### 6.3 通过 Scrapy 适配层调用

示例脚本：

- `demos/run_scrapy.py`

当前推荐把 Scrapy 当作辅助层使用，而不是主逻辑中心。

---

## 7. 测试

测试目录已按新架构分层：

- `tests/runtime/`
- `tests/strategy/`
- `tests/adapters/`
- `tests/browser/`
- `tests/extraction/`
- `tests/captcha/`
- `tests/llm/`
- `tests/integration/`

常用验证命令：

```bash
PYTHONPATH=src pytest tests/runtime tests/strategy tests/integration
```

代码与文档轻量校验：

```bash
PYTHONPATH=src python -m compileall src/ai_crawler
python -m compileall docs
```

---

## 8. 文档索引

### 核心文档

- `docs/ARCHITECTURE.md`
  - 整体系统架构、运行时分层、模块职责、主调用链

- `docs/TIER_SYSTEM.md`
  - Tier 升级策略、各层反爬能力、默认起始 Tier、性能优化边界

- `docs/BLOCK_DETECTOR.md`
  - BlockDetector / AntiBotHandler / AXTree 语义确认 / 误判抑制逻辑

- `docs/ANTI_BOT_FINGERPRINTER.md`
  - 反爬供应商推断、机制推断、fingerprinter 与 trace / policy 的关系

- `docs/LLM_SYSTEM.md`
  - LLM / DSPy 推理层、Pydantic 校验层、LLM 参与的运行时决策链

- `docs/VERIFICATION.md`
  - 分层验证流程、定向测试命令、真实冒烟验证建议

---

## 9. 当前代码状态说明

当前 `gpt` 分支已经完成多轮重构，主要方向包括：

- 建立浏览器优先运行时
- 将 Scrapy 收缩为辅助层
- 引入 AXTree 提取与语义确认
- 分阶段优化 BlockDetector 误判问题
- 为多种浏览器路径补齐池化 / 预热池 / 生命周期管理基础

如果继续演进，建议始终同步更新：

- 代码
- 测试
- docs 目录下的专题文档

避免架构文档和实现再次脱节。

---

## 10. 代码质量改进日志

### 2026-04-19: P0 修复完成

#### P0-1: 类型注解修复
- **问题**: `extraction.py` 中使用 `any` 作为类型注解（应为 `typing.Any`）
- **修复**: 
  - 添加 `from typing import Any, Callable`
  - 替换所有 `page: any` → `page: Any`
  - 替换 `Callable[[any, str, str], ...]` → `Callable[[Any, str, str], ...]`
- **影响文件**: `src/ai_crawler/core/extraction/extraction.py`

#### P0-2: 站点推断逻辑去重
- **问题**: `_infer_source` 方法在 5 个类中重复定义
- **修复**:
  - 创建 `src/ai_crawler/utils/site.py`
  - 提取 `DOMAIN_TO_SITE` 映射表
  - 实现 `infer_site_from_url()` 和 `infer_site_from_url_or_empty()` 函数
  - 更新所有 5 个 ExtractionStrategy 类使用集中化函数
- **影响文件**:
  - `src/ai_crawler/utils/__init__.py` (新增)
  - `src/ai_crawler/utils/site.py` (新增)
  - `src/ai_crawler/core/extraction/extraction.py`

#### P0-3: 异常处理改进
- **问题**: 宽泛的 `except Exception:` 吞掉所有异常，无日志
- **修复**:
  - 添加 `structlog` 导入
  - 在关键位置添加日志记录：
    - `js_evaluation_extraction_failed` (warning)
    - `bs_extraction_failed` (warning)
    - `api_intercept_failed` (debug)
    - `accessibility_snapshot_failed` (debug)
    - `cdp_tree_capture_failed` (debug)
    - `extraction_strategy_failed` (debug)
    - `generic_css_fallback_failed` (debug)
- **影响文件**: `src/ai_crawler/core/extraction/extraction.py`

### P1-1: 拆分 extraction.py (2026-04-19)

- **问题**: `extraction.py` 单文件 1960 行，包含 9 个类和大量重复代码
- **修复**:
  - 拆分为 7 个模块:
    - `base.py` - ExtractionResult, ExtractionStrategy, GenericCSSFallback, ExtractorChain
    - `json_ld.py` - JSONLDExtraction
    - `js_eval.py` - JSEvaluateExtraction (含所有站点 JS 模板)
    - `api_intercept.py` - APIInterceptExtraction
    - `bs_css.py` - BSExtraction
    - `axtree.py` - AXTreeExtraction
    - `extraction.py` - 向后兼容 shim，重新导出所有类
  - 保留 `SITE_EXTRACTION_CHAINS` 向后兼容
- **影响文件**:
  - `src/ai_crawler/core/extraction/base.py` (新增)
  - `src/ai_crawler/core/extraction/json_ld.py` (新增)
  - `src/ai_crawler/core/extraction/js_eval.py` (新增)
  - `src/ai_crawler/core/extraction/api_intercept.py` (新增)
  - `src/ai_crawler/core/extraction/bs_css.py` (新增)
  - `src/ai_crawler/core/extraction/axtree.py` (新增)
  - `src/ai_crawler/core/extraction/extraction.py` (重构为 shim)
  - `src/ai_crawler/core/extraction/__init__.py` (更新导入)

### P1-2: SiteSpider 统一 Spider 类 (2026-04-19)

- **问题**: 30+ 个 spider 类 (amazon.py, walmart.py 等) 95% 代码重复
- **修复**:
  - 创建 `SiteSpider` 统一蜘蛛类，接受 `site` 参数配置
  - 创建 `SiteConfig` 数据类定义站点配置 (域名、URL模板等)
  - 创建 `DEFAULT_SITES` 字典包含 30 个站点配置
  - 保留所有现有 spider 类作为向后兼容
- **影响文件**:
  - `src/ai_crawler/spiders/site_spider.py` (新增)
  - `src/ai_crawler/spiders/__init__.py` (更新)
- **使用示例**:
  ```python
  from ai_crawler.spiders import SiteSpider
  spider = SiteSpider(site='amazon', query='chair', pages=3)
  ```

### P1-3: 站点配置抽取 (2026-04-19)

- **问题**: `strategy.py` 单文件 1700 行，包含大量站点配置数据
- **修复**:
  - 创建 `config/sites.py` 包含所有站点配置
  - 创建 `config/sites.yaml` 作为未来 YAML 配置框架
  - 创建 `core/types.py` 包含核心类型 (CrawlStrategy, enums) 打破循环导入
  - 提取 TIER_CONFIGS, SITE_TIER_DEFAULTS, URL_PATTERNS, PATTERNS, SUPPORTED_SITES
- **影响文件**:
  - `src/ai_crawler/config/__init__.py` (原 config.py 转为包)
  - `src/ai_crawler/config/sites.py` (新增)
  - `src/ai_crawler/config/sites.yaml` (新增)
  - `src/ai_crawler/core/types.py` (新增)
  - `src/ai_crawler/core/strategy.py` (1700→120行)

### P1-4: 目录重命名 (2026-04-19)

- **问题**: `runtime/` 与 `core/runtime/` 命名混淆，难以区分公共API与内部实现
- **修复**:
  - `runtime/` → `orchestration/` (公共API层)
  - `core/runtime/` → `core/engine/` (内部引擎)
- **影响文件** (15个文件更新导入路径):
  - `src/ai_crawler/__init__.py`
  - `src/ai_crawler/crawler.py`
  - `src/ai_crawler/core/__init__.py`
  - `src/ai_crawler/core/runner.py`
  - `src/ai_crawler/orchestration/__init__.py`
  - `src/ai_crawler/orchestration/models.py`
  - `src/ai_crawler/orchestration/orchestrator.py`
  - `src/ai_crawler/orchestration/storage.py`
  - `src/ai_crawler/core/engine/__init__.py`
  - `src/ai_crawler/core/engine/processing.py`
  - `src/ai_crawler/core/engine/outcomes.py`
  - `src/ai_crawler/core/engine/results.py`
  - `src/ai_crawler/core/engine/execution.py`
  - `src/ai_crawler/core/engine/policy_engine.py`
  - `src/ai_crawler/core/engine/planner.py`

### P2-1: Scrapy 适配层废弃标记 (2026-04-19)

- **问题**: `adapters/scrapy/` 适配层与主要爬虫路径不同步
- **修复**:
  - 在 `adapters/scrapy/__init__.py` 添加 DEPRECATED 标记
  - 推荐使用 `ai_crawler.orchestration.SmartCrawlerRuntime` 作为主要入口
- **影响文件**:
  - `src/ai_crawler/adapters/scrapy/__init__.py`

### P2-2: interaction.py 迁移 (2026-04-19)

- **问题**: `core/interaction.py` 与浏览器功能相关但放在 core/ 目录
- **修复**:
  - 将 `core/interaction.py` 移动到 `browser/interaction.py`
  - 更新 `browser/fetching.py` 中的导入路径
- **影响文件**:
  - `src/ai_crawler/core/interaction.py` → `src/ai_crawler/browser/interaction.py`
  - `src/ai_crawler/browser/fetching.py`

### P2-3: integrations/ 目录重组 (2026-04-19)

- **问题**: Scrapy 相关模块分散在顶层，结构混乱
- **修复**:
  - 新建 `integrations/` 目录，汇集所有 Scrapy 集成模块
  - 将 `captcha/`, `proxy/`, `scheduler/`, `extensions/`, `pipelines/`, `middlewares/` 移入 `integrations/`
  - 将 `adapters/scrapy/` 移入 `integrations/scrapy/`
  - 将 `scrapy_middleware.py` 移入 `integrations/scrapy_middleware.py`
  - 将 `settings.py` 移入 `config/settings.py`
  - 将 `crawler.py` 移入 `orchestration/crawler.py`
  - 删除顶层 `types.py` (已在 `core/types.py`)
  - 删除空的 `adapters/` 目录
  - 更新所有导入路径
- **影响文件** (20+ 文件):
  - `src/ai_crawler/crawler.py` → `src/ai_crawler/orchestration/crawler.py`
  - `src/ai_crawler/settings.py` → `src/ai_crawler/config/settings.py`
  - `src/ai_crawler/types.py` (删除)
  - `src/ai_crawler/adapters/` (删除)
  - `src/ai_crawler/integrations/scrapy/` (从 adapters/ 移入)
  - `src/ai_crawler/integrations/captcha/` (从顶层移入)
  - `src/ai_crawler/integrations/proxy/` (从顶层移入)
  - `src/ai_crawler/integrations/scheduler/` (从顶层移入)
  - `src/ai_crawler/integrations/extensions/` (从顶层移入)
  - `src/ai_crawler/integrations/pipelines/` (从顶层移入)
  - `src/ai_crawler/integrations/middlewares/` (从顶层移入)
  - `src/ai_crawler/integrations/scrapy_middleware.py` (从顶层移入)
  - `src/ai_crawler/orchestration/orchestrator.py`
  - `src/ai_crawler/browser/fetching.py`
  - `src/ai_crawler/core/engine/proxying.py`
  - `src/ai_crawler/core/engine/captcha.py`
  - `src/ai_crawler/config/settings.py`
  - `src/ai_crawler/integrations/scheduler/runner.py`
  - `src/ai_crawler/integrations/scrapy/__init__.py`
  - `src/ai_crawler/integrations/scrapy/spiders/__init__.py`
  - `src/ai_crawler/integrations/scrapy/spiders/runtime.py`
  - `src/ai_crawler/integrations/captcha/__init__.py`
  - `src/ai_crawler/integrations/captcha/detector.py`
  - `src/ai_crawler/integrations/scheduler/__init__.py`
  - `src/ai_crawler/integrations/middlewares/__init__.py`
  - `src/ai_crawler/integrations/middlewares/captcha.py`
  - `src/ai_crawler/integrations/middlewares/proxy.py`
  - `src/ai_crawler/integrations/proxy/__init__.py`

### P2-4: 目录结构最终形态 (2026-04-19)

重构后的清晰目录结构：

```text
src/ai_crawler/
├── orchestration/           # 对外运行时入口
│   ├── orchestrator.py    # SmartCrawlerRuntime
│   ├── models.py          # RuntimeTask, RuntimeBatchResult
│   ├── storage.py        # ProductOutputWriter
│   └── crawler.py        # ECrawler (从顶层移入)
│
├── core/                 # 核心引擎
│   ├── engine/           # 内部运行时引擎 (原 core/runtime/)
│   ├── extraction/       # 页面提取链
│   ├── llm/             # AI/LLM
│   ├── runner.py        # CrawlRunner
│   ├── strategy.py      # 策略 (精简后 120 行)
│   └── types.py         # 核心类型 (CrawlStrategy, enums)
│
├── browser/              # 浏览器交互
│   ├── fetching.py
│   ├── interaction.py   # (从 core/ 移入)
│   └── wrappers/        # playwright, cloudscraper, etc.
│
├── config/               # 配置统一
│   ├── __init__.py     # 环境变量
│   ├── settings.py      # Scrapy 设置 (从顶层移入)
│   ├── sites.py         # 站点配置
│   └── sites.yaml       # YAML 配置框架
│
├── integrations/         # Scrapy 集成层 (DEPRECATED)
│   ├── scrapy/        # Scrapy 适配
│   ├── middlewares/    # Scrapy 中间件
│   ├── pipelines/       # Scrapy 管道
│   ├── captcha/        # 验证码
│   ├── proxy/          # 代理管理
│   └── scheduler/       # 任务调度
│
├── spiders/             # 爬虫定义
├── models/              # 数据模型
└── utils/              # 工具函数
```
