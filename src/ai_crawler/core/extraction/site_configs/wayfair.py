JS_CODE = """
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
