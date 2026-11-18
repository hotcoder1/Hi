# TypicalGamer, GTA 6 batch 1 (2026-11-18)

8 clips from viewer-made Twitch clips of his live GTA 6 early-access marathon.
Storyboard: https://claude.ai/artifact/HRmWLjUpqcGo18PknTMcMd (choices in its `choices` collection).

Rebuild in a fresh container:
1. `pip install -q -U yt-dlp faster-whisper chat-downloader`
2. Download each clip from `clip_urls.json` to `../../vods/typicalgamer/2026-11-18-gta6/clips/<slug>.mp4`
3. Copy `words/`, `specs.json`, `render_previews.sh` into that folder (`words/` has the corrected transcripts)
4. From that folder: `./render_previews.sh` for previews, or `./render_previews.sh --final` for finals in `clips/out/`
