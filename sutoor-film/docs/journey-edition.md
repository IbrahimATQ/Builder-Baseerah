# «النِصالُ عَلى النِصالِ», the Journey edition (2160×3840, 24 fps)

## What was asked
- "There was someone screaming while he was talking … fix it."
- "The man's voice … is isolated somehow … like it has been delivered through a tunnel."
- "Do not use the same scene … different burning stuff … as cinematic as possible."
- "I did not like the cinematic appearance of each footage … just like a video with a text in front of it. We need to feel like a cinematic 4K journey of this poem … make it related, make it sensible."

## 1. The scream: found and removed
**What it was.** It was not a second voice in the recitation. It was the forge clip's own audio (Smithy: steel forging, used as hammer sound at 7.3–10.3 s in the Ember and Paper reels). That audio holds a pitched, pulsing tone for about 2.5 s, which `scream_check.py` measures at around 2.6 kHz. Under the words it is heard as a scream.

**What changed.**
- The forge clip's audio is gone from this edition.
- Every effect is a licensed Mixkit sound (free licence) chosen for one purpose: a footstep, a snort, a buckle, a blade drawn, a spear-shaft knock, rain, thunder, surf, fire, wind, a splash.
- Horse whinnies, bird calls and whistling wind are banned. Two wind tracks that measured as whistling were replaced with noise-based wind.
- Any sample that could contain a human voice is also banned.

**How it is checked.** `pipeline/scream_check.py` runs on the final mix, not just on the voice stem:
1. It subtracts the voice bus from the pre-master mix and runs a vocal-separation model on what is left (music, ambience and effects). The result must be silent: under −42 LUFS short-term, with under 2 % pitched frames.
2. It scans the effects and ambience for any held, pitched tone longer than 0.8 s. This detector is calibrated: it flags the old forge sound in both earlier reels and passes every sound used here.
3. It splits the voice bus into a lead voice and any backing voice. The backing part must stay under −50 LUFS. It measures −64.

## 2. The "tunnel": two causes, both removed
**Measured, not guessed.**
- **The 0.92× time-stretch.** It added a phasey, hollow colour. The voice is no longer stretched; only the pauses between lines are lengthened.
- **My earlier corrective EQ.** It cut the top of the voice by 9.5 dB at 8 kHz, which dulled it further.

**The new voice.** It is the lead-voice stem of the original recording, almost untouched:
- 60 Hz high-pass;
- a light de-esser;
- a −1.5 dB shelf above 6.5 kHz.

Its octave-band balance matches the original recording within about 1 dB in every band from 125 Hz to 8 kHz. The 63 Hz band is the exception, about 3 dB lower: that is the high-pass removing rumble.

**Never over silence.** The voice now sits on a quiet bed of the scene's real ambience under every word, so it never floats over silence.

**Timing.** Word timings were re-verified by forced alignment: every word is within ±0.03 s. The first word is the exception, a known aligner artefact that also appears on the earlier file.

## 3. The film
One journey across two days. Most cuts fall in the pauses; three fall on words (the rain volley). The text stays in one place throughout.

| # | Film time (s) | Line | Image | Source |
|---|---|---|---|---|
| 1 | 0.00–5.05 | يُدَفِّنُ بَعضُنا بَعضاً وَتَمشي | **Burn I**: a strip torn from an old manuscript among autumn leaves in low sun. A smouldering ember line reads the line right to left, each word just after it is spoken, under backlit smoke. | Render on a still of Mixkit 1692; flames 3764; smoke 50956, 3452 |
| 2 | 4.75–7.65 | أَواخِرُنا عَلى هامِ الأَوالي | The living reflected upside down beneath wet paving; ripples break them | Mixkit 1324 |
| 3 | 7.65–9.10 | نُعِدُّ المَشرَفِيَّةَ | A man readies the horse; a blade is heard being drawn | Mixkit 100653 |
| 4 | 9.10–10.15 | وَالعَوالي | The same horse, saddled; a spear-shaft knock lands on the cut | Mixkit 100655 |
| 5 | 10.15–12.95 | وَتَقتُلُنا المَنونُ بِلا قِتالِ | The stable's candle shrinks and dies on «قِتالِ»; the letters die with it | Mixkit 3458 |
| 6 | 12.95–16.00 | وَنَرتَبِطُ السَوابِقَ مُقرَباتٍ | The same horse's eye behind the stall bars, in black and white | Mixkit 100639 |
| 7 | 15.45–19.65 | وَما يُنجينَ مِن خَبَبِ اللَيالي | Night overtakes the Alhambra; the floodlights come on under «اللَيالي», which lights up warm; distant hooves | Mixkit 4013 |
| 8 | 19.65–21.70 | وَهانَ فَما أُبالي بِالرَزايا | A heron unmoved as the sea breaks behind it and washes round its feet | Mixkit 1906 |
| 9 | 21.70–24.95 | لِأَنّي ما اِنتَفَعتُ بِأَن أُبالي | **Burn II**: a letter laid on a shore fire's coals. It only scorches while he speaks, then catches all at once in slow real flames and becomes an ash leaf. | Render on Mixkit 3443; flames 52292; smoke 50956, 3452 |
| 10–12 | 24.95–27.75 | رَماني الدَهرُ بِالأَرزاءِ حَتّى | Three cuts on three words, each a strike: rain drops landing like arrows; thunder, no lightning | Mixkit 2208, 3903, 1751 |
| 13 | 27.75–30.70 | فُؤادي في غِشاءٍ مِن نِبالِ | A green heart caged in a sheath of spines, still beaded with rain | Mixkit 1890 |
| 14 | 30.00–33.15 | فَصِرتُ إِذا أَصابَتني سِهامٌ | A lone rock vanishes under a breaking wave and is still there; the camera starts to descend | Mixkit 51506 |
| 15 | 33.15–40.60 | تَكَسَّرَتِ النِصالُ عَلى النِصالِ | **Burn III**: a thick handmade sheet pierced by about 20 arrow holes, on a stone in a tide pool at night. Open wind-whipped flames break out of the holes ahead of the front. Only «النِصالِ» survives, as glowing ember strokes that breathe with three gusts. Seawater then quenches it to black: thin strokes and dots first, the alif and lam last. | Render on Mixkit 2189; flames 3764, 52292; sparks 3463; smoke 50956 |
| 16 | 40.60–44.00 | credits | Black, with the credits in Aref Ruqaa in the dull red of cooled iron | — |

**Three burns, three different scenes:**

| | Burn I | Burn II | Burn III |
|---|---|---|---|
| Object | Manuscript strip | Folded letter | Pierced handmade sheet |
| Ground | Leaves | Coals | Wet stone |
| Light | Low sun | Dawn | Night |
| Camera | Low, raking | Three-quarter top-down | Top-down, pushing in onto the last word |
| Fire | Flameless smoulder | Slow scorch, then a sudden catch | Open flames out of many wounds |
| Ending | The char settles among the leaves | Ash flakes lift away | One word survives, then is quenched |

Only the paper, ink and char are simulated (`pipeline/paper_burn7.py`). The ground, flames, smoke, sparks and water are real footage.

## 4. Text that belongs to the picture
**One system, one place.**
- The sadr is centred at 19 % of the frame height and the ajuz at 27 %, in every footage shot. The eye never hunts for the text.
- Each word appears at its aligned onset with a 0.18 s ink-bleed: no slide, no bounce.
- During the ajuz the sadr stays above it at 45 %, so the whole verse is on screen.
- Every line stays clean until at least 0.4 s after it is spoken.
- In Burns I–III the burning line is written on the paper itself, with no overlay.

**The words take the scene's light:**
- Their colour follows each shot's key light: cold silver on the wet street, warm gold in the barn, amber from the candle, lilac over the Alhambra, pearl at the shore.
- Their brightness rides the measured light of the picture by about ±15 %.
- One grain pass covers picture and text together.

**Four moments where the picture acts on the words:**
- The candle's words die with its flame.
- «اللَيالي» is lit by the palace floodlights.
- The heron and the rock hold still under the sea, and so do the words.
- The burns.

## 5. Format and finishing
- **Master.** 2160×3840 at 24 fps, H.264 High 5.1, BT.709. A 1080×1920 share copy is also provided.
- **Footage resolution:**
  - 4K sources are cropped to 9:16 and scaled 1.78×.
  - The 1080p sources (4013, 1906, 2208) are scaled about 3.5×. Their softness reads as distance.
  - The burns are rendered at 1620×2880 and scaled 1.33×. That is no sharper than the plates they sit on, as the brief asked.
- **Camera moves.** No digital push-ins except the descent onto the rock and the push onto the last word.
- **Grade.** One filmic curve, halation and vignette for the whole film, grading the light each plate already has.
- **Audio.** Voice 12–18 dB over the music during words; master −14 LUFS integrated, −1 dBTP.

## 6. Note on the text
The supplied text writes «النِصالُ» without a shadda. Classical vocalisation has «النِّصالُ». The film shows exactly the supplied text; it can be changed on request.
