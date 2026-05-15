from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class AntiBotFingerprint:
    vendor: str = "unknown"
    mechanisms: list[str] = field(default_factory=list)
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    recommended_response: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class AntiBotFingerprinter:
    def infer(
        self,
        html: str,
        headers: dict,
        status_code: int | None,
        block_type: str,
        waf_detected: str,
        block_reason: str,
    ) -> AntiBotFingerprint:
        lowered = (html or "").lower()
        evidence: list[str] = []
        mechanisms: list[str] = []
        vendor = waf_detected or "unknown"
        confidence = 0.25

        if waf_detected:
            evidence.append(f"waf_detected:{waf_detected}")
            confidence = max(confidence, 0.75)

        if status_code in {403, 429, 451}:
            mechanisms.append("http_status_block")
            evidence.append(f"status:{status_code}")
            confidence = max(confidence, 0.7)

        if "err_no_supported_proxies" in lowered or "proxy error" in lowered:
            mechanisms.append("proxy_transport_error")
            evidence.append("browser_error:proxy")
            confidence = max(confidence, 0.95)
            if vendor == "unknown":
                vendor = "browser_error"

        if "this site can't be reached" in lowered or "chrome-error://" in lowered:
            mechanisms.append("browser_transport_error")
            evidence.append("browser_error:transport")
            confidence = max(confidence, 0.9)
            if vendor == "unknown":
                vendor = "browser_error"

        if block_type == "captcha" or "captcha" in lowered:
            mechanisms.append("captcha_gate")
            evidence.append("pattern:captcha")
            confidence = max(confidence, 0.85)

        if (
            block_type == "cloudflare"
            or "cf-challenge" in lowered
            or "checking your browser" in lowered
        ):
            mechanisms.append("js_challenge")
            evidence.append("pattern:cloudflare_challenge")
            confidence = max(confidence, 0.9)
            if vendor == "unknown":
                vendor = "cloudflare"

        if (
            block_type == "bot_detected"
            or "automated requests" in lowered
            or "unusual traffic" in lowered
        ):
            mechanisms.append("bot_score_gate")
            evidence.append("pattern:bot_detected")
            confidence = max(confidence, 0.85)

        if block_type == "empty_response":
            mechanisms.append("empty_shell_or_soft_block")
            evidence.append("detector:empty_response")
            confidence = max(confidence, 0.6)

        if vendor in {"datadome", "perimeterx", "akamai", "imperva", "incapsula"}:
            mechanisms.append("edge_waf")
            confidence = max(confidence, 0.85)

        mechanisms = list(dict.fromkeys(mechanisms))
        evidence = list(dict.fromkeys(evidence))
        recommended = self._recommend(mechanisms)

        return AntiBotFingerprint(
            vendor=vendor,
            mechanisms=mechanisms,
            confidence=round(confidence, 2),
            evidence=evidence,
            recommended_response=recommended,
        )

    @staticmethod
    def _recommend(mechanisms: list[str]) -> str:
        if "proxy_transport_error" in mechanisms or "browser_transport_error" in mechanisms:
            return "fix_browser_or_proxy_path_before_escalating"
        if "captcha_gate" in mechanisms:
            return "increase_browser_realism_or_use_captcha_solver"
        if "js_challenge" in mechanisms:
            return "prefer_real_browser_with_cookies_and_human_behavior"
        if "bot_score_gate" in mechanisms:
            return "rotate_identity_and_raise_browser_realism"
        if "empty_shell_or_soft_block" in mechanisms:
            return "retry_with_richer_render_or_semantic_confirmation"
        if "http_status_block" in mechanisms:
            return "rotate_ip_or_change_entry_strategy"
        return "observe_and_rank_with_policy_engine"
