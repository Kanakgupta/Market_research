"""Fetch articles from RSS feeds (with bucket hint) and optional NewsAPI."""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone

import feedparser
import re
import requests
from dateutil import parser as dateparser

from .sources import all_feed_urls

log = logging.getLogger(__name__)

USER_AGENT = "IoTNewsAggregator/0.2 (+https://example.local)"
REQUEST_TIMEOUT = 20

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


def fetch_rss() -> list[dict]:
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    feeds = all_feed_urls()
    articles: list[dict] = []
    
    def fetch_one(feed: dict) -> list[dict]:
        name, url, bucket_hint = feed["name"], feed["url"], feed.get("bucket")
        feed_articles = []
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
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
                    "title":     raw_title,
                    "url":       (entry.get("link") or "").strip(),
                    "source":    display_source,
                    "feed_name": name,
                    "published": published,
                    "summary":   (entry.get("summary") or "").strip(),
                    "thumb":     _extract_thumb(entry),
                    "bucket_hint": bucket_hint,
                })
            log.info("Fetched %d entries from %s", len(parsed.entries), name)
        except Exception as exc:
            log.warning("Failed to fetch %s: %s", name, exc)
        return feed_articles

    MAX_WORKERS = 30
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_one, feed): feed for feed in feeds}
        for fut in as_completed(futures):
            articles.extend(fut.result())
            
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
