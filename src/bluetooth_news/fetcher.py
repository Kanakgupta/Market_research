"""Fetch articles from RSS feeds (with bucket hint) and optional NewsAPI."""
from __future__ import annotations

import logging
import os
import random
import re
import json
import time
import threading
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests
from dateutil import parser as dateparser

from .sources import all_feed_urls

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 20
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

DEFAULT_MAX_WORKERS = 16
DEFAULT_GOOGLE_MAX_WORKERS = 2
DEFAULT_OTHER_MAX_WORKERS = 12

_GOOGLE_FAIL_STATE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "google_feed_failures.json"
_google_fail_lock = threading.Lock()
_google_fail_state_loaded = False
_google_fail_state: dict[str, dict] = {}

_IMG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.I)


def _parse_date(value):
    if not value:
        return None
    try:
        if isinstance(value, str):
            dt = dateparser.parse(value)
        else:
            dt = datetime(*value[:6], tzinfo=timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _extract_thumb(entry) -> str:
    thumbs = entry.get("media_thumbnail") or []
    if thumbs and isinstance(thumbs, list):
        url = thumbs[0].get("url")
        if url:
            return url
    media = entry.get("media_content") or []
    if media and isinstance(media, list):
        for m in media:
            url = m.get("url")
            if url and (m.get("medium") == "image" or url.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))):
                return url
    for enc in entry.get("enclosures", []) or []:
        t = (enc.get("type") or "").lower()
        if t.startswith("image/") and enc.get("href"):
            return enc["href"]
    for field in ("content", "summary_detail"):
        val = entry.get(field)
        if isinstance(val, list) and val:
            html = val[0].get("value", "")
        elif isinstance(val, dict):
            html = val.get("value", "")
        else:
            html = ""
        m = _IMG_RE.search(html or "")
        if m:
            return m.group(1)
    m = _IMG_RE.search(entry.get("summary") or "")
    if m:
        return m.group(1)
    return ""


def _is_google_feed(url: str) -> bool:
    return "news.google.com" in (url or "").lower()


def _sleep_with_jitter(seconds: float) -> None:
    jitter = random.uniform(0.0, 0.4)
    time.sleep(seconds + jitter)


def _load_google_fail_state_locked() -> None:
    global _google_fail_state_loaded, _google_fail_state
    if _google_fail_state_loaded:
        return
    _google_fail_state_loaded = True
    if not _GOOGLE_FAIL_STATE_PATH.exists():
        _google_fail_state = {}
        return
    try:
        payload = json.loads(_GOOGLE_FAIL_STATE_PATH.read_text(encoding="utf-8"))
        feeds = payload.get("feeds") if isinstance(payload, dict) else {}
        _google_fail_state = feeds if isinstance(feeds, dict) else {}
    except Exception:
        _google_fail_state = {}


def _save_google_fail_state_locked() -> None:
    _GOOGLE_FAIL_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "feeds": _google_fail_state,
    }
    _GOOGLE_FAIL_STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _fetch_url_with_retries(url: str, name: str) -> bytes:
    is_google = _is_google_feed(url)
    max_attempts = 5 if is_google else 3
    base_backoff = 1.0 if is_google else 0.6
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
    }

    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers=headers)
            if resp.status_code in RETRYABLE_STATUS:
                raise requests.HTTPError(
                    f"{resp.status_code} Server Error for url: {url}", response=resp
                )
            resp.raise_for_status()
            return resp.content
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
            last_exc = exc
            if attempt >= max_attempts:
                break
            # Exponential backoff reduces repeated rate-limited hits.
            _sleep_with_jitter(base_backoff * (2 ** (attempt - 1)))

    assert last_exc is not None
    raise last_exc


def _safe_int_env(name: str, default: int, minimum: int = 1) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        log.warning("Invalid integer for %s=%r; using default=%d", name, raw, default)
        return default


def _google_cooldown_minutes() -> int:
    raw = (os.getenv("GOOGLE_FEED_FAIL_COOLDOWN_MINUTES") or "").strip()
    if not raw:
        return 180
    try:
        return max(0, int(raw))
    except ValueError:
        log.warning("Invalid integer for GOOGLE_FEED_FAIL_COOLDOWN_MINUTES=%r; using default=180", raw)
        return 180


def _google_fail_threshold() -> int:
    raw = (os.getenv("GOOGLE_FEED_FAIL_THRESHOLD") or "").strip()
    if not raw:
        return 2
    try:
        return max(1, int(raw))
    except ValueError:
        log.warning("Invalid integer for GOOGLE_FEED_FAIL_THRESHOLD=%r; using default=2", raw)
        return 2


def _is_google_feed_on_cooldown(url: str) -> bool:
    now = time.time()
    with _google_fail_lock:
        _load_google_fail_state_locked()
        rec = _google_fail_state.get(url) or {}
        cooldown_until = float(rec.get("cooldown_until", 0) or 0)
        if cooldown_until > now:
            return True
        # Purge stale records once cooldown has elapsed.
        if rec:
            _google_fail_state.pop(url, None)
            _save_google_fail_state_locked()
    return False


def _record_google_feed_failure(url: str) -> None:
    now = time.time()
    threshold = _google_fail_threshold()
    cooldown_minutes = _google_cooldown_minutes()
    with _google_fail_lock:
        _load_google_fail_state_locked()
        rec = _google_fail_state.get(url) or {}
        failures = int(rec.get("failures", 0) or 0) + 1
        next_rec = {
            "failures": failures,
            "last_fail_at": now,
        }
        if failures >= threshold and cooldown_minutes > 0:
            next_rec["cooldown_until"] = now + cooldown_minutes * 60
        _google_fail_state[url] = next_rec
        _save_google_fail_state_locked()


def _record_google_feed_success(url: str) -> None:
    with _google_fail_lock:
        _load_google_fail_state_locked()
        if url in _google_fail_state:
            _google_fail_state.pop(url, None)
            _save_google_fail_state_locked()


def _fetch_feed_articles(feed: dict) -> list[dict]:
    name, url, bucket_hint = feed["name"], feed["url"], feed.get("bucket")
    feed_articles = []
    if _is_google_feed(url) and _is_google_feed_on_cooldown(url):
        log.warning("Skipping %s due to recent repeated failures (cooldown active)", name)
        return feed_articles
    try:
        content = _fetch_url_with_retries(url, name)
        parsed = feedparser.parse(content)
        for entry in parsed.entries:
            published = _parse_date(
                entry.get("published") or entry.get("updated") or entry.get("published_parsed")
            )
            raw_title = (entry.get("title") or "").strip()
            # Google News RSS: entry.source.title = real publisher (e.g. "The Verge")
            src_obj = entry.get("source") or {}
            publisher = (src_obj.get("title") or "").strip()
            # Fallback: extract " - Publisher" suffix from title
            if not publisher:
                m_pub = re.search(r" - ([^-]{3,60})$", raw_title)
                if m_pub:
                    publisher = m_pub.group(1).strip()
            display_source = publisher if publisher else name
            feed_articles.append({
                "title": raw_title,
                "url": (entry.get("link") or "").strip(),
                "source": display_source,
                "feed_name": name,
                "published": published,
                "summary": (entry.get("summary") or "").strip(),
                "thumb": _extract_thumb(entry),
                "bucket_hint": bucket_hint,
            })
        if _is_google_feed(url):
            _record_google_feed_success(url)
        log.info("Fetched %d entries from %s", len(parsed.entries), name)
    except Exception as exc:
        if _is_google_feed(url):
            _record_google_feed_failure(url)
        log.warning("Failed to fetch %s: %s", name, exc)
    return feed_articles


def _fetch_concurrent(feeds: list[dict], max_workers: int) -> list[dict]:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if not feeds:
        return []

    articles: list[dict] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_feed_articles, feed): feed for feed in feeds}
        for fut in as_completed(futures):
            articles.extend(fut.result())
    return articles


def fetch_rss() -> list[dict]:
    feeds = all_feed_urls()
    if not feeds:
        return []

    google_feeds = [f for f in feeds if _is_google_feed(f.get("url", ""))]
    other_feeds = [f for f in feeds if not _is_google_feed(f.get("url", ""))]

    max_workers = _safe_int_env("FETCH_MAX_WORKERS", DEFAULT_MAX_WORKERS)
    google_workers = _safe_int_env("FETCH_GOOGLE_MAX_WORKERS", DEFAULT_GOOGLE_MAX_WORKERS)
    other_workers = _safe_int_env("FETCH_OTHER_MAX_WORKERS", DEFAULT_OTHER_MAX_WORKERS)
    # Ensure subgroup workers never exceed the global worker ceiling.
    google_workers = min(google_workers, max_workers)
    other_workers = min(other_workers, max_workers)

    log.info(
        "Fetching RSS feeds: total=%d google=%d other=%d workers(g=%d,o=%d)",
        len(feeds), len(google_feeds), len(other_feeds), google_workers, other_workers
    )

    articles: list[dict] = []
    articles.extend(_fetch_concurrent(other_feeds, other_workers))
    articles.extend(_fetch_concurrent(google_feeds, google_workers))
    return articles


def fetch_newsapi(query: str = "IoT wireless", page_size: int = 100) -> list[dict]:
    api_key = os.getenv("NEWSAPI_KEY", "").strip()
    if not api_key:
        return []
    try:
        resp = requests.get(
            "https://newsapi.org/v2/everything",
            params={"q": query, "language": "en", "sortBy": "publishedAt", "pageSize": page_size},
            headers={"X-Api-Key": api_key, "User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.warning("NewsAPI request failed: %s", exc)
        return []
    out: list[dict] = []
    for item in resp.json().get("articles", []):
        out.append({
            "title":     (item.get("title") or "").strip(),
            "url":       (item.get("url") or "").strip(),
            "source":    f"NewsAPI: {(item.get('source') or {}).get('name', 'unknown')}",
            "published": _parse_date(item.get("publishedAt")),
            "summary":   (item.get("description") or "").strip(),
            "thumb":     (item.get("urlToImage") or "").strip(),
            "bucket_hint": None,
        })
    return out


def fetch_featured_articles() -> list[dict]:
    """Fetch critical featured articles directly using trafilatura.
    
    These articles bypass the relevance filter to ensure important tech news
    is always captured despite potential keyword matching issues.
    """
    from .sources import FEATURED_ARTICLES
    try:
        import trafilatura
    except ImportError:
        log.warning("trafilatura not available; skipping featured articles")
        return []
    
    articles: list[dict] = []
    for url in FEATURED_ARTICLES:
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
            resp.raise_for_status()
            
            # Extract content using trafilatura
            extracted_text = trafilatura.extract(resp.text, include_comments=False, favor_precision=True)
            if not extracted_text:
                log.warning("Could not extract content from featured article: %s", url)
                continue
            
            # Extract metadata (trafilatura may return either object attrs or dict-like)
            metadata = trafilatura.extract_metadata(resp.text)
            if not metadata:
                log.warning("Could not extract metadata from featured article: %s", url)
                continue

            title = None
            published = None
            if isinstance(metadata, dict):
                title = metadata.get("title")
                published = metadata.get("date")
            else:
                title = getattr(metadata, "title", None)
                published = getattr(metadata, "date", None)

            title = title or "Featured Article"
            if isinstance(published, str):
                published = _parse_date(published)
            
            # Extract image from HTML
            thumb_match = _IMG_RE.search(resp.text)
            thumb = thumb_match.group(1) if thumb_match else ""
            
            articles.append({
                "title": title,
                "url": url,
                "source": "Featured",
                "feed_name": "Featured Articles",
                "published": published,
                "summary": extracted_text[:500],  # First 500 chars
                "thumb": thumb,
                "bucket_hint": "bluetooth",  # Default hint for featured articles
            })
            log.info("Fetched featured article: %s", title[:60])
        except Exception as exc:
            log.warning("Failed to fetch featured article %s: %s", url, exc)
    
    return articles


def fetch_all() -> list[dict]:
    return fetch_rss() + fetch_newsapi() + fetch_featured_articles()
