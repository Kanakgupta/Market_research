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
"""

# ---------------------------------------------------------------- nav
_NAV_HTML = """
<header class="topnav"><div class="wrap">
  <a class="brand" href="index.html"><span class="brand-name">IoT Wireless Intel</span></a>
  <nav>
    <a href="index.html" class="{{ 'active' if active=='index' else '' }}">Overview</a>
    <div class="nav-dd">
      <a class="nav-dd-trigger {{ 'active' if active in news_slugs else '' }}" href="news.html">News <span class="dd-caret">&#9662;</span></a>
      <div class="nav-dd-menu">
        <a href="news.html">All News</a>
        {% for slug, label in buckets %}<a href="{{ slug }}.html">{{ label }}</a>{% endfor %}
      </div>
    </div>
    <a href="customers.html" class="{{ 'active' if active=='customers' else '' }}">Customers</a>
    <a href="competitors.html" class="{{ 'active' if active=='competitors' else '' }}">Competitors</a>
    <a href="relationships.html" class="{{ 'active' if active=='relationships' else '' }}">Relationships</a>
    <a href="technology.html" class="{{ 'active' if active=='technology' else '' }}">Technology</a>
    <a href="ai.html" class="{{ 'active' if active=='ai' else '' }}" style="background:linear-gradient(90deg,#7c3aed,#db2777);color:#fff;">✨ AI</a>
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
</head><body>
""" + _NAV_HTML + """
<main class="wrap content">
<section class="hero">
  <h1>{{ page_title }}</h1>
  <p>{{ page_desc }}</p>
  <div class="stats">
    <span class="pill">{{ articles|length }} articles</span>
    {% if vendor_groups %}<span class="pill">{{ vendor_total }} vendors</span>{% endif %}
    {% if customer_tabs %}<span class="pill">{{ customer_tabs|length }} customers</span>{% endif %}
    {% if app_tabs %}<span class="pill">{{ app_tabs|length }} applications</span>{% endif %}
    <button id="refreshBtn" class="pill" style="cursor:pointer;border:1px solid var(--accent);color:var(--accent);background:#eef2ff;font-weight:700;" title="Pull a fresh batch of news from the web (uses the AI server)">\u21bb Refresh news</button>
    <span id="refreshStatus" class="pill" style="display:none;"></span>
  </div>
</section>
<script>
(function(){
  var btn=document.getElementById('refreshBtn'), st=document.getElementById('refreshStatus');
  if(!btn) return;
  // Same origin if served via Flask /report/, else fall back to localhost.
  var apiBase = (location.protocol==='http:'||location.protocol==='https:') ? '' : 'http://localhost:5005';
  function show(msg, color){ st.style.display='inline-block'; st.textContent=msg;
    if(color){ st.style.background=color; st.style.color='#fff'; st.style.borderColor=color; } }
  function poll(){
    fetch(apiBase+'/api/refresh-news/status',{cache:'no-store'})
      .then(function(r){return r.json()})
      .then(function(s){
        if(s.running){ show('Fetching\u2026 ('+Math.round((Date.now()/1000-s.started))+'s)','#f59e0b');
                       setTimeout(poll, 2000); }
        else if(s.ok){ show('Done \u2014 reloading\u2026','#16a34a');
                       setTimeout(function(){ location.reload(); }, 1200); }
        else if(s.ok===false){ show('Refresh failed: '+(s.error||'see server log'),'#dc2626');
                               btn.disabled=false; }
      })
      .catch(function(){ show('AI server unreachable','#dc2626'); btn.disabled=false; });
  }
  btn.addEventListener('click', function(){
    btn.disabled=true; show('Starting\u2026','#2563eb');
    fetch(apiBase+'/api/refresh-news',{method:'POST'})
      .then(function(r){return r.json()})
      .then(function(j){
        if(!j.started && j.reason){ show('Already running\u2026','#f59e0b'); }
        poll();
      })
      .catch(function(){
        show('AI server not running \u2014 start it: python run.py ai --no-open','#dc2626');
        btn.disabled=false;
      });
  });
  // If a refresh is in-flight (e.g. user navigated away and back), resume polling.
  fetch(apiBase+'/api/refresh-news/status',{cache:'no-store'})
    .then(function(r){return r.json()})
    .then(function(s){ if(s.running){ btn.disabled=true; poll(); } })
    .catch(function(){});
})();
</script>

{% if not articles %}<div class="empty">No articles. Try widening <code>--max-age-days</code>.</div>{% endif %}

<div class="grid" id="grid">
  {% for a in articles %}
  <article class="card">
    <div class="thumb">
      {% if a.thumb %}<img src="{{ a.thumb }}" loading="lazy" referrerpolicy="no-referrer" onerror="this.parentElement.classList.add('thumb-empty'); this.remove()">{% endif %}
    </div>
    <div class="body">
      <div class="meta-row">
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
</main>
<footer class="footer"><div class="wrap">IoT Wireless Intel \u00b7 multi-source RSS \u00b7 for informational use</div></footer>
<script>
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

      <!-- Live news feed -->
      <div class="ci-news-feed-wrap">
        <div class="ci-section-h">&#x1F4F0; Live News &amp; Launch Evidence
          <span style="font-size:12px;font-weight:400;color:var(--muted);text-transform:none;letter-spacing:0;margin-left:6px;">{{ live|length }} articles</span>
        </div>
        {% if live %}
        <div class="oc-news-grid">
          {% for n in live %}
          <article class="card" style="margin:0;">
            <div class="thumb">
              {% if n.thumb %}<img src="{{ n.thumb }}" loading="lazy" referrerpolicy="no-referrer" onerror="this.parentElement.classList.add('thumb-empty'); this.remove()">{% endif %}
            </div>
            <div class="body">
              <div class="meta-row">
                {% for b in n.buckets %}<span class="chip chip-tech">{{ bucket_labels.get(b, b) }}</span>{% endfor %}
                <span class="chip chip-cust">{{ c.name }}</span>
              </div>
              <h2 class="title"><a href="{{ n.url }}" target="_blank" rel="noopener">{{ n.title }}</a></h2>
              {% if n.summary %}<p class="summary">{{ n.summary }}</p>{% endif %}
              <div class="meta-row">
                <span class="source">{{ n.source }}</span>
                {% if n.date %}<span class="dot">&middot;</span><span class="time" data-ts="{{ n.date }}">{{ n.date }}</span>{% endif %}
              </div>
            </div>
          </article>
          {% endfor %}
        </div>
        {% else %}
        <div class="ci-no-news">No tagged launch headlines in current window.</div>
        {% endif %}
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

/* vs AIROC section */
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
</head><body>
""" + _NAV_HTML + """
{% set priority_comps = competitors | selectattr('priority') | list %}
{% set other_comps = competitors | rejectattr('priority') | list %}

<main class="wrap content">

<!-- ── Anchor Bar ── -->
<div class="ci-anchor-bar">
  <div style="flex:1;min-width:220px;">
    <h2>{{ anchor.vendor }} {{ anchor.family }}</h2>
    <p>Our wireless connectivity portfolio — the benchmark for every comparison on this page.</p>
    <a class="ci-anchor-link" href="{{ anchor.site }}" target="_blank" rel="noopener">Product family page \u2197</a>
  </div>
  <div>
    <div style="font-size:11px;text-transform:uppercase;letter-spacing:.07em;opacity:.7;margin-bottom:6px;">Headline SKUs</div>
    <div class="ci-anchor-skus">
      {% for s in anchor.headline_skus %}
      <div class="ci-sku-chip"><strong>{{ s.sku }}</strong>{{ s.blurb }}</div>
      {% endfor %}
    </div>
  </div>
</div>

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
        <a class="ci-news-count" href="#cnews-{{ loop.index0 }}" onclick="event.preventDefault();document.getElementById('cnews-'+{{ loop.index0 }}).scrollIntoView({behavior:'smooth',block:'start'});" title="Jump to news feed">
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

      <!-- 6. vs AIROC -->
      <div class="ci-section-h" style="margin-bottom:10px;">\u26a1 vs Infineon {{ anchor.family }}</div>
      <div class="ci-vs-grid">
        <div class="ci-vs-box ci-vs-strength">
          <h4>\u2714 Where {{ c.vendor }} wins vs AIROC\u2122</h4>
          <ul>{% for s in c.vs_airoc_strengths %}<li>{{ s }}</li>{% endfor %}</ul>
        </div>
        <div class="ci-vs-box ci-vs-weakness">
          <h4>\u2717 Where AIROC\u2122 has the edge</h4>
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

      <!-- 9. Company news -->
      {% set cnews = vendor_news.get(c.vendor, []) %}
      <div class="ci-news-feed-wrap" id="cnews-{{ loop.index0 }}">
        <div class="ci-section-h">&#x1F4F0; Latest Wireless News &mdash; {{ c.vendor }}
          <span style="font-size:12px;font-weight:400;color:var(--muted);text-transform:none;letter-spacing:0;margin-left:6px;">{{ cnews|length }} articles</span>
        </div>
        {% if cnews %}
        <div class="oc-news-grid">
          {% for item in cnews %}
          <article class="card" style="margin:0;">
            <div class="thumb">
              {% if item.thumb %}<img src="{{ item.thumb }}" loading="lazy" referrerpolicy="no-referrer" onerror="this.parentElement.classList.add('thumb-empty'); this.remove()">{% endif %}
            </div>
            <div class="body">
              <div class="meta-row">
                {% for b in item.buckets %}<span class="chip chip-tech">{{ bucket_labels.get(b, b) }}</span>{% endfor %}
                <span class="chip chip-vendor">{{ c.vendor }}</span>
              </div>
              <h2 class="title"><a href="{{ item.url }}" target="_blank" rel="noopener">{{ item.title }}</a></h2>
              {% if item.summary %}<p class="summary">{{ item.summary }}</p>{% endif %}
              <div class="meta-row">
                <span class="source">{{ item.source }}</span>
                {% if item.published_iso %}<span class="dot">&middot;</span><span class="time" data-ts="{{ item.published_iso }}">{{ item.published }}</span>{% endif %}
              </div>
            </div>
          </article>
          {% endfor %}
        </div>
        {% else %}
        <div class="ci-no-news">No recent wireless news indexed for {{ c.vendor }}.</div>
        {% endif %}
      </div>

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
        <a class="ci-news-count" href="#cnews-{{ loop.index0 }}" onclick="event.preventDefault();document.getElementById('cnews-'+{{ loop.index0 }}).scrollIntoView({behavior:'smooth',block:'start'});" title="Jump to news feed">
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
              <h4>\u2714 Where {{ c.vendor }} wins vs AIROC\u2122</h4>
              <ul>{% for s in c.vs_airoc_strengths %}<li>{{ s }}</li>{% endfor %}</ul>
            </div>
            <div class="ci-vs-box ci-vs-weakness">
              <h4>\u2717 Where AIROC\u2122 has the edge</h4>
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
      <!-- News feed for non-priority -->
      {% set cnews = vendor_news.get(c.vendor, []) %}
      <div class="ci-news-feed-wrap" id="cnews-{{ loop.index0 }}">
        <div class="ci-section-h">&#x1F4F0; Latest Wireless News &mdash; {{ c.vendor }}
          <span style="font-size:12px;font-weight:400;color:var(--muted);text-transform:none;letter-spacing:0;margin-left:6px;">{{ cnews|length }} articles</span>
        </div>
        {% if cnews %}
        <div class="oc-news-grid">
          {% for item in cnews %}
          <article class="card" style="margin:0;">
            <div class="thumb">
              {% if item.thumb %}<img src="{{ item.thumb }}" loading="lazy" referrerpolicy="no-referrer" onerror="this.parentElement.classList.add('thumb-empty'); this.remove()">{% endif %}
            </div>
            <div class="body">
              <div class="meta-row">
                {% for b in item.buckets %}<span class="chip chip-tech">{{ bucket_labels.get(b, b) }}</span>{% endfor %}
                <span class="chip chip-vendor">{{ c.vendor }}</span>
              </div>
              <h2 class="title"><a href="{{ item.url }}" target="_blank" rel="noopener">{{ item.title }}</a></h2>
              {% if item.summary %}<p class="summary">{{ item.summary }}</p>{% endif %}
              <div class="meta-row">
                <span class="source">{{ item.source }}</span>
                {% if item.published_iso %}<span class="dot">&middot;</span><span class="time" data-ts="{{ item.published_iso }}">{{ item.published }}</span>{% endif %}
              </div>
            </div>
          </article>
          {% endfor %}
        </div>
        {% else %}
        <div class="ci-no-news">No recent wireless news indexed for {{ c.vendor }}.</div>
        {% endif %}
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
        <td><strong>{{ l.vendor }}</strong>{% if l.vendor == 'Infineon' %} <span class="tag">AIROC</span>{% endif %}</td>
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
    "aliro":     "Aliro digital-key spec from CSA \u2014 NFC + UWB + Bluetooth LE access.",
    "thread":    "Thread protocol, OpenThread, Thread 1.4, border routers.",
    "matter":    "Matter spec, certified devices, Matter Casting, ecosystem moves.",
}

_TECHNOLOGY_TEMPLATE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Technology Intel · IoT Wireless Intel</title>
<style>{{ css }}
.tech-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(360px,1fr)); gap:14px; margin-top:16px; }
.tech-card { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:14px 16px; }
.tech-card h2 { margin:0 0 6px; font-size:18px; color:#0f172a; }
.tech-meta { color:var(--muted); font-size:12.5px; margin:0 0 8px; }
.tech-stats { display:flex; gap:8px; flex-wrap:wrap; margin:8px 0 10px; }
.tech-list { margin:6px 0 0; padding-left:18px; }
.tech-list li { margin:5px 0; }
.tech-list a { color:var(--text); font-weight:600; }
.tech-list a:hover { color:var(--accent); }
.subhead { margin:10px 0 4px; font-size:12px; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); }
</style>
</head><body>
""" + _NAV_HTML + """
<main class="wrap content">
<section class="hero">
  <h1>Technology Intelligence</h1>
  <p>Details, latest updates, what's new today, and recent evidence across BT, 15.4, Wi-Fi, Matter, Zigbee, Aliro, and Thread.</p>
</section>

<div class="tech-grid">
{% for s in tech_sections %}
  <section class="tech-card">
    <h2>{{ s.label }}</h2>
    <p class="tech-meta">{{ s.detail }}</p>
    {% if s.current or s.next %}
      <p class="tech-meta"><strong>Current:</strong> {{ s.current or '—' }} · <strong>Next:</strong> {{ s.next or '—' }}</p>
    {% endif %}
    <div class="tech-stats">
      <span class="pill">{{ s.total_count }} total updates</span>
      <span class="pill">{{ s.today_count }} new today</span>
      {% if s.page %}<a class="pill" href="{{ s.page }}">Open full {{ s.label }} feed →</a>{% endif %}
    </div>

    <div class="subhead">What's New Today</div>
    {% if s.today_items %}
      <ul class="tech-list">
        {% for a in s.today_items %}
          <li><a href="{{ a.url }}" target="_blank" rel="noopener">{{ a.title }}</a> <span class="tech-meta">({{ a.source }})</span></li>
        {% endfor %}
      </ul>
    {% else %}
      <p class="tech-meta">No new items today.</p>
    {% endif %}

    <div class="subhead">Latest Updates</div>
    {% if s.latest_items %}
      <ul class="tech-list">
        {% for a in s.latest_items %}
          <li><a href="{{ a.url }}" target="_blank" rel="noopener">{{ a.title }}</a> <span class="tech-meta">({{ a.source }}{% if a.published %} · {{ a.published.strftime('%b %d') }}{% endif %})</span></li>
        {% endfor %}
      </ul>
    {% else %}
      <p class="tech-meta">No updates available yet.</p>
    {% endif %}
  </section>
{% endfor %}
</div>
</main>
<footer class="footer"><div class="wrap">Technology snapshot generated {{ generated_at }} PDT</div></footer>
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
        return vendor_groups, vendor_total, c_tabs, a_tabs

    news_template = env.from_string(_NEWS_TEMPLATE)

    # --- All News page ---
    vg, vt, ct, at = _filters(articles)
    (output_dir / "news.html").write_text(news_template.render(
        page_title="All News", page_desc=PAGE_DESCS["news"],
        articles=articles, active="news",
        vendor_groups=vg, vendor_total=vt, customer_tabs=ct, app_tabs=at, **common_ctx,
    ), encoding="utf-8")

    # --- Per-bucket news pages ---
    for slug, label in BUCKETS:
        items = [a for a in articles if slug in a["buckets"]]
        vg, vt, ct, at = _filters(items)
        (output_dir / f"{slug}.html").write_text(news_template.render(
            page_title=label + " News", page_desc=PAGE_DESCS.get(slug, ""),
            articles=items, active=slug,
            vendor_groups=vg, vendor_total=vt, customer_tabs=ct, app_tabs=at, **common_ctx,
        ), encoding="utf-8")

    # --- Technology page ---
    standards_path = Path(__file__).resolve().parents[2] / "data" / "standards.json"
    standards_map: dict[str, dict] = {}
    if standards_path.exists():
      try:
        standards_raw = json.loads(standards_path.read_text(encoding="utf-8"))
        for row in (standards_raw.get("standards") or []):
          standards_map[(row.get("family") or "").lower()] = row
      except (OSError, json.JSONDecodeError):
        standards_map = {}

    today_local = now_pdt.date()

    def _published(a: dict):
      p = a.get("published")
      if p and p.tzinfo is None:
        p = p.replace(tzinfo=timezone.utc)
      return p

    def _match_articles(bucket: str | None = None, keywords: list[str] | None = None) -> list[dict]:
      keys = [k.lower() for k in (keywords or [])]
      matched: list[dict] = []
      for a in articles:
        if bucket and bucket not in (a.get("buckets") or []):
          continue
        if keys:
          blob = " ".join([
            str(a.get("title") or ""),
            str(a.get("summary") or ""),
            str(a.get("url") or ""),
          ]).lower()
          if not any(k in blob for k in keys):
            continue
        matched.append(a)
      matched.sort(key=lambda x: _published(x) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
      return matched

    _std_bt = standards_map.get("bluetooth", {})
    _std_wifi = standards_map.get("wi-fi", {})
    _std_154 = standards_map.get("802.15.4 / thread / matter", {})

    tech_specs = [
      {
        "label": "BT",
        "detail": "Bluetooth device/chip updates including LE Audio, Channel Sounding, and ecosystem announcements.",
        "bucket": "bluetooth",
        "keywords": [],
        "current": _std_bt.get("current_version", ""),
        "next": _std_bt.get("next_version", ""),
        "page": "bluetooth.html",
      },
      {
        "label": "15.4",
        "detail": "IEEE 802.15.4 radio stack updates, multiprotocol SoCs, and integration signals.",
        "bucket": "ieee15_4",
        "keywords": [],
        "current": _std_154.get("current_version", ""),
        "next": _std_154.get("next_version", ""),
        "page": "ieee15_4.html",
      },
      {
        "label": "Wi-Fi",
        "detail": "Wi-Fi chipset/platform launches and connectivity trends relevant to IoT and edge devices.",
        "bucket": "wifi",
        "keywords": [],
        "current": _std_wifi.get("current_version", ""),
        "next": _std_wifi.get("next_version", ""),
        "page": "wifi.html",
      },
      {
        "label": "Matter",
        "detail": "Matter certification and device ecosystem changes across smart-home categories.",
        "bucket": "matter",
        "keywords": [],
        "current": _std_154.get("current_version", ""),
        "next": _std_154.get("next_version", ""),
        "page": "matter.html",
      },
      {
        "label": "Zigbee",
        "detail": "Zigbee-specific device and module updates tracked from 15.4 ecosystem coverage.",
        "bucket": "ieee15_4",
        "keywords": ["zigbee"],
        "current": _std_154.get("current_version", ""),
        "next": _std_154.get("next_version", ""),
        "page": "ieee15_4.html",
      },
      {
        "label": "Aliro",
        "detail": "Aliro digital-key ecosystem developments, certification, and access-control rollouts.",
        "bucket": "aliro",
        "keywords": [],
        "current": _std_154.get("current_version", ""),
        "next": _std_154.get("next_version", ""),
        "page": "aliro.html",
      },
      {
        "label": "Thread",
        "detail": "Thread stack releases, border-router ecosystem news, and deployment signals.",
        "bucket": "thread",
        "keywords": [],
        "current": _std_154.get("current_version", ""),
        "next": _std_154.get("next_version", ""),
        "page": "thread.html",
      },
    ]

    tech_sections = []
    for spec in tech_specs:
      items = _match_articles(bucket=spec["bucket"], keywords=spec["keywords"])
      today_items = []
      for a in items:
        p = _published(a)
        if p and p.astimezone(PDT).date() == today_local:
          today_items.append(a)
      tech_sections.append({
        **spec,
        "total_count": len(items),
        "today_count": len(today_items),
        "today_items": today_items[:4],
        "latest_items": items[:8],
      })

    (output_dir / "technology.html").write_text(env.from_string(_TECHNOLOGY_TEMPLATE).render(
      tech_sections=tech_sections, active="technology", **common_ctx
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
    (output_dir / "customers.html").write_text(env.from_string(_CUSTOMERS_TEMPLATE).render(
      customers=customers, customer_live=customer_live,
      predictions=predictions,
      news_counts=cust_news_counts, active="customers", **common_ctx,
    ), encoding="utf-8")

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

    (output_dir / "competitors.html").write_text(env.from_string(_COMPETITORS_TEMPLATE).render(
        anchor=comp.get("anchor", {}), competitors=comp.get("competitors", []),
        news_counts=vendor_news_counts, vendor_news=vendor_news,
        active="competitors", **common_ctx,
    ), encoding="utf-8")

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

    # --- AI tab (shim that opens the local Flask chat) ---
    (output_dir / "ai.html").write_text(env.from_string(_AI_SHIM_TEMPLATE).render(
        active="ai", **common_ctx,
    ), encoding="utf-8")

    # --- Index = Overview ---
    (output_dir / "index.html").write_text(_render_index(env, common_ctx, articles, customers, comp, links), encoding="utf-8")

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


_AI_SHIM_TEMPLATE = """<!doctype html>
<html lang=\"en\"><head>
<meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>AIROC AI \u00b7 IoT Wireless Intel</title>
<style>{{ css }}
.ai-frame-wrap{position:relative;height:calc(100vh - 100px);margin:8px 0 0;border:1px solid var(--border);border-radius:12px;overflow:hidden;background:#fff;}
.ai-frame{width:100%;height:100%;border:0;display:block;}
.ai-offline{display:none;padding:40px 30px;text-align:center;color:var(--muted);}
.ai-offline.show{display:block;}
.ai-offline h2{color:var(--text);margin:0 0 10px;font-size:22px;}
.ai-offline code{background:#f1f5f9;padding:3px 8px;border-radius:4px;color:#0f172a;font-size:13px;}
.ai-offline .cmd{display:inline-block;background:#0f172a;color:#e2e8f0;padding:10px 16px;border-radius:8px;margin:14px 0;font-family:Consolas,monospace;font-size:13px;}
.ai-offline ol{display:inline-block;text-align:left;margin:14px auto;}
.ai-toolbar{display:flex;align-items:center;gap:10px;padding:8px 14px;background:#f8fafc;border-bottom:1px solid var(--border);font-size:12.5px;color:var(--muted);}
.ai-toolbar .dot{width:8px;height:8px;border-radius:50%;background:#94a3b8;display:inline-block;}
.ai-toolbar .dot.live{background:#22c55e;box-shadow:0 0 0 3px rgba(34,197,94,.18);}
.ai-toolbar .dot.down{background:#ef4444;}
.ai-toolbar a{margin-left:auto;}
</style></head><body>
""" + _NAV_HTML + """
<main class=\"wrap content\" style=\"padding-top:8px;\">
<div class=\"ai-frame-wrap\">
  <div class=\"ai-toolbar\">
    <span class=\"dot\" id=\"aiDot\"></span>
    <span id=\"aiStatus\">checking AI server\u2026</span>
    <a href=\"#\" id=\"aiOpenNew\" target=\"_blank\">Open in new window \u2197</a>
  </div>
  <iframe id=\"aiFrame\" class=\"ai-frame\" title=\"AIROC AI\"></iframe>
  <div class=\"ai-offline\" id=\"aiOffline\">
    <h2>\u2728 AIROC AI server is not running</h2>
    <p>Start the local AI service so this tab can chat with your indexed documents and the web.</p>
    <div class=\"cmd\">python run.py ai --no-open</div>
    <p style=\"margin-top:18px;\">Then refresh this tab. (Or, if Chrome blocks the iframe due to file:// origin, open the report from the AI server itself: <a href=\"http://localhost:5005/report/\" target=\"_blank\">http://localhost:5005/report/</a>)</p>
    <p style=\"margin-top:18px;\">First-time setup:</p>
    <ol>
      <li><code>pip install -r requirements.txt</code></li>
      <li>Set Gemini key: <code>$env:GEMINI_API_KEY = \"your-key\"</code> &mdash; <a href=\"https://aistudio.google.com/apikey\" target=\"_blank\">get one free</a></li>
      <li>(Optional) extra docs: <code>$env:AI_EXTRA_DOC_PATHS = \"C:\\guptakanak\\ResearchDocs;C:\\guptakanak\\SIG\"</code></li>
      <li>Run <code>python run.py ai --no-open</code> then refresh this tab.</li>
    </ol>
  </div>
</div>
</main>
<script>
(function(){
  var dot=document.getElementById('aiDot'), st=document.getElementById('aiStatus'),
      fr=document.getElementById('aiFrame'), off=document.getElementById('aiOffline'),
      openNew=document.getElementById('aiOpenNew');
  // Only treat as same-origin when actually served by the Flask AI server (port 5005).
  // When served by a static server (e.g. python -m http.server 8000) or file://,
  // fall back to absolute http://localhost:5005/ URLs.
  var sameOrigin = (location.protocol === 'http:' || location.protocol === 'https:')
                   && location.port === '5005';
  var chatUrl = sameOrigin ? '/ai' : 'http://localhost:5005/ai';
  var statusUrl = sameOrigin ? '/api/status' : 'http://localhost:5005/api/status';
  fr.src = chatUrl;
  openNew.href = sameOrigin ? '/ai' : 'http://localhost:5005/ai';
  function check(){
    fetch(statusUrl,{mode:'cors',cache:'no-store'})
      .then(function(r){return r.ok?r.json():Promise.reject()})
      .then(function(j){
        dot.className='dot live';
        st.textContent='AI server live \u2014 '+(j.chunks||0)+' chunks indexed \u00b7 model '+(j.model||'gemini');
        off.classList.remove('show'); fr.style.display='block';
      })
      .catch(function(){
        dot.className='dot down';
        var hint = sameOrigin ? '' : ' \u2014 if iframe is blank, open via http://localhost:5005/report/';
        st.textContent='AI server offline'+hint;
        fr.style.display='none'; off.classList.add('show');
      });
  }
  check(); setInterval(check, 5000);
})();
</script>
</body></html>
"""

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
</style>
</head><body>
""" + _NAV_HTML + """
<main class="wrap content">
<section class="hero">
  <h1>IoT Wireless Intelligence</h1>
  <p>Competitive radar for Infineon AIROC across IoT wireless \u2014 Wi-Fi, Bluetooth, 802.15.4, Aliro, Thread, Matter. What changed, who's moving, where to look next.</p>
</section>

<div class="kpi-row">
  <div class="kpi"><h3>News (last 7d)</h3><div class="v">{{ articles_7d }}</div>
    <div class="delta {{ delta_class }}">{{ delta_arrow }} {{ delta_pct }} vs prior 7d</div></div>
  <div class="kpi"><h3>Competitors tracked</h3><div class="v">{{ competitors|length }}</div>
    <div class="delta flat">vs Infineon AIROC</div></div>
  <div class="kpi"><h3>Customers tracked</h3><div class="v">{{ customers|length }}</div>
    <div class="delta flat">OEM profiles</div></div>
  <div class="kpi"><h3>Relationship links</h3><div class="v">{{ links|length }}</div>
    <div class="delta flat">vendor &harr; customer</div></div>
</div>

<div class="two-col">
  <section class="section">
    <h2>What's new this week</h2>
    <p class="muted">Top headlines from the last 7 days, ranked by recency &times; signal.</p>
    {% if recent_headlines %}
    <ul class="headline-list">
      {% for a in recent_headlines %}
      <li>
        <a href="{{ a.url }}" target="_blank" rel="noopener">{{ a.title }}</a>
        <div class="meta">
          <span class="source">{{ a.source }}</span>
          {% if a.published %}<span>\u00b7 {{ a.published.strftime('%b %d') }}</span>{% endif %}
          {% for b in a.buckets %}<span class="chip chip-tech">{{ bucket_labels[b] }}</span>{% endfor %}
          {% if a.vendor %}<span class="chip chip-vendor">{{ a.vendor }}</span>{% endif %}
          {% if a.customer %}<span class="chip chip-cust">{{ a.customer }}</span>{% endif %}
        </div>
      </li>
      {% endfor %}
    </ul>
    {% else %}<p class="muted">No headlines yet \u2014 try widening <code>--max-age-days</code>.</p>{% endif %}
    <p style="margin-top:12px;"><a href="news.html">Browse all {{ articles|length }} articles \u2192</a></p>
  </section>

  <section class="section">
    <h2>Top moving customers (7d)</h2>
    <p class="muted">OEMs with the most news activity right now.</p>
    {% if top_movers %}
    <ul class="movers">
      {% for name, n, pct in top_movers %}
      <li>
        <span class="name">{{ name }}</span>
        <span class="bar"><i style="width:{{ pct }}%"></i></span>
        <span class="n">{{ n }}</span>
      </li>
      {% endfor %}
    </ul>
    {% else %}<p class="muted">No customer activity in the last 7 days.</p>{% endif %}
    <p style="margin-top:12px;"><a href="customers.html">All customer profiles \u2192</a></p>
  </section>
</div>

<section class="section">
  <h2>Where do you want to go?</h2>
  <div class="jump-row">
    <a class="jump-card" href="news.html"><h3>News \u2192</h3><p>All recent articles by technology, vendor, customer and application.</p></a>
    <a class="jump-card" href="customers.html"><h3>Customers \u2192</h3><p>OEM profiles \u2014 recent products and forward roadmap signals.</p></a>
    <a class="jump-card" href="competitors.html"><h3>Competitors \u2192</h3><p>Side-by-side comparison vs Infineon AIROC \u2014 SKUs, strengths, weaknesses.</p></a>
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

    arts_7d = [a for a in articles if _pub(a) and _pub(a) >= cutoff_7d]
    arts_prev_7d = [a for a in articles if _pub(a) and cutoff_14d <= _pub(a) < cutoff_7d]

    # KPI delta
    n_now, n_prev = len(arts_7d), len(arts_prev_7d)
    if n_prev == 0:
        delta_pct, delta_class, delta_arrow = ("new" if n_now else "\u2014"), "flat", ""
    else:
        pct = (n_now - n_prev) / n_prev * 100
        delta_pct = f"{abs(pct):.0f}%"
        delta_class = "up" if pct > 5 else ("down" if pct < -5 else "flat")
        delta_arrow = "\u25b2" if pct > 5 else ("\u25bc" if pct < -5 else "\u25ac")

    # Recent headlines: prefer those with vendor or customer tagged
    def _score(a):
        s = 0
        if a.get("vendor"): s += 2
        if a.get("customer"): s += 2
        if a.get("application"): s += 1
        p = _pub(a)
        if p:
            hours_old = (now - p).total_seconds() / 3600
            s -= hours_old / 48
        return s
    recent_headlines = sorted(arts_7d, key=_score, reverse=True)[:6]

    # Top moving customers (7d) \u2014 priority list pinned, then any extras by activity
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
        recent_headlines=recent_headlines,
        top_movers=top_movers,
        heatmap=heatmap_rows, heatmap_max=heatmap_max,
        active="index", **ctx,
    )

