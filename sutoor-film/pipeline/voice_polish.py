#!/usr/bin/env python3
"""Make a separated recitation voice sound natural and present (fixes a thin, 'tunnel' sound).

Measured problem (this recording, after separation): 4-8 kHz sat 10-14 dB above normal speech while
250 Hz and 1-2 kHz were relatively low -> thin, hollow, phone-like. Chain (ffmpeg):
  high-pass 70 Hz -> +2 dB body at 250 Hz -> +2 dB presence at 1.2 kHz -> -5 dB high shelf from
  4.2 kHz and -2.5 dB at 7 kHz -> de-esser -> gentle 2:1 compression -> loudness-matched output.
Then a short, soft room (synthetic diffuse impulse response, RT60 ~0.5 s) is blended at -20 dB so
the voice sits in a space instead of feeling cut out. The words, timing and pitch are not changed.

Usage: python voice_polish.py IN.wav OUT.wav [--room-db -20] [--report OUT.json]
"""
from __future__ import annotations

import json
import subprocess
import sys

import numpy as np
import soundfile as sf
from scipy.signal import fftconvolve

SR = 48000
CHAIN = ("highpass=f=70:poles=2,"
         "equalizer=f=120:t=q:w=1.0:g=-2,"
         "equalizer=f=250:t=q:w=1.0:g=2,"
         "equalizer=f=1200:t=q:w=1.1:g=2,"
         "highshelf=f=4200:g=-5:t=q:w=0.7,"
         "equalizer=f=7000:t=q:w=1.5:g=-2.5,"
         "deesser=i=0.35:m=0.5:f=0.5:s=o,"
         "acompressor=threshold=-22dB:ratio=2:attack=10:release=140:makeup=2")


def octave_bands(y: np.ndarray, sr: int) -> list[float]:
    import librosa
    S = np.abs(librosa.stft(y, n_fft=4096, hop_length=1024)) ** 2
    fr = librosa.fft_frequencies(sr=sr, n_fft=4096)
    e = S.mean(axis=1)
    loud = S.sum(axis=0) > np.percentile(S.sum(axis=0), 60)  # speech frames
    e = S[:, loud].mean(axis=1)
    out = []
    for c in (63, 125, 250, 500, 1000, 2000, 4000, 8000):
        m = (fr >= c / np.sqrt(2)) & (fr < c * np.sqrt(2))
        out.append(10 * np.log10(e[m].sum() + 1e-12))
    out = np.array(out)
    return [round(float(x), 1) for x in out - out.max()]


def room_ir(rng: np.random.Generator, rt60: float = 0.5) -> np.ndarray:
    n = int(SR * rt60 * 1.2)
    t = np.arange(n) / SR
    env = np.exp(-6.9 * t / rt60)
    ir = rng.normal(0, 1, (n, 2)) * env[:, None]
    # darker tail: simple one-pole low-pass per channel
    for c in range(2):
        for i in range(1, n):
            ir[i, c] = 0.6 * ir[i, c] + 0.4 * ir[i - 1, c]
    ir[: int(0.012 * SR)] = 0  # 12 ms pre-delay
    return (ir / np.sqrt((ir ** 2).sum(axis=0, keepdims=True))).astype(np.float32)


def main() -> None:
    args = sys.argv[1:]
    room_db, report = -20.0, None
    if "--room-db" in args:
        i = args.index("--room-db"); room_db = float(args[i + 1]); del args[i:i + 2]
    if "--report" in args:
        i = args.index("--report"); report = args[i + 1]; del args[i:i + 2]
    src, dst = args
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-af", f"aresample={SR}," + CHAIN, "-ac", "2", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    y = np.frombuffer(raw, np.float32).reshape(-1, 2).copy()
    ir = room_ir(np.random.default_rng(5))
    wet = np.stack([fftconvolve(y[:, c], ir[:, c])[: len(y)] for c in range(2)], axis=1).astype(np.float32)
    out = y + wet * (10 ** (room_db / 20))
    x0, sr0 = sf.read(src, always_2d=True)
    peak = np.abs(out).max()
    if peak > 0.89:
        out *= 0.89 / peak
    sf.write(dst, out, SR, subtype="FLOAT")
    rep = {"chain": CHAIN, "room_db": room_db,
           "bands_before": octave_bands(x0.mean(axis=1).astype(np.float32), sr0),
           "bands_after": octave_bands(out.mean(axis=1), SR)}
    if report:
        json.dump(rep, open(report, "w"), indent=1)
    print(json.dumps(rep))


if __name__ == "__main__":
    main()
