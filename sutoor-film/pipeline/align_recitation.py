#!/usr/bin/env python3
"""Transcribe (faster-whisper) and force-align (torchaudio MMS_FA) a known Arabic text.

1. Whisper large-v3 transcribes the isolated voice independently. This is a check that the
   recited words match the text we intend to subtitle; Whisper never outputs diacritics.
2. MMS_FA (wav2vec2, multilingual, uroman romanisation) force-aligns the exact known text,
   giving per-word start/end times that drive subtitle timing and music ducking.

Usage: python align_recitation.py VOICE.wav poem.json OUT.json
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata

import numpy as np
import soundfile as sf
import torch
import torchaudio
import torchaudio.functional as AF

ARABIC_DIACRITICS = re.compile(r"[ً-ْٰـ]")


def strip_diacritics(s: str) -> str:
    return ARABIC_DIACRITICS.sub("", s)


def load_mono16k(path: str) -> torch.Tensor:
    data, sr = sf.read(path, dtype="float32", always_2d=True)
    wav = torch.from_numpy(data.mean(axis=1)).unsqueeze(0)
    if sr != 16000:
        wav = torchaudio.functional.resample(wav, sr, 16000)
    return wav


def whisper_transcribe(path: str) -> dict:
    from faster_whisper import WhisperModel

    model = WhisperModel("large-v3", device="cpu", compute_type="int8", cpu_threads=4)
    audio = load_mono16k(path).squeeze(0).numpy()  # pass samples: avoids PyAV API drift in decode_audio
    segments, info = model.transcribe(
        audio, language="ar", word_timestamps=True, beam_size=5, vad_filter=False,
        condition_on_previous_text=False,
    )
    out = {"language_prob": info.language_probability, "segments": []}
    for seg in segments:
        out["segments"].append(
            {
                "start": round(seg.start, 3),
                "end": round(seg.end, 3),
                "text": seg.text.strip(),
                "words": [
                    {"w": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3), "p": round(w.probability, 3)}
                    for w in (seg.words or [])
                ],
            }
        )
    return out


def mms_align(wav: torch.Tensor, words: list[str]) -> list[dict]:
    import uroman as ur

    bundle = torchaudio.pipelines.MMS_FA
    model = bundle.get_model(with_star=False)
    labels = bundle.get_labels(star=None)
    dictionary = {c: i for i, c in enumerate(labels)}
    uro = ur.Uroman()

    def romanize(word: str) -> str:
        r = uro.romanize_string(strip_diacritics(word)).lower()
        r = unicodedata.normalize("NFKD", r)
        return "".join(c for c in r if c in dictionary and c != "-")

    roman = [romanize(w) for w in words]
    keep = [i for i, r in enumerate(roman) if r]
    tokens = [dictionary[c] for i in keep for c in roman[i]]
    with torch.inference_mode():
        emission, _ = model(wav)
    targets = torch.tensor([tokens], dtype=torch.int32)
    aligned, scores = AF.forced_align(emission, targets, blank=0)
    aligned, scores = aligned[0], scores[0].exp()
    spans = AF.merge_tokens(aligned, scores)
    ratio = wav.shape[1] / emission.shape[1] / 16000  # seconds per frame
    out, k = [], 0
    for idx in keep:
        n = len(roman[idx])
        sp = spans[k : k + n]
        k += n
        out.append(
            {
                "index": idx,
                "word": words[idx],
                "roman": roman[idx],
                "start": round(sp[0].start * ratio, 3),
                "end": round(sp[-1].end * ratio, 3),
                "score": round(float(np.mean([s.score for s in sp])), 3),
            }
        )
    return out


def main(voice: str, poem_path: str, out_path: str) -> None:
    poem = json.load(open(poem_path, encoding="utf-8"))
    lines = [("intro", poem["intro_spoken"])]
    for v in poem["verses"]:
        lines += [(f"v{v['n']}a", v["sadr"]), (f"v{v['n']}b", v["ajuz"])]
    words, owner = [], []
    for key, text in lines:
        for w in text.split():
            words.append(w)
            owner.append(key)

    wav = load_mono16k(voice)
    print("aligning", len(words), "words ...", file=sys.stderr)
    aligned = mms_align(wav, words)
    for a in aligned:  # words whose romanisation is empty are skipped by mms_align; map by index
        a["line"] = owner[a["index"]]
    by_line = {}
    for a in aligned:
        by_line.setdefault(a["line"], []).append(a)
    line_times = {
        k: {"start": v[0]["start"], "end": v[-1]["end"], "text": " ".join(x["word"] for x in v)} for k, v in by_line.items()
    }
    json.dump({"words": aligned, "lines": line_times}, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for k, v in line_times.items():
        print(f"{k:6s} {v['start']:6.2f} -> {v['end']:6.2f}  {v['text']}", file=sys.stderr)
    print("transcribing with whisper large-v3 ...", file=sys.stderr)
    asr = whisper_transcribe(voice)
    json.dump(
        {"words": aligned, "lines": line_times, "whisper": asr},
        open(out_path, "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=1,
    )
    for k, v in line_times.items():
        print(f"{k:6s} {v['start']:6.2f} -> {v['end']:6.2f}  {v['text']}")
    print("--- whisper ---")
    for s in asr["segments"]:
        print(f"{s['start']:6.2f} -> {s['end']:6.2f}  {s['text']}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
