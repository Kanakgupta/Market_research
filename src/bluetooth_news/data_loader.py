"""Load editable JSON data files (customers, competitors)."""
from __future__ import annotations

import json
from pathlib import Path


def _data_dir() -> Path:
    # Project root is two levels above this file (src/bluetooth_news/data_loader.py).
    return Path(__file__).resolve().parents[2] / "data"


def load_customers() -> list[dict]:
    p = _data_dir() / "customers.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8")).get("customers", [])


def load_competitors() -> dict:
    p = _data_dir() / "competitors.json"
    if not p.exists():
        return {"anchor": {}, "competitors": []}
    return json.loads(p.read_text(encoding="utf-8"))
