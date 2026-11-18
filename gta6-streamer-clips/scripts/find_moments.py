#!/usr/bin/env python3
"""Rank the most clippable moments in a long stream (VOD) from its audio and chat.

Signals (per second, each compared to the stream's own rolling baseline):
  audio   loudness spikes: yelling, laughing, explosions, crashes
  chat    message-rate spikes (shifted back by --chat-lag, chat reacts late)
  hype    laugh / shock emotes and people typing "clip"

Only needs ffmpeg + Python's standard library. Works on an audio-only download,
which is far smaller than the video for an 8-hour VOD.

  find_moments.py vods/name/123/audio.m4a --chat vods/name/123/chat.json \
      --range 1:02:00-4:30:00 --top 15 --out vods/name/123/candidates.json

Chat formats: chat-downloader JSON, TwitchDownloaderCLI JSON, yt-dlp YouTube
live_chat (.json lines), or JSON lines / CSV with seconds + text.
"""
import argparse
import collections
import csv
import json
import math
import re
import statistics
import subprocess
import sys

HYPE = re.compile(
    r"(\blu+l\b|\blo+l\b|\blmf?a+o+\b|kekw|kekl|omegalul|lulw|\bicant\b|pepelaugh|\bxd+\b|"
    r"💀|😂|🤣|😭|\bpog\w*\b|\bno ?way\b|\bwtf\b|\bholy\b|\bw+\b|\bomg\b|monkas|\?{3,}|\baware\b)",
    re.I)
CLIP = re.compile(r"\bclip(\s?it|\s?that|ped)?\b", re.I)
STOP = set("the a an and or to of in on is it i you he she we they that this what for be was are bro lol".split())


def hms(t):
    t = int(round(t))
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}"


def parse_t(x):
    v = 0.0
    for p in x.split(":"):
        v = v * 60 + float(p)
    return v


def audio_series(path, start, length):
    """Per-second RMS level (dB) via ffmpeg astats."""
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin"]
    if start:
        cmd += ["-ss", str(start)]
    if length:
        cmd += ["-t", str(length)]
    cmd += ["-i", path, "-vn", "-af",
            "aresample=8000,asetnsamples=n=8000,astats=metadata=1:reset=1,"
            "ametadata=mode=print:key=lavfi.astats.Overall.RMS_level:file=-",
            "-f", "null", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
    vals, t = [], None
    for line in p.stdout:
        if line.startswith("frame:"):
            m = re.search(r"pts_time:([\d.]+)", line)
            t = float(m.group(1)) if m else None
        elif "RMS_level=" in line and t is not None:
            v = line.split("=", 1)[1].strip()
            db = -90.0 if "inf" in v else max(-90.0, float(v))
            idx = int(t)
            while len(vals) < idx:
                vals.append(vals[-1] if vals else -90.0)
            vals.append(db)
    p.wait()
    if p.returncode != 0:
        raise SystemExit("ffmpeg could not read the audio")
    return vals


def load_chat(path):
    """-> list of (seconds, text)."""
    raw = open(path, encoding="utf-8").read()
    out = []
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and "comments" in data:  # TwitchDownloaderCLI / rechat
            for c in data["comments"]:
                msg = c.get("message", {})
                body = msg.get("body") if isinstance(msg, dict) else str(msg)
                out.append((float(c["content_offset_seconds"]), body or ""))
            return out
        if isinstance(data, list):  # chat-downloader
            for m in data:
                if "time_in_seconds" in m:
                    out.append((float(m["time_in_seconds"]), m.get("message", "") or ""))
                elif "t" in m:
                    out.append((float(m["t"]), m.get("text", "") or ""))
            return out
    except json.JSONDecodeError:
        pass
    lines = raw.splitlines()
    for line in lines:  # JSON lines: yt-dlp live_chat or {"t":..,"text":..}
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "replayChatItemAction" in d:
            r = d["replayChatItemAction"]
            t = float(r.get("videoOffsetTimeMsec", 0)) / 1000.0
            for a in r.get("actions", []):
                item = a.get("addChatItemAction", {}).get("item", {})
                rend = item.get("liveChatTextMessageRenderer") or item.get("liveChatPaidMessageRenderer")
                if rend:
                    runs = rend.get("message", {}).get("runs", [])
                    out.append((t, "".join(x.get("text", x.get("emoji", {}).get("shortcuts", [""])[0]) for x in runs)))
        elif "t" in d:
            out.append((float(d["t"]), d.get("text", "")))
    if out:
        return out
    for row in csv.reader(lines):  # CSV: seconds,text
        if len(row) >= 2:
            try:
                out.append((float(row[0]), ",".join(row[1:])))
            except ValueError:
                continue
    return out


def rolling_baseline(x, block=60, span=5):
    """Cheap rolling median: median of block medians within +-span blocks."""
    if not x:
        return []
    meds = [statistics.median(x[i:i + block]) for i in range(0, len(x), block)]
    base = []
    for i in range(len(x)):
        b = i // block
        base.append(statistics.median(meds[max(0, b - span):b + span + 1]))
    return base


def smooth(x, w):
    if w <= 1:
        return list(x)
    out, acc, q = [], 0.0, collections.deque()
    for v in x:
        q.append(v)
        acc += v
        if len(q) > w:
            acc -= q.popleft()
        out.append(acc / len(q))
    half = w // 2  # centre the window
    return out[half:] + [out[-1]] * half


def robust_z(x):
    if not x:
        return []
    med = statistics.median(x)
    mad = statistics.median([abs(v - med) for v in x]) * 1.4826 or 1.0
    return [(v - med) / mad for v in x]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("media", help="audio or video file of the VOD (or a section of it)")
    ap.add_argument("--chat", help="chat replay file")
    ap.add_argument("--range", help="only look at START-END of the VOD (e.g. the GTA VI chapter)")
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--pre", type=float, default=30, help="seconds of setup before the peak")
    ap.add_argument("--post", type=float, default=15, help="seconds of reaction after the peak")
    ap.add_argument("--gap", type=float, default=90, help="minimum seconds between two candidates")
    ap.add_argument("--chat-lag", type=float, default=8, help="how many seconds chat trails the stream")
    ap.add_argument("--offset", type=float, default=0, help="VOD time of the file's 0 s (if it is a section)")
    ap.add_argument("--out", default="candidates.json")
    a = ap.parse_args()

    start, end = 0.0, None
    if a.range:
        s, e = a.range.split("-", 1)
        start, end = parse_t(s), parse_t(e)
    length = (end - start) if end else None

    print("reading audio ...", file=sys.stderr)
    db = audio_series(a.media, start, length)
    n = len(db)
    if n < 30:
        raise SystemExit("audio too short to rank")
    base = rolling_baseline(db)
    spike = [d - b for d, b in zip(db, base)]
    s5, s1 = smooth(spike, 5), smooth(spike, 2)
    audio_z = robust_z([0.6 * x + 0.4 * y for x, y in zip(s5, s1)])

    chat_z = hype_z = None
    msgs = []
    if a.chat:
        msgs = load_chat(a.chat)
        rate, hype = [0.0] * n, [0.0] * n
        for t, text in msgs:
            i = int(t - a.offset - start - a.chat_lag)
            if 0 <= i < n:
                rate[i] += 1
                hype[i] += len(HYPE.findall(text)) * 0.5 + (2.0 if CLIP.search(text) else 0.0)
        r10 = smooth(rate, 10)
        rb = rolling_baseline(r10)
        chat_z = robust_z([math.log((r + 1) / (b + 1)) for r, b in zip(r10, rb)])
        hype_z = robust_z(smooth(hype, 10))
        print(f"chat: {len(msgs)} messages", file=sys.stderr)

    score = []
    for i in range(n):
        if chat_z:
            sc = 0.45 * audio_z[i] + 0.35 * chat_z[i] + 0.20 * hype_z[i]
        else:
            sc = audio_z[i]
        score.append(sc)

    order = sorted(range(n), key=lambda i: score[i], reverse=True)
    picked = []
    for i in order:
        if len(picked) >= a.top:
            break
        if score[i] <= 0:
            break
        if all(abs(i - j) >= a.gap for j in picked):
            picked.append(i)
    picked.sort()

    cands = []
    for k, i in enumerate(sorted(picked, key=lambda i: score[i], reverse=True), 1):
        peak = start + i
        c = {
            "id": f"c{k:02d}",
            "rank": k,
            "peak": round(peak + a.offset, 1),
            "start": round(max(start, peak - a.pre) + a.offset, 1),
            "end": round(min(start + n, peak + a.post) + a.offset, 1),
            "vod_time": hms(peak + a.offset),
            "score": round(score[i], 2),
            "audio_z": round(audio_z[i], 2),
        }
        if chat_z:
            c["chat_z"] = round(chat_z[i], 2)
            c["hype_z"] = round(hype_z[i], 2)
            lo, hi = peak + a.offset, peak + a.offset + a.chat_lag + 15
            near = [txt for t, txt in msgs if lo <= t <= hi]
            counts = collections.Counter(txt.strip()[:120] for txt in near if txt.strip())
            # hype / "clip it" lines and the most repeated lines say what happened
            ranked = sorted(counts.items(), key=lambda kv: (bool(HYPE.search(kv[0]) or CLIP.search(kv[0])), kv[1]),
                            reverse=True)
            c["chat_msgs"] = len(near)
            c["chat_sample"] = [f"{txt} x{n}" if n > 1 else txt for txt, n in ranked[:15]]
            words = collections.Counter(w for txt in near for w in re.findall(r"[\w']+|💀|😂|\?{3,}", txt.lower())
                                        if w not in STOP)
            c["top_terms"] = [w for w, _ in words.most_common(8)]
        cands.append(c)

    out = {"source": a.media, "chat": a.chat, "range": [start + a.offset, start + n + a.offset],
           "signals": ["audio"] + (["chat", "hype"] if chat_z else []), "candidates": cands}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"{'id':4} {'vod time':>9} {'score':>6} {'audio':>6} {'chat':>6}  chat says", file=sys.stderr)
    for c in cands:
        said = " | ".join(c.get("chat_sample", [])[:3])
        print(f"{c['id']:4} {c['vod_time']:>9} {c['score']:6.2f} {c['audio_z']:6.2f} "
              f"{c.get('chat_z', float('nan')):6.2f}  {said[:70]}", file=sys.stderr)
    print(f"wrote {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
