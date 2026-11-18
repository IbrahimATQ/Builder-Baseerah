---
name: arabic-poetry-cinematic-film-director
description: Use when turning a recorded Arabic poetry recitation (qasida, classical or modern verse, audio or video) into a cinematic film or subtitled video, including isolating the reciter's voice from background music, syncing diacritized (tashkeel) verse subtitles, choosing Arabic typography, scoring with maqam-aware music, grading footage, or directing imagery for verses.
---

# ARABIC-POETRY-CINEMATIC-FILM-DIRECTOR

## Overview

The recorded recitation is the film's spine; every image, note and letter serves it.
Two rules carry most of the quality: **subtitle and score what is actually recited, at
hemistich resolution, from verified timings**, and **never alter the reciter's delivery**
(no regenerated voice, no gating of breaths, no re-timing of pauses).

## When to Use

- A user uploads a poetry recitation and asks for a "cinematic", "atmospheric" or "film" version
- Voice must be kept but background music removed or replaced
- Arabic subtitles with full harakat must be synchronised to speech
- Verse meaning must drive shot selection, grade, music and typography

Not for: Quran recitation (different textual and musical conventions, no instrumental scoring),
lyric videos of sung songs (melody, not prosody, drives timing).

## The Production Contract (deliver in this order)

1. **Text truth table** — for every verse: supplied? recited? canonical source checked? Recited order.
2. **Isolated voice** — WAV of the complete original recitation, plus QC numbers.
3. **Timing file** — word and hemistich start/end in source and film time, from forced alignment.
   Every subtitle file you hand over (draft or final) has this cue shape, two cues per verse:
   ```
   cue 2k-1  start = sadr_start - 0.12   end = ajuz_start - 0.12   text = sadr
   cue 2k    start = ajuz_start - 0.12   end = next_sadr_start - 0.12   text = sadr ⏎ ajuz
   ```
   Cues never overlap (each ends exactly where the next begins); the last verse holds ~1.5 s.
   Before alignment exists, take ajuz_start from the pause between the hemistichs (energy minimum)
   or the segment midpoint, and label the file DRAFT.
4. **Director's treatment** — per verse: meaning, emotional intensity 1-10, image metaphor, grade, music cue.
5. **Finished film** — rendered MP4, then the QC report (visual, audio, Arabic) with measured values.

If any item cannot be produced, say which and why; never substitute a plan for the film.

## Quick Reference

| Need | Use | Not |
|---|---|---|
| Voice/music separation (CPU) | `audio-separator` with Mel-Band RoFormer `vocals_mel_band_roformer.ckpt`; compare a 2nd model (BS-RoFormer) | Demucs alone; any "AI voice" re-synthesis |
| Removal check | Level of vocal stem in a music-only region; Whisper on the removed stem must find no speech | "Sounds clean" without measurement; gating pauses |
| Subtitle timing | MMS forced alignment (`torchaudio.pipelines.MMS_FA` + `uroman`) of the exact known text | Whisper segment timestamps (merge adjacent phrases, ±0.3-0.5 s) |
| Cut points (e.g. spoken intro → verse) | Energy minimum + Whisper re-transcription from each candidate cut | Guessing from segment boundaries |
| Diacritics of an unsupplied verse | Canonical diwan text (aldiwan via HF dataset `arbml/ashaar`), copied verbatim | Writing tashkeel from memory |
| Verse font | Amiri (classical Naskh, correct shadda+haraka stacking) | Markazi Text (detached shadda), Kufi display faces, system fonts |
| Title font | Aref Ruqaa (restrained calligraphic) | Ornate Thuluth at subtitle sizes |
| Renderer | Chromium/HarfBuzz (Remotion) or libass+HarfBuzz; verify a still of every verse | Platform caption tools (drop/misplace marks) |
| Music | Original score in the maqam on the reciter's pitch centre (pYIN median); CC0 samples (VSCO-2 CE) | Stock "Arabic" loops, vocal music, trailer drums |
| Loudness | Voice ≈12-18 dB over music during words; master −14 LUFS, −1 dBTP | Static music level; normalising the voice stem's dynamics flat |

Detailed method: [references/audio.md](references/audio.md), [references/text-and-typography.md](references/text-and-typography.md),
[references/direction.md](references/direction.md). Runnable tools: `python scripts/align_recitation.py`,
`python scripts/separation_qc.py`, `python scripts/flash_check.py`, `python scripts/flash_limit.py`, `python scripts/repace.py` (see headers for arguments).

## Workflow

1. **Inspect** the upload: `ffprobe`; contact sheet of frames; read any burned-in captions (they reveal the recited text and its order).
2. **Separate** voice with two strong models; keep the best by the measurements in references/audio.md.
3. **Truth table**: Whisper large-v3 on the isolated voice (pass a NumPy array, not a path, to faster-whisper) vs supplied text. Recitations often skip, add or reorder verses — follow the recording, report the differences, verify unsupplied verses against a canonical source.
4. **Align** the exact text with MMS_FA; probe ambiguous boundaries with Whisper re-transcription from candidate cuts.
5. **Direct**: emotional arc per verse → one image metaphor per hemistich (10-14 shots for ~30 s), palette evolving per act.
6. **Score** in the maqam keyed to the voice; verify every sample's pitch (libraries mislabel octaves; some samples are contaminated).
7. **Mix** with word-timed ducking; master; measure.
8. **Compose** (Remotion): picture, hemistich-timed subtitles, title, credits; render.
9. **QC** with numbers (references/direction.md checklist) before saying "done".

## Red Flags — stop and fix

| Thought | Reality |
|---|---|
| "Whisper's timestamps are close enough" | They merged the intro into verse 1 by 0.5 s in testing; align the known text instead. |
| "Show the whole bayt when the verse starts" | The ajuz then appears ~2 s before it is spoken. Reveal sadr, then ajuz, at their aligned starts. |
| "Silence the pauses to hide leftover music" | That deletes breaths and the reciter's pauses. Measure first; the new score masks low residue. |
| "I'll add the diacritics for the extra verse myself" | Copy them from a canonical diwan source and say which. |
| "The supplied text is the script" | The recording is the script. Never subtitle unrecited verses; never drop recited ones. |
| "The music is gone" (unmeasured) | Report the music-only-region level and the ASR check, or say it is unverified. |
| "Vertical because the source is vertical" | If footage is replaced by stock (often ≤1080p landscape), a 9:16 crop needs 1.8-2.7× upscale. Choose aspect from the actual source resolution. |
| "It's from a free stock site, so it's free to use" | Check each item's own licence. Mixkit serves two: `data-license="videoFree"` and `videoRestricted` (personal use only; never in a film, ads or monetised video). In one production 7 of 13 picks were Restricted. |
| "It's a beautiful, cinematic stock shot" | Glossy drone ruins and staged beauty shots read as AI-fake to viewers; in one production two such shots were rejected on sight. Prefer real documentary footage, and offer a contemporary layer (clock, station crowd, train) instead of ruling modern imagery out. |
| "Lightning on the word is powerful" | Ten strikes in 2.4 s failed the 3-flashes-per-second rule in the vertical edition. Screen every edition with scripts/flash_check.py; limit with scripts/flash_limit.py. |
| "Crush the blacks / slow it down for drama" | Crushed rock (60 % of pixels at black) and 0.7× slow motion by frame repetition made real footage look composited. Keep shadow detail; use real speed. |
| "He speaks too fast, so slow the whole voice down a lot" | Measure first. In one production the syllable rate was normal; the gaps between lines were 0.04-0.2 s. Open the pauses (>= 0.6 s within a verse, >= 1.15 s between verses) and stretch at most ~8 % with pitch preserved (scripts/repace.py); re-verify with forced alignment and Whisper. |
| "The samples are labelled, so the pitch is right" | Measure: VSCO strings are named an octave low; one timpani rolls on F#; a tremolo sample carries C#. |
| "A viewer hears a scream, so it must be a second voice in the recitation" | In one production it was a stock clip's own audio (a forge blower: a 2.5 s held tone near 2.6 kHz) used as sound effects. Check the effects and ambience, not only the voice: subtract the voice bus from the pre-master, run a vocal model on the rest, and scan the effects for held pitched tones > 0.8 s (scripts/scream_check.py). Never use a footage clip's own audio unheard. |
| "The isolated voice sounds like a tunnel, so EQ it" | Measure first. The causes were a 0.92x time-stretch (phasiness) and my own corrective EQ (-9.5 dB at 8 kHz). Keep the lead stem nearly untouched, within +/-2 dB of the original recording's long-term spectrum; open pauses instead of stretching; run a quiet real ambience bed under every word. |
| "A rendered paper burn on a rendered floor is fine" | Independent judges scored fully procedural burns 3-4/10. Composite only the paper (fibres, ink, char, curl, ember strokes) onto a REAL photographed plate, with real flame, smoke and spark plates (scripts in the Journey edition: paper_burn7). Make each burn a different object, ground, light, camera and fire grammar. |
| "Make the text interact with every shot" | Ten different text tricks read as captions pasted on a video. Use one system: a fixed zone, the same size, letters coloured by each shot's key light and modulated by its luminance (+/-15 %), one grain over picture and text. Then let the plate act on the words wherever it truly can, driven by measurement, not decoration: foam measured in the text band washes over them, a real impact (a step in a puddle, a drop) ripples them, they rack into focus with the shot, a candle's death dims them. With only 2-4 such moments reviewers still called it "subtitles on video". |
| "The fire reads the line right to left, so it can burn while he speaks" | A word burnt while it is being said cannot be read; the poem's title line was never readable whole. No flame may touch a word's ink before that word's end + 0.3 s: have the renderer report the first-burn time of every word (paper_burn7 meta `word_first_burn_s`) and check it. |
| "Arrow holes are just texture" | A hole on a letter's dot deletes the dot (the film's last word lost the dot of its nun) and a stray hole reads as a dot. Keep every wound clear of all ink, dots and harakat by its radius plus a margin, and log the clearance. |
| "A still frame under a simulated burn is fine" | A frozen plate (correlation 0.999) reads as a photograph. Use the live clip: stabilise a dolly with a moving crop locked on the surface the paper lies on, or re-time a real event (a wave's surge) to land on the beat. |
| "Quench it with a fade" | A fade is not water. Matte the plate's own surge over the sheet (luma key) and cool the ember where the water has been, thin strokes first. |
| "Insert silence at the quietest point between lines" | Where the reciter ran lines together that point is still voiced, so the line stops dead. Fade out over ~80 ms where it was still sounding, put the whole voice in one small room (RT60 ~0.6 s, -20 dB) so lines decay instead of hitting digital zero, and keep word times unchanged (pipeline/voice_edges.py). |
| "The music sits about 9 LU under the voice" (on average) | Measure per hemistich: margins swung 12-33 dB, burying the climax and leaving verse 4 alone over the sea. Hold music 14 dB under the voice in every line and everything else 12 dB under (pipeline/mix_journey.py); duck from the voice's own level with a 1.5 s hold, not from word times. |
| "One good flame clip, placed at every burning point" | Reviewers matched the same flame three times in one frame (template score 0.83) and saw its clip rectangle. Give every flame its own window, start frame, mirror, scale and lean from real flame plates, and an alpha from its own light feathered on all sides; a whole-sheet catch flame must rise only from the burning paper, its edges drawn by its own tongues. |
| "The paper reads well, so light it brightly" | A sheet at luma 138 on rock at 7, with no spill or contact, read as a title card pasted on video. Light paper and ground with the same source (moon on both), lift the ground until its texture shows, keep a soft contact shadow, let firelight fall on the ground, and turn and bow the sheet so it lies on the surface. |
| "Show the half-verse over the burn as well as on the paper" | Two type systems in one frame, and a burnt line returning clean as a recall, read as captions. One lettering system at a time: the overlay half-line fades as the burn shot begins, and a line that burnt never comes back. |
| "The dots are missing" (seen on a shrunken image) | Amiri's diamond dots sit tight against the strokes and vanish in thumbnails. Verify by rendering the word and a dotless spelling (ٮ for ن/ت/ب) and diffing; zoom crops 3x before claiming either way. |
| "One more round and the simulated burn will pass" | It did not, in three rounds: the client's reference was REAL phone footage of real calligraphy burning, and every simulation was called "purely AI generated, purely fake". When the reference is real footage, the answer is real footage: give the client a print sheet and a shooting guide (pipeline/make_burn_strips.cjs), cut their clips in, or drop the effect. Look for real footage of the exact thing first; a free "burning book" clip with Latin print does not carry Arabic verse. |
| "Isolate the voice and write a new score" (when the reel already had music) | The client asked for his sound back: "the voice ... without isolating the music". If the original mix is liked, it is the soundtrack: untouched, film time = recording time, with only recorded effects under it, at least 14 dB below the mix wherever a word is spoken. |
| "Keep the verses small and elegant, in one fixed zone" | Still "a video with a text in front of it". What read as designed: titles, not subtitles. 140-230 px in a 1080-wide frame, one or two words per row, the words split shot by shot (each word inside the shot it is spoken over, leaving with that shot), one gold image-word per line, fast runs of shots keeping one position. |
| "Letters behind things need depth estimation" | Luma is enough and far more robust on a night film: bright things on dark plates pass in front (flames, sparks, falling sand), dark things on bright plates do too (branches, a silhouette); ink mode sets a word on a bright surface (a clock dial) and lets it go dark with it. Keep a light floor (60 %) on letters lit by a shot that dies. |
| "Crop the drone shot to a 9:16 window" | A shot looking straight down has no up. Turn it 90 degrees: a 3840x2160 source fills 2160x3840 uncropped (full 4K, and a wide view the window never had). |
| "It looked fine in the half-size test" | Check 100 % crops at delivery size: a 1080p clip windowed to 608 px showed codec blocks at 4K and was replaced. And measure levels on the delivery encode: grain pushes a codec past a 16-235 clamp (clamp 18-232, accept EBU R103's 5-246). |
| "The cut is on the beat, the word is close enough" | Check it: a word may not appear before its own shot, and its block must stay until the word has been spoken (pipeline/qc_blades.py); two words failed this until the cuts moved to the words. |

## Common Mistakes

- Treating a spoken intro ("شوف فلسفة المتنبي يقول") as a verse, or cutting it mid-word: find the real boundary.
- Tight line-height clipping harakat; outlines/glow filling the counters of letters with marks.
- Letter-spacing Arabic (breaks joins); mixing fonts within a verse.
- One aggressive LUT for every shot; ignore the act-by-act palette.
- Literal illustration (a heart pierced by arrows) instead of metaphor (arrows dense in an old target; waves breaking on rock).
- Claiming "installed"/"operational"/"perfect" without a command output that shows it.
