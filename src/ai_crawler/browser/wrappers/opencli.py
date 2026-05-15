"""OpenCLI browser wrapper — reuses user's logged-in Chrome session via CLI subprocess.

Supports multi-profile: each Chrome profile isolates login state, so different
sites or accounts can use different profiles without cross-contamination.

Usage in ai-crawler:
  - Fetcher._fetch_with_opencli    → calls fetch()
  - API endpoint discovery         → calls network_intercept()
  - JS 提取器增强                   → calls eval_js()
  - 交互式搜索                      → calls search()
  - 预置 adapter 快速抓取            → calls run_adapter()
  - 多账号隔离                      → set_default_profile() + fetch()
"""

from __future__ import annotations

import json
import subprocess
import time
from typing import Any

# ── Module-level defaults ──────────────────────────────────────────────────────

_default_profile: str | None = None
_default_session: str = "ai-crawler"


def set_default_profile(profile: str | None) -> None:
    """Set the default Chrome profile for all subsequent browser commands.

    Pass None to clear (use whatever opencli profile use has set).
    """
    global _default_profile
    _default_profile = profile


def set_default_session(session: str) -> None:
    """Set the default browser session name."""
    global _default_session
    _default_session = session


# ── Internal helpers ───────────────────────────────────────────────────────────


def _browser(
    args: list[str],
    session: str | None = None,
    profile: str | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess:
    """Run 'opencli [--profile X] browser <session> <args...> --window background'."""
    cmd = ["opencli"]
    p = profile if profile is not None else _default_profile
    if p:
        cmd.extend(["--profile", p])
    cmd.append("browser")
    cmd.append(session if session is not None else _default_session)
    cmd.extend(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _cli(
    args: list[str],
    profile: str | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess:
    """Run 'opencli [--profile X] <args...>' (non-browser commands, e.g. adapters)."""
    cmd = ["opencli"]
    p = profile if profile is not None else _default_profile
    if p:
        cmd.extend(["--profile", p])
    cmd.extend(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _strip_code_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.split("\n")
        if len(lines) > 2 and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
    return t


# ── Profile management ─────────────────────────────────────────────────────────


def list_profiles() -> list[dict[str, Any]]:
    """List all connected Chrome profiles with contextId and alias."""
    result = _cli(["profile", "list"])
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        lines = result.stdout.strip().split("\n")
        profiles: list[dict[str, Any]] = []
        for line in lines:
            if line.strip():
                profiles.append({"raw": line})
        return profiles


def profile_use(name: str) -> None:
    """Set the default Chrome profile for the opencli CLI itself.

    This is equivalent to 'opencli profile use <name>' and persists across sessions.
    For per-session selection, pass profile= to individual functions instead.
    """
    _cli(["profile", "use", name])
    global _default_profile
    _default_profile = name


def active_profile_name() -> str | None:
    """Return the currently active profile name, or None if not set."""
    return _default_profile


# ── Core: page fetch ──────────────────────────────────────────────────────────


def fetch(
    url: str,
    session: str | None = None,
    profile: str | None = None,
    wait_selector: str | None = None,
    wait_time: float = 2.0,
    timeout: int = 30,
) -> tuple[str, int]:
    """Navigate to url and return (html, 200)."""
    _browser(["open", url], session=session, profile=profile, timeout=timeout)

    if wait_selector:
        _browser(["wait", "selector", wait_selector], session=session, profile=profile, timeout=timeout)
    elif wait_time > 0:
        _browser(["wait", "time", str(int(wait_time))], session=session, profile=profile, timeout=timeout)

    result = _browser(
        ["eval", "document.documentElement.outerHTML"],
        session=session, profile=profile, timeout=timeout,
    )
    return _strip_code_fence(result.stdout), 200


# ── API endpoint discovery ────────────────────────────────────────────────────


def network_intercept(
    url: str,
    session: str | None = None,
    profile: str | None = None,
    wait_time: float = 3.0,
    timeout: int = 30,
) -> list[dict[str, Any]]:
    """Navigate to url, capture all XHR/fetch requests (API endpoint discovery).

    Returns list of request shapes with url, method, content-type, response preview.

    Uses 'network --follow' streaming mode started BEFORE navigation, which is
    required for the opencli Chrome extension to capture network requests.
    """
    import signal
    import threading

    sess = session if session is not None else _default_session

    # Build the network --follow command
    cmd = ["opencli"]
    p = profile if profile is not None else _default_profile
    if p:
        cmd.extend(["--profile", p])
    cmd.extend(["browser", sess, "network", "--follow"])

    entries: list[dict[str, Any]] = []
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    collected_events = threading.Event()

    def _reader():
        """Read JSON lines from network --follow until process exits."""
        nonlocal entries
        try:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if isinstance(entry, dict) and "url" in entry:
                        entries.append(entry)
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass
        finally:
            collected_events.set()

    reader_thread = threading.Thread(target=_reader, daemon=True)
    reader_thread.start()

    try:
        # Give --follow time to establish the Chrome extension connection
        time.sleep(2.0)
        _browser(["open", url], session=sess, profile=profile, timeout=timeout)
        _browser(["wait", "time", str(int(wait_time))], session=sess, profile=profile, timeout=timeout)

        # Additional settle time for late XHR/analytics calls
        extra_settle = wait_time * 0.5
        if extra_settle > 0:
            time.sleep(extra_settle)
    finally:
        # Terminate the --follow process
        try:
            proc.send_signal(signal.SIGTERM)
        except Exception:
            pass
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        reader_thread.join(timeout=2)

    return entries


def fetch_and_intercept(
    url: str,
    session: str | None = None,
    profile: str | None = None,
    wait_time: float = 3.0,
    wait_selector: str | None = None,
    timeout: int = 30,
) -> tuple[str, int, list[dict[str, Any]]]:
    """Navigate to url and return (html, 200, network_entries) in a single navigation.

    Opens the page, waits for it to load, then queries both the page HTML and
    captured network requests. Single navigation, no --follow required.
    """
    sess = session if session is not None else _default_session

    # Navigate and wait for page load
    _browser(["open", url], session=sess, profile=profile, timeout=timeout)

    if wait_selector:
        _browser(["wait", "selector", wait_selector], session=sess, profile=profile, timeout=timeout)
    elif wait_time > 0:
        _browser(["wait", "time", str(int(wait_time))], session=sess, profile=profile, timeout=timeout)

    # Allow late XHR calls to settle
    extra_settle = wait_time * 0.5
    if extra_settle > 0:
        time.sleep(extra_settle)

    # Query network entries (captures non-static requests from this session)
    entries: list[dict[str, Any]] = []
    try:
        net_result = _browser(["network"], session=sess, profile=profile, timeout=timeout)
        net_data = json.loads(net_result.stdout)
        if isinstance(net_data, dict):
            entries = net_data.get("entries", [])
    except (json.JSONDecodeError, Exception):
        pass

    # Eval HTML
    result = _browser(
        ["eval", "document.documentElement.outerHTML"],
        session=sess, profile=profile, timeout=timeout,
    )
    html = _strip_code_fence(result.stdout)

    return html, 200, entries


def discover_endpoints(
    url: str,
    session: str | None = None,
    profile: str | None = None,
    **kwargs: Any,
) -> list[str]:
    """Convenience: return just the API URLs discovered on a page."""
    requests = network_intercept(url, session=session, profile=profile, **kwargs)
    urls: list[str] = []
    for req in requests:
        if isinstance(req, dict):
            u = req.get("url", "")
            if u and ("api" in u.lower() or "graphql" in u.lower() or "search" in u.lower()):
                urls.append(u)
    return urls or [req.get("url", "") for req in requests if isinstance(req, dict)]


# ── JS execution ──────────────────────────────────────────────────────────────


def eval_js(
    js: str,
    session: str | None = None,
    profile: str | None = None,
    timeout: int = 15,
) -> str:
    """Execute JavaScript in the logged-in page context, return result as string."""
    result = _browser(["eval", js], session=session, profile=profile, timeout=timeout)
    return _strip_code_fence(result.stdout)


# ── Structured extraction ─────────────────────────────────────────────────────


def extract(
    session: str | None = None,
    profile: str | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """Extract page content as structured markdown with interactive element indices."""
    result = _browser(["extract"], session=session, profile=profile, timeout=timeout)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"markdown": result.stdout}


def state(
    session: str | None = None,
    profile: str | None = None,
    timeout: int = 15,
) -> dict[str, Any]:
    """Get page state: url, title, interactive elements with [N] indices."""
    result = _browser(["state", "-f", "json"], session=session, profile=profile, timeout=timeout)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}


# ── Interactive operations ────────────────────────────────────────────────────


def click(
    target: str,
    session: str | None = None,
    profile: str | None = None,
    timeout: int = 15,
) -> dict[str, Any]:
    """Click an element by index [N] or CSS selector."""
    result = _browser(["click", target], session=session, profile=profile, timeout=timeout)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"clicked": False}


def type_text(
    text: str,
    target: str | None = None,
    session: str | None = None,
    profile: str | None = None,
    timeout: int = 15,
) -> dict[str, Any]:
    """Click target (optional) then type text."""
    args = ["type"]
    if target:
        args.append(target)
    args.append(text)
    result = _browser(args, session=session, profile=profile, timeout=timeout)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"typed": False}


def keys(
    key: str,
    session: str | None = None,
    profile: str | None = None,
    timeout: int = 10,
) -> None:
    """Press a keyboard key (Enter, Escape, ArrowDown, etc.)."""
    _browser(["keys", key], session=session, profile=profile, timeout=timeout)


def scroll(
    direction: str = "down",
    session: str | None = None,
    profile: str | None = None,
    timeout: int = 10,
) -> None:
    """Scroll page (up / down)."""
    _browser(["scroll", direction], session=session, profile=profile, timeout=timeout)


def wait_for(
    kind: str,
    value: str,
    session: str | None = None,
    profile: str | None = None,
    timeout: int = 15,
) -> None:
    """Wait for selector, text, or time. Kind: selector | text | time."""
    _browser(["wait", kind, value], session=session, profile=profile, timeout=timeout)


def search(
    url: str,
    query: str,
    session: str | None = None,
    profile: str | None = None,
    input_target: str | None = None,
    timeout: int = 30,
) -> tuple[str, int]:
    """Interactive search: navigate, type query, submit, return result HTML."""
    _browser(["open", url], session=session, profile=profile, timeout=timeout)
    _browser(["wait", "time", "2"], session=session, profile=profile, timeout=timeout)

    if input_target:
        type_text(query, target=input_target, session=session, profile=profile, timeout=timeout)
    else:
        _browser(["type", query], session=session, profile=profile, timeout=timeout)
    time.sleep(0.5)
    keys("Enter", session=session, profile=profile, timeout=timeout)

    _browser(["wait", "time", "3"], session=session, profile=profile, timeout=timeout)
    result = _browser(
        ["eval", "document.documentElement.outerHTML"],
        session=session, profile=profile, timeout=timeout,
    )
    return _strip_code_fence(result.stdout), 200


# ── Pre-built adapter ─────────────────────────────────────────────────────────


def run_adapter(
    site: str,
    command: str,
    *args: str,
    profile: str | None = None,
    output_format: str = "json",
    timeout: int = 30,
) -> dict[str, Any]:
    """Call a pre-built OpenCLI site adapter through a specific profile.

    Examples:
        run_adapter("amazon", "search", "chair")
        run_adapter("amazon", "search", "chair", profile="work")
    """
    cmd = [site, command, *args, "-f", output_format]
    result = _cli(cmd, profile=profile, timeout=timeout)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"raw": result.stdout}


# ── Session management ────────────────────────────────────────────────────────


def close(
    session: str | None = None,
    profile: str | None = None,
) -> None:
    """Release the browser session tab lease."""
    _browser(["close"], session=session, profile=profile)


def screenshot(
    path: str,
    session: str | None = None,
    profile: str | None = None,
    timeout: int = 15,
) -> None:
    """Take a screenshot of the current page."""
    _browser(["screenshot", path], session=session, profile=profile, timeout=timeout)
