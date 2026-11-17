#!/usr/bin/env python3
"""Mix the isolated recitation with the score and ambience, then master.

* The voice is never processed beyond a 45 Hz rumble filter (done upstream) and gain.
* Music is ducked with a smooth envelope derived from the forced-alignment WORD timings
  (fast attack before each word, slow release after), so it breathes in the pauses.
* A wide static presence dip (2.8 kHz) on the music bus leaves room for consonants.
* Master: two-pass EBU R128 loudness normalisation (linear) to -14 LUFS, -1 dBTP.

Usage: python mix_master.py timing.json voice.wav score.wav ambience.wav OUT_DIR
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy.ndimage import uniform_filter1d
from scipy.signal import lfilter

SR = 48000


def peaking(x: np.ndarray, f0: float, gain_db: float, q: float) -> np.ndarray:
    a = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * f0 / SR
    alpha = np.sin(w0) / (2 * q)
    b = [1 + alpha * a, -2 * np.cos(w0), 1 - alpha * a]
    den = [1 + alpha / a, -2 * np.cos(w0), 1 - alpha / a]
    return lfilter(np.array(b) / den[0], np.array(den) / den[0], x, axis=0).astype(np.float32)


def duck_envelope(n: int, words: list[dict], depth_db: float, attack: float, release: float) -> np.ndarray:
    """1.0 = no ducking; 10^(depth/20) inside words. Asymmetric smoothing: drops `attack`
    seconds before a word, recovers over `release` seconds after it."""
    target = np.zeros(n, dtype=np.float32)
    for w in words:
        s = max(0, int((w["film_start"] - attack) * SR))
        e = min(n, int((w["film_end"] + 0.05) * SR))
        target[s:e] = 1.0
    # release: extend each active region with a decaying tail
    hop = 240  # 5 ms control rate
    ctrl = target[::hop]
    out = np.zeros_like(ctrl)
    rel = np.exp(-hop / (release * SR))
    att = np.exp(-hop / (0.04 * SR))
    v = 0.0
    for i, c in enumerate(ctrl):
        coef = att if c > v else rel
        v = c + (v - c) * coef
        out[i] = v
    env_db = out * depth_db
    gain = 10 ** (env_db / 20)
    return np.repeat(gain, hop)[:n]


def _gain(target_lufs: float, measured: float) -> float:
    """Linear gain to reach a loudness target; silent input (-inf LUFS) stays silent."""
    return float(10 ** ((target_lufs - measured) / 20)) if np.isfinite(measured) else 0.0


def load_stereo_48k(path: str, min_len: int) -> np.ndarray:
    """Read any WAV as float32 stereo at 48 kHz, zero-padded to at least `min_len` samples."""
    from fractions import Fraction

    from scipy.signal import resample_poly

    x, sr = sf.read(path, dtype="float32", always_2d=True)
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    x = x[:, :2]
    if sr != SR:
        f = Fraction(SR, sr).limit_denominator(1000)
        x = resample_poly(x, f.numerator, f.denominator, axis=0).astype(np.float32)
    if len(x) < min_len:
        x = np.concatenate([x, np.zeros((min_len - len(x), 2), np.float32)])
    return x


def main(timing_p: str, voice_p: str, score_p: str, amb_p: str, out_dir: str) -> None:
    timing = json.load(open(timing_p, encoding="utf-8"))
    T = timing["duration"]
    n = int(T * SR)
    voice, score, amb = (load_stereo_48k(p, n) for p in (voice_p, score_p, amb_p))

    vbus = np.zeros((n, 2), np.float32)
    s = int(timing["voice_film_start"] * SR)
    voice = voice[: n - s]
    vbus[s : s + len(voice)] = voice

    meter = pyln.Meter(SR)
    v_lufs = meter.integrated_loudness(vbus[s : s + len(voice)])
    vbus *= _gain(-16.0, v_lufs)  # voice integrated loudness -16 LUFS before mastering

    music = peaking(score[:n], 2800, -3.5, 0.8)
    m_lufs = meter.integrated_loudness(music)
    music *= _gain(-25.0, m_lufs)  # music bed sits ~9 LU under the voice on average
    duck = duck_envelope(n, timing["words"], depth_db=-7.0, attack=0.12, release=0.45)
    music *= duck[:, None]
    # Section automation (dB): the prologue bed carries the opening alone, then hands over to the voice.
    vs = timing["voice_film_start"]
    pts_t = [0.0, vs - 0.7, vs - 0.1, T]
    pts_db = [6.0, 6.0, 0.0, 0.0]
    auto = 10 ** (np.interp(np.arange(n) / SR, pts_t, pts_db) / 20)
    music *= auto[:, None].astype(np.float32)

    a_lufs = meter.integrated_loudness(amb[:n])
    ambience = amb[:n] * _gain(-38.0, a_lufs)

    mix = vbus + music + ambience
    os.makedirs(out_dir, exist_ok=True)
    pre = os.path.join(out_dir, "mix_premaster.wav")
    sf.write(pre, mix, SR, subtype="FLOAT")
    sf.write(os.path.join(out_dir, "music_ducked.wav"), music, SR, subtype="FLOAT")
    sf.write(os.path.join(out_dir, "voice_bus.wav"), vbus, SR, subtype="FLOAT")

    # Two-pass loudnorm (linear) to -14 LUFS / -1 dBTP.
    p1 = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", pre, "-af", "loudnorm=I=-14:TP=-1.0:LRA=11:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True,
    ).stderr
    js = json.loads(p1[p1.rindex("{") : p1.rindex("}") + 1])
    af = (
        f"loudnorm=I=-14:TP=-1.0:LRA=11:measured_I={js['input_i']}:measured_TP={js['input_tp']}:"
        f"measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:offset={js['target_offset']}:linear=true,"
        "aresample=48000"
    )
    master = os.path.join(out_dir, "mix_master.wav")
    subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-y", "-i", pre, "-af", af, "-c:a", "pcm_s24le", master], check=True)
    y, _ = sf.read(master, always_2d=True)
    report = {
        "voice_lufs_raw": round(float(v_lufs), 2),
        "music_lufs_raw": round(float(m_lufs), 2),
        "premaster_measure": js,
        "master_integrated_lufs": round(float(meter.integrated_loudness(y)), 2),
        "master_sample_peak_dbfs": round(float(20 * np.log10(np.max(np.abs(y)) + 1e-12)), 2),
        "duck_min_db": round(float(20 * np.log10(duck.min())), 2),
    }
    json.dump(report, open(os.path.join(out_dir, "mix_report.json"), "w"), indent=1)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:6])
