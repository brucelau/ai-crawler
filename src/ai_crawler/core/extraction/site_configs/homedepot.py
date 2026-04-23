JS_CODE = """
(() => {
    const selectors = [
        '[data-item-id]',
        '[data-pod-type="product"]',
        '.product-card',
        '.product-pod',
        'li[class*="product"]',
        '[data-testid="product-card"]',
        'article[class*="product"]'
    ];
    let items = [];
    for (const sel of selectors) {
        items = document.querySelectorAll(sel);
        if (items.length > 0) break;
    }
    return Array.from(items).map(el => {
        const link = el.querySelector('a[href*="/p/"], a[href*="/ip/"]');
        const titleEl = el.querySelector('.product-header__title, [data-testid="product-title"], h3, [class*="title"]');
        const priceEl = el.querySelector('.price-format__dollars, [data-testid="product-price"], [class*="price"]');
        const imgEl = el.querySelector('img');
        return {
            title: titleEl ? titleEl.textContent.trim() : '',
            price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
            url: link ? 'https://www.homedepot.com' + link.getAttribute('href').split('?')[0] : '',
            image: imgEl ? (imgEl.src || imgEl.dataset.src || '') : ''
        };
    }).filter(p => p.title && p.title.length > 5);
})()
"""
