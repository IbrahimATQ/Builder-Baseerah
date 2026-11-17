#!/usr/bin/env python3
"""Reference-free QC of voice/music separation, using forced-alignment word timings.

Metrics per candidate vocal stem:
  speech_rms_db      level inside aligned words
  gap_rms_db         level in non-word regions between words (breaths + any leaked music)
  outro_rms_db       level in the music-only outro (pure leakage: should be ~silent)
  outro_rel_db       outro level relative to speech (lower = cleaner)
  tonal_gap_ratio    share of gap energy in stable tonal peaks (music-like) vs noise-like
  voice_in_inst_db   speech-band (300-3400 Hz) energy of the matching instrumental stem
                     inside words, relative to the vocal stem (lower = less voice lost)
Usage: python separation_qc.py alignment.json outro_start outro_end name=vocals.wav[,inst.wav] ...
"""
from __future__ import annotations

import json
import sys

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt, stft


def db(x: np.ndarray) -> float:
    return float(20 * np.log10(np.sqrt(np.mean(x**2)) + 1e-12))


def masks(n: int, sr: int, words: list[dict], t_end: float) -> tuple[np.ndarray, np.ndarray]:
    word = np.zeros(n, bool)
    for w in words:
        word[int(w["start"] * sr) : int(w["end"] * sr)] = True
    first, last = int(words[0]["start"] * sr), int(min(words[-1]["end"], t_end) * sr)
    gap = ~word
    gap[:first] = False
    gap[last:] = False
    return word, gap


def tonal_ratio(x: np.ndarray, sr: int) -> float:
    if len(x) < sr // 4:
        return float("nan")
    f, t, Z = stft(x, sr, nperseg=4096, noverlap=3072)
    P = np.abs(Z) ** 2
    med = np.median(P, axis=0, keepdims=True) + 1e-12
    peaks = P > 20 * med  # narrow spectral peaks that dominate the frame -> tonal (music-like)
    return float(np.sum(P * peaks) / (np.sum(P) + 1e-12))


def main() -> None:
    align = json.load(open(sys.argv[1], encoding="utf-8"))
    outro = (float(sys.argv[2]), float(sys.argv[3]))
    words = [w for w in align["words"]]
    rows = {}
    for spec in sys.argv[4:]:
        name, paths = spec.split("=", 1)
        vp, *ip = paths.split(",")
        v, sr = sf.read(vp, dtype="float32", always_2d=True)
        v = v.mean(1)
        word, gap = masks(len(v), sr, words, outro[0])
        r = {
            "speech_rms_db": db(v[word]),
            "gap_rms_db": db(v[gap]),
            "outro_rms_db": db(v[int(outro[0] * sr) : int(outro[1] * sr)]),
            "tonal_gap_ratio": tonal_ratio(v[gap], sr),
        }
        r["outro_rel_db"] = r["outro_rms_db"] - r["speech_rms_db"]
        r["gap_rel_db"] = r["gap_rms_db"] - r["speech_rms_db"]
        if ip:
            inst, _ = sf.read(ip[0], dtype="float32", always_2d=True)
            inst = inst.mean(1)[: len(v)]
            sos = butter(4, [300, 3400], btype="band", fs=sr, output="sos")
            r["voice_in_inst_db"] = db(sosfilt(sos, inst)[word[: len(inst)]]) - db(sosfilt(sos, v)[word])
        rows[name] = {k: round(val, 2) for k, val in r.items()}
    print(json.dumps(rows, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
