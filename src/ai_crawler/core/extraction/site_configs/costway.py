JS_CODE = """
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
