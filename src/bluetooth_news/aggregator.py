"""Normalize, dedupe, classify, sort articles."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse

from .classifier import classify_buckets, detect_vendor, detect_customer, detect_application

_WS = re.compile(r"\s+")
_TAG = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _WS.sub(" ", _TAG.sub("", text or "")).strip()


def _normalize_url(url: str) -> str:
    if not url:
        return ""
    try:
        p = urlparse(url)
        return urlunparse((p.scheme.lower(), p.netloc.lower(), p.path, "", "", ""))
    except ValueError:
        return url


def _normalize_title(title: str) -> str:
    return _WS.sub(" ", (title or "").lower()).strip()


def process(
    articles: list[dict],
    max_age_days: int | None = 30,
    limit: int | None = 1000,
    verbose: bool = False,
) -> list[dict]:
    import logging
    logger = logging.getLogger(__name__)
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days) if max_age_days else None
    seen_urls, seen_titles = set(), set()
    cleaned: list[dict] = []
    filtered_count = {"age": 0, "empty": 0, "duplicate": 0, "relevance": 0}
    for a in articles:
        title = (a.get("title") or "").strip()
        # Strip " - Publisher" suffix Google News appends to titles (already captured as source)
        title = re.sub(r"\s+-\s+[^-]{3,60}$", "", title).strip()
        url = (a.get("url") or "").strip()
        if not title or not url:
            filtered_count["empty"] += 1
            continue
        nu, nt = _normalize_url(url), _normalize_title(title)
        if nu in seen_urls or nt in seen_titles:
            filtered_count["duplicate"] += 1
            continue
        published = a.get("published")
        # Featured articles bypass age filter
        is_featured = a.get("feed_name") == "Featured Articles"
        if cutoff and published and published < cutoff and not is_featured:
            filtered_count["age"] += 1
            if verbose:
                logger.info(f"Filtered by age (older than {max_age_days}d): {title[:60]}...")
            continue
        summary = _strip_html(a.get("summary") or "")
        # Strip Google News RSS artifact: summary = "Title\xa0\xa0Publisher" (title repeated)
        # After _strip_html the non-breaking spaces become regular spaces or \xa0
        _sum_norm = re.sub(r"[\s\xa0]+", " ", summary).lower().strip()
        _ttl_norm = re.sub(r"[\s\xa0]+", " ", title).lower().strip()
        if _sum_norm and (_sum_norm == _ttl_norm or _sum_norm.startswith(_ttl_norm[:60])):
            summary = ""
        text = f"{title} {summary}"
        buckets = classify_buckets(text, a.get("bucket_hint"))
        vendor, vendor_region = detect_vendor(text)
        customer = detect_customer(text)
        application = detect_application(text)
        # Keep article when at least one of (bucket / vendor / customer / app) matches.
        # Otherwise the world is too noisy.
        # Featured articles bypass this filter.
        if not is_featured and not buckets and not vendor and not customer and not application:
            filtered_count["relevance"] += 1
            if verbose:
                logger.info(f"Filtered by relevance (no match): {title[:60]}... | buckets={buckets}, vendor={vendor}, customer={customer}, app={application}")
            continue
        seen_urls.add(nu)
        seen_titles.add(nt)
        cleaned.append({
            "title": title, "url": url, "source": a.get("source") or "Unknown",
            "published": published, "summary": summary,
            "thumb": (a.get("thumb") or "").strip(),
            "buckets": buckets,
            "vendor": vendor, "vendor_region": vendor_region,
            "customer": customer, "application": application,
        })
    cleaned.sort(key=lambda x: (x["published"] is None,
                                -(x["published"].timestamp() if x["published"] else 0)))
    if limit:
        cleaned = cleaned[:limit]

    # Decode Google News tracking URLs to direct source URLs in parallel
    try:
        from .gnews_decoder import decode_articles_urls
        cleaned = decode_articles_urls(cleaned)
    except Exception as e:
        logger.warning("Failed decoding Google News URLs: %s", e)

    if verbose or filtered_count["relevance"] > 100:
        logger.info(f"Aggregator filtering summary: empty={filtered_count['empty']}, duplicate={filtered_count['duplicate']}, age={filtered_count['age']}, relevance={filtered_count['relevance']}")        
    return cleaned
