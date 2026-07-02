# ============================================================ Research pages
# Appended to report.py via _research.py to keep the main file maintainable.

from datetime import datetime

from .briefing import load_outputs

_RESEARCH_CSS = """
.r-card { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:14px 16px; margin-bottom:12px; }
.r-card h3 { margin:0 0 6px; font-size:15px; color:#0f172a; }
.r-card .src { color:var(--muted); font-size:12px; margin-top:4px; }
.r-card ul { margin:6px 0 0; padding-left:18px; }
.r-card .meta { color:var(--muted); font-size:12px; }
.priority-high { background:#fee2e2; color:#991b1b; padding:1px 8px; border-radius:10px; font-size:11px; font-weight:700; }
.priority-med { background:#fef3c7; color:#92400e; padding:1px 8px; border-radius:10px; font-size:11px; font-weight:700; }
.priority-low { background:#e0e7ff; color:#3730a3; padding:1px 8px; border-radius:10px; font-size:11px; font-weight:700; }
.empty-llm { background:#f1f5f9; border:1px dashed #cbd5e1; border-radius:8px; padding:16px; color:#475569; font-size:13.5px; line-height:1.6; }
.empty-llm code { background:#fff; padding:2px 6px; border-radius:4px; font-size:12.5px; }
.timeline { border-left:3px solid var(--accent); padding-left:14px; margin:10px 0; }
.timeline .item { margin-bottom:10px; }
.timeline .when { font-weight:700; color:var(--accent); font-size:12.5px; }
.repo-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:12px; }
"""


def _research_nav_template(body_html: str, title: str) -> str:
    """Wrap a body with <html>+nav+css. Returns Jinja template string."""
    from .report import _NAV_HTML, _BASE_CSS  # pylint: disable=import-outside-toplevel
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{title} \u00b7 IoT Wireless Intel</title>'
        '<style>{{ css }}\n' + _RESEARCH_CSS + '</style></head><body>'
        + _NAV_HTML +
        '<main class="wrap content">' + body_html + '</main>'
        '<footer class="footer"><div class="wrap">IoT Wireless Intel \u00b7 {{ generated_at }} PDT</div></footer>'
        '</body></html>'
    )


_BRIEFING_BODY = """
<section class="hero">
  <h1>Weekly Briefing</h1>
  <p>LLM-synthesized themes, competitor moves and customer signals from the last 7 days.</p>
</section>

{% if briefing %}
  {% if briefing.what_changed_vs_last_week %}
  <section class="section"><h2>What changed vs last week</h2>
    <p>{{ briefing.what_changed_vs_last_week }}</p>
  </section>
  {% endif %}

  {% if briefing.themes %}
  <section class="section"><h2>Top themes</h2>
    {% for t in briefing.themes %}
    <div class="r-card">
      <h3>{{ t.title }}</h3>
      <p>{{ t.narrative }}</p>
      {% if t.sources %}<div class="src">Sources: {% for s in t.sources %}<a href="{{ s }}" target="_blank" rel="noopener">[{{ loop.index }}]</a> {% endfor %}</div>{% endif %}
    </div>
    {% endfor %}
  </section>
  {% endif %}

  {% if briefing.competitor_moves %}
  <section class="section"><h2>Competitor moves</h2>
    <table class="tbl"><thead><tr><th>Vendor</th><th>Action</th><th>Implication</th></tr></thead>
    <tbody>
    {% for m in briefing.competitor_moves %}
      <tr><td><strong>{{ m.vendor }}</strong></td><td>{{ m.action }}</td><td>{{ m.implication }}</td></tr>
    {% endfor %}
    </tbody></table>
  </section>
  {% endif %}

  {% if briefing.customer_signals %}
  <section class="section"><h2>Customer signals</h2>
    <table class="tbl"><thead><tr><th>Customer</th><th>Signal</th><th>Implication</th></tr></thead>
    <tbody>
    {% for s in briefing.customer_signals %}
      <tr><td><strong>{{ s.customer }}</strong></td><td>{{ s.signal }}</td><td>{{ s.implication }}</td></tr>
    {% endfor %}
    </tbody></table>
  </section>
  {% endif %}

  {% if briefing.watch_list %}
  <section class="section"><h2>Watch list</h2>
    {% for w in briefing.watch_list %}<div class="r-card"><h3>{{ w.topic }}</h3><p>{{ w.why }}</p></div>{% endfor %}
  </section>
  {% endif %}

{% else %}
<div class="empty-llm">
  <strong>No LLM synthesis yet for this build.</strong>
  <p>To generate the briefing, paste the contents of <code>data/briefing_input.json</code> into a Copilot Chat session along with: <em>"Generate the briefing JSON per the instructions inside this file."</em> Then save the response to <code>data/briefing_output.json</code> and re-run <code>python run.py</code>.</p>
  <p>You can also point the loader at OpenAI / Anthropic / local Ollama by editing <code>src/bluetooth_news/briefing.py</code>.</p>
</div>
{% endif %}
"""


_ROADMAP_BODY = """
<section class="hero">
  <h1>AIROC Roadmap Suggestions</h1>
  <p>LLM-generated feature gap analysis and SKU recommendations based on competitor matrix, customer signals, recent news momentum and standards in flight.</p>
</section>

{% if roadmap %}
  {% if roadmap.feature_gaps %}
  <section class="section"><h2>Feature gaps to close</h2>
    <table class="tbl"><thead><tr><th>Gap</th><th>Priority</th><th>Horizon</th><th>Evidence</th></tr></thead>
    <tbody>
    {% for g in roadmap.feature_gaps %}
      <tr>
        <td><strong>{{ g.gap }}</strong></td>
        <td><span class="priority-{{ g.priority|lower }}">{{ g.priority|upper }}</span></td>
        <td>{{ g.target_horizon }}</td>
        <td>{% for e in g.evidence %}<div>{{ e }}</div>{% endfor %}</td>
      </tr>
    {% endfor %}
    </tbody></table>
  </section>
  {% endif %}

  {% if roadmap.sku_recommendations %}
  <section class="section"><h2>SKU concept recommendations</h2>
    {% for s in roadmap.sku_recommendations %}
    <div class="r-card">
      <h3>{{ s.sku_concept }}</h3>
      <div class="meta">Target apps: {% for a in s.target_apps %}<span class="tag">{{ a }}</span>{% endfor %}</div>
      <ul>{% for f in s.key_features %}<li>{{ f }}</li>{% endfor %}</ul>
      {% if s.competitive_response_to %}<div class="src">Counter to: {% for v in s.competitive_response_to %}<span class="tag">{{ v }}</span>{% endfor %}</div>{% endif %}
    </div>
    {% endfor %}
  </section>
  {% endif %}

  {% if roadmap.software_priorities %}
  <section class="section"><h2>Software / SDK priorities</h2>
    {% for sp in roadmap.software_priorities %}
    <div class="r-card"><h3>{{ sp.area }}</h3><p>{{ sp.justification }}</p><div class="src">Horizon: {{ sp.target_horizon }}</div></div>
    {% endfor %}
  </section>
  {% endif %}

  {% if roadmap.partnership_targets %}
  <section class="section"><h2>Partnership targets</h2>
    <table class="tbl"><thead><tr><th>Partner</th><th>Rationale</th></tr></thead>
    <tbody>{% for p in roadmap.partnership_targets %}<tr><td><strong>{{ p.partner }}</strong></td><td>{{ p.rationale }}</td></tr>{% endfor %}</tbody></table>
  </section>
  {% endif %}

  {% if roadmap.risks %}
  <section class="section"><h2>Risks &amp; mitigations</h2>
    <table class="tbl"><thead><tr><th>Risk</th><th>Mitigation</th></tr></thead>
    <tbody>{% for r in roadmap.risks %}<tr><td>{{ r.risk }}</td><td>{{ r.mitigation }}</td></tr>{% endfor %}</tbody></table>
  </section>
  {% endif %}

{% else %}
<div class="empty-llm">
  <strong>No roadmap synthesis yet.</strong>
  <p>Paste <code>data/roadmap_input.json</code> into Copilot Chat with: <em>"Generate the roadmap JSON per the instructions inside this file."</em> Save the response to <code>data/roadmap_output.json</code>, then re-run.</p>
</div>
{% endif %}
"""


_STANDARDS_BODY = """
<section class="hero">
  <h1>Standards Tracker</h1>
  <p>Wireless standards landscape \u2014 in-flight features and Infineon AIROC positioning.</p>
</section>

{% for s in standards %}
<section class="section">
  <h2>{{ s.family }} <span class="tag">{{ s.body }}</span></h2>
  <p><strong>Current:</strong> {{ s.current_version }}<br><strong>Next:</strong> {{ s.next_version }}</p>
  <h3>In-flight features</h3>
  <ul>{% for f in s.in_flight_features %}<li>{{ f }}</li>{% endfor %}</ul>
  <h3>AIROC position</h3>
  <p>{{ s.infineon_position }}</p>
  <p class="src"><a href="{{ s.url }}" target="_blank" rel="noopener">Official spec page \u2197</a></p>
</section>
{% endfor %}
"""


_EVENTS_BODY = """
<section class="hero">
  <h1>Events Radar</h1>
  <p>Industry events to attend or monitor for competitor announcements and customer wins.</p>
</section>

<section class="section">
<table class="tbl">
<thead><tr><th>Date</th><th>Event</th><th>Location</th><th>Themes</th><th>Watch for</th></tr></thead>
<tbody>
{% for e in events %}
  <tr>
    <td><strong>{{ e.start }}</strong>{% if e.end and e.end != e.start %} <span class="muted">\u2192 {{ e.end }}</span>{% endif %}</td>
    <td><a href="{{ e.url }}" target="_blank" rel="noopener">{{ e.name }}</a></td>
    <td>{{ e.city }}</td>
    <td>{% for t in e.themes %}<span class="tag">{{ t }}</span>{% endfor %}</td>
    <td>{{ e.watch_for }}</td>
  </tr>
{% endfor %}
</tbody>
</table>
</section>
"""


_GITHUB_BODY = """
<section class="hero">
  <h1>OSS Stack Pulse</h1>
  <p>Commit / issue / release activity for the open-source wireless stacks that ship inside competitor and partner products.</p>
</section>

<section class="section">
<div class="repo-grid">
{% for r in pulse %}
<div class="r-card">
  <h3><a href="https://github.com/{{ r.owner }}/{{ r.repo }}" target="_blank" rel="noopener">{{ r.name }}</a></h3>
  <div class="meta">{{ r.label }}</div>
  <p style="margin:8px 0;">
    <strong>{{ r.commits_30d }}</strong> commits 30d \u00b7
    <strong>{{ r.issues_open }}</strong> open issues
    {% if r.stars %}\u00b7 <strong>{{ r.stars }}</strong> \u2605{% endif %}
  </p>
  {% if r.releases %}
  <div class="src">Recent releases:</div>
  <ul>
  {% for rel in r.releases %}
    <li><a href="{{ rel.url }}" target="_blank" rel="noopener">{{ rel.tag }}</a> <span class="meta">{{ rel.published_at[:10] }}</span></li>
  {% endfor %}
  </ul>
  {% endif %}
</div>
{% endfor %}
</div>
</section>

{% if not pulse %}
<div class="empty-llm">No GitHub data yet \u2014 ensure network access. Optional: set <code>GITHUB_TOKEN</code> in <code>.env</code> to lift rate limits.</div>
{% endif %}
"""


_PATENTS_BODY = """
<section class="hero">
  <h1>Patent Radar</h1>
  <p>Recent USPTO wireless patents (last ~6 months) per tracked competitor, via PatentsView API.</p>
</section>

<section class="section">
{% if patents %}
<table class="tbl">
<thead><tr><th>Date</th><th>Vendor</th><th>Title</th><th>#</th></tr></thead>
<tbody>
{% for p in patents %}
  <tr>
    <td>{{ p.date }}</td>
    <td><strong>{{ p.vendor }}</strong></td>
    <td><a href="{{ p.url }}" target="_blank" rel="noopener">{{ p.title }}</a></td>
    <td class="meta">{{ p.number }}</td>
  </tr>
{% endfor %}
</tbody>
</table>
{% else %}
<div class="empty-llm">No patents fetched (PatentsView may be rate-limited or offline).</div>
{% endif %}
</section>
"""


_FILINGS_BODY = """
<section class="hero">
  <h1>SEC Filings (last 90d)</h1>
  <p>Recent 10-K / 10-Q / 8-K / proxy filings for US-listed competitors via SEC EDGAR.</p>
</section>

<section class="section">
{% if filings %}
<table class="tbl">
<thead><tr><th>Date</th><th>Vendor</th><th>Ticker</th><th>Form</th><th></th></tr></thead>
<tbody>
{% for f in filings %}
  <tr>
    <td>{{ f.date }}</td>
    <td><strong>{{ f.vendor }}</strong></td>
    <td>{{ f.ticker }}</td>
    <td><span class="tag">{{ f.form }}</span></td>
    <td><a href="{{ f.url }}" target="_blank" rel="noopener">view filing \u2197</a></td>
  </tr>
{% endfor %}
</tbody>
</table>
{% else %}
<div class="empty-llm">No filings fetched.</div>
{% endif %}
</section>
"""


def _render_research_pages(env, output_dir, common_ctx, articles, comp,
                           pulse, patents, filings):
    import json as _json
    briefing, roadmap = load_outputs()

    # Briefing
    tpl = env.from_string(_research_nav_template(_BRIEFING_BODY, "Weekly Briefing"))
    (output_dir / "briefing.html").write_text(tpl.render(
        briefing=briefing, active="briefing", **common_ctx
    ), encoding="utf-8")

    # Roadmap
    tpl = env.from_string(_research_nav_template(_ROADMAP_BODY, "Roadmap Suggestions"))
    (output_dir / "roadmap.html").write_text(tpl.render(
        roadmap=roadmap, active="roadmap", **common_ctx
    ), encoding="utf-8")

    # Standards
    from .data_loader import _data_dir
    sp = _data_dir() / "standards.json"
    standards = _json.loads(sp.read_text(encoding="utf-8")).get("standards", []) if sp.exists() else []
    tpl = env.from_string(_research_nav_template(_STANDARDS_BODY, "Standards"))
    (output_dir / "standards.html").write_text(tpl.render(
        standards=standards, active="standards", **common_ctx
    ), encoding="utf-8")

    # Events
    ep = _data_dir() / "events.json"
    events = _json.loads(ep.read_text(encoding="utf-8")).get("events", []) if ep.exists() else []
    # sort upcoming first
    today = datetime.now().strftime("%Y-%m-%d")
    events_sorted = sorted(events, key=lambda e: (e.get("start", "") < today, e.get("start", "")))
    tpl = env.from_string(_research_nav_template(_EVENTS_BODY, "Events"))
    (output_dir / "events.html").write_text(tpl.render(
        events=events_sorted, active="events", **common_ctx
    ), encoding="utf-8")

    # GitHub
    tpl = env.from_string(_research_nav_template(_GITHUB_BODY, "OSS Stack Pulse"))
    (output_dir / "github.html").write_text(tpl.render(
        pulse=pulse, active="github", **common_ctx
    ), encoding="utf-8")

    # Patents
    tpl = env.from_string(_research_nav_template(_PATENTS_BODY, "Patent Radar"))
    (output_dir / "patents.html").write_text(tpl.render(
        patents=patents, active="patents", **common_ctx
    ), encoding="utf-8")

    # Filings
    tpl = env.from_string(_research_nav_template(_FILINGS_BODY, "SEC Filings"))
    (output_dir / "filings.html").write_text(tpl.render(
        filings=filings, active="filings", **common_ctx
    ), encoding="utf-8")
