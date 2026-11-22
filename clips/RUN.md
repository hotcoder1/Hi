# Every-2-days clip run

What the user asked for (2026-11-19): **5 finished clips every 2 days, 1 from each active streamer, ready by 9 am Arizona time, sent straight to them (no storyboard).** Active streamers are `_roster.active` in `streamers.json`: Lacy, Jason The Ween, StableRonaldo ("Ron"), Kai Cenat, IShowSpeed. All five are cleared by the user. Don't clip anyone else unless the user adds them.

Skill: `gta6-streamer-clips/` (read `SKILL.md`, `references/gta6-moments.md`, and `references/memes.md` if memes are available). `SK=/home/user/Hi/gta6-streamer-clips`, run from `/home/user/Hi/clips`.

## Steps

1. **Setup** (fresh container): `pip install -q -U yt-dlp faster-whisper chat-downloader` if missing. The session's network must allow Twitch (`www.twitch.tv`, `gql.twitch.tv`, `usher.ttvnw.net`, `d1ndex63qxojbr.cloudfront.net`) and Hugging Face (`huggingface.co`, `us.aws.cdn.hf.co`); the "Hi – GTA 6 clipping" environment has them.
2. **Fetch**: `D=$(date -u +%F)`, then
   `python3 $SK/scripts/fetch_clips.py --streamers lacy,jasontheween,stableronaldo,kaicenat,ishowspeed --since <state.json last_run minus 2 h> --state state.json --top 15 --out vods/run-$D`
3. **Pick 1 per streamer** from `vods/run-$D/rows_<login>.png` (look at them) and the transcripts in `candidates.json`:
   - SKIP nudity and sexual content (showers, strip club, lap dances, "🔞" / "gyat" titles: in launch week these are the most-viewed clips and they get accounts banned), muted clips, slurs, story spoilers, other games, and clips that are just the streamer talking with no GTA on screen.
   - PREFER a clear funny or wild moment (see gta6-moments.md); views break ties.
   - If a streamer has nothing usable, skip them this run and say so; don't fill with a weak clip.
4. **Layout**: facecam and crop come from `streamers.json`. If a streamer's overlay moved (empty facecam panel in a still), measure it from `grid_<login>.png` and pass a per-clip `facecam`. Check with `render_batch.py ... --mode still` and look at the stills.
5. **Write `vods/run-$D/batch.json`**: per clip id, streamer, keep ranges (trim dead air; 10–35 s), title (3–8 words), post_caption (hook line + `🎥 @<login> on Twitch` + `#gta6 #gtavi #gta6clips #<login> #vicecity`). If `memes/library.json` and `sfx/library.json` exist, add 1–2 meme beats per clip (memes.md).
6. **Render + QA**: `python3 $SK/scripts/render_batch.py vods/run-$D/batch.json --clips vods/run-$D/clips --words vods/run-$D/words --streamers streamers.json --out out/run-$D`, then `qa_clip.py` on each and look at the contact sheets. Fix anything that fails (quiet clips: raise volume; wrong facecam: re-measure).
7. **Deliver**: `python3 $SK/scripts/package_batch.py vods/run-$D/batch.json --clips-dir out/run-$D --streamers streamers.json --name "GTA6 Clips $D" --dest /home/user/Hi/dist`, then SendUserFile the zip (status proactive) with a one-line summary per clip. If the zip is over ~400 MB, send the videos individually instead.
8. **Record**: add the 5 clip URLs to `state.json` `used_urls`, set `last_run`, append to `batches`; save the batch recipe (batch.json, candidates.json, words of the picks) to `batches/run-$D/`; commit and push the branch.
