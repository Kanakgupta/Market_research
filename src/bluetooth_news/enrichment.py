"""Fetch & cache article bodies; re-run vendor/customer/app classification on full text."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from .cache import get_body, put_body
from .classifier import detect_vendor, detect_customer, detect_application

log = logging.getLogger(__name__)

USER_AGENT = "IoTNewsAgent/0.3 (+research)"
TIMEOUT = 12
MAX_WORKERS = 8

try:
    import trafilatura  # type: ignore
    _HAS_TRAF = True
except ImportError:
    _HAS_TRAF = False


def _fetch_one(url: str) -> str:
    cached = get_body(url)
    if cached is not None:
        return cached
    body = ""
    if not _HAS_TRAF or not url.startswith(("http://", "https://")):
        put_body(url, body)
        return body
    try:
        downloaded = trafilatura.fetch_url(url, no_ssl=True)
        if downloaded:
            extracted = trafilatura.extract(downloaded, include_comments=False, include_tables=False) or ""
            body = extracted[:8000]  # cap
    except Exception as exc:  # broad: network + parse + ssl
        log.debug("body extract failed for %s: %s", url, exc)
    put_body(url, body)
    return body


def enrich(articles: list[dict], max_articles: int = 400) -> list[dict]:
    """Fetch bodies (parallel) and refine classification.

    Only the first `max_articles` (already filtered/sorted) get their bodies fetched.
    Beyond that we keep the title-based classification.
    """
    if not _HAS_TRAF:
        log.warning("trafilatura not installed; skipping body enrichment")
        return articles

    targets = articles[:max_articles]
    urls = [a["url"] for a in targets if a.get("url")]
    bodies: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(_fetch_one, u): u for u in urls}
        for fut in as_completed(futures):
            u = futures[fut]
            try:
                bodies[u] = fut.result()
            except Exception:
                bodies[u] = ""

    enriched = 0
    for a in targets:
        body = bodies.get(a.get("url", ""), "")
        if not body:
            continue
        # combine for richer classification
        full = f"{a.get('title','')} {a.get('summary','')} {body}"
        v, vr = detect_vendor(full)
        if v and not a.get("vendor"):
            a["vendor"], a["vendor_region"] = v, vr
            enriched += 1
        c = detect_customer(full)
        if c and not a.get("customer"):
            a["customer"] = c
            enriched += 1
        ap = detect_application(full)
        if ap and not a.get("application"):
            a["application"] = ap
            enriched += 1
        # store first 400 chars of body as richer summary if our summary is too thin
        if body and len(a.get("summary", "")) < 80:
            a["summary"] = body[:400]
    log.info("enrichment: refined %d fields across %d articles", enriched, len(targets))
    return articles
