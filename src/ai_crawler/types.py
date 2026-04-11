"""Central type definitions for ai_crawler.

This module re-exports all enum types from their canonical locations.
"""

from ai_crawler.core.strategy import ProxyType, RenderType, TierSystem
from ai_crawler.captcha.solver import CaptchaType

__all__ = [
    "CaptchaType",
    "ProxyType",
    "RenderType",
    "TierSystem",
]
