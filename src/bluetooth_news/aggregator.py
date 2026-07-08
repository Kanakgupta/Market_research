"""Normalize, dedupe, classify, sort articles."""
from __future__ import annotations

import re
import hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse
from difflib import SequenceMatcher

from .classifier import classify_buckets, detect_vendor, detect_customer, detect_application

_WS = re.compile(r"\s+")
_TAG = re.compile(r"<[^>]+>")
_PUNCTUATION = re.compile(r"[^\w\s]")


def _strip_html(text: str) -> str:
    return _WS.sub(" ", _TAG.sub("", text or "")).strip()


def _normalize_url(url: str) -> str:
    if not url:
        return ""
    try:
        p = urlparse(url)
        # Remove query params & fragments for core URL comparison
        return urlunparse((p.scheme.lower(), p.netloc.lower(), p.path, "", "", ""))
    except ValueError:
        return url


def _normalize_title(title: str) -> str:
    """Lowercase, collapse whitespace, remove punctuation."""
    text = _WS.sub(" ", (title or "").lower()).strip()
    # Remove punctuation for better similarity matching
    text = _PUNCTUATION.sub("", text)
    return text


def _content_fingerprint(title: str, summary: str) -> str:
    """Generate a hash fingerprint of content for semantic dedup."""
    norm_title = _normalize_title(title)
    norm_summary = _normalize_title(summary) if summary else ""
    # Take first 30 tokens of normalized content
    tokens = (norm_title + " " + norm_summary).split()[:30]
    content = " ".join(tokens)
    return hashlib.md5(content.encode()).hexdigest()


def _title_similarity(title1: str, title2: str) -> float:
    """Compute fuzzy match score between titles (0.0 to 1.0)."""
    t1 = _normalize_title(title1)
    t2 = _normalize_title(title2)
    if not t1 or not t2:
        return 0.0
    matcher = SequenceMatcher(None, t1, t2)
    return matcher.ratio()


def _content_similarity(text1: str, text2: str) -> float:
    """Compute similarity between article summaries."""
    # Normalize & tokenize
    norm1 = _normalize_title(text1)
    norm2 = _normalize_title(text2)
    if not norm1 or not norm2:
        return 0.0
    tokens1 = set(norm1.split())
    tokens2 = set(norm2.split())
    if not tokens1 or not tokens2:
        return 0.0
    # Jaccard similarity
    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)
    return intersection / union if union > 0 else 0.0


def process(
    articles: list[dict],
    max_age_days: int | None = 30,
    limit: int | None = 1000,
    verbose: bool = False,
) -> list[dict]:
    import logging
    logger = logging.getLogger(__name__)
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days) if max_age_days else None
    
    # Multi-layer dedup tracking:
    # - seen_urls: exact normalized URLs
    # - seen_fingerprints: content hashes (catches rewrites of same article)
    # - candidates: articles that passed basic filters (for fuzzy matching pass)
    seen_urls = set()
    seen_fingerprints = set()
    candidates: list[dict] = []
    filtered_count = {"age": 0, "empty": 0, "duplicate": 0, "semantic_dup": 0, "relevance": 0}
    
    # First pass: basic filtering (empty, URL dedup, age, relevance)
    for a in articles:
        title = (a.get("title") or "").strip()
        # Strip " - Publisher" suffix Google News appends to titles (already captured as source)
        title = re.sub(r"\s+-\s+[^-]{3,60}$", "", title).strip()
        url = (a.get("url") or "").strip()
        if not title or not url:
            filtered_count["empty"] += 1
            continue
        
        # URL-based dedup (exact normalized URLs)
        nu = _normalize_url(url)
        if nu in seen_urls:
            filtered_count["duplicate"] += 1
            continue
        seen_urls.add(nu)
        
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
        # Featured articles bypass this filter.
        if not is_featured and not buckets and not vendor and not customer and not application:
            filtered_count["relevance"] += 1
            if verbose:
                logger.info(f"Filtered by relevance (no match): {title[:60]}...")
            continue
        
        candidates.append({
            "title": title, "url": url, "source": a.get("source") or "Unknown",
            "published": published, "summary": summary,
            "thumb": (a.get("thumb") or "").strip(),
            "buckets": buckets,
            "vendor": vendor, "vendor_region": vendor_region,
            "customer": customer, "application": application,
        })
    
    # Second pass: semantic/content-based dedup (fuzzy matching)
    # Keep newer/better articles when near-duplicates are found
    cleaned: list[dict] = []
    for candidate in candidates:
        title = candidate["title"]
        summary = candidate["summary"]
        
        # Check content fingerprint (catches rewrites of same news)
        fp = _content_fingerprint(title, summary)
        if fp in seen_fingerprints:
            filtered_count["semantic_dup"] += 1
            continue
        
        # Fuzzy match against existing articles: if >75% title match OR >75% content match
        # with a more recent/better source, skip
        duplicate_found = False
        for existing in cleaned:
            title_sim = _title_similarity(title, existing["title"])
            # If same vendor and customer, be stricter (>85% match = duplicate)
            if (candidate.get("vendor") == existing.get("vendor") and
                candidate.get("customer") == existing.get("customer")):
                threshold = 0.85
            else:
                threshold = 0.75  # Slightly lower for real-world news syndication
            
            if title_sim >= threshold:
                # Prefer the one with better source or newer timestamp
                if candidate.get("published") and existing.get("published"):
                    if candidate["published"] <= existing["published"]:
                        duplicate_found = True
                        break
                else:
                    duplicate_found = True
                    break
            
            # Also check content similarity for summaries
            if summary and existing.get("summary"):
                content_sim = _content_similarity(summary, existing["summary"])
                if content_sim > 0.75:  # High content similarity = likely duplicate
                    if candidate.get("published") and existing.get("published"):
                        if candidate["published"] <= existing["published"]:
                            duplicate_found = True
                            break
                    else:
                        duplicate_found = True
                        break
        
        if not duplicate_found:
            seen_fingerprints.add(fp)
            cleaned.append(candidate)
        else:
            filtered_count["semantic_dup"] += 1
    
    # Sort by recency (newest first)
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

    if verbose or filtered_count["relevance"] > 100 or filtered_count["semantic_dup"] > 0:
        logger.info(
            f"Aggregator filtering: empty={filtered_count['empty']}, "
            f"duplicate_urls={filtered_count['duplicate']}, "
            f"semantic_dup={filtered_count['semantic_dup']}, "
            f"age={filtered_count['age']}, relevance={filtered_count['relevance']}"
        )
    return cleaned
