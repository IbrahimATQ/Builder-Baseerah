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

The score and the mix are regenerated on the new timeline, so the music's ducking and its accents follow the new pauses. In the reel the voice enters at 1.3 s, because the first seconds of a reel decide whether people keep watching.

## Shot list (after the independent review)
| Shot | Time (s) | Line | Image | Source · licence |
|---|---|---|---|---|
| E2 | 0–7.3 | يُدَفِّنُ بَعضُنا بَعضاً وَتَمشي / أَواخِرُنا عَلى هامِ الأَوالي | Grey coals lying on the glowing ones beneath, bright from frame 0 | [Mixkit 3443](https://mixkit.co/free-stock-video/fire-burning-red-burning-coal-3443/) · Free |
| E3 | 7.3–10.3 | نُعِدُّ المَشرَفِيَّةَ وَالعَوالي | The forge: a glowing blade struck, then lifted | [Commons: Smithy- steel forging (2)](https://commons.wikimedia.org/wiki/File:Smithy-_steel_forging_(2).webm) · CC BY 3.0 |
| E4 | 10.3–12.35 | وَتَقتُلُنا المَنونُ بِلا قِتالِ | A candle falters and dies with «قِتالِ» | [Mixkit 3458](https://mixkit.co/free-stock-video/candle-lighting-in-the-dark-3458/) · Free |
| E5 | 13.15–15.6 | وَنَرتَبِطُ السَوابِقَ مُقرَباتٍ | The horse's eye, regraded to low firelight | [Mixkit 100645](https://mixkit.co/free-stock-video/horse-in-a-stable-close-up-100645/) · Free |
| E6 | 15.9–18.4 | وَما يُنجينَ مِن خَبَبِ اللَيالي | Tealights; darkness falls on «اللَيالي» | [Mixkit 3438](https://mixkit.co/free-stock-video/flames-in-candles-close-up-3438/) · Free |
| E7 | 18.4–24.3 | وَهانَ فَما أُبالي … / لِأَنّي ما اِنتَفَعتُ … | Smoke rising from spent charcoal: the fire is out | [Mixkit 3452](https://mixkit.co/free-stock-video/smoke-coming-out-of-charcoal-3452/) · Free |
| E8 | 24.3–27.7 | رَماني الدَهرُ بِالأَرزاءِ حَتّى | A coal fire flaring, sparks streaming off the embers; a burst on «رَماني» | [Mixkit 3459](https://mixkit.co/free-stock-video/intense-fire-burning-coal-3459/) · Free |
| E9 | 28.0–30.35 | فُؤادي في غِشاءٍ مِن نِبالِ | A glowing core inside a jagged black crust | [Mixkit 3462](https://mixkit.co/free-stock-video/flame-burning-coal-in-detail-3462/) · Free |
| E10 | 30.35–35.1 | فَصِرتُ إِذا أَصابَتني سِهامٌ / تَكَسَّرَتِ النِصالُ عَلى … | Hammer on hot steel. The last strike (34.93 s) falls on «النِصالِ» (34.97 s), and the picture cuts to black | Commons (as E3) · CC BY 3.0 |
| End | 35.0–41.4 | النِصالِ | The last word arrives on its own, as it is spoken. It flares white-hot on the strike, cools through orange and red, then the credits follow | — |

E3 and E10 use two different, non-overlapping moments of one real take, and QC checks that no moment of footage is reused.

### What the independent review changed
- **The opening:** it now hooks. The reel opens bright on glowing coals, and the voice enters at 1.3 s instead of after nearly 2 s of black. This was the one finding confirmed by both verifiers.
- **The last word:** it lands as it is spoken, the way the reference's «سحر» does. The final word is held back from the line, and the hammer strike cuts to black. The word itself becomes the white-hot iron.
- **The sparks:** sparks on a black background read as a stock effect. They are replaced by a real coal fire whose sparks visibly come off the embers.
- **One night world:**
  - The sunlit horse is regraded to low firelight.
  - The cold smoke is warmed, with its blacks set at true black.
  - The same push-in is no longer used on every shot. Enlarged and moving shots hold still; a 3 % push is kept only on the static close-ups.
- **Legibility:**
  - Verse text is 72 px (was 62).
  - The dark band under the text is stronger over the forge and the flames, and lighter over dark shots.
  - Each verse clears at the picture change.
  - The CC BY attribution is readable and held on screen.
- **Not adopted:**
  - Rebuilding the whole reel around a single forge take. The other forge clips found on Commons are only 480p, and a full search of the Smithy series could not be completed because Commons kept rate-limiting this network.
  - A hand or human gesture, which one of the two verifiers rejected as a matter of taste. Your reference's own hand appears for only about 1.4 s.

## Companion reel: verse 6 only
`Nisal-ala-Nisal_Ember_verse6_9x16.mp4` (about 11 s) is the format closest to the reference: one verse, one object, one action, and one glowing word landing on the strike.

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
