"""Site adapter registry — Command base class with register decorator.

Each site adapter is a Command subclass that encapsulates URL templates,
extraction logic, and strategy hints for a specific page pattern on a site.
"""

from __future__ import annotations

from typing import Any

from ai_crawler.core.types import Product

_COMMANDS: dict[tuple[str, str], type[Command]] = {}


def register(site: str, command: str):
    """Decorator to register a Command subclass for (site, command)."""
    def decorator(cls):
        _COMMANDS[(site, command)] = cls
        return cls
    return decorator


def get_command(site: str, command: str) -> type[Command] | None:
    return _COMMANDS.get((site, command))


def list_sites() -> list[str]:
    return sorted(set(site for site, _ in _COMMANDS))


def list_commands(site: str) -> list[str]:
    return [cmd for s, cmd in _COMMANDS if s == site]


class Command:
    """Base class for site-specific adapters.

    Subclasses must define: site, command, url_template, extract()
    Subclasses may override: start_level, extract_dynamic, extract_api, pagination

    When api_url_template is set, the engine fetches the API response through
    the proxy and passes it to extract_api(data), avoiding adapter-side HTTP.
    """

    site: str = ""
    command: str = ""
    url_template: str = ""
    api_url_template: str = ""

    # Strategy hints — higher = more aggressive anti-detection
    start_level: int = 0
    ip_retries: int = 3

    # Pagination: "query_param" | "scroll" | "click" | None
    pagination: str | None = None
    page_param: str = "page"

    def build_url(self, **kwargs) -> str:
        return self.url_template.format(**kwargs)

    def build_api_url(self, **kwargs) -> str:
        """Build the API URL from api_url_template, filling placeholders.

        Override build_api_params() to add query parameters.
        """
        return self.api_url_template.format(**kwargs)

    def build_api_params(self, query: str) -> dict:
        """Override to return dict of query params for the API call."""
        return {}

    def extract(self, html: str, url: str) -> list[Product]:
        raise NotImplementedError

    async def extract_dynamic(self, page: Any, url: str) -> list[Product]:
        """Override for sites that need live browser JS evaluation."""
        return self.extract("", url)

    def extract_api(self, data: dict) -> list[Product]:
        """Override for sites with structured API responses."""
        return []

    @staticmethod
    def _normalize_price(text: str) -> str:
        import re
        m = re.search(r"[\d,]+\.?\d*", text.replace(",", ""))
        return m.group() if m else ""
