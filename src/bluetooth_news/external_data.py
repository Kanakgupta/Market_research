"""USPTO patent radar + SEC EDGAR filings tracker."""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import requests

from .data_loader import _data_dir

log = logging.getLogger(__name__)
TIMEOUT = 20
UA = "IoTNewsAgent/0.3 research"

PATENTSVIEW = "https://api.patentsview.org/patents/query"
EDGAR_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"


def _load_external() -> dict:
    p = _data_dir() / "external.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------- USPTO
def fetch_patents(months: int = 6, per_assignee: int = 5) -> list[dict]:
    """Use USPTO PatentsView API to get recent wireless patents per assignee.

    Filter to patents whose title/abstract mentions wireless keywords.
    """
    ext = _load_external()
    assignees = ext.get("patent_assignees", [])
    if not assignees:
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=months * 31)).strftime("%Y-%m-%d")
    keywords = ["wireless", "bluetooth", "wi-fi", "wifi", "802.11", "802.15", "thread", "matter"]

    def _query(assignee: str) -> list[dict]:
        q = {
            "_and": [
                {"_gte": {"patent_date": cutoff}},
                {"_text_phrase": {"assignee_organization": assignee}},
                {"_or": [{"_text_phrase": {"patent_title": k}} for k in keywords]},
            ]
        }
        params = {
            "q": json.dumps(q),
            "f": json.dumps(["patent_number", "patent_title", "patent_date", "assignee_organization"]),
            "o": json.dumps({"per_page": per_assignee, "sort": [{"patent_date": "desc"}]}),
        }
        try:
            r = requests.get(PATENTSVIEW, params=params, timeout=TIMEOUT, headers={"User-Agent": UA})
            if r.status_code != 200:
                return []
            data = r.json()
            return [
                {
                    "vendor": assignee,
                    "number": p.get("patent_number"),
                    "title": p.get("patent_title", "").strip(),
                    "date": p.get("patent_date", ""),
                    "url": f"https://patents.google.com/patent/US{p.get('patent_number')}",
                }
                for p in (data.get("patents") or [])
            ]
        except Exception as exc:
            log.warning("PatentsView failed for %s: %s", assignee, exc)
            return []

    out: list[dict] = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(_query, a) for a in assignees]
        for fut in as_completed(futures):
            out.extend(fut.result())
    out.sort(key=lambda x: x.get("date", ""), reverse=True)
    return out


# ---------------------------------------------------------- EDGAR
def fetch_edgar() -> list[dict]:
    """Fetch recent SEC filings (last 90 days) for tracked tickers."""
    ext = _load_external()
    companies = ext.get("edgar_companies", [])
    cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")
    relevant_forms = {"10-K", "10-Q", "8-K", "DEF 14A", "S-1"}

    def _one(comp: dict) -> list[dict]:
        cik = comp["cik"].zfill(10)
        url = EDGAR_SUBMISSIONS.format(cik=cik)
        try:
            r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "IoTAgent contact@example.com"})
            if r.status_code != 200:
                return []
            data = r.json()
            recent = data.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            accessions = recent.get("accessionNumber", [])
            primary_docs = recent.get("primaryDocument", [])
            out: list[dict] = []
            for form, date, acc, doc in zip(forms, dates, accessions, primary_docs):
                if date < cutoff:
                    continue
                if form not in relevant_forms:
                    continue
                acc_clean = acc.replace("-", "")
                doc_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_clean}/{doc}"
                out.append({
                    "vendor": comp["vendor"],
                    "ticker": comp["ticker"],
                    "form": form,
                    "date": date,
                    "url": doc_url,
                })
            return out
        except Exception as exc:
            log.warning("EDGAR failed for %s: %s", comp.get("vendor"), exc)
            return []

    out: list[dict] = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(_one, c) for c in companies]
        for fut in as_completed(futures):
            out.extend(fut.result())
    out.sort(key=lambda x: x.get("date", ""), reverse=True)
    return out
