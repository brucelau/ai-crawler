# Anti-Bot Fingerprinter 参考文档

> 状态：已与当前 `gpt` 分支实现对齐。
>
> 适用范围：反爬供应商推断、反爬机制推断、fingerprinter 与 trace / policy engine 的关系。
>
> 相关文档：
>
> - `docs/ARCHITECTURE.md`
> - `docs/BLOCK_DETECTOR.md`
> - `docs/TIER_SYSTEM.md`
> - `docs/VERIFICATION.md`

---

## 1. 文档目的

Anti-Bot Fingerprinter 的职责不是直接决定页面是否被拦截，而是：

## **在 BlockDetector 已完成主判定之后，对失败页面做“反爬供应商 / 机制”的高概率推断**

它的目标是给系统补充：

- 更细粒度的反爬上下文
- 可聚合的供应商/机制统计
- 可用于策略排序的次级信号

---

## 2. 设计定位

当前系统中：

- **BlockDetector** 负责主判定：
  - blocked / not blocked
  - block_type

- **Anti-Bot Fingerprinter** 负责次级推断：
  - vendor
  - mechanism
  - confidence
  - evidence

所以它不是主裁判，而是：

## **主判定后的语义标签器（diagnostic labeler）**

---

## 3. 当前代码位置

### 核心实现
- `src/ai_crawler/core/engine/fingerprinter.py`

### 运行时接入
- `src/ai_crawler/core/engine/execution.py`

### Trace 接入
- `src/ai_crawler/core/engine/outcomes.py`
- `src/ai_crawler/core/engine/trace_store.py`

### Runtime 结果接入
- `src/ai_crawler/core/engine/results.py`
- `src/ai_crawler/api/models.py`

### Policy Engine 聚合接入
- `src/ai_crawler/core/engine/policy_engine.py`

---

## 4. 输出结构

当前输出结构是：

```python
{
  "vendor": "cloudflare|datadome|akamai|imperva|browser_error|unknown",
  "mechanisms": [
    "js_challenge",
    "captcha_gate",
    "bot_score_gate",
    "http_status_block",
    "proxy_transport_error",
    "browser_transport_error",
    "empty_shell_or_soft_block",
    "edge_waf"
  ],
  "confidence": 0.0,
  "evidence": ["..."],
  "recommended_response": "..."
}
```

---

## 5. 各字段含义

### 5.1 `vendor`

表示更可能命中的反爬供应商或来源。

常见值：

- `cloudflare`
- `datadome`
- `akamai`
- `imperva`
- `browser_error`
- `unknown`

> 其中 `browser_error` 不是 WAF 供应商，而是“浏览器/代理传输错误”类来源的专门标签。

---

### 5.2 `mechanisms`

表示更可能发生的主要机制。

当前使用的机制标签包括：

- `js_challenge`
- `captcha_gate`
- `bot_score_gate`
- `http_status_block`
- `proxy_transport_error`
- `browser_transport_error`
- `empty_shell_or_soft_block`
- `edge_waf`

这些标签允许后续：

- 做统计
- 做策略降权
- 做人工调试判断

---

### 5.3 `confidence`

表示推断置信度，范围：

- `0.0 ~ 1.0`

它不是数学意义上的概率，而是一个工程上的相对可信度。

---

### 5.4 `evidence`

表示触发这个推断的证据片段。

例如：

- `waf_detected:cloudflare`
- `status:403`
- `pattern:captcha`
- `browser_error:proxy`

这些证据主要用于：

- trace 复盘
- 调试
- 策略解释

---

### 5.5 `recommended_response`

表示 fingerprinter 给出的建议响应方向。

例如：

- `prefer_real_browser_with_cookies_and_human_behavior`
- `increase_browser_realism_or_use_captcha_solver`
- `rotate_identity_and_raise_browser_realism`
- `fix_browser_or_proxy_path_before_escalating`
- `retry_with_richer_render_or_semantic_confirmation`
- `observe_and_rank_with_policy_engine`

> 注意：这只是建议，不是强制执行器。真正的调度和策略升级仍然由 runtime / policy engine 决定。

---

## 6. 当前判定依据

Fingerprinter 当前使用这些输入：

- `html`
- `headers`
- `status_code`
- `block_type`
- `waf_detected`
- `block_reason`

也就是说，它是建立在：

1. Detector 已经做完初判
2. Telemetry 已经提取出 headers / waf / reason

之后再运行的。

---

## 7. 当前可识别的主要模式

### 7.1 Cloudflare Challenge

典型触发依据：

- `waf_detected = cloudflare`
- `cf-challenge`
- `checking your browser`

典型输出：

- `vendor = cloudflare`
- `mechanisms` 包含 `js_challenge`

---

### 7.2 CAPTCHA Gate

典型触发依据：

- `block_type = captcha`
- 页面中存在 captcha 强信号

典型输出：

- `mechanisms` 包含 `captcha_gate`

---

### 7.3 Bot Score Gate

典型触发依据：

- `block_type = bot_detected`
- 页面里出现 automated requests / unusual traffic 等信号

典型输出：

- `mechanisms` 包含 `bot_score_gate`

---

### 7.4 代理传输错误

典型触发依据：

- `ERR_NO_SUPPORTED_PROXIES`
- `proxy error`

典型输出：

- `vendor = browser_error`
- `mechanisms` 包含 `proxy_transport_error`

---

### 7.5 浏览器传输错误

典型触发依据：

- `This site can't be reached`
- `chrome-error://`

典型输出：

- `vendor = browser_error`
- `mechanisms` 包含 `browser_transport_error`

---

### 7.6 Empty Shell / Soft Block

典型触发依据：

- `block_type = empty_response`

典型输出：

- `mechanisms` 包含 `empty_shell_or_soft_block`

---

## 8. 当前运行时接入方式

### 8.1 运行位置

当前在：

- `FetchEngineer.execute()`

里运行。

也就是说顺序是：

```text
fetch
 -> detector / block_type
 -> telemetry (waf / headers / reason)
 -> fingerprinter
 -> trace / runtime result / policy stats
```

这是当前最安全的位置，因为这里已经有：

- 原始 HTML
- 响应头
- 状态码
- 主判定结果

---

## 9. 当前 trace 接入方式

`Attempt` 现在会携带：

- `anti_bot_fingerprint`

然后：

- `TraceRecorder.failure_trace_kwargs(...)`
- `TraceRecorder.record_success(...)`

都会把它写入 trace。

最终 `AntiBotTrace` 中也会保存：

- `anti_bot_fingerprint`

---

## 10. 当前运行结果接入方式

`CrawlResult` 当前已经支持：

- `anti_bot_fingerprint`

`RuntimeTaskResult.artifacts` 中也会暴露：

- `anti_bot_fingerprint`

这样可以在最终任务结果层直接看到推断结果，而不必只去 trace 文件里翻。

---

## 11. 当前 Policy Engine 接入方式

Fingerprinter 当前并没有抢占 `block_type` 的主导权。

当前策略是：

### 主信号
- `block_type`

### 次级信号
- `vendor`
- `mechanisms`

具体来说：

`PolicyStatsStore` 已经会聚合：

- `anti_bot_vendors`
- `anti_bot_mechanisms`

`PolicyEngine` 现在也会把这些统计当成：

- **次级惩罚项**

例如：

- `browser_error`
- `proxy_transport_error`
- `browser_transport_error`
- `js_challenge`
- `captcha_gate`
- `bot_score_gate`

都会在已有统计基础上让某些策略被进一步降权。

---

## 12. 当前设计原则

Fingerprinter 的设计原则非常明确：

### 12.1 不替代 BlockDetector

它不负责：

- blocked / not blocked 的主判定

### 12.2 不直接决定策略

它不直接做：

- 立刻跳 Tier
- 立刻换浏览器
- 立刻换代理

### 12.3 只做“更细语义标签”

它的职责是：

- 标注更像哪家反爬
- 标注更像哪种机制
- 给 trace / policy / 人工调试提供更多上下文

---

## 13. 当前测试覆盖

主要测试文件：

- `tests/runtime/test_fingerprinter.py`
- `tests/runtime/test_outcomes.py`
- `tests/runtime/test_orchestrator.py`
- `tests/runtime/test_policy_engine.py`

当前已覆盖：

- Cloudflare challenge 推断
- proxy transport error 推断
- captcha gate 推断
- bot score gate 推断
- trace 中写入 `anti_bot_fingerprint`
- runtime result artifacts 中暴露 `anti_bot_fingerprint`
- Policy Engine 对 fingerprinter 次级惩罚的使用

---

## 14. 当前最值得看的输出

如果你要观察 fingerprinter 是否工作，最有价值的是：

### trace
- `anti_bot_fingerprint.vendor`
- `anti_bot_fingerprint.mechanisms`
- `anti_bot_fingerprint.confidence`
- `anti_bot_fingerprint.evidence`

### runtime result artifacts
- `anti_bot_fingerprint`

### policy stats
- `anti_bot_vendors`
- `anti_bot_mechanisms`

---

## 15. 一句话总结

当前 Anti-Bot Fingerprinter 可以理解成：

## **BlockDetector 之后、Policy Engine 之前的反爬语义标签层**

它已经做到：

- 能推断大概率供应商与机制
- 能沉淀进 trace 和 runtime result
- 能被 policy stats 聚合
- 能作为策略排序的次级惩罚依据

但它仍然遵守一个核心边界：

## **block_type 是主信号，fingerprinter 只是辅助信号。**

---

## 16. 维护建议

如果未来修改 fingerprinter 逻辑，请同步更新这些位置：

1. `src/ai_crawler/core/engine/fingerprinter.py`
2. `src/ai_crawler/core/engine/execution.py`
3. `src/ai_crawler/core/engine/outcomes.py`
4. `src/ai_crawler/core/engine/trace_store.py`
5. `src/ai_crawler/core/engine/policy_engine.py`
6. `tests/runtime/test_fingerprinter.py`
7. 本文档

这份文档应被视为当前反爬指纹推断逻辑的正式参考。 
