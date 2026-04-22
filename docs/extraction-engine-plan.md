# 解析策略引擎实施文档

## 目标

将页面解析策略从硬编码的 `SITE_EXTRACTION_CHAINS` 改为自学习的解析策略引擎。

---

## 现状问题

| 问题 | 文件 | 说明 |
|------|------|------|
| 硬编码站点策略 | `extraction.py` | 26 个站点写死策略链 |
| 重复逻辑 | `ExtractorChain` + `UniversalExtractor` | 重排逻辑重复 |
| 历史数据未使用 | `SiteMemory.get_best_extraction_method()` | 存在但从未调用 |
| 职责不清 | `ExtractionRuntimeService` | 既管提取又管策略 |

---

## 新架构

```
ExtractionEngine (提取引擎)
    │
    ├── 1. 模板提取 (TemplateStore)
    │
    ├── 2. 页面特征分析 (PageAnalyzer)
    │
    ├── 3. 问 ExtractionPolicyEngine 要策略顺序
    │
    ├── 4. 执行提取
    │
    └── 5. 记录结果到 ExtractionPolicyEngine

ExtractionPolicyEngine (解析策略引擎)
    │
    ├── get_order(site, page_type, features) → [策略顺序]
    │
    ├── record(site, method, count, success)
    │
    └── 基于 SiteMemory 自学习
```

---

## 架构图

```
MemoryStore
                    (共享的历史数据)
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 │                 ▼
┌───────────────┐        │      ┌───────────────────┐
│ CrawlPolicy   │        │      │ ExtractionPolicy  │
│   Engine      │        │      │     Engine        │
├───────────────┤        │      ├───────────────────┤
│ 爬取策略决策   │        │      │ 解析策略决策       │
│ - 渲染方式    │        │      │ - 提取器顺序      │
│ - 代理        │        │      │ - 页面特征分析    │
│ - 重试次数    │        │      │ - 模板学习        │
└───────────────┘        │      └───────────────────┘
        │                 │                 │
        │  爬取页面       │                 │
        └─────────────────┼─────────────────┘
                          ▼
                   ┌─────────────┐
                   │   页面池    │
                   └─────────────┘
```

---

## 各自职责

| 维度 | 爬虫策略引擎 | 解析策略引擎 |
|------|-------------|-------------|
| **决策目标** | 成功获取页面 HTML | 成功提取产品 |
| **输入** | URL, site, page_pattern | HTML, page, site |
| **输出** | CrawlStrategy (渲染+代理) | 策略顺序 [json_ld, bs_css, ...] |
| **历史数据** | successful_strategies | extraction_method_stats |
| **SiteMemory 字段** | `successful_strategies` | `extraction_method_stats` |

---

## 实施步骤

### Phase 1: 创建核心组件

**1.1 创建 `PageAnalyzer`**

```python
# src/ai_crawler/core/extraction/page_analyzer.py

@dataclass
class PageFeatures:
    has_json_ld: bool = False
    has_spa_signature: bool = False
    has_api_signatures: bool = False
    dom_depth: int = 0
    script_ratio: float = 0.0

class PageAnalyzer:
    def analyze(self, html: str, page: Any) -> PageFeatures:
        """分析页面特征"""
        has_json_ld = bool(re.search(r'<script[^>]*type=["\']application/ld\+json["\']', html))
        has_spa = any(re.search(p, html) for p in SPA_PATTERNS)
        # ...
```

**1.2 创建 `ExtractionPolicyEngine`**

```python
# src/ai_crawler/core/extraction/policy_engine.py

class ExtractionPolicyEngine:
    # 默认优先级 (数字越小越优先)
    DEFAULT_PRIORITY = {
        "json_ld": 1.0,
        "api_intercept": 2.0,
        "js_eval": 3.0,
        "axtree": 4.0,
        "bs_css": 5.0,
    }

    def __init__(self, memory_store: MemoryStore | None = None):
        self.memory_store = memory_store
        self._cache: dict[str, list[str]] = {}

    def get_order(self, site: str, page_type: str, features: PageFeatures) -> list[str]:
        """返回策略名称列表，按执行顺序"""
        # 1. 构建优先级分数
        scores = dict(self.DEFAULT_PRIORITY)

        # 2. 应用特征调整
        if features.has_json_ld:
            scores["json_ld"] *= 0.1
        if features.has_spa_signature:
            scores["js_eval"] *= 0.3
            scores["axtree"] *= 0.5

        # 3. 应用历史成功率调整
        memory = self._get_memory(site, page_type)
        if memory:
            best = memory.get_best_extraction_method()
            if best and best in scores:
                scores[best] *= 0.5

        # 4. 排序返回
        return sorted(scores.keys(), key=lambda k: scores[k])

    def record(self, site: str, page_type: str, method: str, product_count: int, success: bool):
        """记录提取结果"""
        memory = self._get_memory(site, page_type)
        outcome = "success" if success and product_count >= 3 else "partial"
        memory.record_extraction_quality(method, outcome, product_count)
```

**1.3 创建 `ExtractionEngine`**

```python
# src/ai_crawler/core/extraction/engine.py

class ExtractionEngine:
    def __init__(
        self,
        strategies: dict[str, ExtractionStrategy],
        policy_engine: ExtractionPolicyEngine,
        template_store: TemplateStore | None = None,
    ):
        self.strategies = strategies
        self.policy_engine = policy_engine
        self.template_store = template_store
        self.analyzer = PageAnalyzer()

    def extract(self, task: CrawlTask, page: Any, html: str) -> ExtractionDecision:
        site = task.site
        page_type = getattr(task.page_pattern, 'value', 'unknown')

        # 1. 模板优先
        if self.template_store:
            template = self.template_store.get(site, page_type)
            if template and template.is_valid:
                result = template.extract(page, html, task.url)
                if result.products:
                    self.policy_engine.record(site, page_type, "template", len(result.products), True)
                    return self._to_decision(result, "template")

        # 2. 分析页面特征
        features = self.analyzer.analyze(html, page)

        # 3. 问策略引擎要顺序
        order = self.policy_engine.get_order(site, page_type, features)

        # 4. 按顺序执行
        for strategy_name in order:
            if strategy_name not in self.strategies:
                continue
            extractor = self.strategies[strategy_name]
            try:
                products = extractor.extract(page, html, task.url)
                success = len(products) >= 2
                self.policy_engine.record(site, page_type, strategy_name, len(products), success)
                if products:
                    return ExtractionDecision(...)
            except Exception:
                continue

        # 5. 全失败
        return ExtractionDecision(products=[], outcome=ExtractionOutcomeType.EMPTY_CONTENT)
```

---

### Phase 2: 策略注册表

**2.1 创建 `registry.py`**

```python
# src/ai_crawler/core/extraction/registry.py

from ai_crawler.core.extraction.json_ld import JSONLDExtraction
from ai_crawler.core.extraction.js_eval import JSEvaluateExtraction
from ai_crawler.core.extraction.api_intercept import APIInterceptExtraction
from ai_crawler.core.extraction.axtree import AXTreeExtraction
from ai_crawler.core.extraction.bs_css import BSExtraction

EXTRACTION_STRATEGIES: dict[str, type[ExtractionStrategy]] = {
    "json_ld": JSONLDExtraction,
    "js_eval": JSEvaluateExtraction,
    "api_intercept": APIInterceptExtraction,
    "axtree": AXTreeExtraction,
    "bs_css": BSExtraction,
}

def create_strategy(name: str) -> ExtractionStrategy:
    """工厂方法创建策略实例"""
    cls = EXTRACTION_STRATEGIES.get(name)
    if cls is None:
        raise ValueError(f"Unknown extraction strategy: {name}")
    return cls()
```

---

### Phase 3: 消除硬编码

**3.1 删除 `extraction.py` 中的以下内容**

- `_build_default_chains()` 函数
- `SITE_EXTRACTION_CHAINS` 变量
- 所有站点硬编码链定义

**3.2 更新 `__init__.py` 导出**

```python
# src/ai_crawler/core/extraction/__init__.py

from ai_crawler.core.extraction.engine import ExtractionEngine
from ai_crawler.core.extraction.policy_engine import ExtractionPolicyEngine
from ai_crawler.core.extraction.page_analyzer import PageAnalyzer, PageFeatures
from ai_crawler.core.extraction.registry import EXTRACTION_STRATEGIES, create_strategy

__all__ = [
    "ExtractionEngine",
    "ExtractionPolicyEngine",
    "PageAnalyzer",
    "PageFeatures",
    "EXTRACTION_STRATEGIES",
    "create_strategy",
    # ... 保留原有导出
]
```

---

### Phase 4: 测试

**4.1 单元测试**

| 测试文件 | 验证 |
|----------|------|
| `test_page_analyzer.py` | JSON-LD, SPA, API 特征检测 |
| `test_policy_engine.py` | 历史学习, 特征优先 |
| `test_extraction_engine.py` | 顺序执行, 结果记录 |

**4.2 集成测试**

```python
def test_unknown_site_uses_default_order():
    """新站点使用默认顺序"""
    engine = ExtractionEngine(...)
    policy = ExtractionPolicyEngine()

    features = PageFeatures(has_json_ld=False, has_spa_signature=False)
    order = policy.get_order("unknown_site", "search", features)

    assert order == ["json_ld", "api_intercept", "js_eval", "axtree", "bs_css"]

def test_json_ld_site_prioritizes_json_ld():
    """有 JSON-LD 的页面优先用 JSON-LD"""
    features = PageFeatures(has_json_ld=True)
    order = policy.get_order("any_site", "search", features)

    assert order[0] == "json_ld"
```

---

## 文件变更

| 操作 | 文件 |
|------|------|
| **新增** | `src/ai_crawler/core/extraction/page_analyzer.py` |
| **新增** | `src/ai_crawler/core/extraction/policy_engine.py` |
| **新增** | `src/ai_crawler/core/extraction/engine.py` |
| **新增** | `src/ai_crawler/core/extraction/registry.py` |
| **修改** | `src/ai_crawler/core/extraction/__init__.py` |
| **删除** | `src/ai_crawler/core/extraction/extraction.py` (SITE_EXTRACTION_CHAINS) |
| **修改** | `src/ai_crawler/core/engine/extraction_runtime.py` |

---

## 风险与回滚

| 风险 | 缓解 |
|------|------|
| 新引擎策略顺序不佳 | 保底使用 DEFAULT_PRIORITY 顺序 |
| SiteMemory 数据丢失 | 持久化到 JSON 文件 |
| 性能下降 | 策略顺序结果缓存 |

---

## 实施顺序

1. **Phase 1**: 创建 PageAnalyzer, ExtractionPolicyEngine, ExtractionEngine
2. **Phase 2**: 创建 registry.py 统一策略注册
3. **Phase 3**: 消除 SITE_EXTRACTION_CHAINS 硬编码
4. **Phase 4**: 编写测试
5. **Phase 5**: 集成到现有系统
