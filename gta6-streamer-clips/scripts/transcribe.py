#!/usr/bin/env python3
"""Transcribe a clip section with word timestamps -> words.json.

  transcribe.py sections/c03.mp4 words/c03.json [--model small] [--lang en]

Uses faster-whisper (pip install faster-whisper). The model downloads once on
first use. Output:
  {"language": "en", "text": "...",
   "segments": [{"start", "end", "text"}],
   "words": [{"start", "end", "word"}]}
Times are in the input file's own seconds.

whisper.cpp also works: `whisper-cli -m models/ggml-small.bin -f audio.wav -oj -ml 1 -sow`
gives a JSON that captions.py / render_clip.py --words read directly.
"""
import argparse
import json
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("media")
    ap.add_argument("out")
    ap.add_argument("--model", default="small", help="tiny/base/small/medium/large-v3 (small is a good default)")
    ap.add_argument("--lang", help="force a language code, e.g. en, es, pt, de (default: auto-detect)")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--prompt", default="GTA 6, GTA VI, Vice City, Leonida, Lucia, Jason, wanted level, five stars",
                    help="vocabulary hint so game names are spelled right")
    a = ap.parse_args()
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("faster-whisper is not installed: pip install faster-whisper")

    compute = "int8"
    model = WhisperModel(a.model, device=a.device, compute_type=compute)
    segs, info = model.transcribe(a.media, language=a.lang, word_timestamps=True, vad_filter=True,
                                  initial_prompt=a.prompt, condition_on_previous_text=False)
    out = {"language": info.language, "segments": [], "words": []}
    texts = []
    for s in segs:
        out["segments"].append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()})
        texts.append(s.text.strip())
        for w in s.words or []:
            out["words"].append({"start": round(w.start, 3), "end": round(w.end, 3), "word": w.word.strip()})
    out["text"] = " ".join(texts)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"wrote {a.out}: {len(out['words'])} words, language {info.language}", file=sys.stderr)


if __name__ == "__main__":
    main()
