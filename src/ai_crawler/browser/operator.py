"""BrowserOperator — OpenCLI-style command interface on any browser backend.

Uses the existing MouseAdapter layer (human/mouse.py) for human-like interaction,
and injects JS scripts for extract/state equivalent to OpenCLI's built-in commands.
"""

from __future__ import annotations

import json
import random
import time
from typing import Any

from ai_crawler.browser.human.mouse import (
    MouseAdapter,
    PlaywrightMouseAdapter,
)

# ── JS scripts for extract / state ──────────────────────────────────────────

_EXTRACT_JS = r"""(() => {
  const interactiveTags = new Set(['A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA', 'DETAILS', 'SUMMARY']);
  const skipTags = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'IFRAME', 'SVG', 'META', 'LINK', 'HEAD']);
  let idx = 0;
  const elements = [];
  const lines = [];
  const seenText = new Set();

  function isVisible(el) {
    const style = getComputedStyle(el);
    return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
  }

  function getSelector(el) {
    if (el.id) return '#' + CSS.escape(el.id);
    let path = [];
    let cur = el;
    while (cur && cur !== document.body) {
      let seg = cur.tagName.toLowerCase();
      if (cur.id) { path.unshift('#' + CSS.escape(cur.id)); break; }
      if (cur.className && typeof cur.className === 'string') {
        const cls = cur.className.trim().split(/\s+/).slice(0, 2).join('.');
        if (cls) seg += '.' + cls;
      }
      path.unshift(seg);
      cur = cur.parentElement;
    }
    return path.join(' > ');
  }

  function walk(node, depth) {
    if (!node || skipTags.has(node.tagName)) return;
    if (node.nodeType === 3) {
      const text = node.textContent.trim();
      if (text && text.length > 2 && !seenText.has(text)) {
        seenText.add(text);
        lines.push(text.substring(0, 500));
      }
      return;
    }
    if (node.nodeType !== 1) return;
    if (!isVisible(node)) return;

    const tag = node.tagName;
    if (interactiveTags.has(tag)) {
      const label = (node.textContent || '').trim().substring(0, 80) || node.getAttribute('aria-label') || node.getAttribute('placeholder') || tag;
      const selector = getSelector(node);
      elements.push({ index: idx, tag: tag.toLowerCase(), text: label, selector });
      lines.push('[' + idx + '] <' + tag.toLowerCase() + '> ' + label);
      idx++;
      return;
    }

    // Headings
    if (/^H[1-6]$/.test(tag)) {
      const text = (node.textContent || '').trim().substring(0, 200);
      if (text) lines.push('#'.repeat(parseInt(tag[1])) + ' ' + text);
      return;
    }

    // Paragraph-like
    if (tag === 'P' || tag === 'LI' || tag === 'TD' || tag === 'TH') {
      const text = (node.textContent || '').trim().substring(0, 500);
      if (text && !seenText.has(text)) { seenText.add(text); lines.push(text); }
      return;
    }

    // Lists and tables — recurse
    if (tag === 'UL' || tag === 'OL' || tag === 'TABLE') {
      for (const child of node.children) walk(child, depth + 1);
      return;
    }

    // Generic container — recurse into children
    for (const child of node.children) walk(child, depth + 1);
  }

  walk(document.body, 0);
  return JSON.stringify({ markdown: lines.join('\n'), elements });
})()"""

_STATE_JS = r"""(() => {
  const interactiveTags = new Set(['A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA', 'DETAILS']);
  let idx = 0;
  const elements = [];

  function isVisible(el) {
    const style = getComputedStyle(el);
    return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
  }

  function getSelector(el) {
    if (el.id) return '#' + CSS.escape(el.id);
    let path = [];
    let cur = el;
    while (cur && cur !== document.body && path.length < 4) {
      let seg = cur.tagName.toLowerCase();
      if (cur.id) { path.unshift('#' + CSS.escape(cur.id)); break; }
      if (cur.className && typeof cur.className === 'string') {
        const cls = cur.className.trim().split(/\s+/).slice(0, 2).join('.');
        if (cls) seg += '.' + cls;
      }
      path.unshift(seg);
      cur = cur.parentElement;
    }
    return path.join(' > ');
  }

  function findInteractive(root) {
    if (!root || root.nodeType !== 1) return;
    if (!isVisible(root)) return;
    const tag = root.tagName;
    if (interactiveTags.has(tag)) {
      const text = (root.textContent || '').trim().substring(0, 80) || root.getAttribute('aria-label') || root.getAttribute('placeholder') || tag;
      elements.push({ index: idx, tag: tag.toLowerCase(), text, selector: getSelector(root) });
      idx++;
      return;
    }
    for (const child of root.children) findInteractive(child);
  }

  findInteractive(document.body);
  return JSON.stringify({
    url: location.href,
    title: document.title,
    elements
  });
})()"""

# ── BrowserOperator ─────────────────────────────────────────────────────────


class BrowserOperator:
    """OpenCLI-style command interface on any browser backend.

    Receives a page object from the pool layer (already navigated to a URL)
    and exposes click/type/scroll/eval/extract/state/network commands that
    work across Playwright, Camoufox, and CloakBrowser backends.

    Usage:
        html, status, page = pool.fetch(task, strategy)
        op = BrowserOperator(page)
        op.scroll("down", 500)
        op.click("[3]")
        data = op.extract()
    """

    def __init__(self, page, adapter: MouseAdapter | None = None):
        self._page = page
        self._adapter = adapter or PlaywrightMouseAdapter(page)
        self._network_entries: list[dict[str, Any]] = []
        self._network_capturing = False

    # ── content ─────────────────────────────────────────────────────────

    def content(self) -> str:
        """Return current page HTML."""
        return self._page.content()

    # ── navigate ────────────────────────────────────────────────────────

    def navigate(self, url: str, wait_until: str = "domcontentloaded") -> dict:
        """Navigate to url. Returns {"url": str, "status": int}."""
        try:
            resp = self._page.goto(url, wait_until=wait_until, timeout=30000)
            return {"url": self._page.url, "status": resp.status if resp else 0}
        except Exception as exc:
            return {"url": url, "status": 0, "error": str(exc)}

    # ── wait_for ────────────────────────────────────────────────────────

    def wait_for(self, kind: str, value: str, timeout: int = 15) -> dict:
        """Wait for selector, text, or time.

        kind: "selector" | "text" | "time"
        """
        try:
            if kind == "selector":
                self._page.wait_for_selector(value, timeout=timeout * 1000)
            elif kind == "text":
                self._page.wait_for_function(
                    f"document.body.innerText.includes({value!r})",
                    timeout=timeout * 1000,
                )
            elif kind == "time":
                time.sleep(float(value))
            return {"waited": True, "kind": kind, "value": value}
        except Exception as exc:
            return {"waited": False, "kind": kind, "value": value, "error": str(exc)}

    # ── click ───────────────────────────────────────────────────────────

    def click(self, target: str) -> dict:
        """Click an element by CSS selector or [N] index.

        Returns {"clicked": True/False, "target": str}.
        """
        try:
            selector = self._resolve_target(target)
            self._page.click(selector, timeout=10000)
            return {"clicked": True, "target": target}
        except Exception as exc:
            return {"clicked": False, "target": target, "error": str(exc)}

    # ── type_text ───────────────────────────────────────────────────────

    def type_text(self, text: str, target: str | None = None) -> dict:
        """Optionally click target, then type text character by character.

        Returns {"typed": True/False, "text": str}.
        """
        try:
            if target:
                selector = self._resolve_target(target)
                self._page.click(selector, timeout=5000)
                time.sleep(random.uniform(0.3, 0.6))
            for char in text:
                self._page.keyboard.type(char)
                time.sleep(random.uniform(0.03, 0.12))
            return {"typed": True, "text": text}
        except Exception as exc:
            return {"typed": False, "text": text, "error": str(exc)}

    # ── keys ────────────────────────────────────────────────────────────

    def keys(self, key: str) -> dict:
        """Press a keyboard key (Enter, Escape, ArrowDown, PageDown, etc.)."""
        try:
            self._page.keyboard.press(key)
            return {"pressed": True, "key": key}
        except Exception as exc:
            return {"pressed": False, "key": key, "error": str(exc)}

    # ── scroll ──────────────────────────────────────────────────────────

    def scroll(self, direction: str = "down", amount: int = 300) -> dict:
        """Scroll the page. direction: "up" | "down"."""
        try:
            sign = -1 if direction == "up" else 1
            self._page.evaluate(f"window.scrollBy(0, {sign * amount})")
            return {"scrolled": True, "direction": direction, "amount": amount}
        except Exception as exc:
            return {"scrolled": False, "direction": direction, "error": str(exc)}

    # ── mouse operations ────────────────────────────────────────────────

    def hover(self, target: str) -> dict:
        """Move mouse to element with human curve and hover.

        Returns {"hovered": True/False, "target": str}.
        """
        try:
            selector = self._resolve_target(target)
            box = self._get_bounding_box(selector)
            if not box:
                return {"hovered": False, "target": target, "error": "Element not found"}
            x = box["x"] + box["width"] / 2
            y = box["y"] + box["height"] / 2
            self._adapter.move_to(x, y)
            self._adapter.hover(x, y)
            return {"hovered": True, "target": target}
        except Exception as exc:
            return {"hovered": False, "target": target, "error": str(exc)}

    def human_click(self, target: str) -> dict:
        """Click element using human-like mouse movement curve.

        Returns {"clicked": True/False, "target": str}.
        """
        try:
            selector = self._resolve_target(target)
            box = self._get_bounding_box(selector)
            if not box:
                return {"clicked": False, "target": target, "error": "Element not found"}
            x = box["x"] + box["width"] / 2
            y = box["y"] + box["height"] / 2
            self._adapter.move_to(x, y)
            time.sleep(random.uniform(0.05, 0.15))
            self._adapter.click(x, y)
            return {"clicked": True, "target": target}
        except Exception as exc:
            return {"clicked": False, "target": target, "error": str(exc)}

    def drag(self, source: str, destination: str) -> dict:
        """Drag source element to destination element with human-like movement.

        Returns {"dragged": True/False, "source": str, "destination": str}.
        """
        try:
            src_sel = self._resolve_target(source)
            dst_sel = self._resolve_target(destination)
            src_box = self._get_bounding_box(src_sel)
            dst_box = self._get_bounding_box(dst_sel)
            if not src_box or not dst_box:
                return {"dragged": False, "source": source, "destination": destination,
                        "error": "Element not found"}
            sx = src_box["x"] + src_box["width"] / 2
            sy = src_box["y"] + src_box["height"] / 2
            dx = dst_box["x"] + dst_box["width"] / 2
            dy = dst_box["y"] + dst_box["height"] / 2
            self._adapter.move_to(sx, sy)
            time.sleep(random.uniform(0.05, 0.15))
            # Drag via Playwright mouse or JS fallback
            try:
                self._page.mouse.down()
                self._adapter.move_to(dx, dy)
                self._page.mouse.up()
            except AttributeError:
                # Fallback: scroll destination into view for Selenium backends
                self._adapter.move_to(dx, dy)
            return {"dragged": True, "source": source, "destination": destination}
        except Exception as exc:
            return {"dragged": False, "source": source, "destination": destination,
                    "error": str(exc)}

    def human_scroll(self, amount: int = 300) -> dict:
        """Scroll using human-like mouse wheel behaviour.

        Returns {"scrolled": True, "amount": int}.
        """
        try:
            self._adapter.human_scroll(0, amount)
            return {"scrolled": True, "amount": amount}
        except Exception as exc:
            return {"scrolled": False, "amount": amount, "error": str(exc)}

    # ── helpers ─────────────────────────────────────────────────────────

    def _get_bounding_box(self, selector: str) -> dict | None:
        """Get element bounding box via JS (works on all backends)."""
        escaped = selector.replace("\\", "\\\\").replace("'", "\\'")
        js = f"""(function() {{
            var el = document.querySelector('{escaped}');
            if (!el) return null;
            var r = el.getBoundingClientRect();
            return {{x: r.x, y: r.y, width: r.width, height: r.height}};
        }})()"""
        result = self._page.evaluate(js)
        return result if result else None

    # ── eval_js ─────────────────────────────────────────────────────────

    def eval_js(self, js: str) -> dict:
        """Execute JavaScript in the page context. Returns {"result": ...}."""
        try:
            result = self._page.evaluate(js)
            return {"result": result}
        except Exception as exc:
            return {"result": None, "error": str(exc)}

    # ── extract ─────────────────────────────────────────────────────────

    def extract(self) -> dict:
        """Extract page content as structured markdown with interactive element indices.

        Returns {"markdown": str, "elements": list[dict]}.
        """
        try:
            raw = self._page.evaluate(_EXTRACT_JS)
            data = json.loads(raw)
            return {"markdown": data.get("markdown", ""), "elements": data.get("elements", [])}
        except Exception as exc:
            return {"markdown": "", "elements": [], "error": str(exc)}

    # ── state ───────────────────────────────────────────────────────────

    def state(self) -> dict:
        """Get page state: url, title, and interactive elements with [N] indices.

        Returns {"url": str, "title": str, "elements": list[dict]}.
        """
        try:
            raw = self._page.evaluate(_STATE_JS)
            return json.loads(raw)
        except Exception as exc:
            return {"url": "", "title": "", "elements": [], "error": str(exc)}

    # ── network capture ─────────────────────────────────────────────────

    def network_capture_start(self) -> dict:
        """Start intercepting XHR/fetch requests."""
        if self._network_capturing:
            return {"capturing": True, "message": "already capturing"}

        self._network_entries.clear()
        self._network_capturing = True

        def _on_route(route):
            url = route.request.url
            if not url.startswith("data:"):
                self._network_entries.append({
                    "url": url,
                    "method": route.request.method,
                    "resource_type": route.request.resource_type,
                })
            route.continue_()

        try:
            self._page.route("**/*", _on_route)
            return {"capturing": True}
        except Exception as exc:
            self._network_capturing = False
            return {"capturing": False, "error": str(exc)}

    def network_capture_stop(self) -> list[dict]:
        """Stop intercepting and return captured requests."""
        self._network_capturing = False
        try:
            self._page.unroute("**/*")
        except Exception:
            pass
        entries = list(self._network_entries)
        self._network_entries.clear()
        return entries

    # ── screenshot ──────────────────────────────────────────────────────

    def screenshot(self, path: str) -> dict:
        """Take a screenshot and save to path. Returns {"path": str, "ok": bool}."""
        try:
            self._page.screenshot(path=path)
            return {"path": path, "ok": True}
        except Exception as exc:
            return {"path": path, "ok": False, "error": str(exc)}

    # ── search ──────────────────────────────────────────────────────────

    def search(self, url: str, query: str, input_target: str | None = None) -> dict:
        """Navigate to url, type query, submit, return page HTML.

        If input_target given, clicks that element first before typing.
        """
        try:
            self.navigate(url)
            self.wait_for("time", "2")

            if input_target:
                self.click(input_target)
            else:
                self._page.keyboard.type(query)
                time.sleep(0.3)

            self.keys("Enter")
            self.wait_for("time", "3")

            return {"html": self.content(), "status": 200}
        except Exception as exc:
            return {"html": self.content(), "status": 0, "error": str(exc)}

    # ── helpers ─────────────────────────────────────────────────────────

    def _resolve_target(self, target: str) -> str:
        """If target is [N], resolve to a CSS selector via state()."""
        if target.startswith("[") and target.endswith("]"):
            index = int(target[1:-1])
            state_data = self.state()
            for el in state_data.get("elements", []):
                if el.get("index") == index:
                    return el["selector"]
            raise ValueError(f"No interactive element with index [{index}]")
        return target
