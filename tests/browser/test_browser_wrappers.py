"""Tests for Browser Wrappers - CloakBrowserWrapper, CamoufoxWrapper, SeleniumBaseWrapper."""

import sys
import types

import pytest
from unittest.mock import Mock, MagicMock, patch


def _require_browser_symbol(name: str):
    import ai_crawler.browser as browser_module

    symbol = getattr(browser_module, name)
    if symbol is None:
        pytest.skip(f"{name} unavailable in current environment")
    return symbol


class TestCloakBrowserWrapperInterface:
    """CloakBrowserWrapper should have consistent fetch interface."""

    def test_has_fetch_method(self):
        """CloakBrowserWrapper has fetch() method."""
        CloakBrowserWrapper = _require_browser_symbol("CloakBrowserWrapper")

        wrapper = CloakBrowserWrapper()
        assert hasattr(wrapper, "fetch")
        assert callable(wrapper.fetch)

    def test_has_launch_context_manager(self):
        """CloakBrowserWrapper has launch() context manager."""
        CloakBrowserWrapper = _require_browser_symbol("CloakBrowserWrapper")

        wrapper = CloakBrowserWrapper()
        assert hasattr(wrapper, "launch")
        assert callable(wrapper.launch)

    def test_has_launch_method(self):
        """CloakBrowserWrapper has launch() method."""
        CloakBrowserWrapper = _require_browser_symbol("CloakBrowserWrapper")

        wrapper = CloakBrowserWrapper()
        assert hasattr(wrapper, "launch")
        assert callable(wrapper.launch)

    def test_fetch_accepts_url(self):
        """fetch() accepts url parameter."""
        CloakBrowserWrapper = _require_browser_symbol("CloakBrowserWrapper")

        wrapper = CloakBrowserWrapper()
        assert "url" in wrapper.fetch.__code__.co_varnames


class TestCloakBrowserWrapperInit:
    """CloakBrowserWrapper.__init__ should accept all required parameters."""

    def test_accepts_dynamic_profile(self):
        """Wrapper accepts dynamic_profile parameter."""
        CloakBrowserWrapper = _require_browser_symbol("CloakBrowserWrapper")

        wrapper = CloakBrowserWrapper(dynamic_profile={"locale": "en-US"})
        assert wrapper.dynamic_profile == {"locale": "en-US"}

    def test_accepts_proxy(self):
        """Wrapper accepts proxy parameter."""
        CloakBrowserWrapper = _require_browser_symbol("CloakBrowserWrapper")

        wrapper = CloakBrowserWrapper(proxy="http://proxy:8080")
        assert wrapper.proxy == "http://proxy:8080"

    def test_accepts_wait_selector(self):
        """Wrapper accepts wait_selector parameter."""
        CloakBrowserWrapper = _require_browser_symbol("CloakBrowserWrapper")

        wrapper = CloakBrowserWrapper(wait_selector=".product")
        assert wrapper.wait_selector == ".product"

    def test_accepts_wait_time(self):
        """Wrapper accepts wait_time parameter."""
        CloakBrowserWrapper = _require_browser_symbol("CloakBrowserWrapper")

        wrapper = CloakBrowserWrapper(wait_time=5.0)
        assert wrapper.wait_time == 5.0

    def test_cloakbrowser_keeps_viewport_out_of_launch_kwargs(self):
        CloakBrowserWrapper = _require_browser_symbol("CloakBrowserWrapper")

        wrapper = CloakBrowserWrapper(
            dynamic_profile={"viewport": '{"width": 1280, "height": 720}'}
        )

        captured = {}

        class FakePage:
            def set_viewport_size(self, viewport):
                captured["viewport"] = viewport

            def add_init_script(self, script):
                captured["script"] = script

            def close(self):
                return None

        class FakeBrowser:
            def new_page(self):
                return FakePage()

            def close(self):
                return None

        def fake_launch(**kwargs):
            captured["launch_kwargs"] = kwargs
            return FakeBrowser()

        sys.modules["cloakbrowser"] = types.SimpleNamespace(launch=fake_launch)
        with wrapper.launch() as page:
            pass

        assert "viewport" not in captured["launch_kwargs"]
        assert captured["viewport"] == {"width": 1280, "height": 720}

    def test_accepts_human_scroll(self):
        """Wrapper accepts human_scroll parameter."""
        CloakBrowserWrapper = _require_browser_symbol("CloakBrowserWrapper")

        wrapper = CloakBrowserWrapper(human_scroll=True)
        assert wrapper.human_scroll is True

    def test_defaults_to_empty_dynamic_profile(self):
        """Default dynamic_profile is empty dict."""
        CloakBrowserWrapper = _require_browser_symbol("CloakBrowserWrapper")

        wrapper = CloakBrowserWrapper()
        assert wrapper.dynamic_profile == {}


class TestCamoufoxWrapperInterface:
    """CamoufoxWrapper should have consistent fetch-like interface."""

    def test_has_stealth_page(self):
        """CamoufoxWrapper has stealth_page() method."""
        CamoufoxWrapper = _require_browser_symbol("CamoufoxWrapper")
        FingerprintConfig = _require_browser_symbol("FingerprintConfig")

        wrapper = CamoufoxWrapper(fp=FingerprintConfig(), headless=True)
        assert hasattr(wrapper, "stealth_page")

    def test_parses_authenticated_proxy_for_playwright(self):
        CamoufoxWrapper = _require_browser_symbol("CamoufoxWrapper")
        FingerprintConfig = _require_browser_symbol("FingerprintConfig")

        wrapper = CamoufoxWrapper(
            fp=FingerprintConfig(),
            headless=True,
            proxy="http://user:pass@proxy.example:8080",
        )

        settings = wrapper._playwright_proxy_settings()

        assert settings == {
            "server": "http://proxy.example:8080",
            "username": "user",
            "password": "pass",
        }


class TestSeleniumBaseWrapperInterface:
    """SeleniumBaseWrapper should have consistent fetch interface."""

    def test_has_fetch_method(self):
        """SeleniumBaseWrapper has fetch() method."""
        SeleniumBaseWrapper = _require_browser_symbol("SeleniumBaseWrapper")

        wrapper = SeleniumBaseWrapper()
        assert hasattr(wrapper, "fetch")
        assert callable(wrapper.fetch)

    def test_has_create_driver_method(self):
        """SeleniumBaseWrapper exposes driver creation separately."""
        SeleniumBaseWrapper = _require_browser_symbol("SeleniumBaseWrapper")

        wrapper = SeleniumBaseWrapper()
        assert hasattr(wrapper, "create_driver")
        assert callable(wrapper.create_driver)

    def test_has_close_driver_method(self):
        """SeleniumBaseWrapper exposes driver cleanup separately."""
        SeleniumBaseWrapper = _require_browser_symbol("SeleniumBaseWrapper")

        wrapper = SeleniumBaseWrapper()
        assert hasattr(wrapper, "close_driver")
        assert callable(wrapper.close_driver)

    def test_has_fetch_with_driver_method(self):
        """SeleniumBaseWrapper exposes fetch_with_driver() for future pooling."""
        SeleniumBaseWrapper = _require_browser_symbol("SeleniumBaseWrapper")

        wrapper = SeleniumBaseWrapper()
        assert hasattr(wrapper, "fetch_with_driver")
        assert callable(wrapper.fetch_with_driver)


class TestCloakBrowserWrapperHumanScroll:
    """CloakBrowserWrapper._human_scroll() should implement scrolling."""

    def test_has_human_scroll_method(self):
        """_human_scroll() method exists."""
        CloakBrowserWrapper = _require_browser_symbol("CloakBrowserWrapper")

        wrapper = CloakBrowserWrapper()
        assert hasattr(wrapper, "_human_scroll")


class TestAsyncCloakFetch:
    """async_fetch() should be available from browser module."""

    def test_async_cloak_fetch_exists(self):
        """async_cloak_fetch is exported from browser module."""
        async_cloak_fetch = _require_browser_symbol("async_cloak_fetch")

        assert callable(async_cloak_fetch)


class TestBrowserExports:
    """Browser __init__.py should export all wrappers."""

    def test_exports_camoufox_wrapper(self):
        """CamoufoxWrapper is exported."""
        CamoufoxWrapper = _require_browser_symbol("CamoufoxWrapper")

        assert CamoufoxWrapper is not None

    def test_exports_cloakbrowser_wrapper(self):
        """CloakBrowserWrapper is exported."""
        CloakBrowserWrapper = _require_browser_symbol("CloakBrowserWrapper")

        assert CloakBrowserWrapper is not None

    def test_exports_seleniumbase_wrapper(self):
        """SeleniumBaseWrapper is exported."""
        SeleniumBaseWrapper = _require_browser_symbol("SeleniumBaseWrapper")

        assert SeleniumBaseWrapper is not None

    def test_exports_fingerprint_config(self):
        """FingerprintConfig is exported."""
        FingerprintConfig = _require_browser_symbol("FingerprintConfig")

        assert FingerprintConfig is not None

    def test_exports_human_mouse_controller(self):
        """HumanMouseController is exported."""
        from ai_crawler.browser import HumanMouseController

        assert HumanMouseController is not None
