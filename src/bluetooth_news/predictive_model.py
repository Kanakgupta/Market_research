"""Heuristic predictive model for probable customer product launches.

This model combines:
- roadmap signals from customer profiles
- wireless focus tags
- recent product cadence
- recent news volume and keyword evidence

It returns explainable predictions with confidence and rationale.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone, timedelta
import math
import re

ALLOWED_APPS = [
    "Smart Home",
    "Industrial",
    "Wearable",
    "AR / VR / XR",
    "Smart Glasses",
    "Audio / Speaker",
]

APP_KEYWORDS: dict[str, list[str]] = {
    "Smart Home": ["matter", "thread", "smart home", "home hub", "doorbell", "camera", "thermostat", "zigbee"],
    "Industrial": ["industrial", "iiot", "edge", "factory", "gateway", "predictive maintenance"],
    "Wearable": ["wearable", "watch", "tracker", "ring", "fitness", "health"],
    "AR / VR / XR": ["xr", "ar", "vr", "spatial", "headset", "quest", "vision"],
    "Smart Glasses": ["smart glasses", "ar glasses", "glasses", "ray-ban", "orion"],
    "Audio / Speaker": ["earbuds", "headphone", "speaker", "soundbar", "auracast", "le audio", "audio"],
}

APP_PRODUCT_TEMPLATES: dict[str, list[str]] = {
    "Smart Home": ["{customer} Matter hub refresh", "{customer} next-gen smart camera lineup"],
    "Industrial": ["{customer} industrial IoT edge module", "{customer} enterprise wireless sensor platform"],
    "Wearable": ["{customer} health wearable refresh", "{customer} low-power BLE tracker family"],
    "AR / VR / XR": ["{customer} XR headset generation", "{customer} spatial-computing accessory"],
    "Smart Glasses": ["{customer} smart glasses generation", "{customer} AI glasses companion"],
    "Audio / Speaker": ["{customer} LE Audio earbuds refresh", "{customer} Auracast-ready speaker lineup"],
}

FEATURE_HINTS: dict[str, list[str]] = {
    "matter": ["Matter multi-admin", "Thread border router", "faster onboarding"],
    "thread": ["Thread 1.4 support", "lower standby power", "mesh reliability"],
    "wifi 7": ["Wi-Fi 7 with MLO", "lower latency QoS", "high-throughput backhaul"],
    "wifi 8": ["Wi-Fi 8 readiness", "coexistence improvements"],
    "bluetooth": ["Bluetooth LE 5.4+", "secure pairing hardening"],
    "le audio": ["LE Audio broadcast", "Auracast support", "low-latency audio path"],
    "auracast": ["public broadcast receive", "multi-stream audio", "hearing-accessibility mode"],
    "uwb": ["precision ranging", "secure proximity unlock"],
    "sidewalk": ["long-range low-power telemetry", "neighborhood network compatibility"],
}


def _safe_text(x: object) -> str:
    return str(x or "").lower()


def _news_for_customer(articles: list[dict], customer: str) -> list[dict]:
    return [a for a in articles if a.get("customer") == customer]


def _hits(texts: list[str], keywords: list[str]) -> int:
    blob = " ".join(texts)
    return sum(1 for k in keywords if re.search(r"\b" + re.escape(k) + r"\b", blob, re.I))


def _product_cadence_score(customer: dict) -> float:
    years = sorted({int(p.get("year", 0)) for p in customer.get("recent_products", []) if p.get("year")})
    if not years:
        return 0.0
    now = datetime.now(timezone.utc).year
    recency = max(0.0, 1.0 - (now - max(years)) / 5.0)
    continuity = min(1.0, len(years) / 4.0)
    return 10.0 * (0.6 * recency + 0.4 * continuity)


def _feature_candidates(customer: dict, texts: list[str], app: str) -> list[str]:
    features: list[str] = []
    wf = [_safe_text(w) for w in customer.get("wireless_focus", [])]
    corpus = " ".join(texts + wf)

    for k, vals in FEATURE_HINTS.items():
        if k in corpus:
            features.extend(vals)

    # App-specific defaults to ensure actionable outputs.
    if app == "Smart Home":
        features.extend(["Matter certification", "Thread + BLE commissioning"])
    elif app == "Audio / Speaker":
        features.extend(["Auracast interoperability", "multipoint reliability"])
    elif app == "Wearable":
        features.extend(["ultra-low power BLE", "improved sensor fusion"])
    elif app == "AR / VR / XR":
        features.extend(["low-latency link budget", "spatial accessory pairing"])
    elif app == "Smart Glasses":
        features.extend(["all-day battery profile", "hands-free BLE peripherals"])
    elif app == "Industrial":
        features.extend(["rugged wireless stack", "secure OTA fleet updates"])

    uniq: list[str] = []
    seen = set()
    for f in features:
        if f not in seen:
            uniq.append(f)
            seen.add(f)
    return uniq[:6]


def predict_customer_releases(customers: list[dict], articles: list[dict],
                              mode: str = "balanced") -> list[dict]:
    """Return probable launches table rows with explainable confidence.

    Excludes automotive customers and keeps scope to selected IoT applications.
    """
    now = datetime.now(timezone.utc)
    cutoff_180 = now - timedelta(days=180)
    out: list[dict] = []

    mode_min_conf = {
        "aggressive": 50,
        "balanced": 60,
        "conservative": 70,
    }
    min_conf = mode_min_conf.get(mode, 60)

    for c in customers:
        category = _safe_text(c.get("category"))
        if "automotive" in category:
            continue

        name = c.get("name")
        if not name:
            continue

        c_articles = _news_for_customer(articles, name)
        app_counts = Counter(a.get("application") for a in c_articles if a.get("application") in ALLOWED_APPS)

        texts = []
        texts.extend(_safe_text(x) for x in c.get("roadmap_signals", []))
        texts.extend(_safe_text(x.get("name")) for x in c.get("recent_products", []))
        texts.extend(_safe_text(a.get("title")) for a in c_articles[:80])
        texts.extend(_safe_text(a.get("summary")) for a in c_articles[:80])

        app_scores: dict[str, float] = {}
        for app in ALLOWED_APPS:
            keyword_hits = _hits(texts, APP_KEYWORDS[app])
            article_bias = app_counts.get(app, 0)
            app_scores[app] = keyword_hits * 2.0 + min(8.0, article_bias)

        # Choose top application with enough signal.
        ranked = sorted(app_scores.items(), key=lambda x: x[1], reverse=True)
        if not ranked or ranked[0][1] < 2.0:
            continue

        top_app = ranked[0][0]
        top_score = ranked[0][1]

        product_templates = APP_PRODUCT_TEMPLATES[top_app]
        product_name = product_templates[0].format(customer=name)

        # Confidence model (0-100) with explainability.
        roadmap_hits = _hits([_safe_text(x) for x in c.get("roadmap_signals", [])], APP_KEYWORDS[top_app])
        recent_news = 0
        older_news = 0
        source_set = set()
        for a in c_articles:
            p = a.get("published")
            source_set.add(a.get("source") or "news")
            if p is None:
                continue
            if p.tzinfo is None:
                p = p.replace(tzinfo=timezone.utc)
            if p >= cutoff_180:
                recent_news += 1
            elif p >= now - timedelta(days=360):
                older_news += 1

        trend_boost = 0.0
        if recent_news > older_news:
            trend_boost = min(6.0, (recent_news - older_news) * 0.5)
        source_diversity = min(6.0, len(source_set) * 1.5)

        news_score = min(20.0, 4.0 * math.log1p(recent_news))
        app_score = min(40.0, top_score * 3.2)
        roadmap_score = min(20.0, roadmap_hits * 5.0)
        cadence_score = _product_cadence_score(c)
        partner_score = min(10.0, len(c.get("known_chip_partners", [])) * 2.0)

        confidence = int(max(25.0, min(95.0, app_score + roadmap_score + news_score + cadence_score + partner_score + trend_boost + source_diversity)))
        if confidence >= 80:
            conf_label = "High"
        elif confidence >= 60:
            conf_label = "Medium"
        else:
            conf_label = "Low"

        features = _feature_candidates(c, texts, top_app)

        evidence_bits: list[str] = []
        evidence_bits.append(f"app signal={top_app} (score {top_score:.1f})")
        evidence_bits.append(f"roadmap keyword hits={roadmap_hits}")
        evidence_bits.append(f"customer news in last 180d={recent_news}")
        evidence_bits.append(f"known chip partners={len(c.get('known_chip_partners', []))}")
        if c.get("roadmap_signals"):
            evidence_bits.append(f"roadmap cue: {c['roadmap_signals'][0]}")

        row = {
            "customer": name,
            "application": top_app,
            "probable_product": product_name,
            "expected_features": features,
            "confidence": confidence,
            "confidence_label": conf_label,
            "based_on": evidence_bits,
        }
        if row["confidence"] >= min_conf:
            out.append(row)

    out.sort(key=lambda r: r["confidence"], reverse=True)
    return out
