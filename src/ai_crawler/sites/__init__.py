from importlib import import_module
from pathlib import Path

SITE_JS_CODE: dict[str, str] = {}

_configs_dir = Path(__file__).parent
for _subdir in _configs_dir.iterdir():
    if not _subdir.is_dir() or _subdir.name.startswith("_"):
        continue
    _site_name = _subdir.name

    _js_file = _subdir / "js.py"
    if _js_file.exists():
        try:
            _module = import_module(f".{_site_name}.js", package=__name__)
            if hasattr(_module, "JS_CODE"):
                SITE_JS_CODE[_site_name] = _module.JS_CODE
        except Exception:
            pass

    _adapter_file = _subdir / "adapter.py"
    if _adapter_file.exists():
        try:
            import_module(f".{_site_name}.adapter", package=__name__)
        except Exception:
            pass


def get_js_code(site: str) -> str | None:
    return SITE_JS_CODE.get(site)


def get_supported_sites() -> list[str]:
    return list(SITE_JS_CODE.keys())