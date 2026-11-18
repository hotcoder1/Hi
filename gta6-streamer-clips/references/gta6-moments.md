# What makes a GTA 6 streamer clip work

Use this when checking candidates (is it really a moment?), picking in/out points and writing titles.

## Moment types, roughly from most to least reliably viral

1. **Chaos that escalates.** The wanted level climbs, a chase spirals, and it ends in something spectacular: a crash, a boat flip, a helicopter, an arrest one second from escape. The clip needs the start of the escalation and the ending.
2. **Physics and ragdoll fails.** Bailing out of a car at 100 mph, falling off something, a jet ski hitting a dock, an NPC getting launched. Short and loopable, 10–20 s.
3. **NPCs being too real.** A pedestrian's reaction, "Florida man" energy, cops reacting to something dumb, in-game social media moments. The streamer's disbelief is the payoff.
4. **First reactions (launch weeks).** The first look at Vice City, the map size, graphics, the water and weather, a new mechanic. Works while the game is new; the face matters more than the game here, so use `stack`.
5. **Bugs and glitches.** Launch-period bugs spread fast. Title it honestly ("THIS GTA 6 BUG IS INSANE"), and don't pass off a mod or an edit as the real game.
6. **Streamer meltdowns.** Dying at the end of a long mission, losing money, a failed heist. Needs the 3–5 s of context that shows the stakes.
7. **Clutch skill.** An impossible escape, a perfect shot, threading traffic. Pair it with the reaction.
8. **Chat interplay and bits.** The streamer reading chat, running a joke. Only if it lands without the stream's context.
9. **Story moments.** Big twists are spoilers: mark `"spoiler": true`, keep "GTA 6 SPOILER" at the front of the post caption, and don't put the twist in the title or the first frame.

Not worth clipping: loading screens, menus and long drives with talk, unless the talk itself is the clip; donation and alert sounds; ads; music breaks; anything that needs 30+ s of setup.

## Signs in the transcript and frames

- Transcript: "no no no", "bro", "chat", "what", "oh my god", "let's go", "how", repeated words, a scream, `(laughing)` / `[LAUGHTER]` / "hahaha", a sudden quiet after shouting.
- Frames: the wanted stars HUD, a crash or explosion, the camera flipping, the "wasted"/"busted" screen, the facecam leaning in or out of frame, hands on head.
- Chat sample from `find_moments.py`: what people typed is usually the best one-line summary of what happened, and often the title.

## In and out points

- **In**: 2–4 s before the trigger, at the start of the setup line ("chat, watch this"), not mid-word. The first second should already show motion or a face mid-reaction, never a still menu.
- **Out**: 1–3 s after the reaction peaks. Cut the "anyway, so..." aftermath. Ending just as they start to laugh again often loops well.
- **Middle**: cut long drives and silence between setup and payoff with extra `--keep` ranges; one or two cuts is normal, but never cut inside the payoff itself.
- **Length**: 15–45 s is the sweet spot. Over 60 s only if the story really needs it.

## Titles

3–8 words, caps, what happens or a tease the clip pays off. Use the streamer's name in the post caption rather than the title, unless the name is the draw.
- "HE GOT 5 STARS IN 10 SECONDS"
- "VICE CITY COPS ARE BUILT DIFFERENT"
- "GTA 6 NPCS ARE TOO REAL"
- "HE WAS ONE SECOND AWAY"
- "THIS GTA 6 BUG IS INSANE"
- "HE'S BEEN TRYING THIS FOR 2 HOURS"
- "FIRST TIME SEEING VICE CITY"

Avoid titles the clip doesn't pay off, all-emoji titles, and anything that mocks the streamer harder than the streamer would.

## Post caption + hashtags

One line of hook (it may use emoji), then the credit, then 4–6 hashtags:
```
he really thought he could outrun them 💀
🎥 @<handle> on Twitch
#gta6 #gtavi #gta6clips #<streamer> #vicecity
```
Rotate #gtavi / #grandtheftauto6 / #gta6funny / #gta6moments / #rockstargames. For spoilers, start with "⚠️ GTA 6 SPOILER".

## Whisper vocabulary

`transcribe.py` already passes a hint prompt with the game's names (GTA 6, Vice City, Leonida, Lucia, Jason, wanted level). Add the streamer's name and recurring words with `--prompt` so they're spelled right in the captions. Still read the transcript and fix misheard names before rendering.
