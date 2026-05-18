JS_CODE = """
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

