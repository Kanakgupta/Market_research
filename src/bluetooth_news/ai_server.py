"""Local Flask server for the AI tab. Serves chat UI + REST endpoints.

Run:  python run.py ai           (or)  python -m bluetooth_news.ai_server
Open: http://localhost:5005
"""
from __future__ import annotations

import json
import logging
import os
import threading
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, request, Response, send_from_directory, redirect

from . import ai_assistant as A
from . import tech_news as TN

log = logging.getLogger(__name__)

app = Flask(__name__)
_retriever_lock = threading.Lock()
_retriever: A.Retriever | None = None
_retriever_index_mtime: float | None = None

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = ROOT / "output"


def _latest_site() -> Path | None:
    if not OUTPUT_ROOT.exists():
        return None
    sites = sorted(
        (p for p in OUTPUT_ROOT.glob("site_*") if p.is_dir()),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    return sites[0] if sites else None


@app.after_request
def _cors(resp: Response) -> Response:
    """Allow the static report tab (file:// or other origin) to call our API
    and embed our UI in an iframe."""
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    # Permit being framed by anyone (override Flask default deny)
    resp.headers.pop("X-Frame-Options", None)
    resp.headers["Content-Security-Policy"] = "frame-ancestors *"
    return resp


@app.route("/api/<path:_>", methods=["OPTIONS"])
def _cors_preflight(_):  # type: ignore[no-untyped-def]
    resp = Response("", 204)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


def _r() -> A.Retriever:
    global _retriever, _retriever_index_mtime
    current_mtime: float | None = None
    try:
        current_mtime = A.INDEX_FILE.stat().st_mtime
    except OSError:
        current_mtime = None
    with _retriever_lock:
        if _retriever is None or _retriever_index_mtime != current_mtime:
            _retriever = A.Retriever()
            _retriever_index_mtime = current_mtime
        return _retriever


def _refresh() -> None:
    global _retriever, _retriever_index_mtime
    with _retriever_lock:
        _retriever = A.Retriever()
        try:
            _retriever_index_mtime = A.INDEX_FILE.stat().st_mtime
        except OSError:
            _retriever_index_mtime = None


# ---------------------------------------------------------------- HTML
_CHAT_HTML = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIROC AI · IoT Wireless Intel</title>
<style>
:root{--bg:#f7f9fc;--card:#fff;--border:#e4e8ee;--text:#1a1f2c;--muted:#6b7280;--accent:#2563eb;--user:#eef2ff;--bot:#f8fafc;}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--text);font-size:14.5px;line-height:1.5;height:100vh;display:flex;flex-direction:column}
header{background:var(--card);border-bottom:1px solid var(--border);padding:14px 22px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
header .brand{font-weight:800;font-size:20px;background:linear-gradient(90deg,#2563eb 0%,#7c3aed 50%,#db2777 100%);-webkit-background-clip:text;background-clip:text;color:transparent}
header .pill{background:#eef2ff;color:#3730a3;padding:3px 10px;border-radius:999px;font-size:11.5px;font-weight:600}
header .grow{flex:1}
header button{border:1px solid var(--border);background:#fff;color:#0f172a;border-radius:8px;padding:7px 14px;font-weight:600;cursor:pointer;font-size:13px}
header button:hover{border-color:var(--accent);color:var(--accent)}
header a{color:var(--accent);text-decoration:none;font-weight:600;font-size:13px}
.suggest{padding:10px 22px;display:flex;gap:8px;flex-wrap:wrap;border-bottom:1px solid var(--border);background:var(--card)}
.suggest button{background:#f1f5f9;border:1px solid var(--border);border-radius:999px;padding:6px 12px;font-size:12.5px;cursor:pointer;color:#0f172a}
.suggest button:hover{background:#eef2ff;color:var(--accent);border-color:var(--accent)}
main{flex:1;overflow-y:auto;padding:22px;display:flex;flex-direction:column;gap:14px;max-width:1100px;width:100%;margin:0 auto}
.msg{display:flex;gap:12px}
.msg .who{width:32px;height:32px;border-radius:50%;flex:none;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:12px;color:#fff}
.msg.user .who{background:#2563eb}
.msg.bot .who{background:linear-gradient(135deg,#7c3aed,#db2777)}
.msg .bub{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:12px 16px;flex:1;min-width:0}
.msg.user .bub{background:var(--user)}
.msg .bub p{margin:.4em 0}
.msg .bub h1,.msg .bub h2,.msg .bub h3{margin:.6em 0 .3em;font-size:15.5px}
.msg .bub ul,.msg .bub ol{margin:.4em 0;padding-left:22px}
.msg .bub code{background:#f1f5f9;padding:1px 6px;border-radius:4px;font-size:12.5px}
.msg .bub pre{background:#0f172a;color:#e2e8f0;padding:12px 14px;border-radius:8px;overflow-x:auto;font-size:12.5px}
.msg .bub table{border-collapse:collapse;margin:8px 0;font-size:13px}
.msg .bub table th,.msg .bub table td{border:1px solid var(--border);padding:5px 9px;text-align:left}
.msg .bub table th{background:#f9fafc;font-weight:600}
.cites{margin-top:8px;border-top:1px dashed var(--border);padding-top:8px;font-size:12px;color:var(--muted)}
.cites b{color:#0f172a}
.cites .c{display:inline-block;background:#f1f5f9;border-radius:6px;padding:2px 8px;margin:2px 4px 2px 0}
.cites .c.web{background:#dcfce7;color:#166534}
.cites .c.data{background:#fef3c7;color:#92400e}
footer{padding:14px 22px;background:var(--card);border-top:1px solid var(--border)}
.input-row{max-width:1100px;margin:0 auto;display:flex;gap:10px}
textarea{flex:1;border:1px solid var(--border);border-radius:10px;padding:12px 14px;font:inherit;resize:none;min-height:48px;max-height:160px}
textarea:focus{outline:none;border-color:var(--accent)}
.send{background:var(--accent);color:#fff;border:none;border-radius:10px;padding:0 18px;font-weight:700;cursor:pointer;font-size:14px}
.send:disabled{opacity:.5;cursor:not-allowed}
.opts{max-width:1100px;margin:6px auto 0;font-size:11.5px;color:var(--muted);display:flex;gap:14px;align-items:center}
.opts label{cursor:pointer}
.spin{display:inline-block;width:14px;height:14px;border:2px solid #cbd5e1;border-top-color:var(--accent);border-radius:50%;animation:s 1s linear infinite;vertical-align:-3px;margin-right:6px}
@keyframes s{to{transform:rotate(360deg)}}
.toast{position:fixed;bottom:20px;right:20px;background:#0f172a;color:#fff;padding:10px 16px;border-radius:8px;font-size:13px;opacity:0;transition:opacity .2s;z-index:99}
.toast.show{opacity:.95}
.topnav{background:var(--card);border-bottom:1px solid var(--border);flex:none;padding:0}
.topnav .wrap{display:flex;align-items:center;gap:18px;height:60px;max-width:1280px;margin:0 auto;padding:0 20px}
.topnav .brand-name{font-size:22px;font-weight:800;letter-spacing:.3px;white-space:nowrap;background:linear-gradient(90deg,#2563eb 0%,#7c3aed 50%,#db2777 100%);-webkit-background-clip:text;background-clip:text;color:transparent;-webkit-text-fill-color:transparent;text-decoration:none}
.topnav nav{display:flex;gap:6px;align-items:center;flex:1;flex-wrap:wrap}
.topnav nav a{color:#334155;font-weight:600;font-size:14px;padding:7px 14px;border-radius:8px;background:#f1f5f9;text-decoration:none}
.topnav nav a:hover{color:var(--accent);background:#eef2ff}
.topnav nav a.active{color:#fff;background:var(--accent)}
.topnav .meta-info{color:var(--muted);font-size:12px;white-space:nowrap}
</style></head>
<body>
<header class="topnav"><div class="wrap">
  <a class="brand-name" href="/report/index.html">IoT Wireless Intel</a>
  <nav>
    <a href="/report/index.html">Overview</a>
    <a href="/report/news.html">News</a>
    <a href="/report/customers.html">Customers</a>
    <a href="/report/competitors.html">Competitors</a>
    <a href="/report/relationships.html">Relationships</a>
    <a href="/report/technology.html">Technology</a>
    <a href="/ai" class="active" style="background:linear-gradient(90deg,#7c3aed,#db2777);color:#fff;">✨ AI</a>
  </nav>
  <div class="meta-info">AI Assistant</div>
</div></header>
<header>
  <span class="brand">AIROC AI</span>
  <span class="pill" id="status">loading…</span>
  <span class="grow"></span>
  <button id="reindex">⟳ Reindex docs</button>
  <a href="/" onclick="resetChat();return false;">＋ New chat</a>
  <a href="../output/" target="_blank">Reports ↗</a>
</header>
<div class="suggest">
  <button data-q="Teach me IEEE 802.15.4 — protocol stack, key features, and how it differs from Bluetooth LE.">Teach me 15.4</button>
  <button data-q="Compare Infineon AIROC CYW55513 vs NXP IW612 vs Qualcomm QCC74x for smart-home OEMs.">AIROC vs NXP vs QCA</button>
  <button data-q="Which chip vendors does Arlo use across its camera lineup, and where could AIROC win?">Arlo opportunity</button>
  <button data-q="Summarise Bluetooth 6.0 Channel Sounding and our positioning vs Nordic and Silicon Labs.">BT 6.0 Channel Sounding</button>
</div>
<main id="chat">
  <div class="msg bot"><div class="who">AI</div><div class="bub">
    <p>Hi — I'm <b>AIROC AI</b>. I can teach you IoT-wireless topics, compare competitors, and answer questions about your indexed PDFs/DOCXs and project data. Try a chip on top, or ask anything.</p>
    <p style="color:var(--muted);font-size:12.5px">If I don't have the info locally I'll search the web and add it to the index.</p>
  </div></div>
</main>
<footer>
  <div class="input-row">
    <textarea id="q" placeholder="Ask anything — e.g. 'Create a 1-page brief on AIROC for Stryker medical wearables'…"
              onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();send()}"></textarea>
    <button class="send" id="send" onclick="send()">Send ▸</button>
  </div>
  <div class="opts">
    <label><input type="checkbox" id="useWeb" checked> Allow web search fallback</label>
    <span id="meta"></span>
  </div>
</footer>
<div id="toast" class="toast"></div>

<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script>
const history=[];
const chat=document.getElementById('chat');
const q=document.getElementById('q');
const sendBtn=document.getElementById('send');
const statusEl=document.getElementById('status');
const metaEl=document.getElementById('meta');

function toast(msg){const t=document.getElementById('toast');t.textContent=msg;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2400)}

function addMsg(role,html,cites){
  const div=document.createElement('div');div.className='msg '+role;
  const who=document.createElement('div');who.className='who';who.textContent=role==='user'?'YOU':'AI';
  const bub=document.createElement('div');bub.className='bub';bub.innerHTML=html;
  if(cites&&cites.length){
    const c=document.createElement('div');c.className='cites';
    c.innerHTML='<b>Sources:</b> '+cites.map(s=>{
      const cls=s.kind==='web'?'web':(s.kind==='data'?'data':'');
      const url=s.kind==='web'?s.source.replace(/^web:/,''):'';
      const label=`[#${s.id}] ${escapeHtml(s.title)}`+(s.page?` p.${s.page}`:'');
      return url?`<a class="c ${cls}" href="${url}" target="_blank">${label} ↗</a>`:`<span class="c ${cls}">${label}</span>`;
    }).join('');
    bub.appendChild(c);
  }
  div.appendChild(who);div.appendChild(bub);chat.appendChild(div);
  div.scrollIntoView({behavior:'smooth',block:'end'});
  return bub;
}
function escapeHtml(s){return (s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}

async function send(){
  const text=q.value.trim();if(!text)return;
  q.value='';sendBtn.disabled=true;
  addMsg('user',escapeHtml(text).replace(/\n/g,'<br>'));
  history.push({role:'user',content:text});
  const pending=addMsg('bot','<span class="spin"></span>thinking…');
  try{
    const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:text,history:history.slice(0,-1),allow_web:document.getElementById('useWeb').checked})});
    const j=await r.json();
    pending.innerHTML=marked.parse(j.reply||'(no reply)');
    if(j.sources&&j.sources.length){
      const c=document.createElement('div');c.className='cites';
      c.innerHTML='<b>Sources:</b> '+j.sources.map(s=>{
        const cls=s.kind==='web'?'web':(s.kind==='data'?'data':'');
        const url=s.kind==='web'?s.source.replace(/^web:/,''):'';
        const label=`[#${s.id}] ${escapeHtml(s.title)}`+(s.page?` p.${s.page}`:'');
        return url?`<a class="c ${cls}" href="${url}" target="_blank">${label} ↗</a>`:`<span class="c ${cls}">${label}</span>`;
      }).join('');
      pending.appendChild(c);
    }
    metaEl.textContent=`backend: ${j.backend}${j.used_web?' · web used':''}`;
    history.push({role:'assistant',content:j.reply||''});
  }catch(e){
    pending.innerHTML='<span style="color:#b91c1c">Error: '+escapeHtml(String(e))+'</span>';
  }finally{sendBtn.disabled=false;q.focus()}
}

document.querySelectorAll('.suggest button').forEach(b=>b.addEventListener('click',()=>{q.value=b.dataset.q;send()}));

document.getElementById('reindex').addEventListener('click',async()=>{
  toast('Re-indexing local docs… this can take a minute');
  try{const r=await fetch('/api/reindex',{method:'POST'});const j=await r.json();
    toast('Indexed '+j.count+' chunks');refreshStatus()}
  catch(e){toast('Reindex failed: '+e)}
});

function resetChat(){history.length=0;chat.innerHTML='';location.reload()}

async function refreshStatus(){
  try{const r=await fetch('/api/status');const j=await r.json();
    statusEl.textContent=`${j.chunks} chunks · ${j.backend}`;
  }catch(e){statusEl.textContent='offline'}
}
refreshStatus();
</script>
</body></html>
"""


# ---------------------------------------------------------------- dynamic news page
_NEWS_HTML = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>News · IoT Wireless Intel</title>
<style>
:root{--bg:#f7f9fc;--card:#fff;--border:#e4e8ee;--text:#1a1f2c;--muted:#6b7280;--accent:#2563eb;--hover:#f1f5fb;}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--text);font-size:14.5px;line-height:1.5;}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:1280px;margin:0 auto;padding:0 20px}
.topnav{background:var(--card);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:50}
.topnav .wrap{display:flex;align-items:center;gap:18px;height:60px}
.topnav .brand-name{font-size:22px;font-weight:800;letter-spacing:.3px;white-space:nowrap;background:linear-gradient(90deg,#2563eb 0%,#7c3aed 50%,#db2777 100%);-webkit-background-clip:text;background-clip:text;color:transparent;-webkit-text-fill-color:transparent;text-decoration:none}
.topnav nav{display:flex;gap:6px;align-items:center;flex:1;flex-wrap:wrap}
.topnav nav a{color:#334155;font-weight:600;font-size:14px;padding:7px 14px;border-radius:8px;background:#f1f5f9}
.topnav nav a:hover{color:var(--accent);background:#eef2ff;text-decoration:none}
.topnav nav a.active{color:#fff;background:var(--accent)}
.content{padding:24px 20px 60px}
.hero h1{margin:0 0 6px;font-size:26px}
.hero p{color:var(--muted);margin:0;max-width:900px}
.controls{margin:16px 0 8px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.controls button{border:1px solid var(--border);background:#fff;color:#0f172a;border-radius:8px;padding:7px 14px;font-weight:600;cursor:pointer;font-size:13px}
.controls button:hover{border-color:var(--accent);color:var(--accent)}
.controls .updated{color:var(--muted);font-size:12.5px}
.filters{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 4px}
.filters button{background:#f1f5f9;border:1px solid var(--border);border-radius:999px;padding:5px 12px;font-size:12.5px;cursor:pointer;color:#0f172a}
.filters button.active{background:var(--accent);color:#fff;border-color:var(--accent)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px;margin-top:14px}
.card{background:var(--card);border:1px solid var(--border);border-radius:10px;overflow:hidden;display:flex;flex-direction:column;transition:transform .15s,box-shadow .15s}
.card:hover{transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,.08)}
.thumb{aspect-ratio:16/9;background:#eef2f8;overflow:hidden}
.thumb img{width:100%;height:100%;object-fit:cover;display:block}
.body{padding:.85rem 1rem 1rem;display:flex;flex-direction:column;gap:.5rem;flex:1}
.meta-row{display:flex;gap:.4rem;align-items:center;flex-wrap:wrap;font-size:.72rem;color:var(--muted)}
.chip{padding:.15rem .55rem;border-radius:999px;font-weight:600;font-size:.68rem;text-transform:uppercase;letter-spacing:.04em;background:#eef2ff;color:#3730a3}
.source{font-weight:600;opacity:.8}.dot{opacity:.5}
.title{font-size:.98rem;font-weight:600;line-height:1.35;margin:0}
.title a{color:var(--text)}.title a:hover{color:var(--accent)}
.summary{color:var(--muted);font-size:.83rem;margin:0;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.empty{padding:3rem;text-align:center;color:var(--muted)}
.spin{display:inline-block;width:14px;height:14px;border:2px solid #cbd5e1;border-top-color:var(--accent);border-radius:50%;animation:s 1s linear infinite;vertical-align:-3px;margin-right:6px}
@keyframes s{to{transform:rotate(360deg)}}
.footer{margin-top:2rem;text-align:center;color:var(--muted);font-size:.78rem;padding:20px 0;border-top:1px solid var(--border)}
</style></head>
<body>
<header class="topnav"><div class="wrap">
  <a class="brand-name" href="/report/index.html">IoT Wireless Intel</a>
  <nav>
    <a href="/report/index.html">Overview</a>
    <a href="/report/news.html" class="active">News</a>
    <a href="/report/customers.html">Customers</a>
    <a href="/report/competitors.html">Competitors</a>
    <a href="/report/relationships.html">Relationships</a>
    <a href="/report/technology.html">Technology</a>
    <a href="/ai" style="background:linear-gradient(90deg,#7c3aed,#db2777);color:#fff;">✨ AI</a>
  </nav>
</div></header>

<main class="wrap content">
  <section class="hero">
    <h1>Technology News</h1>
    <p>Live technology headlines fetched from trusted tech sources. Cached and auto-refreshed &mdash; served instantly, re-fetched when stale.</p>
  </section>
  <div class="controls">
    <button id="refresh">⟳ Refresh</button>
    <span class="updated" id="updated">loading…</span>
  </div>
  <div class="filters" id="filters"></div>
  <div id="grid" class="grid"><div class="empty"><span class="spin"></span>Loading technology news…</div></div>
  <div class="footer">IoT Wireless Intel · dynamic technology feed</div>
</main>

<script>
let ALL=[], CAT='All';
const grid=document.getElementById('grid');
const updated=document.getElementById('updated');
const filtersEl=document.getElementById('filters');

function esc(s){return (s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function timeAgo(iso){ if(!iso) return ''; const t=new Date(iso).getTime(); if(!t) return '';
  const m=Math.floor((Date.now()-t)/60000); if(m<1)return 'just now'; if(m<60)return m+(m===1?' min ago':' mins ago');
  const h=Math.floor(m/60); if(h<24)return h+(h===1?' hour ago':' hours ago');
  const d=Math.floor(h/24); if(d<30)return d+(d===1?' day ago':' days ago');
  const mo=Math.floor(d/30); return mo+(mo===1?' month ago':' months ago'); }

function render(){
  const items = CAT==='All' ? ALL : ALL.filter(i=>i.cat===CAT);
  if(!items.length){ grid.innerHTML='<div class="empty">No headlines right now. Try Refresh.</div>'; return; }
  grid.innerHTML = items.map(i=>{
    const thumb = i.image ? `<div class="thumb"><img src="${esc(i.image)}" loading="lazy" onerror="this.parentNode.style.display='none'"></div>` : '';
    return `<article class="card">${thumb}<div class="body">
      <div class="meta-row"><span class="chip">${esc(i.cat||'Tech')}</span><span class="source">${esc(i.source)}</span>${i.pub?`<span class="dot">·</span><span>${esc(timeAgo(i.pub))}</span>`:''}</div>
      <h2 class="title"><a href="${esc(i.link)}" target="_blank" rel="noopener">${esc(i.title)}</a></h2>
      ${i.desc?`<p class="summary">${esc(i.desc)}</p>`:''}
    </div></article>`;
  }).join('');
}

function buildFilters(){
  const cats=['All',...Array.from(new Set(ALL.map(i=>i.cat||'Tech')))];
  filtersEl.innerHTML=cats.map(c=>`<button data-c="${esc(c)}" class="${c===CAT?'active':''}">${esc(c)}</button>`).join('');
  filtersEl.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{CAT=b.dataset.c;buildFilters();render();}));
}

async function load(force){
  updated.innerHTML='<span class="spin"></span>fetching…';
  try{
    const r=await fetch('/api/technews'+(force?'?force=1':''));
    const j=await r.json();
    ALL=j.items||[];
    updated.textContent=`${j.count} headlines · updated ${j.updated_at?timeAgo(j.updated_at):'now'}${j.cached?' · cached':''}`;
    buildFilters(); render();
  }catch(e){ grid.innerHTML='<div class="empty">Could not load news: '+esc(String(e))+'</div>'; updated.textContent='offline'; }
}

document.getElementById('refresh').addEventListener('click',()=>load(true));
load(false);
</script>
</body></html>
"""


# ---------------------------------------------------------------- routes
@app.get("/")
@app.get("/index.html")
def index() -> Response:
    # Backward compatibility: old report builds set AI iframe src to '/'.
    # If the browser is loading this route as an iframe, send chat view.
    if request.headers.get("Sec-Fetch-Dest", "").lower() == "iframe":
        return redirect("/ai", code=302)
    # Single-server mode: root URL serves the latest report HTML.
    return redirect("/report/", code=302)


@app.get("/api/status")
def status() -> Response:
    r = _r()
    backend = "gemini" if (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")) else "retrieval-only"
    model = getattr(A, "_LAST_MODEL", None) or "gemini-2.5-flash-lite"
    return jsonify({"chunks": len(r.chunks), "backend": backend,
                    "model": model, "index_path": str(A.INDEX_FILE)})


@app.post("/api/chat")
def chat() -> Response:
    body = request.get_json(force=True, silent=True) or {}
    msg = (body.get("message") or "").strip()
    history = body.get("history") or []
    allow_web = bool(body.get("allow_web", True))
    if not msg:
        return jsonify({"reply": "Empty message", "sources": []}), 400
    ans = A.ask(msg, history=history, retriever=_r(), allow_web=allow_web)
    if ans.used_web:
        # ensure retriever sees newly-saved web chunks next time
        _refresh()
    return jsonify({"reply": ans.reply, "sources": ans.sources,
                    "used_web": ans.used_web, "backend": ans.backend})


# ---------------------------------------------------------------- preferences
@app.get("/api/prefs")
def get_prefs() -> Response:
    return jsonify(A.load_prefs())


@app.post("/api/prefs")
def set_prefs() -> Response:
    body = request.get_json(force=True, silent=True) or {}
    return jsonify(A.save_prefs(body))


@app.post("/api/reindex")
def reindex() -> Response:
    res = A.build_index(verbose=False)
    _refresh()
    return jsonify(res)


# ---------------------------------------------------------------- news refresh
_refresh_lock = threading.Lock()
_refresh_state: dict = {"running": False, "started": None, "finished": None,
                        "ok": None, "error": None, "site": None, "mode": None}


def _do_refresh(full_refresh: bool) -> None:
    import subprocess, time, sys
    try:
        timeout_sec = 60 * 90 if full_refresh else 60 * 30
        if full_refresh:
            log.info("refresh: full mode starting 'python run.py ai-nightly'")
            p1 = subprocess.run(
                [sys.executable, "run.py", "ai-nightly"],
                cwd=str(ROOT), capture_output=True, text=True, timeout=timeout_sec,
            )
            if p1.returncode != 0:
                raise RuntimeError((p1.stderr or p1.stdout or "ai-nightly failed")[-500:])

        log.info("refresh: site mode starting 'python run.py'")
        p2 = subprocess.run(
            [sys.executable, "run.py"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=timeout_sec,
        )
        ok = p2.returncode == 0
        site = _latest_site()
        with _refresh_lock:
            _refresh_state.update({
                "running": False,
                "finished": time.time(),
                "ok": ok,
                "error": None if ok else (p2.stderr or p2.stdout)[-500:],
                "site": site.name if site else None,
                "mode": "full" if full_refresh else "site",
            })
        log.info("refresh: done mode=%s ok=%s site=%s",
                 "full" if full_refresh else "site", ok, site.name if site else "?")
    except Exception as e:  # noqa: BLE001
        with _refresh_lock:
            _refresh_state.update({
                "running": False,
                "finished": time.time(),
                "ok": False,
                "error": str(e)[:500],
                "mode": "full" if full_refresh else "site",
            })
        log.exception("refresh failed")


def _start_refresh(full_refresh: bool) -> Response:
    import time
    with _refresh_lock:
        if _refresh_state["running"]:
            return jsonify({"started": False, "reason": "already running",
                            "since": _refresh_state["started"]})
        _refresh_state.update({"running": True, "started": time.time(),
                 "finished": None, "ok": None, "error": None,
                 "mode": "full" if full_refresh else "site"})
    tname = "full-refresh" if full_refresh else "site-refresh"
    threading.Thread(target=_do_refresh, args=(full_refresh,), daemon=True, name=tname).start()
    return jsonify({"started": True, "started_at": _refresh_state["started"],
            "mode": _refresh_state["mode"]})


@app.post("/api/refresh-news")
def refresh_news() -> Response:
    # Backward-compatible alias: site refresh only.
    return _start_refresh(full_refresh=False)


@app.post("/api/refresh-site")
def refresh_site() -> Response:
    return _start_refresh(full_refresh=False)


@app.post("/api/refresh-full")
def refresh_full() -> Response:
    return _start_refresh(full_refresh=True)


@app.get("/api/refresh-news/status")
def refresh_news_status() -> Response:
    with _refresh_lock:
        return jsonify(dict(_refresh_state))


@app.get("/api/technews")
def api_technews() -> Response:
    """Cache-then-fetch technology news feed (see tech_news.py)."""
    force = request.args.get("force", "").lower() in ("1", "true", "yes")
    try:
        ttl = int(request.args.get("ttl", TN.DEFAULT_TTL_MINUTES))
    except (TypeError, ValueError):
        ttl = TN.DEFAULT_TTL_MINUTES
    return jsonify(TN.get_tech_news(force=force, ttl_minutes=ttl))


# ---------------------------------------------------------------- report passthrough
@app.get("/report/")
@app.get("/report")
def _report_root():
    site = _latest_site()
    if not site:
        return Response("<h2>No report generated yet.</h2><p>Run <code>python run.py</code> to build one.</p>",
                        mimetype="text/html"), 404
    return send_from_directory(str(site), "index.html")


@app.get("/report/news.html")
@app.get("/technews")
def _news_page() -> Response:
    """Dynamic, cache-then-fetch technology news tab."""
    return Response(_NEWS_HTML, mimetype="text/html")


@app.get("/report/<path:filename>")
def _report_file(filename: str):
    # Always serve AI chat from the live route, not from static built ai.html,
    # so stale report bundles cannot recurse into /report/ again.
    if filename.lower() == "ai.html":
        return redirect("/ai", code=302)
    site = _latest_site()
    if not site:
        return ("not found", 404)
    return send_from_directory(str(site), filename)


@app.get("/ai")
@app.get("/ai.html")
def _ai_alias():
    """Serving the chat at /ai so the report's nav link works inside Flask."""
    return Response(_CHAT_HTML, mimetype="text/html")


# ---------------------------------------------------------------- main
def serve(host: str = "127.0.0.1", port: int = 5005, open_browser: bool = True) -> None:
    # Build index on first run if missing.
    if not A.INDEX_FILE.exists():
        print("[ai] no index found — building one (first run)...")
        A.build_index(verbose=True)
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(f"http://{host}:{port}/")).start()
    print(f"[ai] AIROC AI ready at http://{host}:{port}/")
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5005)
    p.add_argument("--no-open", action="store_true")
    p.add_argument("--reindex", action="store_true", help="Force rebuild the index then exit")
    a = p.parse_args()
    if a.reindex:
        A.build_index(verbose=True)
    else:
        serve(a.host, a.port, open_browser=not a.no_open)
