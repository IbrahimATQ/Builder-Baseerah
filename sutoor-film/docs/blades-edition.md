# «النِصالُ عَلى النِصالِ», the Blades edition (2160×3840, 24 fps, 31 s)

## What was asked
- "Still not the cinematic journey that I was hoping for, and the burning scenes is not good … They look purely AI generated, purely fake."
- "The voice also looks isolated. I'm thinking about getting the voice back without isolating the music, perhaps using the same music that has been already in the previous video."
- "I think the whole journey needs to be replanned and rebuilt for it to be a very cinematic way, like someone who has created it has a very good cinematic editing, montage, effects, great ones."
- Earlier, still standing: "It just like a video with a text in front of it … make it related, make it sensible."

## What this edition does differently
1. **The original soundtrack is back, untouched.** The film runs on the reel's own mix (the reciter's voice in the music it was mixed with), at its own pace. Film time is recording time: 31.0 s. No separation, no stretching, no re-scoring. Recorded effects under it are a separate pass (`data/blades/sfx_cues.json`, when present).
2. **No simulated burning paper.** The reference reel is real phone footage of real calligraphy burning; three rounds of simulation never passed as real. This edition has no burning-paper scene. If real strips are filmed (`docs/paper-shoot-guide.md`, `pipeline/make_burn_strips.cjs`), they cut straight in (section 5).
3. **Real footage only, cut as a montage.** 25 shots in 31 s. Every cut falls on a spoken word's onset or on a music accent. Speed ramps, whips, a zoom punch, flashes, dissolves that pass through a double exposure, a smoke matte, an impact jolt.
4. **The words are set into the shots.** One or two words per row, large, arriving as they are spoken, inside the shot they are spoken over. Flames, sparks and falling sand pass in front of them; branches cross them; a clock dial carries one of them like a numeral.

## 1. The cut
`data/blades/plan.py` is the edit: every shot, cut, ramp, transition and word placement, with the reasons as comments. Running it writes `data/blades/plan.json`, which the pipeline builds from.

| Start (s) | Shot | Picture (Mixkit item) | Words on it | Into the shot |
|---|---|---|---|---|
| 0.00 | fire | flames rising on black (52292) | «المُتَنَبّي», lit by the fire, flames passing in front | fade in |
| 1.78 | lights | red tea-lights going out one by one (3438), ramped so the last dies at 3.3 s | «يُدَفِّنُ» / «بَعضُنا بَعضاً» | cut |
| 3.76 | walk | bare feet and a white robe on wet sand (1013); the music enters; a real prism leak washes over the cut (3987) | «وَتَمشي» | cut from black |
| 4.68 | crowd | ghosts of a night crowd, long exposure (3433) | «أَواخِرُنا» | whip |
| 5.34 | foam | the same feet, the sea running over them (1013) | «عَلى هامِ الأَوالي» | whip |
| 6.34 | pour | molten metal poured, sparks (2861), a push-in on the accent at 7.01 | «نُعِدُّ» / «المَشرَفِيَّةَ» | warm flash |
| 7.40 | forge | tall flames on charred logs (42768) | «وَالعَوالي» | zoom punch |
| 8.13 | glass | an hourglass (28894), ramped so the sand runs out on «بِلا قِتالِ» and the picture dies | «وَتَقتُلُنا المَنونُ» / «بِلا قِتالِ», the sand falling in front | hard cut on the accent |
| 10.63 | tether | a horse's head in halter and chain (100663) | «وَنَرتَبِطُ» | cut from black |
| 11.42 | eye | a horse's eye (100645) | «السَوابِقَ» | cut |
| 12.08 | grey | a grey horse behind stable bars (100646) | «مُقرَباتٍ» | cut |
| 12.82 | canter | a dark horse cantering in dusk haze (1154) | «وَما يُنجينَ» / «مِن خَبَبِ» | whip |
| 14.38 | night | a night sky turning to dawn in half a second (4357) | «اللَيالي» | dissolve |
| 14.95 | man | a man's black profile against lit smoke (948), slow push-in | «وَهانَ» / «فَما أُبالي», in the black of his shoulders | dissolve (the night shows through him) |
| 16.70 | sky | a storm sky shutting, time-lapse ×12 (118) | «بِالرَزايا» | cut |
| 17.42 | dust | a man's back walking into smoke, graded as a dust storm (417) | «لِأَنّي ما اِنتَفَعتُ» / «بِأَن أُبالي» | real smoke as a matte (1961) |
| 19.50 | train | a subway train rushing in (1622), ×2.8 | «رَماني» | whip |
| 20.17 | clock | a clock face whose light goes out (28885) | «الدَهرُ», in ink on the dial like its numerals | flash |
| 20.60 | volley | a storm of sparks streaking like arrows (4426, turned 90°) | «بِالأَرزاءِ», sparks passing in front | dissolve |
| 21.56 | coal | one glowing coal (3462) | «حَتّى» / «فُؤادي» | dissolve |
| 22.46 | thorns | black branches tossed across a low sun (3969) | «في غِشاءٍ» / «مِن نِبالِ», behind the branches | dissolve (the coal becomes the sun) |
| 23.70 | man2 | the man's back (948); from 24.2 s real sparks stream across him (4426) | «فَصِرتُ إِذا» / «أَصابَتني سِهامٌ» | cut |
| 25.52 | shards | splinters of rock in exploding water, from above (1956, turned 90°), with a lens jolt | «تَكَسَّرَتِ» | smash cut |
| 26.22 | blade | a long blade of rock, a wave sweeping over it (51455, turned 90°) | «النِصالُ» | cut |
| 26.84 | rock | a 0.9 s fall onto a lone rock in a dark sea (44398, turned 90°, ×20 then real time); it stays | «عَلى النِصالِ», then the two credits | cut |

**Why these images.** The verses are about burial and the living walking on; weapons made ready and a death that needs none; swift horses that cannot outrun the nights; a man who has stopped flinching; time as the archer; and a heart so full of arrows that new ones only break on the old. The walker of verse 1 becomes the man of verses 4 and 6 and, in the last shot, the rock. Fire runs through the first half (the name, the candles, the pour, the flames, the sparks, the coal) and water takes the end. The modern images the commissioner once asked for are the night crowd, the subway train and the clock.

**Top-down shots are turned 90°.** A drone shot looking straight down has no "up". Turned, a 3840×2160 source fills the 2160×3840 frame with no crop: full 4K, and a wide view a 9:16 window could never hold (the lone rock in its sea; the long rock that reads as a blade).

## 2. The lettering (`remotion/src/BladesText.tsx`, `pipeline/comp_text.py`)
- **Scale and rhythm.** Amiri Bold, 140–230 px in a 1080-wide frame; the poet's name in Aref Ruqaa. A row never exceeds 84 % of the width and nothing sits below 80 % of the height. Each hemistich is split into blocks, one per shot; fast runs of shots keep their words in one place so the eye does not hunt.
- **One gold word per line**, the image-word: «يُدَفِّنُ», «المَشرَفِيَّةَ», «المَنونُ», «السَوابِقَ», «اللَيالي», «بِالرَزايا», «الدَهرُ», «فُؤادي», «نِبالِ», «سِهامٌ», «النِصالُ», «النِصالِ».
- **A block leaves with its shot.** On a hard cut it is gone on the cut frame; into a transition it fades over the transition's first half (`plan.py`, `leaves()`).
- **In the shot, not on it.** Bright things pass in front of the letters (flames over the name, candle flames, falling sand, sparks); dark branches cross «في غِشاءٍ مِن نِبالِ»; «الدَهرُ» is set in ink on the clock dial and goes dark with it; letters lit by a shot's own light keep 60 % when that light dies, so the last word of a dying shot stays readable. Where a plate is bright under a line, a soft shade is pooled there, measured, with no caption box.
- No depth estimation is used in the final cut (the tools for it, `depth_cache.py` and the depth options of `comp_text.py`, remain).

## 3. The engine (`pipeline/montage.py`)
- **Time remapping** with keys, so a shot ramps (the candles, the hourglass, the fall onto the rock), and a real shutter: when a shot runs fast, the source frames inside each output frame's exposure are averaged in linear light.
- **Transitions centred on the cut:** whip (a push with directional blur), zoom (one continuous punch-through), flash (a soft bloom, one rise and one fall), matte (the luma of a real smoke clip wipes one shot into the next), dissolve.
- **Shake** (a small handheld drift; stronger on the two impact shots) and **shock** (colour fringes that close and a breath of overexposure on the smash cut).
- **Overlays** of real elements shot on black (the sparks, the prism leak), screen-blended.
- **Rotation** of top-down sources.
- One grade for all shots (`build_picture.py`), one grain pass over picture and letters together, levels clamped to 18–232 before encoding.

## 4. What could not be had
- **Real burning calligraphy.** The only free burning-paper footage reachable is a printed Latin-script book in flames (Mixkit 52295, 52298–52300); it does not suit Arabic verse. Blank-paper burns exist on Mixkit only under its restricted licence.
- **Swords, spears, archery, a smith.** Mixkit's free tier has none. Wikimedia Commons has candidates (list in the scout's record), but its media server refused every download from this machine (HTTP 429), so none could even be viewed.
- **A person in a real storm.** Free only as figures in smoke (the two shots used).
- **4K sources for five shots.** The flames of the title, the tea-lights and the sparks are 1080 px wide (doubled in the master); the cantering horse comes from a 1920×1080 clip of which a 608 px window survives. Everything else is from 4K files.

## 5. If the burning strips are filmed
`pipeline/make_burn_strips.cjs` prints the twelve hemistichs as strips with a shooting guide. A filmed strip replaces a shot by its file path in `plan.py`; setting `"hide": true` for that hemistich in the plan's `lines` removes the overlaid words there (the line is then in the picture itself), and QC lists it as "in picture".

## Rebuild
```
V=/home/user/film/venv/bin/python; R=/home/user/Builder-Baseerah/sutoor-film
$V $R/data/blades/plan.py                                   # the edit -> data/blades/plan.json
$V $R/pipeline/render_blades.py $R/data/blades/plan.json WORK OUT.mp4 --share OUT_1080.mp4   # picture, letters, grain, the plan's soundtrack
$V $R/pipeline/qc_blades.py OUT.mp4 $R/data/blades/plan.json WORK qc.json --licences LICENCES.json
```
A section can be rendered alone (`--from T --to T --scale 0.5`), which is how every change was checked before the 4K render.
