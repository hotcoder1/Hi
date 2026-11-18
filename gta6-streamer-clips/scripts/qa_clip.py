#!/usr/bin/env python3
"""Check a finished clip before calling it done.

  qa_clip.py out/name_slug.mp4 [--sheet out/qa/name_slug_sheet.png] [--max-len 60]

Prints PASS / WARN / FAIL per check and exits 1 on any FAIL:
  format    1080x1920, H.264, yuv420p, audio stream present
  length    <= --max-len (default 60 s; Shorts allow up to 180 s)
  loudness  integrated around -14 LUFS, true peak <= -1 dBTP
  black     no black stretches >= 0.5 s
  freeze    no frozen picture >= 2 s (dropped stream frames, buffering)
  sheet     contact sheet PNG to look at (captions readable, nothing over the face)
"""
import argparse
import json
import os
import re
import subprocess
import sys


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("--sheet", help="where to write the contact sheet PNG")
    ap.add_argument("--max-len", type=float, default=60)
    a = ap.parse_args()
    results = []

    def res(level, name, msg):
        results.append(level)
        print(f"{level:4}  {name:9} {msg}")

    p = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", a.clip]).stdout or "{}")
    streams = p.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    au = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not v:
        res("FAIL", "format", "no video stream")
        sys.exit(1)
    dur = float(p["format"].get("duration", 0))
    num, den = v.get("avg_frame_rate", "0/1").split("/")
    fps = float(num) / float(den) if float(den) else 0
    ok = v["width"] == 1080 and v["height"] == 1920 and v["codec_name"] == "h264" and v.get("pix_fmt") == "yuv420p"
    res("PASS" if ok else "FAIL", "format",
        f"{v['width']}x{v['height']} {v['codec_name']} {v.get('pix_fmt')} {fps:.2f} fps, audio: {au['codec_name'] if au else 'NONE'}")
    if not au:
        res("FAIL", "audio", "no audio stream")
    if dur > 180:
        res("FAIL", "length", f"{dur:.1f} s (over the 3-minute Shorts limit)")
    elif dur > a.max_len:
        res("WARN", "length", f"{dur:.1f} s (longer than {a.max_len:.0f} s; tighter usually performs better)")
    elif dur < 7:
        res("WARN", "length", f"{dur:.1f} s (very short; is the setup there?)")
    else:
        res("PASS", "length", f"{dur:.1f} s")

    if au:
        err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", a.clip, "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
        summary = err[err.rfind("Summary:"):]
        i_m = re.search(r"I:\s+(-?[\d.]+) LUFS", summary)
        p_m = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summary)
        if i_m:
            lufs = float(i_m.group(1))
            peak = float(p_m.group(1)) if p_m and p_m.group(1) != "-inf" else -99
            lvl = "PASS" if -16 <= lufs <= -12 and peak <= -0.9 else ("FAIL" if peak > 0 else "WARN")
            res(lvl, "loudness", f"{lufs:.1f} LUFS integrated, true peak {peak:.1f} dBTP (target -14 / <= -1)")
        else:
            res("WARN", "loudness", "could not measure")

    err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", a.clip, "-an", "-vf",
               "blackdetect=d=0.5:pix_th=0.10,freezedetect=n=0.003:d=2", "-f", "null", "-"]).stderr
    blacks = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", err)
    freezes = re.findall(r"freeze_start: ([\d.]+)", err)
    res("WARN" if blacks else "PASS", "black", ", ".join(f"{float(s):.1f}-{float(e):.1f}s" for s, e in blacks) or "none")
    res("WARN" if freezes else "PASS", "freeze", ", ".join(f"at {float(s):.1f}s" for s in freezes) or "none")

    sheet = a.sheet or os.path.splitext(a.clip)[0] + "_sheet.png"
    os.makedirs(os.path.dirname(os.path.abspath(sheet)), exist_ok=True)
    n = 12
    step = max(dur / n, 0.1)
    r = run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", a.clip, "-vf",
             f"fps=1/{step:.3f},scale=270:480,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
             f"text='%{{pts\\:hms}}':x=6:y=6:fontsize=18:fontcolor=yellow:box=1:boxcolor=black@0.6,tile=6x2",
             "-frames:v", "1", sheet])
    if r.returncode != 0:  # drawtext font may be missing (macOS/Windows): retry without timestamps
        r = run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", a.clip, "-vf",
                 f"fps=1/{step:.3f},scale=270:480,tile=6x2", "-frames:v", "1", sheet])
    res("PASS" if r.returncode == 0 else "WARN", "sheet", sheet if r.returncode == 0 else "could not write contact sheet")
    print("-> look at the sheet: captions readable, nothing over the face or the action, title spelled right")
    sys.exit(1 if "FAIL" in results else 0)


if __name__ == "__main__":
    main()
