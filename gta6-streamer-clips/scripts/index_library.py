#!/usr/bin/env python3
"""Index a meme or sound-effect folder -> library.json (+ a contact sheet of the images).

  index_library.py "path/to/meme images" memes/library.json --kind meme
  index_library.py "path/to/SFX" sfx/library.json --kind sfx

For every file: name, type, duration, whether it has audio, loudness (sfx), leading
silence (sfx), and a guessed mood from the file name. Unnamed images ("images (23).jpg")
get mood "unknown" and are put on a numbered contact sheet; look at it and fill in their
moods by hand. Moods are what an edit picks by:
  shock, confused, laugh, roast, fail, hype, cringe, sus, sad, awkward, flex, boom, whoosh, pop, other
Re-running keeps moods and notes you already filled in.
"""
import argparse
import json
import os
import re
import subprocess

MOODS = {
    "shock": r"shock|omg|oh-my-god|no-way|aint no way|holy|wtf|what-the-hell|gasp|surpris|wow",
    "confused": r"huh|confus|what\b|what-|\?\?\?|nick young|wait",
    "laugh": r"laugh|lol|lmao|hehe|ha-ha|haha|rehehe|giggl",
    "roast": r"point|clown|trash|ratio|cap|lying|he-lying|get-out|noob|bozo",
    "fail": r"fail|oof|bruh|wasted|mission-failed|death|sad-trombone|fah|augh|damage",
    "hype": r"lets-go|let.?s go|sheesh|yessir|siuu|cheer|hype|w\b|cook|aura|cinema|goat",
    "cringe": r"cringe|disappoint|facepalm|stop|nah|no-no",
    "sus": r"sus|side-eye|suspicious|hmm|thinking|amogus",
    "sad": r"sad|cry|crying|tear",
    "awkward": r"cricket|awkward|silence|snore|sleep",
    "flex": r"flex|drip|salute|respect|sigma",
    "boom": r"boom|thud|hit|impact|bass|explosion",
    "whoosh": r"whoosh|swoosh|swish|transition",
    "pop": r"pop|blink|click|select",
}
IMG = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
GIF = (".gif",)
VID = (".mp4", ".mov", ".webm", ".mkv")
AUD = (".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac")


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
                         capture_output=True, text=True).stdout
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {}


def loudness(path):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af",
                          "silencedetect=noise=-45dB:d=0.05,volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    mean = re.search(r"mean_volume: (-?[\d.]+) dB", err)
    peak = re.search(r"max_volume: (-?[\d.]+) dB", err)
    lead = 0.0
    m = re.search(r"silence_start: (-?[\d.]+)\s.*?silence_end: ([\d.]+)", err, re.S)
    if m and float(m.group(1)) <= 0.01:
        lead = float(m.group(2))
    return (float(mean.group(1)) if mean else None, float(peak.group(1)) if peak else None, round(lead, 2))


def guess(name):
    n = name.lower()
    if re.fullmatch(r"(images?|download|img|image)[ _-]*(\(\d+\))?\.\w+", n):
        return "unknown"
    for mood, pat in MOODS.items():
        if re.search(pat, n):
            return mood
    return "other"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    ap.add_argument("out")
    ap.add_argument("--kind", choices=["meme", "sfx"], required=True)
    a = ap.parse_args()
    old = {}
    if os.path.exists(a.out):
        old = {e["file"]: e for e in json.load(open(a.out, encoding="utf-8")).get("items", [])}
    items, unknown_imgs = [], []
    for root, _, files in os.walk(a.folder):
        for fn in sorted(files):
            path = os.path.join(root, fn)
            rel = os.path.relpath(path, a.folder)
            ext = os.path.splitext(fn)[1].lower()
            if ext not in IMG + GIF + VID + AUD:
                continue
            d = probe(path)
            streams = d.get("streams", [])
            dur = float(d.get("format", {}).get("duration") or 0)
            e = {"file": rel, "type": ("image" if ext in IMG else "gif" if ext in GIF else
                                       "video" if ext in VID else "audio"),
                 "duration": round(dur, 2) if dur and ext not in IMG else None,
                 "has_audio": any(s.get("codec_type") == "audio" for s in streams),
                 "mood": guess(fn), "note": "", "uses": 0}
            if a.kind == "sfx" or (e["type"] in ("audio", "video") and e["has_audio"]):
                e["mean_db"], e["peak_db"], e["lead_silence"] = loudness(path)
            if rel in old:  # keep what a person filled in
                for k in ("mood", "note", "never", "uses"):
                    if k in old[rel] and (k != "mood" or old[rel][k] not in ("unknown", "other")):
                        e[k] = old[rel][k]
            if e["type"] == "image" and e["mood"] == "unknown":
                unknown_imgs.append(path)
            items.append(e)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump({"folder": os.path.abspath(a.folder), "kind": a.kind, "items": items},
              open(a.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"{len(items)} files -> {a.out}")
    counts = {}
    for e in items:
        counts[e["mood"]] = counts.get(e["mood"], 0) + 1
    print("moods:", ", ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1])))
    if unknown_imgs:
        sheet = os.path.splitext(a.out)[0] + "_unknown.png"
        args = []
        for p in unknown_imgs[:30]:
            args += ["-i", p]
        n = len(unknown_imgs[:30])
        fc = "".join(f"[{i}:v]scale=240:240:force_original_aspect_ratio=decrease,pad=240:240:(ow-iw)/2:(oh-ih)/2,"
                     f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='{i + 1}':x=6:y=6:"
                     f"fontsize=24:fontcolor=yellow:box=1:boxcolor=black@0.7[t{i}];" for i in range(n))
        cols = min(6, n)
        layout = "|".join(f"{(i % cols) * 240}_{(i // cols) * 240}" for i in range(n))
        fc += "".join(f"[t{i}]" for i in range(n)) + (f"xstack=inputs={n}:layout={layout}:fill=black" if n > 1 else "null")
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args, "-filter_complex", fc,
                            "-frames:v", "1", sheet])
        if r.returncode == 0:
            print(f"{len(unknown_imgs)} unnamed images: look at {sheet} (numbered in this order):")
            for i, p in enumerate(unknown_imgs[:30], 1):
                print(f"  {i}: {os.path.relpath(p, a.folder)}")


if __name__ == "__main__":
    main()
