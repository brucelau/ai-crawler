"""Hardware fingerprint spoofer for bypassing WAF detection."""

from __future__ import annotations

import hashlib
import json
import time


_cached_scripts: dict[str, str] = {}


def generate_fingerprint_script(
    session_id: str | None = None,
    gpu_vendor: str | None = None,
    gpu_renderer: str | None = None,
    screen_width: int = 1920,
    screen_height: int = 1080,
    device_pixel_ratio: float = 2.0,
    platform_string: str = "MacIntel",
    cores: int = 8,
    memory: int = 8,
    languages: list | None = None,
    connection_type: str = "4g",
    downlink: int = 10,
    rtt: int = 50,
    plugins: list | None = None,
    usb: dict | None = None,
    media_devices: list | None = None,
    battery: dict | None = None,
    webdriver_value: str | None = None,
    permissions_default: str = "default",
    orientation_angle: int = 0,
    orientation_type: str = "landscape-primary",
) -> str:
    """Generate JavaScript code to spoof hardware fingerprints."""
    global _cached_scripts

    cache_key = session_id or f"{gpu_vendor}_{gpu_renderer}_{screen_width}x{screen_height}"
    if cache_key in _cached_scripts:
        return _cached_scripts[cache_key]

    seed = _generate_session_seed(session_id)

    gpu_vendor = gpu_vendor or "NVIDIA"
    gpu_renderer = gpu_renderer or "NVIDIA GeForce RTX 4090"
    languages = languages or ["en-US", "en", "es"]
    languages_json = json.dumps(languages)
    plugins = plugins or [
        {
            "name": "Chrome PDF Plugin",
            "description": "Portable Document Format",
            "filename": "internal-pdf-viewer",
        },
        {
            "name": "Chrome PDF Viewer",
            "description": "",
            "filename": "mhjfbmdgcfjbbpaeojofohoefgiehjai",
        },
        {"name": "Native Client", "description": "", "filename": "internal-nacl-plugin"},
    ]
    plugins_json = json.dumps(plugins)
    usb = usb or {"getDevices": []}
    usb_json = json.dumps(usb)
    media_devices = media_devices or [
        {"kind": "audioinput", "deviceId": "default", "label": "", "groupId": "grp1"},
        {"kind": "videoinput", "deviceId": "default", "label": "", "groupId": "grp2"},
    ]
    media_devices_json = json.dumps(media_devices)
    battery = battery or {"charging": True, "level": 0.95, "chargingTime": 0}
    battery_json = json.dumps(battery)
    webdriver_value = webdriver_value or "undefined"

    script = f"""
(function() {{
    'use strict';

    const _fpSeed = {seed};
    const _noiseCache = new Map();

    function _hash(x, y, s) {{
        const key = x * 1000000 + y * 1000 + s;
        if (_noiseCache.has(key)) return _noiseCache.get(key);
        let h = (s ^ (s >> 13)) * 2147483647;
        h = ((x * 374761393) ^ (y * 668265263)) ^ (h ^ (h >> 16));
        h = (h * 1274126177) ^ (h ^ (h >> 13));
        const noise = ((h ^ (h >> 16)) & 0x7FFFFFFF) / 0x7FFFFFFF;
        const val = (noise - 0.5) * 0.6;
        _noiseCache.set(key, val);
        return val;
    }}

    Object.defineProperty(navigator, 'hardwareConcurrency', {{
        get: () => {cores}
    }});

    Object.defineProperty(navigator, 'deviceMemory', {{
        get: () => {memory}
    }});

    Object.defineProperty(navigator, 'platform', {{
        get: () => '{platform_string}'
    }});

    Object.defineProperty(navigator, 'maxTouchPoints', {{
        get: () => 0
    }});

    Object.defineProperty(navigator, 'touchSupport', {{
        get: () => false
    }});

    Object.defineProperty(navigator, 'webdriver', {{
        get: () => {webdriver_value}
    }});

    const _origQuery = window.navigator.permissions ? window.navigator.permissions.query : null;
    if (_origQuery) {{
        window.navigator.permissions.query = function(query) {{
            if (query && query.name === 'notifications') {{
                return Promise.resolve({{ state: '{permissions_default}', onchange: null }});
            }}
            return _origQuery.call(this, query);
        }};
    }};

    if (screen.orientation) {{
        Object.defineProperty(screen.orientation, 'angle', {{
            get: () => {orientation_angle}
        }});
        Object.defineProperty(screen.orientation, 'type', {{
            get: () => '{orientation_type}'
        }});
    }} else {{
        Object.defineProperty(screen, 'orientation', {{
            get: () => ({{ angle: {orientation_angle}, type: '{orientation_type}', onchange: null }})
        }});
    }};

    Object.defineProperty(screen, 'width', {{
        get: () => {screen_width}
    }});
    Object.defineProperty(screen, 'height', {{
        get: () => {screen_height}
    }});
    Object.defineProperty(screen, 'availWidth', {{
        get: () => {screen_width}
    }});
    Object.defineProperty(screen, 'availHeight', {{
        get: () => {screen_height - 40}
    }});

    Object.defineProperty(window, 'devicePixelRatio', {{
        get: () => {device_pixel_ratio} + (Math.random() - 0.5) * 0.005
    }});

    const _UNMASKED_VENDOR = 0x9245;
    const _UNMASKED_RENDERER = 0x9246;

    const _origGetContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(type, attrs) {{
        const ctx = _origGetContext.call(this, type, attrs);
        if (ctx && (type === 'webgl' || type === 'webgl2' || type === 'experimental-webgl')) {{
            const _origGetParam = ctx.getParameter.bind(ctx);
            ctx.getParameter = function(p) {{
                if (p === _UNMASKED_VENDOR) return '{gpu_vendor}';
                if (p === _UNMASKED_RENDERER) return '{gpu_renderer}';
                return _origGetParam(p);
            }};
        }}
        return ctx;
    }};

    const _origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
    if (_origGetImageData) {{
        CanvasRenderingContext2D.prototype.getImageData = function(sx, sy, sw, sh) {{
            const d = _origGetImageData.call(this, sx, sy, sw, sh);
            for (let i = 0; i < d.data.length; i += 4) {{
                const x = (i >> 2) % sw;
                const y = Math.floor((i >> 2) / sw);
                const n = _hash(x + sx, y + sy, _fpSeed);
                d.data[i] = Math.max(0, Math.min(255, d.data[i] + n));
                d.data[i+1] = Math.max(0, Math.min(255, d.data[i+1] + n));
                d.data[i+2] = Math.max(0, Math.min(255, d.data[i+2] + n));
            }}
            return d;
        }};
    }};

    const _origReadPixels = WebGLRenderingContext.prototype.readPixels;
    if (_origReadPixels) {{
        WebGLRenderingContext.prototype.readPixels = function(x, y, w, h, f, t, p) {{
            const r = _origReadPixels.call(this, x, y, w, h, f, t, p);
            for (let i = 0; i < p.length; i += 4) {{
                const n = _hash(i, _fpSeed, _fpSeed) * 0.3;
                p[i] = Math.max(0, Math.min(255, p[i] + n));
                p[i+1] = Math.max(0, Math.min(255, p[i+1] + n));
                p[i+2] = Math.max(0, Math.min(255, p[i+2] + n));
            }}
            return r;
        }};
    }};

    const _OrigAudioContext = window.AudioContext || window.webkitAudioContext;
    if (_OrigAudioContext) {{
        window.AudioContext = function(opts) {{ return new _OrigAudioContext(opts); }};
        window.AudioContext.prototype = _OrigAudioContext.prototype;
        window.webkitAudioContext = window.AudioContext;
    }};

    const _OrigRTC = window.RTCPeerConnection;
    if (_OrigRTC) {{
        window.RTCPeerConnection = function(cfg) {{ return new _OrigRTC(cfg); }};
        window.RTCPeerConnection.prototype = _OrigRTC.prototype;
    }};

    Object.defineProperty(navigator, 'plugins', {{
        get: () => {plugins_json}
    }});

    Object.defineProperty(navigator, 'languages', {{
        get: () => {languages_json}
    }});

    Object.defineProperty(navigator, 'connection', {{
        get: () => ({{ effectiveType: '{connection_type}', downlink: {downlink}, rtt: {rtt}, downlinkMax: 1000 }})
    }});

    if (navigator.getBattery) {{
        navigator.getBattery = () => Promise.resolve({battery_json});
    }};

    Object.defineProperty(navigator, 'usb', {{
        get: () => {usb_json}
    }});

    if (navigator.mediaDevices) {{
        navigator.mediaDevices.enumerateDevices = () => Promise.resolve({media_devices_json});
    }};

    delete window.cdc_;
    delete window.$cdc_;
    delete window.__webdriver_evaluate;
    delete window.__selenium_evaluate;
    Object.prototype.cdc_ && delete Object.prototype.cdc_;
    Object.prototype.$cdc_ && delete Object.prototype.$cdc_;

    window.MutationObserver = class extends MutationObserver {{
        constructor(cb) {{ super(cb); }}
        disconnect() {{}}
        observe() {{}}
    }};

    if (performance) {{
        const _origNow = performance.now.bind(performance);
        performance.now = () => _origNow() + (Math.random() - 0.5) * 0.1;
    }};

}})();
"""

    _cached_scripts[cache_key] = script
    return script


def _generate_session_seed(session_id: str | None = None) -> int:
    """Generate a deterministic seed from session ID or current time."""
    if session_id:
        hash_input = f"{session_id}".encode()
    else:
        hash_input = f"{time.time()}{id(time)}".encode()
    return int(hashlib.md5(hash_input).hexdigest()[:8], 16)


def get_fingerprint_script(
    session_id: str | None = None,
    gpu_vendor: str | None = None,
    gpu_renderer: str | None = None,
    screen_width: int = 1920,
    screen_height: int = 1080,
    device_pixel_ratio: float = 2.0,
    platform_string: str = "MacIntel",
    cores: int = 8,
    memory: int = 8,
    languages: list | None = None,
    connection_type: str = "4g",
    downlink: int = 10,
    rtt: int = 50,
    plugins: list | None = None,
    usb: dict | None = None,
    media_devices: list | None = None,
    battery: dict | None = None,
    webdriver_value: str | None = None,
    permissions_default: str = "default",
    orientation_angle: int = 0,
    orientation_type: str = "landscape-primary",
) -> str:
    return generate_fingerprint_script(
        session_id=session_id,
        gpu_vendor=gpu_vendor,
        gpu_renderer=gpu_renderer,
        screen_width=screen_width,
        screen_height=screen_height,
        device_pixel_ratio=device_pixel_ratio,
        platform_string=platform_string,
        cores=cores,
        memory=memory,
        languages=languages,
        connection_type=connection_type,
        downlink=downlink,
        rtt=rtt,
        plugins=plugins,
        usb=usb,
        media_devices=media_devices,
        battery=battery,
        webdriver_value=webdriver_value,
        permissions_default=permissions_default,
        orientation_angle=orientation_angle,
        orientation_type=orientation_type,
    )
