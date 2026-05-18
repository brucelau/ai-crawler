from __future__ import annotations

"""WAF detection — maps detected WAF to minimum viable render level.

Used by the planner to skip ineffective strategies. For example, if Cloudflare is
detected, skip httpx (0) and cloudscraper (1) — they'll never pass CF challenges.
"""

from ai_crawler.antidetect.handler import BlockAnalyzer
from ai_crawler.crawl.strategy import MAX_LEVEL


# Minimum render level required to bypass each WAF type.
# Levels: 0=httpx, 1=cloudscraper, 2=playwright, 3=camoufox, 4=cloudflare_uc,
#         5=seleniumbase, 6=cloakbrowser
WAF_MIN_LEVEL: dict[str, int] = {
    "cloudflare": 3,
    "datadome": 2,
    "imperva": 2,
    "perimeterx": 2,
    "akamai": 2,
    "aws_waf": 1,
    "f5_asm": 1,
    "sucuri": 1,
    "reblaze": 1,
    "fortiweb": 1,
    "radware": 1,
    "incapsula": 1,
}

_WAF_JUMP: dict[tuple[int, str], int] = {
    (0, "cloudflare"): 3,
    (1, "cloudflare"): 3,
    (2, "cloudflare"): 3,
    (0, "datadome"): 2,
    (1, "datadome"): 2,
    (0, "perimeterx"): 2,
    (1, "perimeterx"): 2,
    (0, "imperva"): 2,
    (1, "imperva"): 2,
    (0, "akamai"): 2,
    (1, "akamai"): 2,
}


def min_level_for_waf(waf_type: str) -> int:
    return WAF_MIN_LEVEL.get(waf_type, 0)


def jump_level(current_level: int, waf_type: str) -> int:
    target = _WAF_JUMP.get((current_level, waf_type))
    if target is not None:
        return min(target, MAX_LEVEL)
    if current_level >= MAX_LEVEL:
        return current_level
    return current_level + 1


def detect_waf(html: str, headers: dict) -> str:
    """One-shot WAF detection from response content and headers."""
    analysis = BlockAnalyzer.analyze(html, status_code=None, headers=headers)
    return analysis.waf_type
