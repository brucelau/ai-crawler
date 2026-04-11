# Tier 系统详解文档

> 本文档详细说明 ai-crawler 的 8 层爬取策略（Tier 1-8），包括每层的实现原理、代理使用、鼠标轨迹、指纹生成、反反爬策略等。

## 1. Tier 系统概览

### 1.1 层级配置总表

| Tier | 渲染引擎 | 代理 | 人类滚动 | 更换 UA | 使用 Cookie | 延迟 (秒) | 适用场景 |
|------|----------|------|----------|---------|-------------|------------|----------|
| 1 | NONE (curl_cffi) | THORDATA_DEDICATED | ❌ | ❌ | ❌ | 2-5 | 无反爬网站 |
| 2 | CLOUDSCRAPER | THORDATA_DEDICATED | ❌ | ❌ | ✅ | 3-6 | 简单 Cloudflare |
| 3 | PLAYWRIGHT | THORDATA_DEDICATED | ✅ | ❌ | ❌ | 3-8 | JS 渲染页面 |
| 4 | CAMOUFOX | THORDATA_DEDICATED | ✅ | ✅ | ✅ | 3-8 | 指纹感知 |
| 5 | CLOUDERA (undetected-chromedriver) | THORDATA_DEDICATED | ✅ | ✅ | ✅ | 5-10 | Cloudflare 专家 |
| 6 | SELENIUMBASE | THORDATA_DEDICATED | ✅ | ✅ | ✅ | 5-10 | 最大隐身 |
| 7 | CLOAKBROWSER | THORDATA_DEDICATED | ✅ | ✅ | ✅ | 5-10 | C++ 补丁浏览器 |
| 8 | KAMELEO | THORDATA_DEDICATED | ✅ | ✅ | ✅ | 8-15 | 指纹浏览器 |

### 1.2 代理配置

所有层级统一使用 **ThorData 专用代理**：

```python
ProxyType.THORDATA_DEDICATED
```

代理配置（从环境变量读取）：
- **Host**: `pr.thordata.net`（可通过 `THORDATA_PROXY_HOST` 修改）
- **Port**: `9999`（可通过 `THORDATA_PROXY_PORT` 修改）
- **Username**: 从 `THORDATA_RESIDENTIAL_USERNAME` 读取
- **Password**: 从 `THORDATA_RESIDENTIAL_PASSWORD` 读取
- **Session**: Sticky (固定 IP 一段时间)

---

## 2. Tier 1 - curl_cffi (纯 HTTP)

### 2.1 实现原理

使用 `curl_cffi` 库进行 HTTP 请求，模拟不同浏览器的 TLS/Ja3 指纹。

```
Scrapy 请求 → curl_cffi → ThorData 代理 → 目标网站
```

### 2.2 核心技术

**curl_cffi** 是 curl 的 Python 封装，支持：
- TLS 指纹模拟（可伪装成 Chrome、Firefox、Safari 等）
- HTTP/2 支持
- 保持会话

### 2.3 指纹生成

| 指纹类型 | 实现方式 |
|----------|----------|
| TLS 指纹 | curl_cffi 内置模拟 |
| JA3 指纹 | curl_cffi 自动处理 |
| HTTP Headers | 基础 Headers |

### 2.4 反反爬策略

| 策略 | 说明 |
|------|------|
| 代理轮换 | ThorData 住宅代理 |
| 延迟 | 2-5 秒随机延迟 |
| Cookie | ❌ 不使用 |

### 2.5 代码位置

- 渲染逻辑: `middlewares/tier_strategy.py` → `_render_none()`

---

## 3. Tier 2 - cloudscraper (Cloudflare 绕过)

### 3.1 实现原理

使用 `cloudscraper` 库自动解决 Cloudflare 的 JavaScript 挑战。

```
请求 → cloudscraper → ThorData 代理 → 目标网站
```

### 3.2 核心技术

**cloudscraper** 可以：
- 检测 Cloudflare 挑战
- 执行 JavaScript 求解
- 保持 Challenge Cookie
- 支持 Cookie 重用

### 3.3 指纹生成

| 指纹类型 | 实现方式 |
|----------|----------|
| TLS 指纹 | cloudscraper 内置 |
| JavaScript 挑战 | cloudscraper 自动求解 |
| Browser Emulation | cloudscraper 自动处理 |

### 3.4 反反爬策略

| 策略 | 说明 |
|------|------|
| 代理轮换 | ThorData 住宅代理 |
| 延迟 | 3-6 秒随机延迟 |
| Cookie | ✅ 保持会话 |

### 3.5 代码位置

- 渲染逻辑: `middlewares/tier_strategy.py` → `_render_cloudscraper()`

---

## 4. Tier 3 - Playwright (完整浏览器)

### 4.1 实现原理

使用 Microsoft Playwright 启动真实 Chromium 浏览器渲染页面。

```
请求 → Playwright Chromium → ThorData 代理 → 目标网站
```

### 4.2 核心技术

**Playwright** 提供：
- 完整浏览器环境
- Chromium/WebKit/Firefox 支持
- 自动化控制
- 截图、PDF 等功能

### 4.3 指纹生成

| 指纹类型 | 实现方式 |
|----------|----------|
| WebDriver | 隐藏 (`--disable-blink-features=AutomationControlled`) |
| Navigator | 默认浏览器指纹 |
| SSL/TLS | 真实浏览器指纹 |

### 4.4 人类滚动 ✅

使用 **UnifiedHumanBehavior** + **Bezier 曲线**：

```python
# human_mouse.py
behavior = UnifiedHumanBehavior(adapter)
behavior.human_scroll(0, 1500)  # 0 → 1500px
```

滚动特征：
- **速度**: 中等 (120px/step)
- **轨迹**: 三次贝塞尔曲线
- **暂停**: 随机 0.05-0.15 秒

### 4.5 反反爬策略

| 策略 | 说明 |
|------|------|
| 代理轮换 | ThorData 住宅代理 |
| 延迟 | 3-8 秒随机延迟 |
| 人类滚动 | ✅ 启用 |
| Cookie | ❌ 不使用 |

### 4.6 代码位置

- Wrapper: 使用 Playwright 直调
- 人类滚动: `browser/human_mouse.py` → `PlaywrightMouseAdapter`

---

## 5. Tier 4 - Camoufox (指纹感知 Firefox)

### 5.1 实现原理

使用 **Camoufox** - 一个专门反检测的 Firefox 浏览器。

```
请求 → Camoufox (Firefox) → ThorData 代理 → 目标网站
```

### 5.2 核心技术

**Camoufox** 提供：
- 内置指纹 spoofing
- 自动随机化 WebGL、Canvas、Audio
- 人类鼠标移动
- Headless 模式

### 5.3 指纹生成

| 指纹类型 | 实现方式 |
|----------|----------|
| User-Agent | 随机真实 UA |
| WebGL | Camoufox 内置随机化 |
| Canvas | Camoufox 内置随机化 |
| Audio | Camoufox 内置随机化 |
| Navigator | Camoufox 内置随机化 |
| Screen | Camoufox 内置随机化 |

### 5.4 人类滚动 ✅

使用 **HumanMouseController**：

```python
mouse = HumanMouseController(page)
for y in range(0, 1500, random.randint(100, 200)):
    mouse.move_to(random.randint(200, 800), y)
    time.sleep(random.uniform(0.05, 0.15))
```

滚动特征：
- **鼠标曲线**: 真实贝塞尔曲线
- **速度**: 可变 (fast/medium/slow)
- **暂停**: 随机 0.05-0.15 秒

### 5.5 反反爬策略

| 策略 | 说明 |
|------|------|
| 代理轮换 | ThorData 住宅代理 |
| 延迟 | 3-8 秒随机延迟 |
| 人类滚动 | ✅ 启用 |
| 更换 UA | ✅ 启用 |
| Cookie | ✅ 保持 |

### 5.6 代码位置

- Wrapper: `browser/camoufox_wrapper.py` → `CamoufoxWrapper`
- 指纹配置: `browser/camoufox_wrapper.py` → `FingerprintConfig`

---

## 6. Tier 5 - CLOUDERA (Cloudflare 专家)

### 6.1 实现原理

使用 **undetected-chromedriver** (CLOUDERA) - 修改版 ChromeDriver。

```
请求 → undetected_chromedriver Chrome → ThorData 代理 → 目标网站
```

### 6.2 核心技术

**undetected-chromedriver** 提供：
- 隐藏 Selenium 特征
- 绕过 Cloudflare
- 绕过 DataDome
- 绕过 PerimeterX

### 6.3 指纹生成

| 指纹类型 | 实现方式 |
|----------|----------|
| WebDriver | undetected-chromedriver 自动隐藏 |
| Navigator | 默认或动态 UA |
| Chrome Extensions | 已移除 |

### 6.4 人类滚动 ✅

使用 **Selenium ActionChains**：

```python
from selenium.webdriver.common.action_chains import ActionChains
ActionChains(driver).move_by_offset(x, y).perform()
```

### 6.5 反反爬策略

| 策略 | 说明 |
|------|------|
| 代理轮换 | ThorData 住宅代理 |
| 延迟 | 5-10 秒随机延迟 |
| 人类滚动 | ✅ 启用 |
| 更换 UA | ✅ 启用 |
| Cookie | ✅ 保持 |

### 6.6 代码位置

- 渲染逻辑: `middlewares/tier_strategy.py` → `_render_uc()`

---

## 7. Tier 6 - SELENIUMBASE (最大隐身)

### 7.1 实现原理

使用 **SeleniumBase** 启动 UC (Undetected Chrome) 模式的 Chrome。

```
请求 → SeleniumBase (UC 模式) → ThorData 代理 → 目标网站
```

### 7.2 核心技术

**SeleniumBase** 提供：
- Undetected Chrome 模式
- 内置隐身功能
- 自动化增强
- 内置等待机制

### 7.3 指纹生成

| 指纹类型 | 实现方式 |
|----------|----------|
| WebDriver | SeleniumBase UC 模式隐藏 |
| Navigator | `get_fingerprint_script()` 注入 JS |
| Canvas | JS 指纹补丁 |
| WebGL | JS 指纹补丁 |
| AudioContext | JS 指纹补丁 |

**JS 指纹注入** (`fingerprint_spoofer.py`)：

```javascript
// 覆盖 navigator.webdriver
Object.defineProperty(navigator, 'webdriver', { get: () => false });

// 覆盖 navigator.plugins
Object.defineProperty(navigator, 'plugins', { get: () => [...] });

// 覆盖 media devices
navigator.mediaDevices = {};
```

### 7.4 人类滚动 ✅

使用 **UnifiedHumanBehavior** + **SeleniumMouseAdapter**：

```python
adapter = SeleniumMouseAdapter(driver)
behavior = UnifiedHumanBehavior(adapter)
behavior.human_scroll(0, 1500)
```

滚动特征：
- **鼠标曲线**: 三次贝塞尔曲线
- **微抖动**: ±2.5px 高斯抖动
- **缓动**: ease-in-out

### 7.5 反反爬策略

| 策略 | 说明 |
|------|------|
| 代理轮换 | ThorData 住宅代理 |
| 延迟 | 5-10 秒随机延迟 |
| 人类滚动 | ✅ 启用 (Bezier) |
| 更换 UA | ✅ 启用 |
| Cookie | ✅ 保持 |
| JS 指纹 | ✅ 注入 |

### 7.6 代码位置

- Wrapper: `browser/seleniumbase_wrapper.py` → `SeleniumBaseWrapper`
- 指纹脚本: `browser/fingerprint_spoofer.py` → `get_fingerprint_script()`

---

## 8. Tier 7 - CLOAKBROWSER (C++ 补丁 Chromium)

### 8.1 实现原理

使用 **CloakBrowser** - 经过 C++ 层修改的特殊 Chromium 浏览器。

```
请求 → CloakBrowser (修改版 Chromium) → ThorData 代理 → 目标网站
```

### 8.2 核心技术

**CloakBrowser** 提供：
- C++ 层修改的 Chromium
- 内置反检测
- 更深度的浏览器指纹隐藏
- 专为企业级爬虫设计

### 8.3 指纹生成

| 指纹类型 | 实现方式 |
|----------|----------|
| Browser Core | CloakBrowser 内置修改 |
| Navigator | cloaked by C++ patch |
| WebGL | cloaked by C++ patch |
| Canvas | cloaked by C++ patch |

### 8.4 人类滚动 ✅

使用 **UnifiedHumanBehavior** + **CloakBrowserMouseAdapter**：

```python
adapter = CloakBrowserMouseAdapter(page)
behavior = UnifiedHumanBehavior(adapter)
behavior.human_scroll(0, 1500)
```

### 8.5 反反爬策略

| 策略 | 说明 |
|------|------|
| 代理轮换 | ThorData 住宅代理 |
| 延迟 | 5-10 秒随机延迟 |
| 人类滚动 | ✅ 启用 (Bezier) |
| 更换 UA | ✅ 启用 |
| Cookie | ✅ 保持 |
| C++ 指纹 | ✅ 深度隐藏 |

### 8.6 代码位置

- Wrapper: `browser/cloakbrowser_wrapper.py` → `CloakBrowserWrapper`

---

## 9. Tier 8 - KAMELEO (指纹浏览器)

### 9.1 实现原理

使用 **Kameleo** - 专业的指纹浏览器平台。

```
请求 → Kameleo Local API → 创建指纹浏览器 → ThorData 代理 → 目标网站
```

### 9.2 核心技术

**Kameleo** 提供：
- 硬件级指纹模拟
- 独立的浏览器环境
- 指纹 Profile 管理
- 自动化 API

### 9.3 指纹生成

Kameleo 使用 **Profile** 定义指纹：

```python
profile = {
    "browser": {
        "userAgent": "Mozilla/5.0 ...",
        "acceptLanguages": ["en-US", "en"],
        "doNotTrack": "undefined",
        "locale": "en-US",
        "webGLVendor": "Intel Inc.",
        "webGLRenderer": "Intel Iris OpenGL Engine",
    },
    "device": {
        "colorDepth": 24,
        "pixelRatio": 2.0,
        "screenResolution": {"width": 1920, "height": 1080},
    },
    "geoip": {"timezone": "America/New_York"},
}
```

### 9.4 人类滚动

使用 **Kameleo Client API** 发送滚动命令：

```python
client.execute_script(profile.id, "window.scrollTo(0, 500)")
time.sleep(0.5)
client.execute_script(profile.id, "window.scrollTo(0, 1000)")
```

### 9.5 反反爬策略

| 策略 | 说明 |
|------|------|
| 代理轮换 | ThorData 住宅代理 |
| 延迟 | 8-15 秒随机延迟 |
| 人类滚动 | ✅ 启用 (API 控制) |
| 更换 UA | ✅ 启用 (Profile) |
| Cookie | ✅ 保持 |
| 硬件指纹 | ✅ 完全模拟 |

### 9.6 代码位置

- Wrapper: `browser/kameleo_wrapper.py` → `KameleoWrapper`
- API 调用: `browser/kameleo_wrapper.py` → `KameleoClientAPI`

---

## 10. 人类滚动详解

### 10.1 滚动实现对比

| Tier | 实现方式 | 鼠标轨迹 | LLM 生成 |
|------|----------|----------|----------|
| 1 | ❌ | - | - |
| 2 | ❌ | - | - |
| 3 | PlaywrightMouseAdapter | Bezier | ❌ |
| 4 | HumanMouseController | Bezier | ❌ |
| 5 | SeleniumMouseAdapter | Bezier | ❌ |
| 6 | SeleniumMouseAdapter | Bezier | ❌ |
| 7 | CloakBrowserMouseAdapter | Bezier | ✅ (1h 缓存) |
| 8 | Kameleo Client API | 可变 | ✅ (可选) |

### 10.2 Bezier 曲线原理

```python
def generate_human_curve(start, end, segments=50, jitter_std=2.5, curve_intensity=0.3):
    # 1. 计算直线距离和角度
    # 2. 随机生成控制点 (偏离直线)
    # 3. 三次贝塞尔插值
    # 4. 添加高斯微抖动
```

### 10.3 LLM 生成滚动模式

```python
CachedLLMHumanBehavior.get_cached_pattern(site, page_type)
# 返回:
{
    "scroll_strategy": "mixed",
    "scroll_phases": [
        {"start_y": 0, "end_y": 400, "speed": "fast", "pause_after": 0.1},
        {"start_y": 400, "end_y": 1000, "speed": "slow", "pause_after": 0.3, "hover": {"x": 400, "y": 600}},
        ...
    ]
}
```

---

## 11. 指纹生成详解

### 11.1 指纹注入方式对比

| Tier | 指纹来源 | 注入方式 |
|------|----------|----------|
| 1 | curl_cffi 内置 | 自动 |
| 2 | cloudscraper 内置 | 自动 |
| 3 | Playwright 默认 | 无注入 |
| 4 | Camoufox 内置 | 自动 |
| 5 | undetected-chromedriver | 自动 |
| 6 | fingerprint_spoofer.js | JS 注入 |
| 7 | CloakBrowser C++ | 内置 |
| 8 | Kameleo Profile | Profile 定义 |

### 11.2 JS 指纹补丁内容

```javascript
// navigator.webdriver
Object.defineProperty(navigator, 'webdriver', { get: () => false });

// navigator.plugins
Object.defineProperty(navigator, 'plugins', {
    get: () => [
        {name: 'Chrome PDF Plugin', ...},
        {name: 'Chrome PDF Viewer', ...},
        ...
    ]
});

// canvas fingerprint
CanvasRenderingContext2D.prototype.getImageData = ...

// webgl
WebGLRenderingContext.prototype.getParameter = ...

// audio
AudioContext.prototype.createOscillator = ...

// permissions
navigator.permissions.query = ...
```

---

## 12. 代理系统

### 12.1 代理配置

```python
# config.py
THORDATA_PROXY_HOST = "80afep8v.pr.thordata.net"
THORDATA_RESIDENTIAL_USERNAME = "Naoqdrceyc7g"
THORDATA_RESIDENTIAL_PASSWORD = "AuQObe60qx0w"
```

### 12.2 代理格式

```
http://{username}:{password}@{host}:{port}
```

### 12.3 Sticky Session

ThorData 支持 sticky session - 同一 IP 固定一段时间：

```python
manager = ThorDataManager(
    username=self.username,
    password=self.password,
    country="us",
    sticky=True,
    session_duration=180,  # 3 分钟
)
```

---

## 13. 站点默认 Tier

### 13.1 各站点默认 Tier

所有站点默认从 **Tier 6** 开始搜索页面，详情页根据站点复杂度选择 Tier 1-3：

| 站点 | SEARCH Tier | DETAIL Tier |
|------|------------|-------------|
| amazon | 6 | 3 |
| walmart | 6 | 3 |
| target | 6 | 2 |
| ebay | 6 | 2 |
| homedepot | 6 | 2 |
| lowes | 6 | 2 |
| menards | 6 | 3 |
| acehardware | 6 | 2 |
| wayfair | 6 | 2 |
| michaels | 6 | 2 |
| temu | 6 | 1 |
| etsy | 6 | 2 |
| bestbuy | 6 | 2 |
| costco | 6 | 2 |
| qvc | 6 | 2 |
| kohls | 6 | 2 |
| mercadolibre | 6 | 2 |
| walmartmexico | 6 | 2 |
| intexcorp | 6 | 2 |
| meijer | 6 | 2 |
| fivebelow | 6 | 1 |
| samsclub | 6 | 2 |
| bunnings | 6 | 2 |
| dollargeneral | 6 | 1 |
| action | 6 | 1 |
| academy | 6 | 2 |
| wowsports | 6 | 1 |
| coppel | 6 | 2 |
| aosom | 6 | 1 |
| familydollar | 6 | 1 |
| costway | 6 | 1 |

### 13.2 Tier 升级流程

```
请求 → Tier N
    │
    ├──► 成功 → 记录成功策略
    │
    └──► 失败 → 检测 Block 类型
                │
                ├──► 升级到 Tier N+1
                │
                └──► 重试
```

---

## 14. 文件索引

| 文件 | 说明 |
|------|------|
| `core/strategy.py` | Tier 配置定义 |
| `core/proxy/thordata.py` | ThorData 代理实现 |
| `browser/*_wrapper.py` | 各浏览器 Wrapper |
| `browser/fingerprint_spoofer.py` | JS 指纹补丁 |
| `browser/human_mouse.py` | 人类滚动 + LLM |
| `middlewares/tier_strategy.py` | Tier 执行逻辑 |
