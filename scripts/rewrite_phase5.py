"""Phase 5 import rewrites: crawl/, storage/"""
import re
from pathlib import Path

SRC = Path("/Users/cyberway/ocworkspace/ai-crawler/src/ai_crawler")

REWRITES = [
    # crawl/ core
    (r"from ai_crawler\.spider\.runner import", r"from ai_crawler.crawl.runner import"),
    (r"from ai_crawler\.api\.orchestrator import", r"from ai_crawler.crawl.orchestrator import"),
    (r"from ai_crawler\.spider\.engine\.core\.planner import", r"from ai_crawler.crawl.planner import"),
    (r"from ai_crawler\.spider\.engine\.core\.crawl_engine import", r"from ai_crawler.crawl.engine import"),
    (r"from ai_crawler\.spider\.engine\.core\.queue import", r"from ai_crawler.crawl.queue import"),
    (r"from ai_crawler\.spider\.engine\.core\.outcomes import", r"from ai_crawler.crawl.outcomes import"),
    (r"from ai_crawler\.spider\.engine\.core\.results import", r"from ai_crawler.crawl.results import"),
    (r"from ai_crawler\.spider\.engine\.core\.trace_store import", r"from ai_crawler.storage.trace_store import"),
    # crawl/ engine
    (r"from ai_crawler\.spider\.engine\.policy_engine import", r"from ai_crawler.crawl.policy import"),
    (r"from ai_crawler\.spider\.engine\.crawl_policy_generator import", r"from ai_crawler.crawl.policy_generator import"),
    (r"from ai_crawler\.spider\.engine\.recommendation import", r"from ai_crawler.crawl.recommendation import"),
    (r"from ai_crawler\.spider\.engine\.telemetry import", r"from ai_crawler.crawl.telemetry import"),
    (r"from ai_crawler\.spider\.engine\.dynamic_thresholds import", r"from ai_crawler.crawl.thresholds import"),
    (r"from ai_crawler\.spider\.engine\.introspection import", r"from ai_crawler.crawl.introspection import"),
    (r"from ai_crawler\.spider\.engine\.constants import", r"from ai_crawler.core.types import"),
    (r"from ai_crawler\.spider\.runtime\.task_context import", r"from ai_crawler.crawl.task_context import"),
    (r"from ai_crawler\.spider\.coordinator import", r"from ai_crawler.crawl.coordinator import"),
    # storage
    (r"from ai_crawler\.api\.storage import", r"from ai_crawler.storage.backend import"),
    (r"from ai_crawler\.api\.mirage_storage import", r"from ai_crawler.storage.mirage import"),
    (r"from ai_crawler\.spider\.engine\.core\.trace_store import", r"from ai_crawler.storage.trace_store import"),
    # engine.core remaining
    (r"from ai_crawler\.spider\.engine\.core import", r"from ai_crawler.crawl import"),
    # spider/engine/* → crawl/*
    (r"from ai_crawler\.spider\.engine\.(\w+) import", r"from ai_crawler.crawl.\1 import"),
    # spider.runtime.task_context
    (r"from ai_crawler\.spider\.runtime\.task_context import", r"from ai_crawler.crawl.task_context import"),
    # spider/engine/core → crawl/
    (r"from ai_crawler\.spider\.engine\.core\.planner import", r"from ai_crawler.crawl.planner import"),
    (r"from ai_crawler\.spider\.engine\.core\.crawl_engine import", r"from ai_crawler.crawl.engine import"),
    (r"from ai_crawler\.spider\.engine\.core\.queue import", r"from ai_crawler.crawl.queue import"),
    (r"from ai_crawler\.spider\.engine\.core\.outcomes import", r"from ai_crawler.crawl.outcomes import"),
    (r"from ai_crawler\.spider\.engine\.core\.results import", r"from ai_crawler.crawl.results import"),
]

EXEMPT = {
    # Old source files (kept for backward compat, deleted in Phase 6)
    "api/storage.py",
    "api/mirage_storage.py",
    "api/orchestrator.py",
    "spider/runner.py",
    "spider/coordinator.py",
    "spider/engine/core/planner.py",
    "spider/engine/core/crawl_engine.py",
    "spider/engine/core/queue.py",
    "spider/engine/core/outcomes.py",
    "spider/engine/core/results.py",
    "spider/engine/core/trace_store.py",
    "spider/engine/policy_engine.py",
    "spider/engine/crawl_policy_generator.py",
    "spider/engine/recommendation.py",
    "spider/engine/telemetry.py",
    "spider/engine/dynamic_thresholds.py",
    "spider/engine/introspection.py",
    "spider/engine/constants.py",
    "spider/runtime/task_context.py",
    "spider/runtime/crawl.py",
    "spider/engine/errors.py",
    "spider/__init__.py",
    "spider/engine/__init__.py",
    "spider/engine/core/__init__.py",
    "api/__init__.py",
    "api/models.py",
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
        if rel.startswith(("core/", "fetch/", "sites/", "antidetect/", "extraction/", "llm/")):
            continue
        if rewrite_file(pyfile):
            changed.append(rel)
    for f in changed:
        print(f"  {f}")
    print(f"\n{len(changed)} files updated.")


if __name__ == "__main__":
    main()
