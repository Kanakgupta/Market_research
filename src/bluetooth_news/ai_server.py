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
DOCS_ROOT = ROOT / "docs"


def _latest_site() -> Path | None:
    return DOCS_ROOT if DOCS_ROOT.is_dir() else None


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
:root{--bg:#f7f9fc;--card:#fff;--border:#e4e8ee;--text:#1a1f2c;--muted:#6b7280;--accent:#2563eb;--user:#eef2ff;--bot:#f8fafc;--side:#fbfcfe;}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--text);font-size:14.5px;line-height:1.5;height:100vh;display:flex;flex-direction:column;overflow:hidden}
a{color:var(--accent);text-decoration:none}
.topnav{background:var(--card);border-bottom:1px solid var(--border);flex:none;padding:0}
.topnav .wrap{display:flex;align-items:center;gap:18px;height:60px;max-width:1400px;margin:0 auto;padding:0 20px}
.topnav .brand-name{font-size:22px;font-weight:800;letter-spacing:.3px;white-space:nowrap;background:linear-gradient(90deg,#2563eb 0%,#7c3aed 50%,#db2777 100%);-webkit-background-clip:text;background-clip:text;color:transparent;-webkit-text-fill-color:transparent;text-decoration:none}
.topnav nav{display:flex;gap:6px;align-items:center;flex:1;flex-wrap:wrap}
.topnav nav a{color:#334155;font-weight:600;font-size:14px;padding:7px 14px;border-radius:8px;background:#f1f5f9;text-decoration:none}
.topnav nav a:hover{color:var(--accent);background:#eef2ff}
.topnav nav a.active{color:#fff;background:var(--accent)}
.topnav .meta-info{color:var(--muted);font-size:12px;white-space:nowrap}

/* ---- two-pane shell ---- */
.shell{flex:1;display:flex;min-height:0}
.sidebar{width:288px;flex:none;background:var(--side);border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden}
.sidebar .side-top{padding:14px 14px 8px}
.newchat{width:100%;border:1px solid var(--border);background:#fff;color:#0f172a;border-radius:10px;padding:10px 12px;font-weight:700;cursor:pointer;font-size:13.5px;display:flex;align-items:center;gap:8px;justify-content:center}
.newchat:hover{border-color:var(--accent);color:var(--accent)}
.side-scroll{flex:1;overflow-y:auto;padding:4px 10px 16px}
.side-sec{margin-top:12px}
.side-sec .hd{display:flex;align-items:center;justify-content:space-between;padding:6px 6px 4px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
.side-sec .hd .clear{cursor:pointer;font-weight:600;text-transform:none;letter-spacing:0;font-size:11.5px;color:var(--muted)}
.side-sec .hd .clear:hover{color:#b91c1c}
.qitem{display:block;width:100%;text-align:left;border:1px solid transparent;background:transparent;color:#334155;border-radius:8px;padding:8px 10px;font-size:13px;cursor:pointer;line-height:1.35;margin-bottom:2px;white-space:normal;word-break:break-word}
.qitem:hover{background:#eef2ff;border-color:#dbe4ff;color:#1e3a8a}
.qitem.recent::before{content:"↺ ";color:var(--muted)}
.qitem.suggest::before{content:"✦ ";color:#7c3aed}
.side-empty{padding:8px 10px;color:var(--muted);font-size:12.5px}

/* ---- chat column ---- */
.chatcol{flex:1;display:flex;flex-direction:column;min-width:0}
.chathead{background:var(--card);border-bottom:1px solid var(--border);padding:10px 20px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.chathead .brand{font-weight:800;font-size:18px;background:linear-gradient(90deg,#2563eb,#7c3aed 50%,#db2777);-webkit-background-clip:text;background-clip:text;color:transparent}
.chathead .pill{background:#eef2ff;color:#3730a3;padding:3px 10px;border-radius:999px;font-size:11.5px;font-weight:600}
.chathead .grow{flex:1}
.chathead button{border:1px solid var(--border);background:#fff;color:#0f172a;border-radius:8px;padding:7px 12px;font-weight:600;cursor:pointer;font-size:13px}
.chathead button:hover{border-color:var(--accent);color:var(--accent)}
.chathead a{color:var(--accent);font-weight:600;font-size:13px}
main{flex:1;overflow-y:auto;padding:22px;display:flex;flex-direction:column;gap:14px;width:100%;max-width:1000px;margin:0 auto}
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
.cites .c.report{background:#e0f2fe;color:#075985}
.ansbar{margin-top:8px;display:flex;align-items:center;gap:10px;font-size:11.5px;color:var(--muted)}
.cachetag{background:#f1f5f9;border-radius:6px;padding:2px 8px;color:#475569}
.regen{border:1px solid var(--border);background:#fff;border-radius:6px;padding:2px 9px;font-size:11.5px;cursor:pointer;color:#0f172a}
.regen:hover{border-color:var(--accent);color:var(--accent)}
footer{padding:14px 20px;background:var(--card);border-top:1px solid var(--border);flex:none}
.input-row{max-width:1000px;margin:0 auto;display:flex;gap:10px}
textarea{flex:1;border:1px solid var(--border);border-radius:10px;padding:12px 14px;font:inherit;resize:none;min-height:48px;max-height:160px}
textarea:focus{outline:none;border-color:var(--accent)}
.send{background:var(--accent);color:#fff;border:none;border-radius:10px;padding:0 18px;font-weight:700;cursor:pointer;font-size:14px}
.send:disabled{opacity:.5;cursor:not-allowed}
.opts{max-width:1000px;margin:6px auto 0;font-size:11.5px;color:var(--muted);display:flex;gap:14px;align-items:center}
.opts label{cursor:pointer}
.spin{display:inline-block;width:14px;height:14px;border:2px solid #cbd5e1;border-top-color:var(--accent);border-radius:50%;animation:s 1s linear infinite;vertical-align:-3px;margin-right:6px}
@keyframes s{to{transform:rotate(360deg)}}
.toast{position:fixed;bottom:20px;right:20px;background:#0f172a;color:#fff;padding:10px 16px;border-radius:8px;font-size:13px;opacity:0;transition:opacity .2s;z-index:99}
.toast.show{opacity:.95}
.sidetoggle{display:none}
@media(max-width:820px){
  .sidebar{position:fixed;z-index:60;top:60px;bottom:0;left:0;transform:translateX(-100%);transition:transform .2s;box-shadow:0 0 40px rgba(0,0,0,.15)}
  .sidebar.open{transform:translateX(0)}
  .sidetoggle{display:inline-flex}
}
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

<div class="shell">
  <aside class="sidebar" id="sidebar">
    <div class="side-top">
      <button class="newchat" onclick="resetChat()">＋ New chat</button>
    </div>
    <div class="side-scroll">
      <div class="side-sec">
        <div class="hd"><span>Recent</span><span class="clear" id="clearRecent" title="Clear recent">clear</span></div>
        <div id="recentList"><div class="side-empty">No questions yet.</div></div>
      </div>
      <div class="side-sec">
        <div class="hd"><span>Suggested</span></div>
        <div id="suggestList"><div class="side-empty"><span class="spin"></span>loading…</div></div>
      </div>
    </div>
  </aside>

  <div class="chatcol">
    <div class="chathead">
      <button class="sidetoggle" onclick="document.getElementById('sidebar').classList.toggle('open')">☰</button>
      <span class="brand">AIROC AI</span>
      <span class="pill" id="status">loading…</span>
      <span class="grow"></span>
      <button id="reindex">⟳ Reindex</button>
      <a href="/report/" target="_blank">Reports ↗</a>
    </div>
    <main id="chat">
      <div class="msg bot"><div class="who">AI</div><div class="bub">
        <p>Hi — I'm <b>AIROC AI</b>.</p>
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
  </div>
</div>
<div id="toast" class="toast"></div>

<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script>
const history=[];
const chat=document.getElementById('chat');
const q=document.getElementById('q');
const sendBtn=document.getElementById('send');
const statusEl=document.getElementById('status');
const metaEl=document.getElementById('meta');
const recentList=document.getElementById('recentList');
const suggestList=document.getElementById('suggestList');

function toast(msg){const t=document.getElementById('toast');t.textContent=msg;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2400)}
function escapeHtml(s){return (s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}

function citesHtml(cites){
  return '<b>Sources:</b> '+cites.map(s=>{
    const cls=s.kind==='web'?'web':(s.kind==='data'?'data':(s.kind==='report'?'report':''));
    const url=s.kind==='web'?String(s.source||'').replace(/^web:/,''):'';
    const label=`[#${s.id}] ${escapeHtml(s.title)}`+(s.page?` p.${s.page}`:'');
    return url?`<a class="c ${cls}" href="${url}" target="_blank">${label} ↗</a>`:`<span class="c ${cls}">${label}</span>`;
  }).join('');
}

function addMsg(role,html){
  const div=document.createElement('div');div.className='msg '+role;
  const who=document.createElement('div');who.className='who';who.textContent=role==='user'?'YOU':'AI';
  const bub=document.createElement('div');bub.className='bub';bub.innerHTML=html;
  div.appendChild(who);div.appendChild(bub);chat.appendChild(div);
  div.scrollIntoView({behavior:'smooth',block:'end'});
  return bub;
}

// Load a question into the input box for editing (does NOT auto-send).
function pickQuestion(text){
  q.value=text;q.focus();
  q.style.height='auto';q.style.height=Math.min(q.scrollHeight,160)+'px';
  document.getElementById('sidebar').classList.remove('open');
}

async function send(forceText){
  const text=(typeof forceText==='string'?forceText:q.value).trim();if(!text)return;
  if(typeof forceText!=='string')q.value='';
  q.style.height='auto';
  sendBtn.disabled=true;
  addMsg('user',escapeHtml(text).replace(/\n/g,'<br>'));
  const refresh=(typeof forceText==='string');
  const histSnapshot=history.slice();
  if(!refresh)history.push({role:'user',content:text});
  const pending=addMsg('bot','<span class="spin"></span>thinking…');
  try{
    const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:text,history:refresh?[]:histSnapshot,allow_web:document.getElementById('useWeb').checked,refresh})});
    const j=await r.json();
    pending.innerHTML=marked.parse(j.reply||'(no reply)');
    if(j.sources&&j.sources.length){
      const c=document.createElement('div');c.className='cites';c.innerHTML=citesHtml(j.sources);
      pending.appendChild(c);
    }
    const bar=document.createElement('div');bar.className='ansbar';
    if(j.cached)bar.innerHTML='<span class="cachetag">⚡ cached</span>';
    const rb=document.createElement('button');rb.className='regen';rb.textContent='↻ Regenerate';
    rb.onclick=()=>send(text);
    bar.appendChild(rb);pending.appendChild(bar);
    metaEl.textContent=`backend: ${j.backend}${j.used_web?' · web used':''}${j.cached?' · cached':''}`;
    if(!refresh)history.push({role:'assistant',content:j.reply||''});
    loadRecent();
  }catch(e){
    pending.innerHTML='<span style="color:#b91c1c">Error: '+escapeHtml(String(e))+'</span>';
  }finally{sendBtn.disabled=false;q.focus()}
}

document.getElementById('reindex').addEventListener('click',async()=>{
  toast('Re-indexing docs + report pages… this can take a minute');
  try{const r=await fetch('/api/reindex',{method:'POST'});const j=await r.json();
    toast('Indexed '+j.count+' chunks');refreshStatus()}
  catch(e){toast('Reindex failed: '+e)}
});

document.getElementById('clearRecent').addEventListener('click',async()=>{
  try{await fetch('/api/recent',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({clear:true})});}catch(e){}
  loadRecent();
});

function resetChat(){history.length=0;chat.innerHTML='';
  addMsg('bot',"<p>Hi — I'm <b>AIROC AI</b>.</p><p style=\"color:var(--muted);font-size:12.5px\">If I don't have the info locally I'll search the web and add it to the index.</p>");
  q.focus();
}

function renderList(el,items,cls){
  if(!items||!items.length){el.innerHTML='<div class="side-empty">'+(cls==='recent'?'No questions yet.':'None available.')+'</div>';return;}
  el.innerHTML='';
  items.forEach(t=>{
    const b=document.createElement('button');b.className='qitem '+cls;b.textContent=t;b.title=t;
    b.addEventListener('click',()=>pickQuestion(t));
    el.appendChild(b);
  });
}

async function loadRecent(){
  try{const r=await fetch('/api/recent');const j=await r.json();renderList(recentList,j.recent||[],'recent');}
  catch(e){}
}
async function loadSuggestions(){
  try{const r=await fetch('/api/suggestions');const j=await r.json();renderList(suggestList,j.suggestions||[],'suggest');}
  catch(e){suggestList.innerHTML='<div class="side-empty">None available.</div>';}
}

async function refreshStatus(){
  try{const r=await fetch('/api/status');const j=await r.json();
    statusEl.textContent=`${j.chunks} chunks · ${j.backend}`;
  }catch(e){statusEl.textContent='offline'}
}
function shouldHideSources() {
  try {
    if (window.parent && window.parent !== window) {
      if (window.parent.location.href.includes('github.io')) return true;
    }
  } catch (e) {
    return true;
  }
  if (document.referrer && document.referrer.includes('github.io')) return true;
  if (window.location.hostname.includes('github.io')) return true;
  return false;
}
if (shouldHideSources()) {
  const style = document.createElement('style');
  style.textContent = '.cites { display: none !important; }';
  document.head.appendChild(style);
}
refreshStatus();loadRecent();loadSuggestions();
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
    refresh = bool(body.get("refresh"))
    if not msg:
        return jsonify({"reply": "Empty message", "sources": []}), 400

    # Fast path: serve a cached answer unless the user forced a refresh or is
    # mid-conversation (follow-ups depend on history, so skip cache then).
    if not refresh and not history:
        cached = A.qa_cache_get(msg)
        if cached:
            A.push_recent(msg)
            return jsonify({"reply": cached["reply"], "sources": cached.get("sources", []),
                            "used_web": cached.get("used_web", False),
                            "backend": cached.get("backend", "cache"), "cached": True})

    ans = A.ask(msg, history=history, retriever=_r(), allow_web=allow_web)
    if ans.used_web:
        # ensure retriever sees newly-saved web chunks next time
        _refresh()
    # Only cache clean, standalone answers (skip fallbacks and follow-ups).
    if not history and ans.backend.startswith("gemini"):
        A.qa_cache_put(msg, ans)
    A.push_recent(msg)
    return jsonify({"reply": ans.reply, "sources": ans.sources,
                    "used_web": ans.used_web, "backend": ans.backend, "cached": False})


# ---------------------------------------------------------------- sidebar data
@app.get("/api/suggestions")
def suggestions() -> Response:
    return jsonify({"suggestions": A.dynamic_suggestions()})


@app.get("/api/recent")
def get_recent() -> Response:
    return jsonify({"recent": A.load_recent()})


@app.post("/api/recent")
def post_recent() -> Response:
    body = request.get_json(force=True, silent=True) or {}
    if body.get("clear"):
        A.clear_recent()
    elif body.get("question"):
        A.push_recent(str(body["question"]))
    return jsonify({"recent": A.load_recent()})



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
