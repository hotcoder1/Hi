---
name: gta6-streamer-clips
description: "Clip GTA 6 (Grand Theft Auto VI / GTA VI) moments from streamers' Twitch, Kick or YouTube streams into vertical 9:16 Shorts, TikToks and Reels. It finds the best moments from loudness and chat spikes, stacks the facecam over the gameplay, burns in word-by-word captions, credits the streamer, shows a Keep/Change/Drop storyboard, then renders and checks each clip. Use it whenever the user wants GTA 6 clips or highlights, runs or starts a clip channel, says 'clip [streamer] playing GTA 6', pastes a Twitch/Kick/YouTube VOD or stream link and says 'clip this' or 'find the funny parts', or wants a GTA 6 stream turned into shorts, even if they never say 'skill' or 'vertical'. It also works for other games' streams."
---

# GTA 6 streamer clips

Claude works as the user's clipper. It takes a streamer's GTA VI stream (a VOD link, a live stream, Twitch clips, or a file), finds the moments worth posting, and delivers ready-to-post 1080×1920 clips with captions and credit. It uses the same tools and approval gates as the user's `talking-head-video-editor` workflow (yt-dlp, FFmpeg, Whisper, plus a Keep/Change/Drop storyboard before the final render), applied to someone else's stream. For the user's own gameplay, use `fortnite-video-edit` or `recording-to-promo-video` instead.

All scripts are in `scripts/` next to this file. Set `SK=<this skill's folder>` once and call them as `python3 $SK/scripts/<name>.py`. Each script prints `--help`.

## Rights come first (30 seconds, every new streamer)

Clip channels live or die on streamers being OK with them. Before clipping a new streamer, ask the user how they're allowed to clip them, and write the answer in `streamers.json` (`"permission": "..."`). Acceptable answers: the streamer runs a clipping program or Discord clipper role, publicly says clipping is fine, gave the user permission, or it's the user's own channel. If the answer is "no idea", say plainly that the clips could be claimed or struck and that the streamer can ask for them to be taken down, then let the user decide. Always:
- put the streamer's handle on screen (`--credit "twitch.tv/name"`) and in the post caption;
- keep clips short (under 60 s) and edited (cuts, captions, title), never re-upload long stretches of a VOD;
- skip moments where copyrighted music is loud (the streamer's own music or **GTA radio stations**: licensed songs get Content ID claims on YouTube and muted audio on TikTok). If the transcript reads like lyrics, flag it;
- don't clip anything outside the stream (DMs, doxxing, someone's address on screen) or "leaked" footage.

## The workflow: 4 phases, 2 approval gates

0. **Setup** (once): install and test the tools.
1. **Find**: get the stream, rank moments by loudness and chat, then check the top ones by transcript and frames.
2. **Storyboard**: a low-res preview per clip with Keep / Change / Drop. **Gate: no final renders until the user has gone through it.**
3. **Render + QA**: apply every note, render 1080×1920, run the checks, look at the frames.
4. **Deliver**: clips in `out/` plus a ready-to-post caption for each one.

Fast mode: if the user says "just send me the clips", or this is the 2nd+ batch of a streamer whose layout and style are already approved, skip the storyboard and go straight to render + QA. Still show the list of picks with timestamps.

## Where to work

- **Best: the user's computer** (a linked device shell such as `mcp__remote-devices__device_bash`, or a local Claude Code session) in one project folder, e.g. `GTA6 Clips/`. Twitch, Kick and YouTube downloads work there, and they can watch the previews.
- **Cloud sandbox**: these sites are often blocked by the network policy (yt-dlp fails with 403 / "tunnel"). Say so plainly, then either ask the user to upload the VOD section or Twitch clip files, or get the hosts allowed (environment tools if you have them, else `read_documentation` → environment.network). Hosts that are known to work: Twitch `www.twitch.tv`, `gql.twitch.tv`, `usher.ttvnw.net`, clip files `d1ndex63qxojbr.cloudfront.net`; Whisper models `huggingface.co` + `us.aws.cdn.hf.co` (`transcribe.py` turns off Hugging Face's Xet transfer so this one CDN host is enough). VOD and live video segments come from other CDN hosts that vary, so when a download fails, add exactly the host named in the proxy error, not a guess. Never pretend a download or a transcription ran.

## Project folder

```
GTA6 Clips/
  streamers.json            per streamer: platform, url, handle, permission, facecam box, layout, notes
  clip-style.md             optional style rulebook (see "Style")
  vods/<streamer>/<vod_id>/ info.json, audio.*, chat.json, candidates.json
      sections/<cid>.mp4    the video around each candidate (with padding)
      words/<cid>.json      transcript with word times
  memes/, sfx/              the user's meme and sound libraries + library.json indexes (references/memes.md)
  previews/                 low-res storyboard clips + poster frames
  plan.json, storyboard.html
  out/                      final clips + <clip>.txt post captions + qa/ contact sheets
```

## Phase 0 — Tools

| Tool | Job | Install | Test |
|---|---|---|---|
| FFmpeg (with libass) | cutting, layout, captions, loudness, QA | brew / apt / winget | `ffmpeg -hide_banner -filters \| grep " ass "` |
| yt-dlp | VOD / clip / live download, chapters, partial downloads | `pip install -U yt-dlp` | `yt-dlp --version` |
| faster-whisper | word-timed transcripts for captions and picking moments | `pip install faster-whisper` | `python3 $SK/scripts/transcribe.py <short.mp4> /tmp/w.json --model tiny` |
| chat-downloader | Twitch / YouTube chat replay for spike detection | `pip install chat-downloader` | `chat_downloader --help` |
| TwitchDownloaderCLI (optional) | the most reliable Twitch chat download | release binary from lay295/TwitchDownloader | `TwitchDownloaderCLI --help` |

whisper.cpp works instead of faster-whisper (`-oj -ml 1 -sow` output is read directly). Remotion is optional: use it only if the user wants animated graphics beyond captions, titles and zoom punches. The `talking-head-video-editor` skill has the setup. Report one pass/fail line per tool, then "Ready."

## Phase 1 — Find the moments

Exact commands for each platform are in `references/sources.md`. Read it when you start fetching.

1. **Get the inputs.** Many big streamers make their Twitch VODs **subscriber-only** (yt-dlp: "You must be logged into an account that has access to this subscriber-only content"). Then use, in order: public Twitch clips (viewers clip the best moments within minutes; download them and go straight to step 3), recording the live stream while it's on (live is public), the clipping program's own VOD links, or `--cookies-from-browser` from a subscribed account on the user's computer. Never ask for cookies or tokens in chat. For a VOD link: `info.json` (title, chapters, duration), **audio only** (an 8-hour VOD is about 250 MB of audio instead of 10+ GB of video), and the chat replay. For a variety stream, use the "Grand Theft Auto VI" chapter as `--range`. If the user only names a streamer, list their recent VODs, pick the GTA VI ones and confirm which. Twitch's own top clips (by views) are a strong second signal: viewers already clipped the best parts.
2. **Rank:** `python3 $SK/scripts/find_moments.py audio.m4a --chat chat.json --range <gta chapter> --top 15 --out candidates.json`. It prints each candidate's VOD time, score, and what chat was saying ("5 STARS 💀 x27 | CLIP IT x26"). Chat lags the stream by ~5–15 s; the script shifts it back by 8 s (`--chat-lag`). Without chat it ranks on audio alone, which is fine but noisier (music and loud intros also spike).
3. **Check the top 8–10** (more if the user wants a batch):
   - download the video section `start-20 s → end+20 s` at 1080p (sections keep this fast);
   - `transcribe.py sections/<cid>.mp4 words/<cid>.json` and read the text;
   - make a contact sheet (`ffmpeg -i sec.mp4 -vf "fps=1,scale=320:-1,tile=6x5" sheet.png`) and look at it.
   Decide: is something actually happening (see `references/gta6-moments.md` for what works), or was it just a loud ad, a music break or a donation sound? Drop the fakes.
4. **Trim.** Pick the in-point (the start of the setup, not the start of the yelling: viewers need 2–4 s of "what's going on") and the out-point (right after the reaction peaks, not 20 s of aftermath). Cut dead air in the middle with several `--keep` ranges. Aim for 15–45 s. All times from here on are in the **section file's** seconds.
5. **Meme beats** (when the user wants memes): for each clip with a real punchline, plan a zoom punch + boom on it and a full-screen meme cutaway right after it, 1–2 beats per clip, picked from the user's indexed library by mood. Read `references/memes.md` first; it has the placement rules, the mood → meme/sound table and the flags. No library yet → say so and ask for it; don't invent memes.
6. **Title** each clip: 3–8 words, caps, says what happens or teases it ("HE GOT 5 STARS IN 10 SECONDS", "THE COPS HAD NO CHANCE"). No clickbait that the clip doesn't deliver. Mark story spoilers (`"spoiler": true`) and put "GTA 6 SPOILER" in the post caption.

### Facecam layout (once per streamer)

Overlays don't change between streams, so find the box once and save it in `streamers.json`. If the streamer burns their own captions into the stream, set `--game` to stop above them (e.g. `0,0,1,0.88`) so the clip doesn't show two sets.
- Grab a frame with a grid: `ffmpeg -ss 30 -i sec.mp4 -frames:v 1 -vf "drawgrid=w=iw/20:h=ih/20:t=1:c=white@0.4" grid.png`, look at it, and note the facecam box as fractions `x,y,w,h` (e.g. `0.02,0.70,0.22,0.27`). Fractions work at any resolution.
- Pick the layout:
  - `stack` (default when there's a facecam): facecam on top, gameplay below, captions on the seam. Best for reactions.
  - `fit`: the whole 16:9 frame over a blurred fill. Use it when the action is spread out (wide chases, map, phone screens, HUD text that matters) or there's no facecam. `--fit-zoom 1.1–1.3` makes the gameplay bigger by trimming the sides, so check a corner facecam isn't cut in half.
  - `full`: a tight 9:16 crop of the gameplay, with `--pip` for a small facecam. Use it for centred action like a character close-up or a cutscene. Also use it when the source is already vertical (Twitch now makes 9:16 clips, and IRL streams are often shot on a phone); it then just scales the frame up to 1080×1920.
- Check with a still before any video: `render_clip.py sec.mp4 check.png --keep a-b --layout stack --facecam ... --still 3`. Look at it. Adjust `--shift` (move the gameplay crop left/right, -1..1), `--cam-h`, or the box.

## Phase 2 — Storyboard (gate)

1. For each kept candidate, render a preview: `render_clip.py sections/<cid>.mp4 previews/<cid>.mp4 --keep ... --layout ... --facecam ... --words words/<cid>.json --title "..." --credit "twitch.tv/<name>" --preview`. Then grab a poster frame at the payoff: `ffmpeg -ss <t> -i previews/<cid>.mp4 -frames:v 1 -q:v 4 previews/<cid>.jpg`.
2. Write `plan.json` (the format is in `scripts/storyboard.py --help`): id, title, vod_time, keep ranges, duration, quote, why (what chat or audio said), layout, on_screen (including the meme plan: times, files, captions), post_caption, preview, poster, spoiler.
3. `storyboard.py plan.json storyboard.html`. On the user's computer, open it. Otherwise publish it as a claude.ai Artifact: build with `--artifact`, publish with `capabilities: {"db": {}}`, and pass the preview MP4s and posters in the Artifact `files` map under the same `previews/...` paths, so the videos play on the page. With `db`, every tap and note saves to the artifact's database as `choices/<clip id>`, and you read them back with the ArtifactData tool (`list` on `choices`). That's much easier on a phone than copying JSON.
4. **Stop.** Ask the user to Keep / Change / Drop each clip, then read the `choices` collection (or the pasted notes). Don't render finals before that.

## Phase 3 — Render + QA

1. Apply every note, and list each one with what you changed. If a note is unclear ("make it funnier"), ask.
2. Final: `render_clip.py sections/<cid>.mp4 out/<streamer>_<slug>.mp4 --keep ... --layout ... --facecam ... --words words/<cid>.json --title "..." --credit "twitch.tv/<name>" [--punch <t>] [--censor]`.
   - `--punch <t>`: a quick 1.15× zoom at the payoff second (output time). Use 1–2 per clip at most: on the crash, the explosion, or the reaction.
   - `--meme "T|file|dur|CAPTION"` and `--sfx "T|file|vol"`: the meme beats from the plan (see `references/memes.md`). Check a frame inside every meme window.
   - `--censor` stars out slurs and the hardest swears in the captions (the audio stays). Use it by default for TikTok unless the user's style says otherwise.
   - Audio is normalised to −14 LUFS. Captions are the bundled Montserrat Black, uppercase, with the current word in pink (`--accent`).
3. QA: `qa_clip.py out/<clip>.mp4 --sheet out/qa/<clip>.png`. It checks format, length, loudness, black and frozen frames. Then **look at the contact sheet**: captions readable and spelled right, nothing over the face or the key action, credit visible, title not cut off. Fix and re-render on any FAIL or anything that looks wrong.

## Phase 4 — Deliver

For each clip, write `out/<clip>.txt` with a ready-to-post caption:
```
bro lasted 10 seconds in Vice City 💀
🎥 @<handle> on Twitch
#gta6 #gtavi #gta6clips #<streamer> #vicecity
```
Hashtags: 4–6, with #gta6 first. Then report the clip list (file, length, VOD time, title), what was dropped and why, and anything that needs the user (missing permission, music risk). Send the files (SendUserFile) if the user isn't at the computer.

## Style

Default (until the user has their own): `stack` layout; a black 6 px seam; captions 1–3 words, Montserrat Black, white with a black outline, current word pink `#FF4FA3`, on the seam; a title box just under the seam (over the gameplay, clear of the face) for the first 3.5 s; long titles wrap to two lines; the credit small at the top-left; a zoom punch on the payoff (with a boom when the clip has meme beats); 1–2 full-screen meme cutaways on the funniest beat when the user's meme library is available; no music bed (the stream's audio is the content); no emoji in burned-in text (they render as boxes), only in post captions. Keep captions out of the bottom ~20% and the right edge, where the TikTok/Shorts buttons sit.

To match a clip channel the user likes: download 3 of its clips (yt-dlp), make contact sheets, and write `clip-style.md` covering layout, caption font/size/colour/position, title style, cut pace, zooms, SFX and length. Then map it onto the script flags (`--accent`, `--caption-size`, `--caption-y`, `--title-dur`, layout). Get approval, then follow it every time. Avoid AI-slop moves: no Ken Burns on gameplay, no shaky-cam, no gradient glow text, no stock footage.

## Recurring batches

When the user wants clips on a schedule (e.g. "1 clip from each streamer every 2 days"), keep the roster and the schedule in `streamers.json` (`_roster`), what has been used in `state.json`, and the step-by-step run in the project's `RUN.md`; a scheduled task then just says "do the run in RUN.md". The batch scripts:
- `fetch_clips.py --streamers a,b,c --since <last run> --state state.json --top 10 --out vods/run-<date>`: lists each streamer's newest Twitch clips, skips used ones, downloads, flags muted audio, transcribes (one Whisper model for the batch) and makes frame strips + facecam grids.
- `render_batch.py batch.json --clips ... --words ... --streamers streamers.json --out ... --mode still|preview|final`: renders every clip with the streamer's saved layout; per-clip overrides for facecam, crop, memes and SFX.
- `package_batch.py batch.json --clips-dir ... --name "GTA6 Clips <date>" --dest ...`: a folder per streamer with each video's post caption beside it, plus POST_CAPTIONS.md, zipped for one download.
Look at the strips before picking: titles and view counts alone pick nudity and muted clips.

## Gotchas

- **Chat lag**: the chat spike comes *after* the moment. That's why candidates start 30 s before the peak (`--pre`).
- **Loud ≠ funny**: alerts, donation TTS, intro music and ads spike the audio. The transcript and frames decide.
- **Context**: if the clip needs a backstory, put it in the title ("HE'S BEEN TRYING THIS FOR 2 HOURS"), not in a long intro.
- **60 fps** streams stay 60 fps (the default follows the source, up to 60).
- **Other languages**: Whisper auto-detects the language. Keep the captions in the streamer's language unless the user wants a translation (then translate the words.json text and keep the timings).
- **Live streams**: you can't rank a stream that hasn't ended. Either record it with yt-dlp while it's live and run the ranker on the recording, or wait for the VOD.
- **Batches**: process candidates one at a time, from section download through preview, so one bad download doesn't block the rest. Keep everything under `vods/` so a re-render never needs a re-download.
