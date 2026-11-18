#!/usr/bin/env python3
"""plan.json -> storyboard page: one card per clip with Keep / Change / Drop and notes.

  storyboard.py plan.json storyboard.html                 # local file, opens in a browser
  storyboard.py plan.json storyboard.html --artifact      # page body for a claude.ai Artifact

plan.json:
  {"streamer": "name", "platform": "twitch", "source": "https://...", "note": "...",
   "clips": [{"id": "c03", "title": "...", "clip_time": "12:36 UTC", "views": 19,
              "keep": ["12-30.5", "33-48"], "duration": 34.0, "quote": "...", "why": "...",
              "layout": "stack", "preview": "previews/c03.mp4", "poster": "previews/c03.jpg",
              "spoiler": false, "post_caption": "..."}]}

Choices are saved three ways, best first:
  1. Artifact published with capabilities {"db": {}}: each choice is written to the
     artifact's database as choices/<clip id> = {choice, note, title, updatedAt}, which
     Claude reads back with the ArtifactData tool (list "choices"). No pasting needed.
  2. Otherwise in the browser (localStorage), per viewer.
  3. "Copy notes" always gives the JSON to paste back to Claude.

Media paths are relative to the page. For an Artifact, publish the preview MP4s and
posters alongside it with the Artifact tool's `files` map under the same paths.
--embed-posters inlines posters as data URIs instead.
"""
import argparse
import base64
import html
import json
import mimetypes
import os


def data_uri(path):
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    with open(path, "rb") as f:
        return f"data:{mime};base64," + base64.b64encode(f.read()).decode()


CSS = """
/* Layout: one column of clip cards; phone-first, the 9:16 preview beside the notes from 720px up. */
:root{
  --bg:#f5f3f7; --surface:#ffffff; --ink:#1c1722; --mute:#6c6475; --line:#e3dde9;
  --accent:#d6307f; --accent-ink:#ffffff; --keep:#178a5e; --change:#b86e00; --drop:#c43838;
  --display:"Montserrat","Arial Black",system-ui,sans-serif;
  --body:"Inter",system-ui,-apple-system,"Segoe UI",sans-serif;
  --mono:"JetBrains Mono",ui-monospace,Menlo,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#141018; --surface:#1e1824; --ink:#f2edf6; --mute:#a99fb4; --line:#30283a;
  --accent:#ff4fa3; --accent-ink:#1a0d14; --keep:#33c48b; --change:#ffae33; --drop:#ff6464; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#141018; --surface:#1e1824; --ink:#f2edf6; --mute:#a99fb4; --line:#30283a;
  --accent:#ff4fa3; --accent-ink:#1a0d14; --keep:#33c48b; --change:#ffae33; --drop:#ff6464; color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 var(--body);
  padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.page{max-width:980px;margin:0 auto;padding-block:20px 120px;display:grid;gap:14px}
header{display:grid;gap:4px}
h1{font:800 22px/1.2 var(--display);margin:0;text-wrap:balance;letter-spacing:-.01em}
.sub{color:var(--mute);font-size:13px}
.save{font:12px var(--mono);color:var(--mute)}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px;display:grid;gap:14px}
@media (min-width:720px){.card{grid-template-columns:230px minmax(0,1fr)}}
.media{max-width:260px;width:100%;margin:0 auto}
.media video,.media img{display:block;width:100%;max-width:100%;aspect-ratio:9/16;object-fit:cover;border-radius:8px;background:#000}
.info{min-width:0;display:grid;gap:8px;align-content:start}
.top{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
.num{font:800 18px var(--display);color:var(--accent)}
.title{font:800 17px/1.25 var(--display);text-transform:uppercase;letter-spacing:.01em;text-wrap:balance}
.meta{font:12px/1.5 var(--mono);color:var(--mute);font-variant-numeric:tabular-nums}
.tag{font-size:11px;padding:1px 8px;border-radius:99px;border:1px solid var(--line);color:var(--mute)}
.tag.sp{border-color:var(--change);color:var(--change)}
.quote{margin:0;padding-left:10px;border-left:3px solid var(--accent)}
.row{display:grid;grid-template-columns:84px minmax(0,1fr);gap:8px;font-size:13px}
.row span{white-space:pre-line;min-width:0;overflow-wrap:anywhere}
.row b{font:600 10.5px/1.9 var(--mono);color:var(--mute);letter-spacing:.08em;text-transform:uppercase}
.btns{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.btns button{min-height:44px;border-radius:9px;border:1px solid var(--line);background:transparent;color:var(--ink);font:700 14px var(--body);cursor:pointer}
.btns button:focus-visible,textarea:focus-visible,footer button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.btns button[aria-pressed="true"][data-v="keep"]{background:var(--keep);border-color:var(--keep);color:var(--surface)}
.btns button[aria-pressed="true"][data-v="change"]{background:var(--change);border-color:var(--change);color:var(--surface)}
.btns button[aria-pressed="true"][data-v="drop"]{background:var(--drop);border-color:var(--drop);color:var(--surface)}
.hint{font-size:12px;color:var(--mute)}
textarea{width:100%;min-height:56px;border-radius:9px;border:1px solid var(--line);background:var(--bg);color:var(--ink);padding:8px 10px;font:14px/1.4 var(--body);resize:vertical}
.status{font:11px var(--mono);color:var(--mute);min-height:1em}
footer{position:fixed;left:0;right:0;bottom:0;background:var(--surface);border-top:1px solid var(--line);
  padding:10px max(16px,env(safe-area-inset-right,0px)) calc(10px + env(safe-area-inset-bottom,0px)) max(16px,env(safe-area-inset-left,0px))}
footer .in{max-width:980px;margin:0 auto;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
footer button{min-height:40px;padding:0 16px;border-radius:9px;border:0;background:var(--accent);color:var(--accent-ink);font:700 14px var(--body);cursor:pointer}
#count{color:var(--mute);font-size:13px;font-variant-numeric:tabular-nums}
#out{width:100%;max-height:30vh;font:12px var(--mono)}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""

JS = r"""
(function(){
const KEY='storyboard:'+document.title;
let st={};try{st=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}
let db=null;const cards=[...document.querySelectorAll('.card')];
const saveLine=document.getElementById('saveline');
function local(){try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}}
function count(){const d=cards.filter(c=>(st[c.dataset.id]||{}).choice).length;document.getElementById('count').textContent=d+' of '+cards.length+' decided'}
function paint(c){const s=st[c.dataset.id]||{};c.querySelectorAll('.btns button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.v===s.choice)));
  const t=c.querySelector('textarea');if(document.activeElement!==t)t.value=s.note||''}
const busy={},again={};
async function push(id){if(!db)return;if(busy[id]){again[id]=true;return}busy[id]=true;
  const c=document.querySelector('.card[data-id="'+id+'"]');const line=c.querySelector('.status');const s=st[id]||{};
  try{await db.doc('choices/'+id).set({choice:s.choice||'undecided',note:s.note||'',title:c.dataset.title,updatedAt:new Date().toISOString()});line.textContent='Saved for Claude'}
  catch(e){line.textContent=e&&e.code==='invalid_argument'?'View only: this choice stays on your device':'Not saved yet, will retry on your next change'}
  busy[id]=false;if(again[id]){again[id]=false;push(id)}else{pending[id]=false}}
const timers={},pending={};
function changed(id,now){local();count();pending[id]=true;clearTimeout(timers[id]);timers[id]=setTimeout(()=>{push(id)},now?0:700)}
cards.forEach(c=>{const id=c.dataset.id;st[id]=st[id]||{};paint(c);
  c.querySelectorAll('.btns button').forEach(b=>b.addEventListener('click',()=>{st[id].choice=b.dataset.v;paint(c);changed(id,true)}));
  const t=c.querySelector('textarea');t.addEventListener('input',()=>{st[id].note=t.value;changed(id,false)})});
count();
document.getElementById('exp').addEventListener('click',async()=>{const o={};cards.forEach(c=>{const s=st[c.dataset.id]||{};o[c.dataset.id]={choice:s.choice||'undecided',note:s.note||''}});
  const txt=JSON.stringify(o,null,1);const ta=document.getElementById('out');ta.hidden=false;ta.value=txt;
  try{await navigator.clipboard.writeText(txt);document.getElementById('exp').textContent='Copied'}catch(e){ta.select();document.getElementById('exp').textContent='Select and copy below'}});
if(window.claude&&window.claude.use){
  const timer=setTimeout(()=>{if(!db)saveLine.textContent='Choices are kept on this device. Use Copy notes to send them.'},10000);
  window.claude.use('db').then(d=>{if(!d){clearTimeout(timer);saveLine.textContent='Choices are kept on this device. Use Copy notes to send them.';return}
    db=d;
    db.collection('choices').onSnapshot(snap=>{clearTimeout(timer);saveLine.textContent='Choices save automatically, and Claude can read them.';
      snap.docs.forEach(doc=>{const v=doc.data()||{};const c=document.querySelector('.card[data-id="'+doc.id+'"]');if(!c)return;
        if(!pending[doc.id]&&!busy[doc.id]){st[doc.id]={choice:v.choice==='undecided'?undefined:v.choice,note:v.note||''};paint(c)}});
      local();count()},
      e=>{clearTimeout(timer);saveLine.textContent='Saving is off right now. Use Copy notes to send your choices.'})
  }).catch(()=>{clearTimeout(timer);saveLine.textContent='Choices are kept on this device. Use Copy notes to send them.'})
}else{saveLine.textContent='Choices are kept in this browser. Use Copy notes to send them to Claude.'}
})();
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan")
    ap.add_argument("out")
    ap.add_argument("--artifact", action="store_true", help="write the page body only (Artifact skeleton is added at publish)")
    ap.add_argument("--embed-posters", action="store_true")
    a = ap.parse_args()
    plan = json.load(open(a.plan, encoding="utf-8"))
    base = os.path.dirname(os.path.abspath(a.out))
    e = html.escape

    def media(p, embed):
        if not p:
            return ""
        full = p if os.path.isabs(p) else os.path.join(base, p)
        return data_uri(full) if embed and os.path.exists(full) else p

    cards = []
    for i, c in enumerate(plan.get("clips", []), 1):
        poster = media(c.get("poster"), a.embed_posters)
        prev = c.get("preview")
        if prev:
            m = f'<video controls playsinline preload="none" src="{e(prev)}" poster="{e(poster)}"></video>'
        elif poster:
            m = f'<img alt="Frame from clip {i}" src="{e(poster)}">'
        else:
            m = '<div class="hint">No preview yet</div>'
        tags = f'<span class="tag">{e(c["layout"])}</span>' if c.get("layout") else ""
        if c.get("spoiler"):
            tags += '<span class="tag sp">story spoiler</span>'
        meta = [c["id"]]
        if c.get("streamer"):
            meta.insert(0, c["streamer"])
        if c.get("clip_time"):
            meta.append(f"clipped {c['clip_time']}")
        if c.get("views") is not None:
            meta.append(f"{c['views']} views")
        if c.get("duration"):
            meta.append(f"{c['duration']:.0f} s")
        if c.get("keep"):
            meta.append("keep " + ", ".join(c["keep"]))
        rows = ""
        for label, key in (("Why", "why"), ("On screen", "on_screen"), ("Post", "post_caption")):
            if c.get(key):
                rows += f'<div class="row"><b>{label}</b><span>{e(str(c[key]))}</span></div>'
        quote = f'<blockquote class="quote">“{e(c["quote"])}”</blockquote>' if c.get("quote") else ""
        cards.append(f"""<section class="card" data-id="{e(c['id'])}" data-title="{e(c.get('title', ''))}">
<div class="media">{m}</div>
<div class="info">
<div class="top"><span class="num">{i}</span><span class="title">{e(c.get('title', ''))}</span>{tags}</div>
<div class="meta">{e(' · '.join(meta))}</div>
{quote}{rows}
<div class="btns" role="group" aria-label="Decision for clip {i}"><button type="button" data-v="keep" aria-pressed="false">Keep</button><button type="button" data-v="change" aria-pressed="false">Change</button><button type="button" data-v="drop" aria-pressed="false">Drop</button></div>
<div class="hint">Keep: post as is. Change: say how below. Drop: don't post.</div>
<textarea id="note-{e(c['id'])}" aria-label="Notes for clip {i}" placeholder="What works, what to change (start later, new title, cut the ending...)"></textarea>
<div class="status" aria-live="polite"></div>
</div></section>""")

    name = plan.get("streamer", "GTA 6")
    title = plan.get("page_title") or f"{name} GTA 6 Clips"
    sub = " · ".join(x for x in (plan.get("platform", ""), plan.get("note", ""), f"{len(cards)} clips") if x)
    body = f"""<title>{e(title)}</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono:wght@400;600&family=Montserrat:wght@800&display=swap">
<style>{CSS}</style>
<div class="page">
<header><h1>{e(title)}</h1><div class="sub">{e(sub)}</div><div class="save" id="saveline">Loading saved choices…</div></header>
<main style="display:grid;gap:14px">{''.join(cards)}</main>
</div>
<footer><div class="in"><button type="button" id="exp">Copy notes</button><span id="count"></span><textarea id="out" readonly hidden aria-label="Notes as JSON"></textarea></div></footer>
<script>{JS}</script>"""
    if not a.artifact:
        body = f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body>{body}</body></html>'
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(body)
    print(f"wrote {a.out} ({len(cards)} cards)")


if __name__ == "__main__":
    main()
