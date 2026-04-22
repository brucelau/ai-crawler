"""页面特征分析器"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import structlog

log = structlog.get_logger()

SPA_PATTERNS = [
    r'window\.__NEXT_DATA__',
    r'window\.__NUXT__',
    r'window\.__PRELOADED_STATE__',
    r'window\.initialState',
    r'window\.\w+_STORE',
    r'vue-meta',
    r'react-dom',
    r'ng-app',
    r'ng-version',
]

JSON_LD_PATTERN = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>',
    re.IGNORECASE
)

API_KEYWORDS = [
    'product', 'search', 'item', 'goods', 'listing',
    'catalog', 'inventory', 'sku', 'price', 'review'
]


@dataclass
class PageFeatures:
    has_json_ld: bool = False
    has_spa_signature: bool = False
    has_api_signatures: bool = False
    has_amp: bool = False
    dom_depth: int = 0
    script_ratio: float = 0.0
    has_structured_data: bool = False
    is_infinite_scroll: bool = False

    def to_dict(self) -> dict:
        return {
            "has_json_ld": self.has_json_ld,
            "has_spa_signature": self.has_spa_signature,
            "has_api_signatures": self.has_api_signatures,
            "has_amp": self.has_amp,
            "dom_depth": self.dom_depth,
            "script_ratio": self.script_ratio,
            "has_structured_data": self.has_structured_data,
            "is_infinite_scroll": self.is_infinite_scroll,
        }


class PageAnalyzer:

    def analyze(self, html: str, page: Any | None = None) -> PageFeatures:
        if not html:
            return PageFeatures()

        return PageFeatures(
            has_json_ld=self._detect_json_ld(html),
            has_spa_signature=self._detect_spa(html),
            has_api_signatures=self._detect_api_signatures(html),
            has_amp=self._detect_amp(html),
            dom_depth=self._estimate_dom_depth(page) if page else 0,
            script_ratio=self._calc_script_ratio(html),
            has_structured_data=self._detect_structured_data(html),
            is_infinite_scroll=self._detect_infinite_scroll(html),
        )

    def _detect_json_ld(self, html: str) -> bool:
        return bool(JSON_LD_PATTERN.search(html))

    def _detect_spa(self, html: str) -> bool:
        return any(re.search(p, html, re.IGNORECASE) for p in SPA_PATTERNS)

    def _detect_api_signatures(self, html: str) -> bool:
        html_lower = html.lower()
        keyword_count = sum(1 for k in API_KEYWORDS if k in html_lower)
        return keyword_count >= 3

    def _detect_amp(self, html: str) -> bool:
        return 'amp' in html.lower() and ('⚡' in html or 'ampproject.org' in html)

    def _detect_structured_data(self, html: str) -> bool:
        has_microdata = 'itemscope' in html or 'itemtype' in html
        has_rdfa = 'typeof' in html and 'vocab' in html
        return has_microdata or has_rdfa or self._detect_json_ld(html)

    def _detect_infinite_scroll(self, html: str) -> bool:
        indicators = [
            'infinite-scroll', 'load-more', 'loadmore',
            'pagination-infinite', 'autoload', 'intersection-observer',
        ]
        html_lower = html.lower()
        return any(ind in html_lower for ind in indicators)

    def _estimate_dom_depth(self, page: Any | None) -> int:
        if not page:
            return 0
        try:
            script = """
            () => {
                const body = document.body;
                if (!body) return 0;
                let maxDepth = 0;
                function walk(node, depth) {
                    if (depth > maxDepth) maxDepth = depth;
                    for (const child of node.children || []) {
                        walk(child, depth + 1);
                    }
                }
                walk(body, 0);
                return maxDepth;
            }
            """
            depth = page.evaluate(script)
            return int(depth) if depth else 0
        except Exception:
            return 0

    def _calc_script_ratio(self, html: str) -> float:
        if not html:
            return 0.0
        script_len = sum(len(m.group(0)) for m in re.finditer(r'<script[^>]*>', html, re.IGNORECASE))
        return script_len / len(html) if html else 0.0

    def get_recommendations(self, features: PageFeatures) -> dict[str, str]:
        recommendations = {}
        if features.has_json_ld:
            recommendations["json_ld"] = "JSON-LD"
        if features.has_spa_signature:
            recommendations["js_eval"] = "SPA"
            recommendations["axtree"] = "SPA"
        if features.is_infinite_scroll:
            recommendations["js_eval"] = "InfiniteScroll"
        if not recommendations:
            recommendations["bs_css"] = "Default"
        return recommendations
