#!/usr/bin/env python3
"""Finish the edges of a re-paced recitation so its pauses sound like breath, not edits.

repace.py opens the pauses by inserting silence at the quietest point between two lines. Where the
reciter ran one line straight into the next, that point is still voiced, so the line stops dead and
the next starts dead. This pass keeps every word exactly where it is (no time moves) and:
  * fades each line out over 80 ms where it was still sounding at the cut (30 ms where it was quiet),
    and fades the next line in over 25 ms (12 ms) instead of 8 ms
  * adds a small diffuse room (RT60 ~0.6 s, -20 dB, band-limited) to the whole voice, so every line
    decays into a space rather than into digital zero; the same room runs under the words, so it is
    one acoustic, not an effect on the ends
  * lays a very low room tone (about -70 dBFS) under the whole voice
  * optional gentle high shelf (to give back the air an earlier shelf took)
The inserted silences are found as runs of exact zeros, so the pass needs nothing but the file.

Usage: python voice_edges.py IN.wav OUT.wav [--shelf-db 2.0] [--wet-db -20] [--report OUT.json]
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import soundfile as sf
from scipy.signal import butter, fftconvolve, lfilter, sosfilt


def db(x: np.ndarray) -> float:
    return float(20 * np.log10(np.sqrt(np.mean(np.square(x))) + 1e-12))


def high_shelf(x: np.ndarray, sr: int, f0: float, g_db: float) -> np.ndarray:
    a = 10 ** (g_db / 40)
    w0 = 2 * np.pi * f0 / sr
    alpha = np.sin(w0) / 2 * np.sqrt(2)  # shelf slope S = 1
    cw = np.cos(w0)
    b = [a * ((a + 1) + (a - 1) * cw + 2 * np.sqrt(a) * alpha), -2 * a * ((a - 1) + (a + 1) * cw), a * ((a + 1) + (a - 1) * cw - 2 * np.sqrt(a) * alpha)]
    d = [(a + 1) - (a - 1) * cw + 2 * np.sqrt(a) * alpha, 2 * ((a - 1) - (a + 1) * cw), (a + 1) - (a - 1) * cw - 2 * np.sqrt(a) * alpha]
    return lfilter(np.array(b) / d[0], np.array(d) / d[0], x, axis=0)


def room_ir(sr: int, rt60: float = 0.6, pre_ms: float = 14.0, seed: int = 4) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(sr * rt60 * 1.3)
    t = np.arange(n) / sr
    env = np.exp(-6.91 * t / rt60) * (1 - np.exp(-t / 0.006))  # soft onset: no discrete slap
    ir = rng.standard_normal((n, 2)) * env[:, None]
    ir = sosfilt(butter(2, [220, 5200], btype="band", fs=sr, output="sos"), ir, axis=0)
    ir = np.concatenate([np.zeros((int(sr * pre_ms / 1000), 2)), ir])
    return (ir / np.sqrt(np.sum(ir ** 2, axis=0, keepdims=True))).astype(np.float32)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--shelf-db", type=float, default=2.0)
    ap.add_argument("--wet-db", type=float, default=-20.0)
    ap.add_argument("--report")
    a = ap.parse_args()
    x, sr = sf.read(a.inp, dtype="float64", always_2d=True)
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    mono = x.mean(axis=1)
    z = np.abs(x).max(axis=1) == 0
    d = np.diff(np.concatenate([[0], z.astype(int), [0]]))
    runs = [(s, e) for s, e in zip(np.where(d == 1)[0], np.where(d == -1)[0]) if (e - s) / sr > 0.05]
    voiced_end = runs[-1][0] if runs and runs[-1][1] >= len(x) - 1 else len(x)
    rep = {"cuts": []}

    def ref_peak(i0: int, i1: int) -> float:  # loudest 50 ms of the line around the cut
        seg = mono[max(0, i0):min(len(mono), i1)]
        h = int(0.05 * sr)
        return max((db(seg[k:k + h]) for k in range(0, max(1, len(seg) - h), h // 2)), default=-90.0)

    def fade(i0: int, n: int, out: bool) -> None:
        n = max(1, min(n, len(x)))
        w = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, n))
        if out:
            x[max(0, i0 - n):i0] *= w[::-1][-min(n, i0):, None]
        else:
            x[i0:i0 + n] *= w[: len(x[i0:i0 + n]), None]

    for s, e in runs:
        if e >= len(x) - 1:
            continue
        lvl_out = db(mono[s - int(0.03 * sr):s - int(0.008 * sr)]) - ref_peak(s - 2 * sr, s)
        lvl_in = db(mono[e + int(0.008 * sr):e + int(0.03 * sr)]) - ref_peak(e, e + 2 * sr)
        n_out = int((0.08 if lvl_out > -26 else 0.03) * sr)
        n_in = int((0.025 if lvl_in > -26 else 0.012) * sr)
        fade(s, n_out, True)
        fade(e, n_in, False)
        rep["cuts"].append({"at_s": round(s / sr, 3), "resume_s": round(e / sr, 3), "level_out_db": round(lvl_out, 1),
                            "level_in_db": round(lvl_in, 1), "fade_out_ms": round(1000 * n_out / sr), "fade_in_ms": round(1000 * n_in / sr)})
    fade(0, int(0.035 * sr), False)  # the first line
    fade(voiced_end, int(0.06 * sr), True)  # the last

    dry = x
    if abs(a.shelf_db) > 1e-3:
        dry = high_shelf(dry, sr, 6500.0, a.shelf_db)
    ir = room_ir(sr)
    wet = np.stack([fftconvolve(dry.mean(axis=1), ir[:, c])[: len(dry)] for c in range(2)], axis=1)
    act = np.abs(dry).max(axis=1) > 1e-4
    wet *= 10 ** ((db(dry[act]) + a.wet_db - db(wet[act])) / 20)
    y = dry + wet
    rng = np.random.default_rng(11)
    tone = rng.standard_normal((len(y) + 2, 2))
    tone = lfilter([1, -0.97], [1], tone, axis=0)[2:]  # a dark, pink-ish hiss
    tone = sosfilt(butter(2, 5000, fs=sr, output="sos"), tone, axis=0)
    tone *= 10 ** ((-70.0 - db(tone)) / 20)
    y = y + tone
    sf.write(a.out, y.astype(np.float32), sr, subtype="FLOAT")
    rep.update({"room_rt60_s": 0.6, "wet_db": a.wet_db, "shelf_db_6k5": a.shelf_db, "room_tone_dbfs": -70.0,
                "peak_dbfs": round(float(20 * np.log10(np.abs(y).max())), 2)})
    if a.report:
        json.dump(rep, open(a.report, "w"), indent=1)
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
