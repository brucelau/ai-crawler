# LLM 系统文档

> 状态：已与当前 `gpt` 分支实现对齐。
>
> 适用范围：LLM / DSPy 推理层、Pydantic 校验层、LLM 参与的运行时决策链。
>
> 相关文档：
>
> - `docs/ARCHITECTURE.md`
> - `docs/TIER_SYSTEM.md`
> - `docs/BLOCK_DETECTOR.md`

> **重要更新（gpt 分支重构后）**：LLM 现在不是页面提取的唯一智能层。当前页面提取主链已经演进为：
>
> `json_ld -> js_eval -> api_intercept -> axtree -> bs_css`
>
> 其中 LLM 主要负责：
> - selector 生成与模板缓存
> - block / threshold / URL / human behavior / strategy 等决策增强
>
> AXTree 提取属于 `core/extraction/extraction.py` 的运行时提取策略，而不是 LLM 系统本身。
>
> 当前 selector 生成已经支持 **HTML + AXTree 语义采样** 的混合输入思路：
>
> - HTML 仍然是主输入（保留 DOM / class / attribute 线索）
> - AXTree 语义采样作为补充输入（补充页面骨架与可见产品语义）

---

## 1. 系统架构概览

### 1.1 三层架构

```
┌────────────────────────────────────────────────────────────────┐
│                      LLM 调用层                                  │
│  DSPy Signatures + Modules (推理)                                │
│  - SelectorSignature / SelectorExtractor                         │
│  - BlockSignature / BlockDetector                               │
│  - ThresholdSignature / ThresholdOptimizer                     │
│  - URLDiscoverySignature / URLDiscoverer                        │
│  - HumanBehaviorSignature / HumanBehaviorGenerator             │
│  - ProfileGenerationSignature / ProfileGenerator                │
│  - StrategySelectionSignature / StrategySelector                │
│  - InitialTierSignature / InitialTierSelector                   │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼ raw output (dict/str)
┌────────────────────────────────────────────────────────────────┐
│                     Pydantic 校验层                             │
│  Validators (标准化输出)                                        │
│  - validate_selector() → SelectorResult                         │
│  - validate_block() → BlockResult                               │
│  - validate_threshold() → ThresholdResult                       │
│  - validate_url_discovery() → URLDiscoveryResult                │
│  - validate_human_behavior() → HumanBehaviorResult             │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼ standardized output
┌────────────────────────────────────────────────────────────────┐
│                      业务逻辑层                                  │
│  - LLMExtractor / LLMBlockDetector                              │
│  - DynamicThresholdOptimizer / URLDiscovery                      │
│  - CachedLLMHumanBehavior                                      │
│  - （与 LLM 并行协作）AXTree / JSON-LD / JS / BS 提取链          │
└────────────────────────────────────────────────────────────────┘
```

### 1.2 配置

所有 LLM 配置统一通过 `config.py`：

```python
# ai_crawler/config.py
class Config:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o")
```

**当前配置**:
| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| API Key | `OPENAI_API_KEY` | - | OpenAI/DashScope API Key |
| Base URL | `OPENAI_BASE_URL` | `https://api.openai.com/v1` | API Base URL |
| Model | `MODEL_NAME` | `gpt-4o` | 模型名称 |

### 1.3 DSPy LM 配置

DSPy 需要单独配置语言模型（在 `__main__.py` 或 `dspy_scheduler.py` 中）：

```python
# ai_crawler/__main__.py
import dspy

def _configure_dspy_lm():
    if not config.OPENAI_API_KEY:
        return
    
    base_url = config.OPENAI_BASE_URL
    model = config.MODEL_NAME
    
    if "api.openai.com" not in base_url and not model.startswith("openai/"):
        model_str = f"openai/{model}"
    else:
        model_str = model
    
    lm = dspy.LM(model_str, api_key=config.OPENAI_API_KEY, base_url=base_url)
    dspy.settings.configure(lm=lm)
```

---

## 2. DSPy 模块详解

### 2.1 CSS Selector 生成

**文件**: `core/llm/dspy_model.py`

```python
class SelectorSignature(dspy.Signature):
    site = dspy.InputField()
    page_type = dspy.InputField(desc="Page type: search, detail, or category")
    html_sample = dspy.InputField(desc="HTML snippet from the webpage (first 8000 chars)")

    list_container = dspy.OutputField(desc="CSS selector for product list container")
    product_selector = dspy.OutputField(desc="CSS selector for individual product items")
    link_selector = dspy.OutputField(desc="CSS selector for product link")
    title_selector = dspy.OutputField(desc="CSS selector for product title")
    price_selector = dspy.OutputField(desc="CSS selector for product price (integer part)")
    price_fraction_selector = dspy.OutputField(desc="CSS selector for price decimal/fraction part")
    image_selector = dspy.OutputField(desc="CSS selector for product image")
    rating_selector = dspy.OutputField(desc="CSS selector for rating")
    review_count_selector = dspy.OutputField(desc="CSS selector for review count")
    product_id_attribute = dspy.OutputField(desc="Attribute name containing product ID if any")


class SelectorExtractor(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict(SelectorSignature)

    def forward(self, site: str, page_type: str, html_sample: str):
        return self.predict(site=site, page_type=page_type, html_sample=html_sample)
```

**调用示例**:

```python
from ai_crawler.core.dspy_model import SelectorExtractor

extractor = SelectorExtractor()
result = extractor(site="amazon", page_type="search", html_sample=html[:8000])

# result.list_container
# result.product_selector
# result.title_selector
# ...
```

---

### 2.2 Block 类型检测

**文件**: `core/llm/dspy_model.py`

```python
class BlockSignature(dspy.Signature):
    site = dspy.InputField()
    status_code = dspy.InputField(desc="HTTP status code")
    response_text = dspy.InputField(desc="Response content snippet (first 3000 chars)")

    block_type = dspy.OutputField(
        desc="none, http_403, http_429, http_451, http_timeout, captcha, cloudflare, bot_detected, empty_response, unknown"
    )
    reasoning = dspy.OutputField(desc="1-2 sentences explaining the classification")
    suggested_action = dspy.OutputField(
        desc="retry_same, retry_with_different_proxy, retry_with_browser, skip, escalate"
    )


class BlockDetector(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict(BlockSignature)

    def forward(self, site: str, status_code: int, response_text: str):
        return self.predict(site=site, status_code=status_code, response_text=response_text)
```

**调用示例**:

```python
from ai_crawler.core.dspy_model import BlockDetector

detector = BlockDetector()
result = detector(site="amazon", status_code=200, response_text=html[:3000])

# result.block_type  # "none", "captcha", "cloudflare", ...
# result.reasoning
# result.suggested_action
```

---

### 2.3 动态阈值优化

**文件**: `core/llm/dspy_model.py`

```python
class ThresholdSignature(dspy.Signature):
    site = dspy.InputField()
    page_type = dspy.InputField(desc="Page type: search, detail, or category")
    avg_response_time = dspy.InputField(desc="Average response time in seconds")
    success_rate = dspy.InputField(desc="Success rate as decimal (0.0-1.0)")
    total_requests = dspy.InputField(desc="Total number of requests made")
    current_timeout = dspy.InputField(desc="Current request timeout in seconds")
    current_page_load_timeout = dspy.InputField(desc="Current page load timeout in seconds")
    html_sample = dspy.InputField(desc="HTML snippet for page complexity analysis (first 2000 chars)")

    request_timeout = dspy.OutputField(desc="Recommended request timeout in seconds")
    page_load_timeout = dspy.OutputField(desc="Recommended page load timeout in seconds")
    delay_after = dspy.OutputField(desc="Min and max delay between requests as JSON list [min, max]")
    reasoning = dspy.OutputField(desc="Explanation for the recommended values")


class ThresholdOptimizer(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict(ThresholdSignature)

    def forward(
        self,
        site: str,
        page_type: str,
        avg_response_time: float,
        success_rate: float,
        total_requests: int,
        current_timeout: int,
        current_page_load_timeout: int,
        html_sample: str,
    ):
        return self.predict(
            site=site,
            page_type=page_type,
            avg_response_time=avg_response_time,
            success_rate=success_rate,
            total_requests=total_requests,
            current_timeout=current_timeout,
            current_page_load_timeout=current_page_load_timeout,
            html_sample=html_sample,
        )
```

**调用示例**:

```python
from ai_crawler.core.dspy_model import ThresholdOptimizer

optimizer = ThresholdOptimizer()
result = optimizer(
    site="amazon",
    avg_response_time=2.5,
    success_rate=0.85,
    total_requests=20,
    current_timeout=30,
    current_page_load_timeout=30,
    html_sample=html[:2000]
)

# result.request_timeout   # 35.0
# result.page_load_timeout # 40.0
# result.delay_after       # [4, 10]
# result.reasoning
```

---

### 2.4 URL 发现

**文件**: `core/llm/dspy_model.py`

```python
class URLDiscoverySignature(dspy.Signature):
    site = dspy.InputField()
    homepage_html = dspy.InputField(desc="Homepage HTML snippet (first 5000 chars)")

    search_url_pattern = dspy.OutputField(
        desc="Full search URL pattern with {query} placeholder, e.g. https://example.com/search?q={query}"
    )
    search_param = dspy.OutputField(desc="Search parameter name, e.g. q, k, searchTerm")
    page_param = dspy.OutputField(desc="Pagination parameter name, e.g. page, offset")
    product_url_pattern = dspy.OutputField(desc="Product URL pattern with {id} or {asin} placeholder")
    uses_js_rendering = dspy.OutputField(desc="Whether search results use JavaScript rendering (true/false)")


class URLDiscoverer(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict(URLDiscoverySignature)

    def forward(self, site: str, homepage_html: str):
        return self.predict(site=site, homepage_html=homepage_html)
```

**调用示例**:

```python
from ai_crawler.core.dspy_model import URLDiscoverer

discoverer = URLDiscoverer()
result = discoverer(site="amazon", homepage_html=homepage_html[:5000])

# result.search_url_pattern  # "https://www.amazon.com/s?k={query}"
# result.search_param        # "k"
# result.page_param          # "page"
# result.product_url_pattern # "https://www.amazon.com/dp/{asin}"
# result.uses_js_rendering   # False
```

---

### 2.5 人类行为生成

**文件**: `core/llm/dspy_model.py`

```python
class HumanBehaviorSignature(dspy.Signature):
    site = dspy.InputField()
    page_type = dspy.InputField(desc="Page type: search, product, home")
    context = dspy.InputField(desc="Additional context about the page")

    scroll_strategy = dspy.OutputField(desc="gradual, burst, or mixed")
    scroll_phases = dspy.OutputField(
        desc='JSON list of scroll phases, each with start_y, end_y, speed, pause_after, optional hover: [{"start_y": 0, "end_y": 500, "speed": "fast", "pause_after": 0.2, "hover": null}, ...]'
    )
    reasoning = dspy.OutputField(desc="Why a human would browse this way")


class HumanBehaviorGenerator(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict(HumanBehaviorSignature)

    def forward(self, site: str, page_type: str = "search", context: str = ""):
        return self.predict(site=site, page_type=page_type, context=context)
```

**调用示例**:

```python
from ai_crawler.core.dspy_model import HumanBehaviorGenerator

generator = HumanBehaviorGenerator()
result = generator(site="amazon", page_type="search", context="")

# result.scroll_strategy  # "mixed"
# result.scroll_phases
# result.reasoning
```

**scroll_phases 结构**:

```python
[
    {
        "start_y": 0,
        "end_y": 400,
        "speed": "fast",       # fast, medium, slow
        "pause_after": 0.1,
        "hover": None
    },
    {
        "start_y": 400,
        "end_y": 1000,
        "speed": "slow",
        "pause_after": 0.3,
        "hover": {"x": 400, "y": 600, "duration": 0.5}
    },
    # ...
]
```

---

### 2.6 浏览器指纹生成

**文件**: `core/llm/dspy_model.py`

```python
class ProfileGenerationSignature(dspy.Signature):
    system_facts = dspy.InputField(
        desc="JSON string containing os, architecture, network details, and hardware info (GPU, screen) of the host machine."
    )

    user_agent = dspy.OutputField(
        desc="A realistic, up-to-date User-Agent string that strictly matches the OS described in system_facts."
    )
    sec_ch_ua_platform = dspy.OutputField(
        desc='The exact string to use for the sec-ch-ua-platform header (e.g. "macOS", "Windows", "Linux").'
    )
    sec_ch_ua = dspy.OutputField(
        desc="The exact string to use for the sec-ch-ua header matching the generated user_agent's browser version."
    )
    stealth_args = dspy.OutputField(
        desc="A JSON list of string arguments to pass to Playwright/Chromium to improve stealth for this specific OS."
    )
    curl_impersonate_target = dspy.OutputField(
        desc="The curl_cffi impersonate target string (e.g. 'chrome120', 'safari15_5', 'edge101') matching the generated user agent."
    )
    timezone_id = dspy.OutputField(
        desc="A valid IANA timezone ID (e.g. 'America/New_York') matching the target_proxy_country."
    )
    locale = dspy.OutputField(
        desc="A valid BCP-47 locale code (e.g. 'en-US', 'en-GB') matching the target_proxy_country."
    )
    viewport = dspy.OutputField(
        desc="A JSON dictionary containing 'width' and 'height' representing the screen resolution from hardware."
    )
    mouse_behavior = dspy.OutputField(
        desc="A JSON dictionary with 'jitter_std', 'curve_intensity', and 'scroll_pause_mean' tuned for the detected OS."
    )
    gpu_vendor = dspy.OutputField(
        desc="The GPU vendor string to spoof in WebGL (e.g. 'NVIDIA', 'AMD', 'Apple') - MUST match hardware field in system_facts."
    )
    gpu_renderer = dspy.OutputField(
        desc="The GPU renderer string to spoof (e.g. 'NVIDIA GeForce RTX 4090', 'Apple M2 Pro') - MUST match hardware field in system_facts."
    )
    device_pixel_ratio = dspy.OutputField(
        desc="The device pixel ratio to use, matching the hardware screen DPI."
    )
    platform_string = dspy.OutputField(
        desc="The platform string for navigator.platform (e.g. 'MacIntel', 'Win32', 'Linux x86_64') - MUST match hardware field in system_facts."
    )
    connection_type = dspy.OutputField(
        desc="The network connection type to spoof for navigator.connection (e.g. 'wifi', '4g'). Use 'wifi' for home broadband."
    )
    downlink = dspy.OutputField(
        desc="The downlink speed in Mbps for navigator.connection (e.g. 10 for typical broadband, 5 for mobile)."
    )
    rtt = dspy.OutputField(
        desc="The round-trip time in ms for navigator.connection (e.g. 50 for broadband, 100 for mobile)."
    )
    plugins = dspy.OutputField(
        desc="A JSON list of navigator.plugins objects with name, description, filename fields. Use standard Chrome plugins."
    )
    usb = dspy.OutputField(
        desc="A JSON dict with getDevices returning an empty array: {'getDevices': []}."
    )
    media_devices = dspy.OutputField(
        desc="A JSON list of fake media devices with kind, deviceId, label, groupId. Use empty labels and 'default' deviceId."
    )
    battery = dspy.OutputField(
        desc="A JSON dict with battery status: {'charging': true, 'level': 0.95, 'chargingTime': 0}."
    )
    webdriver_value = dspy.OutputField(
        desc="The value for navigator.webdriver. Use 'undefined' to avoid detection."
    )
    permissions_default = dspy.OutputField(
        desc="The default permission state for navigator.permissions.query. Use 'default', 'granted', or 'denied'."
    )
    orientation_angle = dspy.OutputField(
        desc="The screen orientation angle in degrees (0 for landscape, 90 for portrait on mobile)."
    )
    orientation_type = dspy.OutputField(
        desc="The screen orientation type: 'landscape-primary', 'portrait-primary', 'landscape-secondary', etc."
    )
    reasoning = dspy.OutputField(
        desc="Why this specific fingerprint profile was chosen to match the OS and hardware signature."
    )


class ProfileGenerator(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict(ProfileGenerationSignature)

    def forward(self, system_facts: str):
        return self.predict(system_facts=system_facts)
```

**调用示例**:

```python
from ai_crawler.core.dspy_model import ProfileGenerator
from ai_crawler.core.introspection import get_system_facts
import json

generator = ProfileGenerator()
system_facts = get_system_facts()
result = generator(system_facts=json.dumps(system_facts))

# result.user_agent
# result.locale
# result.viewport
# result.gpu_vendor
# result.gpu_renderer
# ... (20+ 输出字段)
```

---

### 2.7 策略选择

**文件**: `core/llm/dspy_model.py`

```python
class StrategySelectionSignature(dspy.Signature):
    site = dspy.InputField()
    page_pattern = dspy.InputField()
    block_type = dspy.InputField()
    response_snippet = dspy.InputField()
    attempt_history = dspy.InputField()

    recommended_strategy = dspy.OutputField()
    confidence = dspy.OutputField()
    reasoning = dspy.OutputField()


class StrategySelector(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict(StrategySelectionSignature)

    def forward(
        self,
        site: str,
        page_pattern: str,
        block_type: str,
        response_snippet: str,
        attempt_history: list,
    ):
        return self.predict(
            site=site,
            page_pattern=page_pattern,
            block_type=block_type,
            response_snippet=response_snippet,
            attempt_history=attempt_history,
        )
```

**调用示例**:

```python
from ai_crawler.core.dspy_model import StrategySelector

selector = StrategySelector()
result = selector(
    site="amazon",
    page_pattern="search",
    block_type="captcha",
    response_snippet=html[:500],
    attempt_history=[
        {"tier": 6, "proxy": "thordata", "result": "failed"},
    ]
)

# result.recommended_strategy
# result.confidence
# result.reasoning
```

---

### 2.8 初始 Tier 选择

**文件**: `core/llm/dspy_model.py`

```python
class InitialTierSignature(dspy.Signature):
    site = dspy.InputField()
    page_pattern = dspy.InputField()
    difficulty_hint = dspy.InputField()
    failure_history = dspy.InputField(
        desc="JSON string of recent failures for this (site, page_pattern). Each entry: tier, block_type, waf_detected, status_code, summary."
    )

    start_tier = dspy.OutputField(
        desc="The starting tier to try (1-6). Higher tiers are more powerful but slower and more expensive."
    )
    confidence = dspy.OutputField()
    reasoning = dspy.OutputField()


class InitialTierSelector(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict(InitialTierSignature)

    def forward(
        self, site: str, page_pattern: str, difficulty_hint: str = "", failure_history: str = ""
    ):
        return self.predict(
            site=site,
            page_pattern=page_pattern,
            difficulty_hint=difficulty_hint,
            failure_history=failure_history,
        )
```

**调用示例**:

```python
from ai_crawler.core.dspy_model import InitialTierSelector

selector = InitialTierSelector()
result = selector(
    site="amazon",
    page_pattern="search",
    difficulty_hint="",
    failure_history="[]"
)

# result.start_tier  # 6
# result.confidence
# result.reasoning
```

---

## 3. Pydantic Validators 详解

**文件**: `core/extraction/validators.py`

### 3.1 SelectorResult

```python
class SelectorResult(BaseModel):
    site: str = ""
    list_container: str = Field(default="", description="CSS selector for product list container")
    product_selector: str = Field(default="", description="CSS selector for individual product items")
    title_selector: str = Field(default="", description="CSS selector for product title")
    price_selector: str = Field(default="", description="CSS selector for product price (integer part)")
    price_fraction_selector: str = Field(default="", description="CSS selector for price decimal/fraction part")
    image_selector: str = Field(default="", description="CSS selector for product image")
    rating_selector: str = Field(default="", description="CSS selector for rating")
    review_count_selector: str = Field(default="", description="CSS selector for review count")
    link_selector: str = Field(default="", description="CSS selector for product link")
    product_id_attribute: str = Field(default="", description="Attribute name containing product ID if any")
```

### 3.2 BlockResult

```python
class BlockResult(BaseModel):
    block_type: str = Field(
        default="unknown",
        description="none, http_403, http_429, http_451, http_timeout, captcha, cloudflare, bot_detected, empty_response, unknown"
    )
    reasoning: str = Field(default="", description="1-2 sentences explaining the classification")
    suggested_action: str = Field(
        default="retry_same",
        description="retry_same, retry_with_different_proxy, retry_with_browser, skip, escalate"
    )
```

### 3.3 ThresholdResult

```python
class ThresholdResult(BaseModel):
    request_timeout: float = Field(default=30.0, description="Recommended request timeout in seconds")
    page_load_timeout: float = Field(default=30.0, description="Recommended page load timeout in seconds")
    delay_after: list[float] = Field(default=[3, 8], description="[min, max] delay between requests in seconds")
    reasoning: str = Field(default="", description="Explanation for the recommended values")
```

### 3.4 URLDiscoveryResult

```python
class URLDiscoveryResult(BaseModel):
    site: str = ""
    search_url_pattern: str = Field(default="", description="Full search URL pattern with {query} placeholder")
    search_param: str = Field(default="q", description="Search parameter name")
    page_param: str = Field(default="page", description="Pagination parameter name")
    product_url_pattern: str = Field(default="", description="Product URL pattern with {id} placeholder")
    uses_js_rendering: bool = Field(default=True, description="Whether search results use JavaScript rendering")
```

### 3.5 HumanBehaviorResult

```python
class HumanBehaviorResult(BaseModel):
    scroll_strategy: str = Field(default="mixed", description="gradual, burst, or mixed")
    scroll_phases: list[dict] = Field(
        default=[],
        description="List of scroll phases with start_y, end_y, speed, pause_after, optional hover"
    )
    reasoning: str = Field(default="", description="Why a human would browse this way")
```

### 3.6 校验函数

```python
def validate_selector(raw: dict) -> SelectorResult:
    try:
        return SelectorResult(**raw)
    except Exception:
        return SelectorResult(site=raw.get("site", ""))


def validate_block(raw: dict) -> BlockResult:
    try:
        return BlockResult(**raw)
    except Exception:
        return BlockResult(
            block_type=raw.get("block_type", "unknown"),
            reasoning=raw.get("reasoning", ""),
            suggested_action=raw.get("suggested_action", "retry_same"),
        )


def validate_threshold(raw: dict) -> ThresholdResult:
    try:
        delay = raw.get("delay_after", [3, 8])
        if isinstance(delay, str):
            import json
            delay = json.loads(delay)
        return ThresholdResult(
            request_timeout=float(raw.get("request_timeout", 30.0)),
            page_load_timeout=float(raw.get("page_load_timeout", 30.0)),
            delay_after=list(delay) if delay else [3, 8],
            reasoning=raw.get("reasoning", ""),
        )
    except Exception:
        return ThresholdResult()


def validate_url_discovery(raw: dict) -> URLDiscoveryResult:
    try:
        return URLDiscoveryResult(**raw)
    except Exception:
        return URLDiscoveryResult(
            site=raw.get("site", ""),
            search_url_pattern=raw.get("search_url_pattern", ""),
            search_param=raw.get("search_param", "q"),
            page_param=raw.get("page_param", "page"),
            product_url_pattern=raw.get("product_url_pattern", ""),
            uses_js_rendering=raw.get("uses_js_rendering", True),
        )


def validate_human_behavior(raw: dict) -> HumanBehaviorResult:
    try:
        phases = raw.get("scroll_phases", [])
        if isinstance(phases, str):
            import json
            phases = json.loads(phases)
        return HumanBehaviorResult(
            scroll_strategy=raw.get("scroll_strategy", "mixed"),
            scroll_phases=phases if isinstance(phases, list) else [],
            reasoning=raw.get("reasoning", ""),
        )
    except Exception:
        return HumanBehaviorResult()
```

---

## 4. 业务逻辑层

### 4.1 LLMExtractor

**文件**: `core/llm/llm_extractor.py`

```python
class LLMExtractor:
    _instance: Optional["LLMExtractor"] = None
    _cache: dict[str, dict] = {}
    _cache_ttl: float = 86400.0

    def _cache_key(self, site: str, page_type: str) -> str:
        return f"{site}:{page_type}"

    def _is_cache_valid(self, site: str, page_type: str) -> bool:
        key = self._cache_key(site, page_type)
        if key not in self._cache:
            return False
        cached_time = self._cache[key].get("_cached_at", 0)
        return (time.time() - cached_time) < self._cache_ttl

    def _generate_selectors(self, site: str, page_type: str, html_sample: str) -> dict:
        extractor = self._get_dspy_extractor()
        if not extractor:
            return self._default_selectors(site, page_type)

        try:
            raw_result = extractor(site=site, page_type=page_type, html_sample=html_sample[:8000])
            result = validate_selector(raw_result.__dict__)
            selectors = result.model_dump()
            selectors["_cached_at"] = time.time()
            return selectors
        except Exception:
            return self._default_selectors(site, page_type)

    def get_selectors(self, site: str, page_type: str, html_sample: str = "") -> dict:
        key = self._cache_key(site, page_type)
        if self._is_cache_valid(site, page_type):
            cached = self._cache[key].copy()
            del cached["_cached_at"]
            return cached

        selectors = self._generate_selectors(site, page_type, html_sample)
        self._cache[key] = selectors
        cached = selectors.copy()
        del cached["_cached_at"]
        return cached

    def extract(self, html: str, site: str, page_type: str, url: str) -> list[Product]:
        selectors = self.get_selectors(site, page_type, html[:50000])
        # ... 提取逻辑
```

**缓存**: `(site, page_type)` 组合级别，TTL=24小时
- `amazon:search` → 搜索页选择器
- `amazon:detail` → 详情页选择器

**Fallback**: 硬编码默认选择器

---

### 4.2 LLMBlockDetector

**文件**: `core/llm/llm_block_detector.py`

```python
class LLMBlockDetector:
    _instance: Optional["LLMBlockDetector"] = None
    _cache: dict[str, tuple[str, str, float]] = {}
    _cache_ttl: float = 86400.0  # 24 hours

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_dspy_detector(self):
        if not config.has_llm():
            return None
        if self._dspy_detector is None:
            from ai_crawler.core.dspy_model import BlockDetector
            self._dspy_detector = BlockDetector()
        return self._dspy_detector

    def _classify_block(self, status_code: int, text: str, site: str) -> tuple[str, str]:
        detector = self._get_dspy_detector()
        if not detector:
            return self._heuristic_classify(status_code, text)

        try:
            raw_result = detector(site=site, status_code=status_code, response_text=text[:3000])
            result = validate_block(raw_result.__dict__)

            block_type_map = {
                "none": BlockType.NONE,
                "http_403": BlockType.HTTP_403,
                "http_429": BlockType.HTTP_429,
                "http_451": BlockType.HTTP_451,
                "http_timeout": BlockType.HTTP_TIMEOUT,
                "captcha": BlockType.CAPTCHA,
                "cloudflare": BlockType.CLOUDFLARE,
                "bot_detected": BlockType.BOT_DETECTED,
                "empty_response": BlockType.EMPTY_RESPONSE,
                "unknown": BlockType.UNKNOWN,
            }
            block_type = block_type_map.get(result.block_type, BlockType.UNKNOWN)
            return block_type, result.reasoning
        except Exception:
            return self._heuristic_classify(status_code, text)

    def detect(self, status_code: int, text: str, site: str) -> tuple[bool, str, str]:
        cache_key = self._get_cache_key(text, status_code)

        if self._is_cache_valid(cache_key):
            block_type, reasoning, _ = self._cache[cache_key]
            is_blocked = block_type != BlockType.NONE
            return is_blocked, block_type, reasoning

        block_type, reasoning = self._classify_block(status_code, text, site)
        self._cache[cache_key] = (block_type, reasoning, time.time())

        is_blocked = block_type != BlockType.NONE
        return is_blocked, block_type, reasoning
```

**缓存**: 响应级别（status_code + hash），TTL=5分钟

**Fallback**: 启发式检测（字符串匹配）

---

### 4.3 DynamicThresholdOptimizer

**文件**: `core/engine/dynamic_thresholds.py`

```python
class DynamicThresholdOptimizer:
    _instance: Optional["DynamicThresholdOptimizer"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._metrics: dict[str, SiteMetrics] = defaultdict(SiteMetrics)
            self._dspy_optimizer = None
            self._initialized = True

    def _get_dspy_optimizer(self):
        if not config.has_llm():
            return None
        if self._dspy_optimizer is None:
            from ai_crawler.core.dspy_model import ThresholdOptimizer
            self._dspy_optimizer = ThresholdOptimizer()
        return self._dspy_optimizer

    def suggest_thresholds_via_llm(self, site: str, html_sample: str) -> dict:
        optimizer = self._get_dspy_optimizer()
        if not optimizer:
            return self.get_thresholds(site)

        metrics = self._metrics[site]
        if metrics.total_requests < 5:
            return self.get_thresholds(site)

        try:
            raw_result = optimizer(
                site=site,
                avg_response_time=metrics.avg_response_time(),
                success_rate=metrics.success_rate(),
                total_requests=metrics.total_requests,
                current_timeout=config.REQUEST_TIMEOUT,
                current_page_load_timeout=config.PAGE_LOAD_TIMEOUT,
                html_sample=html_sample[:2000],
            )

            result = validate_threshold(raw_result.__dict__)
            return {
                "request_timeout": result.request_timeout,
                "page_load_timeout": result.page_load_timeout,
                "delay_after": tuple(result.delay_after),
                "confidence": 0.8,
                "strategy": "llm_suggested",
                "reasoning": result.reasoning,
            }
        except Exception:
            return self.get_thresholds(site)
```

**缓存**: 无自动缓存（基于历史数据动态计算）

**Fallback**: 启发式阈值调整

---

### 4.4 URLDiscovery

**文件**: `core/llm/llm_url_discovery.py`

```python
class URLDiscovery:
    _instance: Optional["URLDiscovery"] = None
    _cache: dict[str, dict] = {}
    _cache_ttl: float = 86400.0

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._dspy_discoverer = None

    def _get_dspy_discoverer(self):
        if not config.has_llm():
            return None
        if self._dspy_discoverer is None:
            from ai_crawler.core.dspy_model import URLDiscoverer
            self._dspy_discoverer = URLDiscoverer()
        return self._dspy_discoverer

    def _discover_url_format(self, site: str, homepage_html: str) -> dict:
        discoverer = self._get_dspy_discoverer()
        if not discoverer:
            return self._default_url_format(site)

        try:
            raw_result = discoverer(site=site, homepage_html=homepage_html[:5000])
            result = validate_url_discovery(raw_result.__dict__)
            url_format = result.model_dump()
            url_format["_cached_at"] = time.time()
            return url_format
        except Exception:
            return self._default_url_format(site)

    def get_url_format(self, site: str, homepage_html: str = "") -> dict:
        if self._is_cache_valid(site):
            cached = self._cache[site].copy()
            del cached["_cached_at"]
            return cached

        url_format = self._discover_url_format(site, homepage_html)
        self._cache[site] = url_format
        cached = url_format.copy()
        del cached["_cached_at"]
        return cached

    def build_search_url(
        self, site: str, query: str, page: int = 1, homepage_html: str = ""
    ) -> str:
        url_format = self.get_url_format(site, homepage_html)
        pattern = url_format.get("search_url_pattern", "")
        search_param = url_format.get("search_param", "q")
        page_param = url_format.get("page_param", "page")

        if "{" in pattern and "}" in pattern:
            try:
                pattern = pattern.format(query=query)
            except Exception:
                pattern = f"{pattern}?{search_param}={query}"
        else:
            sep = "?" if "?" not in pattern else "&"
            pattern = f"{pattern}{sep}{search_param}={query}"

        if page > 1 and page_param:
            sep = "&" if "?" in pattern else "?"
            pattern = f"{pattern}{sep}{page_param}={page}"

        return pattern
```

**缓存**: 站点级别，TTL=24小时

**Fallback**: 硬编码 URL 模板

---

### 4.5 CachedLLMHumanBehavior

**文件**: `browser/human_mouse.py`

```python
class CachedLLMHumanBehavior:
    _instance: "CachedLLMHumanBehavior | None" = None
    _cached_pattern: dict | None = None
    _cached_time: float = 0.0
    _cache_ttl: float = 3600.0

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, cache_ttl: float = 3600.0):
        if not hasattr(self, "_initialized"):
            self._cache_ttl = cache_ttl
            self._dspy_generator = None
            self._initialized = True

    def _get_dspy_generator(self):
        if not config.has_llm():
            return None
        if self._dspy_generator is None:
            from ai_crawler.core.dspy_model import HumanBehaviorGenerator
            self._dspy_generator = HumanBehaviorGenerator()
        return self._dspy_generator

    def _generate_pattern(self, site: str, page_type: str = "search", context: str = "") -> dict:
        generator = self._get_dspy_generator()
        if not generator:
            return self._default_pattern()

        try:
            raw_result = generator(site=site, page_type=page_type, context=context)
            result = validate_human_behavior(raw_result.__dict__)
            return result.model_dump()
        except Exception:
            return self._default_pattern()

    def get_cached_pattern(self, site: str, page_type: str = "search") -> dict:
        if not self._should_refresh():
            return self._cached_pattern

        pattern = self._generate_pattern(site, page_type)
        self._cached_pattern = pattern
        self._cached_time = time.time()
        return pattern

    def execute_pattern(self, adapter: MouseAdapter, pattern: dict) -> None:
        # ... 执行滚动模式
```

**缓存**: 全局单例，TTL=1小时（所有站点共享）

**Fallback**: 固定默认模式

---

## 5. DSPy 训练调度器

### 5.1 模块配置

每个 DSPy 模块独立训练，有独立的配置：

```python
MODULE_CONFIGS = {
    "strategy_selector": {
        "class": "StrategySelector",
        "min_traces": 50,
        "min_new_traces": 10,
        "train_interval": 3600,
    },
    "initial_tier_selector": {
        "class": "InitialTierSelector",
        "min_traces": 30,
        "min_new_traces": 5,
        "train_interval": 7200,
    },
    "selector_extractor": {
        "class": "SelectorExtractor",
        "min_traces": 20,
        "min_new_traces": 5,
        "train_interval": 1800,
    },
    # ... 其他模块
}
```

### 5.2 DSPyScheduler

**文件**: `core/llm/dspy_scheduler.py`

调度器轮询各模块，在不同时间训练不同模块：

```python
class DSPyScheduler:
    def __init__(
        self,
        traces_dir: str = "traces",
        model_dir: str = "models",
        global_train_interval: int = 1800,
    ):
        self.traces_dir = Path(traces_dir)
        self.model_dir = Path(model_dir)
        self.global_train_interval = global_train_interval

    def _get_next_module(self) -> Optional[str]:
        modules = list(MODULE_CONFIGS.keys())
        # 轮询下一个模块

    def _should_train_module(self, module_name: str) -> tuple[bool, str]:
        cfg = MODULE_CONFIGS[module_name]
        state = self._get_module_state(module_name)
        # 检查是否需要训练

    def _train_module(self, module_name: str) -> bool:
        # 训练指定模块并保存

    def run(self):
        while self._running:
            module_to_train = self._get_next_module()
            if self._should_train_module(module_to_train):
                self._train_module(module_to_train)
            time.sleep(self.global_train_interval)
```

### 5.3 训练时机

每个模块独立判断是否需要训练：

| 模块 | 最小 Traces | 最小新 Traces | 训练间隔 |
|------|-------------|---------------|----------|
| `strategy_selector` | 50 | 10 | 1h |
| `initial_tier_selector` | 30 | 5 | 2h |
| `selector_extractor` | 20 | 5 | 30min |
| `block_detector` | 30 | 5 | 1h |
| `threshold_optimizer` | 20 | 5 | 30min |
| `url_discoverer` | 15 | 3 | 1h |
| `human_behavior_generator` | 10 | 3 | 2h |
| `profile_generator` | 10 | 3 | 2h |

### 5.4 模型文件

每个模块保存两个文件：
- `{module_name}.pkl` - 训练好的模型
- `{module_name}_version.json` - 版本信息

```
models/
├── strategy_selector.pkl
├── strategy_selector_version.json
├── initial_tier_selector.pkl
├── initial_tier_selector_version.json
├── selector_extractor.pkl
├── selector_extractor_version.json
└── ...
```

### 5.5 热更新机制

TierStrategyMiddleware 检测模型版本变化时自动热更新：

```python
def _get_strategy_selector(self):
    version_file = Path(self._model_dir) / "strategy_selector_version.json"
    model_file = Path(self._model_dir) / "strategy_selector.pkl"

    if version_file.exists() and model_file.exists():
        with open(version_file, "r") as f:
            version_info = json.load(f)
        current_version = version_info.get("version", 0)

        if current_version > self._current_model_version:
            with open(model_file, "rb") as f:
                self._strategy_selector = pickle.load(f)
            self._current_model_version = current_version
```

### 5.6 CLI 使用

```bash
# 启动后台训练调度器
python -m ai_crawler.core.dspy_scheduler

# 查看所有模块训练状态
python -m ai_crawler.core.dspy_scheduler --status

# 训练所有模块（单次）
python -m ai_crawler.core.dspy_scheduler --train-once

# 训练指定模块
python -m ai_crawler.core.dspy_scheduler --module strategy_selector --train-once
```

---

## 6. LLM 调用详情

### 6.1 SelectorExtractor（CSS Selector 生成）

**用途**: 为每个网站的每个页面类型生成 CSS 选择器，用于提取产品数据

**触发条件**:
- 首次爬取某个站点的某个页面类型（search/detail/category）
- 缓存过期（TTL 24小时）
- 显式传入 `force_regenerate=True`

**缓存策略**:
| 属性 | 值 |
|------|---|
| 缓存 Key | `site:page_type`（如 `amazon:search`） |
| TTL | 24 小时（86400 秒） |
| 缓存位置 | 内存 + 磁盘持久化 |
| 持久化路径 | `site_configs/{site}/{page_type}.json` |

**三级回退**:
```
1. 内存缓存有效？ → 直接返回
2. 磁盘模板存在？ → 加载到内存并返回
3. 调用 DSPy 生成 → 保存到内存+磁盘并返回
4. DSPy 不可用？ → 硬编码默认选择器
```

**输入**:
- `site`: 站点名称
- `page_type`: 页面类型（search/detail/category）
- `html_sample`: HTML 前 8000 字符

**输出**:
```python
{
    "list_container": "CSS selector",
    "product_selector": "CSS selector",
    "title_selector": "CSS selector",
    "price_selector": "CSS selector",
    "price_fraction_selector": "CSS selector",
    "image_selector": "CSS selector",
    "rating_selector": "CSS selector",
    "review_count_selector": "CSS selector",
    "link_selector": "CSS selector",
    "product_id_attribute": "data-asin"
}
```

---

### 6.2 LLMBlockDetector（Block 类型检测）

**用途**: 检测 HTTP 响应是否被反爬拦截，并识别 Block 类型

**触发条件**:
- 每次 HTTP 响应返回后
- 先查缓存，缓存命中则直接返回

**缓存策略**:
| 属性 | 值 |
|------|---|
| 缓存 Key | `status_code:hash(text[:500])` |
| TTL | 24 小时（代码中定义为 86400 秒）|
| 缓存位置 | 内存 |

**Fallback 策略**:
- DSPy 不可用时，使用启发式规则检测（字符串匹配）

**输入**:
- `status_code`: HTTP 状态码
- `text`: 响应内容前 3000 字符
- `site`: 站点名称

**输出**:
```python
(block_type, reasoning)
# block_type: none/http_403/http_429/http_451/http_timeout/captcha/cloudflare/bot_detected/empty_response/unknown
```

---

### 6.3 ThresholdOptimizer（动态阈值优化）

**用途**: 根据站点历史表现，动态调整请求超时和延迟参数

**触发条件**:
- 该站点的请求数 >= 5
- 显式调用 `suggest_thresholds_via_llm(site, page_type, html_sample)`

**缓存策略**:
| 属性 | 值 |
|------|---|
| 缓存 Key | `site:page_type` |
| TTL | 24 小时（86400 秒） |
| 缓存位置 | 内存 |

**前置条件**:
- `metrics.total_requests >= 5`（请求数不足时用启发式阈值）

**输入**:
- `site`: 站点名称
- `page_type`: 页面类型
- `avg_response_time`: 平均响应时间
- `success_rate`: 成功率
- `total_requests`: 总请求数
- `current_timeout`: 当前超时值
- `current_page_load_timeout`: 当前页面加载超时
- `html_sample`: HTML 前 2000 字符

**输出**:
```python
{
    "request_timeout": float,
    "page_load_timeout": float,
    "delay_after": (min, max),
    "confidence": 0.8,
    "strategy": "llm_suggested",
    "reasoning": str
}
```

---

### 6.4 URLDiscoverer（URL 格式发现）

**用途**: 发现站点的搜索 URL 格式和产品 URL 格式

**触发条件**:
- 首次爬取某个站点
- 缓存过期（TTL 24小时）

**缓存策略**:
| 属性 | 值 |
|------|---|
| 缓存 Key | `site` |
| TTL | 24 小时（86400 秒） |
| 缓存位置 | 内存 |

**Fallback 策略**:
- DSPy 不可用时，使用硬编码的默认 URL 模板

**输入**:
- `site`: 站点名称
- `homepage_html`: 首页 HTML 前 5000 字符

**输出**:
```python
{
    "search_url_pattern": "https://www.amazon.com/s?k={query}",
    "search_param": "k",
    "page_param": "page",
    "product_url_pattern": "https://www.amazon.com/dp/{asin}",
    "uses_js_rendering": bool
}
```

---

### 6.5 HumanBehaviorGenerator（人类滚动行为生成）

**用途**: 生成符合人类浏览习惯的滚动模式

**触发条件**:
- 缓存过期（TTL 1小时）
- 所有站点共享同一个缓存

**缓存策略**:
| 属性 | 值 |
|------|---|
| 缓存 Key | 无（全局单例） |
| TTL | 1 小时（3600 秒） |
| 缓存位置 | 内存（全局单例） |

**Fallback 策略**:
- DSPy 不可用时，使用固定默认滚动模式

**输入**:
- `site`: 站点名称
- `page_type`: 页面类型
- `context`: 上下文信息

**输出**:
```python
{
    "scroll_strategy": "mixed",
    "scroll_phases": [
        {
            "start_y": 0,
            "end_y": 500,
            "speed": "fast",
            "pause_after": 0.2,
            "hover": {"x": 400, "y": 300, "duration": 0.5}
        }
    ],
    "reasoning": "..."
}
```

---

### 6.6 ProfileGenerator（浏览器指纹生成）

**用途**: 生成符合目标站点偏好的浏览器指纹

**触发条件**:
- 首次请求（每个 spider 实例初始化时）
- 缓存过期（TTL 1小时）

**缓存策略**:
| 属性 | 值 |
|------|---|
| 缓存 Key | 无（单例，进程内共享） |
| TTL | 1 小时（3600 秒） |
| 缓存位置 | 内存 |

**Fallback 策略**:
- DSPy 不可用时，使用默认指纹

**输入**:
- `system_facts`: JSON 格式的系统信息（OS、架构、硬件等）

**输出**:
```python
{
    "user_agent": "Mozilla/5.0...",
    "sec_ch_ua_platform": "\"macOS\"",
    "viewport": {"width": 1920, "height": 1080},
    "timezone_id": "America/New_York",
    "locale": "en-US",
    "gpu_vendor": "Apple",
    "gpu_renderer": "Apple M4",
    # ... 更多指纹字段
}
```

---

### 6.7 InitialTierSelector（初始 Tier 选择）

**用途**: 为每个站点的每个页面类型选择合适的初始爬取 Tier

**触发条件**:
- 首次爬取某个站点的某个页面类型
- 缓存过期（TTL 24小时）

**缓存策略**:
| 属性 | 值 |
|------|---|
| 缓存 Key | `site:page_type` |
| TTL | 24 小时（86400 秒） |
| 缓存位置 | 内存（`_initial_tier_cache`） |

**成功 Tier 缓存**:
- 当爬取成功时，会用成功的 Tier 更新 `_successful_tier_cache`
- 下次爬取同一站点同一页面类型时，优先使用成功过的 Tier

**优先级**:
```
1. _successful_tier_cache（有成功记录且未过期）→ 直接用成功的 Tier
2. _initial_tier_cache（有缓存记录且未过期）→ 直接用缓存的初始 Tier
3. 调用 DSPy 生成 → 缓存结果并使用
4. DSPy 不可用 → 使用 get_site_tier() 默认值
```

**输入**:
- `site`: 站点名称
- `page_pattern`: 页面模式（search/category/detail）

**输出**:
```python
{
    "start_tier": 1-8,
    "confidence": "high/medium/low",
    "reasoning": "..."
}
```

---

### 6.8 StrategySelector（Block 后策略选择）

**用途**: 当 Block 发生时，智能推荐下一个重试策略

**触发条件**:
- 每次 Block 发生
- **无缓存** - 每次 Block 都独立决策

**缓存策略**:
| 属性 | 值 |
|------|---|
| 缓存 | **无** |
| 原因 | Block 情况每次都不同，需要实时决策 |

**Fallback 策略**:
- DSPy StrategySelector 失败 → 返回 None → 使用默认 Tier 升级

**输入**:
- `site`: 站点名称
- `page_pattern`: 页面模式
- `block_type`: Block 类型
- `response_snippet`: 响应内容片段（前 500 字符）
- `attempt_history`: 之前尝试过的策略列表（JSON 格式，最多 5 条）

**输出**:
```python
{
    "recommended_strategy": {
        "proxy": "thordata_dedicated",
        "render": "playwright",
        "delay_after": [5, 10],
        "use_cookies": True,
        "change_ua": True,
        "use_human_scroll": True
    },
    "confidence": "high/medium/low",
    "reasoning": "..."
}
```

---

## 7. 缓存策略总表

| 模块 | 缓存 Key | TTL | 持久化 | 特殊说明 |
|------|----------|-----|--------|----------|
| `SelectorExtractor` | `site:page_type` | 24h | ✅ `site_configs/{site}/{page_type}.json` | 三级回退：内存→磁盘→DSPy |
| `LLMBlockDetector` | `status_code:hash(text[:500])` | 24h | ❌ | 先查缓存再决策 |
| `ThresholdOptimizer` | `site:page_type` | 24h | ❌ | 请求数>=5才调用 |
| `URLDiscoverer` | `site` | 24h | ❌ | DSPy失败用硬编码默认值 |
| `HumanBehaviorGenerator` | 全局单例 | 1h | ❌ | 所有站点共享 |
| `ProfileGenerator` | 单例 | 1h | ❌ | 进程内共享 |
| `InitialTierSelector` | `site:page_type` | 24h | ❌ | 成功后会更新 `_successful_tier_cache` |
| `StrategySelector` | 无 | - | ❌ | 每次 Block 都独立决策 |

---

## 8. 输入大小限制

| 模块 | 输入限制 | 原因 |
|------|----------|------|
| `SelectorExtractor` | 8000 chars | CSS 选择器只需结构信息 |
| `BlockDetector` | 3000 chars | Block 检测只需关键特征 |
| `ThresholdOptimizer` | 2000 chars | 性能分析只需摘要 |
| `URLDiscoverer` | 5000 chars | URL 发现只需链接结构 |
| `HumanBehaviorGenerator` | ~500 chars | 只需站点名称和页面类型 |
| `ProfileGenerator` | JSON | 完整的系统信息 |
| `InitialTierSelector` | ~500 chars | 只需站点和页面类型信息 |
| `StrategySelector` | ~500 chars | Block 信息和历史记录 |

---

## 9. 文件索引

| 文件 | 说明 |
|------|------|
| `src/ai_crawler/config.py` | 统一配置 |
| `src/ai_crawler/core/llm/dspy_model.py` | DSPy Signatures + Modules |
| `src/ai_crawler/core/extraction/validators.py` | Pydantic Models + Validators |
| `src/ai_crawler/core/llm/llm_extractor.py` | CSS Selector 生成（业务逻辑） |
| `src/ai_crawler/core/llm/llm_block_detector.py` | Block 检测（业务逻辑） |
| `src/ai_crawler/core/engine/dynamic_thresholds.py` | 动态阈值（业务逻辑） |
| `src/ai_crawler/core/llm/llm_url_discovery.py` | URL 发现（业务逻辑） |
| `src/ai_crawler/browser/human_mouse.py` | 人类行为（业务逻辑） |
| `src/ai_crawler/core/llm/dspy_scheduler.py` | DSPy 训练调度器 |
| `src/ai_crawler/middlewares/tier_strategy.py` | Tier 策略中间件（热更新） |

---

## 10. 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENAI_API_KEY` | LLM API Key | - |
| `OPENAI_BASE_URL` | LLM API Base URL | https://api.openai.com/v1 |
| `MODEL_NAME` | 模型名称 | gpt-4o |
| `LLM_HUMAN_BEHAVIOR_CACHE_TTL` | 人类行为缓存 TTL | 3600 |
| `DSPY_MODEL_DIR` | DSPy 模型保存目录 | models |
| `DSPY_TRAIN_INTERVAL` | 训练检查间隔 | 3600 |
| `DSPY_MIN_TRACES` | 开始训练的最小 trace 数 | 50 |
| `DSPY_MIN_NEW_TRACES` | 触发训练的最小新 trace 数 | 10 |
