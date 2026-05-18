"""Session daemon — manages persistent browser sessions via Unix socket.

Architecture:
  CLI client  ──JSON──>  Unix socket  ──>  SessionDaemon  ──>  BrowserOperator
                         /tmp/ai-crawler-{uid}.sock

Each named session holds a live browser page + BrowserOperator instance.
Commands mirror the opencli browser command set.

All browser operations run on the same thread (the accept loop thread) to avoid
Playwright greenlet "cannot switch to a different thread" errors.
"""

from __future__ import annotations

import json
import os
import socket
import struct
import threading
from typing import Any

from ai_crawler.browser.page_adapter import SeleniumPageAdapter


def _socket_path() -> str:
    return f"/tmp/ai-crawler-{os.getuid()}.sock"


class BrowserSession:
    """Holds a live browser page and its BrowserOperator."""

    def __init__(self, name: str, page, operator, cleanup):
        self.name = name
        self.page = page
        self.op = operator
        self._cleanup = cleanup

    def close(self):
        try:
            self._cleanup()
        except Exception:
            pass


class SessionDaemon:
    """Unix-socket server that manages named browser sessions."""

    def __init__(self):
        self._sessions: dict[str, BrowserSession] = {}
        self._lock = threading.Lock()
        self._running = threading.Event()
        self._running.set()

    # ── session lifecycle ─────────────────────────────────────────────────

    def _start_session(self, name: str, backend: str, headless: bool, proxy: str | None) -> dict:
        if name in self._sessions:
            return {"ok": False, "error": f"Session '{name}' already exists"}

        try:
            if backend == "cloakbrowser":
                page, cleanup = self._launch_cloakbrowser(headless, proxy)
            elif backend == "camoufox":
                page, cleanup = self._launch_camoufox(headless, proxy)
            elif backend == "seleniumbase":
                page, cleanup = self._launch_seleniumbase(headless, proxy)
            elif backend == "undetected_chromedriver":
                page, cleanup = self._launch_undetected_chromedriver(headless, proxy)
            else:
                page, cleanup = self._launch_playwright(headless, proxy)
        except Exception as exc:
            return {"ok": False, "error": f"Failed to launch {backend}: {exc}"}

        from ai_crawler.browser.operator import BrowserOperator
        from ai_crawler.browser.human.mouse import PlaywrightMouseAdapter, SeleniumMouseAdapter

        if backend in ("seleniumbase", "undetected_chromedriver"):
            adapter = SeleniumMouseAdapter(page._driver)
        else:
            adapter = PlaywrightMouseAdapter(page)
        op = BrowserOperator(page, adapter)
        session = BrowserSession(name, page, op, cleanup)

        with self._lock:
            self._sessions[name] = session

        return {"ok": True, "session": name, "backend": backend}

    def _close_session(self, name: str) -> dict:
        with self._lock:
            session = self._sessions.pop(name, None)
        if session is None:
            return {"ok": False, "error": f"No session '{name}'"}
        session.close()
        return {"ok": True, "session": name, "closed": True}

    def _get_session(self, name: str) -> BrowserSession:
        with self._lock:
            session = self._sessions.get(name)
        if session is None:
            raise ValueError(f"No session '{name}'. Start one with: aicrawler browser {name} start --backend <backend>")
        return session

    # ── browser launchers ─────────────────────────────────────────────────

    def _launch_playwright(self, headless: bool, proxy: str | None) -> tuple[Any, Any]:
        from playwright.sync_api import sync_playwright
        import glob

        pw = sync_playwright().start()
        launch_kwargs: dict = {"headless": headless}

        # Use installed Chromium if the expected version isn't available
        chromium_dirs = glob.glob(
            os.path.expanduser("~/Library/Caches/ms-playwright/chromium-*")
        )
        if chromium_dirs:
            latest = sorted(chromium_dirs)[-1]
            for arch in ("chrome-mac-arm64", "chrome-mac"):
                chrome_app = os.path.join(
                    latest, arch, "Google Chrome for Testing.app",
                    "Contents", "MacOS", "Google Chrome for Testing"
                )
                if os.path.exists(chrome_app):
                    launch_kwargs["executable_path"] = chrome_app
                    break

        if proxy:
            launch_kwargs["proxy"] = {"server": proxy}
        browser = pw.chromium.launch(**launch_kwargs)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        def cleanup():
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass
            try:
                pw.stop()
            except Exception:
                pass

        return page, cleanup

    def _launch_camoufox(self, headless: bool, proxy: str | None) -> tuple[Any, Any]:
        from playwright.sync_api import sync_playwright
        import glob

        pw = sync_playwright().start()
        launch_kwargs: dict = {
            "headless": headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-gpu",
                "--window-size=1920,1080",
            ],
        }

        chromium_dirs = glob.glob(
            os.path.expanduser("~/Library/Caches/ms-playwright/chromium-*")
        )
        if chromium_dirs:
            latest = sorted(chromium_dirs)[-1]
            for arch in ("chrome-mac-arm64", "chrome-mac"):
                chrome_app = os.path.join(
                    latest, arch, "Google Chrome for Testing.app",
                    "Contents", "MacOS", "Google Chrome for Testing"
                )
                if os.path.exists(chrome_app):
                    launch_kwargs["executable_path"] = chrome_app
                    break

        if proxy:
            launch_kwargs["proxy"] = {"server": proxy}
        browser = pw.chromium.launch(**launch_kwargs)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/New_York",
        )
        context.set_extra_http_headers({
            "Accept-Language": "en-US,en;q=0.9",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        })
        page = context.new_page()
        page.evaluate("""() => {
            Object.defineProperty(navigator, 'webdriver', {get: () => false});
        }""")

        def cleanup():
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass
            try:
                pw.stop()
            except Exception:
                pass

        return page, cleanup

    def _launch_seleniumbase(self, headless: bool, proxy: str | None) -> tuple[Any, Any]:
        from seleniumbase import Driver

        kwargs = {"browser": "chrome", "headless": headless}
        if proxy:
            kwargs["proxy"] = proxy
        driver = Driver(**kwargs)
        adapter = SeleniumPageAdapter(driver)

        def cleanup():
            try:
                driver.quit()
            except Exception:
                pass

        return adapter, cleanup

    def _launch_undetected_chromedriver(self, headless: bool, proxy: str | None) -> tuple[Any, Any]:
        import undetected_chromedriver as uc

        options = uc.ChromeOptions()
        if proxy:
            options.add_argument(f"--proxy-server={proxy}")
        driver = uc.Chrome(headless=headless, no_sandbox=True, options=options)
        adapter = SeleniumPageAdapter(driver)

        def cleanup():
            try:
                driver.quit()
            except Exception:
                pass

        return adapter, cleanup

    def _launch_cloakbrowser(self, headless: bool, proxy: str | None) -> tuple[Any, Any]:
        from ai_crawler.browser.wrappers.cloakbrowser import CloakBrowserWrapper

        wrapper = CloakBrowserWrapper(headless=headless, proxy=proxy)
        ctx = wrapper.launch()
        page = ctx.__enter__()

        def cleanup():
            try:
                ctx.__exit__(None, None, None)
            except Exception:
                pass

        return page, cleanup

    # ── command dispatch ───────────────────────────────────────────────────

    def dispatch(self, cmd: dict) -> dict:
        method = cmd.get("cmd")
        session_name = cmd.get("session", "default")
        args = cmd.get("args", [])

        try:
            if method == "start":
                return self._start_session(
                    session_name,
                    backend=cmd.get("backend", "playwright"),
                    headless=cmd.get("headless", True),
                    proxy=cmd.get("proxy"),
                )
            if method == "close":
                return self._close_session(session_name)
            if method == "stop_daemon":
                return self._shutdown()
            if method == "sessions":
                with self._lock:
                    names = list(self._sessions.keys())
                return {"ok": True, "result": names}

            session = self._get_session(session_name)
            op = session.op

            if method == "open":
                return {"ok": True, "result": op.navigate(args[0])}
            elif method == "content":
                return {"ok": True, "result": op.content()}
            elif method == "click":
                return {"ok": True, "result": op.click(args[0])}
            elif method == "human_click":
                return {"ok": True, "result": op.human_click(args[0])}
            elif method == "hover":
                return {"ok": True, "result": op.hover(args[0])}
            elif method == "drag":
                return {"ok": True, "result": op.drag(args[0], args[1])}
            elif method == "human_scroll":
                amount = int(args[0]) if args else 300
                return {"ok": True, "result": op.human_scroll(amount)}
            elif method == "type":
                text = args[0]
                target = args[1] if len(args) > 1 else None
                return {"ok": True, "result": op.type_text(text, target)}
            elif method == "keys":
                return {"ok": True, "result": op.keys(args[0])}
            elif method == "scroll":
                direction = args[0] if args else "down"
                amount = int(args[1]) if len(args) > 1 else 300
                return {"ok": True, "result": op.scroll(direction, amount)}
            elif method == "extract":
                return {"ok": True, "result": op.extract()}
            elif method == "state":
                return {"ok": True, "result": op.state()}
            elif method == "eval":
                return {"ok": True, "result": op.eval_js(args[0])}
            elif method == "screenshot":
                path = args[0] if args else "screenshot.png"
                return {"ok": True, "result": op.screenshot(path)}
            elif method == "wait":
                kind = args[0] if args else "time"
                value = args[1] if len(args) > 1 else "1"
                return {"ok": True, "result": op.wait_for(kind, value)}
            elif method == "network_start":
                return {"ok": True, "result": op.network_capture_start()}
            elif method == "network_stop":
                return {"ok": True, "result": op.network_capture_stop()}
            elif method == "search":
                url = args[0]
                query = args[1]
                input_target = args[2] if len(args) > 2 else None
                return {"ok": True, "result": op.search(url, query, input_target)}
            else:
                return {"ok": False, "error": f"Unknown command: {method}"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _shutdown(self) -> dict:
        """Signal the daemon to stop."""
        self._running.clear()
        # Ping the socket to unblock accept()
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(0.5)
            s.connect(_socket_path())
            s.sendall(struct.pack(">I", 2) + b"{}")
            s.close()
        except Exception:
            pass
        return {"ok": True, "result": "daemon stopping"}

    # ── socket server ─────────────────────────────────────────────────────

    def run(self):
        sock_path = _socket_path()
        try:
            os.unlink(sock_path)
        except OSError:
            pass

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(sock_path)
        server.listen(5)
        server.settimeout(0.5)  # so we can check self._running periodically
        os.chmod(sock_path, 0o600)
        print(f"Daemon listening on {sock_path}", flush=True)

        try:
            while self._running.is_set():
                try:
                    conn, _ = server.accept()
                except socket.timeout:
                    continue
                # Handle inline on this thread — all browser ops stay on the
                # same thread, avoiding Playwright greenlet thread errors.
                self._handle(conn)
        except KeyboardInterrupt:
            pass
        finally:
            server.close()
            try:
                os.unlink(sock_path)
            except OSError:
                pass
            with self._lock:
                for s in list(self._sessions.values()):
                    s.close()
                self._sessions.clear()

    def _handle(self, conn: socket.socket):
        try:
            raw = self._recv_all(conn)
            cmd = json.loads(raw)
            resp = self.dispatch(cmd)
        except Exception as exc:
            resp = {"ok": False, "error": str(exc)}
        try:
            payload = json.dumps(resp).encode("utf-8")
            conn.sendall(struct.pack(">I", len(payload)) + payload)
        except Exception:
            pass
        finally:
            conn.close()

    @staticmethod
    def _recv_all(conn: socket.socket) -> bytes:
        raw_len = conn.recv(4)
        if len(raw_len) < 4:
            return b"{}"
        msg_len = struct.unpack(">I", raw_len)[0]
        chunks = []
        remaining = msg_len
        while remaining > 0:
            chunk = conn.recv(min(4096, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)


# ── client send helper (used by CLI main) ────────────────────────────────────


def send_command(cmd: dict, timeout: float = 60.0) -> dict:
    """Send a JSON command to the daemon and return the response."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(_socket_path())
    except (FileNotFoundError, ConnectionRefusedError):
        return {"ok": False, "error": "Daemon not running. Start it with: aicrawler daemon start"}
    try:
        payload = json.dumps(cmd).encode("utf-8")
        sock.sendall(struct.pack(">I", len(payload)) + payload)
        raw_len = sock.recv(4)
        if len(raw_len) < 4:
            return {"ok": False, "error": "No response from daemon"}
        msg_len = struct.unpack(">I", raw_len)[0]
        chunks = []
        remaining = msg_len
        while remaining > 0:
            chunk = sock.recv(min(4096, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        return json.loads(b"".join(chunks).decode("utf-8"))
    except socket.timeout:
        return {"ok": False, "error": f"Command timed out after {timeout}s"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        sock.close()


# ── standalone entry point ────────────────────────────────────────────────────

if __name__ == "__main__":
    SessionDaemon().run()
