"""Base browser wrapper interface and common types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generator


@dataclass
class BrowserConfig:
    """Common configuration for all browser wrappers.

    Attributes:
        proxy: Proxy URL (e.g., "http://user:pass@host:port")
        headless: Run browser in headless mode
        wait_time: Seconds to wait after page load
        human_scroll: Enable human-like scrolling behavior
        dynamic_profile: Dynamic fingerprint/profile settings
    """

    proxy: str | None = None
    headless: bool = True
    wait_time: float = 2.0
    human_scroll: bool = False
    dynamic_profile: dict[str, Any] = field(default_factory=dict)


class BaseWrapper(ABC):
    """Abstract base class for browser wrappers.

    All tier wrappers must implement the `fetch` method which returns
    a tuple of (html_content, status_code).

    Optional context manager protocol (`launch`, `stealth_page`) may be
    implemented by wrappers that support it.

    Example:
        >>> class MyWrapper(BaseWrapper):
        ...     def fetch(self, url: str) -> tuple[str, int]:
        ...         ...
    """

    def __init__(
        self,
        proxy: str | None = None,
        headless: bool = True,
        wait_time: float = 2.0,
        human_scroll: bool = False,
        dynamic_profile: dict[str, Any] | None = None,
    ):
        self.proxy = proxy
        self.headless = headless
        self.wait_time = wait_time
        self.human_scroll = human_scroll
        self.dynamic_profile = dynamic_profile or {}

    @abstractmethod
    def fetch(self, url: str) -> tuple[str, int]:
        """Fetch a URL and return (html_content, status_code).

        Args:
            url: The URL to fetch.

        Returns:
            A tuple of (page HTML content, HTTP status code).
            On error, return (error_message, 0).
        """
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(proxy={self.proxy})"
