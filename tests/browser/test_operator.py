"""Unit tests for BrowserOperator — mock Playwright page."""

import json
from unittest.mock import MagicMock

from ai_crawler.browser.operator import BrowserOperator, _EXTRACT_JS, _STATE_JS


class TestBrowserOperator:
    def setup_method(self):
        self.page = MagicMock()
        self.page.content.return_value = "<html><body>test</body></html>"
        self.page.url = "https://example.com"
        self.op = BrowserOperator(self.page)

    def test_content(self):
        assert self.op.content() == "<html><body>test</body></html>"

    def test_navigate(self):
        resp = MagicMock()
        resp.status = 200
        self.page.goto.return_value = resp
        result = self.op.navigate("https://example.com")
        assert result["url"] == "https://example.com"
        assert result["status"] == 200

    def test_click_selector(self):
        result = self.op.click(".btn")
        self.page.click.assert_called_once_with(".btn", timeout=10000)
        assert result["clicked"] is True

    def test_click_index(self):
        self.page.evaluate.return_value = json.dumps({
            "url": "https://example.com",
            "title": "Test",
            "elements": [{"index": 0, "tag": "button", "text": "Go", "selector": "#go"}],
        })
        result = self.op.click("[0]")
        self.page.click.assert_called_once_with("#go", timeout=10000)
        assert result["clicked"] is True

    def test_type_text(self):
        result = self.op.type_text("hello")
        assert self.page.keyboard.type.call_count == 5
        assert result["typed"] is True

    def test_type_text_with_target(self):
        result = self.op.type_text("hi", target="#search")
        self.page.click.assert_called_once_with("#search", timeout=5000)
        assert result["typed"] is True

    def test_keys(self):
        result = self.op.keys("Enter")
        self.page.keyboard.press.assert_called_once_with("Enter")
        assert result["pressed"] is True

    def test_scroll_down(self):
        result = self.op.scroll("down", 500)
        self.page.evaluate.assert_called_once_with("window.scrollBy(0, 500)")
        assert result["scrolled"] is True

    def test_scroll_up(self):
        result = self.op.scroll("up", 200)
        self.page.evaluate.assert_called_once_with("window.scrollBy(0, -200)")
        assert result["scrolled"] is True

    def test_eval_js(self):
        self.page.evaluate.return_value = 42
        result = self.op.eval_js("1 + 1")
        assert result["result"] == 42

    def test_extract(self):
        self.page.evaluate.return_value = json.dumps({
            "markdown": "# Title\n[0] <a> link",
            "elements": [{"index": 0, "tag": "a", "text": "link"}],
        })
        result = self.op.extract()
        assert result["markdown"].startswith("# Title")
        assert len(result["elements"]) == 1

    def test_state(self):
        self.page.evaluate.return_value = json.dumps({
            "url": "https://example.com",
            "title": "Example",
            "elements": [{"index": 0, "tag": "input", "text": "search", "selector": "#q"}],
        })
        result = self.op.state()
        assert result["url"] == "https://example.com"
        assert len(result["elements"]) == 1
        assert result["elements"][0]["tag"] == "input"

    def test_wait_for_selector(self):
        result = self.op.wait_for("selector", ".loaded")
        self.page.wait_for_selector.assert_called_once()
        assert result["waited"] is True

    def test_wait_for_time(self):
        result = self.op.wait_for("time", "0.1")
        assert result["waited"] is True

    def test_screenshot(self):
        result = self.op.screenshot("/tmp/test.png")
        self.page.screenshot.assert_called_once_with(path="/tmp/test.png")
        assert result["ok"] is True

    def test_network_capture(self):
        self.op.network_capture_start()
        self.page.route.assert_called_once()

        # Simulate a captured request
        self.op._network_entries.append({
            "url": "https://example.com/api", "method": "GET", "resource_type": "xhr",
        })
        entries = self.op.network_capture_stop()
        self.page.unroute.assert_called_once()
        assert len(entries) == 1
        assert entries[0]["url"] == "https://example.com/api"


class TestExtractJS:
    """Verify the JS scripts are valid JavaScript that parses correctly."""

    def test_extract_js_is_valid(self):
        assert "JSON.stringify" in _EXTRACT_JS
        assert "markdown" in _EXTRACT_JS
        assert "elements" in _EXTRACT_JS

    def test_state_js_is_valid(self):
        assert "JSON.stringify" in _STATE_JS
        assert "location.href" in _STATE_JS
        assert "document.title" in _STATE_JS
