from __future__ import annotations

import json
from urllib.parse import urlparse

AD_SCRIPT_HOST_MARKERS = (
    "doubleclick.net",
    "googlesyndication.com",
    "adservice.google.com",
    "googleadservices.com",
    "adnxs.com",
    "criteo.com",
    "criteo.net",
    "taboola.com",
    "outbrain.com",
    "ads-twitter.com",
    "amazon-adsystem.com",
    "adsrvr.org",
)


def build_headers(dynamic_profile: dict) -> dict:
    if not dynamic_profile.get("change_ua", True):
        return {}

    ua = dynamic_profile.get(
        "user_agent",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )
    platform = dynamic_profile.get("sec_ch_ua_platform", '"macOS"')
    ch_ua = dynamic_profile.get(
        "sec_ch_ua", '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"'
    )

    return {
        "User-Agent": ua,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "sec-ch-ua": ch_ua,
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": platform,
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
    }


def stable_key(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, default=str)


def structured_proxy_settings(proxy: str | None) -> dict | None:
    if not proxy:
        return None
    parsed = urlparse(proxy)
    if not parsed.scheme or not parsed.hostname or not parsed.port:
        return {"server": proxy}
    settings = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
    if parsed.username:
        settings["username"] = parsed.username
    if parsed.password:
        settings["password"] = parsed.password
    return settings


def browser_error_html(title: str, message: str) -> str:
    return f"<html><head><title>{title}</title></head><body>{message}</body></html>"


def should_block_script(url: str) -> bool:
    lowered = url.lower()
    return any(marker in lowered for marker in AD_SCRIPT_HOST_MARKERS)
