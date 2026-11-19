#!/usr/bin/env python3
"""Render a batch of clips from one batch.json, using each streamer's saved layout.

  render_batch.py batch.json --clips DIR --words DIR --streamers streamers.json --out DIR [--mode final|preview|still]

batch.json: {"clips": [{"id": "lacy-2", "streamer": "lacy", "keep": ["0-24"], "title": "...",
             "layout": "stack|fit|full", "facecam": "x,y,w,h", "game": "x,y,w,h",
             "punch": 6.2, "sfx": ["6.2|sfx/vine-boom.mp3|0.9"], "memes": ["6.6|memes/x.gif|1.3|CAPTION"],
             "no_captions": false, "post_caption": "..."}]}
Per-clip facecam/game/layout override the streamer's entry in streamers.json (facecam,
game_box, layout). With no "punch", the loudest second of the kept audio gets one.
Writes OUT/<id>.mp4 (+ OUT/<id>.jpg poster in preview mode, OUT/<id>.png in still mode),
and saves the punch times it picked back into batch.json.
"""
import argparse
import concurrent.futures as cf
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import captions  # noqa: E402
import find_moments  # noqa: E402


def punch_at(path, keeps):
    db = find_moments.audio_series(path, 0, None)
    best, t_out, off = -999, None, 0.0
    for s, e in keeps:
        for i in range(int(s) + 1, int(e)):
            if i < len(db) and db[i] > best:
                best, t_out = db[i], off + (i - s) + 0.3
        off += e - s
    return t_out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("batch")
    ap.add_argument("--clips", required=True)
    ap.add_argument("--words", required=True)
    ap.add_argument("--streamers", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", default="final", choices=["final", "preview", "still"])
    ap.add_argument("--still-at", type=float, default=1.5)
    ap.add_argument("--only", nargs="*", help="only these clip ids")
    ap.add_argument("--jobs", type=int, default=2)
    a = ap.parse_args()
    data = json.load(open(a.batch, encoding="utf-8"))
    clips = data["clips"] if isinstance(data, dict) else data
    S = json.load(open(a.streamers, encoding="utf-8"))
    os.makedirs(a.out, exist_ok=True)

    def job(c):
        st = c.get("streamer") or c["id"].rsplit("-", 1)[0]
        info = S.get(st, {})
        layout = c.get("layout") or info.get("layout") or "stack"
        cam = c.get("facecam") or info.get("facecam")
        game = c.get("game") or info.get("game_box")
        src = os.path.join(a.clips, c["id"] + ".mp4")
        words = os.path.join(a.words, c["id"] + ".json")
        ext = ".png" if a.mode == "still" else ".mp4"
        out = os.path.join(a.out, c["id"] + ext)
        handle = info.get("handle") or f"twitch.tv/{st}"
        cmd = ["python3", os.path.join(HERE, "render_clip.py"), src, out, "--layout", layout,
               "--title", c["title"], "--credit", handle, "--censor"]
        if layout == "stack" and not cam:
            return c["id"], False, "no facecam box for this streamer: measure it and save it in streamers.json"
        if cam and layout != "fit":
            cmd += ["--facecam", cam]
        if game:
            cmd += ["--game", game]
        if not c.get("no_captions") and os.path.exists(words):
            cmd += ["--words", words]
        for k in c.get("keep", []):
            cmd += ["--keep", k]
        if a.mode == "still":
            cmd += ["--still", str(c.get("still_at", a.still_at))]
        else:
            if "punch" not in c:
                keeps = [captions.parse_keep(k) for k in c.get("keep", [])] or [(0, 9999)]
                p = punch_at(src, keeps)
                c["punch"] = round(p, 2) if p else None
            if c.get("punch"):
                cmd += ["--punch", f"{c['punch']:.2f}"]
            for m in c.get("memes", []):
                cmd += ["--meme", m]
            for x in c.get("sfx", []):
                cmd += ["--sfx", x]
            if a.mode == "preview":
                cmd.append("--preview")
        r = subprocess.run(cmd, capture_output=True, text=True)
        ok = r.returncode == 0
        if ok and a.mode == "preview":
            t = max(0.1, (c.get("punch") or 2) + 0.2)
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(t), "-i", out,
                            "-frames:v", "1", "-q:v", "4", os.path.join(a.out, c["id"] + ".jpg")])
        return c["id"], ok, r.stderr[-400:]

    todo = [c for c in clips if not a.only or c["id"] in a.only]
    with cf.ThreadPoolExecutor(1 if a.mode == "still" else a.jobs) as ex:
        for cid, ok, err in ex.map(job, todo):
            print(cid, "OK" if ok else "FAIL " + err, flush=True)
    if a.mode != "still":
        json.dump(data, open(a.batch, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
