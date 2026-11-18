# «النِصالُ عَلى النِصالِ», the Journey edition (2160×3840, 24 fps)

## What was asked
- "There was someone screaming while he was talking … fix it."
- "The man's voice … is isolated somehow … like it has been delivered through a tunnel."
- "Do not use the same scene … different burning stuff … as cinematic as possible."
- "I did not like the cinematic appearance of each footage … just like a video with a text in front of it. We need to feel like a cinematic 4K journey of this poem … make it related, make it sensible."

The first cut of this edition went to an independent four-critic review: a first-time viewer, a cinematographer, an Arabic calligrapher and a sound mixer. Each major finding was then re-checked by adversarial verifiers. The scores were 5, 5, 6 and 7 out of 10. The revised cut went to a second, fresh panel (the same four lenses plus a regression check of every round-1 row). It scored 5, 5, 8.5 and 6.5, with 6 for the regression check. Its verified findings were again about the burns and the look. This document describes the film after both rounds: section 7 lists the round-1 findings and section 7b the round-2 findings, with what was done about each.

## 1. The scream: found, removed, and checked with a control
**What it was.** It was not a second voice in the recitation. It was the forge clip's own audio (Smithy: steel forging, used as hammer sound in the Ember and Paper reels). That audio holds a pitched, pulsing tone near 2.6 kHz for about 2.5 s, which is heard as a scream under the words. The clip's audio is gone from this edition. Every effect is a licensed Mixkit sound with one job: a footstep, a buckle, a blade, a spear-shaft knock, rain, surf, fire, wind, a splash, steam. Whinnies, bird calls, whistling wind and anything that could hold a human voice are banned.

**How it is checked** (`pipeline/scream_check.py`, run on the final mix):
1. It subtracts the voice bus from the pre-master mix and runs a vocal-separation model on what is left (music, ambience and effects). That remainder must carry no voice: under −42 LUFS short-term, with under 2 % pitched frames.
2. **Positive control (new).** It plants 2 s of a real voice at −30 LUFS in the quietest stretch of the same remainder and re-runs the separator. The check is trusted only if the planted voice is found above −42 LUFS. A silent result therefore means "nothing there", not "the detector heard nothing".
3. It scans the effects and ambience for any held, pitched tone longer than 0.8 s. The detector flags the old forge sound in both earlier reels.
4. It splits the voice bus into a lead voice and any backing voice. The backing part must stay under −50 LUFS.

Every stem's peak level is now reported alongside its loudness. Results: section 6.

## 2. The voice: no tunnel, no dead stops, one room
**Measured causes of the "tunnel":**
- an earlier 0.92× time-stretch, which added a phasey, hollow colour;
- an earlier corrective EQ that cut 9.5 dB at 8 kHz.

Both are gone. The voice is the lead stem of the original recording, with no stretch. Only the pauses between lines are longer.

**What the review found next, and what changed** (`pipeline/voice_edges.py`; every word stays at exactly the same time):
- **Dead stops at line ends.** Where the reciter ran one line into the next, the inserted pause cut him off mid-sound (v1a, v1b, v4a, v5, v6). Each such line now fades out over 80 ms (30 ms where it was already quiet), and the next line fades in over 25 ms.
- **Digital silence between lines.** The whole voice now sits in one small, diffuse room: RT60 0.6 s, 20 dB under the dry voice, band-limited, with no slap. Every line decays into a space instead of into digital zero. A room tone at −70 dBFS runs underneath.
- **Air removed by EQ.** The −1.5 dB shelf above 6.5 kHz is undone.

**Result:**
- The long-term spectrum matches the original separated vocal within ±0.2 dB from 250 Hz to 16 kHz. Before, the voice was 1.5–1.7 dB down from 8 kHz up.
- 63–125 Hz is 1 dB lower: the rumble filter.

## 3. The mix: the voice in one steady place (`pipeline/mix_journey.py`)
The review measured the music between 12 and 33 dB under the voice from line to line. Verse 4 was left alone over the sea bed, and the closing verse was buried at 8–9 dB over everything else. Now:

**Ducking**
- The voice's own level drives it, not a list of word times.
- 5 dB of ducking, 150 ms look-ahead.
- It holds through any pause shorter than 1.5 s and releases over 1.3 s, so the music no longer swells in every gap.

**Level per hemistich (half-verse)**
- Automation holds the music **14.0 dB under the voice in all 12 hemistichs**.
- It holds everything else (music, ambience and effects) **at least 12.0 dB under the voice**. The beds are lowered only in the lines that need it.

**Score and effects**
- A quiet cello and viola pad now carries verse 4.
- The wave under the rock shot fades out at the cut.
- The horse's snort ends before «نُعِدُّ» and is 5 dB lower.
- The footstep in the puddle is now audible.
- The blade sits 3 dB lower.

**Master**
- Static gain, then a 4×-oversampled peak limiter. No moving loudness normalisation, which had lifted the coda by 5 dB.
- −14.4 LUFS integrated, −1.6 dBTP.
- A 1.8 s fade to silence at the end.

## 4. The film
One journey across two days. Cuts fall in the pauses, except the three strikes of the rain volley. The text stays in one place.

| # | Film time (s) | Line | Image | Source |
|---|---|---|---|---|
| 1 | 0.00–5.05 | يُدَفِّنُ بَعضُنا بَعضاً وَتَمشي | **Burn I**: a strip torn from an old manuscript lies on autumn leaves in low sun. A smouldering ember reads the line right to left and reaches each word only after it is spoken. «وَتَمشي» ("and walks on") survives into the next shot, which is of walkers. | Mixkit 1692 (live, stabilised); flames 3764; smoke 50956, 3452 |
| 2 | 4.45–7.65 | أَواخِرُنا عَلى هامِ الأَوالي | Through the smoke: the living reflected upside down beneath wet paving. A foot lands in the puddle on «هامِ» and the words ripple. | Mixkit 1324 |
| 3 | 7.65–9.10 | نُعِدُّ المَشرَفِيَّةَ | A man readies the horse; a blade is heard being drawn | Mixkit 100653 |
| 4 | 9.10–10.15 | وَالعَوالي | The same horse, saddled; a spear-shaft knock lands on the cut | Mixkit 100655 |
| 5 | 10.15–12.95 | وَتَقتُلُنا المَنونُ بِلا قِتالِ | The stable's candle, framed close, shrinks and dies just after «قِتالِ»; the letters die with it | Mixkit 3458 |
| 6 | 12.95–15.70 | وَنَرتَبِطُ السَوابِقَ مُقرَباتٍ | The same horse's eye behind the stall bars, in black and white; the words rack into focus with it | Mixkit 100639 |
| 7 | 15.70–19.65 | وَما يُنجينَ مِن خَبَبِ اللَيالي | Night overtakes the Alhambra; the floodlights come on under «اللَيالي», which lights up warm; distant hooves. The 30 fps timelapse plays at 0.8×, one source frame per film frame (no dropped-frame stutter) | Mixkit 4013 |
| 8 | 19.65–21.70 | وَهانَ فَما أُبالي بِالرَزايا | Blue hour before dawn: a heron unmoved as the sea breaks behind it, in true slow motion. Where the foam rises through the words it washes over them, and they come back. | Mixkit 1906 |
| 9 | 21.70–24.95 | لِأَنّي ما اِنتَفَعتُ بِأَن أُبالي | **Burn II**: a letter laid on a shore fire's coals. It browns from the edge nearest the coals while he speaks, then catches from that edge in slow real flames. | Mixkit 3443; flames 52292; smoke 50956, 3452 |
| 10–12 | 24.95–27.75 | رَماني الدَهرُ بِالأَرزاءِ حَتّى | Three cuts on three words, each a strike: drops landing like arrows; each strike ripples the line | Mixkit 2208, 3903, 1751 |
| 13 | 27.75–30.40 | فُؤادي في غِشاءٍ مِن نِبالِ | A cactus heart caged in a sheath of amber-lit spines, still beaded with rain | Mixkit 1890 |
| 14 | 30.40–33.15 | فَصِرتُ إِذا أَصابَتني سِهامٌ | A lone rock vanishes under a breaking wave and is still there. Once «سِهامٌ» is spoken the wave washes the words away, and the camera pushes in as the day sinks to night | Mixkit 51506 |
| 15 | 33.15–40.60 | تَكَسَّرَتِ النِصالُ عَلى النِصالِ | **Burn III**: a thick handmade sheet, pierced by arrows, lying on the sea rocks at night with the surf in frame (sequence below). | Mixkit 1081 (4K, re-timed); flames 3764, 52292; sparks 3463; smoke 50956; steam 3452 |
| 16 | 40.60–44.00 | credits | The names in Aref Ruqaa, in ember orange, on a grained black | — |

Burn III, step by step:
- The sheet lies slightly turned and bowed on the rock, lit by the same cool moonlight as the rocks around it, with the surf moving at the foot of the frame.
- The whole line stays readable on the sheet until 0.6 s after he finishes it.
- Then every arrow hole catches at once and the fire eats outward from the wounds along ragged fronts. Each flame is its own piece of real fire, and the firelight falls on the rock.
- Only «النِصالِ» survives, as glowing ember strokes on a pale ash flake, and it breathes with three gusts.
- The sea's own surge, real water from the plate, sweeps in. The ember dims as the spray reaches it, and the water puts it out. Steam rises over the dark rock.

**Three burns, three different scenes:**

| | Burn I | Burn II | Burn III |
|---|---|---|---|
| Object | Manuscript strip, bent over a leaf | Folded letter, sagging in perspective on the coal bed | Pierced handmade sheet, turned and bowed on the rock |
| Ground | Leaves (real dolly, stabilised on the leaf) | Coals (red, all warm) | Sea rocks at night, surf in frame (cold blue) |
| Light | Low sun, rim-lit torn edge | Coal glow from below and along the edge nearest the coals | Moonlight on sheet and rock alike, then firelight |
| Fire | Ragged smoulder line, front reads the line | Scorch from the coal side, then a catch | All arrow holes ignite at once, burning outward |
| Ending | «وَتَمشي» survives into the walkers | Flames take the letter | One word survives; the real surge quenches it |

Only the paper, ink, char and ember strokes are simulated (`pipeline/paper_burn7.py`). The ground, flames, smoke, sparks and water are real footage. Each flame on a burning edge is its own window of a real flame clip, with its own start frame, mirror, scale and lean, and an alpha taken from its own light and feathered on every side. Burn II's big catch flame rises only from the part of the letter that is burning, and its edges are drawn by the flames' own tongues.

**Fire timing.** For every word, the renderer logs when the fire first touches its ink (`word_first_burn_s`), and QC checks it against when the word is spoken.

## 5. Text that belongs to the picture
**One system, one place.**
- The sadr (first half of the verse) is centred at 19 % of the frame height and the ajuz (second half) at 27 %.
- Each word appears at its aligned onset with a 0.18 s ink-bleed.
- During the ajuz the sadr stays above it at 45 %. Over a bright plate it rises to 57 %, and over a near-black plate to 62 %, measured under that line.
- Where a half-line is written on burning paper, only one kind of lettering is on screen at a time. Burn I's line, once burnt, does not come back as a recall. Over Burns II and III the overlay half-line fades out as the burn shot begins.
- A soft shade appears only where the plate under the lines is bright, measured per line rather than as the frame average.

**The picture acts on the words**, driven by measurement. `build_picture.py` records, per frame, the brightness under each line and the share of foam-white pixels in the text zone.

| Where | What happens |
|---|---|
| Wet street | The foot lands in the puddle and the lines ripple |
| Candle | The words hold until «قِتالِ» is spoken, then die with the flame |
| Horse's eye | The words rack into focus with the shot |
| Alhambra | The floodlights light «اللَيالي» |
| Heron and rock | Where foam rises through the text zone it washes over the words; they come back when it clears. On the rock the wash waits until «سِهامٌ» has been spoken |
| Rain | Each arrow-drop strike ripples the line |
| The three burns | The line is written on the paper itself |

**Colour.** The words take each shot's key light. One grain pass covers picture and text together.

## 6. Results
**Scream check** (`/home/user/film/journey/scream_check3.json`, on the final mix3): **PASS**
- **Remainder of the mix (no voice bus):** music, ambience and effects. Its vocal stem stays 12 dB under the loudness gate at its highest point (−54.3 LUFS short-term at 25.6 s, a sliver of the second arrow whip) and has 0 % pitched frames.
- **Positive control:** a voice planted at −30 LUFS was found at −27.7 LUFS. The detector can hear a voice in this bed.
- **Effects and ambience:** no held pitched tone.
- **Voice bus:** its backing stem is −64.1 LUFS integrated.

**Mix** (`audio/mix3/mix_report.json`):
- The voice sits 14.0 dB over the music in all 12 hemistichs.
- It sits 12.0–13.8 dB over everything else.
- The master is −14.4 LUFS integrated, −1.6 dBTP.

**Round-2 sound changes** (`data/journey/sfx_spec.json`; the effects track keeps its overall loudness, so every untouched effect sits at exactly its previous level):
- **The wave before the title line** (2411, the storm swell into the cut) now fades in over 0.5 s and ends at the cut, 33.15 s. Beds in 32.9–33.45 s peak at −22.0 LUFS momentary, 10 dB under «تَكَسَّرَتِ» (was 6.5 dB). Nothing of it runs into the line.
- **The ignition** (35.95 s) has its own sound: a fire swoosh catching (1328) and a crackle swell (1736) peaking at 36.46 s. The master reaches −19.0 LUFS momentary there, against a flat −22 before.
- **The surge** hits as the water reaches the word: the splash (1311) lands at 38.88 s (was 38.60), steam at 38.85 s. A breaking wave (1206) crests at 39.70 s with the whitewater, so the climax sustains at about −19.6 LUFS instead of dying away.
- **The candle whoosh** now starts at 12.16 s, after «قِتالِ», and peaks at 12.37 s as the flame dies. The voice is 11.1 dB over everything else on the word (was 7.2).
- **The three arrow whips** are three different sounds (1487, 1471, 1461), correlation 0.07–0.16 (was 1.00), each on exactly the same frame as before.

Rebuild:
```
V=/home/user/film/venv/bin/python; R=/home/user/Builder-Baseerah/sutoor-film; A=/home/user/film/journey/audio
$V $R/pipeline/build_sfx.py $R/data/journey/sfx_spec.json $A/sfx_raw3.wav
$V $R/pipeline/build_sfx.py $R/data/journey/amb_spec.json $A/ambience_raw.wav
ffmpeg -v error -y -i $A/ambience_raw.wav -af "acompressor=threshold=-34dB:ratio=3:attack=20:release=400:makeup=1" -c:a pcm_f32le $A/ambience_bed.wav
$V $R/pipeline/mix_journey.py $R/data/timing_journey.json /home/user/film/journey/voice/voice_edges.wav $A/score/score.wav $A/ambience_bed.wav $A/sfx_raw3.wav $A/mix3
$V $R/pipeline/scream_check.py $A/mix3 /home/user/film/journey/scream_check3.json
```
The score: `cd $A && SCORE_EDITION=journey QUENCH_T=38.75 CREDITS_T=40.5 $V $R/pipeline/compose_score.py $R/data/timing_journey.json score`.

**Picture QC** (`/home/user/film/journey/qc/qc_journey.json`): **20 of 20 checks pass**
- **Text:** every verse matches the supplied text in Unicode with its harakat. Each word appears at its aligned onset, and verses never overlap.
- **Picture:** no unintended black (the candle's death at 12.0–12.7 and the credits are the only black), no frozen picture, and no photosensitive flash failure.
- **Audio:** −14.45 LUFS, −1.5 dBTP, no clipping. The film's audio carries the original voice (correlation 0.957, lag 3 ms).
- **Licences:** every shot has a licence record, and no source footage is reused.
- **Master:** 2160×3840 H.264 High, 44.0 s, 475 MB. A 1080×1920 share copy of 50 MB is also provided.

**Fire never touches a word before it is spoken** (`journey_qc_extra.json`; the renderer logs each word's first-burn time):
- **Burn I:** the margins are 0.41, 0.89, 0.76 and 0.85 s.
- **Burn II:** 0.85–2.03 s.
- **Burn III:** the title line is held whole until 0.61 s after he finishes it. The margins are 2.02, 1.49, 1.17 and 0.61 s.
- In Burn III every wound clears all ink by at least 56 px at render size.

**Black levels by shot** (share of pixels at video black; mean luma):
- **Burn III:** 18 %, mean 34.6. It was 41 % before, mean 31.9.
- **Candle:** 65 %, by design: it is a flame in the dark.
- **Every other shot:** 12 % or less, apart from the rock shot's planned sink to black at its end.

## 7. The review: verified findings and what was done
| Finding (severity) | Done |
|---|---|
| Burn III: composited look; no visible water; dark box around the surviving word; quench was a fade; climax nearly black (blocker) | Rebuilt on a real moving plate of sea boulders (1081), re-timed so the sea's own surge arrives at the quench. Lit sheet; the char breaks into irregular pieces with no box; the real water quenches it; steam |
| The poem's title line never readable in full (blocker) | Held whole and clean until 0.6 s after it is spoken (fire first touches it at 36.05 s; the line ends at 35.45 s) |
| The last word lost the dot of its nun to an arrow hole (blocker) | Wounds are kept clear of all ink, dots and harakat by their radius plus a margin (closest clearance 40 px at render size); the dot glows |
| Burn II looked pasted on: flat card, round scorch discs, rectangle catch, hollow-polygon ash (major) | Perspective on the coal plane, curl, coal underlight. Scorch spreads irregularly from the coal edge. The catch spreads from that edge over 0.85 s. No outline shapes; ash is grey, tumbling flakes; embers cluster |
| Burns share a procedural look: uniform neon edge, polygon ash, straight char (major) | The burning edge varies in width and brightness; embers stay in fresh char; fragment-outline glow removed; each burn has its own fire grammar |
| Burn I: a frozen still; flat strip; fire ate the first and last words as he spoke them; opened from black (major) | Live plate, stabilised on the leaf (real parallax); the strip bends over the leaf with a rim-lit edge; the front reaches each word only after it is spoken (first touches: 2.50, 3.49, 3.72 and 5.19 s, against word ends of 2.08, 2.60, 2.96 and 4.34 s); opens on a lit frame |
| Text still read as subtitles (major) | The picture now acts on the words (section 5) |
| Black levels differed from shot to shot; rain shot milky; night cut to the brightest shot (major) | Black floors matched (the rain shots pulled down 9–17 %); the heron graded as blue hour before dawn; the cactus back to green |
| Smoke wipe was a 3-frame glitch; two muddy dissolves (major and minor) | A 14-frame smoke wipe; the dissolves replaced by cuts in the pauses |
| Heron juddered (59.94 fps dropped to 24) (minor) | Played as 2.5× slow motion, every frame used |
| Voice cut dead at several line edges; music margin swung 20 dB (major) | Sections 2 and 3 |
| Too little grain; sub-legal black under the credits (minor) | Stronger grain matched to the footage; luma held to 16–235 |
| Credits: unreadable fine print, about 1.5 s readable (minor) | Names only, brighter, held about 2.5 s; licences moved to the post caption |

## 7b. The second review: verified findings and what was done
| Finding (severity after verification) | Done |
|---|---|
| Burn III, the closing scene, still read as a card pasted on a dark video. The sheet was a flat, front-on rectangle with no contact, lit at luma 138 over rock at 7. Holes looked like stamped stars. One flame clip was cloned with hard rectangular edges. The char stayed rectangular. The word floated in black, and the grade crushed the climax to a frame mean of about 6 (major, confirmed by three verifiers) | Re-rendered at full 4K on the native 4K plate. The sheet is smaller, turned 3.5°, slightly bowed, and lies on the rock with a soft contact shadow. The same cool moonlight falls on sheet and rock, and the rock is lifted so its texture and the surf show from the first frame. Seven torn, lobed holes with 1–3 tears each show the rock through them. Every flame is its own window, start frame, mirror, scale and lean of a real flame clip, with an alpha drawn from its own light and feathered on all sides. Wound fronts are ragged; the char breaks along wobbly cracks and its edges are eaten early. Firelight lifts the rock around the sheet. The word rests on a pale ash flake and keeps its kasras. The ember dims as the spray nears, then the real water puts it out, and steam (3452) rises over the dark rock. The push-in is 1.4× at most |
| Burn II: flat card hovering over the coals, a sunlit-looking hotspot and dapple, speckle scorch, a stock flame laid over the intact card ending in a vertical edge near the frame side (major) | The coal glow now comes from below and along the edge nearest the coals, deep red, with no central hotspot or mottling. The scorch is broad browning from the hot edge. The letter sags slightly. The catch flame rises only from the part of the letter that is burning, draws in as it climbs, and sways. Toward any edge only the flame's own brightest tongues survive, so no straight boundary is left. Firelight on the coals is doubled |
| Burns II and III read as the same scene: pale paper on a dark lumpy bed (verified minor) | Burn III now shows sea rocks in cold moonlight with surf in frame from its first frame. Burn II is all red coal glow |
| Burn I: see-through char, a rim-light hairline floating over the burnt part (major, unverified) | The char is opaque and darker and breaks into larger pieces. The rim light falls only on unburnt paper. The strip is brighter, for a more legible first line |
| Text still read as subtitles over most shots (major, unverified) | Only one kind of lettering is on screen at a time. The burnt first half-line no longer returns as a recall, and over Burns II and III the overlay half-line fades as the burn shot begins. Ripples are stronger (puddle 16 px, rain 18 px). The heron wash is stronger. The rock wash waits until «سِهامٌ» has been spoken. Over a near-black plate the recall is brighter |
| Exposure jumps at 19.65 (Alhambra night to heron) and 33.15 (day rock to night burn); lifted blacks on the rain and rock shots (major/minor) | The heron is graded a stop darker and bluer. The rock shot is darker, its black floor pulled down, and it sinks to black over its last 0.3 s into the night of Burn III. The rain floor is pulled down further (24 %). The horse shots are 0.2 stop darker after the dark puddle |
| Alhambra timelapse stutter (30 fps dropped to 24) (minor) | Plays at 0.8×, one source frame per film frame, re-cued so the floodlights still come on under «اللَيالي» |
| Credits on a flat, grainless black; small dark red (minor) | Additive grain on the credits card; names larger and in ember orange |
| Sound: wave crash as loud as the voice before the title line; no accent at the ignition; surge peaking before the water reaches the word; candle whoosh on «قِتالِ»; three identical arrow whips (major/minor) | Section 6 (mix3) |
| The tunnel is in the source (HE-AAC 63 kb/s); the voice is dry against a hall; three line ends truncate (all refuted or downgraded to minor by the verifier) | No change: the film's voice matches the original recording's spectrum within about 1 dB up to 24 kHz, and the mix covers the codec texture more than the original did |
| QC licence record named Mixkit 2189 for Burn III (minor) | Corrected to 1081 |

**Not changed, and why:**
- **Soft 1080p sources.** The Alhambra (4013), the heron (1906) and the first rain shot (2208) are 1080p sources scaled about 3.5×. They hold up on a phone but look soft at 100 % on a 4K screen. No free-licensed 4K replacement that keeps the same meaning was found.
- **The rhinestone browband** on the show horse in shot 3 stays.

## 8. Format and finishing
- **Master.** 2160×3840 at 24 fps, H.264 High 5.1, BT.709, luma 16–235, with grain over picture and text. A 1080×1920 share copy is also provided.
- **Footage resolution:**
  - 4K sources are cropped to 9:16.
  - The 1080p sources (4013, 1906, 2208) are scaled about 3.5×.
  - Burns I and II are rendered at 1620×2880. Burn III, the closing scene, is rendered at full 2160×3840 on the native 4K plate.
- **Camera moves.** Digital moves only for the push onto the rock and the push onto the last word (at most 1.4× on the 4K Burn III).
- **Grade.** One filmic curve, halation and vignette for the whole film, with a common black floor.
- **Post caption.** The full licence list is in `output/Nisal-ala-Nisal_Journey_post-caption.txt`.

## 9. Note on the text
The supplied text writes the sun letters without shadda, for example «النِصالُ» where classical vocalisation has «النِّصالُ». The film shows exactly the supplied text. It can be changed on request.
