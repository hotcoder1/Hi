#!/usr/bin/env python3
"""plan.json -> storyboard.html: one card per clip with Keep / Change / Drop and notes.

  storyboard.py plan.json storyboard.html [--embed-posters] [--embed-video]

plan.json:
  {"streamer": "name", "platform": "twitch", "vod": "https://...",
   "clips": [{"id": "c03", "title": "...", "vod_time": "2:14:05", "keep": ["12-30.5", "33-48"],
              "duration": 34.0, "quote": "...", "why": "...", "layout": "stack",
              "preview": "previews/c03.mp4", "poster": "previews/c03.jpg",
              "spoiler": false, "score": 4.1}]}

Paths are relative to the HTML file. --embed-posters inlines the poster images
(use when publishing the page somewhere the files won't be); --embed-video
also inlines the preview videos (only for a few small 540x960 previews).
The page's "Export notes" button gives JSON to paste back to Claude.
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
:root{--bg:#f6f3fa;--card:#fff;--ink:#1b1426;--mute:#6b6280;--line:#e4dcef;--acc:#e0347f;--keep:#1f9d6b;--chg:#d98a00;--drop:#d33a3a}
@media (prefers-color-scheme:dark){:root{--bg:#120d1c;--card:#1d1629;--ink:#f3eefa;--mute:#a89cbf;--line:#2f2540;--acc:#ff4fa3;--keep:#2ec48a;--chg:#ffb02e;--drop:#ff5a5a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
header{padding:20px 16px 8px;max-width:1100px;margin:auto}h1{margin:0 0 4px;font-size:22px}
.sub{color:var(--mute);font-size:13px}.wrap{max-width:1100px;margin:auto;padding:8px 16px 120px;display:grid;gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;display:grid;grid-template-columns:220px 1fr;gap:16px;padding:14px}
@media (max-width:640px){.card{grid-template-columns:1fr}.media{max-width:260px;margin:auto}}
.media video,.media img{width:100%;aspect-ratio:9/16;object-fit:cover;border-radius:10px;background:#000;display:block}
.top{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}.num{font-weight:800;color:var(--acc);font-size:20px}
.title{font-weight:800;font-size:17px}.meta{font:12px ui-monospace,Menlo,monospace;color:var(--mute)}
.tag{font-size:11px;padding:2px 7px;border-radius:99px;border:1px solid var(--line);color:var(--mute)}.tag.sp{border-color:var(--chg);color:var(--chg)}
.quote{margin:8px 0;padding-left:10px;border-left:3px solid var(--acc);font-style:normal}
.row{display:grid;grid-template-columns:70px 1fr;gap:8px;font-size:13px;margin:3px 0}.row b{font:11px ui-monospace,monospace;color:var(--mute);letter-spacing:.06em;padding-top:2px}
.btns{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px}
.btns button{padding:9px;border-radius:9px;border:1px solid var(--line);background:transparent;color:var(--ink);font-weight:700;cursor:pointer}
.btns button.on[data-v=keep]{background:var(--keep);border-color:var(--keep);color:#fff}
.btns button.on[data-v=change]{background:var(--chg);border-color:var(--chg);color:#fff}
.btns button.on[data-v=drop]{background:var(--drop);border-color:var(--drop);color:#fff}
.hint{font-size:11px;color:var(--mute);margin:6px 0}textarea{width:100%;min-height:54px;border-radius:9px;border:1px solid var(--line);background:transparent;color:var(--ink);padding:8px;font:inherit}
footer{position:fixed;left:0;right:0;bottom:0;background:var(--card);border-top:1px solid var(--line);padding:10px 16px}
footer .in{max-width:1100px;margin:auto;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
footer button{padding:10px 16px;border-radius:9px;border:0;background:var(--acc);color:#fff;font-weight:800;cursor:pointer}
#count{color:var(--mute);font-size:13px}#out{width:100%;display:none;min-height:90px;max-height:30vh;font:12px ui-monospace,monospace}
"""

JS = """
const KEY='storyboard:'+document.title;let st={};try{st=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}
function save(){try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}count()}
function count(){const n=document.querySelectorAll('.card').length;const d=Object.values(st).filter(x=>x.choice).length;document.getElementById('count').textContent=d+' / '+n+' decided'}
document.querySelectorAll('.card').forEach(c=>{const id=c.dataset.id;st[id]=st[id]||{};
 c.querySelectorAll('.btns button').forEach(b=>{if(st[id].choice===b.dataset.v)b.classList.add('on');
  b.onclick=()=>{c.querySelectorAll('.btns button').forEach(x=>x.classList.remove('on'));b.classList.add('on');st[id].choice=b.dataset.v;save()}});
 const t=c.querySelector('textarea');t.value=st[id].note||'';t.oninput=()=>{st[id].note=t.value;save()}});
document.getElementById('exp').onclick=async()=>{const o={};document.querySelectorAll('.card').forEach(c=>{const s=st[c.dataset.id]||{};o[c.dataset.id]={choice:s.choice||'undecided',note:s.note||''}});
 const txt=JSON.stringify(o,null,1);const ta=document.getElementById('out');ta.style.display='block';ta.value=txt;ta.select();
 try{await navigator.clipboard.writeText(txt);document.getElementById('exp').textContent='Copied — paste it to Claude'}catch(e){document.getElementById('exp').textContent='Copy the text below'}};
count();
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("out")
    ap.add_argument("--embed-posters", action="store_true")
    ap.add_argument("--embed-video", action="store_true")
    a = ap.parse_args()
    plan = json.load(open(a.plan, encoding="utf-8"))
    base = os.path.dirname(os.path.abspath(a.out))
    e = html.escape

    def media_src(p, embed):
        if not p:
            return ""
        full = p if os.path.isabs(p) else os.path.join(base, p)
        if embed and os.path.exists(full):
            return data_uri(full)
        return p

    cards = []
    for i, c in enumerate(plan.get("clips", []), 1):
        poster = media_src(c.get("poster"), a.embed_posters or a.embed_video)
        prev = media_src(c.get("preview"), a.embed_video)
        if prev:
            media = f'<video controls playsinline preload="metadata" src="{e(prev)}" poster="{e(poster)}"></video>'
        elif poster:
            media = f'<img alt="poster frame" src="{e(poster)}">'
        else:
            media = '<div class="hint">no preview yet</div>'
        keep = ", ".join(c.get("keep", []))
        tags = f'<span class="tag">{e(c.get("layout", ""))}</span>' if c.get("layout") else ""
        if c.get("spoiler"):
            tags += '<span class="tag sp">story spoiler</span>'
        rows = ""
        for label, key in (("WHY", "why"), ("ON SCREEN", "on_screen"), ("SOUND", "sound"), ("CAPTION", "post_caption")):
            if c.get(key):
                rows += f'<div class="row"><b>{label}</b><span>{e(str(c[key]))}</span></div>'
        cards.append(f"""<section class="card" data-id="{e(c['id'])}">
<div class="media">{media}</div>
<div><div class="top"><span class="num">{i}</span><span class="title">{e(c.get('title', ''))}</span>{tags}</div>
<div class="meta">{e(c['id'])} · VOD {e(c.get('vod_time', '?'))} · {c.get('duration', '?')} s · keep {e(keep)}{' · score ' + str(c['score']) if 'score' in c else ''}</div>
{f'<blockquote class="quote">“{e(c["quote"])}”</blockquote>' if c.get('quote') else ''}
{rows}
<div class="btns"><button data-v="keep">Keep</button><button data-v="change">Change</button><button data-v="drop">Drop</button></div>
<div class="hint">Keep = post as is · Change = say how below · Drop = don't post</div>
<textarea placeholder="What works, what to change (start later, new title, other layout...)"></textarea>
</div></section>""")

    title = f"{plan.get('streamer', 'GTA 6')} clips storyboard"
    sub = " · ".join(x for x in (plan.get("platform", ""), plan.get("vod", ""), f"{len(cards)} clips") if x)
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><style>{CSS}</style></head><body>
<header><h1>{e(title)}</h1><div class="sub">{e(sub)}</div></header>
<main class="wrap">{''.join(cards)}</main>
<footer><div class="in"><button id="exp">Export notes</button><span id="count"></span><textarea id="out" readonly></textarea></div></footer>
<script>{JS}</script></body></html>"""
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"wrote {a.out} ({len(cards)} cards)")


if __name__ == "__main__":
    main()
