JS_CODE = """
(() => {
    const items = document.querySelectorAll('[data-asin]');
    return Array.from(items).map(el => {
        const asin = el.getAttribute('data-asin');
        const titleEl = el.querySelector('span.a-text-normal') || el.querySelector('h2 a span');
        const priceEl = el.querySelector('.a-price .a-offscreen');
        const ratingEl = el.querySelector('.a-icon-star-small');
        const imgEl = el.querySelector('img.s-image');
        return {
            title: titleEl ? titleEl.textContent.trim() : '',
            price: priceEl ? priceEl.textContent.trim().replace(/[^\\d.]/g, '') : '',
            asin: asin || '',
            url: asin ? 'https://www.amazon.com/dp/' + asin : '',
            image: imgEl ? imgEl.src : ''
        };
    }).filter(p => p.title && p.asin);
})()
"""

