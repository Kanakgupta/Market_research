"""GitHub pulse \u2014 commit + issue activity for tracked open-source wireless stacks."""
from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import requests

from .data_loader import _data_dir
import json

log = logging.getLogger(__name__)

GH_API = "https://api.github.com"
TIMEOUT = 15


def _headers() -> dict:
    h = {"Accept": "application/vnd.github+json", "User-Agent": "IoTNewsAgent/0.3"}
    tok = os.getenv("GITHUB_TOKEN", "").strip()
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def _repo_pulse(repo: dict, since: datetime) -> dict:
    owner, name = repo["owner"], repo["repo"]
    since_iso = since.isoformat().replace("+00:00", "Z")
    out = dict(repo, commits_30d=0, issues_open=0, prs_open=0, releases=[])
    try:
        # commits since
        r = requests.get(f"{GH_API}/repos/{owner}/{name}/commits",
                         params={"since": since_iso, "per_page": 100},
                         headers=_headers(), timeout=TIMEOUT)
        if r.status_code == 200:
            out["commits_30d"] = len(r.json())
        # open issues
        r = requests.get(f"{GH_API}/repos/{owner}/{name}",
                         headers=_headers(), timeout=TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            out["issues_open"] = data.get("open_issues_count", 0)
            out["stars"] = data.get("stargazers_count", 0)
            out["pushed_at"] = data.get("pushed_at", "")
        # latest releases
        r = requests.get(f"{GH_API}/repos/{owner}/{name}/releases",
                         params={"per_page": 3}, headers=_headers(), timeout=TIMEOUT)
        if r.status_code == 200:
            for rel in r.json()[:3]:
                out["releases"].append({
                    "tag": rel.get("tag_name", ""),
                    "name": rel.get("name", "") or rel.get("tag_name", ""),
                    "published_at": rel.get("published_at", ""),
                    "url": rel.get("html_url", ""),
                })
    except Exception as exc:
        log.warning("github pulse failed for %s/%s: %s", owner, name, exc)
    return out


def fetch_pulse() -> list[dict]:
    path = _data_dir() / "github_repos.json"
    if not path.exists():
        return []
    repos = json.loads(path.read_text(encoding="utf-8")).get("repos", [])
    since = datetime.now(timezone.utc) - timedelta(days=30)
    out: list[dict] = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = [ex.submit(_repo_pulse, r, since) for r in repos]
        for fut in as_completed(futures):
            out.append(fut.result())
    out.sort(key=lambda x: x.get("commits_30d", 0), reverse=True)
    return out
