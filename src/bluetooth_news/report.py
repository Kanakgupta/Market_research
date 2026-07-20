"""Render multi-page IoT Wireless intelligence site."""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

from jinja2 import Environment, BaseLoader, select_autoescape

from .classifier import (
    vendors_by_region, all_customers, all_applications, REGION_LABELS,
)
from .sources import BUCKETS
from .data_loader import load_customers, load_competitors
from .relationships import build_links
from .predictive_model import predict_customer_releases
from .tech_tutorials import TECH_TUTORIALS

PDT = timezone(timedelta(hours=-7), name="PDT")

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

def _parse_press_date(s: str) -> tuple[int, int, int]:
    """Parse loose date strings ("Apr 2026", "Apr 12, 2026", "2026-04-12").

    Returns (year, month, day) for sorting; unparseable -> (0, 0, 0).
    """
    if not s:
        return (0, 0, 0)
    s = s.strip()
    # ISO yyyy-mm-dd
    m = re.match(r"^(\d{4})-(\d{1,2})(?:-(\d{1,2}))?", s)
    if m:
        y = int(m.group(1)); mo = int(m.group(2)); d = int(m.group(3) or 0)
        return (y, mo, d)
    # Mon [DD,] YYYY
    m = re.match(r"^([A-Za-z]+)\.?\s+(?:(\d{1,2}),?\s+)?(\d{4})", s)
    if m:
        mo = _MONTHS.get(m.group(1).lower()[:4], 0) or _MONTHS.get(m.group(1).lower()[:3], 0)
        d = int(m.group(2) or 0)
        y = int(m.group(3))
        return (y, mo, d)
    # YYYY only
    m = re.match(r"^(\d{4})$", s)
    if m:
        return (int(m.group(1)), 0, 0)
    return (0, 0, 0)


def _is_placeholder_search_url(url: str) -> bool:
    if not url:
        return True
    u = url.strip().lower()
    return (
        u.startswith("https://www.google.com/search?")
        or u.startswith("http://www.google.com/search?")
        or u.startswith("https://google.com/search?")
        or u.startswith("http://google.com/search?")
        or u.startswith("https://www.bing.com/search?")
        or u.startswith("http://www.bing.com/search?")
        or ("news.google.com" in u and "/rss/articles/" in u)
    )


def _norm_title(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"\bpress\s+release\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _resolve_direct_press_url(
    vendor: str,
    pr_title: str,
    vendor_news: dict[str, list[dict]],
) -> str:
    target = _norm_title(pr_title)
    if not target:
        return ""

    best_url = ""
    best_score = 0
    target_tokens = set(target.split())
    for item in vendor_news.get(vendor, []):
        cand_url = (item.get("url") or "").strip()
        if not cand_url or _is_placeholder_search_url(cand_url):
            continue
        cand_title = _norm_title(item.get("title") or "")
        if not cand_title:
            continue

        score = 0
        if cand_title == target:
            score = 100
        elif target in cand_title or cand_title in target:
            score = 85
        else:
            overlap = len(target_tokens & set(cand_title.split()))
            # Require meaningful overlap to avoid mismatched links.
            if overlap >= 5:
                score = 50 + overlap

        if score > best_score:
            best_score = score
            best_url = cand_url

    return best_url

# ---------------------------------------------------------------- shared
_BASE_CSS = """
:root { color-scheme: light;
  --bg:#f7f9fc; --card:#fff; --border:#e4e8ee; --text:#1a1f2c; --muted:#6b7280;
  --accent:#2563eb; --hover:#f1f5fb;
  --chip-bg:#eef2ff; --chip-fg:#3730a3;
  --vendor-bg:#fef3c7; --vendor-fg:#92400e;
  --cust-bg:#fce7f3; --cust-fg:#9d174d;
  --app-bg:#dcfce7; --app-fg:#166534;
}
* { box-sizing:border-box; }
body { margin:0; font-family:-apple-system,Segoe UI,Roboto,sans-serif; background:var(--bg); color:var(--text); font-size:14.5px; line-height:1.5; }
a { color:var(--accent); text-decoration:none; }
a:hover { text-decoration:underline; }
.wrap { max-width:1280px; margin:0 auto; padding:0 20px; }

.topnav { background:var(--card); border-bottom:1px solid var(--border); position:sticky; top:0; z-index:50; }
.topnav .wrap { display:flex; align-items:center; gap:18px; height:60px; }
.brand-name { font-size:22px; font-weight:800; letter-spacing:.3px; white-space:nowrap;
  background:linear-gradient(90deg,#2563eb 0%,#7c3aed 50%,#db2777 100%);
  -webkit-background-clip:text; background-clip:text; color:transparent; -webkit-text-fill-color:transparent; }
.brand { display:flex; align-items:center; }
.topnav nav { display:flex; gap:6px; align-items:center; flex:1; flex-wrap:wrap; }
.topnav nav a { color:#334155; font-weight:600; font-size:14px; padding:7px 14px; border-radius:8px; background:#f1f5f9; }
.topnav nav a:hover { color:var(--accent); background:#eef2ff; text-decoration:none; }
.topnav nav a.active { color:#fff; background:var(--accent); }
.nav-dd { position:relative; }
.nav-dd-trigger { cursor:pointer; display:inline-flex; align-items:center; gap:4px; }
.dd-caret { font-size:10px; }
.nav-dd-menu { position:absolute; top:100%; left:0; margin-top:6px; min-width:220px; background:#fff; border:1px solid var(--border); border-radius:8px; box-shadow:0 12px 32px -10px rgba(15,23,42,.18); padding:6px; z-index:100; opacity:0; visibility:hidden; transform:translateY(-4px); transition:opacity .15s, transform .15s, visibility .15s; }
.nav-dd:hover .nav-dd-menu, .nav-dd:focus-within .nav-dd-menu { opacity:1; visibility:visible; transform:translateY(0); }
.nav-dd-menu a { display:block; padding:8px 12px; font-size:14px; font-weight:600; color:#0f172a; background:transparent; border-radius:6px; }
.nav-dd-menu a:hover { background:#f1f5f9; color:var(--accent); }
.topnav .meta-info { color:var(--muted); font-size:12px; white-space:nowrap; }

.content { padding:24px 20px 60px; }
.hero h1 { margin:0 0 6px; font-size:26px; }
.hero p { color:var(--muted); margin:0; max-width:900px; }
.hero .stats { margin-top:14px; display:flex; gap:8px; flex-wrap:wrap; }
.pill { background:var(--card); border:1px solid var(--border); border-radius:20px; padding:5px 14px; font-size:12.5px; color:var(--muted); }

.grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(310px, 1fr)); gap:14px; margin-top:18px; }
.card { background:var(--card); border:1px solid var(--border); border-radius:10px; overflow:hidden; display:flex; flex-direction:column; transition:transform .15s, box-shadow .15s; }
.card:hover { transform:translateY(-2px); box-shadow:0 8px 24px rgba(0,0,0,.08); }
.thumb { aspect-ratio:16/9; background:#f1f5fb; position:relative; overflow:hidden; }
.thumb:not(:has(img)), .thumb.thumb-empty { display:none; }
.thumb img { width:100%; height:100%; object-fit:cover; display:block; }

.body { padding:.85rem 1rem 1rem; display:flex; flex-direction:column; gap:.5rem; flex:1; }
.meta-row { display:flex; gap:.4rem; align-items:center; flex-wrap:wrap; font-size:.72rem; color:var(--muted); }
.chip { padding:.15rem .55rem; border-radius:999px; font-weight:600; font-size:.68rem; text-transform:uppercase; letter-spacing:.04em; }
.chip-tech    { background:var(--chip-bg);   color:var(--chip-fg); }
.chip-vendor  { background:var(--vendor-bg); color:var(--vendor-fg); }
.chip-cust    { background:var(--cust-bg);   color:var(--cust-fg); }
.chip-app     { background:var(--app-bg);    color:var(--app-fg); }
.chip-std     { background:#ede9fe;          color:#5b21b6; }
.source { font-weight:600; opacity:.75; }
.dot { opacity:.5; }
.title { font-size:.98rem; font-weight:600; line-height:1.35; margin:0; }
.title a { color:var(--text); }
.title a:hover { color:var(--accent); }
.summary { color:var(--muted); font-size:.83rem; margin:0; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }
.empty { padding:3rem; text-align:center; color:var(--muted); }
.footer { margin-top:2rem; text-align:center; color:var(--muted); font-size:.78rem; padding:20px 0; border-top:1px solid var(--border); }

/* Section / table styling shared by Customers / Competitors */
.section { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:18px 20px; margin:18px 0; }
.section h2 { margin:0 0 8px; font-size:18px; }
.section h3 { margin:18px 0 8px; font-size:15px; color:#0f172a; }
.section .muted { color:var(--muted); font-size:13px; }
.tbl { width:100%; border-collapse:separate; border-spacing:0; font-size:13.5px; }
.tbl th, .tbl td { padding:9px 12px; text-align:left; border-bottom:1px solid var(--border); vertical-align:top; }
.tbl th { background:#f9fafc; font-weight:600; color:#374151; font-size:12.5px; text-transform:uppercase; letter-spacing:.3px; position:sticky; top:60px; }
.tbl tr:hover td { background:var(--hover); }
.tbl ul { margin:0; padding-left:18px; }
.tbl ul li { margin-bottom:3px; }
.tag { display:inline-block; background:#eef2ff; color:#3730a3; padding:1px 8px; border-radius:10px; font-size:11px; font-weight:600; margin:1px 2px; }
.tag-strong { background:#dcfce7; color:#166534; }
.tag-weak { background:#fee2e2; color:#991b1b; }
.tag-region-americas { background:#dbeafe; color:#1e40af; }
.tag-region-europe { background:#e0e7ff; color:#3730a3; }
.tag-region-asia { background:#fef3c7; color:#92400e; }

.disclaimer { background:#fffbeb; border:1px solid #fde68a; color:#92400e; border-radius:8px; padding:10px 14px; font-size:12.5px; margin:12px 0 18px; }

/* Refresh button */
.btn-refresh { padding:6px 12px; font-size:13px; font-weight:600; border:1px solid var(--border); background:#fff; color:var(--accent); border-radius:6px; cursor:pointer; transition:all .15s; display:inline-flex; align-items:center; gap:6px; }
.btn-refresh:hover { background:var(--accent); color:#fff; border-color:var(--accent); }
.btn-refresh:disabled { opacity:.5; cursor:not-allowed; }
.refresh-icon { display:inline-block; width:14px; height:14px; }
.refresh-icon.spinning { animation:spin 1s linear infinite; }
@keyframes spin { from { transform:rotate(0deg); } to { transform:rotate(360deg); } }
.refresh-status { font-size:11px; color:var(--muted); margin-left:8px; }

/* Technology tabs */
.tech-toolbar { display:flex; gap:12px; align-items:center; justify-content:space-between; margin:16px 0; flex-wrap:wrap; }
.tech-tabs { display:flex; gap:6px; flex-wrap:wrap; }
.tech-tab { padding:6px 12px; font-size:12px; font-weight:600; border:1px solid var(--border); background:#f1f5f9; color:#334155; border-radius:6px; cursor:pointer; transition:all .15s; }
.tech-tab:hover { background:var(--accent); color:#fff; border-color:var(--accent); }
.tech-tab.active { background:var(--accent); color:#fff; border-color:var(--accent); }
.tech-actions { display:flex; gap:8px; align-items:center; }
.tech-count { font-size:12px; color:var(--muted); }

/* News page left panel */
.news-layout { display:grid; grid-template-columns:240px 1fr; gap:18px; align-items:start; margin-top:16px; }
@media (max-width:900px) { .news-layout { grid-template-columns:1fr; } }
.news-sidebar { background:var(--card); border:1px solid var(--border); border-radius:12px; overflow:hidden; position:sticky; top:70px; max-height:calc(100vh - 90px); overflow-y:auto; }
.news-sidebar-hdr { padding:10px 14px; font-size:11.5px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); font-weight:700; background:#f9fafc; border-bottom:1px solid var(--border); border-top:1px solid var(--border); }
.news-sidebar-hdr:first-child { border-top:none; }
.news-class-block { border-bottom:1px solid #e5e7eb; }
.news-class-title { width:100%; display:flex; align-items:center; justify-content:space-between; padding:9px 12px; font-size:11px; text-transform:uppercase; letter-spacing:.06em; font-weight:800; border:none; border-bottom:1px solid #f1f5f9; cursor:pointer; }
.news-class-title .caret { font-size:11px; transition:transform .15s ease; }
.news-class-block.collapsed .news-class-title .caret { transform:rotate(-90deg); }
.news-class-body { display:block; }
.news-class-block.collapsed .news-class-body { display:none; }
.news-class-title.customers { background:#fdf2f8; color:#9d174d; }
.news-class-title.competitors { background:#eff6ff; color:#1d4ed8; }
.news-class-title.generic { background:#ecfdf5; color:#065f46; }
.news-class-title.standards { background:#f5f3ff; color:#5b21b6; }
.news-side-item { display:flex; justify-content:space-between; align-items:center; gap:6px; width:100%; text-align:left; background:none; border:none; border-bottom:1px solid #f1f5f9; padding:7px 14px; font-size:12.5px; color:#334155; cursor:pointer; }
.news-side-item:hover { background:var(--hover); color:var(--accent); }
.news-side-item.active { background:#eef2ff; color:var(--accent); font-weight:700; }
.news-side-item .side-count { font-size:10.5px; color:var(--muted); background:#f1f5f9; border-radius:8px; padding:1px 6px; }
.news-main { min-width:0; }
"""

# Client-side password gate injected into every generated page.
_PASSWORD_GATE_HTML = """
<script id="password-gate-v1">
(function(){
  var KEY='airoc_unlock_v1';
  var HASH='eecb6691ea4b94d780985dd0797634885fd7195f12c889ed367be387492f68ef';
  function hex(buf){return Array.prototype.map.call(new Uint8Array(buf), function(b){return b.toString(16).padStart(2,'0');}).join('');}
  function sha256(text){return crypto.subtle.digest('SHA-256', new TextEncoder().encode(text)).then(hex);}
  if (sessionStorage.getItem(KEY)==='1') { return; }
  document.documentElement.style.display='none';
  (async function(){
    while(true){
      var p=prompt('Enter password to access this site');
      if (p===null){ location.replace('about:blank'); return; }
      try {
        var h=await sha256(p);
        if (h===HASH){ sessionStorage.setItem(KEY,'1'); document.documentElement.style.display=''; return; }
      } catch (e) {}
      alert('Wrong password');
    }
  })();
})();
</script>
"""

# ---------------------------------------------------------------- nav
_NAV_HTML = """
<header class="topnav"><div class="wrap">
  <a class="brand" href="index.html"><span class="brand-name">IoT Wireless Intel</span></a>
  <nav>
    <a href="index.html" class="{{ 'active' if active=='index' else '' }}">Overview</a>
    <a href="news.html" class="{{ 'active' if active in news_slugs else '' }}">News</a>
    <a href="opportunity.html" class="{{ 'active' if active in ['customers','opportunity'] else '' }}">Opportunity</a>
    <a href="threat.html" class="{{ 'active' if active in ['competitors','threat'] else '' }}">Threat</a>
    <a href="relationships.html" class="{{ 'active' if active=='relationships' else '' }}">Relationships</a>
    <a href="technology.html" class="{{ 'active' if active=='technology' else '' }}">Technology</a>
  </nav>
  <div class="meta-info">Updated {{ generated_at }} PDT</div>
</div></header>
<script>
(function(){
  if(location.protocol !== 'file:') return;
  if(!/\/site_\d{8}-\d{6}\//.test(location.href)) return;
  var redirected = location.href.replace(/\/site_[^\/]+\//, '/latest/');
  if(redirected !== location.href) location.replace(redirected);
})();
</script>
"""

# ---------------------------------------------------------------- news template
_NEWS_TEMPLATE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ page_title }} \u00b7 IoT Wireless Intel</title>
<style>{{ css }}</style>
""" + _PASSWORD_GATE_HTML + """
</head><body>
""" + _NAV_HTML + """
<script>
(function(){
  if(location.protocol !== 'file:') return;
  if(!/\/site_\d{8}-\d{6}\//.test(location.href)) return;
  var redirected = location.href.replace(/\/site_[^\/]+\//, '/latest/');
  if(redirected !== location.href) location.replace(redirected);
})();
</script>

<main class="wrap content">
<section class="hero">
  <h1>{{ page_title }}</h1>
  {% if page_title != 'All News' %}
  <p>{{ page_desc }}</p>
  {% endif %}
  <div class="stats">
    {% if page_title != 'All News' %}
    <span class="pill">{{ articles|length }} articles</span>
    {% if vendor_groups %}<span class="pill">{{ vendor_total }} vendors</span>{% endif %}
    {% if customer_tabs %}<span class="pill">{{ customer_tabs|length }} customers</span>{% endif %}
    {% if app_tabs %}<span class="pill">{{ app_tabs|length }} applications</span>{% endif %}
    {% endif %}
    <span class="pill" id="lastUpdatedPill">Last updated: <span id="lastUpdatedText" data-ts="{{ generated_at }}">{{ generated_at }} PDT</span></span>
  </div>
</section>

{% if page_title == 'All News' %}
<section class="tech-toolbar">
  <div class="tech-tabs" id="techTabs">
    <button class="tech-tab active" data-filter="all" onclick="filterByTech('all', this)">All News</button>
    {% for bucket, label in bucket_labels.items() %}<button class="tech-tab" data-filter="{{ bucket }}" onclick="filterByTech('{{ bucket }}', this)">{{ label }}</button>{% endfor %}
  </div>
  <div class="tech-actions">
    <span class="tech-count" id="articleCount">{{ articles|length }} articles</span>
    <button class="btn-refresh" id="refreshBtn" onclick="refreshNews(event)"><span class="refresh-icon" id="refreshIcon">&#x21bb;</span> Refresh</button>
  </div>
</section>

<div class="news-layout">
  <aside class="news-sidebar">
    <div class="news-sidebar-hdr">Classified News</div>

    <div class="news-class-block" id="newsClassStandards">
      <button class="news-class-title standards" onclick="toggleNewsSection('newsClassStandards')">Standards <span class="caret">▾</span></button>
      <div class="news-class-body">
        <button class="news-side-item" data-side-type="standard" data-side-value="" onclick="filterBySideFromButton(this)">All standards news <span class="side-count">{{ standard_total }}</span></button>
        {% for slug, label, cnt in standard_tabs %}
        <button class="news-side-item" data-side-type="standard" data-side-value="{{ slug }}" onclick="filterBySideFromButton(this)">{{ label }} <span class="side-count">{{ cnt }}</span></button>
        {% endfor %}
      </div>
    </div>

    <div class="news-class-block" id="newsClassCustomers">
      <button class="news-class-title customers" onclick="toggleNewsSection('newsClassCustomers')">Opportunity <span class="caret">▾</span></button>
      <div class="news-class-body">
        {% for name, cnt in customer_tabs %}
        <button class="news-side-item" data-side-type="customer" data-side-value="{{ name }}" onclick="filterBySideFromButton(this)">{{ name }} <span class="side-count">{{ cnt }}</span></button>
        {% endfor %}
      </div>
    </div>

    <div class="news-class-block" id="newsClassCompetitors">
      <button class="news-class-title competitors" onclick="toggleNewsSection('newsClassCompetitors')">Threat <span class="caret">▾</span></button>
      <div class="news-class-body">
        {% for region_slug, region_label, names, region_count in vendor_groups %}
          {% for name, cnt in names %}
          <button class="news-side-item" data-side-type="vendor" data-side-value="{{ name }}" onclick="filterBySideFromButton(this)">{{ name }} <span class="side-count">{{ cnt }}</span></button>
          {% endfor %}
        {% endfor %}
      </div>
    </div>

    <div class="news-class-block" id="newsClassGeneric">
      <button class="news-class-title generic" onclick="toggleNewsSection('newsClassGeneric')">Generic IoT <span class="caret">▾</span></button>
      <div class="news-class-body">
        <button class="news-side-item active" data-side-type="all" data-side-value="" onclick="filterBySideFromButton(this)">All IoT news</button>
        <button class="news-side-item" data-side-type="market" data-side-value="" onclick="filterBySideFromButton(this)">Generic IoT only</button>
      </div>
    </div>
  </aside>

  <div class="news-main">
{% endif %}

{% if not articles %}<div class="empty">No articles. Try widening <code>--max-age-days</code>.</div>{% endif %}

<div class="grid" id="grid">
  {% for a in articles %}
  <article class="card" data-buckets="{{ a.buckets|join(',') }}" data-vendor="{{ a.vendor or '' }}" data-customer="{{ a.customer or '' }}" data-standard="{{ a.standard or '' }}">
    <div class="thumb">
      {% if a.thumb %}<img src="{{ a.thumb }}" loading="lazy" referrerpolicy="no-referrer" onerror="this.parentElement.classList.add('thumb-empty'); this.remove()">{% endif %}
    </div>
    <div class="body">
      <div class="meta-row">
        {% if a.standard %}<span class="chip chip-std">{{ bucket_labels[a.standard] }} spec</span>{% endif %}
        {% for b in a.buckets %}<span class="chip chip-tech">{{ bucket_labels[b] }}</span>{% endfor %}
        {% if a.vendor %}<span class="chip chip-vendor">{{ a.vendor }}</span>{% endif %}
        {% if a.customer %}<span class="chip chip-cust">{{ a.customer }}</span>{% endif %}
        {% if a.application %}<span class="chip chip-app">{{ a.application }}</span>{% endif %}
      </div>
      <h2 class="title"><a href="{{ a.url }}" target="_blank" rel="noopener">{{ a.title }}</a></h2>
      {% if a.summary %}<p class="summary">{{ a.summary[:240] }}{% if a.summary|length > 240 %}\u2026{% endif %}</p>{% endif %}
      <div class="meta-row">
        <span class="source">{{ a.source }}</span>
        {% if a.published %}<span class="dot">\u00b7</span><span class="time" data-ts="{{ a.published.isoformat() }}">{{ a.published.strftime('%Y-%m-%d') }}</span>{% endif %}
      </div>
    </div>
  </article>
  {% endfor %}
</div>

{% if page_title == 'All News' %}
  </div><!-- /.news-main -->
</div><!-- /.news-layout -->
{% endif %}
</main>
<footer class="footer"><div class="wrap">IoT Wireless Intel \u00b7 multi-source RSS \u00b7 for informational use</div></footer>
<script>
const BUCKET_LABELS = {{ bucket_labels|tojson }};

function timeAgo(iso){
  const d=new Date(iso); if(isNaN(d)) return '';
  let s=Math.floor((Date.now()-d.getTime())/1000); if(s<0)s=0;
  if(s<45) return 'just now';
  const m=Math.floor(s/60); if(m<60) return m+(m===1?' min ago':' mins ago');
  const h=Math.floor(m/60); if(h<24){const r=m%60; if(h<6&&r) return h+'h '+r+'m ago'; return h+(h===1?' hour ago':' hours ago');}
  const day=Math.floor(h/24); if(day<7) return day+(day===1?' day ago':' days ago');
  if(day<30){const w=Math.floor(day/7); return w+(w===1?' week ago':' weeks ago');}
  if(day<365){const mo=Math.floor(day/30); return mo+(mo===1?' month ago':' months ago');}
  const y=Math.floor(day/365); return y+(y===1?' year ago':' years ago');
}
document.querySelectorAll('.time[data-ts]').forEach(el=>{el.textContent=timeAgo(el.dataset.ts); el.title=el.dataset.ts;});

let techFilter = 'all';
let sideFilter = { type: 'all', value: '' };

function applyFilters(){
  const cards = document.querySelectorAll('#grid .card');
  let visible = 0;
  cards.forEach(card => {
    const buckets = (card.dataset.buckets || '').split(',').filter(Boolean);
    const vendor = card.dataset.vendor || '';
    const customer = card.dataset.customer || '';
    const standard = card.dataset.standard || '';
    const techOk = techFilter === 'all' || buckets.includes(techFilter);
    let sideOk = true;
    if (sideFilter.type === 'vendor') sideOk = vendor === sideFilter.value;
    else if (sideFilter.type === 'customer') sideOk = customer === sideFilter.value;
    else if (sideFilter.type === 'market') sideOk = !vendor && !customer;
    else if (sideFilter.type === 'standard') sideOk = sideFilter.value ? (standard === sideFilter.value) : (standard !== '');
    const show = techOk && sideOk;
    card.style.display = show ? '' : 'none';
    if (show) visible++;
  });
  const countEl = document.getElementById('articleCount');
  if (countEl) countEl.textContent = visible + ' article' + (visible !== 1 ? 's' : '');
}

function updateSidebarCounts(){
  const cards = document.querySelectorAll('#grid .card');
  const activeCards = [];
  cards.forEach(card => {
    const buckets = (card.dataset.buckets || '').split(',').filter(Boolean);
    if (techFilter === 'all' || buckets.includes(techFilter)) activeCards.push(card);
  });

  const vendorCounts = Object.create(null);
  const customerCounts = Object.create(null);
  const standardCounts = Object.create(null);
  let standardTotal = 0;

  activeCards.forEach(card => {
    const vendor = (card.dataset.vendor || '').trim();
    const customer = (card.dataset.customer || '').trim();
    const standard = (card.dataset.standard || '').trim();
    if (vendor) vendorCounts[vendor] = (vendorCounts[vendor] || 0) + 1;
    if (customer) customerCounts[customer] = (customerCounts[customer] || 0) + 1;
    if (standard) {
      standardCounts[standard] = (standardCounts[standard] || 0) + 1;
      standardTotal += 1;
    }
  });

  document.querySelectorAll('.news-side-item[data-side-type]').forEach(btn => {
    const type = btn.dataset.sideType || '';
    const value = (btn.dataset.sideValue || '').trim();
    const badge = btn.querySelector('.side-count');
    if (!badge) return;
    if (type === 'vendor') badge.textContent = String(vendorCounts[value] || 0);
    else if (type === 'customer') badge.textContent = String(customerCounts[value] || 0);
    else if (type === 'standard') badge.textContent = String(value ? (standardCounts[value] || 0) : standardTotal);
  });
}

function filterByTech(bucket, el) {
  document.querySelectorAll('.tech-tab').forEach(t => t.classList.remove('active'));
  const target = el || (window.event && window.event.target && window.event.target.closest('.tech-tab'));
  if (target) target.classList.add('active');
  techFilter = bucket;
  updateSidebarCounts();
  applyFilters();
}

function filterBySide(type, value) {
  document.querySelectorAll('.news-side-item').forEach(b => b.classList.remove('active'));
  if (window.event && window.event.target) {
    const btn = window.event.target.closest('.news-side-item');
    if (btn) btn.classList.add('active');
  }
  sideFilter = { type: type, value: value };
  applyFilters();
}

function filterBySideFromButton(btn) {
  document.querySelectorAll('.news-side-item').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  sideFilter = { type: btn.dataset.sideType || 'all', value: btn.dataset.sideValue || '' };
  applyFilters();
}

function toggleNewsSection(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.toggle('collapsed');
}

function escapeHtml(s){
  return (s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function cardHtml(a){
  const buckets = a.buckets || [];
  const bucketChips = buckets.map(b => '<span class="chip chip-tech">' + escapeHtml(BUCKET_LABELS[b] || b) + '</span>').join('');
  const stdChip = a.standard ? '<span class="chip chip-std">' + escapeHtml((BUCKET_LABELS[a.standard] || a.standard)) + ' spec</span>' : '';
  const vendorChip = a.vendor ? '<span class="chip chip-vendor">' + escapeHtml(a.vendor) + '</span>' : '';
  const customerChip = a.customer ? '<span class="chip chip-cust">' + escapeHtml(a.customer) + '</span>' : '';
  const appChip = a.application ? '<span class="chip chip-app">' + escapeHtml(a.application) + '</span>' : '';
  const thumb = a.thumb ? '<img src="' + a.thumb + '" loading="lazy" referrerpolicy="no-referrer" onerror="this.parentElement.classList.add(\\'thumb-empty\\'); this.remove()">' : '';
  let summary = a.summary || '';
  if (summary.length > 240) summary = summary.slice(0, 240) + '\u2026';
  const summaryHtml = summary ? '<p class="summary">' + escapeHtml(summary) + '</p>' : '';
  const timeHtml = a.published ? '<span class="dot">\u00b7</span><span class="time" data-ts="' + a.published + '">' + a.published.slice(0, 10) + '</span>' : '';
  return '<article class="card" data-buckets="' + buckets.join(',') + '" data-vendor="' + escapeHtml(a.vendor || '') + '" data-customer="' + escapeHtml(a.customer || '') + '" data-standard="' + escapeHtml(a.standard || '') + '">' +
    '<div class="thumb">' + thumb + '</div>' +
    '<div class="body">' +
      '<div class="meta-row">' + stdChip + bucketChips + vendorChip + customerChip + appChip + '</div>' +
      '<h2 class="title"><a href="' + a.url + '" target="_blank" rel="noopener">' + escapeHtml(a.title) + '</a></h2>' +
      summaryHtml +
      '<div class="meta-row"><span class="source">' + escapeHtml(a.source || '') + '</span>' + timeHtml + '</div>' +
    '</div>' +
  '</article>';
}

async function loadNews(){
  const grid = document.getElementById('grid');
  if (!grid) return;
  if (!isLocalBackend()) return;
  try {
    const res = await fetch('/api/news?limit=2000');
    if (!res.ok) return;
    const data = await res.json();
    if (!Array.isArray(data) || !data.length) return;
    grid.innerHTML = data.map(cardHtml).join('');
    document.querySelectorAll('#grid .time[data-ts]').forEach(el=>{el.textContent=timeAgo(el.dataset.ts); el.title=el.dataset.ts;});
    updateSidebarCounts();
    applyFilters();
  } catch (e) {
    // No backend available (static hosting) - keep server-rendered cards as-is.
  }
}

function isLocalBackend() {
  return location.hostname === 'localhost' || location.hostname === '127.0.0.1';
}

function staticRefreshFallback(btn, icon) {
  btn.textContent = '\u21bb Reloading\u2026';
  const next = new URL(location.href);
  next.searchParams.set('_ts', String(Date.now()));
  location.href = next.toString();
}

async function refreshNews(event) {
  event.preventDefault();
  const btn = document.getElementById('refreshBtn');
  const icon = document.getElementById('refreshIcon');

  if (btn.disabled) return;

  btn.disabled = true;
  icon.classList.add('spinning');
  btn.textContent = '\u21bb Refreshing\u2026';

  if (!isLocalBackend()) {
    staticRefreshFallback(btn, icon);
    return;
  }

  try {
    const response = await fetch('/api/refresh-news', { method: 'POST' });
    const data = await response.json();

    if (data.ok) {
      btn.textContent = '\u2713 Done';
      const lu = document.getElementById('lastUpdatedText');
      if (lu && data.timestamp) {
        const d = new Date(data.timestamp);
        if (!isNaN(d)) lu.textContent = d.toLocaleString();
      }
      await loadNews();
      setTimeout(() => {
        btn.textContent = '\u21bb Refresh';
        btn.disabled = false;
        icon.classList.remove('spinning');
      }, 1200);
    } else {
      btn.textContent = '\u2717 Error';
      setTimeout(() => {
        btn.textContent = '\u21bb Refresh';
        btn.disabled = false;
        icon.classList.remove('spinning');
      }, 3000);
    }
  } catch (err) {
    btn.textContent = '\u2717 Error';
    setTimeout(() => {
      btn.textContent = '\u21bb Refresh';
      btn.disabled = false;
      icon.classList.remove('spinning');
    }, 3000);
  }
}

document.addEventListener('DOMContentLoaded', function(){
  updateSidebarCounts();
  const btn = document.getElementById('refreshBtn');
  if (btn && !isLocalBackend()) {
    btn.title = 'GitHub Pages cannot run backend refresh; this reloads the page to pick up latest published content.';
  }
  if (document.getElementById('grid')) loadNews();
});
</script>
</body></html>
"""

# ---------------------------------------------------------------- customers template
_CUSTOMERS_TEMPLATE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Customers \u00b7 IoT Wireless Intel</title>
<style>{{ css }}

/* ===== OEM CUSTOMER INTELLIGENCE HUB ===== */
{% set cat_colors = {
  'Big Tech / Smart Home': '#2563eb',
  'Big Tech / Consumer':   '#7c3aed',
  'Big Tech / PC + Enterprise': '#0ea5e9',
  'AR/VR/XR':              '#db2777',
  'Consumer Electronics':  '#059669',
  'Audio':                 '#d97706',
  'Security / Cameras':    '#dc2626',
  'Wearables / Sports':    '#16a34a',
  'Automotive':            '#0891b2'
} %}

.oc-stats-bar { display:flex; gap:10px; flex-wrap:wrap; margin:0 0 20px; }
.oc-stat-pill { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:10px 18px; display:flex; flex-direction:column; align-items:center; min-width:110px; }
.oc-stat-pill .v { font-size:22px; font-weight:800; color:var(--accent); }
.oc-stat-pill .l { font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; margin-top:2px; }

/* Layout */
.ci-layout { display:grid; grid-template-columns:260px 1fr; gap:20px; align-items:start; min-width:0; }
@media (max-width:860px) { .ci-layout { grid-template-columns:1fr; } }

/* Sidebar */
.ci-sidebar { background:var(--card); border:1px solid var(--border); border-radius:12px; overflow:hidden; position:sticky; top:70px; }
.ci-sidebar-hdr { padding:12px 16px; font-size:13.5px; text-transform:uppercase; letter-spacing:.07em; color:var(--muted); font-weight:700; border-bottom:1px solid var(--border); background:#f9fafc; }
.ci-tab { width:100%; background:transparent; border:none; border-bottom:1px solid var(--border); padding:12px 14px; cursor:pointer; display:flex; align-items:center; gap:10px; text-align:left; transition:background .12s; font-family:inherit; }
.ci-tab:hover  { background:var(--hover); }
.ci-tab.active { background:#eef2ff; border-left:3px solid var(--accent); }
.ci-tab:last-child { border-bottom:none; }
.ci-avatar { width:34px; height:34px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:15px; color:#fff; flex-shrink:0; }
.ci-tab-info { flex:1; min-width:0; }
.ci-tab-info strong { display:block; font-size:15px; color:#0f172a; }
.ci-tab-region { font-size:12px; color:var(--muted); }
.ci-news-badge { background:#f1f5f9; border:1px solid var(--border); border-radius:20px; padding:2px 8px; font-size:12.5px; font-weight:700; color:#334155; white-space:nowrap; }

/* Panel */
.ci-panel { display:none; }
.ci-panel.active { display:block; }

/* Panel header */
.ci-header { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:20px 24px; margin-bottom:16px; display:flex; align-items:flex-start; justify-content:space-between; gap:16px; }
.ci-header-left { display:flex; gap:16px; align-items:flex-start; }
.ci-avatar-lg { width:54px; height:54px; border-radius:14px; display:flex; align-items:center; justify-content:center; font-weight:900; font-size:26px; color:#fff; flex-shrink:0; }
.ci-header-left h2 { margin:0 0 4px; font-size:26px; }
.ci-meta { color:var(--muted); font-size:15px; margin-bottom:8px; }
.ci-news-count { text-align:center; background:#eef2ff; border:1px solid #c7d2fe; border-radius:10px; padding:10px 16px; flex-shrink:0; display:block; }
.ci-nc-num { font-size:28px; font-weight:900; color:var(--accent); line-height:1; }
.ci-nc-label { font-size:10px; color:#6366f1; text-transform:uppercase; letter-spacing:.05em; margin-top:2px; }

/* Section headings */
.ci-section-h { font-size:15px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); font-weight:700; margin:0 0 10px; display:flex; align-items:center; gap:6px; }

/* Two-col grid */
.ci-grid-2 { display:grid; grid-template-columns:1fr 1fr; gap:18px; margin-bottom:16px; }
@media (max-width:1000px) { .ci-grid-2 { grid-template-columns:1fr; } }
.ci-grid-2 > div { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:16px 18px; }

/* Product cards */
.ci-products { display:flex; flex-direction:column; gap:8px; }
.ci-product-card { background:#f9fafc; border:1px solid var(--border); border-radius:8px; padding:10px 14px; }
.ci-product-sku { font-weight:700; font-size:15px; color:#0f172a; margin-bottom:2px; }
.ci-product-type { font-size:13px; color:var(--muted); line-height:1.5; margin-bottom:3px; }
.ci-product-summary { font-size:12px; color:#475569; line-height:1.4; margin-top:4px; font-style:italic; }

/* Chip partner cards */
.ci-customers-wrap { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:14px 18px; margin-bottom:16px; }
.ci-customers { display:flex; flex-wrap:wrap; gap:8px; margin-top:8px; }
.ci-customer-card { background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:7px 14px; }
.ci-customer-name { font-size:14px; font-weight:700; color:#1e293b; }

/* Wireless focus tags */
.oc-focus-wrap { display:flex; flex-wrap:wrap; gap:6px; margin-top:8px; }
.oc-focus-tag { background:#e0f2fe; border:1px solid #bae6fd; color:#0369a1; border-radius:16px; padding:3px 12px; font-size:12px; font-weight:700; }

/* News feed */
.ci-news-feed-wrap { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:14px 18px; margin-bottom:16px; }
.ci-news-feed { display:flex; flex-direction:column; gap:8px; margin-top:8px; max-height:360px; overflow-y:auto; }
.ci-news-item { display:flex; flex-direction:column; gap:2px; padding:8px 10px; border-radius:8px; background:#f8fafc; border:1px solid #f1f5f9; transition:background .15s; }
.ci-news-item:hover { background:#f0f9ff; }
.ci-news-item a { font-size:14px; font-weight:600; color:#1e40af; text-decoration:none; line-height:1.35; }
.ci-news-item a:hover { text-decoration:underline; }
.ci-news-meta { display:flex; gap:8px; align-items:center; font-size:12px; color:#94a3b8; }
.ci-no-news { color:#94a3b8; font-size:14px; font-style:italic; padding:8px 0; }

/* Product link */
.ci-prod-link { color:inherit; text-decoration:none; }
.ci-prod-link:hover { color:var(--accent); text-decoration:underline; }
.ci-prod-search-icon { font-size:11px; opacity:.45; margin-left:2px; }

/* News card grid (mirrors main news tab) */
.oc-news-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(290px,1fr)); gap:16px; margin-top:12px; }
.oc-news-grid .card { margin:0; }
</style>
""" + _PASSWORD_GATE_HTML + """
</head><body>
""" + _NAV_HTML + """
<main class="wrap content">

<section class="hero" style="margin-bottom:18px;">
  <h1>OEM Customer Intelligence</h1>
  <p style="color:var(--muted);margin:4px 0 0;">Live news evidence, recent product portfolio &amp; chip partner data for key OEM customers.</p>
</section>

<!-- Stats bar -->
<div class="oc-stats-bar">
  <div class="oc-stat-pill"><div class="v">{{ customers|length }}</div><div class="l">OEMs tracked</div></div>
  <div class="oc-stat-pill"><div class="v">{{ news_counts.values()|sum }}</div><div class="l">News (all time)</div></div>
  <div class="oc-stat-pill"><div class="v">{{ customers|sum(attribute='recent_products'|length) if false else customers|map(attribute='recent_products')|map('length')|sum }}</div><div class="l">Products tracked</div></div>
</div>

<!-- Main layout -->
<div class="ci-layout">

  <!-- Sidebar -->
  <aside class="ci-sidebar">
    <div class="ci-sidebar-hdr">OEM Customers</div>
    {% for c in customers %}
    {% set color = cat_colors.get(c.category, '#6b7280') %}
    <button class="ci-tab {{ 'active' if loop.index0 == 0 else '' }}" data-panel="{{ loop.index0 }}" style="{{ 'border-left:3px solid ' + color + ';' if loop.index0 == 0 else '' }}">
      <span class="ci-avatar" style="background:{{ color }}">{{ c.name[0] }}</span>
      <div class="ci-tab-info">
        <strong>{{ c.name }}</strong>
        <div class="ci-tab-region">{{ c.category }}</div>
      </div>
      <span class="ci-news-badge">{{ news_counts.get(c.name, 0) }}</span>
    </button>
    {% endfor %}
  </aside>

  <!-- Detail panels -->
  <div class="ci-panels">
    {% for c in customers %}
    {% set color = cat_colors.get(c.category, '#6b7280') %}
    {% set nc = news_counts.get(c.name, 0) %}
    {% set live = customer_live.get(c.name, []) %}
    <div class="ci-panel {{ 'active' if loop.index0 == 0 else '' }}" id="panel-{{ loop.index0 }}">

      <!-- Header -->
      <div class="ci-header" style="border-left:4px solid {{ color }};">
        <div class="ci-header-left">
          <div class="ci-avatar-lg" style="background:{{ color }};">{{ c.name[0] }}</div>
          <div>
            <h2 style="color:{{ color }};">{{ c.name }}</h2>
            <div class="ci-meta">{{ c.category }}</div>
            <div class="oc-focus-wrap">
              {% for w in c.wireless_focus %}<span class="oc-focus-tag">{{ w }}</span>{% endfor %}
            </div>
          </div>
        </div>
        <div class="ci-news-count">
          <div class="ci-nc-num">{{ nc }}</div>
          <div class="ci-nc-label">news<br>articles</div>
        </div>
      </div>

      <!-- Recent Products -->
      <div style="background:var(--card); border:1px solid var(--border); border-radius:10px; padding:16px 18px; margin-bottom:16px;">
        <div class="ci-section-h">&#x1F4F1; Recent Products (last 0-2 years)</div>
        <div class="ci-products">
          {% for p in c.recent_products|sort(attribute='year', reverse=True) %}
          <div class="ci-product-card">
            <div class="ci-product-sku">{{ p.year }} &mdash;
              {% if p.url %}
              <a href="{{ p.url }}" target="_blank" rel="noopener" class="ci-prod-link">{{ p.name }} &#x2197;</a>
              {% else %}
              <span class="ci-prod-link" title="Direct source URL not available">{{ p.name }}</span>
              {% endif %}
            </div>
            <div class="ci-product-type">{{ p.tech }}</div>
            {% if p.summary %}<div class="ci-product-summary">{{ p.summary }}</div>{% endif %}
          </div>
          {% endfor %}
        </div>
      </div>

    </div>
    {% endfor %}
  </div>

</div><!-- /ci-layout -->

</main>
<footer class="footer"><div class="wrap">Edit data in <code>data/customers.json</code> &middot; IoT Wireless Intel &middot; {{ generated_at }}</div></footer>
<script>
function timeAgo(iso){
  var s=iso; if(s&&s.length===10)s+='T00:00:00Z';
  var d=new Date(s); if(isNaN(d)) return iso;
  var sec=Math.floor((Date.now()-d.getTime())/1000); if(sec<0)sec=0;
  if(sec<45) return 'just now';
  var m=Math.floor(sec/60); if(m<60) return m+(m===1?' min ago':' mins ago');
  var h=Math.floor(m/60); if(h<24) return h+(h===1?' hour ago':' hours ago');
  var day=Math.floor(h/24); if(day<7) return day+(day===1?' day ago':' days ago');
  if(day<30){var w=Math.floor(day/7); return w+(w===1?' week ago':' weeks ago');}
  if(day<365){var mo=Math.floor(day/30); return mo+(mo===1?' month ago':' months ago');}
  var y=Math.floor(day/365); return y+(y===1?' year ago':' years ago');
}
document.querySelectorAll('.time[data-ts]').forEach(function(el){el.textContent=timeAgo(el.dataset.ts); el.title=el.dataset.ts;});
(function(){
  var tabs = document.querySelectorAll('.ci-tab');
  var panels = document.querySelectorAll('.ci-panel');
  tabs.forEach(function(tab){
    tab.addEventListener('click', function(){
      var idx = parseInt(tab.dataset.panel, 10);
      tabs.forEach(function(t, i){
        t.classList.toggle('active', i===idx);
        if(i===idx){ t.style.borderLeft='3px solid '+t.querySelector('.ci-avatar').style.background; }
        else { t.style.borderLeft=''; }
      });
      panels.forEach(function(p, i){ p.classList.toggle('active', i===idx); });
    });
  });
})();
</script>
</body></html>
"""

# ---------------------------------------------------------------- competitors template
_COMPETITORS_TEMPLATE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Competitive Intelligence \u00b7 IoT Wireless Intel</title>
<style>{{ css }}

/* ===== COMPETITOR INTELLIGENCE HUB ===== */
{% set vendor_colors = {
  'Nordic':       '#4f46e5',
  'NXP':          '#0ea5e9',
  'Qualcomm':     '#dc2626',
  'Silicon Labs':  '#16a34a',
  'TI':           '#d97706',
  'MediaTek':     '#7c3aed',
  'Espressif':    '#0891b2',
  'STMicro':      '#2563eb',
  'Renesas':      '#059669',
  'Synaptics':    '#db2777'
} %}
{% set seg_colors = {
  'consumer':   '#3b82f6',
  'industrial': '#f59e0b',
  'automotive': '#10b981',
  'smart_home': '#8b5cf6',
  'medical':    '#ef4444',
  'other':      '#94a3b8'
} %}
{% set ctype_css = {
  'app_note':      'background:#fef3c7;color:#92400e;border-color:#fde68a',
  'product_brief': 'background:#dbeafe;color:#1e40af;border-color:#bfdbfe',
  'datasheet':     'background:#ede9fe;color:#5b21b6;border-color:#ddd6fe',
  'sdk':           'background:#d1fae5;color:#065f46;border-color:#a7f3d0',
  'whitepaper':    'background:#f3f4f6;color:#374151;border-color:#d1d5db'
} %}
{% set ctype_labels = {
  'app_note':      'App Note',
  'product_brief': 'Product Brief',
  'datasheet':     'Datasheet',
  'sdk':           'SDK / Tools',
  'whitepaper':    'Whitepaper'
} %}

.ci-anchor-bar { background:linear-gradient(135deg,#1e3a8a 0%,#2563eb 50%,#7c3aed 100%); color:#fff; border-radius:12px; padding:18px 24px; margin:18px 0; display:flex; gap:24px; flex-wrap:wrap; align-items:center; }
.ci-anchor-bar h2 { margin:0 0 4px; font-size:18px; color:#fff; }
.ci-anchor-bar p  { margin:0; font-size:13px; opacity:.85; }
.ci-anchor-skus   { display:flex; gap:8px; flex-wrap:wrap; margin-top:10px; }
.ci-sku-chip { background:rgba(255,255,255,.18); border:1px solid rgba(255,255,255,.3); border-radius:8px; padding:5px 12px; font-size:12px; color:#fff; }
.ci-sku-chip strong { display:block; font-size:13px; }
.ci-anchor-link { color:#bfdbfe; font-size:13px; margin-top:8px; display:inline-block; }
.ci-anchor-link:hover { color:#fff; }

.ci-stats-bar { display:flex; gap:10px; flex-wrap:wrap; margin:0 0 20px; }
.ci-stat-pill { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:10px 18px; display:flex; flex-direction:column; align-items:center; min-width:110px; }
.ci-stat-pill .v { font-size:22px; font-weight:800; color:var(--accent); }
.ci-stat-pill .l { font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; margin-top:2px; }

/* Layout */
.ci-layout { display:grid; grid-template-columns:270px 1fr; gap:20px; align-items:start; min-width:0; }
@media (max-width:860px) { .ci-layout { grid-template-columns:1fr; } }

/* Sidebar */
.ci-sidebar { background:var(--card); border:1px solid var(--border); border-radius:12px; overflow:hidden; position:sticky; top:70px; }
.ci-sidebar-hdr { padding:12px 16px; font-size:13.5px; text-transform:uppercase; letter-spacing:.07em; color:var(--muted); font-weight:700; border-bottom:1px solid var(--border); background:#f9fafc; }
.ci-tab { width:100%; background:transparent; border:none; border-bottom:1px solid var(--border); padding:12px 14px; cursor:pointer; display:flex; align-items:center; gap:10px; text-align:left; transition:background .12s; font-family:inherit; }
.ci-tab:hover  { background:var(--hover); }
.ci-tab.active { background:#eef2ff; border-left:3px solid var(--accent); }
.ci-tab:last-child { border-bottom:none; }
.ci-avatar { width:34px; height:34px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:15px; color:#fff; flex-shrink:0; }
.ci-tab-info { flex:1; min-width:0; }
.ci-tab-info strong { display:block; font-size:15px; color:#0f172a; }
.ci-tab-region { font-size:12px; color:var(--muted); }
.ci-news-badge { background:#f1f5f9; border:1px solid var(--border); border-radius:20px; padding:2px 8px; font-size:12.5px; font-weight:700; color:#334155; white-space:nowrap; }

/* Panel */
.ci-panel { display:none; }
.ci-panel.active { display:block; }

/* Panel header */
.ci-header { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:20px 24px; margin-bottom:16px; display:flex; align-items:flex-start; justify-content:space-between; gap:16px; }
.ci-header-left { display:flex; gap:16px; align-items:flex-start; }
.ci-avatar-lg { width:54px; height:54px; border-radius:14px; display:flex; align-items:center; justify-content:center; font-weight:900; font-size:26px; color:#fff; flex-shrink:0; }
.ci-header-left h2 { margin:0 0 4px; font-size:26px; }
.ci-meta { color:var(--muted); font-size:15px; margin-bottom:4px; }
.ci-website-link { font-size:12.5px; color:var(--accent); }
.ci-news-count { text-align:center; background:#eef2ff; border:1px solid #c7d2fe; border-radius:10px; padding:10px 16px; flex-shrink:0; text-decoration:none; cursor:pointer; transition:background .15s,transform .1s; display:block; }
.ci-news-count:hover { background:#e0e7ff; transform:translateY(-1px); }
.ci-nc-num { font-size:28px; font-weight:900; color:var(--accent); line-height:1; }
.ci-nc-label { font-size:10px; color:#6366f1; text-transform:uppercase; letter-spacing:.05em; margin-top:2px; }

/* Positioning */
.ci-positioning { background:linear-gradient(135deg,#f0f9ff,#e0f2fe); border:1px solid #bae6fd; border-radius:10px; padding:14px 18px; margin-bottom:16px; font-size:16px; font-style:italic; color:#0369a1; line-height:1.6; }

/* Section headings */
.ci-section-h { font-size:15px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); font-weight:700; margin:0 0 10px; display:flex; align-items:center; gap:6px; }
.ci-est-badge { background:#fef3c7; color:#92400e; border:1px solid #fde68a; border-radius:6px; padding:1px 6px; font-size:10px; text-transform:none; letter-spacing:0; font-style:italic; }

/* Two-col grid */
.ci-grid-2 { display:grid; grid-template-columns:1fr 1fr; gap:18px; margin-bottom:16px; }
@media (max-width:1000px) { .ci-grid-2 { grid-template-columns:1fr; } }
.ci-grid-2 > div { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:16px 18px; }

/* Product cards */
.ci-products { display:flex; flex-direction:column; gap:8px; }
.ci-product-card { background:#f9fafc; border:1px solid var(--border); border-radius:8px; padding:10px 14px; }
.ci-product-sku { font-weight:700; font-size:16px; color:#0f172a; margin-bottom:3px; }
.ci-product-type { font-size:15px; color:var(--muted); line-height:1.5; margin-bottom:5px; }
.ci-product-summary { font-size:13px; color:#475569; line-height:1.4; margin-bottom:5px; font-style:italic; }
.ci-product-links { font-size:11.5px; }
.ci-product-links a { color:var(--accent); margin-right:8px; }

/* Segment revenue bars */
.ci-seg-bars { display:flex; flex-direction:column; gap:9px; }
.ci-seg-row { display:flex; align-items:center; gap:8px; }
.ci-seg-label { font-size:15px; color:#374151; min-width:140px; }
.ci-seg-track { flex:1; height:10px; background:#e5e7eb; border-radius:5px; overflow:hidden; }
.ci-seg-fill { height:100%; border-radius:5px; transition:width .5s ease; }
.ci-seg-pct { font-size:15px; font-weight:700; color:#374151; min-width:34px; text-align:right; }
.ci-seg-note { font-size:11px; color:var(--muted); font-style:italic; margin:10px 0 0; line-height:1.5; }

/* Press release timeline */
.ci-timeline { display:flex; flex-direction:column; gap:10px; }
.ci-pr-item { display:flex; flex-direction:column; gap:2px; padding-left:12px; border-left:2px solid #c7d2fe; }
.ci-pr-date { font-size:13px; font-weight:700; color:#6366f1; text-transform:uppercase; }
.ci-pr-title { font-size:15px; color:#0f172a; line-height:1.45; }
.ci-pr-title:hover { color:var(--accent); }

/* Events */
.ci-events { display:flex; flex-direction:column; gap:8px; }
.ci-event-card { background:#f9fafc; border:1px solid var(--border); border-radius:8px; padding:9px 12px; }
.ci-event-name { font-size:15px; font-weight:600; }
.ci-event-name a { color:#0f172a; }
.ci-event-name a:hover { color:var(--accent); }
.ci-event-meta { font-size:13px; color:var(--muted); margin:2px 0; }
.ci-event-role { display:inline-block; background:#e0f2fe; color:#0369a1; border:1px solid #bae6fd; border-radius:6px; padding:1px 7px; font-size:10.5px; font-weight:600; }

/* SWOT section */
.ci-vs-grid { display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-bottom:16px; }
@media (max-width:700px) { .ci-vs-grid { grid-template-columns:1fr; } }
.ci-vs-box { border-radius:10px; padding:14px 16px; }
.ci-vs-box h4 { margin:0 0 8px; font-size:14px; text-transform:uppercase; letter-spacing:.05em; }
.ci-vs-box ul { margin:0; padding-left:16px; }
.ci-vs-box ul li { font-size:15px; margin-bottom:5px; line-height:1.45; }
.ci-vs-strength { background:#f0fdf4; border:1px solid #bbf7d0; }
.ci-vs-strength h4 { color:#15803d; }
.ci-vs-strength ul li::marker { color:#16a34a; }
.ci-vs-weakness { background:#fff1f2; border:1px solid #fecdd3; }
.ci-vs-weakness h4 { color:#b91c1c; }
.ci-vs-weakness ul li::marker { color:#dc2626; }

/* Customers */
.ci-customers-wrap { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:14px 18px; margin-bottom:16px; }
.ci-customers { display:flex; flex-wrap:wrap; gap:8px; margin-top:8px; }
.ci-customer-card { background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:7px 12px; display:flex; flex-direction:column; gap:2px; min-width:130px; }
.ci-customer-name { font-size:15px; font-weight:700; color:#1e293b; text-decoration:none; }
a.ci-customer-name:hover { color:#2563eb; text-decoration:underline; }
.ci-customer-date { font-size:13px; color:#94a3b8; }

/* Wireless protocol matrix */
.ci-proto-wrap { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:14px 18px; margin-bottom:16px; }
.ci-proto-grid { display:flex; flex-wrap:wrap; gap:8px; margin:8px 0 10px; }
.ci-proto-badge { display:inline-flex; align-items:center; gap:5px; padding:4px 11px; border-radius:16px; font-size:12px; font-weight:700; border:1.5px solid; }
.ci-proto-yes  { background:#dcfce7; border-color:#86efac; color:#166534; }
.ci-proto-no   { background:#f1f5f9; border-color:#cbd5e1; color:#94a3b8; }
.ci-proto-plan { background:#fef9c3; border-color:#fde047; color:#854d0e; }
.ci-proto-chips { display:flex; flex-wrap:wrap; gap:6px; margin-top:6px; }
.ci-proto-chip-tag { background:#f0f9ff; border:1px solid #bae6fd; color:#0369a1; border-radius:8px; padding:4px 12px; font-size:15px; font-weight:700; text-decoration:none; display:inline-block; transition:background .15s,transform .1s; }
.ci-proto-chip-tag:hover { background:#e0f2fe; transform:translateY(-1px); text-decoration:underline; }
.ci-proto-chip-tag.t154 { background:#faf5ff; border-color:#d8b4fe; color:#6d28d9; }
.ci-proto-chip-tag.t154:hover { background:#f3e8ff; }
.ci-proto-stack { font-size:15px; color:#64748b; margin-top:6px; }
.ci-proto-note  { font-size:14px; color:#64748b; font-style:italic; margin-top:6px; background:#f8fafc; border-left:3px solid #e2e8f0; padding:4px 8px; border-radius:0 4px 4px 0; }

/* Company news feed */
.ci-news-feed-wrap { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:14px 18px; margin-bottom:16px; }
.ci-news-feed { display:flex; flex-direction:column; gap:8px; margin-top:8px; max-height:340px; overflow-y:auto; }
.ci-news-item { display:flex; flex-direction:column; gap:2px; padding:8px 10px; border-radius:8px; background:#f8fafc; border:1px solid #f1f5f9; transition:background .15s; }
.ci-news-item:hover { background:#f0f9ff; }
.ci-news-item a { font-size:15px; font-weight:600; color:#1e40af; text-decoration:none; line-height:1.35; }
.ci-news-item a:hover { text-decoration:underline; }
.ci-news-meta { display:flex; gap:8px; align-items:center; font-size:13px; color:#94a3b8; }
.ci-news-bucket { background:#e0f2fe; color:#0369a1; border-radius:10px; padding:1px 7px; font-weight:700; font-size:10.5px; }
.ci-no-news { color:#94a3b8; font-size:15px; font-style:italic; padding:8px 0; }

/* News card grid (mirrors main news tab + customers page) */
.oc-news-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(290px,1fr)); gap:16px; margin-top:12px; }
.oc-news-grid .card { margin:0; }

/* Secondary table */
.ci-secondary { margin-top:32px; }
.ci-secondary h2 { font-size:17px; margin-bottom:10px; color:#374151; }
</style>
""" + _PASSWORD_GATE_HTML + """
</head><body>
""" + _NAV_HTML + """
{% set priority_comps = competitors | selectattr('priority') | list %}
{% set other_comps = competitors | rejectattr('priority') | list %}

<main class="wrap content">

<!-- ── Anchor Bar ── -->
<div class="ci-anchor-bar" style="display:none;"></div>

<!-- ── Stats bar ── -->
<div class="ci-stats-bar">
  <div class="ci-stat-pill"><div class="v">{{ priority_comps|length }}</div><div class="l">Deep-dive</div></div>
  <div class="ci-stat-pill"><div class="v">{{ competitors|length }}</div><div class="l">Total monitored</div></div>
  <div class="ci-stat-pill"><div class="v">{{ news_counts.values()|sum }}</div><div class="l">News articles (30d)</div></div>
  <div class="ci-stat-pill"><div class="v">3</div><div class="l">Regions covered</div></div>
  <div class="ci-stat-pill" style="flex:1;min-width:200px;align-items:flex-start;">
    <div style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px;">Data note</div>
    <div style="font-size:11.5px;color:var(--muted);">Revenue &amp; segment mix are estimates from public filings and analyst data (FY2024\u201325). Verify before quoting.</div>
  </div>
</div>

<!-- ── Main layout ── -->
<div class="ci-layout">

  <!-- Sidebar -->
  <aside class="ci-sidebar">
    <div class="ci-sidebar-hdr">Deep-Dive Competitors</div>
    {% for c in competitors %}
    {% set vc = vendor_colors.get(c.vendor, '#6b7280') %}
    {% if not c.priority and loop.index0 == priority_comps|length %}
    <div class="ci-sidebar-hdr" style="margin-top:4px;font-size:10.5px;">Also Monitored</div>
    {% endif %}
    <button class="ci-tab{% if loop.first %} active{% endif %}" data-panel="{{ loop.index0 }}" style="{% if loop.first %}border-left:3px solid {{ vc }};{% endif %}">
      <span class="ci-avatar" style="background:{{ vc }}">{{ c.vendor[0] }}</span>
      <div class="ci-tab-info">
        <strong>{{ c.vendor }}</strong>
        <div class="ci-tab-region">{{ region_labels[c.region] }}{% if c.revenue_fy %} &nbsp;\u00b7&nbsp; {{ c.revenue_fy }}{% endif %}</div>
      </div>
      <span class="ci-news-badge">{{ news_counts.get(c.vendor, 0) }}</span>
    </button>
    {% endfor %}
  </aside>

  <!-- Detail panels -->
  <div class="ci-panels">
    {% for c in competitors %}
    {% set vc = vendor_colors.get(c.vendor, '#6b7280') %}
    {% if c.priority %}
    <!-- Full deep-dive panel -->
    <div class="ci-panel{% if loop.first %} active{% endif %}" id="panel-{{ loop.index0 }}">

      <!-- 1. Header -->
      <div class="ci-header" style="border-left:4px solid {{ vc }};">
        <div class="ci-header-left">
          <div class="ci-avatar-lg" style="background:{{ vc }};">{{ c.vendor[0] }}</div>
          <div>
            <h2 style="color:{{ vc }};">{{ c.vendor }}</h2>
            <div class="ci-meta">
              &#x1F4CD; {{ c.hq }}&nbsp;&nbsp;&middot;&nbsp;&nbsp;&#x1F465; {{ c.employees }}&nbsp;&nbsp;&middot;&nbsp;&nbsp;
              {% if c.ticker %}&#x1F4C8; {{ c.ticker }}&nbsp;&nbsp;&middot;&nbsp;&nbsp;{% endif %}
              &#x1F4B0; {{ c.revenue_fy }}
            </div>
            <a href="{{ c.website }}" target="_blank" rel="noopener" class="ci-website-link">{{ c.website }} \u2197</a>
          </div>
        </div>
        <a class="ci-news-count" href="news.html" title="View latest news for {{ c.vendor }} on the News page">
          <div class="ci-nc-num">{{ news_counts.get(c.vendor, 0) }}</div>
          <div class="ci-nc-label">news<br>30-day</div>
        </a>
      </div>

      <!-- 2. Positioning -->
      <div class="ci-positioning">&ldquo;{{ c.positioning }}&rdquo;</div>

      <!-- 3. Products + Revenue side-by-side -->
      <div class="ci-grid-2">
        <div>
          <div class="ci-section-h">&#x1F527; Headline Products</div>
          <div class="ci-products">
            {% for p in c.headline_products %}
            <div class="ci-product-card">
              <div class="ci-product-sku">{{ p.sku }}</div>
              <div class="ci-product-type">{{ p.type }}</div>
              <div class="ci-product-links">
                {% if p.site %}<a href="{{ p.site }}" target="_blank" rel="noopener">Product page \u2197</a>{% endif %}
                {% if p.datasheet %}&nbsp;&middot;&nbsp;<a href="{{ p.datasheet }}" target="_blank" rel="noopener">Datasheet \u2197</a>{% endif %}
              </div>
            </div>
            {% endfor %}
          </div>
        </div>
        <div>
          <div class="ci-section-h">&#x1F4CA; IoT Revenue Mix <span class="ci-est-badge">estimated</span></div>
          <div class="ci-seg-bars">
            {% for s in c.segment_revenue %}
            <div class="ci-seg-row">
              <span class="ci-seg-label">{{ s.label }}</span>
              <div class="ci-seg-track"><div class="ci-seg-fill" style="width:{{ s.pct }}%;background:{{ seg_colors.get(s.key, '#94a3b8') }};"></div></div>
              <span class="ci-seg-pct">{{ s.pct }}%</span>
            </div>
            {% endfor %}
          </div>
          {% if c.segment_revenue_note %}
          <p class="ci-seg-note">{{ c.segment_revenue_note }}</p>
          {% endif %}
        </div>
      </div>

      <!-- 4. Press releases + Events -->
      <div class="ci-grid-2">
        <div>
          <div class="ci-section-h">&#x1F4F0; Press Releases</div>
          <div class="ci-timeline">
            {% for pr in c.press_releases %}
            <div class="ci-pr-item">
              <span class="ci-pr-date">{{ pr.date }}</span>
              {% if pr.url %}
              <a href="{{ pr.url }}" target="_blank" rel="noopener" class="ci-pr-title">{{ pr.title }}</a>
              {% else %}
              <span class="ci-pr-title">{{ pr.title }}</span>
              {% endif %}
            </div>
            {% endfor %}
          </div>
        </div>
        <div>
          <div class="ci-section-h">&#x1F5D3; Upcoming Events</div>
          <div class="ci-events">
            {% for ev in c.events %}
            <div class="ci-event-card">
              <div class="ci-event-name"><a href="{{ ev.url }}" target="_blank" rel="noopener">{{ ev.name }}</a></div>
              <div class="ci-event-meta">{{ ev.date }}&nbsp;&nbsp;&middot;&nbsp;&nbsp;{{ ev.location }}</div>
              <span class="ci-event-role">{{ ev.role }}</span>
            </div>
            {% endfor %}
          </div>
        </div>
      </div>

      <!-- 6. SWOT -->
      <div class="ci-section-h" style="margin-bottom:10px;">\u26a1 Strength/Weakness</div>
      <div class="ci-vs-grid">
        <div class="ci-vs-box ci-vs-strength">
          <h4>\u2714 Strengths: {{ c.vendor }}</h4>
          <ul>{% for s in c.vs_airoc_strengths %}<li>{{ s }}</li>{% endfor %}</ul>
        </div>
        <div class="ci-vs-box ci-vs-weakness">
          <h4>\u2717 Weaknesses: {{ c.vendor }}</h4>
          <ul>{% for s in c.vs_airoc_weaknesses %}<li>{{ s }}</li>{% endfor %}</ul>
        </div>
      </div>

      <!-- 7. Key customers -->
      <div class="ci-customers-wrap">
        <div class="ci-section-h">&#x1F3E2; Key Design-Win Customers</div>
        <div class="ci-customers">
          {% for k in c.key_customers %}
          <div class="ci-customer-card">
            {% if k.url %}
            <a class="ci-customer-name" href="{{ k.url }}" target="_blank" rel="noopener">{{ k.name }}</a>
            {% else %}
            <span class="ci-customer-name">{{ k.name if k.name is defined else k }}</span>
            {% endif %}
            {% if k.date %}<span class="ci-customer-date">Design win: {{ k.date }}</span>{% endif %}
          </div>
          {% endfor %}
        </div>
      </div>

      <!-- 8. Wireless protocol support -->
      {% if c.wireless_protocols %}
      {% set wp = c.wireless_protocols %}
      <div class="ci-proto-wrap">
        <div class="ci-section-h">&#x1F4F6; Bluetooth &amp; 802.15.4 Protocol Support</div>
        <div class="ci-proto-grid">
          <span class="ci-proto-badge ci-proto-yes">&#x2705; BLE {{ wp.bt_version }}</span>
          {% if wp.bt_classic %}<span class="ci-proto-badge ci-proto-yes">&#x2705; BT Classic</span>{% else %}<span class="ci-proto-badge ci-proto-no">&#x2716; BT Classic</span>{% endif %}
          {% if wp.le_audio %}<span class="ci-proto-badge ci-proto-yes">&#x2705; LE Audio</span>{% else %}<span class="ci-proto-badge ci-proto-no">&#x2716; LE Audio</span>{% endif %}
          {% if wp.channel_sounding %}<span class="ci-proto-badge ci-proto-yes">&#x2705; Channel Sounding</span>{% else %}<span class="ci-proto-badge ci-proto-plan">&#x23F3; CS Planned</span>{% endif %}
          {% for proto in wp.protocols %}
            {% if '802.15.4' in proto or 'Thread' in proto or 'Matter' in proto or 'Zigbee' in proto %}
            <span class="ci-proto-badge ci-proto-yes">&#x2705; {{ proto }}</span>
            {% endif %}
          {% endfor %}
        </div>
        <div class="ci-grid-2" style="margin-top:10px;">
          <div>
            <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;">Key BT Chips</div>
            <div class="ci-proto-chips">
              {% for chip in wp.key_bt_chips %}
              {% if chip.url %}<a href="{{ chip.url }}" target="_blank" rel="noopener" class="ci-proto-chip-tag">{{ chip.name }}</a>
              {% else %}<span class="ci-proto-chip-tag">{{ chip if chip is string else chip.name }}</span>{% endif %}
              {% endfor %}
              {% if not wp.key_bt_chips %}<span style="color:#94a3b8;font-size:14px;">None</span>{% endif %}
            </div>
          </div>
          <div>
            <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;">Key 802.15.4 Chips</div>
            <div class="ci-proto-chips">
              {% for chip in wp.key_154_chips %}
              {% if chip.url %}<a href="{{ chip.url }}" target="_blank" rel="noopener" class="ci-proto-chip-tag t154">{{ chip.name }}</a>
              {% else %}<span class="ci-proto-chip-tag t154">{{ chip if chip is string else chip.name }}</span>{% endif %}
              {% endfor %}
              {% if not wp.key_154_chips %}<span style="color:#94a3b8;font-size:14px;">None</span>{% endif %}
            </div>
          </div>
        </div>
        <div class="ci-proto-stack">&#x1F4E6; Stack: {{ wp.stack }}</div>
        {% if wp.notes %}<div class="ci-proto-note">{{ wp.notes }}</div>{% endif %}
      </div>
      {% endif %}

    </div>
    {% else %}
    <!-- Simplified panel for non-priority competitors -->
    <div class="ci-panel" id="panel-{{ loop.index0 }}">
      <div class="ci-header" style="border-left:4px solid {{ vc }};">
        <div class="ci-header-left">
          <div class="ci-avatar-lg" style="background:{{ vc }};">{{ c.vendor[0] }}</div>
          <div>
            <h2 style="color:{{ vc }};">{{ c.vendor }}</h2>
            <div class="ci-meta"><span class="tag tag-region-{{ c.region }}">{{ region_labels[c.region] }}</span></div>
            {% if c.website %}<a href="{{ c.website }}" target="_blank" rel="noopener" class="ci-website-link">{{ c.website }} \u2197</a>{% endif %}
          </div>
        </div>
        <a class="ci-news-count" href="news.html" title="View latest news for {{ c.vendor }} on the News page">
          <div class="ci-nc-num">{{ news_counts.get(c.vendor, 0) }}</div>
          <div class="ci-nc-label">news<br>30-day</div>
        </a>
      </div>
      <div class="ci-grid-2">
        <div>
          <div class="ci-section-h">&#x1F527; Headline Products</div>
          <div class="ci-products">
            {% for p in c.headline_products %}
            <div class="ci-product-card">
              <div class="ci-product-sku">{{ p.sku }}</div>
              <div class="ci-product-type">{{ p.type }}</div>
              <div class="ci-product-links">
                {% if p.site %}<a href="{{ p.site }}" target="_blank" rel="noopener">Product page \u2197</a>{% endif %}
                {% if p.datasheet %}&nbsp;&middot;&nbsp;<a href="{{ p.datasheet }}" target="_blank" rel="noopener">Datasheet \u2197</a>{% endif %}
              </div>
            </div>
            {% endfor %}
          </div>
        </div>
        <div>
          <div class="ci-vs-grid" style="grid-template-columns:1fr;gap:10px;">
            <div class="ci-vs-box ci-vs-strength">
              <h4>\u2714 Strengths: {{ c.vendor }}</h4>
              <ul>{% for s in c.vs_airoc_strengths %}<li>{{ s }}</li>{% endfor %}</ul>
            </div>
            <div class="ci-vs-box ci-vs-weakness">
              <h4>\u2717 Weaknesses: {{ c.vendor }}</h4>
              <ul>{% for s in c.vs_airoc_weaknesses %}<li>{{ s }}</li>{% endfor %}</ul>
            </div>
          </div>
        </div>
      </div>
      <div class="ci-customers-wrap">
        <div class="ci-section-h">&#x1F3E2; Key Customers</div>
        <div class="ci-customers">
          {% for k in c.key_customers %}<span class="ci-customer-tag">{{ k }}</span>{% endfor %}
        </div>
      </div>
    </div>
    {% endif %}
    {% endfor %}
  </div><!-- /.ci-panels -->

</div><!-- /.ci-layout -->

</main>
<footer class="footer"><div class="wrap">Data source: <code>data/competitors.json</code> &nbsp;&middot;&nbsp; Segment revenue is estimated from public filings (FY2024\u201325). Verify before external use.</div></footer>

<script>
(function(){
  var tabs   = document.querySelectorAll('.ci-tab');
  var panels = document.querySelectorAll('.ci-panel');
  tabs.forEach(function(tab){
    tab.addEventListener('click', function(){
      var idx = this.dataset.panel;
      var vc  = this.querySelector('.ci-avatar').style.background;
      tabs.forEach(function(t){ t.classList.remove('active'); t.style.borderLeft = ''; });
      panels.forEach(function(p){ p.classList.remove('active'); });
      this.classList.add('active');
      this.style.borderLeft = '3px solid ' + vc;
      var panel = document.getElementById('panel-' + idx);
      if(panel){ panel.classList.add('active'); }
    });
  });
})();
function timeAgo(iso){
  var s=iso; if(s&&s.length===10)s+='T00:00:00Z';
  var d=new Date(s); if(isNaN(d)) return iso;
  var sec=Math.floor((Date.now()-d.getTime())/1000); if(sec<0)sec=0;
  if(sec<45) return 'just now';
  var m=Math.floor(sec/60); if(m<60) return m+(m===1?' min ago':' mins ago');
  var h=Math.floor(m/60); if(h<24) return h+(h===1?' hour ago':' hours ago');
  var day=Math.floor(h/24); if(day<7) return day+(day===1?' day ago':' days ago');
  if(day<30){var w=Math.floor(day/7); return w+(w===1?' week ago':' weeks ago');}
  if(day<365){var mo=Math.floor(day/30); return mo+(mo===1?' month ago':' months ago');}
  var y=Math.floor(day/365); return y+(y===1?' year ago':' years ago');
}
document.querySelectorAll('.time[data-ts]').forEach(function(el){el.textContent=timeAgo(el.dataset.ts); el.title=el.dataset.ts;});
</script>
</body></html>
"""

# ---------------------------------------------------------------- relationships template (Sankey)
_RELATIONSHIPS_TEMPLATE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Relationships \u00b7 IoT Wireless Intel</title>
<style>{{ css }}
.sankey-wrap { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:18px; }
.sankey-wrap svg { width:100%; height:auto; display:block; }
.legend { font-size:12px; color:var(--muted); margin-top:10px; display:flex; gap:14px; flex-wrap:wrap; }
.legend span { display:inline-flex; align-items:center; gap:5px; }
.legend i { display:inline-block; width:12px; height:12px; border-radius:3px; }
</style>
""" + _PASSWORD_GATE_HTML + """
</head><body>
""" + _NAV_HTML + """
<main class="wrap content">
<section class="hero">
  <h1>Vendor &harr; IoT Customer Relationships</h1>
  <p>Verified IoT-only mappings. Each row requires at least one news article whose text contains an IoT context cue (Matter / Thread / smart home / wearable / automotive / industrial-IoT / Bluetooth LE Audio / Wi-Fi 6E/7 / etc.) and which is <em>not</em> about phones, laptops, datacenters, baseband modems, or financial commentary. Width of each ribbon &asymp; number of evidence articles.</p>
</section>

<div class="sankey-wrap">
  <svg id="sankey" viewBox="0 0 1200 700" preserveAspectRatio="xMinYMin meet"></svg>
  <div class="legend">
    <span>Each chip vendor has its own color \u2014 ribbons inherit the vendor's hue</span>
    <span>Hover a ribbon to highlight \u00b7 thicker = stronger relationship</span>
  </div>
</div>

<section class="section">
  <h2>Top relationships ({{ links|length }} total)</h2>
  <table class="tbl">
    <thead><tr><th style="width:140px;">Vendor</th><th style="width:200px;">Customer</th><th style="width:80px;">Strength</th><th>Strength Breakdown</th><th>Sources (links)</th></tr></thead>
    <tbody>
    {% for l in links[:60] %}
      <tr>
        <td><strong>{{ l.vendor }}</strong>{% if l.vendor == 'Infineon' %} <span class="tag">Infineon</span>{% endif %}</td>
        <td>{{ l.customer }}</td>
        <td>{{ l.weight }}</td>
        <td>{{ l.strength_explained }}</td>
        <td>
          {% if l.evidence %}
            <ul>
            {% for e in l.evidence %}
              <li><a href="{{ e.url }}" target="_blank" rel="noopener">{{ e.title }}</a> <span class="muted">({{ e.source }} {{ e.date }})</span></li>
            {% endfor %}
            </ul>
          {% endif %}
          {% if 'seed' in l.sources %}<span class="tag">seed mapping</span>{% endif %}
        </td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</section>

</main>
<footer class="footer"><div class="wrap">Powered by d3-sankey \u00b7 data co-derived from news + seeds</div></footer>

<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
<script src="https://cdn.jsdelivr.net/npm/d3-sankey@0.12"></script>
<script>
const links = {{ links_json|safe }};
if (links.length === 0) {
  document.getElementById('sankey').innerHTML = '<text x="20" y="40" fill="#888">No relationships detected yet.</text>';
} else {
  const vendors = [...new Set(links.map(l => l.vendor))];
  const customers = [...new Set(links.map(l => l.customer))];
  const nodes = [
    ...vendors.map(v => ({ name: v, kind: 'vendor' })),
    ...customers.map(c => ({ name: c, kind: 'customer' }))
  ];
  const idx = name => nodes.findIndex(n => n.name === name);
  const sankeyLinks = links.map(l => ({ source: idx(l.vendor), target: nodes.findIndex(n => n.name === l.customer && n.kind === 'customer'), value: l.weight }));

  const width = 1200, height = Math.max(700, nodes.length * 22);
  const svg = d3.select('#sankey').attr('viewBox', `0 0 ${width} ${height}`);
  const sankey = d3.sankey().nodeWidth(18).nodePadding(12).extent([[140, 20], [width - 140, height - 20]]);
  const graph = sankey({ nodes: nodes.map(d => ({...d})), links: sankeyLinks.map(d => ({...d})) });

  // Distinct color per vendor (Tableau10 + Set3 = 22 hues)
  const palette = d3.schemeTableau10.concat(d3.schemeSet3 || []);
  const vendorColor = d3.scaleOrdinal().domain(vendors).range(palette);

  // Gradient defs so each ribbon fades vendor color -> customer color
  const defs = svg.append('defs');
  graph.links.forEach((d, i) => {
    d.gradId = 'lg' + i;
    const g = defs.append('linearGradient')
      .attr('id', d.gradId).attr('gradientUnits', 'userSpaceOnUse')
      .attr('x1', d.source.x1).attr('x2', d.target.x0);
    g.append('stop').attr('offset', '0%').attr('stop-color', vendorColor(d.source.name));
    g.append('stop').attr('offset', '100%').attr('stop-color', d3.color(vendorColor(d.source.name)).brighter(0.6).formatHex());
  });

  svg.append('g').attr('fill', 'none').selectAll('path').data(graph.links).join('path')
    .attr('d', d3.sankeyLinkHorizontal())
    .attr('stroke', d => `url(#${d.gradId})`)
    .attr('data-vendor-color', d => vendorColor(d.source.name))
    .attr('stroke-opacity', 0.55)
    .attr('stroke-width', d => Math.max(1.5, d.width))
    .style('mix-blend-mode', 'multiply')
    .style('cursor', 'pointer')
    .on('mouseover', function(){
        d3.select(this).attr('stroke', '#000').attr('stroke-opacity', 1).style('mix-blend-mode', 'normal');
    })
    .on('mouseout',  function(){
        const c = d3.select(this);
        c.attr('stroke', `url(#${c.datum().gradId})`).attr('stroke-opacity', 0.55).style('mix-blend-mode', 'multiply');
    })
    .append('title').text(d => `${d.source.name} \u2192 ${d.target.name}\\nstrength: ${d.value}`);

  const node = svg.append('g').selectAll('g').data(graph.nodes).join('g');
  node.append('rect')
    .attr('x', d => d.x0).attr('y', d => d.y0)
    .attr('height', d => d.y1 - d.y0).attr('width', d => d.x1 - d.x0)
    .attr('fill', d => d.kind === 'vendor' ? vendorColor(d.name) : '#475569')
    .attr('stroke', '#fff').attr('stroke-width', 1)
    .append('title').text(d => `${d.name}\\ntotal: ${d.value}`);
  node.append('text')
    .attr('x', d => d.kind === 'vendor' ? d.x0 - 6 : d.x1 + 6)
    .attr('y', d => (d.y0 + d.y1) / 2)
    .attr('dy', '0.35em')
    .attr('text-anchor', d => d.kind === 'vendor' ? 'end' : 'start')
    .style('font-size', '12px').style('font-weight', '600')
    .text(d => d.name);
}
</script>
</body></html>
"""

# ---------------------------------------------------------------- main render
PAGE_DESCS = {
    "news":      "Latest IoT wireless news across all chip vendors, OEMs, customers and applications.",
    "wifi":      "Wi-Fi 6E/7/8, MLO, HaLow \u2014 vendor chips and customer wins.",
    "bluetooth": "Bluetooth 6.0, LE Audio, Auracast, Channel Sounding, Coded PHY, profiles & open-source stacks.",
    "ieee15_4":  "IEEE 802.15.4 radios, Zigbee, multiprotocol SoCs.",
    "zigbee":    "Zigbee mesh + ZCL clusters on 802.15.4 \u2014 lighting, sensors, building automation.",
    "aliro":     "Aliro digital-key spec from CSA \u2014 NFC + UWB + Bluetooth LE access.",
    "thread":    "Thread protocol, OpenThread, Thread 1.4, border routers.",
    "matter":    "Matter spec, certified devices, Matter Casting, ecosystem moves.",
}

_TECHNOLOGY_TEMPLATE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wireless Technology \u00b7 IoT Wireless Intel</title>
<style>{{ css }}
.tech-tabs { display:flex; gap:6px; flex-wrap:wrap; margin:16px 0 0; border-bottom:1px solid var(--border); padding-bottom:0; }
.tech-tab { cursor:pointer; border:1px solid var(--border); border-bottom:none; background:#f1f5f9; color:#334155; font-weight:700; font-size:13.5px; padding:9px 18px; border-radius:10px 10px 0 0; }
.tech-tab:hover { background:#e2e8f0; }
.tech-tab.active { background:var(--card); color:var(--accent); border-color:var(--border); position:relative; top:1px; }
.tech-panel { display:none; background:var(--card); border:1px solid var(--border); border-radius:0 10px 10px 10px; padding:22px 24px; margin-top:-1px; }
.tech-panel.active { display:block; }
.tech-panel .tagline { color:var(--muted); font-size:14px; margin:2px 0 14px; }
.spec-snapshot { display:flex; gap:10px; flex-wrap:wrap; align-items:center; background:#f9fafc; border:1px solid var(--border); border-radius:8px; padding:10px 14px; margin-bottom:18px; font-size:12.5px; }
.spec-snapshot b { color:#0f172a; }
.tech-h2 { font-size:16.5px; margin:26px 0 4px; padding-top:14px; border-top:1px solid var(--border); display:flex; align-items:center; gap:8px; }
.tech-h2:first-of-type { border-top:none; padding-top:0; margin-top:6px; }
.tech-overview { font-size:14px; line-height:1.65; color:#1f2937; margin:6px 0 0; }

/* Architecture stack diagram */
.stack { display:flex; flex-direction:column; gap:3px; margin-top:12px; }
.stack-layer { display:flex; gap:12px; align-items:flex-start; background:#fafbfd; border:1px solid var(--border); border-left:4px solid var(--accent); border-radius:8px; padding:10px 14px; text-decoration:none; transition:transform .12s ease, box-shadow .12s ease; }
.stack-layer:hover { transform:translateY(-1px); box-shadow:0 8px 20px rgba(15,23,42,.08); }
.stack-layer .tag { flex:none; width:56px; text-align:center; font-size:10.5px; font-weight:800; color:#fff; border-radius:5px; padding:4px 2px; letter-spacing:.03em; }
.stack-layer .body strong { display:block; font-size:13.5px; color:#0f172a; margin-bottom:2px; }
.stack-layer .body span { font-size:12.5px; color:#4b5563; line-height:1.5; }
.stack-arrow { text-align:center; color:var(--muted); font-size:11px; margin:-1px 0; }
.stack-layer:nth-child(4n+1) { background:linear-gradient(90deg,#e0f2fe,#f8fafc); border-left-color:#0284c7; }
.stack-layer:nth-child(4n+1) .tag { background:#0284c7; }
.stack-layer:nth-child(4n+2) { background:linear-gradient(90deg,#ecfccb,#f8fafc); border-left-color:#65a30d; }
.stack-layer:nth-child(4n+2) .tag { background:#65a30d; }
.stack-layer:nth-child(4n+3) { background:linear-gradient(90deg,#ffe4e6,#f8fafc); border-left-color:#e11d48; }
.stack-layer:nth-child(4n+3) .tag { background:#e11d48; }
.stack-layer:nth-child(4n+4) { background:linear-gradient(90deg,#ede9fe,#f8fafc); border-left-color:#7c3aed; }
.stack-layer:nth-child(4n+4) .tag { background:#7c3aed; }

.layer-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(290px, 1fr)); gap:10px; margin-top:12px; }
.layer-card { background:#fff; border:1px solid var(--border); border-radius:10px; padding:12px; scroll-margin-top:84px; }
.layer-card h3 { margin:0 0 6px; font-size:13.5px; color:#0f172a; }
.layer-card p { margin:0; font-size:12.5px; color:#4b5563; line-height:1.6; }
.layer-card .chips { display:flex; flex-wrap:wrap; gap:6px; margin-top:8px; }
.layer-card .chips span { font-size:11px; font-weight:700; color:#334155; background:#f1f5f9; border:1px solid #e2e8f0; border-radius:999px; padding:2px 8px; }

.deep-grid { display:grid; grid-template-columns:1fr; gap:10px; margin-top:12px; }
.deep-card { background:#fffdf5; border:1px solid #f4e7c4; border-radius:10px; padding:12px 14px; }
.deep-card h3 { margin:0 0 5px; font-size:13.5px; color:#7c2d12; }
.deep-card p { margin:0; font-size:12.5px; color:#4b5563; line-height:1.6; }

/* Core concepts glossary */
.concept-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(280px, 1fr)); gap:10px; margin-top:12px; }
.concept-card { background:#fafbfd; border:1px solid var(--border); border-radius:8px; padding:10px 12px; }
.concept-card .term { font-weight:700; font-size:13px; color:#0f172a; margin-bottom:3px; }
.concept-card .def { font-size:12.5px; color:#4b5563; line-height:1.5; }

/* How it works steps */
.steps { display:flex; flex-direction:column; gap:8px; margin-top:12px; }
.step { display:flex; gap:12px; background:#fafbfd; border:1px solid var(--border); border-radius:8px; padding:10px 14px; }
.step .num { flex:none; width:26px; height:26px; border-radius:50%; background:#eef2ff; color:#3730a3; font-weight:800; font-size:12px; display:flex; align-items:center; justify-content:center; }
.step .st-body strong { display:block; font-size:13px; color:#0f172a; }
.step .st-body span { font-size:12.5px; color:#4b5563; line-height:1.5; }

/* Developer view cards */
.dev-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(270px, 1fr)); gap:10px; margin-top:12px; }
.dev-card { background:#fdf4ff; border:1px solid #f3e8ff; border-radius:8px; padding:10px 12px; }
.dev-card .dt { font-weight:700; font-size:13px; color:#6b21a8; margin-bottom:3px; }
.dev-card .dd { font-size:12.5px; color:#4b5563; line-height:1.5; }

.usecase-chips { display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }
.usecase-chips span { background:#dcfce7; color:#166534; font-size:12px; font-weight:600; padding:5px 12px; border-radius:999px; }

.resource-list { margin:12px 0 0; padding:0; list-style:none; }
.resource-list li { padding:6px 0; border-bottom:1px dashed var(--border); font-size:13px; }
.resource-list li:last-child { border-bottom:none; }

/* Vibrant hero + tabs */
.tech-hero { background:linear-gradient(120deg,#4f46e5,#0ea5e9 55%,#06b6d4); color:#fff; border-radius:16px; padding:26px 28px; margin:14px 0 6px; box-shadow:0 18px 40px rgba(2,132,199,.18); }
.tech-hero h1 { margin:0 0 6px; font-size:27px; letter-spacing:-.01em; color:#fff; }
.tech-hero p { margin:0; font-size:14px; line-height:1.6; color:#eaf2ff; max-width:840px; }
.tech-tab.active { background:linear-gradient(180deg,#ffffff,#eef2ff); color:var(--accent); }

/* Architecture block diagram (SAP / interface style) */
.arch { margin-top:12px; }
.arch-planes { display:flex; justify-content:space-between; font-size:11px; font-weight:800; letter-spacing:.03em; margin:2px 2px 8px; }
.arch-planes .pl.mgmt { color:#b45309; }
.arch-planes .pl.data { color:#1d4ed8; }
.arch-block { border-radius:12px; padding:14px 16px; color:#fff; box-shadow:0 10px 24px rgba(15,23,42,.14); position:relative; overflow:hidden; }
.arch-block .ab-name { font-size:15px; font-weight:800; letter-spacing:.01em; }
.arch-block .ab-sub { font-size:12px; margin-top:3px; opacity:.96; line-height:1.5; }
.arch-block.k-upper  { background:linear-gradient(120deg,#6d28d9,#8b5cf6); }
.arch-block.k-nwk    { background:linear-gradient(120deg,#0f766e,#14b8a6); }
.arch-block.k-mac    { background:linear-gradient(120deg,#1d4ed8,#3b82f6); }
.arch-block.k-phy    { background:linear-gradient(120deg,#047857,#10b981); }
.arch-block.k-medium { background:linear-gradient(120deg,#334155,#64748b); }
.arch-conn { display:flex; align-items:center; justify-content:center; gap:34px; padding:9px 0; position:relative; }
.arch-conn::before { content:""; position:absolute; top:0; bottom:0; left:50%; width:2px; transform:translateX(-50%); background:repeating-linear-gradient(#cbd5e1 0 5px, transparent 5px 10px); }
.sap { position:relative; z-index:1; font-size:11px; font-weight:800; padding:4px 11px; border-radius:999px; border:1px solid transparent; background:#fff; box-shadow:0 2px 7px rgba(15,23,42,.12); }
.sap.mgmt { color:#b45309; border-color:#fde68a; background:#fffbeb; }
.sap.data { color:#1d4ed8; border-color:#bfdbfe; background:#eff6ff; }
.sap.iface { color:#0f172a; border-color:#e2e8f0; background:#f8fafc; }
.arch-cap { font-size:12px; color:#475569; line-height:1.6; margin:14px 2px 0; padding:10px 13px; background:#f8fafc; border:1px solid var(--border); border-left:3px solid var(--accent); border-radius:8px; }
</style>
""" + _PASSWORD_GATE_HTML + """
</head><body>
""" + _NAV_HTML + """
<main class="wrap content">
<section class="tech-hero">
  <h1>Wireless Technology \u2014 Learn the Stacks</h1>
  <p>A hands-on tutorial for each protocol we track: a colorful architecture block diagram with the real layer interfaces, clickable layers that jump to deep-dive explanations, core concepts, how the protocol actually works step by step, and what an application developer builds against. Pick a technology below.</p>
</section>

<div class="tech-tabs" id="techTabs">
  {% for t in tech_tutorials %}
  <div class="tech-tab {{ 'active' if loop.first else '' }}" data-slug="{{ t.slug }}">{{ t.label }}</div>
  {% endfor %}
</div>

{% for t in tech_tutorials %}
<div class="tech-panel {{ 'active' if loop.first else '' }}" id="panel-{{ t.slug }}">
  <p class="tagline">{{ t.tagline }}</p>

  {% if t.current_version or t.next_version %}
  <div class="spec-snapshot">
    <span><b>Current:</b> {{ t.current_version or '\u2014' }}</span>
    <span><b>Next:</b> {{ t.next_version or '\u2014' }}</span>
    {% if t.spec_url %}<a href="{{ t.spec_url }}" target="_blank" rel="noopener">Official spec &rarr;</a>{% endif %}
  </div>
  {% endif %}

  <h2 class="tech-h2">\U0001F4D6 Overview</h2>
  <p class="tech-overview">{{ t.overview }}</p>

  {% if t.block_diagram %}
  <h2 class="tech-h2">\U0001F9F1 Architecture Block Diagram</h2>
  <div class="arch">
    {% if t.block_diagram.blocks[0].mgmt %}
    <div class="arch-planes"><span class="pl mgmt">&#9664; Management plane (LME SAPs)</span><span class="pl data">Data plane (data SAPs) &#9654;</span></div>
    {% endif %}
    {% for b in t.block_diagram.blocks %}
    <div class="arch-block k-{{ b.kind }}">
      <div class="ab-name">{{ b.name }}</div>
      {% if b.sub %}<div class="ab-sub">{{ b.sub }}</div>{% endif %}
    </div>
    {% if not loop.last %}
    <div class="arch-conn">
      {% if b.iface %}<span class="sap iface">{{ b.iface }}</span>
      {% else %}<span class="sap mgmt">{{ b.mgmt or '' }}</span><span class="sap data">{{ b.data or '' }}</span>{% endif %}
    </div>
    {% endif %}
    {% endfor %}
    {% if t.block_diagram.caption %}<p class="arch-cap">{{ t.block_diagram.caption }}</p>{% endif %}
  </div>
  {% endif %}

  <h2 class="tech-h2">\U0001F3D7\uFE0F Layer-by-layer Responsibilities</h2>
  <p class="tech-overview" style="margin-bottom:0">Click any layer to jump to its detailed explanation below.</p>
  <div class="stack">
    {% for layer in t.architecture %}
    <a class="stack-layer" href="#{{ t.slug }}-layer-{{ loop.index }}" title="Jump to {{ layer.name }} details">
      <span class="tag">{{ layer.tag }}</span>
      <div class="body"><strong>{{ layer.name }}</strong><span>{{ layer.function }}</span></div>
    </a>
    {% if not loop.last %}<div class="stack-arrow">&#8595;</div>{% endif %}
    {% endfor %}
  </div>

  {% if t.layer_details %}
  <h2 class="tech-h2">\U0001F50E Layer Deep Dive (clickable from stack)</h2>
  <div class="layer-grid">
    {% for ld in t.layer_details %}
    <article class="layer-card" id="{{ t.slug }}-layer-{{ loop.index }}">
      <h3>{{ ld.title }}</h3>
      <p>{{ ld.detail }}</p>
      {% if ld.points %}
      <div class="chips">{% for p in ld.points %}<span>{{ p }}</span>{% endfor %}</div>
      {% endif %}
    </article>
    {% endfor %}
  </div>
  {% endif %}

  <h2 class="tech-h2">\U0001F4DA Core Concepts</h2>
  <div class="concept-grid">
    {% for c in t.core_concepts %}
    <div class="concept-card"><div class="term">{{ c.term }}</div><div class="def">{{ c.definition }}</div></div>
    {% endfor %}
  </div>

  <h2 class="tech-h2">\u2699\uFE0F How It Works</h2>
  <div class="steps">
    {% for s in t.how_it_works %}
    <div class="step"><span class="num">{{ loop.index }}</span><div class="st-body"><strong>{{ s.title }}</strong><span>{{ s.detail }}</span></div></div>
    {% endfor %}
  </div>

  <h2 class="tech-h2">\U0001F468\u200D\U0001F4BB For Application Developers</h2>
  <div class="dev-grid">
    {% for d in t.developer_view %}
    <div class="dev-card"><div class="dt">{{ d.title }}</div><div class="dd">{{ d.detail }}</div></div>
    {% endfor %}
  </div>

  {% if t.zigbee_in_depth %}
  <h2 class="tech-h2">\U0001F9E9 Zigbee In Depth</h2>
  <div class="deep-grid">
    {% for z in t.zigbee_in_depth %}
    <article class="deep-card"><h3>{{ z.title }}</h3><p>{{ z.detail }}</p></article>
    {% endfor %}
  </div>
  {% endif %}

  {% if t.thread_in_depth %}
  <h2 class="tech-h2">\U0001F9F5 OpenThread / Thread In Depth</h2>
  <div class="deep-grid">
    {% for th in t.thread_in_depth %}
    <article class="deep-card"><h3>{{ th.title }}</h3><p>{{ th.detail }}</p></article>
    {% endfor %}
  </div>
  {% endif %}

  <h2 class="tech-h2">\U0001F4A1 Common Use Cases</h2>
  <div class="usecase-chips">
    {% for u in t.use_cases %}<span>{{ u }}</span>{% endfor %}
  </div>

  <h2 class="tech-h2">\U0001F517 Learn More</h2>
  <ul class="resource-list">
    {% for r in t.resources %}<li><a href="{{ r.url }}" target="_blank" rel="noopener">{{ r.label }}</a></li>{% endfor %}
  </ul>
</div>
{% endfor %}

</main>
<footer class="footer"><div class="wrap">Wireless Technology tutorial \u00b7 hand-curated, not news-driven \u00b7 spec versions verified {{ generated_at }} PDT</div></footer>
<script>
(function(){
  var tabs = document.querySelectorAll('.tech-tab');
  var panels = document.querySelectorAll('.tech-panel');
  tabs.forEach(function(tab){
    tab.addEventListener('click', function(){
      var slug = this.dataset.slug;
      tabs.forEach(function(t){ t.classList.remove('active'); });
      panels.forEach(function(p){ p.classList.remove('active'); });
      this.classList.add('active');
      var panel = document.getElementById('panel-' + slug);
      if (panel) panel.classList.add('active');
    });
  });
})();
</script>
</body></html>
"""


PINNED_CUSTOMERS = ["Google", "Amazon", "Apple", "Microsoft", "Meta", "Samsung",
                    "Sony", "LG", "Motorola", "Bose", "Sonos", "Sennheiser", "Bang & Olufsen",
                    "Marshall", "Ultimate Ears", "Harman Kardon",
                    "Arlo", "SimpliSafe", "Wyze", "Ecobee", "Eufy/Anker", "Aqara",
                    "Garmin", "Whoop", "Oura", "GoPro",
                    "Xiaomi", "Huawei", "Tesla", "BMW", "HKMC", "Toyota", "Ford"]
PINNED_APPS = ["Smart Home", "Industrial", "Automotive", "Wearable",
               "AR / VR / XR", "Smart Glasses", "Audio / Speaker"]


def _write_news_cache(articles: list[dict]) -> None:
    """Persist the current top news articles for the dynamic /api/news endpoint."""
    data_dir = Path(__file__).resolve().parents[2] / "data"
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        payload = []
        for a in articles:
            pub = a.get("published")
            payload.append({
                "title": a.get("title") or "",
                "url": a.get("url") or "",
                "source": a.get("source") or "",
                "summary": a.get("summary") or "",
                "thumb": a.get("thumb") or "",
                "buckets": [b for b in (a.get("buckets") or []) if b],
                "vendor": a.get("vendor") or "",
                "customer": a.get("customer") or "",
                "application": a.get("application") or "",
                "standard": a.get("standard") or "",
                "published": pub.isoformat() if pub else "",
            })
        (data_dir / "news_cache.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass


def _curated_standard_cards() -> list[dict]:
    """Build always-present 'Standards' cards from the curated standards.json
    watchlist (spec adopted, next version, roadmap features, official link) so
    every technology family has authoritative spec/roadmap content even when
    the live standards-body feeds are quiet."""
    path = Path(__file__).resolve().parents[2] / "data" / "standards.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    entries = data.get("standards", []) or []
    bt = wifi = combo = uwb = None
    for e in entries:
        fam = e.get("family", "")
        if fam == "Bluetooth":
            bt = e
        elif fam == "Wi-Fi":
            wifi = e
        elif "802.15.4" in fam or "Thread" in fam or "Matter" in fam:
            combo = e
        elif "UWB" in fam or "Aliro" in fam:
            uwb = e
    label_map = {slug: label for slug, label in BUCKETS}
    # (slug, source entry, keyword to filter roadmap features by, or None)
    plan = [
        ("bluetooth", bt, None),
        ("wifi", wifi, None),
        ("matter", combo, "matter"),
        ("thread", combo, "thread"),
        ("ieee15_4", combo, "zigbee"),
        ("aliro", uwb, None),
    ]
    cards: list[dict] = []
    for slug, e, kw in plan:
        if not e:
            continue
        feats = e.get("in_flight_features", []) or []
        sel = [f for f in feats if kw in f.lower()] if kw else feats
        if not sel:
            sel = feats
        summary = (
            f"Current: {e.get('current_version', '')}. "
            f"Next: {e.get('next_version', '')}. "
            f"Roadmap: " + " · ".join(sel[:4])
        )
        pub = None
        lv = e.get("last_verified")
        if lv:
            try:
                pub = datetime.fromisoformat(lv).replace(tzinfo=timezone.utc)
            except ValueError:
                pub = None
        cards.append({
            "title": f"{label_map.get(slug, slug)} standard — spec & roadmap ({e.get('body', 'SDO')})",
            "url": e.get("url", ""),
            "source": e.get("body", "Standards body"),
            "summary": summary,
            "thumb": "",
            "buckets": [slug],
            "vendor": "", "vendor_region": "",
            "customer": "", "application": "",
            "standard": slug,
            "published": pub,
        })
    return cards


def render(articles: list[dict], output_dir: Path,
           pulse: list[dict] | None = None,
           patents: list[dict] | None = None,
           filings: list[dict] | None = None) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=BaseLoader(), autoescape=select_autoescape(["html"]))

    now_pdt = datetime.now(timezone.utc).astimezone(PDT)
    generated_at = now_pdt.strftime("%Y-%m-%d %H:%M")
    bucket_labels = {slug: label for slug, label in BUCKETS}
    news_slugs = ["news"] + [b for b, _ in BUCKETS]
    region_groups_def = vendors_by_region()
    customers_order = all_customers()
    apps_order = all_applications()

    common_ctx = dict(
        css=_BASE_CSS, generated_at=generated_at,
        buckets=BUCKETS, bucket_labels=bucket_labels, news_slugs=news_slugs,
        region_labels=REGION_LABELS,
    )

    def _filters(items: list[dict]):
        v_count = Counter(a["vendor"] for a in items if a.get("vendor"))
        c_count = Counter(a["customer"] for a in items if a.get("customer"))
        a_count = Counter(a["application"] for a in items if a.get("application"))
        r_count = Counter(a["vendor_region"] for a in items if a.get("vendor_region"))
        s_count = Counter(a["standard"] for a in items if a.get("standard"))

        vendor_groups = []
        for region_slug, names in region_groups_def:
            present = [(n, v_count.get(n, 0)) for n in names]
            if present:
                vendor_groups.append((region_slug, REGION_LABELS[region_slug], present, r_count.get(region_slug, 0)))
        vendor_total = sum(1 for v in v_count if v_count[v] > 0)

        c_tabs: list = [(n, c_count.get(n, 0)) for n in PINNED_CUSTOMERS]
        for n in customers_order:
            if n not in PINNED_CUSTOMERS and c_count.get(n, 0) > 0:
                c_tabs.append((n, c_count[n]))
        a_tabs: list = [(n, a_count.get(n, 0)) for n in PINNED_APPS]
        for n in apps_order:
            if n not in PINNED_APPS and a_count.get(n, 0) > 0:
                a_tabs.append((n, a_count[n]))
        # Standards families always shown in the fixed BUCKETS order.
        s_tabs: list = [(slug, bucket_labels[slug], s_count.get(slug, 0)) for slug, _ in BUCKETS]
        s_total = sum(s_count.values())
        return vendor_groups, vendor_total, c_tabs, a_tabs, s_tabs, s_total

    news_template = env.from_string(_NEWS_TEMPLATE)

    # --- All News page ---
    # Render ALL articles (not just top 50) so the sidebar customer/competitor
    # counts match the cards that can actually be filtered/shown. Previously the
    # page rendered only the top 50 by recency while the sidebar counts were
    # computed from every article, so clicking a customer/competitor filtered an
    # incomplete DOM and often showed an empty result set.
    articles_by_recency = sorted(
        articles, key=lambda a: a.get("published") or datetime.min.replace(tzinfo=timezone.utc), reverse=True
    )
    # Curated standards cards are always shown so every family has spec/roadmap
    # content; live standards-body news is appended on top.
    curated_standards = _curated_standard_cards()
    news_articles = curated_standards + articles_by_recency
    news_by_recency = sorted(
        news_articles, key=lambda a: a.get("published") or datetime.min.replace(tzinfo=timezone.utc), reverse=True
    )
    vg, vt, ct, at, st, stot = _filters(news_articles)
    (output_dir / "news.html").write_text(news_template.render(
        page_title="All News", page_desc=PAGE_DESCS["news"],
        articles=news_by_recency, active="news",
        vendor_groups=vg, vendor_total=vt, customer_tabs=ct, app_tabs=at,
        standard_tabs=st, standard_total=stot, **common_ctx,
    ), encoding="utf-8")
    _write_news_cache(articles_by_recency)

    # --- Per-bucket news pages ---
    for slug, label in BUCKETS:
        items = [a for a in news_articles if slug in a["buckets"]]
        vg, vt, ct, at, st, stot = _filters(items)
        (output_dir / f"{slug}.html").write_text(news_template.render(
            page_title=label + " News", page_desc=PAGE_DESCS.get(slug, ""),
            articles=items, active=slug,
            vendor_groups=vg, vendor_total=vt, customer_tabs=ct, app_tabs=at,
            standard_tabs=st, standard_total=stot, **common_ctx,
        ), encoding="utf-8")

    # --- Technology page (hand-crafted tutorials, versions merged from standards.json) ---
    standards_path = Path(__file__).resolve().parents[2] / "data" / "standards.json"
    standards_map: dict[str, dict] = {}
    if standards_path.exists():
      try:
        standards_raw = json.loads(standards_path.read_text(encoding="utf-8"))
        for row in (standards_raw.get("standards") or []):
          standards_map[(row.get("family") or "").lower()] = row
      except (OSError, json.JSONDecodeError):
        standards_map = {}

    tech_tutorials = []
    for t in TECH_TUTORIALS:
      std = standards_map.get(t.get("spec_family", ""), {})
      tech_tutorials.append({
        **t,
        "current_version": std.get("current_version", ""),
        "next_version": std.get("next_version", ""),
        "spec_url": std.get("url", ""),
      })

    _tab_order = ["bluetooth", "ieee15_4", "zigbee", "thread", "wifi", "matter", "aliro"]
    tech_tutorials.sort(key=lambda x: _tab_order.index(x["slug"]) if x["slug"] in _tab_order else 99)

    (output_dir / "technology.html").write_text(env.from_string(_TECHNOLOGY_TEMPLATE).render(
      tech_tutorials=tech_tutorials, active="technology", **common_ctx
    ), encoding="utf-8")

    # --- Customers page ---
    customers = load_customers()
    cust_news_counts = Counter(a["customer"] for a in articles if a.get("customer"))
    customer_live: dict[str, list[dict]] = {c.get("name", ""): [] for c in customers}
    for a in sorted(articles, key=lambda x: x.get("published") or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
      cname = a.get("customer")
      if not cname or cname not in customer_live:
        continue
      customer_live[cname].append({
        "date": a.get("published").strftime("%Y-%m-%d") if a.get("published") else "",
        "title": a.get("title") or "article",
        "url": a.get("url"),
        "source": a.get("source") or "",
        "thumb": (a.get("thumb") or "").strip(),
        "summary": (a.get("summary") or "")[:220],
        "buckets": [b for b in (a.get("buckets") or []) if b],
      })
    from .sources import FEATURED_ARTICLES
    featured_urls = set(FEATURED_ARTICLES)

    for cname in list(customer_live.keys()):
      seen = set()
      deduped = []
      for row in customer_live[cname]:
        u = row.get("url")
        if not u or u in seen:
          continue
        seen.add(u)
        deduped.append(row)

      # Keep featured URLs visible even when a customer has many newer items.
      pinned = [r for r in deduped if (r.get("url") or "") in featured_urls]
      rest = [r for r in deduped if (r.get("url") or "") not in featured_urls]
      customer_live[cname] = (pinned + rest)[:20]
    predictions = predict_customer_releases(customers, articles, mode="conservative")
    customers_html = env.from_string(_CUSTOMERS_TEMPLATE).render(
      customers=customers, customer_live=customer_live,
      predictions=predictions,
      news_counts=cust_news_counts, active="opportunity", **common_ctx,
    )
    (output_dir / "opportunity.html").write_text(customers_html, encoding="utf-8")
    # Keep legacy URL for backward compatibility.
    (output_dir / "customers.html").write_text(customers_html, encoding="utf-8")

    # --- Competitors page ---
    comp = load_competitors()
    # Sort press_releases reverse-chronologically for every competitor
    for _c in comp.get("competitors", []):
        prs = _c.get("press_releases") or []
        if prs:
            _c["press_releases"] = sorted(
                prs, key=lambda p: _parse_press_date(p.get("date", "")), reverse=True
            )
    vendor_news_counts = Counter(a["vendor"] for a in articles if a.get("vendor"))
    _WIRELESS_BUCKETS = {"bluetooth", "ieee15_4", "thread", "matter", "aliro", "wifi"}
    vendor_news: dict[str, list[dict]] = {}
    for a in articles:
        v = a.get("vendor")
        if not v:
            continue
        bucket_label = ", ".join(
            b.replace("ieee15_4", "802.15.4").replace("aliro", "Aliro")
             .replace("thread", "Thread").replace("matter", "Matter")
             .replace("bluetooth", "Bluetooth")
            for b in (a.get("buckets") or []) if b in _WIRELESS_BUCKETS
        )
        entry = {
            "title": a.get("title", ""),
            "url": a.get("url", ""),
            "source": a.get("source", ""),
            "published": a["published"].strftime("%b %d, %Y") if a.get("published") else "",
            "published_iso": a["published"].strftime("%Y-%m-%d") if a.get("published") else "",
            "bucket_label": bucket_label,
            "buckets": [b for b in (a.get("buckets") or []) if b in _WIRELESS_BUCKETS],
            "thumb": (a.get("thumb") or "").strip(),
            "summary": (a.get("summary") or "")[:220],
        }
        vendor_news.setdefault(v, []).append(entry)
    # Keep latest 20 per vendor
    vendor_news = {v: items[:20] for v, items in vendor_news.items()}

    # Replace placeholder search URLs in static press-release data with direct
    # article links from live vendor news when possible.
    for c in comp.get("competitors", []):
      vendor = c.get("vendor", "")
      for pr in (c.get("press_releases") or []):
        current_url = (pr.get("url") or "").strip()
        if not _is_placeholder_search_url(current_url):
          continue
        resolved_url = _resolve_direct_press_url(vendor, pr.get("title", ""), vendor_news)
        # If no reliable direct URL is found, keep it non-clickable instead
        # of sending users to a generic search page.
        pr["url"] = resolved_url or ""

    # Fallback: if a vendor has no live articles in this run, use static press releases
    # so competitor panels remain populated instead of showing an empty state.
    for c in comp.get("competitors", []):
        v = c.get("vendor")
        if not v or vendor_news.get(v):
            continue
        fallback = []
        for pr in (c.get("press_releases") or [])[:8]:
            fallback.append({
                "title": pr.get("title", ""),
                "url": pr.get("url", ""),
                "source": "Press release",
                "published": pr.get("date", ""),
                "published_iso": "",
                "bucket_label": "",
                "buckets": [],
                "thumb": "",
                "summary": "",
            })
        if fallback:
            vendor_news[v] = fallback

    competitors_html = env.from_string(_COMPETITORS_TEMPLATE).render(
        anchor=comp.get("anchor", {}), competitors=comp.get("competitors", []),
        news_counts=vendor_news_counts, vendor_news=vendor_news,
      active="threat", **common_ctx,
    )
    (output_dir / "threat.html").write_text(competitors_html, encoding="utf-8")
    # Keep legacy URL for backward compatibility.
    (output_dir / "competitors.html").write_text(competitors_html, encoding="utf-8")

    # --- Relationships page ---
    links = build_links(articles, iot_only=True)
    (output_dir / "relationships.html").write_text(env.from_string(_RELATIONSHIPS_TEMPLATE).render(
        links=links, links_json=json.dumps(links), active="relationships", **common_ctx,
    ), encoding="utf-8")

    # --- Research pages ---
    pulse = pulse or []
    patents = patents or []
    filings = filings or []
    from .research_pages import _render_research_pages
    _render_research_pages(env, output_dir, common_ctx, articles, comp,
                           pulse, patents, filings)

    # --- Index = Overview ---
    (output_dir / "index.html").write_text(_render_index(env, common_ctx, articles, customers, comp, links), encoding="utf-8")

    # Normalize visible terminology across all generated HTML pages.
    _neutralize_site_outputs(output_dir)

    # --- Post-process: rewrite Google News RSS redirect URLs to working
    #     Google-search URLs (the rss/articles/... links don't open in
    #     a browser; they return an interstitial). Done in-place across
    #     every rendered page using a lightweight regex.
    _rewrite_broken_links(output_dir)

    return output_dir / "index.html"


_GNEWS_HREF_RE = re.compile(
    r'href="(https://(?:www\.)?news\.google\.com/rss/articles/[^"]+)"([^>]*)>([^<]*)</a>',
    re.IGNORECASE,
)


def _rewrite_broken_links(output_dir: Path) -> None:
    from urllib.parse import urlparse, parse_qs, unquote

    def _sub(m: re.Match) -> str:
        orig_href = m.group(1)
        attrs = m.group(2)
        # Prefer explicit target URL if present in query params.
        parsed = urlparse(orig_href)
        qs = parse_qs(parsed.query)
        target = unquote((qs.get("url") or [""])[0]).strip()
        href = target if target.startswith(("http://", "https://")) else orig_href
        return f'href="{href}"{attrs}>{m.group(3)}</a>'

    for html in output_dir.glob("*.html"):
        try:
            src = html.read_text(encoding="utf-8")
        except OSError:
            continue
        new = _GNEWS_HREF_RE.sub(_sub, src)
        if new != src:
            html.write_text(new, encoding="utf-8")
 

def _neutralize_site_html(text: str) -> str:
    text = text.replace("airoc_unlock_v1", "site_unlock_v1")
    text = text.replace("stack-tag.airoc", "stack-tag.platform")
    replacements = [
      (re.compile(r'Infineon AIROC(?:™)?', re.IGNORECASE), 'Platform'),
      (re.compile(r'\bAIROC(?:™)?\b', re.IGNORECASE), 'Platform'),
      (re.compile(r'\bvs\s+Infineon\b', re.IGNORECASE), 'vs platform'),
      (re.compile(r'\bInfineon\b'), ''),
        (re.compile(r'\bAIROC\s+position\b', re.IGNORECASE), 'Platform position'),
        (re.compile(r'\bAIROC\s+roadmap\b', re.IGNORECASE), 'Platform roadmap'),
        (re.compile(r'\bAIROC\s+Bluetooth\s+stack\b', re.IGNORECASE), 'Bluetooth stack'),
    ]
    for pattern, replacement in replacements:
        text = pattern.sub(replacement, text)
    return text


def _neutralize_site_outputs(output_dir: Path) -> None:
    for html in output_dir.rglob("*.html"):
        try:
            original = html.read_text(encoding="utf-8")
        except OSError:
            continue
        updated = _neutralize_site_html(original)
        if updated != original:
            html.write_text(updated, encoding="utf-8")


_INDEX_TEMPLATE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Overview \u00b7 IoT Wireless Intel</title>
<style>{{ css }}
.kpi-row { display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:14px; margin:18px 0; }
.kpi { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:16px 18px; }
.kpi h3 { margin:0 0 6px; font-size:11.5px; color:var(--muted); text-transform:uppercase; letter-spacing:.08em; font-weight:700; }
.kpi .v { font-size:30px; font-weight:800; color:var(--accent); line-height:1; }
.kpi .delta { font-size:12px; margin-top:4px; font-weight:600; }
.kpi .delta.up { color:#15803d; }
.kpi .delta.down { color:#b91c1c; }
.kpi .delta.flat { color:var(--muted); }

.two-col { display:grid; grid-template-columns:1.4fr 1fr; gap:18px; margin:18px 0; }
@media (max-width: 900px) { .two-col { grid-template-columns:1fr; } }

.headline-list { list-style:none; padding:0; margin:0; }
.headline-list li { padding:11px 0; border-bottom:1px solid var(--border); }
.headline-list li:last-child { border-bottom:none; }
.headline-list a { font-weight:600; color:var(--text); font-size:14.5px; line-height:1.4; }
.headline-list a:hover { color:var(--accent); }
.headline-list .meta { font-size:11.5px; color:var(--muted); margin-top:3px; display:flex; gap:6px; flex-wrap:wrap; align-items:center; }

.heatmap { width:100%; border-collapse:collapse; font-size:12.5px; }
.heatmap th, .heatmap td { padding:6px 8px; text-align:center; border:1px solid var(--border); }
.heatmap th { background:#f9fafc; font-weight:600; font-size:11.5px; text-transform:uppercase; letter-spacing:.04em; }
.heatmap th.row-h, .heatmap td.row-h { text-align:left; font-weight:600; background:#f9fafc; }
.heatmap td.cell { font-variant-numeric:tabular-nums; color:#1a1f2c; font-weight:600; }
.heatmap td.c0 { color:#cbd5e1; font-weight:400; }

.movers { list-style:none; padding:0; margin:0; }
.movers li { display:flex; justify-content:space-between; align-items:center; padding:8px 0; border-bottom:1px dashed var(--border); }
.movers li:last-child { border-bottom:none; }
.movers .name { font-weight:600; }
.movers .bar { flex:1; margin:0 12px; height:6px; background:#e2e8f0; border-radius:3px; overflow:hidden; }
.movers .bar i { display:block; height:100%; background:linear-gradient(90deg,#7c3aed,#db2777); }
.movers .n { font-variant-numeric:tabular-nums; color:var(--muted); font-size:12.5px; min-width:30px; text-align:right; }

.radar { display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:10px; margin-top:8px; }
.radar .item { background:#fafbfd; border:1px solid var(--border); border-left:3px solid var(--accent); border-radius:6px; padding:10px 12px; font-size:13px; }
.radar .item .src { display:block; font-size:11px; color:var(--muted); font-weight:600; margin-bottom:3px; text-transform:uppercase; letter-spacing:.04em; }

.jump-row { display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:14px; margin-top:14px; }
.jump-card { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:18px; transition:all .15s; display:block; color:inherit; }
.jump-card:hover { border-color:var(--accent); transform:translateY(-2px); box-shadow:0 8px 24px rgba(0,0,0,.06); text-decoration:none; }
.jump-card h3 { margin:0 0 4px; font-size:15px; color:var(--accent); }
.jump-card p { margin:0; font-size:12.5px; color:var(--muted); line-height:1.45; }
.section-head { display:flex; align-items:center; justify-content:space-between; gap:10px; flex-wrap:wrap; }
.section-head h2 { margin:0; }
.section-sub { color:var(--muted); font-size:13px; margin:2px 0 0; }

/* Competitive battlecard */
.battle-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(290px, 1fr)); gap:14px; margin-top:12px; }
.battle-card { background:var(--card); border:1px solid var(--border); border-top:3px solid var(--accent); border-radius:10px; padding:14px 16px; display:flex; flex-direction:column; }
.battle-card h3 { margin:0 0 2px; font-size:15.5px; display:flex; align-items:center; justify-content:space-between; gap:6px; }
.battle-card .region-tag { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); background:#f1f5f9; padding:2px 8px; border-radius:999px; }
.battle-list { list-style:none; margin:8px 0; padding:0; }
.battle-list li { font-size:12.5px; padding:4px 0 4px 20px; position:relative; line-height:1.4; color:#1f2937; }
.battle-list li.win::before { content:"\u2713"; position:absolute; left:0; color:#16a34a; font-weight:800; }
.battle-list li.watch::before { content:"\u26a0"; position:absolute; left:0; color:#d97706; font-weight:800; font-size:11px; }
.battle-press { font-size:11.5px; color:var(--muted); border-top:1px dashed var(--border); margin-top:auto; padding-top:8px; }
.battle-press a { color:var(--text); font-weight:600; }
.battle-press a:hover { color:var(--accent); }
.battle-link { font-size:12px; margin-top:10px; display:inline-block; font-weight:600; }

/* Strength/Weakness radar (win vs respond) */
.opp-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:12px; }
@media (max-width: 800px) { .opp-grid { grid-template-columns:1fr; } }
.opp-col { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:14px 16px; }
.opp-col.win { border-left:4px solid #16a34a; }
.opp-col.watch { border-left:4px solid #d97706; }
.opp-col h3 { margin:0 0 4px; font-size:14.5px; }
.opp-col .section-sub { margin-bottom:8px; }
.opp-item { font-size:13px; padding:7px 0; border-bottom:1px dashed var(--border); }
.opp-item:last-child { border-bottom:none; }
.opp-item b { color:var(--text); }

/* Customer radar */
.cust-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:14px; margin-top:12px; }
.cust-card { background:var(--card); border:1px solid var(--border); border-top:3px solid #db2777; border-radius:10px; padding:14px 16px; }
.cust-card .hd { display:flex; align-items:center; justify-content:space-between; gap:8px; }
.cust-card h3 { margin:0; font-size:15px; }
.conf-badge { font-size:10px; font-weight:700; padding:3px 9px; border-radius:999px; white-space:nowrap; }
.conf-high { background:#dcfce7; color:#166534; }
.conf-medium { background:#fef3c7; color:#92400e; }
.conf-low { background:#f1f5f9; color:#475569; }
.cust-app { font-size:11.5px; color:var(--muted); margin:4px 0 8px; text-transform:uppercase; letter-spacing:.04em; font-weight:700; }
.cust-product { font-size:13px; font-weight:600; margin:0 0 6px; }
.feat-chip { display:inline-block; background:#eef2ff; color:#3730a3; font-size:10.5px; padding:2px 8px; border-radius:999px; margin:2px 4px 2px 0; }
.cust-basis { font-size:11px; color:var(--muted); margin-top:8px; border-top:1px dashed var(--border); padding-top:6px; }
.cust-links { margin-top:10px; display:flex; flex-wrap:wrap; gap:8px; }
.cust-links a { font-size:12px; font-weight:600; color:var(--accent); text-decoration:none; }
.cust-links a:hover { text-decoration:underline; }
.cust-signal { margin-top:8px; font-size:11px; color:var(--muted); }
.cust-evidence { margin:8px 0 0; padding-left:16px; }
.cust-evidence li { margin:4px 0; font-size:12px; color:#334155; }
.cust-evidence a { color:#1e40af; text-decoration:none; }
.cust-evidence a:hover { text-decoration:underline; }

/* Technology & standards radar */
.std-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(300px, 1fr)); gap:14px; margin-top:12px; }
.std-card { background:var(--card); border:1px solid var(--border); border-top:3px solid #7c3aed; border-radius:10px; padding:14px 16px; }
.std-card h3 { margin:0 0 8px; font-size:15px; }
.std-version-row { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:8px; }
.std-pill { font-size:10.5px; padding:3px 10px; border-radius:999px; background:#eef2ff; color:#3730a3; font-weight:700; }
.std-pill.next { background:#fce7f3; color:#9d174d; }
.std-feat-list { margin:0 0 8px; padding:0; list-style:none; }
.std-feat-list li { font-size:12px; margin:3px 0; padding-left:14px; position:relative; color:#374151; }
.std-feat-list li::before { content:"\u2022"; position:absolute; left:0; color:var(--accent); font-weight:800; }
.std-position { font-size:11.5px; color:var(--muted); font-style:italic; margin:8px 0 0; border-top:1px dashed var(--border); padding-top:8px; }
.std-activity { font-size:11px; color:var(--muted); margin-top:6px; }

.stack-table { width:100%; border-collapse:separate; border-spacing:0; margin-top:12px; font-size:12.5px; }
.stack-table th, .stack-table td { text-align:left; vertical-align:top; padding:8px 10px; border-bottom:1px solid var(--border); }
.stack-table th { background:#f9fafc; font-size:11px; text-transform:uppercase; letter-spacing:.04em; color:#64748b; }
.stack-table td:first-child { font-weight:700; white-space:nowrap; }
.stack-tag { font-size:10px; font-weight:700; border-radius:999px; padding:2px 7px; margin-left:6px; border:1px solid transparent; }
.stack-tag.platform { background:#dcfce7; border-color:#bbf7d0; color:#166534; }
.stack-tag.oss { background:#eef2ff; border-color:#c7d2fe; color:#3730a3; }

/* Compact market signal feed */
.signal-feed { display:grid; grid-template-columns:1fr 1fr; gap:0 24px; margin-top:10px; }
@media (max-width: 800px) { .signal-feed { grid-template-columns:1fr; } }
.signal-col h3 { font-size:13px; margin:0 0 4px; }
.signal-row { display:flex; gap:9px; padding:7px 0; border-bottom:1px solid var(--border); align-items:flex-start; }
.signal-row:last-child { border-bottom:none; }
.signal-dot { width:7px; height:7px; border-radius:50%; margin-top:6px; flex:none; }
.signal-dot.vendor { background:#d97706; }
.signal-dot.customer { background:#db2777; }
.signal-body { flex:1; min-width:0; }
.signal-title { font-size:12.5px; font-weight:600; color:var(--text); display:block; }
.signal-title:hover { color:var(--accent); }
.signal-meta { font-size:10.5px; color:var(--muted); }

.mini-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:12px; margin-top:10px; }
.mini-card { background:#fafbfd; border:1px solid var(--border); border-radius:10px; padding:12px; }
.mini-card h3 { margin:0 0 4px; font-size:14px; }
.mini-card p { margin:0 0 8px; font-size:12px; color:var(--muted); }
.mini-list { margin:0; padding-left:16px; }
.mini-list li { margin:5px 0; font-size:13px; }
.mini-meta { font-size:11.5px; color:var(--muted); }
</style>
""" + _PASSWORD_GATE_HTML + """
</head><body>
""" + _NAV_HTML + """
<main class="wrap content">
<section class="hero">
  <h1>IoT Wireless Intelligence</h1>
  <p>Product-marketing command center for the Infineon wireless platform \u2014 competitor positioning, customer signals, and technology roadmap in one view. Built to help define features, prioritize the roadmap, and find openings against the competition.</p>
</section>

<div class="section">
  <div class="section-head">
    <h2>Data Freshness &amp; Coverage</h2>
  </div>
  <p class="section-sub">Current ingestion depth and signal spread powering this view.</p>
  <div class="mini-grid">
    <article class="mini-card">
      <h3>Ingestion Horizon</h3>
      <p>Article volume by recency window.</p>
      <ul class="mini-list">
        <li><b>{{ freshness_7d }}</b> articles in last 7 days</li>
        <li><b>{{ freshness_30d }}</b> articles in last 30 days</li>
        <li><b>{{ freshness_45d }}</b> articles in last 45 days</li>
      </ul>
    </article>
    <article class="mini-card">
      <h3>Source Breadth</h3>
      <p>How diverse the collected signal is.</p>
      <ul class="mini-list">
        <li><b>{{ unique_sources }}</b> unique publishers/sources</li>
        <li><b>{{ bucket_coverage }}</b>/{{ total_buckets }} technology buckets represented</li>
        <li><b>{{ lookback_span_days }}</b> days between oldest and newest captured article</li>
      </ul>
    </article>
    <article class="mini-card">
      <h3>Market Signal Depth</h3>
      <p>How many entities are backed by recent evidence.</p>
      <ul class="mini-list">
        <li><b>{{ vendors_with_news }}</b> vendors with linked news</li>
        <li><b>{{ customers_with_news }}</b> customers with linked news</li>
        <li><b>{{ latest_article_label }}</b> latest article timestamp</li>
      </ul>
    </article>
  </div>
</div>

<div class="section">
  <div class="section-head">
    <h2>Competitive Battlecard</h2>
    <span class="pill">SWOT</span>
  </div>
  <p class="section-sub">Where we are strongest today and where each rival leads &mdash; use this to sharpen messaging and spot feature gaps.</p>
  <div class="battle-grid">
    {% for c in battlecard %}
    <article class="battle-card">
      <h3>{{ c.vendor }}<span class="region-tag">{{ c.region }}</span></h3>
      {% if c.strengths %}
      <ul class="battle-list">
        {% for s in c.strengths %}<li class="win">{{ s }}</li>{% endfor %}
      </ul>
      {% endif %}
      {% if c.weaknesses %}
      <ul class="battle-list">
        {% for w in c.weaknesses %}<li class="watch">{{ w }}</li>{% endfor %}
      </ul>
      {% endif %}
      {% if c.press %}
      <div class="battle-press">
        {% for pr in c.press %}
          <div>{% if pr.url %}<a href="{{ pr.url }}" target="_blank" rel="noopener">{{ pr.title }}</a>{% else %}{{ pr.title }}{% endif %} &middot; {{ pr.date }}</div>
        {% endfor %}
      </div>
      {% endif %}
      <a class="battle-link" href="threat.html">Full profile &rarr;</a>
    </article>
    {% endfor %}
  </div>
</div>

<div class="section">
  <div class="section-head">
    <h2>Strength/Weakness Radar</h2>
  </div>
  <p class="section-sub">Aggregated across tracked competitors &mdash; where to lean into messaging, and where to close the gap.</p>
  <div class="opp-grid">
    <div class="opp-col win">
      <h3>\u2713 Strengths</h3>
      <p class="section-sub">Lead with these in positioning &amp; sales collateral.</p>
      {% for o in opportunity_wins %}
      <div class="opp-item"><b>{{ o.vendor }}:</b> {{ o.text }}</div>
      {% endfor %}
    </div>
    <div class="opp-col watch">
      <h3>\u26a0 Weaknesses</h3>
      <p class="section-sub">Feature gaps competitors use against us &mdash; candidates for the roadmap.</p>
      {% for o in opportunity_watch %}
      <div class="opp-item"><b>{{ o.vendor }}:</b> {{ o.text }}</div>
      {% endfor %}
    </div>
  </div>
</div>

<div class="section">
  <div class="section-head">
    <h2>Customer Radar</h2>
  </div>
  <p class="section-sub">Model-predicted next launches per OEM, with expected features &mdash; a window into what customers will need next.</p>
  <div class="cust-grid">
    {% for r in customer_radar %}
    <article class="cust-card">
      <div class="hd">
        <h3>{{ r.customer }}</h3>
        <span class="conf-badge conf-{{ r.confidence_label|lower }}">{{ r.confidence_label }} &middot; {{ r.confidence }}%</span>
      </div>
      <div class="cust-app">{{ r.application }}</div>
      <p class="cust-product">{{ r.probable_product }}</p>
      <div>
        {% for f in r.expected_features %}<span class="feat-chip">{{ f }}</span>{% endfor %}
      </div>
      <div class="cust-signal">Recent customer signals (30d): <b>{{ r.recent_signals_30d }}</b></div>
      {% if r.evidence_links %}
      <ul class="cust-evidence">
        {% for ev in r.evidence_links %}
        <li><a href="{{ ev.url }}" target="_blank" rel="noopener">{{ ev.title }}</a> &middot; {{ ev.source }}</li>
        {% endfor %}
      </ul>
      {% endif %}
      {% if r.based_on %}<div class="cust-basis">{{ r.based_on[0] }}</div>{% endif %}
      <div class="cust-links">
        <a href="{{ r.customer_page }}">Customer profile &rarr;</a>
        <a href="{{ r.news_page }}">Customer news feed &rarr;</a>
      </div>
    </article>
    {% endfor %}
  </div>
  {% if not customer_radar %}<p class="muted">Not enough signal yet to project next launches &mdash; check back after the next data refresh.</p>{% endif %}
  <p style="margin-top:12px;"><a href="opportunity.html">All customer profiles &amp; full roadmap table &rarr;</a></p>
</div>

<div class="section">
  <div class="section-head">
    <h2>Bluetooth Stack Positioning &amp; Full Coverage</h2>
  </div>
  <p class="section-sub">Complete tracked customer/competitor coverage plus explicit Infineon Bluetooth stack positioning against Zephyr and BlueZ.</p>

  <table class="stack-table">
    <thead>
      <tr>
        <th>Stack</th>
        <th>Primary Targets</th>
        <th>Positioning Strength</th>
        <th>Trade-off / Gap</th>
        <th>Missing Features</th>
        <th>Best Fit</th>
      </tr>
    </thead>
    <tbody>
      {% for r in stack_positioning %}
      <tr>
        <td>{{ r.stack }}{% if r.kind == 'Platform' %}<span class="stack-tag platform">Infineon</span>{% else %}<span class="stack-tag oss">Open Source</span>{% endif %}</td>
        <td>{{ r.targets }}</td>
        <td>{{ r.strength }}</td>
        <td>{{ r.tradeoff }}</td>
        <td>{{ r.missing_features }}</td>
        <td>{{ r.best_fit }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>

<div class="section">
  <div class="section-head">
    <h2>Technology &amp; Standards Radar</h2>
  </div>
  <p class="section-sub">Current vs. next spec version and in-flight features per domain &mdash; direct input for roadmap planning.</p>
  <div class="std-grid">
    {% for s in standards_radar %}
    <article class="std-card">
      <h3>{{ s.family }}</h3>
      <div class="std-version-row">
        {% if s.current_version %}<span class="std-pill">Now: {{ s.current_version }}</span>{% endif %}
        {% if s.next_version %}<span class="std-pill next">Next: {{ s.next_version }}</span>{% endif %}
      </div>
      {% if s.features %}
      <ul class="std-feat-list">
        {% for f in s.features %}<li>{{ f }}</li>{% endfor %}
      </ul>
      {% endif %}
      {% if s.position %}<p class="std-position">{{ s.position }}</p>{% endif %}
      <div class="std-activity">{{ s.count }} related articles &middot; {{ s.window_label }}{% if s.page %} &middot; <a href="{{ s.page }}" target="_blank" rel="noopener">Open feed &rarr;</a>{% endif %}</div>
    </article>
    {% endfor %}
  </div>
</div>

<div class="section">
  <div class="section-head">
    <h2>Market Signal Feed</h2>
    <span class="pill">{{ competitor_window_label }}</span>
  </div>
  <p class="section-sub">Latest competitor and customer headlines &mdash; supporting evidence for the sections above.</p>
  <div class="signal-feed">
    <div class="signal-col">
      <h3>Competitor signals</h3>
      {% for a in competitor_headlines[:8] %}
      <div class="signal-row">
        <span class="signal-dot vendor"></span>
        <div class="signal-body">
          <a class="signal-title" href="{{ a.url }}" target="_blank" rel="noopener">{{ a.title }}</a>
          <div class="signal-meta">{{ a.vendor }} &middot; {{ a.source }}{% if a.published %} &middot; {{ a.published.strftime('%b %d') }}{% endif %}</div>
        </div>
      </div>
      {% else %}<p class="muted">No competitor headlines yet.</p>{% endfor %}
    </div>
    <div class="signal-col">
      <h3>Customer signals</h3>
      {% for a in customer_headlines[:8] %}
      <div class="signal-row">
        <span class="signal-dot customer"></span>
        <div class="signal-body">
          <a class="signal-title" href="{{ a.url }}" target="_blank" rel="noopener">{{ a.title }}</a>
          <div class="signal-meta">{{ a.customer }} &middot; {{ a.source }}{% if a.published %} &middot; {{ a.published.strftime('%b %d') }}{% endif %}</div>
        </div>
      </div>
      {% else %}<p class="muted">No customer headlines yet.</p>{% endfor %}
    </div>
  </div>
  <p style="margin-top:12px;"><a href="news.html">Browse all news &rarr;</a></p>
</div>

<section class="section">
  <h2>Where do you want to go?</h2>
  <div class="jump-row">
    <a class="jump-card" href="news.html"><h3>News \u2192</h3><p>All recent articles by technology, vendor, customer and application.</p></a>
    <a class="jump-card" href="opportunity.html"><h3>Customers \u2192</h3><p>OEM profiles \u2014 recent products and forward roadmap signals.</p></a>
    <a class="jump-card" href="threat.html"><h3>Strength/Weakness \u2192</h3><p>Side-by-side SWOT comparison \u2014 SKUs, strengths, weaknesses.</p></a>
    <a class="jump-card" href="relationships.html"><h3>Relationships \u2192</h3><p>Sankey map of which vendor sells to which customer.</p></a>
  </div>
</section>

</main>
<footer class="footer"><div class="wrap">IoT Wireless Intel \u00b7 generated {{ generated_at }} PDT</div></footer>
</body></html>
"""


def _render_index(env, ctx, articles, customers, comp, links) -> str:
    now = datetime.now(timezone.utc)
    cutoff_7d = now - timedelta(days=7)
    cutoff_14d = now - timedelta(days=14)

    def _pub(a):
        p = a.get("published")
        if p and p.tzinfo is None:
            p = p.replace(tzinfo=timezone.utc)
        return p

    def _recent(items: list[dict], days: int) -> list[dict]:
        cutoff = now - timedelta(days=days)
        return [a for a in items if _pub(a) and _pub(a) >= cutoff]

    arts_7d = [a for a in articles if _pub(a) and _pub(a) >= cutoff_7d]
    arts_prev_7d = [a for a in articles if _pub(a) and cutoff_14d <= _pub(a) < cutoff_7d]
    arts_30d = _recent(articles, 30)
    arts_45d = _recent(articles, 45)

    published_list = [p for p in (_pub(a) for a in articles) if p]
    latest_article = max(published_list) if published_list else None
    oldest_article = min(published_list) if published_list else None
    lookback_span_days = (latest_article - oldest_article).days if latest_article and oldest_article else 0
    latest_article_label = latest_article.strftime("%Y-%m-%d") if latest_article else "n/a"

    unique_sources = len({(a.get("source") or "").strip() for a in articles if (a.get("source") or "").strip()})
    vendors_with_news = len({(a.get("vendor") or "").strip() for a in articles if (a.get("vendor") or "").strip()})
    customers_with_news = len({(a.get("customer") or "").strip() for a in articles if (a.get("customer") or "").strip()})
    total_buckets = len(BUCKETS)
    bucket_coverage = len({b for a in articles for b in (a.get("buckets") or [])})

    # KPI delta
    n_now, n_prev = len(arts_7d), len(arts_prev_7d)
    if n_prev == 0:
        delta_pct, delta_class, delta_arrow = ("new" if n_now else "\u2014"), "flat", ""
    else:
        pct = (n_now - n_prev) / n_prev * 100
        delta_pct = f"{abs(pct):.0f}%"
        delta_class = "up" if pct > 5 else ("down" if pct < -5 else "flat")
        delta_arrow = "\u25b2" if pct > 5 else ("\u25bc" if pct < -5 else "\u25ac")

    def _unique_by_url(items: list[dict]) -> list[dict]:
        seen = set()
        out = []
        for a in items:
            u = a.get("url")
            if not u or u in seen:
                continue
            seen.add(u)
            out.append(a)
        return out

    bucket_info = {slug: label for slug, label in BUCKETS}

    # --- Competitive battlecard: strengths/weaknesses + latest press per priority competitor
    competitors_list = comp.get("competitors", []) or []
    priority_comps = competitors_list
    battlecard = []
    for c in priority_comps:
        battlecard.append({
            "vendor": c.get("vendor", "Unknown"),
            "region": REGION_LABELS.get(c.get("region", ""), c.get("region", "") or ""),
            "strengths": (c.get("vs_airoc_strengths") or [])[:2],
            "weaknesses": (c.get("vs_airoc_weaknesses") or [])[:2],
            "press": (c.get("press_releases") or [])[:2],
        })

    # --- Strength/Weakness radar: aggregate first strength/weakness across ALL competitors
    opportunity_wins = []
    opportunity_watch = []
    for c in competitors_list:
        vendor = c.get("vendor", "Unknown")
        strengths = c.get("vs_airoc_strengths") or []
        weaknesses = c.get("vs_airoc_weaknesses") or []
        if strengths:
            opportunity_wins.append({"vendor": vendor, "text": strengths[0]})
        if weaknesses:
            opportunity_watch.append({"vendor": vendor, "text": weaknesses[0]})
    opportunity_wins = opportunity_wins[:8]
    opportunity_watch = opportunity_watch[:8]

    # --- Customer radar: model-predicted next launches
    try:
      customer_radar_predicted = predict_customer_releases(customers, articles, mode="balanced")
    except Exception:
      customer_radar_predicted = []

    # Keep predictor output where available, then add fallback rows so all tracked customers appear.
    by_customer = {
      (r.get("customer") or "").strip(): r
      for r in customer_radar_predicted
      if (r.get("customer") or "").strip()
    }
    customer_radar = []
    for c in (customers or []):
      name = (c.get("name") or "").strip()
      if not name:
        continue
      cust_articles = [a for a in articles if (a.get("customer") or "").strip() == name and a.get("url")]
      cust_articles.sort(key=lambda a: (_pub(a) is None, -(_pub(a).timestamp() if _pub(a) else 0)))
      recent_signals_30d = len([a for a in cust_articles if _pub(a) and _pub(a) >= now - timedelta(days=30)])
      evidence_links = [
        {
          "title": (a.get("title") or "Untitled")[:120],
          "url": a.get("url"),
          "source": a.get("source") or "Unknown",
        }
        for a in cust_articles[:3]
      ]
      if name in by_customer:
        row = dict(by_customer[name])
        row["recent_signals_30d"] = recent_signals_30d
        row["evidence_links"] = evidence_links
        row["customer_page"] = "opportunity.html"
        row["news_page"] = "news.html"
        customer_radar.append(row)
        continue

      apps = c.get("applications") or []
      needs = c.get("wireless_needs") or []
      customer_radar.append({
        "customer": name,
        "application": apps[0] if apps else "Connected Device",
        "probable_product": f"{name} wireless product refresh",
        "expected_features": needs[:6],
        "confidence": 35,
        "confidence_label": "Low",
        "based_on": ["Coverage entry: limited recent launch signal in current news window"],
        "recent_signals_30d": recent_signals_30d,
        "evidence_links": evidence_links,
        "customer_page": "opportunity.html",
        "news_page": "news.html",
      })

    # --- Technology & standards radar: current/next version + in-flight features + activity
    standards_path = Path(__file__).resolve().parents[2] / "data" / "standards.json"
    standards_by_family: dict[str, dict] = {}
    if standards_path.exists():
        try:
            standards_raw = json.loads(standards_path.read_text(encoding="utf-8"))
            for row in (standards_raw.get("standards") or []):
                standards_by_family[(row.get("family") or "").lower()] = row
        except (OSError, json.JSONDecodeError):
            standards_by_family = {}

    def _pick_features(items: list[str], keywords: list[str]) -> list[str]:
      if not items:
        return []
      if not keywords:
        return items[:3]
      picked = []
      for feat in items:
        low = feat.lower()
        if any(k in low for k in keywords):
          picked.append(feat)
      return picked[:3] if picked else items[:3]

    STANDARDS_DOMAINS = [
      {
        "label": "Bluetooth",
        "source_key": "bluetooth",
        "bucket_slugs": ["bluetooth"],
        "page": "https://www.bluetooth.com/",
        "feature_keywords": [],
      },
      {
        "label": "Wi-Fi",
        "source_key": "wi-fi",
        "bucket_slugs": ["wifi"],
        "page": "https://www.wi-fi.org/discover-wi-fi",
        "feature_keywords": [],
      },
      {
        "label": "802.15.4",
        "source_key": "802.15.4 / thread / matter",
        "bucket_slugs": ["ieee15_4"],
        "page": "https://www.ieee802.org/15/",
        "feature_keywords": ["802.15.4", "ieee"],
        "features": [
          "Low-power PHY/MAC baseline used under Thread/Zigbee mesh ecosystems",
          "Channel agility and robust coexistence remain central for dense IoT deployments",
          "Interoperability outcomes depend on upper-layer protocol/profile alignment",
        ],
        "current_version": "IEEE 802.15.4 baseline in active low-power mesh deployments",
        "next_version": "Incremental profile updates driven by ecosystem layers",
        "position": "Infineon CYW55573 provides 802.15.4 support as the PHY/MAC base for Thread and Zigbee class networks.",
      },
      {
        "label": "Zigbee",
        "source_key": "802.15.4 / thread / matter",
        "bucket_slugs": ["ieee15_4"],
        "page": "https://csa-iot.org/all-solutions/zigbee/",
        "feature_keywords": ["zigbee"],
        "current_version": "Zigbee ecosystem refresh under CSA (Zigbee 4.0 program messaging)",
        "next_version": "Broader Zigbee 4.0 ecosystem rollout",
        "position": "Infineon 802.15.4 capability is relevant for Zigbee-class low-power mesh designs; confirm Zigbee roadmap alignment.",
      },
      {
        "label": "Thread",
        "source_key": "802.15.4 / thread / matter",
        "bucket_slugs": ["thread"],
        "page": "https://www.threadgroup.org/",
        "feature_keywords": ["thread"],
        "features": [
          "Border-router robustness and commissioning reliability across mixed-vendor homes",
          "Operational mesh stability tuning for larger multi-hop IoT installations",
          "Ongoing alignment with Matter-over-Thread deployment best practices",
        ],
        "current_version": "Thread 1.4 (last publicly verified)",
        "next_version": "Next Thread revision not publicly confirmed",
        "position": "Infineon CYW55573 provides the 802.15.4 foundation for Thread-enabled products; continue certification alignment.",
      },
      {
        "label": "Matter",
        "source_key": "802.15.4 / thread / matter",
        "bucket_slugs": ["matter"],
        "page": "https://csa-iot.org/all-solutions/matter/",
        "feature_keywords": ["matter", "commission"],
        "current_version": "Matter 1.6 (Jun 2026)",
        "next_version": "Matter 1.7 (scope not yet public)",
        "position": "Matter SDK support is in place; prioritize Matter 1.6 features like Joint Fabric and NFC commissioning.",
      },
      {
        "label": "Aliro",
        "source_key": "uwb",
        "bucket_slugs": ["aliro"],
        "page": "https://csa-iot.org/all-solutions/aliro/",
        "feature_keywords": ["aliro", "digital key", "nfc", "uwb"],
        "current_version": "Aliro digital key profile adoption underway (NFC + UWB + BLE)",
        "next_version": "Additional OEM/member Aliro rollouts expected",
      },
    ]
    standards_radar = []
    for domain in STANDARDS_DOMAINS:
        std = standards_by_family.get(domain["source_key"])
        if not std:
            continue

        b7 = [
            a for a in arts_7d
            if any(slug in (a.get("buckets") or []) for slug in domain["bucket_slugs"])
        ]
        b_window = "7d"
        if len(b7) < 2:
            b7 = [
                a for a in _recent(articles, 14)
                if any(slug in (a.get("buckets") or []) for slug in domain["bucket_slugs"])
            ]
            b_window = "14d fallback"

        standards_radar.append({
            "family": domain["label"],
            "current_version": domain.get("current_version", std.get("current_version", "")),
            "next_version": domain.get("next_version", std.get("next_version", "")),
          "features": domain.get("features") or _pick_features(
            std.get("in_flight_features") or [],
            domain.get("feature_keywords", []),
          ),
            "position": domain.get("position", std.get("infineon_position", "")),
            "count": len(b7),
            "window_label": b_window,
            "page": domain["page"],
        })

    # --- Stack positioning (platform vs Zephyr/BlueZ)
    stack_positioning = [
        {
            "stack": "Infineon Bluetooth Stack",
            "kind": "Platform",
            "targets": "Infineon SoCs/modules, embedded MCU and Linux gateway designs",
            "strength": "Tight silicon + stack integration, low-power tuning, and vendor-backed lifecycle/support",
            "tradeoff": "Less portable outside Infineon ecosystem than fully open host stacks",
            "missing_features": "No native cross-vendor portability layer for non-Infineon silicon",
            "best_fit": "Commercial products prioritizing time-to-market, qualification, and long-term support",
        },
        {
            "stack": "Zephyr Bluetooth Host",
            "kind": "OSS",
            "targets": "RTOS-based embedded IoT devices across many MCU vendors",
            "strength": "Portable open-source stack, broad board support, high customization flexibility",
            "tradeoff": "More integration/maintenance ownership for product teams",
            "missing_features": "No single-vendor production support SLA and less turnkey certification assistance",
            "best_fit": "Teams optimizing for cross-vendor firmware reuse and deep embedded customization",
        },
        {
            "stack": "BlueZ",
            "kind": "OSS",
            "targets": "Linux hosts/gateways, edge computers, and application processors",
            "strength": "Mature Linux ecosystem integration with strong host-side interoperability",
            "tradeoff": "Not an RTOS device stack; typically needs Linux-class host footprint",
            "missing_features": "Limited direct fit for tiny MCU-only endpoints without a Linux host",
            "best_fit": "Gateway/host products where Linux is already the system baseline",
        },
        {
            "stack": "Apache NimBLE",
            "kind": "OSS",
            "targets": "Resource-constrained MCU products and embedded RTOS environments",
            "strength": "Small memory footprint and widely reused BLE host for constrained systems",
            "tradeoff": "Feature integration breadth depends on chosen platform/vendor SDK",
            "missing_features": "No unified full-stack toolchain across all MCU vendors",
            "best_fit": "Ultra-low-resource BLE endpoints prioritizing compact implementation",
        },
        {
            "stack": "BTstack",
            "kind": "OSS",
            "targets": "Embedded devices, prototyping platforms, and custom Bluetooth firmware",
            "strength": "Clean architecture and flexibility for custom protocol/application work",
            "tradeoff": "Requires stronger in-house Bluetooth expertise for production hardening",
            "missing_features": "Smaller ecosystem and fewer out-of-box vertical integrations than mainstream stacks",
            "best_fit": "Engineering-led products needing highly tailored stack behavior",
        },
        {
            "stack": "Android Fluoride Stack",
            "kind": "OSS",
            "targets": "Android phones/tablets and Android-based consumer devices",
            "strength": "Deep integration with Android framework and large deployed device base",
            "tradeoff": "Tightly coupled to Android platform release and vendor customization layers",
            "missing_features": "Not suitable as a drop-in RTOS stack for standalone MCU peripherals",
            "best_fit": "Products with Android as the primary OS and app-facing Bluetooth requirements",
        },
    ]

    # --- Recent headline pools (still used for the compact Market Signal Feed)
    comp_7d = [a for a in arts_7d if a.get("vendor")]
    cust_7d = [a for a in arts_7d if a.get("customer")]
    comp_window = "7d"
    cust_window = "7d"
    if len(comp_7d) < 4:
        comp_7d = [a for a in _recent(articles, 14) if a.get("vendor")]
        comp_window = "14d fallback"
    if len(cust_7d) < 4:
        cust_7d = [a for a in _recent(articles, 14) if a.get("customer")]
        cust_window = "14d fallback"

    competitor_headlines = _unique_by_url(
        sorted(comp_7d, key=lambda x: _pub(x) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    )[:12]
    customer_headlines = _unique_by_url(
        sorted(cust_7d, key=lambda x: _pub(x) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    )[:12]

    cust_counts_7d = Counter(a["customer"] for a in arts_7d if a.get("customer"))
    priority = ["Amazon", "Google", "Meta", "Arlo", "Motorola", "BMW", "HKMC"]
    ordered: list[tuple[str, int]] = [(p, cust_counts_7d.get(p, 0)) for p in priority]
    extras = [(n, c) for n, c in cust_counts_7d.most_common() if n not in priority][: max(0, 8 - len(ordered))]
    ordered.extend(extras)
    max_n = max((n for _, n in ordered), default=1) or 1
    top_movers = [(name, n, int(n / max_n * 100) if max_n else 0) for name, n in ordered]

    # Competitive heatmap last 30d (uses all articles since fetch window ~30d)
    vendor_counts = Counter(a["vendor"] for a in articles if a.get("vendor"))
    top_vendors_for_map = [v for v, _ in vendor_counts.most_common(12)]
    heatmap_rows = []
    heatmap_max = 0
    for v in top_vendors_for_map:
        row = {"total": vendor_counts[v]}
        for slug, _label in BUCKETS:
            n = sum(1 for a in articles if a.get("vendor") == v and slug in a.get("buckets", []))
            row[slug] = n
            if n > heatmap_max: heatmap_max = n
        heatmap_rows.append((v, row))

    return env.from_string(_INDEX_TEMPLATE).render(
        articles=articles, customers=customers,
        competitors=comp.get("competitors", []), links=links,
        articles_7d=n_now, delta_pct=delta_pct, delta_class=delta_class, delta_arrow=delta_arrow,
        competitor_headlines=competitor_headlines,
        customer_headlines=customer_headlines,
        competitor_window_label=comp_window,
        customer_window_label=cust_window,
        battlecard=battlecard,
        opportunity_wins=opportunity_wins,
        opportunity_watch=opportunity_watch,
        customer_radar=customer_radar,
        stack_positioning=stack_positioning,
        standards_radar=standards_radar,
        freshness_7d=len(arts_7d),
        freshness_30d=len(arts_30d),
        freshness_45d=len(arts_45d),
        unique_sources=unique_sources,
        vendors_with_news=vendors_with_news,
        customers_with_news=customers_with_news,
        bucket_coverage=bucket_coverage,
        total_buckets=total_buckets,
        lookback_span_days=lookback_span_days,
        latest_article_label=latest_article_label,
        top_movers=top_movers,
        heatmap=heatmap_rows, heatmap_max=heatmap_max,
        active="index", **ctx,
    )


