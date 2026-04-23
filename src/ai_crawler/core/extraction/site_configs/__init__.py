from importlib import import_module
from pathlib import Path

SITE_JS_CODE: dict[str, str] = {}

_configs_dir = Path(__file__).parent
for _file in _configs_dir.glob("*.py"):
    if _file.name.startswith("_"):
        continue
    _site_name = _file.stem
    try:
        _module = import_module(f".{_site_name}", package=__name__)
        if hasattr(_module, "JS_CODE"):
            SITE_JS_CODE[_site_name] = _module.JS_CODE
    except Exception:
        pass


def get_js_code(site: str) -> str | None:
    return SITE_JS_CODE.get(site)


def get_supported_sites() -> list[str]:
    return list(SITE_JS_CODE.keys())
