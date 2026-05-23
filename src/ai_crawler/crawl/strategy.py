"""Adaptive escalation engine — replaces pre-configured tier tables.

Instead of pre-generating all strategy combinations and ranking them,
the engine starts cheap and escalates specific dimensions based on the
block type detected.
"""

from __future__ import annotations

from ai_crawler.core.types import CrawlPolicy, ProxyType, RenderType


# Ordered from cheapest/fastest to strongest/slowest.
# Fields: (render, use_cookies, change_ua, use_human_scroll, delay_after)
_LADDER: list[dict] = [
    {"render": RenderType.NONE, "cookies": False, "ua": False, "scroll": False, "delay": (2, 5), "proxy": ProxyType.THORDATA_DEDICATED},
    {"render": RenderType.CLOUDSCRAPER, "cookies": True, "ua": False, "scroll": False, "delay": (3, 6), "proxy": ProxyType.THORDATA_DEDICATED},
    {"render": RenderType.PLAYWRIGHT, "cookies": True, "ua": True, "scroll": True, "delay": (3, 8), "proxy": ProxyType.THORDATA_DEDICATED},
    {"render": RenderType.CAMOUFOX, "cookies": True, "ua": True, "scroll": True, "delay": (3, 8), "proxy": ProxyType.THORDATA_DEDICATED},
    {"render": RenderType.CLOUDERA, "cookies": True, "ua": True, "scroll": True, "delay": (5, 10), "proxy": ProxyType.THORDATA_DEDICATED},
    {"render": RenderType.SELENIUMBASE, "cookies": True, "ua": True, "scroll": True, "delay": (5, 10), "proxy": ProxyType.THORDATA_DEDICATED},
    {"render": RenderType.CLOAKBROWSER, "cookies": True, "ua": True, "scroll": True, "delay": (5, 10), "proxy": ProxyType.DIRECT, "interactive_search": True},
]

MAX_LEVEL = len(_LADDER) - 1

# Which dimension to escalate when this block type is encountered.
_BLOCK_DIMENSION: dict[str, str] = {
    "ip_blocked": "proxy",
    "http_403": "proxy",
    "http_429": "proxy",
    "http_451": "proxy",
    "http_timeout": "proxy",
    "cloudflare": "render",
    "captcha": "render",
    "bot_detected": "both",
    "soft_suspicion": "behavior",
    "empty_response": "render",
    "human_behavior": "behavior",
    "interactive_failed": "render",
}

# Minimum render level to jump to for each block type at a given current level.
# (current_level, block_type) → target_level. Used when no WAF vendor is detected.
_BLOCK_JUMP: dict[tuple[int, str], int] = {
    # bot_detected at low levels → need a real browser
    (0, "bot_detected"): 2,
    (1, "bot_detected"): 2,
    # cloudflare at low levels → need camoufox or better
    (0, "cloudflare"): 3,
    (1, "cloudflare"): 3,
    (2, "cloudflare"): 3,
    # captcha → need JS-capable renderer
    (0, "captcha"): 2,
    (1, "captcha"): 2,
    # empty response at low levels → try with browser
    (0, "empty_response"): 2,
    (1, "empty_response"): 2,
    # http 403 at low levels → IP blocked, need browser + fresh IP
    (0, "http_403"): 2,
    (1, "http_403"): 3,
    (2, "http_403"): 4,
    # http 429 at low levels → rate limited, need browser + fresh IP
    (0, "http_429"): 2,
    (1, "http_429"): 3,
}


def build_policy(level: int, proxy_type: ProxyType | None = None) -> CrawlPolicy:
    """Build a CrawlPolicy from an escalation level."""
    if level < 0 or level > MAX_LEVEL:
        level = max(0, min(level, MAX_LEVEL))
    cfg = _LADDER[level]
    if proxy_type is None:
        proxy_type = cfg.get("proxy", ProxyType.THORDATA_DEDICATED)
    return CrawlPolicy(
        tier=level,
        proxy=proxy_type,
        render=cfg["render"],
        delay_after=cfg["delay"],
        use_cookies=cfg["cookies"],
        change_ua=cfg["ua"],
        use_human_scroll=cfg["scroll"],
        use_interactive_search=cfg.get("interactive_search", False),
    )


def level_for_render(render: RenderType, human_scroll: bool = False) -> int:
    """Find the escalation level that matches a given render + scroll combination."""
    for i, cfg in enumerate(_LADDER):
        if cfg["render"] == render and cfg["scroll"] == human_scroll:
            return i
        if cfg["render"] == render:
            return i
    return 0


def escalate_dimension(block_type: str) -> str:
    """Determine which dimension to escalate based on block type."""
    return _BLOCK_DIMENSION.get(block_type, "render")


def next_level(current_level: int, block_type: str, ip_retries_remaining: int) -> int | None:
    """Return the next escalation level, or None if already at max.

    Proxy-related blocks don't escalate the level if IP retries remain —
    they rotate the IP at the same level instead.

    Non-WAF blocks use _BLOCK_JUMP to skip ineffective levels (e.g.
    bot_detected at level 0 jumps straight to level 2).
    """
    dim = _BLOCK_DIMENSION.get(block_type, "render")
    if dim == "proxy" and ip_retries_remaining > 0:
        return current_level  # stay, rotate IP
    if current_level >= MAX_LEVEL:
        return None
    jump_to = _BLOCK_JUMP.get((current_level, block_type))
    if jump_to is not None:
        return min(jump_to, MAX_LEVEL)
    return current_level + 1
