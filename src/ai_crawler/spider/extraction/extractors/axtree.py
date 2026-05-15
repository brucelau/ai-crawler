import re
import structlog
from typing import Any

from ai_crawler.spider.extraction.base import ExtractionStrategy
from ai_crawler.models.product import Product
from ai_crawler.config.sites import infer_site_from_url

log = structlog.get_logger()


class AXTreeExtractor(ExtractionStrategy):
    name = "axtree"
    method = "accessibility_tree"

    def __init__(self):
        super().__init__(name=self.name, method=self.method)

    PRODUCT_CONTAINER_ROLES = {"listitem", "article", "group", "row"}
    TEXT_ROLES = {
        "text",
        "statictext",
        "heading",
        "link",
        "button",
        "labeltext",
        "generic",
        "paragraph",
    }
    SITE_HINTS = {
        "amazon": {
            "min_title_len": 6,
            "ignore_title_terms": {"sponsored", "options", "more buying choices"},
        },
        "walmart": {
            "min_title_len": 6,
            "ignore_title_terms": {"options", "pickup", "shipping"},
        },
        "target": {
            "min_title_len": 6,
            "ignore_title_terms": {"same day delivery", "when purchased online"},
        },
        "default": {
            "min_title_len": 4,
            "ignore_title_terms": {"sponsored", "featured", "shop now"},
        },
    }

    def extract(self, page: Any, html: str, url: str) -> list[Product]:
        payload = self._capture_payload(page)
        if not payload:
            return []

        products = self._products_from_payload(payload, url)
        return products

    def build_semantic_confirmation(
        self, page: Any, url: str, page_pattern: str = "unknown"
    ) -> dict | None:
        payload = self._capture_payload(page)
        if not payload:
            return None

        products = self._products_from_payload(payload, url)
        texts = self._payload_texts(payload)
        lowered = [text.lower() for text in texts]

        has_price = any(self._looks_like_price(text) for text in texts)
        has_rating = any("star" in text or "rating" in text for text in lowered)
        review_signal_count = sum(
            1
            for signal in [
                "customer reviews",
                "write a review",
                "verified purchase",
                "out of 5 stars",
                "global ratings",
                "review this product",
            ]
            if any(signal in text for text in lowered)
        )

        if review_signal_count >= 2:
            return {
                "kind": "review",
                "confidence": 0.85,
                "entity_count": review_signal_count,
                "has_price": has_price,
                "has_rating": has_rating,
            }

        if len(products) >= 2:
            return {
                "kind": "search",
                "confidence": 0.85,
                "entity_count": len(products),
                "has_price": any(bool(p.price) for p in products),
                "has_rating": any(bool(p.rating) for p in products),
            }

        if len(products) == 1:
            product = products[0]
            confidence = 0.75 if (product.price or product.rating) else 0.6
            kind = "detail" if page_pattern != "search" else "search"
            return {
                "kind": kind,
                "confidence": confidence,
                "entity_count": 1,
                "has_price": bool(product.price),
                "has_rating": bool(product.rating),
            }

        if page_pattern == "review" and review_signal_count >= 1:
            return {
                "kind": "review",
                "confidence": 0.6,
                "entity_count": review_signal_count,
                "has_price": has_price,
                "has_rating": has_rating,
            }
        return None

    def build_selector_semantic_sample(
        self,
        page: Any,
        url: str,
        page_pattern: str = "unknown",
        max_products: int = 4,
        max_chars: int = 2000,
    ) -> str:
        payload = self._capture_payload(page)
        if not payload:
            return ""

        source = self._infer_source(url)
        products = self._products_from_payload(payload, url)
        semantic = self.build_semantic_confirmation(page, url, page_pattern) or {}
        texts = self._payload_texts(payload)[:12]

        lines = [
            f"site={source}",
            f"page_pattern={page_pattern}",
            f"semantic_kind={semantic.get('kind', 'unknown')}",
            f"semantic_confidence={semantic.get('confidence', 0)}",
            f"entity_count={semantic.get('entity_count', 0)}",
        ]

        if products:
            lines.append("visible_product_candidates:")
            for product in products[:max_products]:
                parts = [product.title]
                if product.price:
                    parts.append(f"price={product.price}")
                if product.rating:
                    parts.append(f"rating={product.rating}")
                if product.review_count:
                    parts.append(f"reviews={product.review_count}")
                lines.append(f"- {' | '.join(parts)}")
        elif texts:
            lines.append("visible_semantic_text:")
            for text in texts[:8]:
                lines.append(f"- {text}")

        sample = "\n".join(lines)
        return sample[:max_chars]

    def _capture_payload(self, page: Any) -> dict | None:
        if page is None:
            return None

        snapshot = self._capture_accessibility_snapshot(page)
        if snapshot:
            return {"root": snapshot, "nodes": self._flatten_snapshot(snapshot)}

        cdp_tree = self._capture_cdp_tree(page)
        if cdp_tree:
            return cdp_tree
        return None

    def _capture_accessibility_snapshot(self, page: Any):
        try:
            accessibility = getattr(page, "accessibility", None)
            if accessibility and hasattr(accessibility, "snapshot"):
                return accessibility.snapshot(interesting_only=False)
        except Exception:
            log.debug("accessibility_snapshot_failed")
            return None
        return None

    def _capture_cdp_tree(self, page: Any) -> dict | None:
        try:
            context = getattr(page, "context", None)
            if context and hasattr(context, "new_cdp_session"):
                session = context.new_cdp_session(page)
                result = session.send("Accessibility.getFullAXTree")
                try:
                    if hasattr(session, "detach"):
                        session.detach()
                except Exception:
                    log.debug("cdp_session_detach_failed")
                nodes = [self._normalize_cdp_node(node) for node in result.get("nodes", [])]
                return {"root": None, "nodes": [node for node in nodes if node]}
        except Exception:
            log.debug("cdp_tree_capture_failed")
            return None
        return None

    def _flatten_snapshot(self, node: dict, path: str = "root") -> list[dict]:
        if not isinstance(node, dict):
            return []

        normalized = {
            "role": str(node.get("role", "")).lower(),
            "name": str(node.get("name", "") or ""),
            "value": str(node.get("value", "") or ""),
            "description": str(node.get("description", "") or ""),
            "path": path,
            "children": [],
        }
        children = []
        for index, child in enumerate(node.get("children", []) or []):
            child_path = f"{path}.{index}"
            children.extend(self._flatten_snapshot(child, child_path))
        normalized["children"] = children
        return [normalized, *children]

    def _normalize_cdp_node(self, node: dict) -> dict | None:
        role = self._cdp_value(node.get("role"))
        name = self._cdp_value(node.get("name"))
        value = self._cdp_value(node.get("value"))
        description = self._cdp_value(node.get("description"))
        if not any([role, name, value, description]):
            return None
        return {
            "role": str(role).lower(),
            "name": str(name or ""),
            "value": str(value or ""),
            "description": str(description or ""),
            "path": str(node.get("backendDOMNodeId", node.get("nodeId", ""))),
            "children": [],
        }

    @staticmethod
    def _cdp_value(raw: Any) -> str:
        if isinstance(raw, dict):
            return str(raw.get("value", "") or "")
        return str(raw or "")

    def _products_from_payload(self, payload: dict, url: str) -> list[Product]:
        nodes = payload.get("nodes", []) or []
        candidates = [node for node in nodes if node.get("role") in self.PRODUCT_CONTAINER_ROLES]
        if not candidates:
            candidates = [{"role": "document", "children": nodes, "path": "root"}]

        products: list[Product] = []
        seen_titles: set[str] = set()
        source = self._infer_source(url)
        for candidate in candidates:
            product = self._product_from_candidate(candidate, url, source)
            if not product or not product.title:
                continue
            if product.title in seen_titles:
                continue
            seen_titles.add(product.title)
            products.append(product)

        return products

    def _product_from_candidate(self, candidate: dict, url: str, source: str) -> Product | None:
        texts = self._collect_candidate_texts(candidate)
        if len(texts) < 2:
            return None

        title = self._pick_title(source, texts)
        price = self._pick_price(texts)
        rating = self._pick_rating(texts)
        review_count = self._pick_review_count(texts)

        if not title:
            return None
        if not price and not rating and len(title) < 5:
            return None

        return Product(
            source=source,
            url=url,
            title=title,
            price=price,
            rating=rating,
            review_count=review_count,
        )

    def _payload_texts(self, payload: dict) -> list[str]:
        texts: list[str] = []
        for node in payload.get("nodes", []) or []:
            for raw in (node.get("name"), node.get("value"), node.get("description")):
                text = self._normalize_text(raw)
                if text:
                    texts.append(text)
        return texts

    def _collect_candidate_texts(self, candidate: dict) -> list[str]:
        texts: list[str] = []
        seen: set[str] = set()
        for node in [candidate, *(candidate.get("children") or [])]:
            role = str(node.get("role", "")).lower()
            if role and role not in self.TEXT_ROLES and role not in self.PRODUCT_CONTAINER_ROLES:
                continue
            for raw in (node.get("name"), node.get("value"), node.get("description")):
                text = self._normalize_text(raw)
                if text and text not in seen:
                    seen.add(text)
                    texts.append(text)
        return texts

    @staticmethod
    def _normalize_text(value: str | None) -> str:
        if not value:
            return ""
        text = re.sub(r"\s+", " ", str(value)).strip()
        return text[:300]

    def _pick_title(self, source: str, texts: list[str]) -> str:
        hints = self.SITE_HINTS.get(source, self.SITE_HINTS["default"])
        for text in texts:
            lowered = text.lower()
            if any(term in lowered for term in hints["ignore_title_terms"]):
                continue
            if self._looks_like_price(text):
                continue
            if "review" in lowered or "star" in lowered or "rating" in lowered:
                continue
            if len(text) < hints["min_title_len"]:
                continue
            return text
        return ""

    def _pick_price(self, texts: list[str]) -> str:
        for text in texts:
            if self._looks_like_price(text):
                return text
        return ""

    @staticmethod
    def _looks_like_price(text: str) -> bool:
        return bool(re.search(r"(?:[$€£]|USD|EUR|GBP)\s?\d[\d,]*(?:\.\d{2})?", text, re.I))

    @staticmethod
    def _pick_rating(texts: list[str]) -> float:
        for text in texts:
            if "star" not in text.lower() and "rating" not in text.lower():
                continue
            match = re.search(r"([0-5](?:\.\d)?)\s*(?:star|rating)", text, re.I)
            if match:
                return float(match.group(1))
        return 0.0

    @staticmethod
    def _pick_review_count(texts: list[str]) -> int:
        for text in texts:
            if "review" not in text.lower() and "rating" not in text.lower():
                continue
            match = re.search(r"(\d[\d,]*)\s*reviews?", text, re.I)
            if match:
                return int(match.group(1).replace(",", ""))
        return 0

    def _infer_source(self, url: str) -> str:
        return infer_site_from_url(url)
