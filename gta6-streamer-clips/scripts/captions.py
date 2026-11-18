#!/usr/bin/env python3
"""Word timings -> ASS subtitle file for a vertical 1080x1920 clip.

Pop-in captions (1-3 words at a time, current word highlighted), an optional
hook title at the top and a streamer credit line. Times are remapped through
the same keep-ranges the renderer uses, so captions stay in sync after cuts.

Used as a module by render_clip.py, or standalone:
  python3 captions.py words.json out.ass --keep 12.5-41 --keep 44-52 \
      --caption-y 760 --title "HE GOT 5 STARS IN 10 SECONDS" --credit "twitch.tv/name"
"""
import argparse
import json
import re
import sys

W, H = 1080, 1920

# A short list is enough for TikTok/Shorts-safe captions; extend per channel.
SWEARS = ["fuck", "fucking", "fucked", "shit", "bitch", "motherfucker", "dick", "pussy",
          "asshole", "cunt", "nigga", "nigger", "retard", "faggot"]


def parse_keep(spec):
    """'12.5-41' or '1:02.5-1:10' -> (start, end) seconds."""
    def t(x):
        parts = [float(p) for p in x.split(":")]
        v = 0.0
        for p in parts:
            v = v * 60 + p
        return v
    a, b = spec.split("-", 1)
    s, e = t(a), t(b)
    if e <= s:
        raise ValueError(f"keep range ends before it starts: {spec}")
    return s, e


def load_words(path):
    """Accepts transcribe.py output ({"words": [...]}) or a bare list of
    {start, end, word|text}. Also accepts whisper.cpp -oj -ml 1 output."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "transcription" in data:  # whisper.cpp
        out = []
        for seg in data["transcription"]:
            txt = seg.get("text", "").strip()
            if not txt:
                continue
            out.append({"start": seg["offsets"]["from"] / 1000.0,
                        "end": seg["offsets"]["to"] / 1000.0, "word": txt})
        return out
    if isinstance(data, dict):
        data = data.get("words", [])
    out = []
    for w in data:
        txt = (w.get("word") or w.get("text") or "").strip()
        if txt:
            out.append({"start": float(w["start"]), "end": float(w["end"]), "word": txt})
    return out


def remap(words, keeps):
    """Drop words outside the keep ranges and shift the rest onto the output timeline."""
    if not keeps:
        return words
    out, offset = [], 0.0
    for ks, ke in keeps:
        for w in words:
            mid = (w["start"] + w["end"]) / 2
            if ks <= mid < ke:
                s = max(w["start"], ks) - ks + offset
                e = min(w["end"], ke) - ks + offset
                out.append({"start": s, "end": max(e, s + 0.05), "word": w["word"]})
        offset += ke - ks
    return out


def censor(word):
    core = re.sub(r"[^a-z]", "", word.lower())
    for s in SWEARS:
        if core.startswith(s):
            letters = [c for c in word if c.isalpha()]
            if len(letters) <= 1:
                return word
            first = letters[0]
            return first + "*" * (len(letters) - 1) + word[len(word.rstrip("!?.,")):]
    return word


def chunk(words, max_words=3, max_chars=16, gap=0.4):
    chunks, cur = [], []
    for w in words:
        if cur:
            text_len = sum(len(x["word"]) + 1 for x in cur) + len(w["word"])
            prev = cur[-1]
            if (len(cur) >= max_words or text_len > max_chars
                    or w["start"] - prev["end"] > gap
                    or prev["word"].endswith((".", "!", "?", ","))):
                chunks.append(cur)
                cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    return chunks


def ts(t):
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def ass_color(hex_rgb, alpha=0):
    """'#RRGGBB' -> ASS &HAABBGGRR."""
    h = hex_rgb.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def esc(text):
    return text.replace("\\", "").replace("{", "(").replace("}", ")")


def clean(word, upper, do_censor):
    w = word.strip()
    if do_censor:
        w = censor(w)
    w = w.rstrip(",.;:")  # keep ? and ! — they carry the tone
    return esc(w.upper() if upper else w)


def build_ass(words, keeps=None, caption_y=1250, title=None, title_y=230, title_dur=None,
              credit=None, credit_y=70, duration=None, font="Montserrat Black",
              size=96, accent="#FF4FA3", upper=True, do_censor=False,
              max_words=3, title_size=70):
    words = remap(words, keeps or [])
    if duration is None:
        duration = sum(e - s for s, e in keeps) if keeps else (words[-1]["end"] + 1 if words else 10)
    white = ass_color("#FFFFFF")
    black = ass_color("#000000")
    acc = ass_color(accent)
    box = ass_color("#000000", alpha=0x40)

    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},{size},{white},{white},{black},{black},0,0,0,0,100,100,1,0,1,7,2,5,60,60,0,1
Style: Title,{font},{title_size},{white},{white},{box},{box},0,0,0,0,100,100,0,0,3,18,0,8,70,70,0,1
Style: Credit,{font},34,{ass_color('#FFFFFF', 0x50)},{white},{ass_color('#000000', 0x60)},{black},0,0,0,0,100,100,1,0,1,3,0,7,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    if title:
        t_end = duration if title_dur is None else min(duration, title_dur)
        pop = r"{\fad(0,150)\fscx85\fscy85\t(0,120,\fscx104\fscy104)\t(120,200,\fscx100\fscy100)}"
        txt = esc(title.upper() if upper else title)
        ev.append(f"Dialogue: 2,{ts(0)},{ts(t_end)},Title,,0,0,0,,{{\\pos({W//2},{title_y})}}{pop}{txt}")
    if credit:
        ev.append(f"Dialogue: 3,{ts(0)},{ts(duration)},Credit,,0,0,0,,{{\\pos(40,{credit_y})}}{esc(credit)}")

    chunks = chunk(words, max_words=max_words)
    for ci, ch in enumerate(chunks):
        c_start = ch[0]["start"]
        nxt = chunks[ci + 1][0]["start"] if ci + 1 < len(chunks) else duration
        c_end = min(max(ch[-1]["end"] + 0.25, c_start + 0.3), nxt, duration)
        toks = [clean(w["word"], upper, do_censor) for w in ch]
        for wi, w in enumerate(ch):
            s = c_start if wi == 0 else w["start"]
            e = ch[wi + 1]["start"] if wi + 1 < len(ch) else c_end
            if e - s < 0.02:
                continue
            parts = []
            for k, tok in enumerate(toks):
                parts.append(f"{{\\c{acc}}}{tok}{{\\c{white}}}" if k == wi else tok)
            pop = r"\fscx70\fscy70\t(0,90,\fscx108\fscy108)\t(90,150,\fscx100\fscy100)" if wi == 0 else ""
            ev.append(f"Dialogue: 1,{ts(s)},{ts(e)},Cap,,0,0,0,,{{\\pos({W//2},{caption_y}){pop}}}" + " ".join(parts))
    return head + "\n".join(ev) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("words")
    ap.add_argument("out")
    ap.add_argument("--keep", action="append", default=[], help="kept range in source seconds, repeatable")
    ap.add_argument("--caption-y", type=int, default=1250)
    ap.add_argument("--title")
    ap.add_argument("--title-y", type=int, default=230)
    ap.add_argument("--title-dur", type=float)
    ap.add_argument("--credit")
    ap.add_argument("--accent", default="#FF4FA3")
    ap.add_argument("--font", default="Montserrat Black")
    ap.add_argument("--size", type=int, default=96)
    ap.add_argument("--censor", action="store_true")
    ap.add_argument("--no-upper", action="store_true")
    a = ap.parse_args()
    keeps = [parse_keep(k) for k in a.keep]
    words = load_words(a.words)
    ass = build_ass(words, keeps, caption_y=a.caption_y, title=a.title, title_y=a.title_y,
                    title_dur=a.title_dur, credit=a.credit, font=a.font, size=a.size,
                    accent=a.accent, upper=not a.no_upper, do_censor=a.censor)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(ass)
    print(f"wrote {a.out}: {ass.count('Dialogue:')} events", file=sys.stderr)


if __name__ == "__main__":
    main()
