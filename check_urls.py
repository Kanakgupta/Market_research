#!/usr/bin/env python3
import json
from pathlib import Path

cust = json.loads(Path('data/customers.json').read_text())
google = next((c for c in cust['customers'] if c['name'] == 'Google'), None)
if google:
    total = len(google['recent_products'])
    with_url = sum(1 for p in google['recent_products'] if p.get('url'))
    with_summary = sum(1 for p in google['recent_products'] if p.get('summary'))
    print(f'Google products: {total} total, {with_url} with URL, {with_summary} with summary')
    print()
    print('Newest 5:')
    for p in google['recent_products'][:5]:
        name = p.get('name', '')[:40]
        year = p.get('year')
        has_url = 'url' in p
        has_summary = 'summary' in p
        print(f'{year}: {name} | url:{has_url} summary:{has_summary}')
        if p.get('url'):
            print(f'  -> {p["url"][:70]}')
