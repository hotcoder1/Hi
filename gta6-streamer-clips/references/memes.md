# Meme beats: cutaways, zoom punch + boom

Read this before adding memes to a clip. The user's choices (2026-11-18): memes come from **their own meme folder**, sounds from **their own SFX folder**; the moves are a **full-screen meme cutaway** and a **zoom punch + boom**; **1–2 meme beats per clip, on the funniest beat**. The streamer's moment stays the star; the meme is the punchline's exclamation mark, not the joke.

## Contents
- The library (getting it, indexing it)
- Where a meme beat goes
- Picking the meme and the sound
- Render flags
- Storyboard and QA
- Rules

## The library

The meme and SFX folders live on the user's computer (if their `fortnite-video-edit` skill is installed, its sections 7–8 describe both folders, what the files mean and which ones are banned; use that). Get them into the project once:
- On the user's computer, or with their folder connected over Remote Control: copy only what's needed into `memes/` and `sfx/` in the project folder.
- In a cloud session with no computer: ask them to connect the folders (Claude desktop app → Settings → Claude Code → Remote Control) or upload a zip of each. Say plainly that meme beats wait until then; don't invent or download substitute memes.

Index each folder once, and again when the user adds files:
```
python3 $SK/scripts/index_library.py memes memes/library.json --kind meme
python3 $SK/scripts/index_library.py sfx sfx/library.json --kind sfx
```
It records type, duration, audio, loudness and leading silence, and guesses a mood from each name (shock, confused, laugh, roast, fail, hype, cringe, sus, sad, awkward, flex, boom, whoosh, pop). Unnamed images ("images (23).jpg") come out as `unknown` on a numbered contact sheet: look at it and fill in their mood and a one-line `note` ("bald man palm on head: disappointment"). Mark banned files `"never": true` (copyrighted songs, anything the user ruled out). Re-running keeps what you filled in.

## Where a meme beat goes

1. Find the punchline in the transcript: the word or moment the clip exists for ("…in my ass!", the car flipping, "I'm at 12 FPS").
2. **Zoom punch + boom on the punchline**: `--punch T` and a boom-type SFX at the same `T` (vine boom first; rotate others).
3. **Meme cutaway right after it**: start 0.2–0.5 s after the punchline word ends (or after the crash lands), for 0.8–1.8 s. Never cover the payoff itself: the viewer must see the crash or hear the line first.
4. A second beat only if the clip has a second, different laugh (a repeat of the joke, a reaction to the reaction). Never two within 5 s, and never in the first 2 s (the hook is the stream, not a meme).
5. Leave clips with no real punchline alone (scenery, hype speeches, countdowns): a zoom punch at most.

Times are **output seconds** (after `--keep` cuts), the same timeline as `--punch`.

## Picking the meme and the sound

Match the meme's mood to what the viewer should feel at that beat, not to the words:
| Beat | Meme mood | Sound |
|---|---|---|
| Streamer or NPC says something absurd | confused, sus | huh / what / record scratch |
| Streamer fails, crashes, dies | fail, laugh | bruh / oof / sad trombone |
| Someone gets roasted (incl. the streamer by an NPC) | roast, laugh | laugh / "he lying" |
| Shocking twist, jaw-drop visual | shock | boom / gasp / "oh my god" |
| Clutch play, huge win | hype, flex | "let's go" / sheesh |
| Flirty or weird NPC | sus, cringe | huh / side-eye |
| Silence after a bad joke | awkward | crickets |

- Use the meme's own audio when it's a video meme with a voice line; otherwise the SFX carries it.
- Rotate: a meme at most twice per batch, a voice-line SFX at most 3 times per batch (whooshes and booms are exempt). Bump `uses` in the library index as you go.
- Optional meme caption, 2–5 words, caps, roasting the moment from the viewer's side ("BRO SAID WHERE?!", "HE WAS NOT READY"). Never repeat the transcript, never punch down at the streamer harder than they would.

## Render flags

```
render_clip.py ... --punch 4.6 --sfx "4.6|sfx/vine-boom.mp3|0.9" \
    --meme "5.0|memes/bruh-no.gif|1.3|BRO SAID WHERE?!"
```
- `--meme "T|file|dur|CAPTION|vol"`: full-screen cutaway (image, GIF or short video) over a blurred, darkened fill of itself, with the caption near the bottom. The stream keeps running underneath at `--meme-duck` volume (default 0.35); stream captions step aside while it's up; the title ends early if a meme starts during it.
- `--sfx "T|file|vol"`: leading silence is trimmed automatically, so the hit lands on `T`. Start from vol 0.9 for booms and voice lines and 0.5 for whooshes and pops; if the index says `mean_db` above −12, start at 0.6.
- Animated WebP doesn't decode in ffmpeg: convert it to GIF first (Pillow) or use a still.

## Storyboard and QA

- Put the plan on the card's ON SCREEN line: `4.6 zoom + vine-boom · 5.0–6.3 meme bruh-no.gif "BRO SAID WHERE?!"`, so the user can Keep / Change / Drop the meme separately from the clip ("keep the clip, different meme").
- After rendering, grab a frame inside each meme window and one 0.3 s after it ends: the meme fills the frame, the caption is readable, and the stream picks up cleanly. Check the per-second loudness around each beat: the boom is audible, nothing clips (qa_clip.py true peak ≤ −1 dBTP).

## Rules

- Memes stay short (≤2 s) and are used as reactions, never as long stretches of someone else's content. Skip meme clips with copyrighted songs, and every file marked `never`.
- No memes that mock someone's race, religion, gender, sexuality or disability, even as a joke on an NPC.
- No new memes from the internet without the user's OK: the library is theirs and they've cleared it.
