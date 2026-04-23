JS_CODE = """
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
