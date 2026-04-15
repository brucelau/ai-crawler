from dataclasses import dataclass
import re
from typing import Callable

from ai_crawler.models.product import Product


@dataclass
class ExtractionResult:
    products: list[Product]
    strategy: str
    method: str


ExtractFn = Callable[[any, str, str], list[Product]]


class ExtractionStrategy:
    name: str
    method: str

    def extract(self, page: any, html: str, url: str) -> list[Product]:
        raise NotImplementedError


class JSONLDExtraction(ExtractionStrategy):
    name = "json_ld"
    method = "beautifulsoup"

    def extract(self, page: any, html: str, url: str) -> list[Product]:
        import json
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        products = []
        seen = set()

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get("@type") == "Product":
                        name = item.get("name", "")
                        if not name or name in seen:
                            continue
                        seen.add(name)

                        offers = item.get("offers", {}) or {}
                        if isinstance(offers, list):
                            offers = offers[0] if offers else {}

                        price = ""
                        if offers:
                            price = str(offers.get("price", ""))
                            price_currency = offers.get("priceCurrency", "")
                            if price and price_currency:
                                price = f"{price_currency} {price}"

                        brand = ""
                        brand_data = item.get("brand")
                        if isinstance(brand_data, str):
                            brand = brand_data
                        elif isinstance(brand_data, dict):
                            brand = brand_data.get("name", "")

                        image = ""
                        img = item.get("image")
                        if isinstance(img, str):
                            image = img
                        elif isinstance(img, list) and img:
                            image = img[0]

                        products.append(
                            Product(
                                source=self._infer_source(url),
                                url=url,
                                title=name,
                                price=price,
                                brand=brand,
                                images=[image] if image else [],
                            )
                        )
            except (json.JSONDecodeError, TypeError, KeyError):
                continue

        return products

    def _infer_source(self, url: str) -> str:
        if "amazon." in url:
            return "amazon"
        if "walmart." in url:
            return "walmart"
        if "target." in url:
            return "target"
        if "ebay." in url:
            return "ebay"
        if "wowsports." in url:
            return "wowsports"
        if "costway." in url:
            return "costway"
        if "wayfair." in url:
            return "wayfair"
        if "homedepot." in url:
            return "homedepot"
        if "lowes." in url:
            return "lowes"
        if "bestbuy." in url:
            return "bestbuy"
        if "costco." in url:
            return "costco"
        if "temu." in url:
            return "temu"
        if "etsy." in url:
            return "etsy"
        if "menards." in url:
            return "menards"
        if "kohls." in url:
            return "kohls"
        if "qvc." in url:
            return "qvc"
        if "michaels." in url:
            return "michaels"
        if "samsclub." in url:
            return "samsclub"
        if "bunnings." in url:
            return "bunnings"
        if "mercadolibre." in url:
            return "mercadolibre"
        if "acehardware." in url:
            return "acehardware"
        if "intexcorp." in url:
            return "intexcorp"
        if "meijer." in url:
            return "meijer"
        if "fivebelow." in url:
            return "fivebelow"
        if "dollargeneral." in url:
            return "dollargeneral"
        if "action." in url:
            return "action"
        if "academy." in url:
            return "academy"
        if "coppel." in url:
            return "coppel"
        if "aosom." in url:
            return "aosom"
        if "familydollar." in url:
            return "familydollar"
        return "unknown"


class JSEvaluateExtraction(ExtractionStrategy):
    name = "js_eval"
    method = "page_evaluate"

    def extract(self, page: any, html: str, url: str) -> list[Product]:
        if page is None:
            return []

        source = self._infer_source(url)

        js_code = self._get_js_code(source)
        if not js_code:
            return []

        try:
            items = page.evaluate(js_code)
            if not isinstance(items, list):
                return []
            products: list[Product] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title", "") or "").strip()
                if not title:
                    continue
                products.append(
                    Product(
                        source=source,
                        url=str(item.get("url", url) or url),
                        title=title,
                        price=str(item.get("price", "") or "").strip(),
                        rating=float(item.get("rating", 0) or 0),
                        review_count=int(item.get("review_count", 0) or 0),
                        images=[item.get("image")] if item.get("image") else [],
                        asin=str(item.get("asin", "") or "").strip(),
                    )
                )
            return products
        except Exception:
            return []

    def _infer_source(self, url: str) -> str:
        if "amazon." in url:
            return "amazon"
        if "walmart." in url:
            return "walmart"
        if "target." in url:
            return "target"
        if "ebay." in url:
            return "ebay"
        if "wowsports." in url:
            return "wowsports"
        if "costway." in url:
            return "costway"
        if "homedepot." in url:
            return "homedepot"
        if "lowes." in url:
            return "lowes"
        if "bestbuy." in url:
            return "bestbuy"
        if "costco." in url:
            return "costco"
        if "temu." in url:
            return "temu"
        if "etsy." in url:
            return "etsy"
        if "menards." in url:
            return "menards"
        if "kohls." in url:
            return "kohls"
        if "qvc." in url:
            return "qvc"
        if "michaels." in url:
            return "michaels"
        if "samsclub." in url:
            return "samsclub"
        if "bunnings." in url:
            return "bunnings"
        if "mercadolibre." in url:
            return "mercadolibre"
        if "acehardware." in url:
            return "acehardware"
        if "intexcorp." in url:
            return "intexcorp"
        if "meijer." in url:
            return "meijer"
        if "fivebelow." in url:
            return "fivebelow"
        if "dollargeneral." in url:
            return "dollargeneral"
        if "action." in url:
            return "action"
        if "academy." in url:
            return "academy"
        if "coppel." in url:
            return "coppel"
        if "aosom." in url:
            return "aosom"
        if "familydollar." in url:
            return "familydollar"
        return "unknown"

    def _get_js_code(self, source: str) -> str:
        if source == "ebay":
            return """
            (() => {
                const items = document.querySelectorAll('[data-listingid]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/itm/"]');
                    const titleEl = el.querySelector('.s-card__title') || el.querySelector('h3') || el.querySelector('[class*="title"]');
                    const priceEl = el.querySelector('.s-card__price') || el.querySelector('[class*="price"]');
                    const imgEl = el.querySelector('img');
                    const title = titleEl ? titleEl.textContent.trim() : '';
                    if (!title || title === 'Shop on eBay') return null;
                    return {
                        title,
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? link.href.split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(Boolean).filter(p => p.title && p.url);
            })()
            """
        if source == "target":
            return """
            (() => {
                const items = document.querySelectorAll('a[href*="/A-"], a[href*="/p/"]');
                const seen = new Set();
                const results = [];
                items.forEach(a => {
                    const href = a.getAttribute('href', '').split('#')[0].split('?')[0];
                    const title = a.getAttribute('aria-label', '') ||
                        (a.textContent || '').trim() ||
                        Array.from(a.querySelectorAll('span,div,h2,h3')).find(el =>
                            el.textContent.trim().length > 10
                        )?.textContent?.trim() || '';
                    if (!href || !title || title.length <= 5 || seen.has(href)) return;
                    seen.add(href);
                    const parent = a.closest('li, div, section');
                    const priceText = parent ? parent.textContent : '';
                    const price = (priceText.match(/\\$([\\d,]+\\.?\\d*)/) || [])[1] || '';
                    const img = a.querySelector('img');
                    results.push({
                        title: title.slice(0, 200),
                        url: 'https://www.target.com' + href,
                        price: price.replace(/,/g, ''),
                        image: img ? (img.src || img.dataset.src || '') : ''
                    });
                });
                return results.filter(p => p.title.length > 5);
            })()
            """
        if source == "amazon":
            return """
            (() => {
                const items = document.querySelectorAll('[data-asin]');
                return Array.from(items).map(el => {
                    const asin = el.getAttribute('data-asin');
                    const titleEl = el.querySelector('span.a-text-normal') || el.querySelector('h2 a span');
                    const priceEl = el.querySelector('.a-price .a-offscreen');
                    const ratingEl = el.querySelector('.a-icon-star-small');
                    const imgEl = el.querySelector('img.s-image');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        asin: asin || '',
                        url: asin ? 'https://www.amazon.com/dp/' + asin : '',
                        image: imgEl ? imgEl.src : ''
                    };
                }).filter(p => p.title && p.asin);
            })()
            """
        if source == "walmart":
            return """
            (() => {
                const items = document.querySelectorAll('[data-item-id]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/ip/"]');
                    const titleEl = el.querySelector('[data-automation="product-title"]') || el.querySelector('span');
                    const priceEl = el.querySelector('[itemprop="price"]');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? link.href.split('?')[0] : '',
                        image: imgEl ? imgEl.src : ''
                    };
                }).filter(p => p.title);
            })()
            """
        if source == "lowes":
            return """
            (() => {
                const items = document.querySelectorAll('[data-product-id]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/p/"]');
                    const titleEl = el.querySelector('[data-testid="product-title"]');
                    const priceEl = el.querySelector('[data-testid="product-price"]');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? 'https://www.lowes.com' + link.getAttribute('href').split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(p => p.title);
            })()
            """
        if source == "homedepot":
            return """
            (() => {
                const items = document.querySelectorAll('[data-item-id]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/p/"]');
                    const titleEl = el.querySelector('.product-header__title') || el.querySelector('[data-testid="product-title"]');
                    const priceEl = el.querySelector('.price-format__dollars') || el.querySelector('[data-testid="product-price"]');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? 'https://www.homedepot.com' + link.getAttribute('href').split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(p => p.title);
            })()
            """
        if source == "acehardware":
            return """
            (() => {
                const items = document.querySelectorAll('[data-product-id]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/product/"]');
                    const titleEl = el.querySelector('.product-title');
                    const priceEl = el.querySelector('.product-price');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? 'https://www.acehardware.com' + link.getAttribute('href').split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(p => p.title);
            })()
            """
        if source == "wayfair":
            return """
            (() => {
                const items = document.querySelectorAll('[data-product-id]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/a/s/"]');
                    const titleEl = el.querySelector('.ProductCard-productTitle');
                    const priceEl = el.querySelector('.ProductCard-price');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? link.href.split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(p => p.title);
            })()
            """
        if source == "michaels":
            return """
            (() => {
                const items = document.querySelectorAll('[data-product-id]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/p/"]');
                    const titleEl = el.querySelector('.product-card__title');
                    const priceEl = el.querySelector('.product-card__price');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? 'https://www.michaels.com' + link.getAttribute('href').split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(p => p.title);
            })()
            """
        if source == "temu":
            return """
            (() => {
                const items = document.querySelectorAll('[data-id]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/p/"]');
                    const titleEl = el.querySelector('.goods-title');
                    const priceEl = el.querySelector('.price');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? 'https://www.temu.com' + link.getAttribute('href').split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(p => p.title);
            })()
            """
        if source == "etsy":
            return """
            (() => {
                const items = document.querySelectorAll('[data-listing-id]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/listing/"]');
                    const titleEl = el.querySelector('.wt-text-title-3');
                    const priceEl = el.querySelector('.currency-value');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? link.href.split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(p => p.title);
            })()
            """
        if source == "bestbuy":
            return """
            (() => {
                const items = document.querySelectorAll('[data-sku-id]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/site/"]');
                    const titleEl = el.querySelector('.sku-title');
                    const priceEl = el.querySelector('.priceView-customer-price');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? 'https://www.bestbuy.com' + link.getAttribute('href').split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(p => p.title);
            })()
            """
        if source == "costco":
            return """
            (() => {
                const items = document.querySelectorAll('[data-product-id]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/product/"]');
                    const titleEl = el.querySelector('.description');
                    const priceEl = el.querySelector('.price');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? 'https://www.costco.com' + link.getAttribute('href').split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(p => p.title);
            })()
            """
        if source == "qvc":
            return """
            (() => {
                const items = document.querySelectorAll('[data-product-id]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/p/"]');
                    const titleEl = el.querySelector('.product-title');
                    const priceEl = el.querySelector('.price');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? 'https://www.qvc.com' + link.getAttribute('href').split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(p => p.title);
            })()
            """
        if source == "kohls":
            return """
            (() => {
                const items = document.querySelectorAll('[data-product-id]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/p/"]');
                    const titleEl = el.querySelector('.product-title');
                    const priceEl = el.querySelector('.price');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? 'https://www.kohls.com' + link.getAttribute('href').split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(p => p.title);
            })()
            """
        if source == "mercadolibre":
            return """
            (() => {
                const items = document.querySelectorAll('[data-product-id]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/ML"]');
                    const titleEl = el.querySelector('.poly-component__title');
                    const priceEl = el.querySelector('.poly-price__current');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? link.href.split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(p => p.title);
            })()
            """
        if source == "walmartmexico":
            return """
            (() => {
                const items = document.querySelectorAll('[data-product-id]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/mx/"]');
                    const titleEl = el.querySelector('.product-title');
                    const priceEl = el.querySelector('.price');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? link.href.split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(p => p.title);
            })()
            """
        if source == "intexcorp":
            return """
            (() => {
                const items = document.querySelectorAll('[data-product-id]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/product/"]');
                    const titleEl = el.querySelector('.product-title');
                    const priceEl = el.querySelector('.price');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? link.href.split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(p => p.title);
            })()
            """
        if source == "meijer":
            return """
            (() => {
                const items = document.querySelectorAll('[data-product-id]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/p/"]');
                    const titleEl = el.querySelector('.product-title');
                    const priceEl = el.querySelector('.price');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? 'https://www.meijer.com' + link.getAttribute('href').split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(p => p.title);
            })()
            """
        if source == "fivebelow":
            return """
            (() => {
                const items = document.querySelectorAll('[data-product-id]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/p/"]');
                    const titleEl = el.querySelector('.product-title');
                    const priceEl = el.querySelector('.price');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? 'https://www.fivebelow.com' + link.getAttribute('href').split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(p => p.title);
            })()
            """
        if source == "samsclub":
            return """
            (() => {
                const items = document.querySelectorAll('[data-product-id]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/p/"]');
                    const titleEl = el.querySelector('.product-title');
                    const priceEl = el.querySelector('.price');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? 'https://www.samsclub.com' + link.getAttribute('href').split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(p => p.title);
            })()
            """
        if source == "bunnings":
            return """
            (() => {
                const items = document.querySelectorAll('[data-product-id]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/product/"]');
                    const titleEl = el.querySelector('.product-title');
                    const priceEl = el.querySelector('.price');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? 'https://www.bunnings.com.au' + link.getAttribute('href').split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(p => p.title);
            })()
            """
        if source == "dollargeneral":
            return """
            (() => {
                const items = document.querySelectorAll('[data-product-id]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/p/"]');
                    const titleEl = el.querySelector('.product-title');
                    const priceEl = el.querySelector('.price');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? 'https://www.dollargeneral.com' + link.getAttribute('href').split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(p => p.title);
            })()
            """
        if source == "action":
            return """
            (() => {
                const items = document.querySelectorAll('[data-product-id]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/product/"]');
                    const titleEl = el.querySelector('.product-title');
                    const priceEl = el.querySelector('.price');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? 'https://www.action.com' + link.getAttribute('href').split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(p => p.title);
            })()
            """
        if source == "academy":
            return """
            (() => {
                const items = document.querySelectorAll('[data-product-id]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/p/"]');
                    const titleEl = el.querySelector('.product-title');
                    const priceEl = el.querySelector('.price');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? 'https://www.academy.com' + link.getAttribute('href').split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(p => p.title);
            })()
            """
        if source == "wowsports":
            return """
            (() => {
                const items = document.querySelectorAll('main .grid__item, main .card-wrapper');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a.full-unstyled-link[href*="/products/"]');
                    const titleEl = el.querySelector('.card__heading, [class*="card__heading"]');
                    const priceEl = el.querySelector('.price');
                    const imgEl = el.querySelector('img');
                    const title = titleEl ? titleEl.textContent.trim() : '';
                    if (!title || title.length <= 5) return null;
                    return {
                        title,
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? 'https://wowsports.com' + link.getAttribute('href').split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(Boolean).filter(p => p.title && p.url);
            })()
            """
        if source == "coppel":
            return """
            (() => {
                const items = document.querySelectorAll('[data-product-id]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/product/"]');
                    const titleEl = el.querySelector('.product-title');
                    const priceEl = el.querySelector('.price');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? 'https://www.coppel.com' + link.getAttribute('href').split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(p => p.title);
            })()
            """
        if source == "aosom":
            return """
            (() => {
                const items = document.querySelectorAll('[data-product-id]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/product/"]');
                    const titleEl = el.querySelector('.product-title');
                    const priceEl = el.querySelector('.price');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? 'https://www.aosom.com' + link.getAttribute('href').split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(p => p.title);
            })()
            """
        if source == "familydollar":
            return """
            (() => {
                const items = document.querySelectorAll('[data-product-id]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/p/"]');
                    const titleEl = el.querySelector('.product-title');
                    const priceEl = el.querySelector('.price');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? 'https://www.familydollar.com' + link.getAttribute('href').split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(p => p.title);
            })()
            """
        if source == "costway":
            return """
            (() => {
                const items = document.querySelectorAll('.product-item');
                return Array.from(items).map(el => {
                    const link = el.querySelector('.product-images a[href$=".html"], a[href$=".html"]');
                    const titleEl = el.querySelector('img[alt], [class*="title"], [class*="name"]');
                    const priceEl = el.querySelector('.price');
                    const imgEl = el.querySelector('img');
                    const title = titleEl ? (titleEl.getAttribute && titleEl.getAttribute('alt') ? titleEl.getAttribute('alt').trim() : titleEl.textContent.trim()) : '';
                    if (!title || title.length <= 5) return null;
                    return {
                        title,
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? 'https://www.costway.com' + link.getAttribute('href').split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(Boolean).filter(p => p.title && p.url);
            })()
            """
        return ""


class APIInterceptExtraction(ExtractionStrategy):
    name = "api_intercept"
    method = "network_intercept"

    def __init__(self):
        self._captured_responses: list[dict] = []

    def extract(self, page: any, html: str, url: str) -> list[Product]:
        return []

    def intercept(self, response: any) -> None:
        try:
            content_type = response.headers.get("content-type", "")
            if "json" in content_type and self._is_product_api(response.url):
                data = response.json()
                if data:
                    self._captured_responses.append(data)
        except Exception:
            pass

    def get_and_clear(self) -> list[Product]:
        products = self._parse_responses(self._captured_responses)
        self._captured_responses = []
        return products

    def _is_product_api(self, url: str) -> bool:
        return any(k in url.lower() for k in ["product", "search", "item", "listing"])

    def _parse_responses(self, responses: list[dict]) -> list[Product]:
        products = []
        for resp in responses:
            items = self._find_products(resp)
            products.extend(items)
        return products

    def _find_products(self, data: any) -> list[Product]:
        if isinstance(data, dict):
            if "products" in data:
                return self._find_products(data["products"])
            if "items" in data:
                return self._find_products(data["items"])
            if "results" in data:
                return self._find_products(data["results"])
            if data.get("@type") == "Product":
                return [self._dict_to_product(data)]
        if isinstance(data, list):
            results = []
            for item in data:
                results.extend(self._find_products(item))
            return results
        return []

    def _dict_to_product(self, item: dict) -> Product:
        offers = item.get("offers", {}) or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = str(offers.get("price", "")) if offers else ""
        return Product(
            source="unknown",
            url=item.get("url", ""),
            title=item.get("name", ""),
            price=price,
            images=[item.get("image", "")] if item.get("image") else [],
        )


class BSExtraction(ExtractionStrategy):
    name = "bs_css"
    method = "beautifulsoup"

    def extract(self, page: any, html: str, url: str) -> list[Product]:
        from ai_crawler.spiders import EXTRACTORS

        source = self._infer_source(url)
        extractor = EXTRACTORS.get(source, {}).get("list")
        if extractor:
            try:
                return extractor(html, url)
            except Exception:
                return []

        if source == "amazon":
            return self._extract_amazon_search(html)
        if source == "ebay":
            return self._extract_ebay_search(html)
        if source == "target":
            return self._extract_target_search(html, url)
        if source == "wowsports":
            return self._extract_wowsports_search(html)
        if source == "costway":
            return self._extract_costway_search(html)
        if source == "wayfair":
            return self._extract_wayfair_search(html)
        return []

    def _infer_source(self, url: str) -> str:
        if "amazon." in url:
            return "amazon"
        if "walmart." in url:
            return "walmart"
        if "target." in url:
            return "target"
        if "ebay." in url:
            return "ebay"
        if "wowsports." in url:
            return "wowsports"
        if "costway." in url:
            return "costway"
        if "wayfair." in url:
            return "wayfair"
        if "homedepot." in url:
            return "homedepot"
        if "lowes." in url:
            return "lowes"
        if "bestbuy." in url:
            return "bestbuy"
        if "costco." in url:
            return "costco"
        if "temu." in url:
            return "temu"
        if "etsy." in url:
            return "etsy"
        if "menards." in url:
            return "menards"
        if "kohls." in url:
            return "kohls"
        if "qvc." in url:
            return "qvc"
        if "michaels." in url:
            return "michaels"
        if "samsclub." in url:
            return "samsclub"
        if "bunnings." in url:
            return "bunnings"
        if "mercadolibre." in url:
            return "mercadolibre"
        if "acehardware." in url:
            return "acehardware"
        if "intexcorp." in url:
            return "intexcorp"
        if "meijer." in url:
            return "meijer"
        if "fivebelow." in url:
            return "fivebelow"
        if "dollargeneral." in url:
            return "dollargeneral"
        if "action." in url:
            return "action"
        if "academy." in url:
            return "academy"
        if "coppel." in url:
            return "coppel"
        if "aosom." in url:
            return "aosom"
        if "familydollar." in url:
            return "familydollar"
        return ""

    def _extract_target_search(self, html: str, url: str) -> list[Product]:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin

        soup = BeautifulSoup(html, "html.parser")
        anchors = soup.select('a[href*="/A-"], a[href*="/p/"]')
        products: list[Product] = []
        seen: set[str] = set()

        for anchor in anchors:
            href = (anchor.get("href") or "").split("#")[0].split("?")[0]
            title = (anchor.get("aria-label") or anchor.get_text(" ", strip=True) or "").strip()
            if not href or len(title) <= 5 or href in seen:
                continue
            seen.add(href)

            parent = anchor.find_parent(["li", "div", "section"])
            price_text = (
                parent.get_text(" ", strip=True) if parent else anchor.get_text(" ", strip=True)
            )
            price_match = re.search(r"\$([\d,]+\.?\d*)", price_text)
            price = price_match.group(1).replace(",", "") if price_match else ""

            image = ""
            img = anchor.select_one("img")
            if img:
                image = img.get("src") or img.get("data-src") or ""

            products.append(
                Product(
                    source="target",
                    url=urljoin("https://www.target.com", href),
                    title=title[:200],
                    price=price,
                    images=[image] if image else [],
                )
            )

        return products

    def _extract_ebay_search(self, html: str) -> list[Product]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        items = [el for el in soup.select("[data-listingid]") if el.get("data-listingid")]
        products: list[Product] = []
        seen: set[str] = set()

        for item in items:
            listing_id = item.get("data-listingid", "").strip()
            if not listing_id or listing_id in seen:
                continue

            title = ""
            for sel in [".s-card__title", "h3", '[class*="title"]']:
                el = item.select_one(sel)
                if el and el.get_text(" ", strip=True):
                    title = el.get_text(" ", strip=True)
                    break
            if not title or title == "Shop on eBay":
                continue

            link = ""
            link_el = item.select_one('a[href*="/itm/"]')
            if link_el and link_el.get("href"):
                link = link_el.get("href").split("?")[0]

            price = ""
            price_el = item.select_one(".s-card__price, [class*=price]")
            if price_el and price_el.get_text(" ", strip=True):
                price = re.sub(r"[^\d.,]", "", price_el.get_text(" ", strip=True))

            image = ""
            img = item.select_one("img")
            if img:
                image = img.get("src") or img.get("data-src") or ""

            products.append(
                Product(
                    source="ebay",
                    url=link,
                    title=title[:200],
                    price=price,
                    images=[image] if image else [],
                )
            )
            seen.add(listing_id)

        return products

    def _extract_wowsports_search(self, html: str) -> list[Product]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        items = soup.select("main .grid__item, main .card-wrapper")
        products: list[Product] = []
        seen: set[str] = set()

        for item in items:
            link_el = item.select_one('a.full-unstyled-link[href*="/products/"]')
            href = (link_el.get("href") if link_el else "") or ""
            href = href.split("?")[0]
            if not href or href in seen:
                continue

            title = ""
            title_el = item.select_one('.card__heading, [class*="card__heading"]')
            if title_el and title_el.get_text(" ", strip=True):
                title = title_el.get_text(" ", strip=True)
            if not title or len(title) <= 5:
                continue

            price = ""
            price_el = item.select_one('.price, [class*="price"]')
            if price_el and price_el.get_text(" ", strip=True):
                price = re.sub(r"[^\d.,]", "", price_el.get_text(" ", strip=True))

            image = ""
            img = item.select_one("img")
            if img:
                image = img.get("src") or img.get("data-src") or ""

            products.append(
                Product(
                    source="wowsports",
                    url="https://wowsports.com" + href,
                    title=title[:200],
                    price=price,
                    images=[image] if image else [],
                )
            )
            seen.add(href)

        return products

    def _extract_costway_search(self, html: str) -> list[Product]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        items = soup.select(".product-item")
        products: list[Product] = []
        seen: set[str] = set()

        for item in items:
            link_el = item.select_one('.product-images a[href$=".html"], a[href$=".html"]')
            href = (link_el.get("href") if link_el else "") or ""
            href = href.split("?")[0]
            if not href or href in seen:
                continue

            title = ""
            img = item.select_one("img[alt]")
            if img and img.get("alt"):
                title = img.get("alt").strip()
            if not title:
                title_el = item.select_one('[class*="title"], [class*="name"]')
                if title_el and title_el.get_text(" ", strip=True):
                    title = title_el.get_text(" ", strip=True)
            if not title or len(title) <= 5:
                continue

            price = ""
            price_el = item.select_one('.price, [class*="price"]')
            if price_el and price_el.get_text(" ", strip=True):
                price = re.sub(r"[^\d.,]", "", price_el.get_text(" ", strip=True))

            image = img.get("src") if img else ""
            products.append(
                Product(
                    source="costway",
                    url="https://www.costway.com" + href,
                    title=title[:200],
                    price=price,
                    images=[image] if image else [],
                )
            )
            seen.add(href)

        return products

    def _extract_wayfair_search(self, html: str) -> list[Product]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        links = soup.select('a[href*="/furniture/pdp/"]')
        containers: list = []
        for link in links:
            container = link.find_parent(["div", "article", "section", "li"])
            if container and container not in containers:
                containers.append(container)

        products_by_url: dict[str, Product] = {}
        ignore_titles = {"30-day low price", "tax refund sale", "bundle and save"}

        for container in containers:
            candidate_links = container.select('a[href*="/furniture/pdp/"]')
            best_href = ""
            best_title = ""
            for link_el in candidate_links:
                href = (link_el.get("href") or "").split("?")[0]
                title = (
                    link_el.get("aria-label") or link_el.get_text(" ", strip=True) or ""
                ).strip()
                if not href:
                    continue
                if title and title.lower() not in ignore_titles and len(title) > len(best_title):
                    best_title = title
                    best_href = href

            href = best_href
            title = best_title
            if not href or not title or title.lower() in ignore_titles or len(title) <= 8:
                continue
            container_text = container.get_text(" ", strip=True)
            price_match = re.search(r"\$\s*([\d,]+(?:\.\d{2})?)", container_text)
            price = price_match.group(1).replace(",", "") if price_match else ""

            image = ""
            img = container.select_one("img[alt]")
            if img:
                image = img.get("src") or img.get("data-src") or ""

            product = Product(
                source="wayfair",
                url=href if href.startswith("http") else "https://www.wayfair.com" + href,
                title=title[:200],
                price=price,
                images=[image] if image else [],
            )
            existing = products_by_url.get(product.url)
            if existing is None or len(product.title) > len(existing.title):
                products_by_url[product.url] = product

        return list(products_by_url.values())

    def _extract_amazon_search(self, html: str) -> list[Product]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        items = [el for el in soup.select("[data-asin]") if el.get("data-asin")]
        products: list[Product] = []
        seen: set[str] = set()

        for item in items:
            asin = (item.get("data-asin") or "").strip()
            if not asin or asin in seen:
                continue

            title = ""
            for sel in [
                '[data-cy="title-recipe"]',
                "h2 a span",
                "h2 span",
                "a.a-link-normal.s-no-outline + h2 span",
            ]:
                el = item.select_one(sel)
                if el and el.get_text(" ", strip=True):
                    title = el.get_text(" ", strip=True)
                    break

            if not title or title.lower().startswith("results check"):
                continue

            link = ""
            for sel in ['a[href*="/dp/"]', "a.a-link-normal.s-no-outline"]:
                el = item.select_one(sel)
                href = el.get("href") if el else ""
                if href:
                    link = href.split("?")[0]
                    break
            if not link:
                link = f"https://www.amazon.com/dp/{asin}"
            elif link.startswith("/"):
                link = "https://www.amazon.com" + link

            price = ""
            price_el = item.select_one(".a-price .a-offscreen")
            if price_el and price_el.get_text(" ", strip=True):
                price = price_el.get_text(" ", strip=True).replace("$", "").replace(",", "")

            image = ""
            img = item.select_one("img.s-image")
            if img:
                image = img.get("src") or ""

            products.append(
                Product(
                    source="amazon",
                    url=link,
                    title=title[:200],
                    price=price,
                    asin=asin,
                    images=[image] if image else [],
                )
            )
            seen.add(asin)

        return products


class AXTreeExtraction(ExtractionStrategy):
    name = "axtree"
    method = "accessibility_tree"

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

    def extract(self, page: any, html: str, url: str) -> list[Product]:
        payload = self._capture_payload(page)
        if not payload:
            return []

        products = self._products_from_payload(payload, url)
        return products

    def build_semantic_confirmation(
        self, page: any, url: str, page_pattern: str = "unknown"
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
        page: any,
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

    def _capture_payload(self, page: any) -> dict | None:
        if page is None:
            return None

        snapshot = self._capture_accessibility_snapshot(page)
        if snapshot:
            return {"root": snapshot, "nodes": self._flatten_snapshot(snapshot)}

        cdp_tree = self._capture_cdp_tree(page)
        if cdp_tree:
            return cdp_tree
        return None

    def _capture_accessibility_snapshot(self, page: any):
        try:
            accessibility = getattr(page, "accessibility", None)
            if accessibility and hasattr(accessibility, "snapshot"):
                return accessibility.snapshot(interesting_only=False)
        except Exception:
            return None
        return None

    def _capture_cdp_tree(self, page: any) -> dict | None:
        try:
            context = getattr(page, "context", None)
            if context and hasattr(context, "new_cdp_session"):
                session = context.new_cdp_session(page)
                result = session.send("Accessibility.getFullAXTree")
                try:
                    if hasattr(session, "detach"):
                        session.detach()
                except Exception:
                    pass
                nodes = [self._normalize_cdp_node(node) for node in result.get("nodes", [])]
                return {"root": None, "nodes": [node for node in nodes if node]}
        except Exception:
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
    def _cdp_value(raw: any) -> str:
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
        if "amazon." in url:
            return "amazon"
        if "walmart." in url:
            return "walmart"
        if "target." in url:
            return "target"
        if "ebay." in url:
            return "ebay"
        if "wowsports." in url:
            return "wowsports"
        if "costway." in url:
            return "costway"
        if "wayfair." in url:
            return "wayfair"
        if "homedepot." in url:
            return "homedepot"
        if "lowes." in url:
            return "lowes"
        if "bestbuy." in url:
            return "bestbuy"
        if "costco." in url:
            return "costco"
        if "temu." in url:
            return "temu"
        if "etsy." in url:
            return "etsy"
        if "menards." in url:
            return "menards"
        if "kohls." in url:
            return "kohls"
        if "qvc." in url:
            return "qvc"
        if "michaels." in url:
            return "michaels"
        if "samsclub." in url:
            return "samsclub"
        if "bunnings." in url:
            return "bunnings"
        if "mercadolibre." in url:
            return "mercadolibre"
        if "acehardware." in url:
            return "acehardware"
        if "intexcorp." in url:
            return "intexcorp"
        if "meijer." in url:
            return "meijer"
        if "fivebelow." in url:
            return "fivebelow"
        if "dollargeneral." in url:
            return "dollargeneral"
        if "action." in url:
            return "action"
        if "academy." in url:
            return "academy"
        if "coppel." in url:
            return "coppel"
        if "aosom." in url:
            return "aosom"
        if "familydollar." in url:
            return "familydollar"
        return "unknown"


class GenericCSSFallback(ExtractionStrategy):
    """Fallback that uses loose CSS selectors when all template strategies fail."""

    name = "generic_css_fallback"
    method = "beautifulsoup"

    def extract(self, page: any, html: str, url: str) -> list[Product]:
        from bs4 import BeautifulSoup

        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        source = self._infer_source(url)
        products: list[Product] = []
        seen_titles: set[str] = set()

        # Try multiple generic selectors that commonly contain product cards
        generic_selectors = [
            "article",
            "li[data-item-id]",
            'li[class*="product"]',
            'div[class*="product"][class*="item"]',
            "[itemtype*='Product']",
            '[data-testid*="product"]',
            'div[class*="search"][class*="result"]',
            'li[class*="catalogue"]',
        ]

        for selector in generic_selectors:
            elements = soup.select(selector)
            for el in elements:
                title = self._extract_title(el)
                if not title or title in seen_titles or len(title) < 5:
                    continue
                seen_titles.add(title)

                price = self._extract_price(el)
                product_url = self._extract_url(el, url)
                image = self._extract_image(el)

                products.append(
                    Product(
                        source=source,
                        url=product_url,
                        title=title,
                        price=price,
                        images=[image] if image else [],
                    )
                )

            if len(products) >= 5:
                break

        return products

    def _extract_title(self, el) -> str:
        # Try various title sources
        for tag in el.find_all(["h2", "h3", "h4"]):
            text = tag.get_text(strip=True)
            if text and len(text) > 5:
                return text

        # Try aria-label
        aria = el.get("aria-label", "")
        if aria and len(aria) > 5:
            return aria

        # Try classname patterns
        for tag in el.find_all(["span", "div", "a"]):
            cls = tag.get("class", [])
            cls_str = " ".join(cls) if isinstance(cls, list) else str(cls)
            if "title" in cls_str.lower():
                text = tag.get_text(strip=True)
                if text and len(text) > 5:
                    return text

        # Fallback to any text
        text = el.get_text(strip=True)
        if text and len(text) > 10:
            return text[:200]

        return ""

    def _extract_price(self, el) -> str:
        # Try price patterns
        for tag in el.find_all(["span", "div", "p", "strong"]):
            cls = tag.get("class", [])
            cls_str = " ".join(cls) if isinstance(cls, list) else str(cls)
            if "price" in cls_str.lower():
                text = tag.get_text(strip=True)
                # Look for price pattern
                import re

                match = re.search(r"[$€£¥]?\s*[\d,]+\.?\d*", text)
                if match:
                    return match.group(0)
            # Also check data attributes
            for attr in ["data-price", "data-testid"]:
                val = tag.get(attr, "")
                if val and "price" in str(val).lower():
                    return str(val)

        return ""

    def _extract_url(self, el, base_url: str) -> str:
        import urllib.parse

        a_tag = el.find("a")
        if a_tag:
            href = a_tag.get("href", "")
            if href:
                if href.startswith("/"):
                    parsed = urllib.parse.urlparse(base_url)
                    return f"{parsed.scheme}://{parsed.netloc}{href}"
                elif href.startswith("http"):
                    return href
                elif href.startswith("?"):
                    parsed = urllib.parse.urlparse(base_url)
                    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}{href}"

        # Try own href if this element has one
        href = el.get("href", "")
        if href:
            if href.startswith("/"):
                parsed = urllib.parse.urlparse(base_url)
                return f"{parsed.scheme}://{parsed.netloc}{href}"
            elif href.startswith("http"):
                return href

        return base_url

    def _extract_image(self, el) -> str:
        img = el.find("img")
        if img:
            return (
                img.get("src", "") or img.get("data-src", "") or img.get("data-lazy-src", "") or ""
            )
        return ""

    def _infer_source(self, url: str) -> str:
        if "amazon." in url:
            return "amazon"
        if "walmart." in url:
            return "walmart"
        if "target." in url:
            return "target"
        if "ebay." in url:
            return "ebay"
        if "wowsports." in url:
            return "wowsports"
        if "costway." in url:
            return "costway"
        if "wayfair." in url:
            return "wayfair"
        if "homedepot." in url:
            return "homedepot"
        if "lowes." in url:
            return "lowes"
        if "bestbuy." in url:
            return "bestbuy"
        if "costco." in url:
            return "costco"
        if "temu." in url:
            return "temu"
        if "etsy." in url:
            return "etsy"
        if "menards." in url:
            return "menards"
        if "kohls." in url:
            return "kohls"
        if "qvc." in url:
            return "qvc"
        if "michaels." in url:
            return "michaels"
        if "samsclub." in url:
            return "samsclub"
        if "bunnings." in url:
            return "bunnings"
        if "mercadolibre." in url:
            return "mercadolibre"
        if "acehardware." in url:
            return "acehardware"
        if "intexcorp." in url:
            return "intexcorp"
        if "meijer." in url:
            return "meijer"
        if "fivebelow." in url:
            return "fivebelow"
        if "dollargeneral." in url:
            return "dollargeneral"
        if "action." in url:
            return "action"
        if "academy." in url:
            return "academy"
        if "coppel." in url:
            return "coppel"
        if "aosom." in url:
            return "aosom"
        if "familydollar." in url:
            return "familydollar"
        return "unknown"


class ExtractorChain:
    def __init__(self, strategies: list[tuple[str, int, ExtractionStrategy]]):
        self.strategies = strategies

    def extract(
        self, page: any, html: str, url: str, page_type: str = "unknown"
    ) -> ExtractionResult:
        strategies = self.strategies
        if page_type == "search":
            strategies = self._reorder_for_search(strategies)
        results: list[ExtractionResult] = []
        for name, min_needed, strategy in strategies:
            try:
                products = strategy.extract(page, html, url)
                if len(products) >= min_needed:
                    results.append(
                        ExtractionResult(
                            products=products,
                            strategy=name,
                            method=strategy.method,
                        )
                    )
            except Exception:
                continue
        if results:
            return max(results, key=lambda r: len(r.products))

        # Fallback: try generic CSS selectors when all strategies fail
        try:
            fallback = GenericCSSFallback()
            products = fallback.extract(page, html, url)
            if products:
                return ExtractionResult(
                    products=products,
                    strategy="generic_css_fallback",
                    method="beautifulsoup",
                )
        except Exception:
            pass

        return ExtractionResult(products=[], strategy="none", method="none")

    def _reorder_for_search(
        self, strategies: list[tuple[str, int, ExtractionStrategy]]
    ) -> list[tuple[str, int, ExtractionStrategy]]:
        axtree_strategy = None
        other_strategies = []
        for item in strategies:
            if item[0] == "axtree":
                axtree_strategy = item
            else:
                other_strategies.append(item)
        if axtree_strategy:
            return [axtree_strategy] + other_strategies
        return strategies


def _insert_axtree_before_bs_css(
    strategies: list[tuple[str, int, ExtractionStrategy]],
) -> list[tuple[str, int, ExtractionStrategy]]:
    if any(name == "axtree" for name, _, _ in strategies):
        return strategies

    enhanced: list[tuple[str, int, ExtractionStrategy]] = []
    inserted = False
    for name, min_needed, strategy in strategies:
        if name == "bs_css" and not inserted:
            enhanced.append(("axtree", 3, AXTreeExtraction()))
            inserted = True
        enhanced.append((name, min_needed, strategy))

    if not inserted:
        enhanced.append(("axtree", 3, AXTreeExtraction()))
    return enhanced


def build_axtree_semantic_confirmation(
    page: any, url: str, page_pattern: str = "unknown"
) -> dict | None:
    return AXTreeExtraction().build_semantic_confirmation(page, url, page_pattern)


def build_axtree_selector_sample(
    page: any,
    url: str,
    page_pattern: str = "unknown",
    max_products: int = 4,
    max_chars: int = 2000,
) -> str:
    return AXTreeExtraction().build_selector_semantic_sample(
        page,
        url,
        page_pattern=page_pattern,
        max_products=max_products,
        max_chars=max_chars,
    )


SITE_EXTRACTION_CHAINS: dict[str, ExtractorChain] = {
    "ebay": ExtractorChain(
        _insert_axtree_before_bs_css(
            [
                ("json_ld", 5, JSONLDExtraction()),
                ("js_eval", 5, JSEvaluateExtraction()),
                ("api_intercept", 10, APIInterceptExtraction()),
                ("bs_css", 3, BSExtraction()),
            ]
        )
    ),
    "target": ExtractorChain(
        _insert_axtree_before_bs_css(
            [
                ("json_ld", 3, JSONLDExtraction()),
                ("js_eval", 5, JSEvaluateExtraction()),
                ("api_intercept", 10, APIInterceptExtraction()),
                ("bs_css", 3, BSExtraction()),
            ]
        )
    ),
    "amazon": ExtractorChain(
        _insert_axtree_before_bs_css(
            [
                ("js_eval", 5, JSEvaluateExtraction()),
                ("bs_css", 3, BSExtraction()),
            ]
        )
    ),
    "walmart": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "lowes": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "homedepot": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "acehardware": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "menards": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "wayfair": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "michaels": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "temu": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "etsy": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "bestbuy": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "costco": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "qvc": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "kohls": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "mercadolibre": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "walmartmexico": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "intexcorp": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "meijer": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "fivebelow": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "samsclub": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "bunnings": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "dollargeneral": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "action": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "academy": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "wowsports": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "coppel": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "aosom": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "familydollar": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "costway": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
}

for _site_chain in SITE_EXTRACTION_CHAINS.values():
    _site_chain.strategies = _insert_axtree_before_bs_css(_site_chain.strategies)
