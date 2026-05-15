JS_CODE = """
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

