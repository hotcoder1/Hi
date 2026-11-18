#!/usr/bin/env python3
"""Cut a stream recording into a vertical 1080x1920 clip.

Layouts
  stack  facecam on top, gameplay below, captions on the seam (needs --facecam)
  fit    the whole 16:9 frame over a blurred fill, title above, captions below
  full   9:16 crop of the gameplay, optional facecam picture-in-picture (--pip)

Examples
  # layout check: one PNG at output time 3 s
  render_clip.py section.mp4 check.png --keep 12-48 --layout stack \
      --facecam 0.02,0.70,0.22,0.27 --still 3
  # low-res storyboard preview
  render_clip.py section.mp4 previews/c03.mp4 --keep 12-48 --layout stack \
      --facecam 0.02,0.70,0.22,0.27 --words words.json --title "..." --preview
  # final
  render_clip.py section.mp4 out/name_slug.mp4 --keep 12-30.5 --keep 33-48 \
      --layout stack --facecam 0.02,0.70,0.22,0.27 --words words.json \
      --title "COPS HAD NO CHANCE" --credit "twitch.tv/name" --punch 21.4

Boxes are x,y,w,h in source pixels, or as fractions of the frame (all values <= 1).
--keep ranges are in the source file's own seconds; --punch / --still are in output seconds.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import captions  # noqa: E402

FONT_DIR = os.path.normpath(os.path.join(HERE, "..", "assets", "fonts"))
OW, OH = 1080, 1920


def even(x):
    return max(2, int(round(x / 2.0)) * 2)


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    has_audio = any(s["codec_type"] == "audio" for s in d["streams"])
    num, den = (v.get("avg_frame_rate") or v.get("r_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den) if float(den) else 30.0
    return int(v["width"]), int(v["height"]), fps, has_audio, float(d["format"].get("duration", 0))


def parse_box(spec, w0, h0):
    vals = [float(v) for v in spec.split(",")]
    if len(vals) != 4:
        raise SystemExit(f"box needs x,y,w,h: {spec}")
    if all(v <= 1.0 for v in vals):
        vals = [vals[0] * w0, vals[1] * h0, vals[2] * w0, vals[3] * h0]
    x, y, w, h = vals
    x, y = max(0, x), max(0, y)
    w, h = min(w, w0 - x), min(h, h0 - y)
    return even(x), even(y), even(w), even(h)


def crop_to_aspect(box, aspect, shift=0.0, vshift=0.0):
    """Largest crop of `box` with width/height == aspect. shift/vshift in -1..1 move it off-centre."""
    x, y, w, h = box
    if w / h > aspect:
        cw, ch = even(h * aspect), h
    else:
        cw, ch = w, even(w / aspect)
    cx = x + (w - cw) / 2 * (1 + max(-1, min(1, shift)))
    cy = y + (h - ch) / 2 * (1 + max(-1, min(1, vshift)))
    return f"crop={cw}:{ch}:{even(cx)}:{even(cy)}"


IMG_EXT = (".png", ".jpg", ".jpeg", ".bmp", ".webp")


def has_audio_stream(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                          "-of", "csv=p=0", path], capture_output=True, text=True).stdout
    return bool(out.strip())


def parse_meme(spec):
    p = spec.split("|")
    if len(p) < 2:
        raise SystemExit(f'--meme needs "T|file[|dur|caption|vol]": {spec}')
    path = os.path.abspath(p[1])
    if not os.path.exists(path):
        raise SystemExit(f"meme file not found: {path}")
    m = {"t": float(p[0]), "path": path, "dur": float(p[2]) if len(p) > 2 and p[2] else 1.5,
         "caption": p[3] if len(p) > 3 else "", "vol": float(p[4]) if len(p) > 4 and p[4] else 1.0}
    m["kind"] = ("image" if path.lower().endswith(IMG_EXT) else "gif" if path.lower().endswith(".gif") else "video")
    m["has_audio"] = m["kind"] == "video" and has_audio_stream(path)
    return m


def parse_sfx(spec):
    p = spec.split("|")
    path = os.path.abspath(p[1])
    if not os.path.exists(path):
        raise SystemExit(f"sfx file not found: {path}")
    return {"t": float(p[0]), "path": path, "vol": float(p[2]) if len(p) > 2 and p[2] else 0.9}


def meme_input_args(m, fps):
    d = f"{m['dur'] + 0.2:.3f}"
    if m["kind"] == "image":
        return ["-loop", "1", "-framerate", str(fps), "-t", d, "-i", m["path"]]
    if m["kind"] == "gif":
        return ["-ignore_loop", "0", "-t", d, "-i", m["path"]]
    return ["-stream_loop", "-1", "-t", d, "-i", m["path"]]


def build(args):
    w0, h0, sfps, has_audio, dur = probe(args.src)
    if args.still is not None:
        has_audio = False  # a still has no audio output, so leave it out of the graph
    keeps = [captions.parse_keep(k) for k in args.keep] if args.keep else [(0.0, dur)]
    fps = args.fps or min(60, round(sfps) or 30)
    t0 = max(0.0, min(s for s, _ in keeps) - 0.5)
    t_end = max(e for _, e in keeps) + 0.5
    out_dur = sum(e - s for s, e in keeps)

    memes = [parse_meme(m) for m in (args.meme or [])]
    sfxs = [parse_sfx(x) for x in (args.sfx or [])] if args.still is None else []
    extra_inputs, meme_idx, sfx_idx = [], [], []
    nin = 1
    for m in memes:
        extra_inputs += meme_input_args(m, fps)
        meme_idx.append(nin); nin += 1
    for x in sfxs:
        extra_inputs += ["-i", os.path.abspath(x["path"])]
        sfx_idx.append(nin); nin += 1

    layout = args.layout or ("stack" if args.facecam else "fit")
    if layout == "stack" and not args.facecam:
        raise SystemExit("stack layout needs --facecam x,y,w,h")
    game = parse_box(args.game, w0, h0) if args.game else (0, 0, w0, h0)
    cam = parse_box(args.facecam, w0, h0) if args.facecam else None

    f = []
    n = len(keeps)
    vsrc = [f"[vs{i}]" for i in range(n)]
    asrc = [f"[as{i}]" for i in range(n)]
    f.append(f"[0:v]split={n}{''.join(vsrc)}" if n > 1 else "[0:v]null[vs0]")
    if has_audio:
        f.append(f"[0:a]asplit={n}{''.join(asrc)}" if n > 1 else "[0:a]anull[as0]")
    for i, (s, e) in enumerate(keeps):
        a, b = s - t0, e - t0
        f.append(f"{vsrc[i]}trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[v{i}]")
        if has_audio:
            d = e - s
            fade = min(0.015, d / 4)
            f.append(f"{asrc[i]}atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS,"
                     f"afade=t=in:d={fade:.3f},afade=t=out:st={d - fade:.3f}:d={fade:.3f}[a{i}]")
    if n > 1:
        pairs = "".join(f"[v{i}]" + (f"[a{i}]" if has_audio else "") for i in range(n))
        f.append(f"{pairs}concat=n={n}:v=1:a={1 if has_audio else 0}[cv]" + ("[ca]" if has_audio else ""))
    else:
        f.append("[v0]null[cv]")
        if has_audio:
            f.append("[a0]anull[ca]")
    f.append(f"[cv]fps={fps},setsar=1[cvf]")

    geo = {"layout": layout, "src_size": [w0, h0]}
    title_y, caption_y = 200, 1250
    if layout == "stack":
        fx, fy, fw, fh = cam
        hf = args.cam_h or max(540, min(840, even(OW * fh / fw)))
        hf = even(hf)
        hg = OH - hf
        f.append("[cvf]split=2[c1][c2]")
        f.append(f"[c1]{crop_to_aspect(cam, OW / hf)},scale={OW}:{hf}:flags=lanczos,setsar=1[cam]")
        f.append(f"[c2]{crop_to_aspect(game, OW / hg, args.shift, args.vshift)},scale={OW}:{hg}:flags=lanczos,setsar=1[gm]")
        f.append(f"[cam][gm]vstack=inputs=2,drawbox=x=0:y={hf - 3}:w={OW}:h=6:color=black@0.85:t=fill[lay]")
        caption_y, title_y = hf, hf + 100  # title under the seam, over the gameplay sky, clear of the face
        geo.update(cam_panel_h=hf)
    elif layout == "fit":
        x, y, w, h = game
        z = max(1.0, args.fit_zoom)
        cw = even(w / z)
        fg_h = even(OW * h / cw)
        fg_y = even((OH - fg_h) / 2 - 80)
        f.append("[cvf]split=2[b1][b2]")
        f.append(f"[b1]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=12:2,"
                 f"eq=brightness=-0.18:saturation=1.15,scale={OW}:{OH}[bg]")
        f.append(f"[b2]crop={cw}:{h}:{even(x + (w - cw) / 2)}:{y},scale={OW}:{fg_h}:flags=lanczos,setsar=1[fg]")
        f.append(f"[bg][fg]overlay=0:{fg_y}[lay]")
        title_y = max(120, fg_y - 250)
        caption_y = min(1500, fg_y + fg_h + 140)
        geo.update(fg_y=fg_y, fg_h=fg_h)
    else:  # full
        gcrop = f"{crop_to_aspect(game, OW / OH, args.shift, args.vshift)},scale={OW}:{OH}:flags=lanczos,setsar=1"
        if cam and args.pip:
            pw = 420
            ph = even(pw * cam[3] / cam[2])
            f.append("[cvf]split=2[p1][p2]")
            f.append(f"[p1]{gcrop}[g1]")
            f.append(f"[p2]crop={cam[2]}:{cam[3]}:{cam[0]}:{cam[1]},scale={pw}:{ph},setsar=1[pip]")
            f.append(f"[g1][pip]overlay={OW - pw - 40}:130[lay]")
            title_y = 130 + ph + 40
        else:
            f.append(f"[cvf]{gcrop}[lay]")
            title_y = 200
        caption_y = 1150
    if args.caption_y:
        caption_y = args.caption_y
    if args.title_y:
        title_y = args.title_y
    geo.update(caption_y=caption_y, title_y=title_y, fps=fps, duration=round(out_dur, 2))

    last = "[lay]"
    if args.punch:
        expr = "1"
        for p in sorted(args.punch, reverse=True):
            expr = f"if(between(it,{p:.2f},{p + 0.5:.2f}),{args.punch_zoom}-{args.punch_zoom - 1}*(it-{p:.2f})/0.5,{expr})"
        f.append(f"{last}zoompan=z='{expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={OW}x{OH}:fps={fps}[pz]")
        last = "[pz]"

    for k, m in enumerate(memes):
        i, T, d = meme_idx[k], m["t"], m["dur"]
        f.append(f"[{i}:v]fps={fps},format=rgba,split=2[mb{k}][mf{k}]")
        f.append(f"[mb{k}]scale={OW}:{OH}:force_original_aspect_ratio=increase,crop={OW}:{OH},boxblur=20:2,"
                 f"eq=brightness=-0.28,format=rgba[mbb{k}]")
        f.append(f"[mf{k}]scale={OW}:1300:force_original_aspect_ratio=decrease[mff{k}]")
        f.append(f"[mbb{k}][mff{k}]overlay=(W-w)/2:(H-h)/2-110,format=yuv420p,setsar=1,trim=duration={d:.3f},"
                 f"setpts=PTS-STARTPTS+{T:.3f}/TB[mm{k}]")
        f.append(f"{last}[mm{k}]overlay=0:0:enable='between(t,{T:.3f},{T + d:.3f})':eof_action=pass[mo{k}]")
        last = f"[mo{k}]"
    windows = [(m["t"], m["t"] + m["dur"]) for m in memes]

    use_ass = bool(args.ass or args.words or args.title or args.credit or any(m["caption"] for m in memes))
    if use_ass:
        f.append(f"{last}ass=c.ass:fontsdir=fonts[sub]")
        last = "[sub]"
    if args.preview and not args.still:
        f.append(f"{last}scale=540:960:flags=bicubic[pv]")
        last = "[pv]"
    f.append(f"{last}format=yuv420p[vout]")
    if has_audio:
        mix_in = []
        if windows:
            cond = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in windows)
            f.append(f"[ca]volume='if({cond},{args.meme_duck},1)':eval=frame,aresample=48000,"
                     f"aformat=channel_layouts=stereo[cad]")
        else:
            f.append("[ca]aresample=48000,aformat=channel_layouts=stereo[cad]")
        mix_in.append("[cad]")
        for k, m in enumerate(memes):
            if m["has_audio"]:
                ms = int(m["t"] * 1000)
                f.append(f"[{meme_idx[k]}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{m['dur']:.3f},"
                         f"asetpts=PTS-STARTPTS,afade=t=out:st={max(0, m['dur'] - 0.15):.3f}:d=0.15,"
                         f"adelay=delays={ms}:all=1,volume={m['vol']}[ma{k}]")
                mix_in.append(f"[ma{k}]")
        for k, x in enumerate(sfxs):
            ms = int(x["t"] * 1000)
            f.append(f"[{sfx_idx[k]}:a]aresample=48000,silenceremove=start_periods=1:start_threshold=-45dB,"
                     f"aformat=channel_layouts=stereo,"
                     f"adelay=delays={ms}:all=1,volume={x['vol']}[sx{k}]")
            mix_in.append(f"[sx{k}]")
        if len(mix_in) > 1:
            f.append(f"{''.join(mix_in)}amix=inputs={len(mix_in)}:normalize=0:duration=first[cmx]")
            src_a = "[cmx]"
        else:
            src_a = "[cad]"
        if args.no_loudnorm:
            f.append(f"{src_a}anull[aout]")
        else:
            f.append(f"{src_a}loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000,alimiter=limit=0.8:level=false[aout]")

    ass_text = None
    if args.ass:
        with open(args.ass, encoding="utf-8") as fh_:
            ass_text = fh_.read()
    elif use_ass:
        words = captions.load_words(args.words) if args.words else []
        title_dur = args.title_dur if args.title_dur is not None else (3.5 if layout == "stack" else None)
        ass_text = captions.build_ass(words, keeps, caption_y=caption_y, title=args.title, title_y=title_y,
                                      title_dur=title_dur, credit=args.credit, duration=out_dur,
                                      accent=args.accent, do_censor=args.censor, size=args.caption_size,
                                      hide=windows, meme_caps=[(m["t"], m["t"] + m["dur"], m["caption"]) for m in memes if m["caption"]])
    geo.update(memes=[{"t": m["t"], "dur": m["dur"], "file": os.path.basename(m["path"])} for m in memes],
               sfx=[{"t": x["t"], "file": os.path.basename(x["path"])} for x in sfxs])
    return f, ass_text, t0, t_end, has_audio, geo, extra_inputs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--keep", action="append", help="kept range in source seconds (repeatable, in order)")
    ap.add_argument("--layout", choices=["stack", "fit", "full"])
    ap.add_argument("--facecam", help="facecam box x,y,w,h")
    ap.add_argument("--game", help="gameplay box x,y,w,h (default: whole frame)")
    ap.add_argument("--shift", type=float, default=0.0, help="move gameplay crop left/right, -1..1")
    ap.add_argument("--vshift", type=float, default=0.0, help="move gameplay crop up/down, -1..1")
    ap.add_argument("--cam-h", type=int, help="stack: facecam panel height (540-840 typical)")
    ap.add_argument("--fit-zoom", type=float, default=1.0, help="fit: trim the sides to make gameplay bigger (1.0-1.35)")
    ap.add_argument("--pip", action="store_true", help="full: overlay the facecam top-right")
    ap.add_argument("--words", help="words.json from transcribe.py (source-file times)")
    ap.add_argument("--ass", help="use this ASS file instead of generating captions")
    ap.add_argument("--title")
    ap.add_argument("--title-dur", type=float, help="seconds the title stays (default: 3.5 in stack, whole clip otherwise)")
    ap.add_argument("--title-y", type=int)
    ap.add_argument("--caption-y", type=int)
    ap.add_argument("--caption-size", type=int, default=96)
    ap.add_argument("--credit", help='e.g. "twitch.tv/name"')
    ap.add_argument("--accent", default="#FF4FA3", help="highlight colour for the current word")
    ap.add_argument("--censor", action="store_true", help="star out swears in captions")
    ap.add_argument("--punch", type=float, action="append", help="zoom punch at this output second (repeatable)")
    ap.add_argument("--punch-zoom", type=float, default=1.15)
    ap.add_argument("--meme", action="append",
                    help='full-screen meme cutaway "T|file|dur|CAPTION|vol" (output seconds; dur 1.5, caption and vol optional)')
    ap.add_argument("--meme-duck", type=float, default=0.35, help="stream volume while a meme is up")
    ap.add_argument("--sfx", action="append", help='sound effect "T|file|vol" at output second T (vol default 0.9)')
    ap.add_argument("--fps", type=int)
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--preview", action="store_true", help="540x960 fast encode for the storyboard")
    ap.add_argument("--still", type=float, help="write one PNG at this output second instead of a video")
    ap.add_argument("--no-loudnorm", action="store_true")
    ap.add_argument("--print-cmd", action="store_true")
    args = ap.parse_args()

    graph, ass_text, t0, t_end, has_audio, geo, extra_inputs = build(args)
    tmp = tempfile.mkdtemp(prefix="clip_")
    try:
        if ass_text is not None:
            with open(os.path.join(tmp, "c.ass"), "w", encoding="utf-8") as fh_:
                fh_.write(ass_text)
            os.makedirs(os.path.join(tmp, "fonts"))
            if os.path.isdir(FONT_DIR):
                for name in os.listdir(FONT_DIR):
                    if name.lower().endswith((".ttf", ".otf")):
                        shutil.copy(os.path.join(FONT_DIR, name), os.path.join(tmp, "fonts", name))
        src = os.path.abspath(args.src)
        out = os.path.abspath(args.out)
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-nostdin",
               "-ss", f"{t0:.3f}", "-t", f"{t_end - t0:.3f}", "-i", src, *extra_inputs,
               "-filter_complex", ";".join(graph), "-map", "[vout]"]
        if args.still is not None:
            cmd += ["-ss", f"{args.still:.3f}", "-frames:v", "1", out]
        else:
            if has_audio:
                cmd += ["-map", "[aout]", "-c:a", "aac", "-b:a", "96k" if args.preview else "192k"]
            cmd += ["-c:v", "libx264", "-preset", "veryfast" if args.preview else "medium",
                    "-crf", "30" if args.preview else str(args.crf), "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", out]
        if args.print_cmd:
            print(" ".join(cmd), file=sys.stderr)
        r = subprocess.run(cmd, cwd=tmp)
        if r.returncode != 0:
            raise SystemExit(f"ffmpeg failed ({r.returncode}). Re-run with --print-cmd to see the graph.")
        print(json.dumps({"out": out, **geo}))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
