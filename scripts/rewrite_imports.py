"""Rewrite imports across ai_crawler to use new core/ package paths."""
import re
from pathlib import Path

SRC = Path("/Users/cyberway/ocworkspace/ai-crawler/src/ai_crawler")

# Maps of (old_module, new_module) for import rewriting.
# Import analysis goes from most-specific to least-specific.
REWRITES = [
    # spider/runtime/crawl types → core/types
    (
        r"from ai_crawler\.spider\.runtime\.crawl import (.+)",
        r"from ai_crawler.core.types import \1",
    ),
    # models/product → core/types
    (
        r"from ai_crawler\.models\.product import (.+)",
        r"from ai_crawler.core.types import \1",
    ),
    # spider/engine/errors → core/types
    (
        r"from ai_crawler\.spider\.engine\.errors import (.+)",
        r"from ai_crawler.core.types import \1",
    ),
    # spider/engine/constants → core/types
    (
        r"from ai_crawler\.spider\.engine\.constants import (.+)",
        r"from ai_crawler.core.types import \1",
    ),
    # config/sites → core/sites
    (
        r"from ai_crawler\.config\.sites import (.+)",
        r"from ai_crawler.core.sites import \1",
    ),
    # config/crawler_config → core/config
    (
        r"from ai_crawler\.config\.crawler_config import (.+)",
        r"from ai_crawler.core.config import \1",
    ),
    # config import * (the config singleton + setup_logging etc.)
    (
        r"from ai_crawler\.config import (.+)",
        r"from ai_crawler.core.config import \1",
    ),
]

# Exempt files that should NOT have their imports rewritten
# (they are source files that still form the old package structure)
EXEMPT = {
    # Old source files whose content has moved to core/ — keep as-is, delete in Phase 6
    "config/__init__.py",
    "config/settings.py",
    "config/crawler_config.py",
    "config/sites.py",
    "spider/runtime/crawl.py",
    "spider/engine/errors.py",
    "spider/engine/constants.py",
    "models/__init__.py",
    "models/product.py",
    # These reference internal types that haven't moved yet
    "api/models.py",
    "api/orchestrator.py",
    "data/__init__.py",
    "data/bs/__init__.py",
}


def rewrite_file(filepath: Path) -> bool:
    content = filepath.read_text()
    new_content = content
    for pattern, replacement in REWRITES:
        new_content = re.sub(pattern, replacement, new_content)
    if new_content != content:
        filepath.write_text(new_content)
        return True
    return False


def main():
    changed = []
    for pyfile in sorted(SRC.rglob("*.py")):
        rel = pyfile.relative_to(SRC).as_posix()
        if rel in EXEMPT:
            continue
        # Skip the newly created core/ files
        if rel.startswith("core/"):
            continue
        if rewrite_file(pyfile):
            changed.append(rel)
    for f in changed:
        print(f"  ✅ {f}")
    print(f"\n{len(changed)} files updated.")


if __name__ == "__main__":
    main()
