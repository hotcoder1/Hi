#!/usr/bin/env bash
# usage: render_previews.sh [--final]  (preview by default)
set -u
S=/home/user/Hi/gta6-streamer-clips/scripts
MODE=${1:-}
python3 -I - "$MODE" <<'PY'
import json, subprocess, sys
final = sys.argv[1] == "--final"
S = "/home/user/Hi/gta6-streamer-clips/scripts"
for c in json.load(open("specs.json")):
    out = f"/home/user/Hi/clips/out/typicalgamer_{c['id']}_{c['src']}.mp4" if final else f"/home/user/Hi/clips/previews/{c['id']}.mp4"
    cmd = ["python3", f"{S}/render_clip.py", f"clips/{c['src']}.mp4", out, "--layout", "stack",
           "--facecam", "0.010,0.405,0.218,0.240", "--game", "0,0,1,0.88",
           "--words", f"words/{c['src']}.json", "--title", c["title"], "--credit", "twitch.tv/typicalgamer", "--censor"]
    for k in c["keep"]: cmd += ["--keep", k]
    for p in c.get("punch", []): cmd += ["--punch", str(p)]
    if not final: cmd.append("--preview")
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(c["id"], "OK" if r.returncode == 0 else "FAIL " + r.stderr[-300:], flush=True)
    if r.returncode == 0 and not final:
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(c["poster"]), "-i", out,
                        "-frames:v", "1", "-q:v", "4", f"/home/user/Hi/clips/previews/{c['id']}.jpg"])
PY
