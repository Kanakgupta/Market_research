"""Auto-update customers.json and competitors.json from live article corpus.

Called once per nightly run BEFORE HTML rendering. Uses Gemini to extract
newly-announced products / press releases from the last 90 days of articles,
then merges them into the static JSON files — never removes existing entries.

A local date-stamp cache (`data/auto_update_state.json`) prevents re-running
the LLM extraction more than once per calendar day.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_STATE_FILE = Path(__file__).resolve().parents[2] / "data" / "auto_update_state.json"
_CUSTOMERS_FILE = Path(__file__).resolve().parents[2] / "data" / "customers.json"
_COMPETITORS_FILE = Path(__file__).resolve().parents[2] / "data" / "competitors.json"

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _load_state() -> dict:
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_state(state: dict) -> None:
    _STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _normalise(text: str) -> str:
    """Lower-case, strip accents, collapse whitespace for fuzzy dedup."""
    nfkd = unicodedata.normalize("NFKD", text or "")
    ascii_ = nfkd.encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", ascii_).lower().strip()


def _resolve_api_key() -> str:
    import os
    key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
    if key:
        return key
    if os.name == "nt":
        try:
            import winreg  # type: ignore[attr-defined]
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as reg:
                for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
                    try:
                        val, _ = winreg.QueryValueEx(reg, var)
                        sval = str(val).strip()
                        if sval:
                            return sval
                    except OSError:
                        continue
        except Exception:
            pass
    return ""


def _gemini_chain() -> list[str]:
    import os
    names = (os.environ.get("GEMINI_MODELS") or os.environ.get("GEMINI_MODEL") or "").strip()
    chain = [n.strip() for n in names.split(",") if n.strip()] if names else []
    for m in ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-1.5-flash"]:
        if m not in chain:
            chain.append(m)
    return chain


def _call_gemini(prompt: str) -> dict | list | None:
    api_key = _resolve_api_key()
    if not api_key:
        log.warning("auto_update: no Gemini API key — skipping LLM extraction")
        return None
    try:
        import google.generativeai as genai
    except Exception as e:
        log.warning("auto_update: google-generativeai unavailable: %s", e)
        return None

    genai.configure(api_key=api_key)
    for model_name in _gemini_chain():
        try:
            model = genai.GenerativeModel(model_name)
            resp = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json", "temperature": 0.1},
            )
            text = (getattr(resp, "text", None) or "").strip()
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            # Accept both object and array at top level
            if not (text.startswith("{") or text.startswith("[")):
                m = re.search(r"[\[{].*[\]}]", text, flags=re.S)
                if not m:
                    continue
                text = m.group(0)
            result = json.loads(text)
            return result
        except Exception as e:
            log.debug("auto_update: model %s failed: %s", model_name, e)
            continue
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Article helpers
# ──────────────────────────────────────────────────────────────────────────────

def _articles_for(articles: list[dict], entity_name: str, days: int = 90) -> list[dict]:
    """Return articles tagged to entity_name within last `days` days."""
    cut = datetime.now(timezone.utc) - timedelta(days=days)
    out = []
    nl = _normalise(entity_name)
    for a in articles:
        pub = a.get("published")
        if pub and pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        if pub and pub < cut:
            continue
        # match customer or vendor or title
        if (
            _normalise(a.get("customer") or "") == nl
            or _normalise(a.get("vendor") or "") == nl
            or nl in _normalise(a.get("title") or "")
        ):
            out.append(a)
    return out[:80]  # cap to avoid token overflow


def _slim_article(a: dict) -> dict:
    pub = a.get("published")
    return {
        "title": a.get("title", ""),
        "url": a.get("url", ""),
        "date": pub.strftime("%Y-%m-%d") if pub else "",
        "summary": (a.get("summary") or "")[:200],
    }


# ──────────────────────────────────────────────────────────────────────────────
# Customer product extraction
# ──────────────────────────────────────────────────────────────────────────────

def _extract_customer_products(customer_name: str, articles: list[dict]) -> list[dict]:
    """Ask Gemini to extract new wireless product launches for one customer."""
    art_list = [_slim_article(a) for a in articles]
    if not art_list:
        return []

    prompt = f"""You are a product intelligence analyst.
Given the following news articles about {customer_name}, extract a list of
wireless/connectivity consumer or enterprise PRODUCTS that {customer_name} has
ANNOUNCED OR RELEASED. Focus on hardware product launches only (not software updates,
not rumours).

Return a JSON array. Each element:
{{
  "year": <integer YYYY>,
  "name": "<product name>",
  "tech": "<wireless technologies, e.g. Wi-Fi 7, BT 5.4, UWB>",
  "summary": "<brief 2-3 sentence overview of this product, detailing key features, specs, use-cases, context, or design wins mentioned in the source articles (about 120-180 characters)>",
  "url": "<the exact matching article url from the list of articles where this product was found>"
}}

Rules:
- Only include products with clear evidence in the articles below.
- year = year of announcement or release.
- tech = concise wireless spec string (comma-separated standards/versions).
- summary = informative 2-3 sentence summary.
- url = the exact same string as the "url" property of the article where this product was found. Do NOT invent a new url; it MUST match the article's url exactly.
- Return [] if no clear product launches are found.
- Return only the JSON array, no markdown, no explanation.

NEWS ARTICLES:
{json.dumps(art_list, ensure_ascii=False)}
"""
    result = _call_gemini(prompt)
    if not isinstance(result, list):
        return []
    out = []
    for item in result:
        if not isinstance(item, dict):
            continue
        try:
            yr = int(item.get("year") or 0)
        except (ValueError, TypeError):
            continue
        name = str(item.get("name") or "").strip()
        tech = str(item.get("tech") or "").strip()
        summary = str(item.get("summary") or "").strip()
        url = str(item.get("url") or "").strip()
        # Avoid redirect/search placeholders: keep only direct article URLs.
        if url and "news.google.com" in url and "/rss/articles/" in url:
            from urllib.parse import parse_qs, unquote, urlparse
            target = unquote((parse_qs(urlparse(url).query).get("url") or [""])[0]).strip()
            url = target if target.startswith(("http://", "https://")) else ""
        if yr >= 2021 and name:
            out.append({"year": yr, "name": name, "tech": tech, "summary": summary, "url": url})
    return out


def _merge_customer_products(existing: list[dict], new_items: list[dict]) -> tuple[list[dict], int, int]:
    """Merge new product entries into existing list. Returns (merged_list, added_count, updated_count)."""
    key_to_index = {(_normalise(p.get("name", "")), p.get("year")): i for i, p in enumerate(existing)}
    added = 0
    updated = 0
    result = [dict(p) for p in existing]
    for item in new_items:
        name = item.get("name", "")
        year = item.get("year")
        key = (_normalise(name), year)
        if key in key_to_index:
            idx = key_to_index[key]
            existing_item = result[idx]
            changed_item = False
            if not existing_item.get("summary") and item.get("summary"):
                existing_item["summary"] = item["summary"]
                changed_item = True
            if not existing_item.get("url") and item.get("url"):
                existing_item["url"] = item["url"]
                changed_item = True
            if not existing_item.get("tech") and item.get("tech"):
                existing_item["tech"] = item["tech"]
                changed_item = True
            if changed_item:
                updated += 1
        else:
            result.append(item)
            key_to_index[key] = len(result) - 1
            added += 1
    # Sort by year descending
    result.sort(key=lambda x: x.get("year", 0), reverse=True)
    return result, added, updated


# ──────────────────────────────────────────────────────────────────────────────
# Competitor press-release extraction
# ──────────────────────────────────────────────────────────────────────────────

def _extract_competitor_press(vendor_name: str, articles: list[dict]) -> list[dict]:
    """Ask Gemini to extract press release entries for a competitor."""
    art_list = [_slim_article(a) for a in articles]
    if not art_list:
        return []

    prompt = f"""You are a competitive intelligence analyst.
Given the following news articles about {vendor_name} (a wireless chip/semiconductor vendor),
extract PRESS RELEASE style announcements: product launches, financial results, partnerships,
new chips, SDK releases, customer wins.

Return a JSON array. Each element:
{{
  "title": "<concise press release headline>",
  "date": "<Mon YYYY, e.g. Apr 2026>",
  "url": "<url if available, else empty string>"
}}

Rules:
- Only include items with clear evidence in the articles.
- Return [] if nothing notable found.
- Return only the JSON array, no markdown.

NEWS ARTICLES:
{json.dumps(art_list, ensure_ascii=False)}
"""
    result = _call_gemini(prompt)
    if not isinstance(result, list):
        return []
    out = []
    for item in result:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        date_ = str(item.get("date") or "").strip()
        url_ = str(item.get("url") or "").strip()
        # Avoid redirect/search placeholders: keep only direct article URLs.
        if url_ and "news.google.com" in url_ and "/rss/articles/" in url_:
            from urllib.parse import parse_qs, unquote, urlparse
            target = unquote((parse_qs(urlparse(url_).query).get("url") or [""])[0]).strip()
            url_ = target if target.startswith(("http://", "https://")) else ""
        if title and date_:
            out.append({"title": title, "date": date_, "url": url_})
    return out[:6]


def _merge_press_releases(existing: list[dict], new_items: list[dict]) -> tuple[list[dict], int]:
    existing_titles = {_normalise(p.get("title", "")) for p in existing}
    added = 0
    result = list(existing)
    for item in new_items:
        key = _normalise(item["title"])
        if key not in existing_titles:
            result.append(item)
            existing_titles.add(key)
            added += 1
    # Sort newest first by date string (handles "Mon YYYY", "Mon DD, YYYY", "YYYY-MM-DD")
    _months = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
               "jul":7,"aug":8,"sep":9,"sept":9,"oct":10,"nov":11,"dec":12}
    def _key(p: dict) -> tuple[int, int, int]:
        s = str(p.get("date", "")).strip()
        if not s:
            return (0, 0, 0)
        m = re.match(r"^(\d{4})-(\d{1,2})(?:-(\d{1,2}))?", s)
        if m:
            return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0))
        m = re.match(r"^([A-Za-z]+)\.?\s+(?:(\d{1,2}),?\s+)?(\d{4})", s)
        if m:
            mo = _months.get(m.group(1).lower()[:4], 0) or _months.get(m.group(1).lower()[:3], 0)
            return (int(m.group(3)), mo, int(m.group(2) or 0))
        m = re.match(r"^(\d{4})$", s)
        if m:
            return (int(m.group(1)), 0, 0)
        return (0, 0, 0)
    result.sort(key=_key, reverse=True)
    return result[:10], added  # cap to 10 most recent


# ──────────────────────────────────────────────────────────────────────────────
# Public entry point
# ──────────────────────────────────────────────────────────────────────────────

def auto_update_from_articles(articles: list[dict], force: bool = False) -> dict:
    """Update customers.json + competitors.json with products/press from articles.

    Skips if already run today (unless force=True).
    Returns a summary dict with counts of changes made.
    """
    today = _today()
    state = _load_state()
    if not force and state.get("last_run_date") == today:
        log.info("auto_update: already ran today (%s) — skipping", today)
        return {"skipped": True, "reason": "already ran today"}

    summary: dict = {
        "customers_updated": 0,
        "customer_products_added": 0,
        "competitors_updated": 0,
        "competitor_press_added": 0,
        "errors": [],
    }

    # ── 1. Update customers.json ──────────────────────────────────────────────
    if not _CUSTOMERS_FILE.exists():
        log.warning("auto_update: customers.json not found")
    else:
        try:
            cdata = json.loads(_CUSTOMERS_FILE.read_text(encoding="utf-8"))
            customers = cdata.get("customers", [])
            changed = False
            for c in customers:
                name = c.get("name", "")
                arts = _articles_for(articles, name, days=90)
                if not arts:
                    continue
                log.info("auto_update: extracting products for %s (%d articles)", name, len(arts))
                new_items = _extract_customer_products(name, arts)
                if not new_items:
                    continue
                merged, added, updated = _merge_customer_products(c.get("recent_products", []), new_items)
                if added or updated:
                    c["recent_products"] = merged
                    summary["customers_updated"] += 1
                    summary["customer_products_added"] += added
                    changed = True
                    log.info("auto_update: %s — added %d, updated %d products", name, added, updated)
            if changed:
                _CUSTOMERS_FILE.write_text(
                    json.dumps(cdata, indent=2, ensure_ascii=False), encoding="utf-8"
                )
        except Exception as e:
            log.error("auto_update: customers error: %s", e)
            summary["errors"].append(f"customers: {e}")

    # ── 2. Update competitors.json press_releases ─────────────────────────────
    if not _COMPETITORS_FILE.exists():
        log.warning("auto_update: competitors.json not found")
    else:
        try:
            comp_data = json.loads(_COMPETITORS_FILE.read_text(encoding="utf-8"))
            competitors = comp_data.get("competitors", [])
            changed = False
            for comp in competitors:
                name = comp.get("vendor", "")
                arts = _articles_for(articles, name, days=90)
                if not arts:
                    continue
                log.info("auto_update: extracting press for %s (%d articles)", name, len(arts))
                new_press = _extract_competitor_press(name, arts)
                if not new_press:
                    continue
                existing_press = comp.get("press_releases", [])
                merged, added = _merge_press_releases(existing_press, new_press)
                if added:
                    comp["press_releases"] = merged
                    summary["competitors_updated"] += 1
                    summary["competitor_press_added"] += added
                    changed = True
                    log.info("auto_update: %s — added %d press releases", name, added)
            if changed:
                _COMPETITORS_FILE.write_text(
                    json.dumps(comp_data, indent=2, ensure_ascii=False), encoding="utf-8"
                )
        except Exception as e:
            log.error("auto_update: competitors error: %s", e)
            summary["errors"].append(f"competitors: {e}")

    # ── 3. Persist state ──────────────────────────────────────────────────────
    state["last_run_date"] = today
    state["last_run_summary"] = summary
    _save_state(state)

    log.info("auto_update: done — %s", summary)
    return summary
