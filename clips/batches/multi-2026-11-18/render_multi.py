#!/usr/bin/env python3
"""Render previews (default), stills (--still) or finals (--final) for specs.json."""
import json, subprocess, sys, os, concurrent.futures as cf
sys.path.insert(0, "/home/user/Hi/gta6-streamer-clips/scripts")
import find_moments, captions
S = "/home/user/Hi/gta6-streamer-clips/scripts"
mode = sys.argv[1] if len(sys.argv) > 1 else "--preview"
only = sys.argv[2:]
L = json.load(open("layouts.json")); specs = json.load(open("specs.json"))
def punch_at(c):
    """Loudest second inside the kept ranges (skipping each range's first second), in output time."""
    db = find_moments.audio_series(f"clips/{c['id']}.mp4", 0, None)
    best, t_out, off = -999, None, 0.0
    for k in c["keep"]:
        s, e = captions.parse_keep(k)
        for i in range(int(s) + 1, int(e)):
            if i < len(db) and db[i] > best: best, t_out = db[i], off + (i - s) + 0.3
        off += e - s
    return t_out
def job(c):
    st = c["id"].rsplit("-", 1)[0]; lay = L[st]
    layout = c.get("layout", "stack")
    if mode == "--still": out = f"check/{c['id']}.png"
    elif mode == "--final": out = f"/home/user/Hi/clips/out/{c['id']}.mp4"
    else: out = f"/home/user/Hi/clips/previews/{c['id']}.mp4"
    cmd = ["python3", f"{S}/render_clip.py", f"clips/{c['id']}.mp4", out, "--layout", layout,
           "--title", c["title"], "--credit", f"twitch.tv/{st}", "--censor"]
    if not c.get("no_captions"): cmd += ["--words", f"words/{c['id']}.json"]
    if layout != "fit": cmd += ["--facecam", c.get("facecam", lay["facecam"])]
    g = c.get("game", lay.get("game"))
    if g: cmd += ["--game", g]
    for k in c["keep"]: cmd += ["--keep", k]
    if mode == "--still": cmd += ["--still", "1.5"]
    else:
        p = c.get("punch", punch_at(c))
        if p: cmd += ["--punch", f"{p:.2f}"]; c["punch"] = round(p, 2)
        if mode != "--final": cmd.append("--preview")
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = r.returncode == 0
    if ok and mode == "--preview":
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(max(0.1, (c.get("punch") or 2) + 0.2)),
                        "-i", out, "-frames:v", "1", "-q:v", "4", f"/home/user/Hi/clips/previews/{c['id']}.jpg"])
    return c["id"], ok, r.stderr[-300:]
os.makedirs("check", exist_ok=True)
todo = [c for c in specs if not only or c["id"] in only]
with cf.ThreadPoolExecutor(1 if mode == "--still" else 2) as ex:
    for cid, ok, err in ex.map(job, todo):
        print(cid, "OK" if ok else "FAIL " + err, flush=True)
if mode != "--still": json.dump(specs, open("specs.json", "w"), indent=1)
