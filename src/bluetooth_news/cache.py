"""SQLite-backed key-value cache for fetched article bodies (avoid re-scraping)."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "cache.db"


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(_DB_PATH)
    c.execute("CREATE TABLE IF NOT EXISTS body_cache (url TEXT PRIMARY KEY, body TEXT, fetched_at REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS history (date TEXT, url TEXT, vendor TEXT, customer TEXT, application TEXT, buckets TEXT, PRIMARY KEY (date, url))")
    # Add columns if they don't exist yet (safe on existing DBs)
    for col, typ in (("title", "TEXT"), ("summary", "TEXT"), ("thumb", "TEXT"), ("source", "TEXT")):
        try:
            c.execute(f"ALTER TABLE history ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass  # column already exists
    return c


def get_body(url: str, max_age_days: int = 30) -> str | None:
    with _conn() as c:
        row = c.execute("SELECT body, fetched_at FROM body_cache WHERE url = ?", (url,)).fetchone()
    if not row:
        return None
    body, ts = row
    if time.time() - (ts or 0) > max_age_days * 86400:
        return None
    return body


def put_body(url: str, body: str) -> None:
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO body_cache (url, body, fetched_at) VALUES (?, ?, ?)",
                  (url, body, time.time()))


def record_history(date_iso: str, articles: list[dict]) -> None:
    """Insert one row per article for the given date (idempotent)."""
    with _conn() as c:
        for a in articles:
            c.execute(
                "INSERT OR IGNORE INTO history "
                "(date, url, vendor, customer, application, buckets, title, summary, thumb, source) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    date_iso, a.get("url", ""), a.get("vendor"), a.get("customer"),
                    a.get("application"), ",".join(a.get("buckets", []) or []),
                    (a.get("title") or "")[:500],
                    (a.get("summary") or "")[:500],
                    (a.get("thumb") or "")[:500],
                    (a.get("source") or "")[:200],
                )
            )


def vendor_history(days: int = 90) -> list[tuple[str, str, int]]:
    """Return [(date, vendor, count)] for the last `days` days."""
    with _conn() as c:
        rows = c.execute(
            "SELECT date, vendor, COUNT(*) FROM history "
            "WHERE vendor IS NOT NULL AND date >= date('now', ?) "
            "GROUP BY date, vendor ORDER BY date",
            (f"-{days} days",)
        ).fetchall()
    return rows


def vendor_week_counts(weeks: int = 8) -> tuple[dict[str, list[int]], list[str]]:
    """Return ({vendor: [counts]}, [week_labels]) over the last `weeks` weeks."""
    with _conn() as c:
        rows = c.execute(
            "SELECT vendor, strftime('%Y-%W', date) AS wk, COUNT(*) "
            "FROM history WHERE vendor IS NOT NULL AND date >= date('now', ?) "
            "GROUP BY vendor, wk ORDER BY wk",
            (f"-{weeks * 7} days",)
        ).fetchall()
    out: dict[str, dict[str, int]] = {}
    weeks_seen: list[str] = []
    for vendor, wk, n in rows:
        out.setdefault(vendor, {})[wk] = n
        if wk not in weeks_seen:
            weeks_seen.append(wk)
    return {v: [counts.get(w, 0) for w in weeks_seen] for v, counts in out.items()}, weeks_seen
