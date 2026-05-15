from ai_crawler.spider.engine.anti_bot.fingerprinter import AntiBotFingerprinter


def test_fingerprinter_identifies_cloudflare_js_challenge():
    fp = AntiBotFingerprinter().infer(
        html="Checking your browser before accessing site. cf-challenge",
        headers={"server": "cloudflare", "cf-ray": "abc"},
        status_code=403,
        block_type="cloudflare",
        waf_detected="cloudflare",
        block_reason="Cloudflare Challenge",
    )

    assert fp.vendor == "cloudflare"
    assert "js_challenge" in fp.mechanisms
    assert fp.confidence >= 0.9
    assert fp.recommended_response == "prefer_real_browser_with_cookies_and_human_behavior"


def test_fingerprinter_identifies_proxy_transport_error():
    fp = AntiBotFingerprinter().infer(
        html="This site can't be reached ERR_NO_SUPPORTED_PROXIES",
        headers={},
        status_code=200,
        block_type="http_timeout",
        waf_detected="",
        block_reason="browser error",
    )

    assert fp.vendor == "browser_error"
    assert "proxy_transport_error" in fp.mechanisms
    assert fp.confidence >= 0.9


def test_fingerprinter_identifies_captcha_gate():
    fp = AntiBotFingerprinter().infer(
        html="Please prove you're not a robot and complete the captcha",
        headers={},
        status_code=200,
        block_type="captcha",
        waf_detected="",
        block_reason="captcha",
    )

    assert "captcha_gate" in fp.mechanisms
    assert fp.recommended_response == "increase_browser_realism_or_use_captcha_solver"


def test_fingerprinter_marks_bot_score_gate():
    fp = AntiBotFingerprinter().infer(
        html="Automated requests detected due to unusual traffic",
        headers={},
        status_code=200,
        block_type="bot_detected",
        waf_detected="",
        block_reason="bot",
    )

    assert "bot_score_gate" in fp.mechanisms
    assert fp.confidence >= 0.85
