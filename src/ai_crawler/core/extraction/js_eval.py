import structlog
from typing import Any

from ai_crawler.core.extraction.base import ExtractionResult, ExtractionStrategy
from ai_crawler.models.product import Product
from ai_crawler.utils.site import infer_site_from_url

log = structlog.get_logger()


class JSEvaluateExtraction(ExtractionStrategy):
    name = "js_eval"
    method = "page_evaluate"

    def extract(self, page: Any, html: str, url: str) -> list[Product]:
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
            log.warning("js_evaluation_extraction_failed", url=url)
            return []

    def _infer_source(self, url: str) -> str:
        return infer_site_from_url(url)

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
                        url: link ? link.getAttribute('href').split('?')[0] : '',
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
