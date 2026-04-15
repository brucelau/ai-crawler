# BlockDetector 参考文档

> 状态：已与当前 `gpt` 分支实现对齐。
>
> 适用范围：BlockDetector / AntiBotHandler / AXTree 语义确认 / 误判抑制逻辑。
>
> 相关文档：
>
> - `docs/ARCHITECTURE.md`
> - `docs/TIER_SYSTEM.md`
> - `docs/LLM_SYSTEM.md`
>
> 当前运行时还增加了与 BlockDetector 并行协作的 **Anti-Bot Fingerprinter**，用于在不改变主判定逻辑的前提下输出：
>
> - 反爬供应商推断
> - 主要机制推断
> - 置信度
> - 证据

本文档系统说明当前 BlockDetector 的完整逻辑，覆盖以下代码路径：

- `src/ai_crawler/core/runtime/handler.py`
- `src/ai_crawler/core/runtime/execution.py`
- `src/ai_crawler/core/runtime/processing.py`
- `src/ai_crawler/core/extraction/extraction.py`（AXTree 语义确认）

---

## 1. 文档目的

`BlockDetector` 的职责是判断一次抓取得到的页面应该被视为：

- 正常页
- 被拦截页
- 或者“存在弱可疑信号，但可被更强语义证据放行”的页面

它的设计目标是：

- 降低正常电商页面的误判
- 优先保护以下页面类型：
  - 搜索结果页
  - 商品详情页
  - 评论页
- 同时对强反爬挑战保持保守、严格的判断方式

---

## 2. 主要组成部分

### 2.1 `BlockType`

定义位置：

- `src/ai_crawler/core/runtime/handler.py`

当前枚举值：

- `none`
- `http_403`
- `http_429`
- `http_451`
- `http_timeout`
- `captcha`
- `cloudflare`
- `bot_detected`
- `soft_suspicion`
- `empty_response`
- `unknown`

> 说明：`soft_suspicion` 目前仍属于内部逻辑概念。对外公开的 runtime 接口依旧保持 `blocked / not blocked` 的使用方式，没有单独暴露一个新的状态机。

---

### 2.2 `BlockDetectionContext`

定义位置：

- `src/ai_crawler/core/runtime/handler.py`

字段：

- `site`
- `page_pattern`
- `goal`
- `semantic_confirmation`

它让 detector 具备：

- 页面类型感知能力
- 任务目标回退能力（当 `page_pattern` 无法确定时）
- AXTree 语义确认能力

---

### 2.3 `AntiBotHandler`

定义位置：

- `src/ai_crawler/core/runtime/handler.py`

职责：

- 委托给 `BlockDetector.detect(...)`
- 为每个 URL 记录尝试历史
- 仅保留最近 20 次尝试记录

当前公开方法：

```python
is_blocked(status_code, text, context=None) -> tuple[bool, str]
```

---

## 3. 调用链路

### 3.1 主运行时路径

1. `TaskExecutionEngine.execute(...)` 抓取页面
2. 构造 `BlockDetectionContext`
3. 调用：

```python
self.anti_bot.is_blocked(status_code, html, context)
```

4. 如果被判为 blocked：
   - 可能触发代理轮换
   - 可能触发 captcha 求解
   - 可能触发失败处理、trace 记录、策略升级
5. 如果不被判为 blocked：
   - 继续进入 extraction 流程

主要文件：

- `src/ai_crawler/core/runtime/execution.py`
- `src/ai_crawler/core/runtime/processing.py`

### 3.2 Captcha 重试路径

当 captcha 被求解后，runtime 会重新抓取页面，并再次执行 block 判断。此时如果仍有 live `page`，也会把 semantic confirmation 一起带入。

---

## 4. 规则优先级

BlockDetector 当前严格按照下面的顺序判断：

1. **硬 HTTP 状态码 block**
2. **强 Cloudflare 信号**
3. **强 CAPTCHA 信号**
4. **强 bot-detection 信号**
5. **成功页信号**
6. **弱信号判断**
7. **空响应判断**
8. 否则返回 `none`

这个顺序非常关键：

- 强 challenge 页必须优先命中
- 成功页可以压过弱信号
- AXTree 语义确认只能辅助压低误判，不能压过强 challenge

---

## 5. 硬拦截规则

### 5.1 HTTP 状态码规则

以下情况会立即判为 block：

- `403` -> `http_403`
- `429` -> `http_429`
- `451` -> `http_451`
- `None` 或 `>= 500` -> `http_timeout`

这些规则优先级最高。

---

### 5.2 强 Cloudflare 信号

当前强 Cloudflare 模式包括：

- `checking your browser`
- `cf-challenge`
- `attention required!`
- `just a moment`

命中即返回：

- `cloudflare`

---

### 5.3 强 CAPTCHA 信号

当前强 CAPTCHA 模式包括：

- `are you a robot`
- `prove you're not a robot`
- `i am not a robot`
- `verify you are human`
- `complete the captcha`
- `enter the characters`
- `type the letters`

命中即返回：

- `captcha`

---

### 5.4 强 bot 信号

当前强 bot 模式包括：

- `blocked your ip`
- `unusual traffic`
- `automated requests`
- `security check failed`

命中即返回：

- `bot_detected`

---

## 6. 成功页信号

Detector 内置了大量成功页 allow-signal，用于降低误判。

### 6.1 硬成功信号

示例：

- `s-item__title`
- `data-listingid`
- `ebay.com/itm/`
- `data-asin`
- `data-item-id`
- `product-title`
- `"@type":"product"`
- `itemprop="price"`
- `itemprop="name"`

如果命中硬成功信号，并且之前没有命中更高优先级规则，则返回：

- `none`

---

### 6.2 页面类型成功信号

Detector 现在按页面类型区分成功信号。

#### Search 页成功信号

示例：

- `search results`
- `results for`
- `gridcell`
- `product-grid`
- `product-list`
- `search-result`
- `result-item`

#### Detail 页成功信号

示例：

- `add to cart`
- `buy now`
- `product details`
- `about this item`
- `description`
- `specifications`

#### Review 页成功信号

示例：

- `customer reviews`
- `write a review`
- `verified purchase`
- `out of 5 stars`
- `global ratings`
- `review this product`

---

### 6.3 软成功信号

示例：

- `product-card`
- `product-tile`
- `data-product-id`
- `data-productid`
- `add to cart`
- `buy now`
- `search results`
- `results for`
- `price-current`
- `price__current`

这些信号不会被视为绝对证据，而是按数量计算。

不同页面类型要求的最少软命中数：

- `search`: 2
- `detail`: 1
- `review`: 1
- `unknown`: 2

---

## 7. 页面类型感知逻辑

Detector 会按下面顺序解析页面意图：

1. `context.page_pattern`
2. `context.goal`
3. fallback 到 `unknown`

目标回退映射：

- `search` -> search
- `detail` -> detail
- `reviews` -> review

这样即使 URL pattern matcher 暂时无法识别，也还能借助任务意图得到更稳的判断。

---

## 8. 弱信号逻辑

弱信号不会像强信号那样直接判死。

### 8.1 弱 Cloudflare 信号

- `cloudflare`

### 8.2 弱 CAPTCHA 信号

- `recaptcha`
- `hcaptcha`

### 8.3 弱 bot 信号

- `access denied`
- `suspicious activity`
- `please verify`

这些信号只有结合以下条件，才可能触发 block：

- 页面是否过薄
- 是否缺少最小页面结构
- 是否缺少成功页信号
- 是否缺少 semantic confirmation

如果 semantic confirmation 足够强，则弱信号不会触发 block。

---

## 9. 空响应判断

Detector 已不再因为“页面短”就直接判死。

### 9.1 当前空响应判断条件

通常要满足以下条件才可能被判为空响应：

- `status_code == 200`
- 不命中 `costway.com` 特例放行
- 不命中成功页信号
- 不存在足够强的 semantic confirmation

然后再结合页面类型使用不同最小阈值：

- `search`: 400
- `detail`: 220
- `review`: 260
- `unknown`: 300

额外规则：

- 如果页面长度 < 5000 且缺少最小页面结构，也会判为 `empty_response`

### 9.2 最小页面结构信号

示例：

- `<html`
- `<body`
- `<main`
- `<div`
- `<script`
- `id="app"`
- `data-reactroot`
- `__next_data__`
- `application/ld+json`

这套规则用于保护：

- 很薄但合法的 app shell
- 很薄但合法的商品页
- 很薄但合法的评论页

---

## 10. AXTree 语义确认

### 10.1 设计目标

AXTree 不是主 block detector。它的作用是：

## **作为辅助语义确认层，专门降低弱信号误判**

### 10.2 当前来源

当前 semantic confirmation 来自：

- `AXTreeExtraction.build_semantic_confirmation(...)`

定义位置：

- `src/ai_crawler/core/extraction/extraction.py`

### 10.3 当前输出结构

semantic confirmation 当前可能包含：

- `kind`: `search` / `detail` / `review`
- `confidence`
- `entity_count`
- `has_price`
- `has_rating`

### 10.4 当前在 detector 中的作用

当前它可以帮助放行：

- 弱 Cloudflare 信号
- 弱 CAPTCHA 信号
- 弱 bot 信号
- `empty_response` 可疑页

当前它不会覆盖：

- `403`
- `429`
- `451`
- 强 Cloudflare challenge
- 强 CAPTCHA challenge
- 强 bot 文案

这是刻意设计的。

---

## 11. AXTree 语义确认当前判定规则

### Search 页确认

如果满足：

- `kind == search`
- `confidence >= 0.65`
- `entity_count >= 2`

则可作为有效 search 语义确认。

### Detail 页确认

如果满足：

- `kind == detail`
- `confidence >= 0.55`
- 且 `has_price` 或 `has_rating` 为真

则可作为有效 detail 语义确认。

### Review 页确认

如果满足：

- `kind == review`
- `confidence >= 0.55`
- `entity_count >= 1`

则可作为有效 review 语义确认。

### Unknown 页确认

如果 `page_pattern` 不明确，则要求：

- `confidence >= 0.8`

才认为语义确认足够强。

---

## 12. semantic_confirmation 的构造方式

### 12.1 正常抓取路径

在：

- `src/ai_crawler/core/runtime/execution.py`

中，`TaskExecutionEngine._build_detection_context(...)` 会在有 live `page` 时自动构造：

- `semantic_confirmation=build_axtree_semantic_confirmation(...)`

### 12.2 Captcha 重试路径

在：

- `src/ai_crawler/core/runtime/processing.py`

里，captcha solve 后的二次抓取也会重新生成 semantic confirmation。

---

## 13. 尝试历史记录

`AntiBotHandler.record_attempt(...)` 会记录每个 URL 的尝试历史，包括：

- proxy
- render
- delay_after
- use_cookies
- change_ua
- use_human_scroll
- block_type
- blocked

最多保留最近 20 条。

用途：

- 调试
- 策略分析
- 后续自适应决策

---

## 14. block 判断的下游影响

一旦 `is_blocked(...)` 返回 blocked：

1. 尝试历史会被记录
2. runtime 可能触发：
   - 代理轮换
   - captcha 求解
   - 失败处理
   - 策略升级
3. trace / runtime result 会记录这次 block 结果

相关文件：

- `src/ai_crawler/core/runtime/execution.py`
- `src/ai_crawler/core/runtime/processing.py`
- `src/ai_crawler/core/runtime/outcomes.py`

因此 false positive 的代价很高：

- 浪费浏览器时间
- 触发不必要重试
- 触发不必要升级
- 污染 trace 统计

---

## 15. 当前测试覆盖

主测试文件：

- `tests/runtime/test_block_detector.py`

目前已覆盖：

- 硬 HTTP block
- 强 CAPTCHA / Cloudflare / bot 信号
- 空响应判断
- 薄但合法的商品页
- 带 `recaptcha` / `cloudflare` 弱词的合法页
- 页面类型感知的 search/detail/review 行为
- semantic confirmation 对弱信号的放行
- semantic confirmation **不会压过强 CAPTCHA**

---

## 16. 当前逻辑的一句话总结

当前 detector 可以理解成四层：

### 第一层：硬 block 层

优先级最高，快且保守。

### 第二层：成功页识别层

尽量让明显合法的电商页直接通过。

### 第三层：弱信号怀疑层

对弱词做谨慎判断，避免过度误杀。

### 第四层：AXTree 语义确认层

用浏览器语义结构进一步压低弱信号误判。

---

## 17. 维护建议

如果未来要修改 block 逻辑，请一起更新这些位置：

1. `src/ai_crawler/core/runtime/handler.py`
2. `src/ai_crawler/core/runtime/execution.py`
3. `src/ai_crawler/core/runtime/processing.py`
4. `src/ai_crawler/core/extraction/extraction.py`（如果 semantic confirmation 变化）
5. `tests/runtime/test_block_detector.py`
6. 本文档

这份文档应被视为当前 block 检测逻辑的正式参考。 
