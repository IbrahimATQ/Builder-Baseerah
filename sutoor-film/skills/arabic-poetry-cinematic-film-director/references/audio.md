# Audio: voice isolation, alignment, score, mix

## 1. Isolate the voice (CPU is fine for < 2 min)

```bash
pip install "audio-separator[cpu]" audioread standard-aifc standard-sunau
ffmpeg -i in.mp4 -vn -c:a pcm_s16le -ar 44100 orig.wav
audio-separator orig.wav -m vocals_mel_band_roformer.ckpt --output_format WAV   # ~1.5 min for 31 s on 4 vCPU
audio-separator orig.wav -m model_bs_roformer_ep_368_sdr_12.9628.ckpt --output_format WAV  # ~12 min, comparison
```
Model weights come from GitHub release assets and Hugging Face. If Hugging Face downloads hang
behind a proxy, `export HF_HUB_DISABLE_XET=1` (the Xet client uses a different host).

## 2. Prove the music is gone (no reference track exists)

Run `python scripts/separation_qc.py alignment.json OUTRO_START OUTRO_END name=vocals.wav,inst.wav ...`
and also:

| Check | Pass condition | Example (Mel-Band RoFormer, this project) |
|---|---|---|
| Vocal stem level in a music-only region (intro/outro) | ≥ 60 dB below speech | −240 dB (digital silence) vs speech −18 dB |
| Vocal stem level in real inter-verse pauses vs original | clearly lower than original | 5-19 dB lower |
| Whisper on the *removed* stem (VAD on) | no speech detected | "NO SPEECH DETECTED" |
| Spectrogram of pauses | no sustained horizontal partials that continue through the pause | voice-tail harmonics only |

Pauses that are not lower than the original usually contain voice (breath, elongated vowel) — keep them.
**Never gate or "fade down" pauses**: breaths and silences are part of the delivery.

## 3. Transcribe, then align the KNOWN text

- `faster-whisper` large-v3, `language="ar"`, `word_timestamps=True`; pass a 16 kHz NumPy array
  (PyAV API drift breaks path input). Whisper outputs no harakat and hallucinates credits
  ("ترجمة ...") over music-only tails — ignore text after the last aligned word.
- Use Whisper only to build the truth table (what is recited, in what order).
- Timing comes from `torchaudio.pipelines.MMS_FA` on the exact diacritised text, romanised by
  `uroman` (diacritics stripped for romanisation). Word scores < 0.4 mark unreliable boundaries.
- Ambiguous boundary (intro running into verse 1): candidate cuts at energy minima, re-transcribe
  from each; choose the earliest cut whose first word is the verse's first word.

## 4. Score

- Tonal centre = pYIN median of the voice (use `vf` voiced flags, not a probability threshold).
- Maqam palette on that tonic: Kurd (b2 sigh) for elegy; Hijaz (b2 + augmented 2nd) for wounds and
  climaxes; resolve on open fifths lit by Hijaz's major third for endurance.
- Place every cue relative to hemistich timings (prologue, per-act entries, a stroke on the key word).
- Verify each sample after pitch shifting: pYIN + strongest spectral peak + chroma must agree.
  Known VSCO-2 CE facts: Strings named one octave low; Timpani4 = E, Timpani1 roll = F#;
  `BKCtbss_Trem_E1` carries C#/C/A# partials (use sustain instead); low-velocity contrabass pizz smears.
- Chroma per act must show the intended pitch classes; plucked transients add ~25-30 % out-of-mode chroma (normal).

## 5. Mix and master

- Voice to −16 LUFS integrated before mastering; music bed ≈ −25 LUFS; ambience ≈ −38 LUFS.
- Duck music 7 dB with an envelope built from aligned WORD times (attack 0.12 s before the word,
  release 0.45 s); static −3.5 dB presence dip at 2.8 kHz on music.
- Section automation: lift the bed where the voice is absent (prologue +6 dB, coda).
- Two-pass `loudnorm` linear to −14 LUFS / −1 dBTP. Report: per-hemistich voice-minus-music dB
  (target 12-18 dB), integrated LUFS, true peak, LRA.
