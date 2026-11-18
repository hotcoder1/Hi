# Getting streams, clips and chat

Commands per platform. `URL` is the VOD/clip link. Run these from the project folder. Add `--cookies-from-browser chrome` (or firefox/safari) when a site wants a login, for sub-only VODs or age gates. Add `-N 8` to speed up HLS downloads.

## Contents
- Twitch: list VODs, info + chapters, audio, chat, sections, clips, live
- Kick
- YouTube
- Local files
- Section timing

## Twitch

List recent past broadcasts (pick the GTA VI ones by title, or check the chapters):
```
yt-dlp --flat-playlist --print "%(id)s | %(upload_date)s | %(duration_string)s | %(title)s" \
  "https://www.twitch.tv/<name>/videos?filter=archives&sort=time"
```
Info + game chapters (variety streams switch games, so use the GTA VI chapter as `--range`):
```
yt-dlp -J "https://www.twitch.tv/videos/<id>" > vods/<name>/<id>/info.json
python3 -c "import json;[print(int(c['start_time']),int(c['end_time']),c.get('title')) for c in json.load(open('vods/<name>/<id>/info.json')).get('chapters') or []]"
```
If there are no chapters, ask the user roughly when GTA VI started, or rank the whole VOD.

Audio only (small, fast; this is all the ranker needs):
```
yt-dlp -f "Audio_Only/bestaudio/worst" -o "vods/<name>/<id>/audio.%(ext)s" "https://www.twitch.tv/videos/<id>"
```
Chat replay (either one):
```
chat_downloader "https://www.twitch.tv/videos/<id>" --output vods/<name>/<id>/chat.json
TwitchDownloaderCLI chatdownload --id <id> -o vods/<name>/<id>/chat.json
```
A video section around a candidate (VOD times, with ~20 s padding):
```
yt-dlp -f "bv*[height<=1080]+ba/b[height<=1080]" --merge-output-format mp4 \
  --download-sections "*2:13:35-2:15:10" -o "vods/<name>/<id>/sections/c03.%(ext)s" "https://www.twitch.tv/videos/<id>"
```
Twitch clips the viewers already made: the best moments, pre-picked, already ≤60 s and 1080p. List the top ones from the last 7 days (`range=24hr|7d|30d|all`):
```
yt-dlp --flat-playlist --print "%(url)s | %(duration)s s | %(title)s" \
  "https://www.twitch.tv/<name>/clips?filter=clips&range=7d"
yt-dlp -o "vods/<name>/clips/%(id)s.%(ext)s" "<clip url>"
```
A clip can go straight to Phase 1 step 3 (transcribe → trim → title). The ranker isn't needed.

Recording a live stream (from now on; Twitch can't seek back before you joined):
```
yt-dlp -o "vods/<name>/live_%(epoch)s.%(ext)s" "https://www.twitch.tv/<name>"
```
Stop it with Ctrl-C. The file is playable. Then run `find_moments.py` on the recording (no chat replay; record the chat live with `chat_downloader https://www.twitch.tv/<name> --output live_chat.json` in parallel if you want it).

## Kick

yt-dlp handles Kick VODs, clips and live streams, but Kick sits behind Cloudflare, so install impersonation support: `pip install -U "yt-dlp[default,curl-cffi]"`, and add `--impersonate chrome` if you get 403s.
```
yt-dlp -J "https://kick.com/<name>/videos/<uuid>" > info.json
yt-dlp -f "bestaudio/worst" -o "audio.%(ext)s" "https://kick.com/<name>/videos/<uuid>"
yt-dlp --download-sections "*1:02:00-1:03:30" -o "sections/c01.%(ext)s" "https://kick.com/<name>/videos/<uuid>"
yt-dlp -o "clips/%(id)s.%(ext)s" "https://kick.com/<name>/clips/<clip_id>"
```
There's no dependable Kick chat-replay tool, so rank on audio only and lean harder on the transcript check. Get VOD links from the channel's Videos tab (yt-dlp can't list a Kick channel's VODs reliably).

## YouTube

```
yt-dlp --flat-playlist --print "%(id)s | %(title)s" "https://www.youtube.com/@<handle>/streams"
yt-dlp -J "https://www.youtube.com/watch?v=<id>" > info.json        # has chapters if the streamer added them
yt-dlp -f ba -o "audio.%(ext)s" "https://www.youtube.com/watch?v=<id>"
yt-dlp --skip-download --write-subs --sub-langs live_chat -o "chat" "https://www.youtube.com/watch?v=<id>"   # -> chat.live_chat.json
yt-dlp -f "bv*[height<=1080]+ba/b" --merge-output-format mp4 --download-sections "*45:10-46:40" -o "sections/c02.%(ext)s" "<url>"
```
`find_moments.py --chat chat.live_chat.json` reads YouTube's format directly. Ongoing streams: `--live-from-start` records from the beginning while still live.

## Local files

If the user has the VOD or a recording, skip downloads: `find_moments.py <file.mp4>` reads the audio straight from the video file. Cut sections with `ffmpeg -ss <start> -to <end> -i vod.mp4 -c copy sections/c01.mp4` (the copy starts at the nearest keyframe, which is fine because everything after this point uses the section file's own times).

## Section timing

Everything after the section download (transcripts, `--keep` ranges, captions) uses the **section file's own seconds**, so it doesn't matter if yt-dlp or ffmpeg started the section a second or two early at a keyframe. Store the section's requested VOD start in `plan.json` (`"section_start"`) so you can still quote the VOD timestamp (`vod_time`) to the user.
