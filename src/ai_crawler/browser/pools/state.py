from collections import OrderedDict
from threading import RLock


class PoolState:
    def __init__(self):
        self._pool_lock = RLock()
        self._session_cookies: dict[str, list] = {}
        self._playwright_runtime = None
        self._playwright_browsers: dict[str, any] = {}
        self._playwright_contexts: dict[str, any] = {}
        self._camoufox_launchers: dict[str, any] = {}
        self._camoufox_browsers: dict[str, any] = {}
        self._camoufox_browser_meta: dict[str, dict[str, float | int]] = {}
        self._uc_proxy_bridges: dict[str, any] = {}
        self._uc_drivers: OrderedDict[str, any] = OrderedDict()
        self._uc_driver_meta: dict[str, dict[str, float | int]] = {}
        self._cloak_browsers: dict[str, any] = {}
        self._camoufox_pool_cap = 2
        self._camoufox_max_leases = 5
        self._camoufox_idle_ttl_seconds = 300
        self._uc_pool_cap = 2
        self._uc_max_leases = 2
        self._uc_idle_ttl_seconds = 120
        self._stats = {
            "playwright_runtime_created": 0,
            "playwright_browser_created": 0,
            "playwright_browser_reused": 0,
            "playwright_context_created": 0,
            "playwright_context_reused": 0,
            "camoufox_browser_created": 0,
            "camoufox_browser_reused": 0,
            "camoufox_browser_evicted": 0,
            "camoufox_healthcheck_failed": 0,
            "uc_browser_created": 0,
            "uc_browser_reused": 0,
            "uc_browser_evicted": 0,
            "uc_healthcheck_failed": 0,
            "uc_reset_failed": 0,
            "cloak_browser_created": 0,
            "cloak_browser_reused": 0,
            "pages_opened": 0,
            "pages_released": 0,
            "ad_block_handlers_installed": 0,
            "ad_scripts_blocked": 0,
        }

    def increment_stat(self, key: str, amount: int = 1) -> None:
        with self._pool_lock:
            self._stats[key] = self._stats.get(key, 0) + amount

    def stats_snapshot(self) -> dict:
        with self._pool_lock:
            snapshot = dict(self._stats)
            snapshot.update(
                {
                    "active_playwright_browsers": len(self._playwright_browsers),
                    "active_playwright_contexts": len(self._playwright_contexts),
                    "active_camoufox_browsers": len(self._camoufox_browsers),
                    "active_uc_proxy_bridges": len(self._uc_proxy_bridges),
                    "active_uc_browsers": len(self._uc_drivers),
                    "active_cloak_browsers": len(self._cloak_browsers),
                }
            )
            return snapshot
