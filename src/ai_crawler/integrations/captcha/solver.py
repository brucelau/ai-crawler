"""2Captcha solver integration."""

from __future__ import annotations

import time
from enum import Enum
from typing import Any


class CaptchaType(str, Enum):
    RECAPTCHA_V2 = "recaptcha-v2"
    RECAPTCHA_V3 = "recaptcha-v3"
    HCAPTCHA = "hcaptcha"
    IMAGE_CAPTCHA = "imagecaptcha"
    CLOUDFLARE_TURNSTILE = "turnstile"


class CaptchaSolver:
    BASE_URL = "https://2captcha.com"

    def __init__(self, api_key: str, timeout: int = 120, polling_interval: int = 5):
        self.api_key = api_key
        self.timeout = timeout
        self.polling_interval = polling_interval

    def _request(self, endpoint: str, **params) -> dict[str, Any]:
        import httpx

        params["key"] = self.api_key
        params["json"] = 1
        resp = httpx.get(f"{self.BASE_URL}/{endpoint}", params=params, timeout=30)
        return resp.json()

    def _wait_result(self, task_id: str) -> str:
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            result = self._request("res.php", action="get", id=task_id)
            if result.get("status") == 1:
                return result["request"]
            if result.get("request") == "CAPCHA_NOT_READY":
                time.sleep(self.polling_interval)
            else:
                raise RuntimeError(f"Captcha solve failed: {result}")
        raise TimeoutError(f"Captcha solving timed out after {self.timeout}s")

    def solve_recaptcha_v2(self, site_key: str, page_url: str) -> str:
        result = self._request(
            "in.php", method="userrecaptcha", googlekey=site_key, pageurl=page_url
        )
        if result.get("status") != 1:
            raise RuntimeError(f"Failed to submit captcha: {result}")
        task_id = result["request"]
        return self._wait_result(task_id)

    def solve_hcaptcha(self, site_key: str, page_url: str) -> str:
        result = self._request("in.php", method="hcaptcha", sitekey=site_key, pageurl=page_url)
        if result.get("status") != 1:
            raise RuntimeError(f"Failed to submit hCaptcha: {result}")
        task_id = result["request"]
        return self._wait_result(task_id)

    def solve_image(self, image_base64: str) -> str:
        result = self._request("in.php", method="base64", body=image_base64)
        if result.get("status") != 1:
            raise RuntimeError(f"Failed to submit image captcha: {result}")
        task_id = result["request"]
        return self._wait_result(task_id)

    def solve_turnstile(self, site_key: str, page_url: str) -> str:
        result = self._request("in.php", method="turnstile", sitekey=site_key, pageurl=page_url)
        if result.get("status") != 1:
            raise RuntimeError(f"Failed to submit turnstile: {result}")
        task_id = result["request"]
        return self._wait_result(task_id)

    def solve_recaptcha_v3(
        self, site_key: str, page_url: str, action: str = "verify", min_score: float = 0.9
    ) -> str:
        result = self._request(
            "in.php",
            method="userrecaptcha",
            version="v3",
            googlekey=site_key,
            pageurl=page_url,
            action=action,
            min_score=min_score,
        )
        if result.get("status") != 1:
            raise RuntimeError(f"Failed to submit reCAPTCHA v3: {result}")
        task_id = result["request"]
        return self._wait_result(task_id)

    def solve(self, captcha_type: CaptchaType, site_key: str, page_url: str, **kwargs) -> str:
        if captcha_type == CaptchaType.RECAPTCHA_V2:
            return self.solve_recaptcha_v2(site_key, page_url)
        elif captcha_type == CaptchaType.RECAPTCHA_V3:
            action = kwargs.get("action", "verify")
            min_score = kwargs.get("min_score", 0.9)
            return self.solve_recaptcha_v3(site_key, page_url, action, min_score)
        elif captcha_type == CaptchaType.HCAPTCHA:
            return self.solve_hcaptcha(site_key, page_url)
        elif captcha_type == CaptchaType.CLOUDFLARE_TURNSTILE:
            return self.solve_turnstile(site_key, page_url)
        else:
            raise ValueError(f"Unsupported captcha type: {captcha_type}")
