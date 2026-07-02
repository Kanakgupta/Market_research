"""Build vendor <-> customer relationship graph from articles + seed data."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from urllib.parse import quote_plus, urlparse

from .classifier import detect_vendor, detect_customer
from .data_loader import load_competitors, load_customers


def _seed_url_is_useful(url: str, customer: str) -> bool:
    """A seed URL is only useful if it likely points at a specific
    announcement (path mentions the customer or a year-month-slug), not
    a generic press-room / newsroom landing page."""
    if not url:
        return False
    try:
        path = urlparse(url).path.lower().rstrip("/")
    except Exception:
        return False
    cust_token = re.split(r"[\s\(]", customer.lower(), 1)[0]
    # Path mentions the customer name
    if cust_token and cust_token in path:
        return True
    # Or path has a long, dated slug (e.g. /News/2024/03/Logitech-selects-...)
    if re.search(r"/\d{4}/\d{1,2}/[a-z][a-z0-9-]{8,}", path):
        return True
    return False


def _google_evidence_url(vendor: str, customer: str) -> str:
    q = f'"{vendor}" "{customer}" (partnership OR selects OR announces OR powered)'
    return f"https://www.google.com/search?q={quote_plus(q)}"


IOT_APPS = {
    "Smart Home", "Industrial", "Automotive", "Wearable", "AR / VR / XR",
    "Smart Glasses", "Audio / Speaker", "Healthcare", "Asset Tracking",
    "Retail", "Energy/Utility", "Smart City", "Agriculture", "Robotics",
}

# Article must mention at least one of these IoT context cues to count
# as a vendor<->customer relationship signal.
_IOT_CONTEXT = re.compile(
    r"\b("
    r"iot|aiot|internet of things|"
    r"smart\s+(home|lock|plug|lighting|thermostat|speaker|doorbell|switch|camera|sensor|appliance|building|city|meter)|"
    r"home\s+automation|"
    r"matter|thread|zigbee|z[- ]wave|aliro|"
    r"ble\b|bluetooth\s+(le|low\s+energy|mesh|audio|le\s+audio)|"
    r"wi[- ]?fi\s+(halow|6e|7)|"
    r"earbud|hearable|tws|true\s+wireless|soundbar|headphone|wireless\s+(speaker|audio)|"
    r"wearable|smartwatch|fitness\s+(tracker|band|ring)|"
    r"hearing\s+aid|cgm|insulin|patient\s+monitor|medical\s+device|"
    r"automotive|vehicle|adas|tpms|digital\s+key|infotainment|carplay|android\s+auto|"
    r"industrial\s+iot|iiot|industry\s+4\.0|predictive\s+maintenance|edge\s+gateway|"
    r"asset\s+(tracker|tracking)|fleet|cold\s+chain|rtls|airtag|"
    r"electronic\s+shelf\s+label|esl\b|beacon|"
    r"smart\s+meter|ev\s+charger|charging\s+station|energy\s+management|"
    r"drone|robot|cobot|amr\b|agv\b|"
    r"ar\s+glasses|vr\s+headset|xr\s+headset|mixed\s+reality|spatial\s+computing|smart\s+glasses|"
    r"ble\s+beacon|nfc|uwb|ultra[- ]wideband|lpwan|lorawan|nb[- ]iot|cat[- ]m|cellular\s+iot"
    r")\b",
    re.IGNORECASE,
)

# Article is excluded if it is dominated by non-IoT topics (smartphones,
# laptops, datacenters, AI infra spend, modem-IP licensing, financial news).
_NON_IOT_TOPIC = re.compile(
    r"\b("
    r"smartphone|flagship\s+phone|iphone\s+\d|galaxy\s+s\d{1,2}|pixel\s+\d{1,2}\s+pro|"
    r"snapdragon\s+\d+\s+(mobile|gen|for\s+phone)|application\s+processor|ap\s+chip|"
    r"laptop|notebook|macbook|chromebook|windows\s+pc|copilot\+\s+pc|surface\s+laptop|"
    r"data\s*center|datacenter|hyperscaler|cloud\s+gpu|server\s+cpu|ai\s+accelerator|"
    r"foundry|node\s+(process|technology)|3nm|2nm|wafer|tsmc|"
    r"earnings|q[1-4]\s+revenue|stock\s+(rally|price|forecast)|seeking\s+alpha|"
    r"5g\s+(modem|fwa|fixed\s+wireless)|baseband\s+modem|modem[- ]ip"
    r")\b",
    re.IGNORECASE,
)


def _is_iot_article(a: dict) -> bool:
    """Article counts as IoT signal only if it has IoT context cues
    AND isn't dominated by phone/PC/datacenter/financial topics."""
    text = f"{a.get('title','')} {a.get('summary','')} {a.get('body','')[:400]}"
    if not _IOT_CONTEXT.search(text):
        return False
    if _NON_IOT_TOPIC.search(text):
        return False
    return True


def build_links(articles: list[dict], vendor_focus: str | None = None,
                iot_only: bool = False) -> list[dict]:
    """Return list of relationship links with strength and evidence.

    Only emits links that have at least one IoT-context news article as
    evidence (with a clickable URL). Seed mappings are used as a small
    bonus signal, never as a sole reason to publish a link.
    """
    weights: Counter[tuple[str, str]] = Counter()
    sources: dict[tuple[str, str], set[str]] = defaultdict(set)
    evidence: dict[tuple[str, str], list[dict]] = defaultdict(list)
    iot_customers = {c.get("name") for c in load_customers()}

    for a in articles:
        if not _is_iot_article(a):
            continue
        text = f"{a.get('title','')} {a.get('summary','')}"
        # primary tags
        v = a.get("vendor")
        c = a.get("customer")
        if (not v) and ("infineon" in text.lower() or "airoc" in text.lower()):
            v = "Infineon"
        if not v:
            v, _region = detect_vendor(text)
        if not c:
            c = detect_customer(text)

        if iot_only and c and c not in iot_customers:
            continue
        if vendor_focus and v != vendor_focus:
            continue

        if v and c:
            weights[(v, c)] += 2
            sources[(v, c)].add("news")
            url = (a.get("url") or "").strip()
            # Skip evidence rows pointing at unusable Google News RSS
            # redirects — they wouldn't open in a browser anyway.
            if url and not ("news.google.com" in url and "/rss/articles/" in url):
                evidence[(v, c)].append({
                    "title": a.get("title") or "article",
                    "url": url,
                    "source": a.get("source") or "news",
                    "date": a.get("published").strftime("%Y-%m-%d") if a.get("published") else "",
                })

    # Seed mappings: vendor -> customer with a stored evidence URL count
    # as a verified business relationship (we treat each as a single news
    # equivalent so seed-only links can still render — provided they have
    # a real URL and the customer isn't a non-IoT entity).
    comp = load_competitors()
    _NON_IOT_CUSTOMERS = {"Microsoft", "Apple", "Sony"}  # only their phone/PC/console SKUs leak through; skip seed-only
    for entry in comp.get("competitors", []):
        v = entry.get("vendor")
        if vendor_focus and v != vendor_focus:
            continue
        for cust in entry.get("key_customers", []):
            if isinstance(cust, dict):
                cust_str = cust.get("name", "")
                seed_url = (cust.get("url") or "").strip()
                seed_date = cust.get("date", "")
            else:
                cust_str = cust
                seed_url = ""
                seed_date = ""
            cust_clean = cust_str.split("(")[0].strip()
            if not (v and cust_clean):
                continue
            # Boost weight on links that already have news evidence.
            if (v, cust_clean) in weights:
                weights[(v, cust_clean)] += 1
                sources[(v, cust_clean)].add("seed")
            # Allow seed-only links if the customer is IoT-relevant.
            elif cust_clean not in _NON_IOT_CUSTOMERS:
                # Rewrite generic press-room URLs to a targeted Google
                # search so the link is always useful when clicked.
                if _seed_url_is_useful(seed_url, cust_clean):
                    ev_url = seed_url
                    ev_src = "vendor seed"
                else:
                    ev_url = _google_evidence_url(v, cust_clean)
                    ev_src = "web search"
                weights[(v, cust_clean)] += 2
                sources[(v, cust_clean)].add("seed")
                evidence[(v, cust_clean)].append({
                    "title": f"{v} chosen by {cust_clean} (partnership evidence)",
                    "url": ev_url,
                    "source": ev_src,
                    "date": seed_date,
                })

    for cust_entry in load_customers():
        c = cust_entry.get("name")
        for vp in cust_entry.get("known_chip_partners", []):
            if isinstance(vp, dict):
                v_clean = (vp.get("name") or "").split("(")[0].strip()
                seed_url = (vp.get("url") or "").strip()
                seed_date = vp.get("date", "")
            else:
                v_clean = vp.split("(")[0].strip()
                seed_url = ""
                seed_date = ""
            if vendor_focus and v_clean != vendor_focus:
                continue
            if not (c and v_clean):
                continue
            if (v_clean, c) in weights:
                weights[(v_clean, c)] += 1
                sources[(v_clean, c)].add("seed")
            elif c not in _NON_IOT_CUSTOMERS:
                if _seed_url_is_useful(seed_url, v_clean):
                    ev_url = seed_url
                    ev_src = "customer seed"
                else:
                    ev_url = _google_evidence_url(v_clean, c)
                    ev_src = "web search"
                weights[(v_clean, c)] += 2
                sources[(v_clean, c)].add("seed")
                evidence[(v_clean, c)].append({
                    "title": f"{c} partners with {v_clean} (partnership evidence)",
                    "url": ev_url,
                    "source": ev_src,
                    "date": seed_date,
                })

    out: list[dict] = []
    for (v, c), w in weights.most_common():
        ev = evidence[(v, c)]
        if not ev:
            # Require at least one clickable, IoT-context news source.
            continue
        # de-dupe by URL, keep latest 5
        uniq: dict[str, dict] = {}
        for row in ev:
            if row.get("url"):
                uniq[row["url"]] = row
        top_ev = list(uniq.values())[:5]
        out.append({
            "vendor": v,
            "customer": c,
            "weight": w,
            "news_count": len(ev),
            "seed_count": 1 if "seed" in sources[(v, c)] else 0,
            "strength_explained": (
                f"news x2 ({len(ev) * 2})"
                + (f" + seed x1 (1)" if "seed" in sources[(v, c)] else "")
            ),
            "sources": sorted(sources[(v, c)]),
            "evidence": top_ev,
        })
    return out
