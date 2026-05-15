"""Persist discovered API endpoints to site data directory for reuse across runs.

After Tier 0 (OpenCLI) discovers API endpoints via network_intercept, they are
saved to data/<site>/endpoints.json. On subsequent runs, Tier 1 (curl_cffi)
can hit these URLs directly — no browser needed.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).parent


def _endpoints_path(site: str) -> Path:
    site_dir = DATA_DIR / site
    site_dir.mkdir(parents=True, exist_ok=True)
    return site_dir / "endpoints.json"


def save_endpoints(
    site: str,
    endpoints: list[dict[str, Any]],
    page_pattern: str = "search",
) -> None:
    """Persist discovered API endpoints to data/<site>/endpoints.json.

    Merges with existing entries, deduplicating by url. Old entries are kept
    but marked with lower priority so freshly discovered endpoints take precedence.
    """
    path = _endpoints_path(site)
    existing: list[dict[str, Any]] = []
    existing_urls: set[str] = set()
    if path.exists():
        try:
            existing = json.loads(path.read_text())
            existing_urls = {e["url"] for e in existing if isinstance(e, dict)}
        except (json.JSONDecodeError, KeyError):
            existing = []

    now = time.time()
    new_entries = []
    for ep in endpoints:
        if not isinstance(ep, dict):
            continue
        url = ep.get("url", "")
        if not url or url in existing_urls:
            continue
        existing_urls.add(url)
        new_entries.append({
            "url": url,
            "method": ep.get("method", "GET"),
            "page_pattern": page_pattern,
            "response_type": ep.get("response_type", ""),
            "discovered_at": now,
            "source": "opencli_network_intercept",
        })

    if new_entries:
        existing.extend(new_entries)
        path.write_text(json.dumps(existing, indent=2, ensure_ascii=False))


def load_endpoints(
    site: str,
    page_pattern: str | None = None,
) -> list[dict[str, Any]]:
    """Load saved API endpoints for a site, optionally filtered by page_pattern."""
    path = _endpoints_path(site)
    if not path.exists():
        return []
    try:
        endpoints = json.loads(path.read_text())
        if not isinstance(endpoints, list):
            return []
        if page_pattern:
            endpoints = [e for e in endpoints if e.get("page_pattern") == page_pattern]
        return endpoints
    except (json.JSONDecodeError, OSError):
        return []


def get_best_endpoint(
    site: str,
    page_pattern: str = "search",
) -> dict[str, Any] | None:
    """Return the most recently discovered API endpoint for a site + page pattern."""
    endpoints = load_endpoints(site, page_pattern)
    if not endpoints:
        return None
    endpoints.sort(key=lambda e: e.get("discovered_at", 0), reverse=True)
    return endpoints[0]
