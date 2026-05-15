from importlib import import_module
from pathlib import Path

BS_EXTRACTORS: dict[str, callable] = {}

_bs_dir = Path(__file__).parent
_parent_dir = _bs_dir.parent
for _subdir in _parent_dir.iterdir():
    if not _subdir.is_dir() or _subdir.name.startswith("_"):
        continue
    _bs_file = _subdir / "bs.py"
    if not _bs_file.exists():
        continue
    _site_name = _subdir.name
    try:
        _module = import_module(f".{_site_name}.bs", package="ai_crawler.data")
        if hasattr(_module, "extract"):
            BS_EXTRACTORS[_site_name] = _module.extract
    except Exception:
        pass


def get_bs_extractor(site: str) -> callable | None:
    return BS_EXTRACTORS.get(site)


def get_supported_bs_sites() -> list[str]:
    return list(BS_EXTRACTORS.keys())