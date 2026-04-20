import re
import httpx
import base64

from ai_crawler.integrations.captcha.solver import CaptchaSolver, CaptchaType


class CaptchaDetector:
    CAPTCHA_PATTERNS = [
        "captcha",
        "are you a robot",
        "prove you're not",
        "i am not a robot",
        "verify you are human",
        "complete the captcha",
        "recaptcha",
        "hcaptcha",
        "cf-challenge",
        "checking your browser",
        "type the characters",
        "enter the code",
        "enter the letters",
        "type the text",
        "image captcha",
    ]

    IMAGE_CAPTCHA_PATTERNS = [
        r'<input[^>]+type=["\']image["\'][^>]*src=["\']([^"\']+)["\']',
        r'<img[^>]+class=["\'][^"\']*captcha[^"\']*["\'][^>]*src=["\']([^"\']+)["\']',
        r'<img[^>]+id=["\'][^"\']*captcha[^"\']*["\'][^>]*src=["\']([^"\']+)["\']',
        r"data:image/[^;]+;base64,([a-zA-Z0-9+/=]+)",
    ]

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key
        self._solver = CaptchaSolver(api_key) if api_key else None

    def detect(self, html: str, status_code: int = 200) -> tuple[bool, str, str, str]:
        if status_code != 200:
            return False, "", "", ""
        text = html.lower()
        for pattern in self.CAPTCHA_PATTERNS:
            if pattern in text:
                captcha_type, site_key, action = self._extract_captcha_info(html)
                return True, captcha_type, site_key, action
        return False, "", "", ""

    def _extract_captcha_info(self, html: str) -> tuple[str, str, str]:
        text = html
        action = "verify"

        if "data-sitekey" in text:
            idx = text.find("data-sitekey=")
            key_start = text.find('"', idx + 14)
            key_end = text.find('"', key_start + 1)
            site_key = text[key_start + 1 : key_end]
            if "recaptcha" in text.lower():
                return CaptchaType.RECAPTCHA_V2.value, site_key, action
            elif "hcaptcha" in text.lower():
                return CaptchaType.HCAPTCHA.value, site_key, action
            else:
                return CaptchaType.RECAPTCHA_V2.value, site_key, action

        if "sitekey" in text:
            idx = text.find("sitekey=")
            key_start = text.find('"', idx + 9)
            key_end = text.find('"', key_start + 1)
            site_key = text[key_start + 1 : key_end]
            if "turnstile" in text.lower():
                return CaptchaType.CLOUDFLARE_TURNSTILE.value, site_key, action
            return CaptchaType.RECAPTCHA_V2.value, site_key, action

        recaptcha_v3_pattern = r"recaptcha/api\.js\?render=([a-zA-Z0-9_-]+)"
        match = re.search(recaptcha_v3_pattern, text)
        if match:
            site_key = match.group(1)
            action_match = re.search(
                r"grecaptcha\.execute\([^,]+,\s*\{[^}]*action:\s*['\"]([^'\"]+)['\"]", text
            )
            if action_match:
                action = action_match.group(1)
            return CaptchaType.RECAPTCHA_V3.value, site_key, action

        for pattern in self.IMAGE_CAPTCHA_PATTERNS:
            img_match = re.search(pattern, text, re.IGNORECASE)
            if img_match:
                if "data:image" in img_match.group(0):
                    base64_data = img_match.group(1)
                    return CaptchaType.IMAGE_CAPTCHA.value, base64_data, action
                else:
                    img_url = img_match.group(1)
                    return CaptchaType.IMAGE_CAPTCHA.value, img_url, action

        return "", "", action

    def solve(self, captcha_type: str, site_key: str, page_url: str, action: str = "verify") -> str:
        if not self._solver:
            raise ValueError("No captcha solver configured")

        ct = CaptchaType(captcha_type)

        if ct == CaptchaType.IMAGE_CAPTCHA:
            return self._solve_image(site_key, page_url)

        if ct == CaptchaType.RECAPTCHA_V3:
            return self._solver.solve_recaptcha_v3(site_key, page_url, action)

        return self._solver.solve(ct, site_key, page_url)

    def _solve_image(self, image_data: str, page_url: str) -> str:
        if image_data.startswith("data:image"):
            base64_part = image_data.split(",")[1]
            return self._solver.solve_image(base64_part)

        full_url = (
            image_data
            if image_data.startswith("http")
            else page_url.rsplit("/", 1)[0] + "/" + image_data
        )
        resp = httpx.get(full_url, timeout=30)
        img_base64 = base64.b64encode(resp.content).decode()
        return self._solver.solve_image(img_base64)
