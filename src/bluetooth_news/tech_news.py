"""Cache-then-fetch technology news feed.

Mirrors the SCREENER ``fetch_market_news`` + tiered-cache pattern:

* Technology RSS feeds are fetched server-side (no CORS / proxy at view time).
* Results are written to ``data/tech_news_cache.json`` with an ``updated_at``.
* :func:`get_tech_news` serves straight from that cache until it is older than
  ``ttl_minutes`` (default 30), then refetches once and rewrites the cache.

This gives the News tab a live, always-technology feed that updates on demand
without waiting for the nightly full rebuild.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
CACHE_FILE = ROOT / "data" / "tech_news_cache.json"
DEFAULT_TTL_MINUTES = 30

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_IMG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.I)
_TAG_RE = re.compile(r"<[^>]+>")

# Technology-focused RSS sources. Broad consumer/enterprise tech plus the
# wireless / IoT / semiconductor angle this project cares about.
TECH_FEEDS: list[dict] = [
    {"source": "The Verge",     "cat": "Tech",           "url": "https://www.theverge.com/rss/index.xml"},
    {"source": "Ars Technica",  "cat": "Tech",           "url": "https://feeds.arstechnica.com/arstechnica/index"},
    {"source": "TechCrunch",    "cat": "Tech",           "url": "https://techcrunch.com/feed/"},
    {"source": "The Register",  "cat": "Tech",           "url": "https://www.theregister.com/headlines.atom"},
    {"source": "Wired",         "cat": "Tech",           "url": "https://www.wired.com/feed/rss"},
    {"source": "Engadget",      "cat": "Tech",           "url": "https://www.engadget.com/rss.xml"},
    {"source": "9to5Google",    "cat": "Tech",           "url": "https://9to5google.com/feed/"},
    {"source": "9to5Mac",       "cat": "Tech",           "url": "https://9to5mac.com/feed/"},
    {"source": "IEEE Spectrum", "cat": "Tech",           "url": "https://spectrum.ieee.org/rss"},
    {"source": "EE Times",      "cat": "Semiconductors", "url": "https://www.eetimes.com/feed/"},
    {"source": "CNX Software",  "cat": "Semiconductors", "url": "https://www.cnx-software.com/feed/"},
    {"source": "ZDNet",         "cat": "Tech",           "url": "https://www.zdnet.com/news/rss.xml"},
    {"source": "Bluetooth SIG", "cat": "Wireless",       "url": "https://www.bluetooth.com/blog/feed/"},
    {"source": "CSA / Matter",  "cat": "Wireless",       "url": "https://csa-iot.org/feed/"},
]

_lock = threading.Lock()


def _strip_html(s: str) -> str:
    if not s:
        return ""
    return _TAG_RE.sub("", s).replace("&nbsp;", " ").strip()


def _thumb(entry) -> str:
    thumbs = entry.get("media_thumbnail") or []
    if isinstance(thumbs, list) and thumbs and thumbs[0].get("url"):
        return thumbs[0]["url"]
    for m in entry.get("media_content", []) or []:
        url = m.get("url")
        if url and (m.get("medium") == "image" or url.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))):
            return url
    for enc in entry.get("enclosures", []) or []:
        if (enc.get("type") or "").lower().startswith("image/") and enc.get("href"):
            return enc["href"]
    m = _IMG_RE.search(entry.get("summary") or "")
    return m.group(1) if m else ""


def _iso(entry) -> str:
    for key in ("published_parsed", "updated_parsed"):
        val = entry.get(key)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc).isoformat()
            except Exception:
                pass
    return ""


def _fetch_feed(feed: dict, timeout: int = 12) -> list[dict]:
    url = feed["url"]
    source = feed.get("source") or url
    cat = feed.get("cat") or "Tech"
    try:
        resp = requests.get(
            url, timeout=timeout,
            headers={"User-Agent": _UA,
                     "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8"},
        )
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)
    except Exception as exc:  # noqa: BLE001
        log.info("tech_news: skip %s: %s", source, exc)
        return []

    items: list[dict] = []
    for e in parsed.entries[:25]:
        title = (e.get("title") or "").strip()
        link = (e.get("link") or "").strip()
        if not title or not link:
            continue
        items.append({
            "source": source,
            "cat": cat,
            "title": title,
            "link": link,
            "desc": _strip_html(e.get("summary") or "")[:240],
            "image": _thumb(e),
            "pub": _iso(e),
        })
    return items


def _fetch_all(max_workers: int = 8) -> dict:
    all_items: list[dict] = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_fetch_feed, f): f for f in TECH_FEEDS}
        for fut in as_completed(futures):
            try:
                all_items.extend(fut.result(timeout=15))
            except Exception as exc:  # noqa: BLE001
                log.info("tech_news: feed error: %s", exc)

    # Advanced de-dupe: by link (exact) + title similarity + content hash
    import hashlib
    from difflib import SequenceMatcher
    
    def _title_sim(t1: str, t2: str) -> float:
        """Fuzzy title match (0-1)."""
        if not t1 or not t2:
            return 0.0
        t1_norm = t1.lower().replace("&amp;", "&").replace("-", " ")
        t2_norm = t2.lower().replace("&amp;", "&").replace("-", " ")
        return SequenceMatcher(None, t1_norm, t2_norm).ratio()
    
    def _content_hash(title: str, desc: str) -> str:
        """Quick content fingerprint."""
        combined = (title + " " + (desc or "")).lower()
        # Keep only first 50 chars-worth of meaningful text
        words = combined.split()[:15]
        return hashlib.md5(" ".join(words).encode()).hexdigest()
    
    seen_links = set()
    seen_hashes = set()
    deduped: list[dict] = []
    
    for it in all_items:
        link = it.get("link", "")
        title = it.get("title", "")
        desc = it.get("desc", "")
        
        # Exact link match = skip
        if link in seen_links:
            continue
        
        # Content hash match = skip (catches rewrites)
        ch = _content_hash(title, desc)
        if ch in seen_hashes:
            continue
        
        # Fuzzy title match with higher similarity + recent timestamp = skip
        dup_by_title = False
        for existing in deduped:
            sim = _title_sim(title, existing.get("title", ""))
            if sim > 0.75:  # 75% similarity threshold for news syndication
                # Prefer if this one is newer or from better source
                if (it.get("pub", "") <= existing.get("pub", "")):
                    dup_by_title = True
                    break
        
        if not dup_by_title:
            seen_links.add(link)
            seen_hashes.add(ch)
            deduped.append(it)
    
    # Sort by recency
    items = sorted(deduped, key=lambda x: x.get("pub") or "", reverse=True)

    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(items),
        "items": items[:200],
    }


def _load_cache() -> dict | None:
    if not CACHE_FILE.exists():
        return None
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_cache(payload: dict) -> None:
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        log.warning("tech_news: could not write cache: %s", exc)


def _age_minutes(payload: dict) -> float:
    ts = payload.get("updated_at")
    if not ts:
        return 1e9
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 60.0
    except Exception:
        return 1e9


def get_tech_news(force: bool = False, ttl_minutes: int = DEFAULT_TTL_MINUTES) -> dict:
    """Cache-then-fetch: return cached tech news unless stale (or ``force``)."""
    with _lock:
        cached = _load_cache()
        if not force and cached and _age_minutes(cached) < ttl_minutes and cached.get("items"):
            cached["cached"] = True
            return cached
        try:
            payload = _fetch_all()
        except Exception as exc:  # noqa: BLE001
            log.warning("tech_news: fetch failed (%s); serving cache", exc)
            if cached:
                cached["cached"] = True
                return cached
            return {"updated_at": datetime.now(timezone.utc).isoformat(), "count": 0, "items": []}
        _save_cache(payload)
        payload["cached"] = False
        return payload


def refresh(ttl_minutes: int = 0) -> dict:
    """Force a refresh (used by the nightly/daily build)."""
    return get_tech_news(force=True, ttl_minutes=ttl_minutes)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    t0 = time.time()
    data = get_tech_news(force=True)
    print(f"[tech_news] fetched {data['count']} items in {time.time() - t0:.1f}s -> {CACHE_FILE}")
