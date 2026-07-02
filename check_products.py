#!/usr/bin/env python3
import json
from pathlib import Path

cust_file = Path('data/customers.json')
cust = json.loads(cust_file.read_text())

google = next((c for c in cust['customers'] if c['name'] == 'Google'), None)
if google:
    print('Google recent_products sample:')
    for p in google['recent_products'][:5]:
        has_url = "url" in p
        print(f"  Name: {p.get('name')}, Year: {p.get('year')}, Has URL: {has_url}, Has Summary: {'summary' in p}")
        if has_url:
            print(f"    URL: {p['url'][:60]}...")
        if 'summary' in p:
            print(f"    Summary: {p['summary'][:80]}...")
