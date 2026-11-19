#!/usr/bin/env python3
"""Put a batch of finished clips into one folder (a subfolder per streamer) and zip it.

  package_batch.py batch.json --clips-dir out --streamers streamers.json --name "GTA6 Clips 2026-11-19" --dest dist

Each clip goes to <name>/<Streamer>/<id> <title-slug>.mp4 with its post caption next to it as
a .txt, plus <name>/POST_CAPTIONS.md listing every clip. Writes <dest>/<name>.zip (stored, not
compressed: video doesn't shrink) and prints its path and size.
"""
import argparse
import json
import os
import re
import shutil
import zipfile


def slug(s):
    s = re.sub(r"[^a-z0-9 ]", "", s.lower())
    return "-".join(s.split())[:48]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("batch")
    ap.add_argument("--clips-dir", required=True)
    ap.add_argument("--streamers", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--dest", required=True)
    a = ap.parse_args()
    data = json.load(open(a.batch, encoding="utf-8"))
    clips = data["clips"] if isinstance(data, dict) else data
    S = json.load(open(a.streamers, encoding="utf-8"))
    root = os.path.join(a.dest, a.name)
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root)
    lines = [f"# {a.name}", "", "1080x1920, streamer credited on screen. Post each video with the caption under its name.", ""]
    n = 0
    for c in clips:
        src = os.path.join(a.clips_dir, c["id"] + ".mp4")
        if not os.path.exists(src):
            print("missing", src)
            continue
        st = c.get("streamer") or c["id"].rsplit("-", 1)[0]
        folder = os.path.join(root, S.get(st, {}).get("name") or st)
        os.makedirs(folder, exist_ok=True)
        base = f"{c['id']} {slug(c['title'])}"
        shutil.copy(src, os.path.join(folder, base + ".mp4"))
        cap = c.get("post_caption", "")
        open(os.path.join(folder, base + ".txt"), "w", encoding="utf-8").write(cap + "\n")
        lines += [f"## {S.get(st, {}).get('name') or st}: {base}.mp4", f"On screen: {c['title'].upper()}", "", cap, ""]
        n += 1
    open(os.path.join(root, "POST_CAPTIONS.md"), "w", encoding="utf-8").write("\n".join(lines))
    zp = os.path.join(a.dest, a.name + ".zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_STORED) as z:
        for base_dir, _, files in os.walk(root):
            for f in sorted(files):
                full = os.path.join(base_dir, f)
                z.write(full, os.path.relpath(full, a.dest))
    print(f"{n} clips -> {zp} ({os.path.getsize(zp) / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
