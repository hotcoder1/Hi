# Live GTA 6 streamers, batch 1 (2026-11-18)

21 clips (3 each from xQc, Lacy, Jason The Ween, Kai Cenat, Agent00, NICKMERCS, Tfue), from viewer-made
Twitch clips of their live early-access streams. TimTheTatman was skipped (only camera-talk clips so far).
Storyboard: https://claude.ai/artifact/UG97yMDWZ3ZR4PivNQcxTN (choices in its `choices` collection).

- `candidates.json`: all 44 candidates with clip URLs, views and times; `specs.json`: the 21 picks with cuts, titles, punches
  and per-clip facecam/crop overrides; `layouts.json`: default facecam/crop per streamer; `words/`: transcripts.
- Rebuild: download each pick's URL to `../../vods/multi-2026-11-18/clips/<id>.mp4`, copy this folder's files there,
  then `python3 render_multi.py --preview` (or `--final` for clips/out/).
