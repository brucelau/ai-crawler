"""Tests for CloakBrowserWrapper.launch context manager."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from ai_crawler.browser.wrappers.cloakbrowser import CloakBrowserWrapper


class TestCloakBrowserWrapperLaunch:
    """Unit tests for CloakBrowserWrapper.launch."""

    @pytest.fixture
    def wrapper(self):
        return CloakBrowserWrapper(
            proxy=None,
            headless=True,
            wait_time=2.0,
            human_scroll=False,
        )

    def test_launch_yields_page(self, wrapper):
        """launch context manager yields a page and cleans up."""
        mock_page = MagicMock()
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page

        with patch(
            "cloakbrowser.launch",
            return_value=mock_browser,
            create=True,
        ), patch(
            "ai_crawler.browser.wrappers.cloakbrowser.get_fingerprint_script",
            return_value="/* fp */",
        ):
            with wrapper.launch() as page:
                assert page is mock_page
                mock_page.add_init_script.assert_called_once()

            mock_page.close.assert_called_once()
            mock_browser.close.assert_called_once()

    def test_launch_with_proxy(self, wrapper):
        """Proxy URL is parsed and passed to CloakBrowser launch."""
        wrapper.proxy = "http://user:pass@proxy.example.com:8080"
        mock_page = MagicMock()
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page

        with patch(
            "cloakbrowser.launch",
            return_value=mock_browser,
            create=True,
        ) as mock_launch, patch(
            "ai_crawler.browser.wrappers.cloakbrowser.get_fingerprint_script",
            return_value="/* fp */",
        ):
            with wrapper.launch() as page:
                pass

            call_kwargs = mock_launch.call_args[1]
            assert "proxy" in call_kwargs
            assert call_kwargs["proxy"]["server"] == "http://proxy.example.com:8080"
            assert call_kwargs["proxy"]["username"] == "user"
            assert call_kwargs["proxy"]["password"] == "pass"

    def test_launch_with_viewport(self, wrapper):
        """Dynamic profile viewport is applied to page."""
        wrapper.dynamic_profile = {
            "viewport": '{"width": 1280, "height": 720}',
        }
        mock_page = MagicMock()
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page

        with patch(
            "cloakbrowser.launch",
            return_value=mock_browser,
            create=True,
        ), patch(
            "ai_crawler.browser.wrappers.cloakbrowser.get_fingerprint_script",
            return_value="/* fp */",
        ):
            with wrapper.launch() as page:
                pass

            mock_page.set_viewport_size.assert_called_once_with(
                {"width": 1280, "height": 720}
            )

    def test_launch_with_languages_header(self, wrapper):
        """Languages from dynamic_profile are set as HTTP headers."""
        wrapper.dynamic_profile = {
            "languages": '["en-US", "fr-FR"]',
        }
        mock_page = MagicMock()
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page

        with patch(
            "cloakbrowser.launch",
            return_value=mock_browser,
            create=True,
        ), patch(
            "ai_crawler.browser.wrappers.cloakbrowser.get_fingerprint_script",
            return_value="/* fp */",
        ):
            with wrapper.launch() as page:
                pass

            mock_page.set_extra_http_headers.assert_called_once_with(
                {"Accept-Language": "en-US,fr-FR"}
            )

    def test_launch_cleans_up_on_error(self, wrapper):
        """Page and browser are closed even if an error occurs inside the context."""
        mock_page = MagicMock()
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page

        with patch(
            "cloakbrowser.launch",
            return_value=mock_browser,
            create=True,
        ), patch(
            "ai_crawler.browser.wrappers.cloakbrowser.get_fingerprint_script",
            return_value="/* fp */",
        ):
            try:
                with wrapper.launch():
                    raise ValueError("simulated error")
            except ValueError:
                pass

            mock_page.close.assert_called_once()
            mock_browser.close.assert_called_once()

    def test_launch_close_errors_are_suppressed(self, wrapper):
        """Errors during close() are suppressed and don't mask original exceptions."""
        mock_page = MagicMock()
        mock_page.close.side_effect = RuntimeError("close failed")
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page

        with patch(
            "cloakbrowser.launch",
            return_value=mock_browser,
            create=True,
        ), patch(
            "ai_crawler.browser.wrappers.cloakbrowser.get_fingerprint_script",
            return_value="/* fp */",
        ):
            # Should not raise — close errors are suppressed
            with wrapper.launch() as page:
                assert page is mock_page

    def test_fingerprint_params_passed(self, wrapper):
        """Fingerprint parameters from dynamic_profile are passed to init script."""
        wrapper.dynamic_profile = {
            "gpu_vendor": "NVIDIA",
            "gpu_renderer": "RTX 3080",
            "screen_width": 2560,
            "screen_height": 1440,
        }
        mock_page = MagicMock()
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page

        with patch(
            "cloakbrowser.launch",
            return_value=mock_browser,
            create=True,
        ), patch(
            "ai_crawler.browser.wrappers.cloakbrowser.get_fingerprint_script",
            return_value="/* fp */",
        ) as mock_fp:
            with wrapper.launch():
                pass

            call_kwargs = mock_fp.call_args[1]
            assert call_kwargs["gpu_vendor"] == "NVIDIA"
            assert call_kwargs["gpu_renderer"] == "RTX 3080"
            assert call_kwargs["screen_width"] == 2560
            assert call_kwargs["screen_height"] == 1440
