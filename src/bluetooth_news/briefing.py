"""Assemble briefing input for LLM and read back any prior synthesis result.

Workflow:
1. Each run writes `data/briefing_input.json` and `data/roadmap_input.json`
   containing structured snapshots (top headlines, vendor moves, competitor
   matrix, AIROC SKUs, standards, events, GitHub pulse).
2. The user can paste either file into Copilot Chat ("synthesize this") and
   write the response back to `data/briefing_output.json` /
   `data/roadmap_output.json`.
3. The next site build picks up those output files and renders the Briefing /
   Roadmap pages.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .data_loader import _data_dir, load_customers, load_competitors


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _recent(articles: list[dict], days: int = 7) -> list[dict]:
    cut = datetime.now(timezone.utc) - timedelta(days=days)
    out: list[dict] = []
    for a in articles:
        p = a.get("published")
        if p and p.tzinfo is None:
            p = p.replace(tzinfo=timezone.utc)
        if p and p >= cut:
            out.append(a)
    return out


def write_inputs(articles: list[dict], github_pulse: list[dict],
                 patents: list[dict], filings: list[dict]) -> None:
    """Write briefing_input.json and roadmap_input.json."""
    dd = _data_dir()
    dd.mkdir(parents=True, exist_ok=True)

    arts_7d = _recent(articles, 7)
    arts_30d = _recent(articles, 30)

    def _slim(a: dict) -> dict:
        return {
            "title": a.get("title"),
            "url": a.get("url"),
            "source": a.get("source"),
            "date": a.get("published").strftime("%Y-%m-%d") if a.get("published") else "",
            "vendor": a.get("vendor"),
            "customer": a.get("customer"),
            "application": a.get("application"),
            "buckets": a.get("buckets") or [],
            "summary": (a.get("summary") or "")[:300],
        }

    vendor_30d = Counter(a["vendor"] for a in arts_30d if a.get("vendor"))
    customer_30d = Counter(a["customer"] for a in arts_30d if a.get("customer"))

    competitors = load_competitors()
    customers = load_customers()

    standards_path = dd / "standards.json"
    events_path = dd / "events.json"
    standards = json.loads(standards_path.read_text(encoding="utf-8")) if standards_path.exists() else {}
    events = json.loads(events_path.read_text(encoding="utf-8")) if events_path.exists() else {}

    briefing_input = {
        "generated_at": _now_iso(),
        "instructions_for_llm": (
            "You are a market analyst tracking the IoT wireless chip space for an "
            "Infineon AIROC product manager. Read the inputs below and produce a JSON "
            "object with these keys: "
            "themes (list of {title, narrative, sources:[urls]}), "
            "competitor_moves (list of {vendor, action, implication, sources:[urls]}), "
            "customer_signals (list of {customer, signal, implication}), "
            "what_changed_vs_last_week (string), "
            "watch_list (list of {topic, why}). "
            "Be concise, factual, cite urls from the inputs. Save the result to "
            "data/briefing_output.json."
        ),
        "headlines_last_7d": [_slim(a) for a in arts_7d[:40]],
        "vendor_news_30d": dict(vendor_30d.most_common(25)),
        "customer_news_30d": dict(customer_30d.most_common(25)),
        "github_pulse": github_pulse,
        "recent_patents": patents[:60],
        "sec_filings_90d": filings[:60],
        "tracked_competitors": competitors.get("competitors", []),
        "tracked_customers_summary": [
            {"name": c["name"], "category": c.get("category"), "wireless_focus": c.get("wireless_focus", [])}
            for c in customers
        ],
        "standards_landscape": standards.get("standards", []),
        "upcoming_events": events.get("events", []),
    }

    airoc = competitors.get("anchor", {})
    roadmap_input = {
        "generated_at": _now_iso(),
        "instructions_for_llm": (
            "You are a chip product strategist for Infineon AIROC. Given the current "
            "AIROC SKUs, the competitor matrix (strengths/weaknesses vs AIROC), "
            "in-flight standards, customer roadmap signals, recent news momentum, and "
            "GitHub stack activity, produce a JSON with: "
            "feature_gaps (list of {gap, evidence:[urls/notes], priority: 'high|med|low', target_horizon}), "
            "sku_recommendations (list of {sku_concept, target_apps, key_features, "
            "competitive_response_to:[vendors]}), "
            "software_priorities (list of {area, justification, target_horizon}), "
            "partnership_targets (list of {partner, rationale}), "
            "risks (list of {risk, mitigation}). "
            "Be concrete and tie each item to evidence. Save result to "
            "data/roadmap_output.json."
        ),
        "airoc_anchor": airoc,
        "competitor_matrix": competitors.get("competitors", []),
        "customer_roadmap_signals": [
            {"name": c["name"], "signals": c.get("roadmap_signals", []),
             "known_chip_partners": c.get("known_chip_partners", [])}
            for c in customers
        ],
        "vendor_news_momentum_30d": dict(vendor_30d.most_common(25)),
        "standards_in_flight": standards.get("standards", []),
        "github_stack_activity": github_pulse,
        "recent_competitor_patents": patents[:40],
    }

    (dd / "briefing_input.json").write_text(
        json.dumps(briefing_input, indent=2, default=str), encoding="utf-8"
    )
    (dd / "roadmap_input.json").write_text(
        json.dumps(roadmap_input, indent=2, default=str), encoding="utf-8"
    )


def load_outputs() -> tuple[dict, dict]:
    """Load briefing_output.json and roadmap_output.json if present."""
    dd = _data_dir()
    b_path = dd / "briefing_output.json"
    r_path = dd / "roadmap_output.json"
    briefing = json.loads(b_path.read_text(encoding="utf-8")) if b_path.exists() else {}
    roadmap = json.loads(r_path.read_text(encoding="utf-8")) if r_path.exists() else {}
    return briefing, roadmap


def _extract_json_object(text: str) -> dict:
    """Parse model output into a JSON object, tolerating fences/preamble."""
    t = (text or "").strip()
    if not t:
        raise ValueError("empty model output")
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    if not t.startswith("{"):
        m = re.search(r"\{.*\}", t, flags=re.S)
        if not m:
            raise ValueError("no JSON object found in model output")
        t = m.group(0)
    data = json.loads(t)
    if not isinstance(data, dict):
        raise ValueError("model output must be a JSON object")
    return data


def _gemini_chain() -> list[str]:
    names = (os.environ.get("GEMINI_MODELS") or os.environ.get("GEMINI_MODEL") or "").strip()
    if names:
        chain = [n.strip() for n in names.split(",") if n.strip()]
    else:
        chain = []
    defaults = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-1.5-flash"]
    for name in defaults:
        if name not in chain:
            chain.append(name)
    return chain


def _resolve_api_key() -> str:
    """Resolve Gemini key from process env or Windows user env registry."""
    key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
    if key:
        return key

    # VS Code terminals can miss freshly set user env vars; fall back to registry.
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


def _synthesize_one(input_path: Path, output_path: Path) -> tuple[bool, str]:
    api_key = _resolve_api_key()
    if not api_key:
        return False, "missing GEMINI_API_KEY/GOOGLE_API_KEY"
    if not input_path.exists():
        return False, f"missing input {input_path.name}"

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    instruction = payload.get("instructions_for_llm") or "Generate JSON from this payload."

    prompt = (
        "You are a strict JSON generator. Return only valid JSON object with no markdown.\n\n"
        + str(instruction)
        + "\n\nINPUT JSON:\n"
        + json.dumps(payload, ensure_ascii=False)
    )

    try:
        import google.generativeai as genai
    except Exception as e:  # noqa: BLE001
        return False, f"google-generativeai import failed: {e}"

    genai.configure(api_key=api_key)
    last_err = "unknown"
    for name in _gemini_chain():
        try:
            model = genai.GenerativeModel(name)
            resp = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json", "temperature": 0.2},
            )
            text = (getattr(resp, "text", None) or "").strip()
            data = _extract_json_object(text)
            output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            return True, f"generated with {name}"
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            continue
    return False, last_err


def synthesize_outputs(force: bool = False) -> dict:
    """Generate briefing_output/roadmap_output from input snapshots using Gemini.

    Returns a status dict with per-file results. If force=False, existing output
    files are preserved.
    """
    dd = _data_dir()
    tasks = [
        (dd / "briefing_input.json", dd / "briefing_output.json", "briefing"),
        (dd / "roadmap_input.json", dd / "roadmap_output.json", "roadmap"),
    ]

    out: dict = {"ok": True, "files": {}}
    for in_path, out_path, label in tasks:
        if out_path.exists() and not force:
            out["files"][label] = {"ok": True, "status": "kept existing output"}
            continue
        ok, status = _synthesize_one(in_path, out_path)
        out["files"][label] = {"ok": ok, "status": status}
        if not ok:
            out["ok"] = False
    return out
