#!/usr/bin/env python3
"""Fetch each streamer's most-viewed new Twitch clips and get them ready to judge.

  fetch_clips.py --streamers lacy,jasontheween,stableronaldo,kaicenat,ishowspeed \
      --since 2026-11-18T12:00Z --state clips/state.json --top 5 --out clips/vods/2026-11-19

For each streamer: lists clips (Twitch's clips page, range 24hr/7d/30d), keeps those
created after --since and not already used (state.json "used_urls"), takes the --top most
viewed, then for each one:
  - downloads it at up to 1080p        -> OUT/clips/<id>.mp4
  - flags muted audio (Twitch mutes clips with copyrighted music)
  - transcribes it (one Whisper model for the whole batch) -> OUT/words/<id>.json
  - makes a 6-frame strip               -> OUT/rows/<id>.png, stacked per streamer in OUT/rows_<streamer>.png
plus a grid frame per streamer for measuring the facecam -> OUT/grid_<streamer>.png.
Writes OUT/candidates.json and prints a table. Picking, trimming and titling stay a person's
(or Claude's) call: look at the strips and read the transcripts.
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def parse_since(s):
    s = s.strip().replace("Z", "+00:00")
    t = dt.datetime.fromisoformat(s)
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.timestamp()


def list_clips(login, rng, limit):
    url = f"https://www.twitch.tv/{login}/clips?filter=clips&range={rng}"
    r = subprocess.run(["timeout", "300", "yt-dlp", "--no-warnings", "--flat-playlist", "--playlist-end", str(limit),
                        "--print", "%(view_count)s|%(duration)s|%(timestamp)s|%(url)s|%(title)s", url],
                       capture_output=True, text=True)
    rows = []
    for line in r.stdout.splitlines():
        p = line.split("|", 4)
        if len(p) == 5 and p[0].isdigit() and p[2].isdigit():
            rows.append(dict(views=int(p[0]), duration=float(p[1] or 0), ts=int(p[2]), url=p[3], title=p[4]))
    return login, rows, r.stderr[-300:] if not rows else ""


def download(c, outdir):
    path = os.path.join(outdir, "clips", c["id"] + ".mp4")
    if not os.path.exists(path):
        subprocess.run(["timeout", "180", "yt-dlp", "-q", "--no-warnings", "-f", "best[height<=1080]/best",
                        "-o", path, c["url"]], capture_output=True)
    return c["id"], os.path.exists(path)


def mean_volume(path):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = re.search(r"mean_volume: (-?[\d.]+) dB", err)
    return float(m.group(1)) if m else -99.0


def strip(path, out, label):
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                             capture_output=True, text=True).stdout or 30)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", path, "-vf",
                    f"fps=6/{d:.3f},scale=240:-1,tile=6x1,drawtext=fontfile={FONT}:text='{label}':x=4:y=4:"
                    f"fontsize=16:fontcolor=yellow:box=1:boxcolor=black@0.8", "-frames:v", "1", out])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--streamers", required=True, help="comma-separated Twitch logins")
    ap.add_argument("--since", required=True, help="only clips created after this time (ISO, e.g. 2026-11-18T12:00Z)")
    ap.add_argument("--state", help="state.json with used_urls to skip")
    ap.add_argument("--top", type=int, default=5, help="candidates per streamer")
    ap.add_argument("--range", default="7d", choices=["24hr", "7d", "30d", "all"])
    ap.add_argument("--list-limit", type=int, default=40)
    ap.add_argument("--model", default="small")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    since = parse_since(a.since)
    used = set()
    if a.state and os.path.exists(a.state):
        used = set(json.load(open(a.state)).get("used_urls", []))
    for sub in ("clips", "words", "rows"):
        os.makedirs(os.path.join(a.out, sub), exist_ok=True)
    logins = [s.strip().lower() for s in a.streamers.split(",") if s.strip()]

    print(f"listing clips for {len(logins)} streamers ...", file=sys.stderr)
    cands, problems = [], []
    with cf.ThreadPoolExecutor(len(logins)) as ex:
        for login, rows, err in ex.map(lambda s: list_clips(s, a.range, a.list_limit), logins):
            fresh = sorted([r for r in rows if r["ts"] >= since and r["url"] not in used], key=lambda r: -r["views"])
            if not rows:
                problems.append(f"{login}: no clips listed ({err.strip()[:120] or 'offline, or no clips in range'})")
            elif not fresh:
                problems.append(f"{login}: {len(rows)} clips listed, none new since {a.since}")
            for n, r in enumerate(fresh[:a.top], 1):
                cands.append(dict(id=f"{login}-{n}", streamer=login, **r,
                                  created=dt.datetime.fromtimestamp(r["ts"], dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")))

    print(f"downloading {len(cands)} clips ...", file=sys.stderr)
    with cf.ThreadPoolExecutor(6) as ex:
        ok = dict(ex.map(lambda c: download(c, a.out), cands))
    cands = [c for c in cands if ok.get(c["id"])]

    model = None
    try:
        sys.path.insert(0, HERE)
        import transcribe as tr  # noqa: E402  (sets HF_HUB_DISABLE_XET, provides load_audio)
        from faster_whisper import WhisperModel
        model = WhisperModel(a.model, device="auto", compute_type="int8")
    except Exception as e:  # keep going without transcripts
        problems.append(f"transcription unavailable: {e}")
    for c in cands:
        path = os.path.join(a.out, "clips", c["id"] + ".mp4")
        c["mean_db"] = round(mean_volume(path), 1)
        c["muted"] = c["mean_db"] < -60
        wpath = os.path.join(a.out, "words", c["id"] + ".json")
        if model and not c["muted"] and not os.path.exists(wpath):
            segs, info = model.transcribe(tr.load_audio(path), word_timestamps=True, vad_filter=True,
                                          initial_prompt="GTA 6, GTA VI, Vice City, Leonida, Lucia, Jason, chat",
                                          condition_on_previous_text=False)
            out = {"language": info.language, "segments": [], "words": []}
            for s in segs:
                out["segments"].append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()})
                out["words"] += [{"start": round(w.start, 3), "end": round(w.end, 3), "word": w.word.strip()} for w in s.words or []]
            json.dump(out, open(wpath, "w"), indent=1, ensure_ascii=False)
        if os.path.exists(wpath):
            c["transcript"] = " / ".join(f"[{g['start']:.0f}] {g['text']}" for g in json.load(open(wpath))["segments"])
        strip(path, os.path.join(a.out, "rows", c["id"] + ".png"), c["id"])

    for login in logins:
        mine = [c for c in cands if c["streamer"] == login]
        rows = [os.path.join(a.out, "rows", c["id"] + ".png") for c in mine]
        if rows:
            args = sum((["-i", r] for r in rows), [])
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args, "-filter_complex",
                            f"vstack=inputs={len(rows)}" if len(rows) > 1 else "null",
                            os.path.join(a.out, f"rows_{login}.png")])
            src = next((os.path.join(a.out, "clips", c["id"] + ".mp4") for c in mine if not c["muted"]), None)
            if src:
                subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", "5", "-i", src,
                                "-frames:v", "1", "-vf", "scale=960:540,drawgrid=w=48:h=27:t=1:c=yellow@0.5,"
                                "drawgrid=w=96:h=54:t=2:c=red@0.7", os.path.join(a.out, f"grid_{login}.png")])

    json.dump(cands, open(os.path.join(a.out, "candidates.json"), "w"), indent=1, ensure_ascii=False)
    for c in cands:
        flag = " MUTED" if c["muted"] else ""
        print(f"{c['id']:18} {c['views']:>6} views {c['duration']:>4.0f}s {c['created'][11:]}  {c['title'][:50]}{flag}")
    for p in problems:
        print("note:", p)
    print(f"wrote {os.path.join(a.out, 'candidates.json')} ({len(cands)} candidates)")


if __name__ == "__main__":
    main()
