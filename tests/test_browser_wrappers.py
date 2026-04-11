"""Tests for Browser Wrappers - CloakBrowserWrapper, CamoufoxWrapper, SeleniumBaseWrapper."""

import pytest
from unittest.mock import Mock, MagicMock, patch


class TestCloakBrowserWrapperInterface:
    """CloakBrowserWrapper should have consistent fetch interface."""

    def test_has_fetch_method(self):
        """CloakBrowserWrapper has fetch() method."""
        from ai_crawler.browser import CloakBrowserWrapper

        wrapper = CloakBrowserWrapper()
        assert hasattr(wrapper, "fetch")
        assert callable(wrapper.fetch)

    def test_has_launch_context_manager(self):
        """CloakBrowserWrapper has launch() context manager."""
        from ai_crawler.browser import CloakBrowserWrapper

        wrapper = CloakBrowserWrapper()
        assert hasattr(wrapper, "launch")
        assert callable(wrapper.launch)

    def test_has_launch_method(self):
        """CloakBrowserWrapper has launch() method."""
        from ai_crawler.browser import CloakBrowserWrapper

        wrapper = CloakBrowserWrapper()
        assert hasattr(wrapper, "launch")
        assert callable(wrapper.launch)

    def test_fetch_accepts_url(self):
        """fetch() accepts url parameter."""
        from ai_crawler.browser import CloakBrowserWrapper

        wrapper = CloakBrowserWrapper()
        assert "url" in wrapper.fetch.__code__.co_varnames


class TestCloakBrowserWrapperInit:
    """CloakBrowserWrapper.__init__ should accept all required parameters."""

    def test_accepts_dynamic_profile(self):
        """Wrapper accepts dynamic_profile parameter."""
        from ai_crawler.browser import CloakBrowserWrapper

        wrapper = CloakBrowserWrapper(dynamic_profile={"locale": "en-US"})
        assert wrapper.dynamic_profile == {"locale": "en-US"}

    def test_accepts_proxy(self):
        """Wrapper accepts proxy parameter."""
        from ai_crawler.browser import CloakBrowserWrapper

        wrapper = CloakBrowserWrapper(proxy="http://proxy:8080")
        assert wrapper.proxy == "http://proxy:8080"

    def test_accepts_wait_selector(self):
        """Wrapper accepts wait_selector parameter."""
        from ai_crawler.browser import CloakBrowserWrapper

        wrapper = CloakBrowserWrapper(wait_selector=".product")
        assert wrapper.wait_selector == ".product"

    def test_accepts_wait_time(self):
        """Wrapper accepts wait_time parameter."""
        from ai_crawler.browser import CloakBrowserWrapper

        wrapper = CloakBrowserWrapper(wait_time=5.0)
        assert wrapper.wait_time == 5.0

    def test_accepts_human_scroll(self):
        """Wrapper accepts human_scroll parameter."""
        from ai_crawler.browser import CloakBrowserWrapper

        wrapper = CloakBrowserWrapper(human_scroll=True)
        assert wrapper.human_scroll is True

    def test_defaults_to_empty_dynamic_profile(self):
        """Default dynamic_profile is empty dict."""
        from ai_crawler.browser import CloakBrowserWrapper

        wrapper = CloakBrowserWrapper()
        assert wrapper.dynamic_profile == {}


class TestCamoufoxWrapperInterface:
    """CamoufoxWrapper should have consistent fetch-like interface."""

    def test_has_stealth_page(self):
        """CamoufoxWrapper has stealth_page() method."""
        from ai_crawler.browser import CamoufoxWrapper, FingerprintConfig

        wrapper = CamoufoxWrapper(fp=FingerprintConfig(), headless=True)
        assert hasattr(wrapper, "stealth_page")


class TestSeleniumBaseWrapperInterface:
    """SeleniumBaseWrapper should have consistent fetch interface."""

    def test_has_fetch_method(self):
        """SeleniumBaseWrapper has fetch() method."""
        from ai_crawler.browser import SeleniumBaseWrapper

        wrapper = SeleniumBaseWrapper()
        assert hasattr(wrapper, "fetch")
        assert callable(wrapper.fetch)


class TestCloakBrowserWrapperHumanScroll:
    """CloakBrowserWrapper._human_scroll() should implement scrolling."""

    def test_has_human_scroll_method(self):
        """_human_scroll() method exists."""
        from ai_crawler.browser import CloakBrowserWrapper

        wrapper = CloakBrowserWrapper()
        assert hasattr(wrapper, "_human_scroll")


class TestAsyncCloakFetch:
    """async_fetch() should be available from browser module."""

    def test_async_cloak_fetch_exists(self):
        """async_cloak_fetch is exported from browser module."""
        from ai_crawler.browser import async_cloak_fetch

        assert callable(async_cloak_fetch)


class TestBrowserExports:
    """Browser __init__.py should export all wrappers."""

    def test_exports_camoufox_wrapper(self):
        """CamoufoxWrapper is exported."""
        from ai_crawler.browser import CamoufoxWrapper

        assert CamoufoxWrapper is not None

    def test_exports_cloakbrowser_wrapper(self):
        """CloakBrowserWrapper is exported."""
        from ai_crawler.browser import CloakBrowserWrapper

        assert CloakBrowserWrapper is not None

    def test_exports_seleniumbase_wrapper(self):
        """SeleniumBaseWrapper is exported."""
        from ai_crawler.browser import SeleniumBaseWrapper

        assert SeleniumBaseWrapper is not None

    def test_exports_fingerprint_config(self):
        """FingerprintConfig is exported."""
        from ai_crawler.browser import FingerprintConfig

        assert FingerprintConfig is not None

    def test_exports_human_mouse_controller(self):
        """HumanMouseController is exported."""
        from ai_crawler.browser import HumanMouseController

        assert HumanMouseController is not None
