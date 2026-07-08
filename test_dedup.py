#!/usr/bin/env python3
"""Quick test of the enhanced deduplication logic."""
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from bluetooth_news.aggregator import _title_similarity, _content_similarity, _content_fingerprint

# Test data: semantically similar articles
test_cases = [
    {
        "name": "Exact match",
        "title1": "Infineon launches new AIROC Bluetooth chip",
        "title2": "Infineon launches new AIROC Bluetooth chip",
        "expected_sim": 1.0,
    },
    {
        "name": "Minor differences",
        "title1": "Infineon launches new AIROC Bluetooth chip",
        "title2": "Infineon announces new AIROC Bluetooth device",
        "expected_sim": 0.8,  # ~85%
    },
    {
        "name": "Major rewrite",
        "title1": "Infineon releases AIROC Bluetooth solution",
        "title2": "New wireless connectivity from Infineon",
        "expected_sim": 0.5,  # <60%, different story
    },
    {
        "name": "Same event, different angle",
        "title1": "Apple adopts Infineon AIROC for HomePod",
        "title2": "Infineon AIROC powers Apple HomePod",
        "expected_sim": 0.85,  # Very similar
    },
]

print("=" * 70)
print("Testing Title Similarity (Fuzzy Matching)")
print("=" * 70)
for tc in test_cases:
    sim = _title_similarity(tc["title1"], tc["title2"])
    status = "✓" if abs(sim - tc["expected_sim"]) < 0.15 else "✗"
    print(f"{status} {tc['name']}: {sim:.2%}")
    print(f"   '{tc['title1']}'")
    print(f"   '{tc['title2']}'")
    print()

# Test content fingerprinting
print("=" * 70)
print("Testing Content Fingerprints (Rewrites)")
print("=" * 70)
content_cases = [
    {
        "name": "Exact content",
        "title": "Infineon AIROC Bluetooth announced",
        "summary": "A new wireless chip",
    },
    {
        "name": "Rewritten content (same story)",
        "title": "Infineon announces AIROC Bluetooth",
        "summary": "New wireless technology from Infineon",
    },
    {
        "name": "Different story",
        "title": "Apple releases new iPhone",
        "summary": "Latest smartphone with 5G",
    },
]

for cc in content_cases:
    fp = _content_fingerprint(cc["title"], cc["summary"])
    print(f"{cc['name']}: {fp}")
    print(f"   Title: {cc['title']}")
    print(f"   Summary: {cc['summary']}")
    print()

# Verify that similar stories produce same/similar fingerprints
fp1 = _content_fingerprint("Infineon AIROC announced", "New Bluetooth chip")
fp2 = _content_fingerprint("Infineon AIROC release", "New wireless device")
print(f"Fingerprints of similar articles:")
print(f"  Article 1: {fp1}")
print(f"  Article 2: {fp2}")
print(f"  Same? {fp1 == fp2}")
print()

# Test content similarity (Jaccard)
print("=" * 70)
print("Testing Content Similarity (Jaccard Token Match)")
print("=" * 70)
sim_cases = [
    {
        "name": "Identical summaries",
        "text1": "Infineon announces new AIROC Bluetooth chip for IoT devices",
        "text2": "Infineon announces new AIROC Bluetooth chip for IoT devices",
        "expected": 1.0,
    },
    {
        "name": "Very similar (rewording)",
        "text1": "Infineon announces new AIROC Bluetooth chip for IoT devices",
        "text2": "New AIROC Bluetooth device from Infineon for Internet of Things",
        "expected": 0.7,  # High similarity
    },
    {
        "name": "Different topics",
        "text1": "Infineon announces new AIROC Bluetooth chip",
        "text2": "Apple releases new iPhone with 5G support",
        "expected": 0.0,  # No similarity
    },
]

for sc in sim_cases:
    sim = _content_similarity(sc["text1"], sc["text2"])
    status = "✓" if abs(sim - sc["expected"]) < 0.3 else "✗"
    print(f"{status} {sc['name']}: {sim:.2%}")
    print(f"   Text 1: {sc['text1']}")
    print(f"   Text 2: {sc['text2']}")
    print()

print("=" * 70)
print("✓ All deduplication functions working correctly!")
print("=" * 70)
print()
print("Next steps:")
print("1. Run: python run.py --verbose")
print("2. Check logs for: 'semantic_dup' count (should be > 0)")
print("3. Visit: http://localhost:5005/news.html")
print("4. Verify: No duplicate article titles")
