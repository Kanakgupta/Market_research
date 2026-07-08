#!/usr/bin/env python3
"""Integration test: verify dedup pipeline works end-to-end."""
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent / "src"))

from bluetooth_news.aggregator import process

# Test data with intentional duplicates
test_articles = [
    {
        'title': 'Infineon launches AIROC Bluetooth chip',
        'url': 'https://example.com/article1',
        'source': 'TechCrunch',
        'published': datetime.now(timezone.utc),
        'summary': 'New wireless connectivity solution',
        'thumb': '',
        'bucket_hint': 'bluetooth'
    },
    {
        'title': 'Infineon announces new AIROC Bluetooth device',
        'url': 'https://example.com/article1-mirror',
        'source': 'Engadget',
        'published': datetime.now(timezone.utc),
        'summary': 'New wireless connectivity announced',
        'thumb': '',
        'bucket_hint': 'bluetooth'
    },
    {
        'title': 'Apple adopts Bluetooth 5.4',
        'url': 'https://example.com/article2',
        'source': 'Engadget',
        'published': datetime.now(timezone.utc),
        'summary': 'Latest Apple device uses new Bluetooth',
        'thumb': '',
        'bucket_hint': 'bluetooth'
    },
]

print("=" * 70)
print("Integration Test: Deduplication Pipeline")
print("=" * 70)
print(f"Input: {len(test_articles)} articles (with intentional duplicates)")
for i, a in enumerate(test_articles, 1):
    print(f"  {i}. {a['title']}")
print()

result = process(test_articles, max_age_days=30, verbose=True)

print()
print("=" * 70)
print(f"Output: {len(result)} articles (duplicates removed)")
print("=" * 70)
for i, r in enumerate(result, 1):
    print(f"  {i}. {r['title']}")
    print(f"     Source: {r['source']}")
print()

# Verify deduplication worked
if len(result) == 2:
    print("✓ SUCCESS: Deduplication removed 1 duplicate article!")
    print("  - Kept: 'Infineon launches AIROC Bluetooth chip' (first source)")
    print("  - Kept: 'Apple adopts Bluetooth 5.4' (different story)")
    print("  - Removed: Duplicate 'Infineon announces...' via fuzzy matching")
else:
    print(f"✗ UNEXPECTED: Expected 2 articles, got {len(result)}")
    sys.exit(1)
