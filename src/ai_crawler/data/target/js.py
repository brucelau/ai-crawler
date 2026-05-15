JS_CODE = """
(() => {
    const items = document.querySelectorAll('a[href*="/A-"], a[href*="/p/"]');
    const seen = new Set();
    const results = [];
    items.forEach(a => {
        const href = a.getAttribute('href', '').split('#')[0].split('?')[0];
        const title = a.getAttribute('aria-label', '') ||
            (a.textContent || '').trim() ||
            Array.from(a.querySelectorAll('span,div,h2,h3')).find(el =>
                el.textContent.trim().length > 10
            )?.textContent?.trim() || '';
        if (!href || !title || title.length <= 5 || seen.has(href)) return;
        seen.add(href);
        const parent = a.closest('li, div, section');
        const priceText = parent ? parent.textContent : '';
        const price = (priceText.match(/\\$([\\d,]+\\.?\\d*)/) || [])[1] || '';
        const img = a.querySelector('img');
        results.push({
            title: title.slice(0, 200),
            url: 'https://www.target.com' + href,
            price: price.replace(/,/g, ''),
            image: img ? (img.src || img.dataset.src || '') : ''
        });
    });
    return results.filter(p => p.title.length > 5);
})()
"""

