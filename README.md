# GTA 6 streamer clips — a Claude skill

`gta6-streamer-clips/` is a Claude skill that turns a streamer's GTA VI stream (Twitch, Kick, YouTube VOD, Twitch clips, or a local recording) into vertical 1080×1920 Shorts/TikToks/Reels:

1. **Find**: rank moments by loudness and chat spikes (`scripts/find_moments.py`), then check the top ones by transcript and frames.
2. **Storyboard**: a low-res preview per clip with Keep / Change / Drop (`scripts/storyboard.py`).
3. **Render + QA**: facecam stacked over the gameplay, word-by-word captions, title, streamer credit, zoom punch, −14 LUFS (`scripts/render_clip.py`, `scripts/qa_clip.py`).
4. **Deliver**: clips + ready-to-post captions.

Tools: FFmpeg (with libass), yt-dlp, faster-whisper (or whisper.cpp), chat-downloader. See `gta6-streamer-clips/SKILL.md`.

Test cases for `claude plugin eval` are in `gta6-streamer-clips/evals/` (run from the skill folder: `claude plugin eval . --allow-tools Write,Edit,Bash --scaffold`).

Font: Montserrat Black, SIL Open Font License (`assets/fonts/OFL.txt`).
