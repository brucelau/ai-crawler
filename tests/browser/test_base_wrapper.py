"""Tests for browser wrapper base classes."""

import pytest

from ai_crawler.browser.base import BaseWrapper, BrowserConfig


class ConcreteWrapper(BaseWrapper):
    def fetch(self, url: str):
        return f"<html>{url}</html>", 200


class TestBrowserConfig:
    def test_default_values(self):
        config = BrowserConfig()
        assert config.proxy is None
        assert config.headless is True
        assert config.wait_time == 2.0
        assert config.human_scroll is False
        assert config.dynamic_profile == {}

    def test_custom_values(self):
        config = BrowserConfig(
            proxy="http://localhost:8080",
            headless=False,
            wait_time=5.0,
            human_scroll=True,
            dynamic_profile={"key": "value"},
        )
        assert config.proxy == "http://localhost:8080"
        assert config.headless is False
        assert config.wait_time == 5.0
        assert config.human_scroll is True
        assert config.dynamic_profile == {"key": "value"}


class TestBaseWrapper:
    def test_init_sets_attributes(self):
        wrapper = ConcreteWrapper(
            proxy="http://proxy:8080",
            headless=False,
            wait_time=3.0,
            human_scroll=True,
            dynamic_profile={"ua": "test"},
        )
        assert wrapper.proxy == "http://proxy:8080"
        assert wrapper.headless is False
        assert wrapper.wait_time == 3.0
        assert wrapper.human_scroll is True
        assert wrapper.dynamic_profile == {"ua": "test"}

    def test_fetch_returns_tuple(self):
        wrapper = ConcreteWrapper()
        html, status = wrapper.fetch("http://example.com")
        assert isinstance(html, str)
        assert status == 200
        assert "example.com" in html

    def test_repr(self):
        wrapper = ConcreteWrapper(proxy="http://proxy:8080")
        assert "ConcreteWrapper" in repr(wrapper)
        assert "proxy" in repr(wrapper)

    def test_repr_without_proxy(self):
        wrapper = ConcreteWrapper()
        assert "ConcreteWrapper" in repr(wrapper)
