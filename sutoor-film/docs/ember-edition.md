# «النِصالُ عَلى النِصالِ», the Ember edition (9:16 reel)

## What was asked
- "Something similar to this (not copy-paste), same concept and ideas", with a 6.8 s reference reel attached.
- "The speaker … looks like he is speaking so fast; adjust that."

## The reference, analysed
| Element | Reference | Ember edition (same idea, our own form) |
|---|---|---|
| World | One intimate, practical place: a carpet, a candle, then the ground at night | One world of fire, at night: coal, embers, a candle, smoke, a forge |
| Object carrying the verse | Calligraphy on a strip of paper | The poem's own object: a blade, forged on the anvil |
| Transformation | The paper burns | The blade is struck («تَكَسَّرَتِ النِصالُ عَلى النِصالِ») |
| Text | Each word appears as it is spoken | Each word appears as it is spoken (aligned onsets, 0.06 s lead) |
| Ending | One word glowing alone on black («سحر») | The last word, «النِصالِ», glowing like iron from the forge, then cooling to darkness |
| Format | Full-screen vertical | Full-screen 1080×1920, native-vertical footage where possible |

Not copied: no paper, no handwriting being burned, no carpet. Burning-book footage was available and was deliberately left out because it is too close to the reference.

## Pace
Measured, not guessed. The reciter's syllable rate (about 4–5 per second) is close to the reference reciter's (about 4–6). What made him feel rushed was the lack of breathing room. Gaps between lines were as short as 0.04 s between verses 1 and 2, and 0.08 s between verses 5 and 6. A new line and a new shot arrived every two seconds.

Fix (`pipeline/repace.py`):
- **Pitch-preserving slowdown:** 0.92× (rubberband), applied to the whole voice. Intonation and pitch are unchanged.
- **Pauses opened:**
  - At least 0.60 s between the two hemistichs of a verse.
  - At least 1.15 s between verses.
  - The silence is inserted at the quietest point of each gap.
- **Result:** the recitation runs 35.1 s instead of 26.8 s.

Verified:
- A fresh forced alignment on the slowed voice matches the remapped word times (median error 7 ms, 90th percentile 16 ms).
- Whisper still transcribes the verses.
- No clicks at the joins: the largest sample step in the slowed file (0.67) is lower than in the original (0.72), and the steepest attacks belong to the reciter's own consonants.

The score and the mix are regenerated on the new timeline, so the music's ducking and its accents follow the new pauses. In the reel the voice enters at 2.5 s, not 4.5 s, because the first seconds of a reel decide whether people keep watching.

## Shot list
| Shot | Time (s) | Line | Image | Source · licence |
|---|---|---|---|---|
| E0 | 0–2.3 | — | Veins of fire in black coal, fading up from darkness | [Mixkit 3435](https://mixkit.co/free-stock-video/chunks-of-coal-lit-in-the-dark-3435/) · Free |
| E1 | 2.3–5.9 | يُدَفِّنُ بَعضُنا بَعضاً وَتَمشي | Live embers under a crust of ash | [Mixkit 3454](https://mixkit.co/free-stock-video/coal-consumed-in-fire-3454/) · Free |
| E2 | 5.9–8.5 | أَواخِرُنا عَلى هامِ الأَوالي | Grey coals lying on the glowing ones beneath | [Mixkit 3443](https://mixkit.co/free-stock-video/fire-burning-red-burning-coal-3443/) · Free |
| E3 | 8.5–11.2 | نُعِدُّ المَشرَفِيَّةَ وَالعَوالي | The forge: a glowing blade hammered, strike on «المَشرَفِيَّةَ» | [Commons: Smithy- steel forging (2)](https://commons.wikimedia.org/wiki/File:Smithy-_steel_forging_(2).webm) · CC BY 3.0 |
| E4 | 11.2–13.6 | وَتَقتُلُنا المَنونُ بِلا قِتالِ | A candle falters on «المَنونُ» and dies on «قِتالِ» | [Mixkit 3458](https://mixkit.co/free-stock-video/candle-lighting-in-the-dark-3458/) · Free |
| E5 | 14.0–16.8 | وَنَرتَبِطُ السَوابِقَ مُقرَباتٍ | The horse's eye under its forelock | [Mixkit 100645](https://mixkit.co/free-stock-video/horse-in-a-stable-close-up-100645/) · Free |
| E6 | 16.8–19.6 | وَما يُنجينَ مِن خَبَبِ اللَيالي | Tealights; darkness falls on «اللَيالي» | [Mixkit 3438](https://mixkit.co/free-stock-video/flames-in-candles-close-up-3438/) · Free |
| E7 | 19.6–25.5 | وَهانَ فَما أُبالي … / لِأَنّي ما اِنتَفَعتُ … | One long thread of smoke: nothing left to burn | [Mixkit 50956](https://mixkit.co/free-stock-video/soft-and-traslucent-smoke-flows-up-on-a-dark-background-50956/) · Free |
| E8 | 25.5–28.9 | رَماني الدَهرُ بِالأَرزاءِ حَتّى | Sparks fly at the camera; a burst on «رَماني» | [Mixkit 3463](https://mixkit.co/free-stock-video/sparks-of-fire-on-a-black-background-3463/) · Free |
| E9 | 28.9–31.6 | فُؤادي في غِشاءٍ مِن نِبالِ | A glowing core inside a jagged black crust | [Mixkit 3462](https://mixkit.co/free-stock-video/flame-burning-coal-in-detail-3462/) · Free |
| E10 | 31.6–38.0 | فَصِرتُ إِذا أَصابَتني سِهامٌ / تَكَسَّرَتِ النِصالُ عَلى النِصالِ | Hammer on hot steel: sparks on «أَصابَتني سِهامٌ», real strikes on «تَكَسَّرَتِ» and «النِصالِ» | Commons (as E3) · CC BY 3.0 |
| End | 38.0–44.9 | — | «النِصالِ» white-hot on black, cooling through orange and red; credits | — |

E3 and E10 use two different, non-overlapping moments of one real take. QC checks that no moment of footage is reused.

## Sound
- **Voice:** re-paced as above. Nothing else is done to it beyond gain and a 45 Hz high-pass.
- **Hammer:** the forge clip's own sound, cut at exactly the picture's in-points, so every strike is in sync. The last strike rings into the black.
- **Fire:** Mixkit "Campfire crackles" and "Campfire burning crackles" (Mixkit Sound Effects Free License). The fire bed drops under the candle's death and the smoke, and rises for the opening and the glowing word.
- **Score:** the original maqam score (Kurd/Hijaz on E), re-composed on the new timeline.
- **Master:** −14 LUFS, −1 dBTP.

## Text
- **Truth table:** the exact text, with full diacritics. QC confirms that the word tokens rebuild every hemistich exactly, and that the closing word equals the poem's last word.
- **Font:** Amiri for the verses. Aref Ruqaa for the glowing word, whose handwritten character echoes the reference's calligraphy.
- **Layout:** the verse sits in the lower-middle of the frame, over a soft dark band, clear of the bottom area that social-app controls cover.
