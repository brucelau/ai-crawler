"""Phase 4 import rewrites: antidetect/, extraction/, llm/"""
import re
from pathlib import Path

SRC = Path("/Users/cyberway/ocworkspace/ai-crawler/src/ai_crawler")

REWRITES = [
    # antidetect internal cross-refs
    (r"from ai_crawler\.spider\.engine\.anti_bot\.handler import", r"from ai_crawler.antidetect.handler import"),
    (r"from ai_crawler\.spider\.engine\.anti_bot\.fingerprinter import", r"from ai_crawler.antidetect.fingerprinter import"),
    (r"from ai_crawler\.spider\.engine\.anti_bot\.fetch_engineer import", r"from ai_crawler.fetch.engineer import"),
    # captcha
    (r"from ai_crawler\.spider\.engine\.captcha\.solver import", r"from ai_crawler.antidetect.captcha.solver import"),
    (r"from ai_crawler\.spider\.engine\.captcha\.detector import", r"from ai_crawler.antidetect.captcha.detector import"),
    (r"from ai_crawler\.spider\.engine\.captcha\.service import", r"from ai_crawler.antidetect.captcha.service import"),
    (r"from ai_crawler\.spider\.engine\.captcha import", r"from ai_crawler.antidetect.captcha import"),
    # proxy
    (r"from ai_crawler\.spider\.engine\.proxy\.provider import", r"from ai_crawler.antidetect.proxy.provider import"),
    (r"from ai_crawler\.spider\.engine\.proxy\.thordata import", r"from ai_crawler.antidetect.proxy.thordata import"),
    (r"from ai_crawler\.spider\.engine\.proxy\.uc_bridge import", r"from ai_crawler.antidetect.proxy.uc_bridge import"),
    (r"from ai_crawler\.spider\.engine\.proxy import", r"from ai_crawler.antidetect.proxy import"),
    # extraction
    (r"from ai_crawler\.spider\.extraction\.base import", r"from ai_crawler.extraction.base import"),
    (r"from ai_crawler\.spider\.extraction\.engine\.extraction_engine import", r"from ai_crawler.extraction.engine import"),
    (r"from ai_crawler\.spider\.extraction\.engine\.policy_engine import", r"from ai_crawler.extraction.policy import"),
    (r"from ai_crawler\.spider\.extraction\.engine\.registry import", r"from ai_crawler.extraction.registry import"),
    (r"from ai_crawler\.spider\.extraction\.engine import", r"from ai_crawler.extraction import"),
    (r"from ai_crawler\.spider\.extraction\.extractors\.json_ld import", r"from ai_crawler.extraction.extractors.json_ld import"),
    (r"from ai_crawler\.spider\.extraction\.extractors\.js_eval import", r"from ai_crawler.extraction.extractors.js_eval import"),
    (r"from ai_crawler\.spider\.extraction\.extractors\.api_intercept import", r"from ai_crawler.extraction.extractors.api_intercept import"),
    (r"from ai_crawler\.spider\.extraction\.extractors\.bs_css import", r"from ai_crawler.extraction.extractors.bs_css import"),
    (r"from ai_crawler\.spider\.extraction\.extractors\.axtree import", r"from ai_crawler.extraction.extractors.axtree import"),
    (r"from ai_crawler\.spider\.extraction\.extractors import", r"from ai_crawler.extraction.extractors import"),
    (r"from ai_crawler\.spider\.extraction\.analysis\.page_analyzer import", r"from ai_crawler.extraction.analysis.page_analyzer import"),
    (r"from ai_crawler\.spider\.extraction\.analysis\.validators import", r"from ai_crawler.extraction.analysis.validators import"),
    (r"from ai_crawler\.spider\.extraction\.analysis import", r"from ai_crawler.extraction.analysis import"),
    (r"from ai_crawler\.spider\.extraction\.generic\.detail_page import", r"from ai_crawler.extraction.generic.detail_page import"),
    (r"from ai_crawler\.spider\.extraction\.generic\.extraction import", r"from ai_crawler.extraction.generic.extraction import"),
    (r"from ai_crawler\.spider\.extraction\.generic import", r"from ai_crawler.extraction.generic import"),
    (r"from ai_crawler\.spider\.extraction\.templates\.template_based import", r"from ai_crawler.extraction.templates.template_based import"),
    (r"from ai_crawler\.spider\.extraction\.templates\.template_store import", r"from ai_crawler.extraction.templates.template_store import"),
    (r"from ai_crawler\.spider\.extraction\.templates import", r"from ai_crawler.extraction.templates import"),
    (r"from ai_crawler\.spider\.extraction import", r"from ai_crawler.extraction import"),
    # llm
    (r"from ai_crawler\.spider\.llm\.dspy_model import", r"from ai_crawler.llm.dspy_model import"),
    (r"from ai_crawler\.spider\.llm\.dspy_scheduler import", r"from ai_crawler.llm.dspy_scheduler import"),
    (r"from ai_crawler\.spider\.llm\.llm_block_detector import", r"from ai_crawler.llm.block_detector import"),
    (r"from ai_crawler\.spider\.llm\.llm_extractor import", r"from ai_crawler.llm.extractor import"),
    (r"from ai_crawler\.spider\.llm\.llm_url_discovery import", r"from ai_crawler.llm.url_discovery import"),
    (r"from ai_crawler\.spider\.llm import", r"from ai_crawler.llm import"),
]

EXEMPT = {
    # Old files (will be deleted)
    "spider/engine/anti_bot/handler.py",
    "spider/engine/anti_bot/fingerprinter.py",
    "spider/engine/anti_bot/fetch_engineer.py",
    "spider/engine/captcha/detector.py",
    "spider/engine/captcha/solver.py",
    "spider/engine/captcha/service.py",
    "spider/engine/proxy/provider.py",
    "spider/engine/proxy/thordata.py",
    "spider/engine/proxy/uc_bridge.py",
    "spider/extraction/base.py",
    "spider/extraction/engine/extraction_engine.py",
    "spider/extraction/engine/policy_engine.py",
    "spider/extraction/engine/registry.py",
    "spider/extraction/extractors/json_ld.py",
    "spider/extraction/extractors/js_eval.py",
    "spider/extraction/extractors/api_intercept.py",
    "spider/extraction/extractors/bs_css.py",
    "spider/extraction/extractors/axtree.py",
    "spider/extraction/analysis/page_analyzer.py",
    "spider/extraction/analysis/validators.py",
    "spider/extraction/generic/detail_page.py",
    "spider/extraction/generic/extraction.py",
    "spider/extraction/templates/template_based.py",
    "spider/extraction/templates/template_store.py",
    "spider/llm/dspy_model.py",
    "spider/llm/dspy_scheduler.py",
    "spider/llm/llm_block_detector.py",
    "spider/llm/llm_extractor.py",
    "spider/llm/llm_url_discovery.py",
    # __init__.py files from old packages
    "spider/engine/anti_bot/__init__.py",
    "spider/engine/captcha/__init__.py",
    "spider/engine/proxy/__init__.py",
    "spider/extraction/__init__.py",
    "spider/extraction/engine/__init__.py",
    "spider/extraction/extractors/__init__.py",
    "spider/extraction/analysis/__init__.py",
    "spider/extraction/generic/__init__.py",
    "spider/extraction/templates/__init__.py",
    "spider/llm/__init__.py",
    "spider/engine/__init__.py",
    "spider/__init__.py",
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
        if rel.startswith(("core/", "fetch/", "sites/")):
            continue
        if rewrite_file(pyfile):
            changed.append(rel)
    for f in changed:
        print(f"  {f}")
    print(f"\n{len(changed)} files updated.")


if __name__ == "__main__":
    main()
