JS_CODE = """
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
