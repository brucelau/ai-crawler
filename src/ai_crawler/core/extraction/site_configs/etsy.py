JS_CODE = """
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
