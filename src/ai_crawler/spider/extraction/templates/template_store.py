import json
import time
from pathlib import Path
from typing import Optional


class TemplateStore:
    def __init__(self, template_dir: str | None = None):
        if template_dir:
            self.template_dir = Path(template_dir)
        else:
            import ai_crawler.data
            self.template_dir = Path(ai_crawler.data.__file__).parent
        self.template_dir.mkdir(parents=True, exist_ok=True)

    def _get_template_dir(self, site: str) -> Path:
        return self.template_dir / site

    def _get_template_path(self, site: str, page_type: str = "search") -> Path:
        return self._get_template_dir(site) / f"{page_type}.json"

    def load(self, site: str, page_type: str = "search") -> Optional[dict]:
        path = self._get_template_path(site, page_type)
        if not path.exists():
            return None
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return None

    def save(self, site: str, page_type: str, template: dict) -> None:
        site_dir = self._get_template_dir(site)
        site_dir.mkdir(parents=True, exist_ok=True)
        path = self._get_template_path(site, page_type)
        template["site"] = site
        template["page_type"] = page_type
        template["_loaded_at"] = time.time()
        with open(path, "w") as f:
            json.dump(template, f, indent=2)

    def exists(self, site: str, page_type: str = "search") -> bool:
        return self._get_template_path(site, page_type).exists()

    def delete(self, site: str, page_type: str = "search") -> None:
        path = self._get_template_path(site, page_type)
        if path.exists():
            path.unlink()

    def list_sites(self) -> list[str]:
        return [d.name for d in self.template_dir.iterdir() if d.is_dir()]


template_store = TemplateStore()
