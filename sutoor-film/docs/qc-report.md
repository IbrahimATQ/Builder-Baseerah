# QC report — «النِصالُ عَلى النِصالِ»

Automated checks: `pipeline/qc_film.py` (19–20 checks depending on edition; results JSON kept with the project). Visual checks: contact sheets
and per-hemistich stills reviewed frame by frame, plus an independent review panel. Every shot was rated by a
separate reviewer for "does this look really filmed?", and each flagged shot was re-examined by three skeptics
(forensic, ordinary-viewer, devil's-advocate).

## Summary

All editions use the **calmer pacing**. The recitation is re-paced (0.92×, pitch preserved, pauses opened to at least 0.6 s and 1.15 s; see `docs/ember-edition.md`), and the montage edit, score and mix were re-timed to match. The QC below refers to the re-paced editions.

| Edition | File | Length | Automated checks |
|---|---|---|---|
| Master 16:9, 2.39:1 scope | `output/Nisal-ala-Nisal_16x9_scope.mp4` | 46.9 s | 17/19 pass; 2 reviewed exceptions (below) |
| Vertical 9:16 | `output/Nisal-ala-Nisal_9x16_vertical.mp4` | 46.9 s | 17/19 pass; same 2 exceptions |
| Share encode 16:9 | `output/Nisal-ala-Nisal_16x9_scope_share.mp4` | 46.9 s | Re-encode of the master (CRF 22) |
| **Ember reel 9:16** (reference-inspired) | `output/Nisal-ala-Nisal_Ember_9x16.mp4` | 41.4 s | 19/20 pass; 1 reviewed exception (speech onsets after pauses) |
| Ember, verse 6 only | `output/Nisal-ala-Nisal_Ember_verse6_9x16.mp4` | 11.1 s | Excerpt of the Ember reel; flash check pass (2.4 %), −14.9 LUFS |

Ember reel, specifically:
- **Text:** all 49 words are revealed at their own aligned onsets. The word tokens rebuild every hemistich exactly, and the closing glowing word is identical to the poem's last word.
- **Audio:** voice correlation 0.966 at 0.0 ms; -14.22 LUFS.
- **Flashing:** worst window 2.6 % of the screen (limit 11 %).
- **Dark by design:** the candle stretch (10.8–13.0 s) is listed as intended black. The flame stays visible (peak luma 234) until it dies at 12.3 s.

## Arabic text
- All 12 hemistichs are **identical (Unicode) to the truth table**: five verses copied from your text, and «وَهانَ…» from the canonical diwan (aldiwan.net poem 9758, verse 7).
- The text is NFC-normalised, and every hemistich carries its harakat (counts per [sadr, ajuz]: {'v1': [11, 6], 'v2': [12, 9], 'v3': [11, 8], 'v4': [6, 10], 'v5': [8, 6], 'v6': [8, 11]}).
- The two supplied but unrecited verses are not displayed.
- Right-to-left order is correct: the sadr sits to the right of the ajuz. Amiri shaping and mark stacking were checked on a still of every hemistich.
- Each hemistich appears 0.12 s before its aligned onset (12 cues; error 0.00 s). Verses never overlap on screen.
- The SRT sidecar has 12 non-overlapping cues; all 18 Arabic lines match the truth table exactly and contain no control characters.

## Audio
- Integrated loudness -14.3 LUFS; true peak -0.9 dBTP; **0 clipped samples**.
- **Voice preserved and in sync:** the film audio correlates 0.962 with the re-paced isolated voice at lag 0.0 ms. Beyond the pacing change (a 0.92× pitch-preserving stretch, plus silence inserted at the quietest point of each gap), the voice gets only a 45 Hz high-pass and gain. A fresh forced alignment of the re-paced voice matches the remapped word times (median error 7 ms, 90th percentile 16 ms).
- Voice over music during words: 12–18 dB in every hemistich, and 34 dB in Act IV, by design.
- Music automation is smooth: after the first note, the music bus never moves more than 5.9 dB per 0.4 s.
- Background music removed. In the original's music-only outro, the isolated voice measures −240 dB (digital silence). In pauses it is 5–19 dB below the original. Whisper finds no speech in the removed music.

## Picture
- 14 shots, one metaphor per hemistich. Cuts fall only in the pauses between hemistichs. No source clip is reused.
- Modern footage is deliberate in three shots (clock, Grand Central, train). Grand Central's kiosk signage («Information», «Arrivals») and a small MTA logo stay visible in S2 as documentary context (no product branding). Unintended modern intrusions were cropped out of the others: solar panels (dune), a painted stencil (anvil) and a flag (Alhambra).
- Colour: graded per act. Output is tagged BT.709 limited range. Black level inside the picture (Y≈15) matches the matte (Y=16). Grain is applied only inside the picture, so text stays clean.

## Photosensitivity (flashing)
- The lightning shot (S9) originally had 10 single-frame strikes in 2.4 s, up to 5 within one second. The vertical edition marginally failed the general-flash rule (11.1 % of the screen flashing more than 3 times per second; limit 11 %).
- Fixed with `pipeline/flash_limit.py`: the strongest strikes are kept, at most 2 per second (5 kept, 7 replaced with the dark frame before them). The strike on «رَماني» is kept.
- `pipeline/flash_check.py` (QC check 17) now passes on both editions. The worst window is no longer the lightning but commuters in high-contrast clothing walking close to the camera in S2: 3.5 % of the screen (16:9) and 10.8 % (vertical). That is ordinary documentary motion, not flashing.
- After re-pacing, the longer train shot (S6) strobed as light broke through between carriages (34 % of the picture band in one 1 s window). A 3-frame motion blend (natural motion blur on a fast train) brings it to 4.7 %. Both montage editions pass.
- Ember reel: the first forge moment flagged 17 % of the screen (arm, hammer and trousers swinging through a tight portrait crop). It was replaced by a calmer moment of the same take (0.5–1.0 %). A smoke shot that curled into a face-like shape was replaced. The reel passes at 2.6 %.
- This is an automated screen modelled on WCAG 2.3.1 / Harding general-flash rules (red-flash and spatial-pattern rules not evaluated), not a certified Harding test.

## Shot review (independent panel)
- All 14 shots were judged real filmed footage. None was rated AI-generated after verification.
- Acted on: S10's spark particles read as CGI and were replaced by a real coal fire. S7's curtain could not be read and was replaced by rain on a window. S11's grade had clipped 51–66 % of the picture to black, which made the rocks look composited. It is now 0.6 %, the source's natural darkness is kept, and the shot plays at real speed instead of 0.7× frame-repeat slow motion.
- Also fixed: the candle flame ghosting on the horse's cheek and the sea spray over the Alhambra (now hard cuts); the title under the clock hands; vertical framing of the clock hub, the Alhambra towers and the dune; the prologue's sunburst cropped out of the 16:9.

## Export
H.264 High@4.1, yuv420p, 30 fps, AAC-LC 317 kb/s 48 kHz, `+faststart`, no watermark. Video bitrate: master 24095 kb/s, vertical 19613 kb/s, share encode 4627 kb/s, Ember reel about 9400 kb/s (1080×1920).

## Reviewed exceptions (flagged by the automated checks and kept deliberately)
1. **"Black segment" during the dying candle** («وَتَقتُلُنا المَنونُ بِلا قِتالِ»): the montage at 14.5–16.0 s, the Ember reel at 10.8–13.0 s. The flame stays visible until it dies (peak luma 153–234), and the verse stays on screen. It is dark by design: death without a battle.
2. **"Loudness jump > 12 dB per 0.4 s."** These jumps are the reciter's onsets after the newly opened pauses, worst at «رَماني» (montage 22.4 dB, Ember 21.4 dB). The music falls almost silent in Act IV (indifference) before time "strikes". Raising the ambience and fire beds, and level-matching the fire recordings, reduced these jumps (from 25–26 dB). The rest is the voice's natural attack, not automation.

## Footage licences (each verified on its own source page)
| Shot | Clip | Licence |
|---|---|---|
| P1 | 4113 | Mixkit videoFree (verified on item page) |
| S1 | 28893 | Mixkit videoFree (verified on item page) |
| S2 | 4180 | Mixkit videoFree (verified on item page) |
| S3 | wm_smithy_forging2 | CC BY 3.0 (credited) |
| S4 | 3458 | Mixkit videoFree (verified on item page) |
| S5 | 100645 | Mixkit videoFree (verified on item page) |
| S6 | 3025 | Mixkit videoFree (verified on item page) |
| S7 | 2846 | Mixkit videoFree (verified on item page) |
| S8 | 28890 | Mixkit videoFree (verified on item page) |
| S9 | 4423 | Mixkit videoFree (verified on item page) |
| S10 | 3459 | Mixkit videoFree (verified on item page) |
| S11 | 1081 | Mixkit videoFree (verified on item page) |
| S12 | 4013 | Mixkit videoFree (verified on item page) |
| C1 | 4149 | Mixkit videoFree (verified on item page) |

Seven earlier picks were **replaced** after their item pages showed Mixkit's *Restricted* licence (personal use only; "never… in a film").

## Not verifiable by me
- **Listening by ear.** All audio judgements come from measurements. Please listen once on headphones.
- **How each social platform re-encodes the upload.**
