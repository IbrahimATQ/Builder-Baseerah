# QC report — «النِصالُ عَلى النِصالِ»

Automated checks: `pipeline/qc_film.py` (results JSON kept with the project); visual checks: contact sheets
and per-hemistich stills reviewed frame by frame.

## Summary

| Edition | File | Automated checks |
|---|---|---|
| Master 16:9, 2.39:1 scope | `output/Nisal-ala-Nisal_16x9_scope.mp4` | 14/16 pass; 2 reviewed exceptions (below) |
| Vertical 9:16 | `output/Nisal-ala-Nisal_9x16_vertical.mp4` | 14/16 pass; same 2 exceptions |
| Share encode 16:9 | `output/Nisal-ala-Nisal_16x9_scope_share.mp4` | Re-encode of the master (CRF 22) |

## Arabic text
- All 12 hemistichs are **identical (Unicode) to the truth table**: five verses copied from your text, and «وَهانَ…» from the canonical diwan (aldiwan.net poem 9758, verse 7).
- The text is NFC-normalised, and every hemistich carries its harakat (counts per [sadr, ajuz]: {'v1': [11, 6], 'v2': [12, 9], 'v3': [11, 8], 'v4': [6, 10], 'v5': [8, 6], 'v6': [8, 11]}).
- The two supplied but unrecited verses are not displayed.
- Right-to-left order is correct: the sadr sits to the right of the ajuz. Amiri shaping and mark stacking were checked on a still of every hemistich.
- Each hemistich appears 0.12 s before its aligned onset (12 cues; error 0.00 s). Verses never overlap on screen.
- The SRT sidecar has 12 non-overlapping cues; all 18 Arabic lines match the truth table exactly and contain no control characters.

## Audio
- Integrated loudness -14.14 LUFS; true peak -0.9 dBTP; **0 clipped samples**.
- **Voice preserved and in sync:** the film audio correlates 0.982 with the isolated voice at lag 0.0 ms. The voice is unprocessed apart from a 45 Hz high-pass and gain.
- Voice over music during words: 12–18 dB in every hemistich, and 34 dB in Act IV, by design.
- Music automation is smooth: after the first note, the music bus never moves more than 5.9 dB per 0.4 s.
- Background music removed. In the original's music-only outro, the isolated voice measures −240 dB (digital silence). In pauses it is 5–19 dB below the original. Whisper finds no speech in the removed music.

## Picture
- 14 shots, one metaphor per hemistich. Cuts fall only in the pauses between hemistichs. No source clip is reused.
- Modern footage is deliberate in three shots (clock, Grand Central, train). Grand Central's kiosk signage («Information», «Arrivals») and a small MTA logo stay visible in S2 as documentary context (no product branding). Unintended modern intrusions were cropped out of the others: solar panels (dune), a painted stencil (anvil) and a flag (Alhambra).
- Colour: graded per act. Output is tagged BT.709 limited range. Black level inside the picture (Y≈15) matches the matte (Y=16). Grain is applied only inside the picture, so text stays clean.

## Export
H.264 High@4.1, yuv420p, 30 fps, AAC-LC 317 kb/s 48 kHz, `+faststart`, no watermark. Video bitrate: master 24557 kb/s, vertical 20302 kb/s, share encode 4971 kb/s.

## Reviewed exceptions (flagged by the automated checks and kept deliberately)
1. **"Black segment" at 12.07–12.90 s.** This is the dying candle in Act II («بِلا قِتالِ»). The flame is still visible (peak luma 150–227; thousands of lit pixels per frame). It is dark by design.
2. **"Loudness jump > 12 dB."** These jumps occur at speech onsets after pauses: the first verse after the prologue (+18 dB at 4.4 s), and words at 6.86 s and 13.63 s. That is the reciter's natural dynamics, not automation. The music bus itself never jumps more than 5.9 dB.

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
| S7 | 3977 | Mixkit videoFree (verified on item page) |
| S8 | 28890 | Mixkit videoFree (verified on item page) |
| S9 | 4423 | Mixkit videoFree (verified on item page) |
| S10 | 4426 | Mixkit videoFree (verified on item page) |
| S11 | 1081 | Mixkit videoFree (verified on item page) |
| S12 | 4013 | Mixkit videoFree (verified on item page) |
| C1 | 4149 | Mixkit videoFree (verified on item page) |

Seven earlier picks were **replaced** after their item pages showed Mixkit's *Restricted* licence (personal use only; "never… in a film").

## Not verifiable by me
- **Listening by ear.** All audio judgements come from measurements. Please listen once on headphones.
- **How each social platform re-encodes the upload.**
