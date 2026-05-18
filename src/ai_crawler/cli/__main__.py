"""ai-crawler CLI — OpenCLI-style browser commands powered by ai-crawler's anti-detection backends.

Usage:
  aicrawler daemon start                  Start the session daemon (background)
  aicrawler daemon stop                   Stop the daemon
  aicrawler daemon status                 Check if daemon is running

  aicrawler crawl <site...> --query <query> [--pages N]  Automated crawl (auto strategy)

  aicrawler browser <session> open <url>
  aicrawler browser <session> click <target>
  aicrawler browser <session> human_click <target>
  aicrawler browser <session> hover <target>
  aicrawler browser <session> drag <source> <destination>
  aicrawler browser <session> type <text> [target]
  aicrawler browser <session> keys <key>
  aicrawler browser <session> scroll [direction] [amount]
  aicrawler browser <session> human_scroll [amount]
  aicrawler browser <session> extract
  aicrawler browser <session> state
  aicrawler browser <session> eval <js>
  aicrawler browser <session> screenshot [path]
  aicrawler browser <session> wait <kind> <value>
  aicrawler browser <session> content
  aicrawler browser <session> network start|stop
  aicrawler browser <session> search <url> <query> [input_target]
  aicrawler browser <session> close

Start a session:
  aicrawler browser <session> start [--backend camoufox|playwright|cloakbrowser] [--headless/--visible] [--proxy PROXY]

Examples:
  aicrawler crawl amazon walmart --query "inflatable pool" --pages 2
  aicrawler daemon start
  aicrawler browser mysession start --backend camoufox
  aicrawler browser mysession open https://example.com
  aicrawler browser mysession state
  aicrawler browser mysession click [0]
  aicrawler browser mysession extract
  aicrawler browser mysession close
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

from ai_crawler.cli.daemon import send_command, _socket_path


def _is_daemon_running() -> bool:
    sock_path = _socket_path()
    if not os.path.exists(sock_path):
        return False
    try:
        resp = send_command({"cmd": "sessions"}, timeout=2.0)
        return resp.get("ok") is True
    except Exception:
        return False


def _start_daemon():
    """Start the daemon as a background process."""
    if _is_daemon_running():
        print("Daemon is already running.")
        return

    env = os.environ.copy()
    # Use the same Python interpreter
    cmd = [sys.executable, "-m", "ai_crawler.cli.daemon"]
    proc = subprocess.Popen(
        cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    # Wait for daemon to become ready (imports can take 5-10s)
    for _ in range(60):
        time.sleep(0.2)
        if _is_daemon_running():
            print(f"Daemon started (pid={proc.pid})")
            return
    print(f"Daemon process spawned (pid={proc.pid}) but not responding yet.")


def _stop_daemon():
    """Stop the daemon."""
    resp = send_command({"cmd": "stop_daemon"}, timeout=2.0)
    if resp.get("ok"):
        print("Daemon stopped.")
    else:
        # Force kill
        sock_path = _socket_path()
        if os.path.exists(sock_path):
            os.unlink(sock_path)
        print("Daemon forcefully stopped.")


def daemon_command(args):
    if args.daemon_action == "start":
        _start_daemon()
    elif args.daemon_action == "stop":
        _stop_daemon()
    elif args.daemon_action == "status":
        if _is_daemon_running():
            print("Daemon is running.")
        else:
            print("Daemon is not running.")


def browser_command(args):
    cmd: dict = {"cmd": args.browser_action, "session": args.session}

    if args.browser_action == "start":
        cmd["backend"] = getattr(args, "backend", "playwright")
        cmd["headless"] = getattr(args, "headless", True)
        cmd["proxy"] = getattr(args, "proxy", None)
    elif args.browser_action == "open":
        cmd["args"] = [args.url]
    elif args.browser_action == "click":
        cmd["args"] = [args.target]
    elif args.browser_action == "type":
        if args.target:
            cmd["args"] = [args.text, args.target]
        else:
            cmd["args"] = [args.text]
    elif args.browser_action == "keys":
        cmd["args"] = [args.key]
    elif args.browser_action == "scroll":
        cmd["args"] = [args.direction, str(args.amount)]
    elif args.browser_action == "eval":
        cmd["args"] = [args.js]
    elif args.browser_action == "screenshot":
        cmd["args"] = [args.path] if args.path else []
    elif args.browser_action == "wait":
        cmd["args"] = [args.wait_kind, args.wait_value]
    elif args.browser_action == "network":
        if args.net_action == "start":
            cmd["cmd"] = "network_start"
        else:
            cmd["cmd"] = "network_stop"
    elif args.browser_action == "hover":
        cmd["args"] = [args.target]
    elif args.browser_action == "human_click":
        cmd["args"] = [args.target]
    elif args.browser_action == "drag":
        cmd["args"] = [args.source, args.destination]
    elif args.browser_action == "human_scroll":
        cmd["args"] = [str(args.amount)]
    elif args.browser_action == "search":
        cmd["args"] = [args.search_url, args.query]
        if args.input_target:
            cmd["args"].append(args.input_target)

    resp = send_command(cmd)
    _print_response(resp)


def crawl_command(args):
    """Run automated crawl with automatic strategy selection."""
    from ai_crawler import run_crawl
    from ai_crawler.core.config import config

    storage_backend = None
    if args.storage == "mirage":
        from ai_crawler.storage.mirage import MirageStorageBackend
        from mirage import MountMode, Workspace

        if args.mirage_disk:
            from mirage.resource.disk import DiskResource
            Resource = lambda: DiskResource(root=args.mirage_disk)
        else:
            from mirage.resource.ram import RAMResource
            Resource = RAMResource

        ws = Workspace(
            {"/output": Resource(), "/traces": Resource(), "/memory": Resource()},
            mode=MountMode.WRITE,
        )
        storage_backend = MirageStorageBackend(ws, mount_prefix="/output")

    result = run_crawl(
        sites=args.sites,
        query=args.query,
        pages=args.pages,
        proxy_username=config.THORDATA_RESIDENTIAL_USERNAME,
        proxy_password=config.THORDATA_RESIDENTIAL_PASSWORD,
        llm_api_key=config.OPENAI_API_KEY,
        captcha_api_key=config.TWO_CAPTCHA_API_KEY,
        output_dir=args.output_dir,
        traces_dir=args.traces_dir,
        max_ip_retries=args.max_ip_retries,
        proxy_disabled=args.proxy_disabled,
        storage_backend=storage_backend,
        save_html=args.save_html,
    )

    print(f"Products: {len(result.products)}")
    print(f"Success: {result.stats['tasks_success']}/{result.stats['tasks_total']}")
    print(f"Output: {', '.join(result.output_files) if result.output_files else 'none'}")
    print(f"Traces: {result.traces_file}")
    if result.stats.get('block_types'):
        print(f"Block types: {result.stats['block_types']}")


def _print_response(resp: dict):
    if resp.get("ok"):
        result = resp.get("result")
        if result is not None:
            if isinstance(result, (dict, list)):
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print(result)
        else:
            # Some commands return top-level keys (e.g. start returns session/backend)
            extra = {k: v for k, v in resp.items() if k not in ("ok", "result")}
            if extra:
                print(json.dumps(extra, indent=2, ensure_ascii=False))
    else:
        print(f"Error: {resp.get('error', 'unknown')}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="aicrawler",
        description="OpenCLI-style browser commands on ai-crawler's anti-detection backends",
    )
    sub = parser.add_subparsers(dest="command")

    # ── daemon ────────────────────────────────────────────────────────
    daemon_p = sub.add_parser("daemon", help="Manage the session daemon")
    daemon_p.add_argument("daemon_action", choices=["start", "stop", "status"])

    # ── browser ───────────────────────────────────────────────────────
    browser_p = sub.add_parser("browser", help="Browser session commands")
    browser_p.add_argument("session", help="Session name (e.g. 'mysession')")
    browser_p.add_argument(
        "browser_action",
        choices=[
            "start", "open", "click", "human_click", "hover", "drag",
            "type", "keys", "scroll", "human_scroll",
            "extract", "state", "eval", "screenshot", "wait",
            "content", "network", "search", "close",
        ],
        help="Action to perform",
    )

    # -- start args
    browser_p.add_argument("--backend", default="camoufox",
                           choices=["playwright", "camoufox", "cloakbrowser", "seleniumbase", "undetected_chromedriver"],
                           help="Browser backend (default: camoufox)")
    browser_p.add_argument("--visible", dest="headless", action="store_false", default=True,
                           help="Run browser visibly (not headless)")
    browser_p.add_argument("--proxy", help="Proxy server URL")

    # -- open args
    browser_p.add_argument("--url", help="URL for 'open' and 'search' commands")

    # -- click args
    browser_p.add_argument("--target", help="CSS selector or [N] index for 'click'")

    # -- type args
    browser_p.add_argument("--text", help="Text to type")

    # -- keys args
    browser_p.add_argument("--key", help="Key to press (Enter, Escape, ArrowDown, etc.)")

    # -- scroll args
    browser_p.add_argument("--direction", default="down", choices=["up", "down"],
                           help="Scroll direction (default: down)")
    browser_p.add_argument("--amount", type=int, default=300,
                           help="Scroll amount in pixels (default: 300)")

    # -- eval args
    browser_p.add_argument("--js", help="JavaScript to evaluate")

    # -- screenshot args
    browser_p.add_argument("--path", help="Path for screenshot")

    # -- wait args
    browser_p.add_argument("--wait-kind", dest="wait_kind", choices=["selector", "text", "time"],
                           help="Wait kind")
    browser_p.add_argument("--wait-value", dest="wait_value", help="Wait value")

    # -- network args
    browser_p.add_argument("--net-action", dest="net_action", choices=["start", "stop"],
                           help="Network capture action")

    # -- drag args
    browser_p.add_argument("--source", help="Source CSS selector or [N] index for 'drag'")
    browser_p.add_argument("--destination", help="Destination CSS selector or [N] index for 'drag'")

    # -- search args
    browser_p.add_argument("--search-url", dest="search_url", help="URL for 'search'")
    browser_p.add_argument("--query", help="Search query")
    browser_p.add_argument("--input-target", dest="input_target",
                           help="Input element to click before typing")

    # ── crawl ─────────────────────────────────────────────────────────
    crawl_p = sub.add_parser("crawl", help="Automated crawl with automatic strategy selection")
    crawl_p.add_argument("sites", nargs="+", help="Site(s) to crawl (e.g. amazon walmart)")
    crawl_p.add_argument("--query", required=True, help="Search query")
    crawl_p.add_argument("--pages", type=int, default=1, help="Number of search result pages (default: 1)")
    crawl_p.add_argument("--output-dir", default="output", help="Output directory (default: output)")
    crawl_p.add_argument("--traces-dir", default="traces", help="Traces directory (default: traces)")
    crawl_p.add_argument("--max-ip-retries", type=int, default=3, help="Max IP retries (default: 3)")
    crawl_p.add_argument("--proxy-disabled", action="store_true", help="Disable proxy")
    crawl_p.add_argument("--storage", default="local", choices=["local", "mirage"],
                         help="Storage backend (default: local)")
    crawl_p.add_argument("--mirage-disk", help="Directory for Mirage DiskResource mount (persistent)")
    crawl_p.add_argument("--save-html", action="store_true", help="Save raw HTML for each successful crawl")

    args = parser.parse_args()

    if args.command == "daemon":
        daemon_command(args)
    elif args.command == "browser":
        browser_command(args)
    elif args.command == "crawl":
        crawl_command(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
