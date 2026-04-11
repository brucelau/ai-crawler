from dataclasses import dataclass
from typing import Callable

from ai_crawler.spiders import Product


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
            return [p for p in items if p.get("title")]
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
        return "unknown"

    def _get_js_code(self, source: str) -> str:
        if source == "ebay":
            return """
            (() => {
                const items = document.querySelectorAll('[data-listingid]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/itm/"]');
                    const titleEl = el.querySelector('h3') || el.querySelector('[class*="title"]');
                    const priceEl = el.querySelector('[class*="price"]');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? link.href.split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(p => p.title && p.url);
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
                    if (!href || seen.has(href)) return;
                    seen.add(href);
                    const title = a.getAttribute('aria-label', '') ||
                        Array.from(a.querySelectorAll('span,div,h2,h3')).find(el =>
                            el.textContent.trim().length > 10
                        )?.textContent?.trim() || '';
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
                const items = document.querySelectorAll('[data-product-id]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/product/"]');
                    const titleEl = el.querySelector('.product-title');
                    const priceEl = el.querySelector('.price');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? 'https://wowsports.com' + link.getAttribute('href').split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(p => p.title);
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
                const items = document.querySelectorAll('[data-product-id]');
                return Array.from(items).map(el => {
                    const link = el.querySelector('a[href*="/product/"]');
                    const titleEl = el.querySelector('.product-title');
                    const priceEl = el.querySelector('.price');
                    const imgEl = el.querySelector('img');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
                        url: link ? 'https://www.costway.com' + link.getAttribute('href').split('?')[0] : '',
                        image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
                    };
                }).filter(p => p.title);
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

        extractor = EXTRACTORS.get(self._infer_source(url), {}).get("list")
        if extractor:
            try:
                return extractor(html, url)
            except Exception:
                return []
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
        return ""


class ExtractorChain:
    def __init__(self, strategies: list[tuple[str, int, ExtractionStrategy]]):
        self.strategies = strategies

    def extract(self, page: any, html: str, url: str) -> ExtractionResult:
        for name, min_needed, strategy in self.strategies:
            try:
                products = strategy.extract(page, html, url)
                if len(products) >= min_needed:
                    return ExtractionResult(
                        products=products,
                        strategy=name,
                        method=strategy.method,
                    )
            except Exception:
                continue

        return ExtractionResult(products=[], strategy="none", method="none")


SITE_EXTRACTION_CHAINS: dict[str, ExtractorChain] = {
    "ebay": ExtractorChain(
        [
            ("json_ld", 5, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "target": ExtractorChain(
        [
            ("json_ld", 3, JSONLDExtraction()),
            ("js_eval", 5, JSEvaluateExtraction()),
            ("api_intercept", 10, APIInterceptExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
    ),
    "amazon": ExtractorChain(
        [
            ("js_eval", 5, JSEvaluateExtraction()),
            ("bs_css", 3, BSExtraction()),
        ]
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
