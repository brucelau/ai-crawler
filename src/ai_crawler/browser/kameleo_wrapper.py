"""Kameleo browser wrapper with fingerprint browser capabilities."""

from __future__ import annotations

import json
import time
from typing import Any

from ai_crawler.browser.base import BaseWrapper


class KameleoWrapper(BaseWrapper):
    """Wrapper for Kameleo fingerprint browser API."""

    def __init__(
        self,
        proxy: str | None = None,
        headless: bool = True,
        wait_time: float = 8.0,
        human_scroll: bool = True,
        dynamic_profile: dict | None = None,
        api_url: str = "http://localhost:5050",
        api_key: str | None = None,
        profile_id: str | None = None,
    ):
        super().__init__(proxy, headless, wait_time, human_scroll, dynamic_profile)
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.profile_id = profile_id
        self._client = None
        self._browser_conn_id = None

    def _get_client(self):
        """Get or create Kameleo client."""
        if self._client is None:
            try:
                from kameleo_client import KameleoClient

                self._client = KameleoClient(self.api_url, self.api_key)
            except ImportError:
                try:
                    import requests

                    self._client = None
                except ImportError:
                    raise ImportError("kameleo-client or requests library required")
        return self._client

    def _apply_fingerprint_profile(self) -> dict:
        """Apply dynamic fingerprint profile settings to Kameleo."""
        profile_settings = {
            "browser": {
                "acceptLanguages": self.dynamic_profile.get("languages", ["en-US"]),
                "userAgent": self.dynamic_profile.get(
                    "user_agent",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                ),
            },
            "device": {
                "colorDepth": 24,
                "pixelRatio": self.dynamic_profile.get("device_pixel_ratio", 2.0),
                "screenResolution": {
                    "width": self.dynamic_profile.get("screen_width", 1920),
                    "height": self.dynamic_profile.get("screen_height", 1080),
                },
            },
        }

        if self.proxy:
            parts = self.proxy.split("@")
            if len(parts) == 2:
                auth, host = parts
                auth_parts = auth.split(":")
                if len(auth_parts) == 2:
                    profile_settings["proxy"] = {
                        "host": host,
                        "port": 80,
                        "username": auth_parts[0],
                        "password": auth_parts[1],
                        "protocol": "http",
                    }

        return profile_settings

    def launch(self, profile_id: str | None = None) -> str:
        """Launch Kameleo browser with profile and return connection ID."""
        client = self._get_client()

        if profile_id is None:
            profile_id = self.profile_id

        if profile_id is None:
            profile_settings = self._apply_fingerprint_profile()
            try:
                profile = client.create_profiles(
                    [
                        {
                            "platform": "windows",
                            "browser": "chrome",
                            "profileType": "default",
                            "settings": profile_settings,
                        }
                    ]
                )[0]
                profile_id = profile.id
            except Exception as e:
                raise e

        try:
            start_options = client.get_start_options(profile_id)
            browser_conn = client.start_browser_with_profile(profile_id, start_options)
            self._browser_conn_id = browser_conn.id
            return browser_conn.id
        except Exception as e:
            raise e

    def navigate(self, url: str) -> str:
        """Navigate to URL and return page content."""
        client = self._get_client()

        if self._browser_conn_id is None:
            self.launch()

        try:
            client.navigate_to(self._browser_conn_id, url)
            time.sleep(self.wait_time)

            if self.human_scroll:
                self._human_scroll()

            page_content = client.get_page_content(self._browser_conn_id)
            return page_content
        except Exception as e:
            raise e

    def _human_scroll(self) -> None:
        """Send human-like scroll commands via Kameleo."""
        try:
            client = self._get_client()
            for _ in range(3):
                scroll_y = 300 + int(time.time() % 500)
                client.send_command(
                    self._browser_conn_id,
                    {
                        "type": "scroll",
                        "x": 0,
                        "y": scroll_y,
                    },
                )
                time.sleep(0.8 + time.time() % 0.7)
        except Exception:
            pass

    def stop(self) -> None:
        """Stop the Kameleo browser."""
        if self._browser_conn_id:
            try:
                client = self._get_client()
                client.stop_browser(self._browser_conn_id)
            except Exception:
                pass
            finally:
                self._browser_conn_id = None

    def fetch(self, url: str) -> tuple[str, int]:
        """Fetch a URL and return (page_content, status_code)."""
        try:
            self.launch()
            return self.navigate(url), 200
        finally:
            self.stop()


def _sync_fetch(
    url: str,
    api_url: str = "http://localhost:5050",
    api_key: str | None = None,
    proxy: str | None = None,
    wait_time: float = 8.0,
    human_scroll: bool = True,
    dynamic_profile: dict | None = None,
) -> tuple[str, int]:
    wrapper = KameleoWrapper(
        api_url=api_url,
        api_key=api_key,
        proxy=proxy,
        wait_time=wait_time,
        human_scroll=human_scroll,
        dynamic_profile=dynamic_profile or {},
    )
    return wrapper.fetch(url)


async def async_fetch(
    url: str,
    api_url: str = "http://localhost:5050",
    api_key: str | None = None,
    proxy: str | None = None,
    wait_time: float = 8.0,
    human_scroll: bool = True,
    dynamic_profile: dict | None = None,
) -> tuple[str, int]:
    import asyncio

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        _sync_fetch,
        url,
        api_url,
        api_key,
        proxy,
        wait_time,
        human_scroll,
        dynamic_profile,
    )
