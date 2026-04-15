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
  -> runtime/SmartCrawlerRuntime
  -> core/runner.CrawlRunner
  -> core/runtime/* 运行时服务
  -> browser/fetching.py
  -> output/traces
```

Scrapy 当前仅作为：

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
├─ runtime/                 # 对外运行时入口
├─ core/runtime/            # 内部运行时服务
├─ browser/                 # 浏览器抓取与 wrapper
├─ core/extraction/         # 提取链与 AXTree 提取
├─ adapters/scrapy/         # Scrapy 辅助适配层
├─ models/                  # 与 Scrapy 解耦的领域模型
└─ tests/                   # 按架构分层后的测试目录
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

- `src/ai_crawler/config.py`

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
