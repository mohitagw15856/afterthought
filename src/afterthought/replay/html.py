"""Static, single-file HTML viewers. No server, no network, no build step.

Data is embedded as JSON inside a <script type="application/json"> tag. The
page is deterministic for a given run so re-capturing produces no change.
"""

from __future__ import annotations

import json

from ..schemas import Run
from .diff import RunDiff

CSS = """
:root{--bg:#0f172a;--panel:#111827;--ink:#e5e7eb;--muted:#94a3b8;--user:#38bdf8;--assistant:#a78bfa;--tool:#fbbf24;--result:#34d399;--system:#f87171;--diff:#f472b6;font-family:ui-sans-serif,-apple-system,Segoe UI,Helvetica,Arial,sans-serif}
@media (prefers-color-scheme: light){:root{--bg:#f8fafc;--panel:#ffffff;--ink:#0f172a;--muted:#475569}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink)}
header{padding:14px 20px;border-bottom:1px solid #334155;display:flex;gap:16px;align-items:baseline;flex-wrap:wrap}
header h1{font-size:18px;margin:0}header .meta{color:var(--muted);font-size:13px}
main{display:grid;grid-template-columns:320px 1fr;height:calc(100vh - 56px)}
@media (max-width:800px){main{grid-template-columns:1fr;height:auto}}
nav{overflow:auto;border-right:1px solid #334155;padding:8px}
nav button{display:block;width:100%;text-align:left;background:none;border:0;color:var(--ink);padding:8px 10px;border-radius:8px;cursor:pointer;font:inherit}
nav button:hover{background:rgba(148,163,184,.12)}nav button.active{background:rgba(148,163,184,.22)}
nav button.changed{box-shadow:inset 3px 0 0 var(--diff)}
.k{display:inline-block;font-size:11px;padding:1px 6px;border-radius:999px;margin-right:6px;color:#0f172a;font-weight:600}
.k.user{background:var(--user)}.k.assistant{background:var(--assistant)}.k.tool_call{background:var(--tool)}.k.tool_result{background:var(--result)}.k.system{background:var(--system)}
section{padding:18px 22px;overflow:auto}
.toolbar{display:flex;gap:8px;align-items:center;margin-bottom:12px;flex-wrap:wrap}
.toolbar button,.toolbar select{background:var(--panel);color:var(--ink);border:1px solid #334155;border-radius:8px;padding:6px 10px;font:inherit;cursor:pointer}
pre{background:var(--panel);border:1px solid #334155;border-radius:10px;padding:14px;white-space:pre-wrap;word-break:break-word;font-size:13px;line-height:1.45;margin:0}
.step h2{margin:0 0 6px;font-size:15px}.step .meta{color:var(--muted);font-size:12px;margin-bottom:10px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:12px}@media (max-width:1000px){.cols{grid-template-columns:1fr}}
.banner{background:rgba(244,114,182,.12);border:1px solid var(--diff);border-radius:10px;padding:10px 14px;margin-bottom:12px;font-size:14px}
.muted{color:var(--muted)}
"""

JS_RUN = """
const data=JSON.parse(document.getElementById('data').textContent);
const steps=data.steps;let cur=0;let filter='all';
const nav=document.getElementById('nav');const view=document.getElementById('view');
function label(s){return `<span class="k ${s.kind}">${s.kind.replace('_',' ')}</span>${s.name?'<b>'+esc(s.name)+'</b> ':''}<span class="muted">${esc(s.content.slice(0,60).replace(/\\s+/g,' '))}</span>`}
function esc(t){return (t||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function render(){nav.innerHTML='';steps.forEach((s,i)=>{if(filter!=='all'&&s.kind!==filter)return;const b=document.createElement('button');b.innerHTML=`<span class="muted">${i}</span> ${label(s)}`;b.className=i===cur?'active':'';b.onclick=()=>{cur=i;render()};nav.appendChild(b)});
const s=steps[cur];if(!s){view.innerHTML='<p class="muted">No steps.</p>';return}
view.innerHTML=`<div class="step"><h2><span class="k ${s.kind}">${s.kind.replace('_',' ')}</span>${s.name?esc(s.name):''} <span class="muted">step ${cur+1} of ${steps.length}</span></h2><div class="meta">${s.ts||'no timestamp'}${s.ref?' · ref '+esc(s.ref):''}${s.input_hash?' · input '+s.input_hash:''}${s.output_hash?' · output '+s.output_hash:''}</div><pre>${esc(s.content)}</pre></div>`;
const a=nav.querySelector('.active');if(a)a.scrollIntoView({block:'nearest'})}
document.getElementById('prev').onclick=()=>{cur=Math.max(0,cur-1);render()};
document.getElementById('next').onclick=()=>{cur=Math.min(steps.length-1,cur+1);render()};
document.getElementById('filter').onchange=e=>{filter=e.target.value;render()};
document.addEventListener('keydown',e=>{if(e.key==='ArrowLeft'||e.key==='k')document.getElementById('prev').click();if(e.key==='ArrowRight'||e.key==='j')document.getElementById('next').click()});
render();
"""

JS_DIFF = """
const data=JSON.parse(document.getElementById('data').textContent);
const A=data.a.steps,B=data.b.steps,pairs=data.pairs,changed=new Set(data.changed);let cur=0;
const nav=document.getElementById('nav');const view=document.getElementById('view');
function esc(t){return (t||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function cell(s){return s?`<span class="k ${s.kind}">${s.kind.replace('_',' ')}</span>${s.name?'<b>'+esc(s.name)+'</b> ':''}<span class="muted">${esc(s.content.slice(0,50).replace(/\\s+/g,' '))}</span>`:'<span class="muted">(missing)</span>'}
function block(s,title){return `<div><div class="meta">${title}</div>${s?`<pre>${esc(s.content)}</pre>`:'<pre class="muted">(no step)</pre>'}</div>`}
function render(){nav.innerHTML='';pairs.forEach((p,i)=>{const b=document.createElement('button');const sa=p[0]==null?null:A[p[0]],sb=p[1]==null?null:B[p[1]];b.innerHTML=`<span class="muted">${i}</span> ${cell(sa||sb)}`;b.className=(i===cur?'active ':'')+(changed.has(i)?'changed':'');b.onclick=()=>{cur=i;render()};nav.appendChild(b)});
const p=pairs[cur];if(!p){view.innerHTML='<p class="muted">Nothing to compare.</p>';return}
const sa=p[0]==null?null:A[p[0]],sb=p[1]==null?null:B[p[1]];
view.innerHTML=`<div class="step"><h2>pair ${cur+1} of ${pairs.length} ${changed.has(cur)?'<span class="k system">differs</span>':'<span class="k tool_result">same</span>'}</h2><div class="cols">${block(sa,'A · step '+(p[0]??'-'))}${block(sb,'B · step '+(p[1]??'-'))}</div></div>`;
const a=nav.querySelector('.active');if(a)a.scrollIntoView({block:'nearest'})}
document.getElementById('prev').onclick=()=>{cur=Math.max(0,cur-1);render()};
document.getElementById('next').onclick=()=>{cur=Math.min(pairs.length-1,cur+1);render()};
document.getElementById('jump').onclick=()=>{const n=[...changed].sort((x,y)=>x-y).find(i=>i>cur);if(n!==undefined){cur=n;render()}};
document.addEventListener('keydown',e=>{if(e.key==='ArrowLeft'||e.key==='k')document.getElementById('prev').click();if(e.key==='ArrowRight'||e.key==='j')document.getElementById('next').click()});
render();
"""


def _embed(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")


def _page(title: str, header_meta: str, banner: str, toolbar_extra: str, data: object, js: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>{CSS}</style></head>
<body>
<header><h1>{title}</h1><span class="meta">{header_meta}</span><span class="meta">Afterthought replay · ← → or j/k to step</span></header>
<main>
<nav id="nav"></nav>
<section>
{f'<div class="banner">{banner}</div>' if banner else ""}
<div class="toolbar"><button id="prev">← prev</button><button id="next">next →</button>{toolbar_extra}</div>
<div id="view"></div>
</section>
</main>
<script id="data" type="application/json">{_embed(data)}</script>
<script>{js}</script>
</body></html>
"""


def _esc(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_run_html(run: Run) -> str:
    meta = f"{run.source} · {len(run.steps)} steps · {run.started.strftime('%Y-%m-%d %H:%M UTC') if run.started else 'no timestamps'}"
    filt = (
        '<select id="filter"><option value="all">all steps</option><option value="user">user</option>'
        '<option value="assistant">assistant</option><option value="tool_call">tool calls</option>'
        '<option value="tool_result">tool results</option><option value="system">system</option></select>'
    )
    return _page(_esc(run.title or run.id), meta, "", filt, run.model_dump(mode="json"), JS_RUN)


def render_diff_html(diff: RunDiff) -> str:
    changed_pairs = set()
    for c in diff.changes:
        for i, (pa, pb) in enumerate(diff.pairs):
            if (c.a is not None and pa == c.a.index) or (c.b is not None and pb == c.b.index):
                changed_pairs.add(i)
    data = {
        "a": diff.a.model_dump(mode="json"),
        "b": diff.b.model_dump(mode="json"),
        "pairs": diff.pairs,
        "changed": sorted(changed_pairs),
    }
    banner = _esc(diff.summary())
    meta = f"A: {_esc(diff.a.id)} ({len(diff.a.steps)} steps) · B: {_esc(diff.b.id)} ({len(diff.b.steps)} steps)"
    return _page(
        f"Diff: {_esc(diff.a.id)} vs {_esc(diff.b.id)}",
        meta,
        banner,
        '<button id="jump">next difference</button>',
        data,
        JS_DIFF,
    )
