JS_CODE = """
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

