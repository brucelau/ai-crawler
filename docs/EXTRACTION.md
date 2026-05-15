# Extraction 模块

## 概述

Extraction 模块（`ai_crawler.spider.extraction`）负责在页面被抓取后从中提取产品数据。

## 架构

```
extraction/
├── base.py              # 核心抽象类
├── extractors/          # 具体提取器实现
│   ├── axtree.py       # 辅助树提取
│   ├── api_intercept.py # API 响应拦截
│   ├── bs_css.py       # BeautifulSoup CSS 选择器
│   ├── json_ld.py      # JSON-LD 结构化数据
│   └── js_eval.py      # JavaScript 执行
├── engine/              # 提取编排
│   ├── extraction_engine.py  # 主提取流程
│   ├── policy_engine.py     # 策略选择逻辑
│   └── registry.py          # 提取器注册表
├── templates/           # 模板提取
├── analysis/            # 页面分析工具
└── generic/            # 共享工具
```

## 核心概念

### ExtractionStrategy

所有提取器的基类：

```python
class ExtractionStrategy:
    name: str
    method: str

    def extract(self, page: Any, html: str, url: str) -> list[Product]:
        raise NotImplementedError
```

### ExtractionResult

提取器返回类型：

```python
@dataclass
class ExtractionResult:
    products: list[Product]
    strategy: str
    method: str
    outcome: str = "success"
```

### ExtractionDecision

提取引擎的最终决策：

```python
@dataclass
class ExtractionDecision:
    products: list[Product]
    outcome: ExtractionOutcomeType
    strategy_name: str
    method: str
    metadata: dict | None
    retry_strategy: CrawlStrategy | None
```

## 提取器

| 提取器 | 方法 | 说明 |
|--------|------|------|
| `JSONLDExtractor` | beautifulsoup | 解析 `<script type="application/ld+json">` 中的 JSON-LD 结构化数据 |
| `JSEvaluateExtractor` | page_evaluate | 执行 JavaScript 提取产品数据 |
| `BSExtractor` | beautifulsoup | 使用站点特定的 BeautifulSoup CSS 选择器 |
| `AXTreeExtractor` | accessibility_tree | 使用浏览器辅助树提取 |
| `APIInterceptExtractor` | api_intercept | 拦截页面加载期间的 API 响应 |
| `DetailPageExtraction` | beautifulsoup | 详情页专用提取器 |
| `GenericCSSFallback` | beautifulsoup | 使用通用 CSS 选择器作为兜底 |

## 提取流程

```
ExtractionEngine.extract(task, page, html)
    │
    ├─► 1. 尝试模板提取（如有模板）
    │       └─► Template.extract() → ExtractionResult
    │
    ├─► 2. 分析页面特征
    │       └─► PageAnalyzer.analyze() → PageFeatures
    │
    ├─► 3. 从策略引擎获取执行顺序
    │       └─► ExtractionPolicyEngine.get_order() → list[str]
    │
    └─► 4. 按顺序尝试各策略直到成功
            for strategy_name in order:
                extractor = STRATEGY_REGISTRY[strategy_name]
                result = extractor.extract(page, html, url)
                if len(products) >= 2:
                    return ExtractionDecision(products, success)
            return ExtractionDecision(outcome=EMPTY_CONTENT)
```

## 策略引擎

`ExtractionPolicyEngine` 根据以下因素决定使用哪些提取器及其顺序：

- 站点特定的历史成功率
- 页面类型（搜索、详情等）
- 页面特征（是否有 JSON-LD、是否有辅助树等）

```python
engine.get_order(site, page_type, features) -> list[str]
```

## 注册表

`STRATEGY_REGISTRY` 将策略名称映射到提取器类：

```python
STRATEGY_REGISTRY = {
    "json_ld": JSONLDExtractor,
    "js_eval": JSEvaluateExtractor,
    "api_intercept": APIInterceptExtractor,
    "axtree": AXTreeExtractor,
    "bs_css": BSExtractor,
    "detail_page": DetailPageExtraction,
}
```

使用 `create_strategy(name)` 实例化提取器：

```python
extractor = create_strategy("json_ld")
```

## 使用示例

```python
from ai_crawler.spider.extraction import ExtractionEngine, ExtractionPolicyEngine
from ai_crawler.spider.extraction.engine.registry import create_strategy, STRATEGY_REGISTRY

# 创建带策略的引擎
policy = ExtractionPolicyEngine()
engine = ExtractionEngine(
    strategies={name: create_strategy(name) for name in STRATEGY_REGISTRY},
    policy_engine=policy,
)

# 从页面提取产品
decision = engine.extract(task, page, html)
print(f"使用 {decision.strategy_name} 提取了 {len(decision.products)} 个产品")
```

## 模板提取

模板（`TemplateStore`）提供站点特定的提取逻辑：

```python
from ai_crawler.spider.extraction.templates import template_store

template = template_store.load(site, page_pattern)
if template and template.is_valid:
    result = template.extract(page, html, url)
```

模板优先于基于策略的提取。

## 页面分析

`PageAnalyzer` 检查 HTML 以确定页面特征：

```python
features = analyzer.analyze(html, page)
# features.has_json_ld
# features.has_accessibility_tree
# features.has_api_calls
# 等等
```

这些特征影响策略引擎的策略选择。
