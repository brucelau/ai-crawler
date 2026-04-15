# Tier 系统参考文档

> 状态：已与当前 `gpt` 分支实现对齐。
>
> 适用范围：Tier 升级策略、各层反爬能力、默认起始 Tier、性能优化边界。
>
> Tier 配置的代码真相来源：
>
> - `src/ai_crawler/core/strategy.py`（`TIER_CONFIGS`、`SITE_TIER_DEFAULTS`、`URL_PATTERNS`）
> - `src/ai_crawler/browser/fetching.py`
> - `src/ai_crawler/core/runtime/*`
>
> 相关文档：
>
> - `docs/ARCHITECTURE.md`
> - `docs/BLOCK_DETECTOR.md`
> - `docs/LLM_SYSTEM.md`

---

## 1. 文档目的

Tier 系统是整个爬虫运行时的**反爬升级框架**。

它的核心目标是平衡四件事：

1. **速度**：尽量先用更轻、更快的路径
2. **生存能力**：遇到反爬后逐级升级
3. **成本**：只在必要时进入更昂贵的浏览器层
4. **提取质量**：在需要时保留足够的浏览器上下文，支持 `js_eval`、`axtree` 和后续回退提取

当前架构已经是：

## **浏览器优先运行时 + Scrapy 辅助适配层**

Scrapy 不再负责 Tier 决策本身。

---

## 2. Tier 总表

| Tier | 渲染引擎 | 代理 | 延迟 | Human Scroll | 换 UA | Cookies | 主要反爬策略 | 可用提取能力 | 典型适用场景 | 典型升级触发 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `NONE`（`curl_cffi`） | `THORDATA_DEDICATED` | 2-5s | 否 | 否 | 否 | 低成本 HTTP 试探，利用 TLS/JA3 风格浏览器伪装 | `json_ld`、HTML、`bs_css` | 静态页、SSR 页、结构化数据丰富页 | challenge / 403 / 429 / 空页 / 需要 JS |
| 2 | `CLOUDSCRAPER` | `THORDATA_DEDICATED` | 3-6s | 否 | 否 | 是 | 轻量 Cloudflare / challenge 绕过 + Cookie 持续化 | HTML、`json_ld`、`bs_css` | 简单挑战页、轻量防护页 | HTML 不完整、挑战未过、提取失败 |
| 3 | `LIGHTPAND` | `THORDATA_DEDICATED` | 2-5s | 是 | 否 | 否 | 轻量浏览器，亚 100ms 启动，执行 JS | `js_eval`、`axtree`、`bs_css` | 中等反爬强度、需要 JS 渲染的页面 | 指纹检测、简单 challenge、需要 JS 执行 |
| 4 | `PLAYWRIGHT` | `THORDATA_DEDICATED` | 3-8s | 是 | 否 | 否 | 真实 Chromium、执行 JS、隐藏 webdriver | `js_eval`、`axtree`、`bs_css` | 需要真实浏览器的 JS 页 | 指纹检测、captcha、bot_detected、持续 challenge |
| 5 | `CAMOUFOX` | `THORDATA_DEDICATED` | 3-8s | 是 | 是 | 是 | 指纹感知 Firefox 路径，强化浏览器身份伪装 | 浏览器内提取、可能使用 `axtree` | 指纹敏感站点 | 持续被识别、captcha、会话污染 |
| 6 | `CLOUDERA` / `cloudflare_uc` | `THORDATA_DEDICATED` | 5-10s | 是 | 是 | 是 | 针对 Chromium/challenge 场景的 UC 路线 | 浏览器内提取 | 更强的 Cloudflare / Chromium 型挑战 | 持续 challenge、浏览器不稳定 |
| 7 | `SELENIUMBASE` | `THORDATA_DEDICATED` | 5-10s | 是 | 是 | 是 | 更重型 stealth 自动化路径 | 浏览器内提取 | 交互复杂、兼容性要求高的页面 | 依旧被封、提取不稳定 |
| 8 | `CLOAKBROWSER` | `THORDATA_DEDICATED` | 5-10s | 是 | 是 | 是 | 高拟真补丁 Chromium 路径 | `js_eval`、`axtree`、`bs_css` | 高强度反爬、需要真实 Chromium 行为 | 深层浏览器指纹检测仍命中 |
| 9 | `KAMELEO` | `THORDATA_DEDICATED` | 8-15s | 是 | 是 | 是 | 指纹浏览器最终兜底层 | 浏览器内提取 | 最后一级高成本身份浏览器 | 通常已是末级，只能终止或人工分析 |

---

## 3. 每一层的策略说明

### Tier 1：快速 HTTP 试探层

**目标**

- 用最低成本判断页面能否直接拿下
- 在不进入真实浏览器的情况下尽可能完成抓取

**当前能力**

- ThorData 代理
- `curl_cffi` HTTP impersonation
- 低成本随机延迟

**这一层不会做的事**

- 不启真实浏览器
- 不做人类滚动
- 不保留 Cookie 连续性
- 不做显式 UA 旋转

**最适合**

- JSON-LD 丰富的商品详情页
- SSR 页面
- 低风控详情页

---

### Tier 2：轻量反挑战层

**目标**

- 用比真实浏览器更便宜的方式处理简单 challenge

**当前能力**

- ThorData 代理
- `cloudscraper`
- Cookie 连续性
- 面向 challenge 的 HTTP 客户端行为

**最适合**

- 需要 challenge Cookie 但不需要真实浏览器的页面

---

### Tier 3：轻量浏览器层（Lightpanda）

**目标**

- 在 Playwright 的完整浏览器成本之前，提供一个轻量但支持 JS 渲染的选项
- 亚 100ms 冷启动，远快于 Playwright

**当前能力**

- Lightpanda（Zig 构建的 AI 专用浏览器）
- V8 JavaScript 执行
- Chrome DevTools Protocol（CDP）兼容
- human scroll
- 活跃 page 对象可用于后续提取

**提取优势**

这是第一层完整支持以下提取路径的 Tier：

- `js_eval`
- `axtree`
- 浏览器上下文回退提取

**当前性能优化**

- 单进程、多线程架构
- 极低内存占用（约 Playwright 的 1/10）
- 100ms 以内冷启动

---

### Tier 4：第一层真实浏览器（Playwright）

**目标**

- 只有在低层不够时才进入真实浏览器

**当前能力**

- 真实 Chromium
- webdriver 抑制
- human scroll
- 活跃 page 对象可用于后续提取

**提取优势**

这是第一层完整支持以下提取路径的 Tier：

- `js_eval`
- `axtree`
- 浏览器上下文回退提取

**当前性能优化**

- Playwright runtime 池化
- browser 池化
- context 池化
- 仅广告脚本拦截
- fetcher 复用/拦截指标

---

### Tier 5：指纹感知浏览器层

**目标**

- 从“真实浏览器”升级到“更强浏览器身份塑形”

**当前能力**

- Camoufox
- UA 旋转
- Cookie 连续性
- human behavior
- 浏览器级指纹伪装/随机化

**当前性能优化**

- Camoufox browser 池化
- 仅广告脚本拦截
- fetcher 观测指标

**最适合**

- 明显会看浏览器指纹的网站

---

### Tier 6：UC / Chromium Challenge 专项层

**目标**

- 使用更偏向 Chromium challenge 处理的浏览器路径

**当前能力**

- undetected-chromedriver 路线
- 浏览器执行
- UA 旋转
- Cookie
- human behavior

**当前复用策略**

- 小型 UC 预热池
- 按站点 + 代理 + 启动签名复用
- 复用前健康检查
- 使用后 reset / 淘汰

**最适合**

- 更强的 Cloudflare / Chromium 型 challenge 环境

---

### Tier 7：重型 stealth 自动化层

**目标**

- 处理更复杂、更依赖兼容性的浏览器流程

**当前能力**

- SeleniumBase stealth 路径
- 浏览器执行
- UA 旋转
- Cookie
- human behavior

**最适合**

- 页面交互复杂、需要更高兼容性的场景

---

### Tier 8：高拟真 Chromium 层

**目标**

- 当普通浏览器 stealth 仍不够时，使用更拟真的 Chromium 路径

**当前能力**

- CloakBrowser
- 更真实的浏览器行为
- UA 旋转
- Cookie
- human behavior

**当前性能优化**

- CloakBrowser pooling
- 仅广告脚本拦截
- fetcher 观测指标

**提取优势**

和 Tier 4 一样，这一层也明确支持：

- `js_eval`
- `axtree`
- 浏览器上下文回退提取

---

### Tier 9：指纹浏览器最终层

**目标**

- 用最高成本换取最强身份模拟能力

**当前能力**

- Kameleo profile 型指纹浏览器能力
- UA/Profile 旋转
- Cookie
- human behavior

**最适合**

- 所有较低成本路径都失败后的最终兜底

---

## 4. 各 Tier 的提取能力

| Tier | 可用 `json_ld` | 可用 `js_eval` | 可用 `axtree` | 可用 `bs_css` | 说明 |
|---|---|---|---|---|---|
| 1 | 是 | 否 | 否 | 是 | 纯 HTML 路径 |
| 2 | 是 | 否 | 否 | 是 | challenge-oriented HTTP |
| 3 | 是 | 是 | 是 | 是 | Lightpanda 轻量浏览器 |
| 4 | 是 | 是 | 是 | 是 | Playwright 完整浏览器 |
| 5 | 是 | 是* | 是* | 是 | 取决于活跃 page 是否可用 |
| 6 | 是 | 是* | 是* | 是 | 依赖 wrapper/runtime 具体路径 |
| 7 | 是 | 是* | 是* | 是 | 依赖 wrapper/runtime 具体路径 |
| 8 | 是 | 是 | 是 | 是 | 明确有活 page 支撑 |
| 9 | 是 | 是* | 是* | 是 | 依赖具体实现 |

> `*` 表示在原理上支持，但要取决于该 wrapper 路径是否真正保留了可用 page / 浏览器上下文。

---

## 5. 当前升级哲学

### 5.1 低层追求效率

Tier 1-4 的核心问题是：

> 这页能不能便宜地拿下？

所以它们允许更快失败、更快升级。

### 5.2 高层追求真实性

Tier 5+ 的核心问题是：

> 需要多少浏览器真实性，才能活过反爬？

所以这些层级更偏向：

- 身份连续性
- Cookie
- 指纹稳定性
- 浏览器行为真实性

---

## 附表 A：各 Tier 当前实现状态

| Tier | 是否真实浏览器 | 是否已做池化 | 是否已做广告脚本拦截 | AXTree 当前是否实际可用 | 是否已有 fetcher 指标 | 说明 |
|---|---|---|---|---|---|---|
| 1 | 否 | 不适用 | 否 | 否 | 否 | 纯 HTTP |
| 2 | 否 | 不适用 | 否 | 否 | 否 | challenge-oriented HTTP |
| 3 | 是（Lightpanda） | 暂未池化 | 否 | **是** | 否 | 轻量浏览器，亚 100ms 启动，需集成 CDP |
| 4 | 是（Playwright） | **是** | **是** | **是** | **是** | 当前性价比最高的浏览器层 |
| 5 | 是（Camoufox） | **是** | **是** | 部分可用 / 取决于 page | **是** | 已纳入 fetcher 管理复用 |
| 6 | 是（UC） | **小型预热池** | 否 | 部分可用 / 取决于 page | **是** | 谨慎复用，带健康检查 |
| 7 | 是（SeleniumBase） | 暂未池化 | 否 | 部分可用 / 取决于 page | 否 | 当前已拆生命周期边界，为后续池化做准备 |
| 8 | 是（CloakBrowser） | **是** | **是** | **是** | **是** | 高拟真 Chromium 已接入池化 |
| 9 | 是（Kameleo） | 否 | 否 | 部分可用 / 取决于 page | 否 | 当前不做池化 |

---

## 附表 B：各站点 / 页面类型默认起始 Tier

本表对应 `src/ai_crawler/core/strategy.py` 中的 `SITE_TIER_DEFAULTS`。

| 站点 | Search | Detail | Review |
|---|---:|---:|---:|
| amazon | 7 | 4 | 4 |
| walmart | 7 | 4 | - |
| target | 7 | 3 | - |
| ebay | 7 | 3 | - |
| menards | 7 | 4 | - |
| lowes | 7 | 3 | - |
| homedepot | 7 | 3 | - |
| acehardware | 7 | 3 | - |
| wayfair | 7 | 3 | - |
| michaels | 7 | 3 | - |
| temu | 7 | 1 | - |
| etsy | 7 | 3 | - |
| bestbuy | 7 | 3 | - |
| costco | 7 | 3 | - |
| qvc | 7 | 3 | - |
| kohls | 7 | 3 | - |
| mercadolibre | 7 | 3 | - |
| walmartmexico | 7 | 3 | - |
| intexcorp | 7 | 3 | - |
| meijer | 7 | 3 | - |
| fivebelow | 7 | 1 | - |
| samsclub | 7 | 3 | - |
| bunnings | 7 | 3 | - |
| dollargeneral | 7 | 1 | - |
| action | 7 | 1 | - |
| academy | 7 | 3 | - |
| wowsports | 7 | 1 | - |
| coppel | 7 | 3 | - |
| aosom | 7 | 1 | - |
| familydollar | 7 | 1 | - |
| costway | 7 | 1 | - |

### 说明

- 几乎所有站点的 search 页当前默认都是 **Tier 7** 起步
- detail 页根据各站点预估摩擦程度落在 **Tier 1 / 3 / 4**
- review 页目前在默认配置中主要只明确到了 Amazon

---

## 附表 C：Tier 1-4 的性能优化边界

### 当前策略

Tier 1-4 可以更偏向效率，因为这些层级本来就是"便宜尝试、失败升级"。

### 允许做的优化

- 拦截明显第三方广告脚本
- 拦截明显第三方追踪脚本
- 在安全前提下做浏览器/运行时复用

### 当前明确不默认做的优化

- 不默认拦截图片
- 不默认拦截视频
- 不默认拦截字体
- 不默认拦截站点主域业务脚本

### Tier 5+ 的原则

Tier 5 及以上优先真实性，所以：

- 不宜激进裁剪资源
- 更重视 Cookie / 身份 / 指纹 / 行为一致性

### 当前代码现状

目前"仅广告脚本拦截"已明确落在以下浏览器 fetch 路径：

- Tier 4（Playwright）
- Tier 5（Camoufox）
- Tier 8（CloakBrowser）

Tier 6（UC）当前主要先做了小型预热池和健康检查，还没把广告脚本拦截推进到同等程度。

---

## 附表 D：实战决策表

| 场景 | 建议起始 Tier |
|---|---:|
| 静态 / SSR / JSON-LD 丰富详情页 | 1 |
| 简单 challenge 页 | 2 |
| 中等反爬、需要 JS 渲染 | 3 |
| 需要真实浏览器渲染的 JS 页 | 4 |
| 指纹敏感浏览器页 | 5 |
| 更强 Cloudflare / Chromium challenge | 6 |
| 更复杂 stealth / 兼容性要求 | 7 |
| 需要高拟真 Chromium 行为 | 8 |
| 最终高成本指纹浏览器兜底 | 9 |

---

## 6. 维护建议

未来如果 Tier 行为变化，请一起更新这些位置：

1. `src/ai_crawler/core/strategy.py`
2. `src/ai_crawler/browser/fetching.py`
3. `src/ai_crawler/core/runtime/*`
4. 本文档 `docs/TIER_SYSTEM.md`

这是一份**架构文档**，不是说明性宣传文档。代码变了，这里就必须一起变。 
