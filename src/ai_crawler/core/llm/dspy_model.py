from __future__ import annotations

import json

import dspy
from dspy.teleprompt import BootstrapFewShot


class ProfileGenerationSignature(dspy.Signature):
    """Generate a realistic browser fingerprint profile that matches the underlying host OS and hardware."""

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


class DSPyTrainer:
    def __init__(self, traces: list[dict]):
        self.traces = traces

    def build_trainset(self) -> list[dspy.Example]:
        examples = []
        for t in self.traces:
            if not t.get("success"):
                continue
            example = dspy.Example(
                site=t["site"],
                page_pattern=t["page_pattern"],
                block_type=t["block_type"],
                response_snippet=t.get("response_snippet", ""),
                attempt_history=t.get("attempt_history", []),
                recommended_strategy=t.get("recommended_strategy", {}),
                confidence=t.get("confidence", "medium"),
                reasoning=t.get("reasoning", ""),
            ).with_inputs(
                "site", "page_pattern", "block_type", "response_snippet", "attempt_history"
            )
            examples.append(example)
        return examples

    def compile(self, max_demos: int = 8) -> StrategySelector:
        trainset = self.build_trainset()
        if not trainset:
            raise ValueError("No successful traces to train on")

        teleprompter = BootstrapFewShot(
            metric=self._metric,
            max_bootstrapped_demos=max_demos,
        )

        selector = StrategySelector()
        compiled = teleprompter.compile(selector, trainset=trainset)
        return compiled

    def _metric(self, example, prediction, trace=None):
        if prediction.confidence not in ("high", "medium"):
            return 0.0

        s_pred = prediction.recommended_strategy
        s_true = example.recommended_strategy

        if isinstance(s_pred, str):
            return 0.5

        score = 0.0
        if s_pred.get("proxy") == s_true.get("proxy"):
            score += 0.4
        if s_pred.get("render") == s_true.get("render"):
            score += 0.4
        if s_pred.get("change_ua") == s_true.get("change_ua"):
            score += 0.1
        if s_pred.get("use_cookies") == s_true.get("use_cookies"):
            score += 0.1

        return min(score, 1.0)


def load_traces(traces_dir: str) -> list[dict]:
    from pathlib import Path
    import json

    traces = []
    traces_path = Path(traces_dir)
    if not traces_path.exists():
        return []

    for file in traces_path.glob("*.jsonl"):
        with open(file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    traces.append(json.loads(line))
    return traces


def train_dspy_model(traces_dir: str, max_demos: int = 8) -> StrategySelector:
    traces = load_traces(traces_dir)
    if not traces:
        raise ValueError(f"No traces found in {traces_dir}")

    trainer = DSPyTrainer(traces)
    compiled = trainer.compile(max_demos=max_demos)
    return compiled


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


class ThresholdSignature(dspy.Signature):
    site = dspy.InputField()
    page_type = dspy.InputField(desc="Page type: search, detail, or category")
    avg_response_time = dspy.InputField(desc="Average response time in seconds")
    success_rate = dspy.InputField(desc="Success rate as decimal (0.0-1.0)")
    total_requests = dspy.InputField(desc="Total number of requests made")
    current_timeout = dspy.InputField(desc="Current request timeout in seconds")
    current_page_load_timeout = dspy.InputField(desc="Current page load timeout in seconds")
    html_sample = dspy.InputField(
        desc="HTML snippet for page complexity analysis (first 2000 chars)"
    )

    request_timeout = dspy.OutputField(desc="Recommended request timeout in seconds")
    page_load_timeout = dspy.OutputField(desc="Recommended page load timeout in seconds")
    delay_after = dspy.OutputField(
        desc="Min and max delay between requests as JSON list [min, max]"
    )
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


class URLDiscoverySignature(dspy.Signature):
    site = dspy.InputField()
    homepage_html = dspy.InputField(desc="Homepage HTML snippet (first 5000 chars)")

    search_url_pattern = dspy.OutputField(
        desc="Full search URL pattern with {query} placeholder, e.g. https://example.com/search?q={query}"
    )
    search_param = dspy.OutputField(desc="Search parameter name, e.g. q, k, searchTerm")
    page_param = dspy.OutputField(desc="Pagination parameter name, e.g. page, offset")
    product_url_pattern = dspy.OutputField(
        desc="Product URL pattern with {id} or {asin} placeholder"
    )
    uses_js_rendering = dspy.OutputField(
        desc="Whether search results use JavaScript rendering (true/false)"
    )


class URLDiscoverer(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict(URLDiscoverySignature)

    def forward(self, site: str, homepage_html: str):
        return self.predict(site=site, homepage_html=homepage_html)


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
