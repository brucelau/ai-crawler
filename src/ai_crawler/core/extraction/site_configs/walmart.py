JS_CODE = """
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
