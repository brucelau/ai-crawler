import re, json
from ai_crawler.browser.wrappers.opencli import fetch

html, _ = fetch(
    'https://www.galaxus.ch/en/search?q=inflatables&take=108',
    session='galaxus-gql2',
    wait_time=3.0,
    timeout=30
)

next_data = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
data = json.loads(next_data.group(1))
page_props = data['props']['pageProps']

print('=== preloadedQuery ===')
pq = page_props.get('preloadedQuery', {})
print('Keys:', list(pq.keys()) if isinstance(pq, dict) else type(pq))
if isinstance(pq, dict):
    for k, v in pq.items():
        vstr = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
        print(f'  {k}: {vstr[:300]}')

print()
print('=== variables ===')
variables = page_props.get('variables', {})
print(json.dumps(variables, indent=2)[:1000])

print()
print('=== searchQueryIdWithSelectedFilters ===')
sq = page_props.get('searchQueryIdWithSelectedFilters', {})
print(json.dumps(sq, indent=2)[:1000])
