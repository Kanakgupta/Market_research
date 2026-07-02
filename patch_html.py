#!/usr/bin/env python3
"""Quick patch to apply template changes to existing HTML output."""
from pathlib import Path
import re

html_path = Path('output/latest/customers.html')
if not html_path.exists():
    print(f"File not found: {html_path}")
    exit(1)

content = html_path.read_text(encoding='utf-8')
original = content

# 1. Change "last 3-5 yr" to "last 0-2 years"
content = re.sub(
    r'Recent Products \(last 3-5 yr\)',
    'Recent Products (last 0-2 years)',
    content
)

# 2. Remove Wireless Chip Partners section (entire right column of grid-2)
# Find and remove the right <div> containing "Wireless Chip Partners"
pattern = r'<div>\s*<div class="ci-section-h">&#x1F9E9; Wireless Chip Partners</div>.*?</div>\s*</div>\s*</div>'
content = re.sub(pattern, '</div>', content, flags=re.DOTALL)

if content != original:
    html_path.write_text(content, encoding='utf-8')
    print("✓ Updated customers.html")
    print("  - Changed timeframe to 0-2 years")
    print("  - Removed Wireless Chip Partners section")
else:
    print("No changes made (patterns not found)")
