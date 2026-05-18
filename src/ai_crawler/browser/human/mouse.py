"""Human-like mouse trajectory generator using cubic Bezier curves.

Simulates realistic human mouse movement:
- Non-linear speed (slow at start/end, fast in middle)
- Random curve variation using Bezier control points
- Micro-jitter to simulate hand tremor

Also provides unified adapters for different browser automation libraries.
"""

from __future__ import annotations

import math
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator, TYPE_CHECKING

from ai_crawler.core.config import config
from ai_crawler.extraction.analysis.validators import validate_human_behavior

if TYPE_CHECKING:
    pass


@dataclass
class Point:
    x: float
    y: float


def _cubic_bezier(t: float, p0: float, p1: float, p2: float, p3: float) -> float:
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t**2 * p2 + t**3 * p3


def _bezier_point(t: float, start: Point, cp1: Point, cp2: Point, end: Point) -> Point:
    return Point(
        x=_cubic_bezier(t, start.x, cp1.x, cp2.x, end.x),
        y=_cubic_bezier(t, start.y, cp1.y, cp2.y, end.y),
    )


def _ease_in_out(t: float) -> float:
    if t < 0.5:
        return 2 * t * t
    return 1 - (-2 * t + 2) ** 2 / 2


def _human_ease(t: float) -> float:
    curve = random.choice(["ease_in_out", "ease_out", "ease_in", "w_curve"])
    if curve == "ease_in_out":
        return _ease_in_out(t)
    elif curve == "ease_out":
        return 1 - (1 - t) ** random.uniform(1.5, 3.0)
    elif curve == "ease_in":
        return t ** random.uniform(1.5, 3.0)
    else:
        delta = abs(t - 0.5)
        return (
            0.5 - delta + (delta * 2) ** random.uniform(0.7, 1.3) * 0.5
            if t < 0.5
            else 0.5 + delta * 2 ** random.uniform(0.7, 1.3) / 2
        )


def generate_human_curve(
    start: tuple[float, float],
    end: tuple[float, float],
    segments: int = 50,
    jitter_std: float = 2.5,
    curve_intensity: float = 0.3,
) -> list[Point]:
    sx, sy = start
    ex, ey = end
    dx = ex - sx
    dy = ey - sy
    dist = math.sqrt(dx * dx + dy * dy)

    if dist < 5:
        return [Point(sx, sy), Point(ex, ey)]

    cp_offset = dist * curve_intensity
    angle = math.atan2(dy, dx)
    perp_angle = angle + math.pi / 2

    cp1x = (
        sx
        + dx * random.uniform(0.15, 0.40)
        + math.cos(perp_angle) * random.uniform(-cp_offset, cp_offset)
    )
    cp1y = (
        sy
        + dy * random.uniform(0.15, 0.40)
        + math.sin(perp_angle) * random.uniform(-cp_offset, cp_offset)
    )
    cp2x = (
        sx
        + dx * random.uniform(0.60, 0.85)
        + math.cos(perp_angle) * random.uniform(-cp_offset, cp_offset)
    )
    cp2y = (
        sy
        + dy * random.uniform(0.60, 0.85)
        + math.sin(perp_angle) * random.uniform(-cp_offset, cp_offset)
    )

    start_pt = Point(sx, sy)
    end_pt = Point(ex, ey)

    points = []
    for i in range(segments + 1):
        t = i / segments
        eased_t = _human_ease(t)
        pt = _bezier_point(eased_t, start_pt, Point(cp1x, cp1y), Point(cp2x, cp2y), end_pt)
        jitter_x = random.gauss(0, jitter_std)
        jitter_y = random.gauss(0, jitter_std)
        points.append(Point(pt.x + jitter_x, pt.y + jitter_y))

    points[-1] = Point(ex, ey)
    return points


def scroll_human(
    page,
    start_y: int = 0,
    end_y: int = 800,
    step: int = 100,
    pause_mean: float = 0.08,
    pause_std: float = 0.04,
) -> None:
    for y in range(start_y, end_y, step):
        sign = 1 if end_y > start_y else -1
        curve = generate_human_curve((0, 0), (random.randint(100, 300), sign * step))
        for pt in curve:
            page.mouse.move(int(pt.x), int(pt.y + y - start_y))
        time.sleep(max(0.01, random.gauss(pause_mean, pause_std)))


class HumanMouseController:
    def __init__(
        self,
        page,
        min_step_delay: float = 0.008,
        max_step_delay: float = 0.035,
        jitter_std: float = 2.5,
        curve_intensity: float = 0.3,
    ):
        self.page = page
        self.min_step_delay = min_step_delay
        self.max_step_delay = max_step_delay
        self.jitter_std = jitter_std
        self.curve_intensity = curve_intensity

    def move_to(self, x: int, y: int, duration: float | None = None) -> None:
        start = (random.randint(0, 100), random.randint(0, 100))
        end = (x, y)
        if duration is None:
            dist = math.sqrt((x - start[0]) ** 2 + (y - start[1]) ** 2)
            duration = max(0.3, min(2.5, dist / 500))

        points = generate_human_curve(
            start,
            end,
            segments=max(20, int(duration * 60)),
            jitter_std=self.jitter_std,
            curve_intensity=self.curve_intensity,
        )

        for pt in points:
            self.page.mouse.move(int(pt.x), int(pt.y))
            time.sleep(random.uniform(self.min_step_delay, self.max_step_delay))

    def click(self, x: int, y: int) -> None:
        self.move_to(x, y)
        pause = random.gauss(0.12, 0.05)
        time.sleep(max(0.01, pause))
        self.page.mouse.click(x, y)

    def hover(self, x: int, y: int) -> None:
        self.move_to(x, y)

    def human_scroll(self, start_y: int = 0, end_y: int = 800, step: int = 100) -> None:
        scroll_human(self.page, start_y, end_y, step)


class MouseAdapter(ABC):
    @abstractmethod
    def move(self, x: int, y: int) -> None:
        pass

    @abstractmethod
    def scroll(self, x: int, y: int) -> None:
        pass


class PlaywrightMouseAdapter(MouseAdapter):
    def __init__(self, page):
        self._page = page

    def move(self, x: int, y: int) -> None:
        self._page.mouse.move(x, y)

    def scroll(self, x: int, y: int) -> None:
        self._page.mouse.wheel(0, y)


class SeleniumMouseAdapter(MouseAdapter):
    def __init__(self, driver):
        self._driver = driver

    def move(self, x: int, y: int) -> None:
        from selenium.webdriver.common.action_chains import ActionChains

        ActionChains(self._driver).move_by_offset(x, y).perform()

    def scroll(self, x: int, y: int) -> None:
        self._driver.execute_script(f"window.scrollBy(0, {y})")


class CloakBrowserMouseAdapter(MouseAdapter):
    def __init__(self, page):
        self._page = page

    def move(self, x: int, y: int) -> None:
        self._page.mouse.move(x, y)

    def scroll(self, x: int, y: int) -> None:
        self._page.mouse.wheel(0, y)


class UnifiedHumanBehavior:
    def __init__(
        self,
        adapter: MouseAdapter,
        min_step_delay: float = 0.008,
        max_step_delay: float = 0.035,
        jitter_std: float = 2.5,
        curve_intensity: float = 0.3,
    ):
        self._adapter = adapter
        self._min_step_delay = min_step_delay
        self._max_step_delay = max_step_delay
        self._jitter_std = jitter_std
        self._curve_intensity = curve_intensity

    def move_to(self, x: int, y: int, duration: float | None = None) -> None:
        start_x = random.randint(0, 100)
        start_y = random.randint(0, 100)
        end_x, end_y = x, y

        if duration is None:
            dist = math.sqrt((end_x - start_x) ** 2 + (end_y - start_y) ** 2)
            duration = max(0.3, min(2.5, dist / 500))

        points = generate_human_curve(
            (start_x, start_y),
            (end_x, end_y),
            segments=max(20, int(duration * 60)),
            jitter_std=self._jitter_std,
            curve_intensity=self._curve_intensity,
        )

        for pt in points:
            self._adapter.move(int(pt.x), int(pt.y))
            time.sleep(random.uniform(self._min_step_delay, self._max_step_delay))

    def scroll(self, start_y: int = 0, end_y: int = 1500, step: int = 100) -> None:
        for y in range(start_y, end_y, step):
            curve = generate_human_curve(
                (random.randint(200, 600), 0),
                (random.randint(200, 600), step),
                segments=30,
                jitter_std=self._jitter_std,
                curve_intensity=self._curve_intensity,
            )
            for pt in curve:
                self._adapter.move(int(pt.x), int(pt.y))
                self._adapter.scroll(0, int(pt.y))
            time.sleep(random.uniform(0.05, 0.15))

    def human_scroll(self, start_y: int = 0, end_y: int = 1500) -> None:
        self.scroll(start_y, end_y)


class LLMHumanBehavior:
    def __init__(
        self, api_key: str | None = None, base_url: str | None = None, model: str | None = None
    ):
        from ai_crawler.core.config import config

        self._api_key = api_key or config.OPENAI_API_KEY
        self._base_url = base_url or config.OPENAI_BASE_URL
        self._model = model or config.MODEL_NAME
        self._client = None

    def _get_client(self):
        if not self._client and self._api_key:
            from openai import OpenAI

            self._client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client

    def generate_pattern(self, site: str, page_type: str = "search", context: str = "") -> dict:
        client = self._get_client()
        if not client:
            return self._default_pattern()

        prompt = f"""为网页爬虫生成人类浏览行为模式。

网站: {site}
页面类型: {page_type}
上下文: {context}

你是一个用户行为专家。用户浏览电商网站时有以下特点：
- 不是匀速滚动，而是有时快有时慢
- 会在感兴趣的区域停留
- 鼠标会在某些元素上悬停
- 滚动模式反映用户的阅读兴趣

请生成一个 JSON 行为模式：
{{
  "scroll_strategy": "mixed",  // gradual(缓慢浏览) | burst(快速扫描) | mixed(混合)
  "scroll_phases": [
    {{
      "start_y": 0,
      "end_y": 500,
      "speed": "fast",  // fast | medium | slow
      "pause_after": 0.2,  // 滚动完成后的暂停(秒)
      "hover": {{"x": 400, "y": 300, "duration": 0.5}}  // 可选悬停动作
    }},
    {{
      "start_y": 500,
      "end_y": 1000,
      "speed": "slow",
      "pause_after": 0.5
    }}
  ],
  "reasoning": "为什么用户会这样浏览"
}}

要求：
- scroll_phases 的 end_y 应该覆盖整个页面(通常是 1500-3000px)
- speed 影响滚动步长：fast=200-300px, medium=100-150px, slow=50-80px
- 至少3个滚动阶段，覆盖不同页面区域
- hover 动作在 slow 阶段更常见

直接输出 JSON，不要有其他内容。"""

        try:
            response = client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=800,
            )
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            import json

            return json.loads(content)
        except Exception:
            return self._default_pattern()

    def _default_pattern(self) -> dict:
        return {
            "scroll_strategy": "mixed",
            "scroll_phases": [
                {"start_y": 0, "end_y": 400, "speed": "fast", "pause_after": 0.1, "hover": None},
                {
                    "start_y": 400,
                    "end_y": 1000,
                    "speed": "slow",
                    "pause_after": 0.3,
                    "hover": {"x": 400, "y": 600, "duration": 0.5},
                },
                {
                    "start_y": 1000,
                    "end_y": 1800,
                    "speed": "medium",
                    "pause_after": 0.2,
                    "hover": None,
                },
                {
                    "start_y": 1800,
                    "end_y": 2500,
                    "speed": "fast",
                    "pause_after": 0.1,
                    "hover": None,
                },
            ],
            "reasoning": "默认混合模式",
        }

    def execute_pattern(self, adapter: MouseAdapter, pattern: dict) -> None:
        behavior = UnifiedHumanBehavior(adapter)
        scroll_phases = pattern.get("scroll_phases", [])
        for phase in scroll_phases:
            start_y = phase.get("start_y", 0)
            end_y = phase.get("end_y", 1500)
            speed = phase.get("speed", "medium")
            pause_after = phase.get("pause_after", 0.2)
            hover = phase.get("hover")

            step_size = {"fast": 200, "medium": 120, "slow": 60}.get(speed, 120)

            if hover:
                behavior.move_to(hover["x"], hover["y"])
                time.sleep(hover["duration"])

            for y in range(start_y, end_y, step_size):
                curve = generate_human_curve(
                    (random.randint(200, 600), y),
                    (random.randint(200, 600), min(y + step_size, end_y)),
                    segments=25,
                    jitter_std=2.5,
                    curve_intensity=0.3,
                )
                for pt in curve:
                    adapter.move(int(pt.x), int(pt.y))
                    time.sleep(0.01)
                adapter.scroll(0, step_size)
                time.sleep(pause_after)

    def human_scroll(self, adapter: MouseAdapter, site: str, page_type: str = "search") -> None:
        pattern = self.get_cached_pattern(site, page_type)
        self.execute_pattern(adapter, pattern)


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
            from ai_crawler.llm.dspy_model import HumanBehaviorGenerator

            self._dspy_generator = HumanBehaviorGenerator()
        return self._dspy_generator

    def _should_refresh(self) -> bool:
        if self._cached_pattern is None:
            return True
        return (time.time() - self._cached_time) > self._cache_ttl

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

    def _default_pattern(self) -> dict:
        return {
            "scroll_strategy": "mixed",
            "scroll_phases": [
                {"start_y": 0, "end_y": 400, "speed": "fast", "pause_after": 0.1, "hover": None},
                {
                    "start_y": 400,
                    "end_y": 1000,
                    "speed": "slow",
                    "pause_after": 0.3,
                    "hover": {"x": 400, "y": 600, "duration": 0.5},
                },
                {
                    "start_y": 1000,
                    "end_y": 1800,
                    "speed": "medium",
                    "pause_after": 0.2,
                    "hover": None,
                },
                {
                    "start_y": 1800,
                    "end_y": 2500,
                    "speed": "fast",
                    "pause_after": 0.1,
                    "hover": None,
                },
            ],
            "reasoning": "默认混合模式",
        }

    def execute_pattern(self, adapter: MouseAdapter, pattern: dict) -> None:
        behavior = UnifiedHumanBehavior(adapter)
        scroll_phases = pattern.get("scroll_phases", [])
        for phase in scroll_phases:
            start_y = phase.get("start_y", 0)
            end_y = phase.get("end_y", 1500)
            speed = phase.get("speed", "medium")
            pause_after = phase.get("pause_after", 0.2)
            hover = phase.get("hover")

            step_size = {"fast": 200, "medium": 120, "slow": 60}.get(speed, 120)

            if hover:
                behavior.move_to(hover["x"], hover["y"])
                time.sleep(hover["duration"])

            for y in range(start_y, end_y, step_size):
                curve = generate_human_curve(
                    (random.randint(200, 600), y),
                    (random.randint(200, 600), min(y + step_size, end_y)),
                    segments=25,
                    jitter_std=2.5,
                    curve_intensity=0.3,
                )
                for pt in curve:
                    adapter.move(int(pt.x), int(pt.y))
                    time.sleep(0.01)
                adapter.scroll(0, step_size)
                time.sleep(pause_after)

    def human_scroll(self, adapter: MouseAdapter, site: str, page_type: str = "search") -> None:
        pattern = self.get_cached_pattern(site, page_type)
        self.execute_pattern(adapter, pattern)
