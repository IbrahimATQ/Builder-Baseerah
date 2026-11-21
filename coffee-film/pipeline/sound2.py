#!/usr/bin/env python3
"""Sound of the director's cut: score + sound design + the scene's own sound, mixed to the picture.

Spec (data/sound2.json):
  {"duration": s,
   "score": {"file": music.wav, "gain_db": 0, "stems": {"organ": [file, gain_db], ...} (optional, instead of file)},
   "beds":  [{"file", "src_in", "start", "end", "tempo": 0.8, "gain_db", "gain_keys": [[film s, dB], ...], "hp", "lp", "notch": [Hz],
              "fade_in", "fade_out", "rms_db"}],
   "cues":  [{"file", "src_in", "dur", "at", "gain_db", "fade_in", "fade_out", "hp", "lp", "pitch": semitones,
              "reverse": false, "rms_db": target RMS before gain (optional), "align": "end" (the sound ends at `at`), "gain_keys"}],
   "ticks": [{"file", "tick_in", "tock_in", "dur", "pre", "times": [...], "gain_db", "gain_keys": [[t, db], ...], "hp", "lp"}, ...]
            (one group per clock voice; ticks alternate tick/tock; `pre` = how far into the cut the transient sits),
   cue "reverb": {"rt60": s, "mix": 0..1, "predelay": s} puts a sound far away in a large space (synthetic hall),
   "ducks": [[t0, t1, db]]   (master-level dips of everything but the score, e.g. for a hard stop)
   "silence": [[t0, t1]]     (absolute silence windows: everything is cut, with 4 ms fades)}
Every sound is decoded with ffmpeg to 48 kHz stereo; tempo uses atempo (pitch kept), pitch uses resampling.
Masters: mix.wav (-14 LUFS, true peak <= -1.5 dBTP) and sfx_only.wav (everything but the score, -16 LUFS).
Usage: python sound2.py SPEC.json OUT_DIR
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy.ndimage import minimum_filter1d
from scipy.signal import resample_poly

SR = 48000


def decode(path: str, start: float = 0.0, dur: float | None = None, af: str | None = None) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{max(start, 0):.4f}"] + (["-t", f"{dur:.4f}"] if dur else []) + ["-i", path, "-vn"] + \
          (["-af", af] if af else []) + ["-ac", "2", "-ar", str(SR), "-f", "f32le", "-"]
    a = np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32)
    return a.reshape(-1, 2).astype(np.float64)


def rms_db(a: np.ndarray) -> float:
    return 20 * np.log10(np.sqrt(np.mean(a ** 2)) + 1e-12)


def env(n: int, fi: float, fo: float) -> np.ndarray:
    e = np.ones(n)
    a, b = min(n, int(fi * SR)), min(n, int(fo * SR))
    if a > 0:
        e[:a] = np.sin(np.linspace(0, np.pi / 2, a)) ** 2
    if b > 0:
        e[-b:] *= np.cos(np.linspace(0, np.pi / 2, b)) ** 2
    return e


def keyed(c: dict, at: float, n: int) -> np.ndarray:
    """A gain curve from `gain_keys` [[film s, dB], ...] (held flat outside the keys)."""
    if not c.get("gain_keys"):
        return np.ones(n)
    k = c["gain_keys"]
    t = at + np.arange(n) / SR
    return 10 ** (np.interp(t, [q[0] for q in k], [q[1] for q in k]) / 20)


def filters(c: dict) -> list[str]:
    f = []
    for hz in c.get("notch", []):
        f.append(f"bandreject=f={hz}:width_type=q:w=12")
    if c.get("hp"):
        f.append(f"highpass=f={c['hp']}")
    if c.get("lp"):
        f.append(f"lowpass=f={c['lp']}")
    return f


def reverb(a: np.ndarray, rt60: float, mix: float, predelay: float = 0.02, seed: int = 3) -> np.ndarray:
    """A synthetic hall: decorrelated exponentially decaying noise per channel, darker as it decays."""
    from scipy.signal import fftconvolve, butter, sosfilt
    rng = np.random.default_rng(seed)
    n = int(rt60 * 1.2 * SR)
    t = np.arange(n) / SR
    out = np.zeros((len(a) + n + int(predelay * SR), 2))
    for ch in range(2):
        ir = rng.standard_normal(n) * np.exp(-6.91 * t / rt60)
        ir = sosfilt(butter(2, 5000, "low", fs=SR, output="sos"), ir)
        ir /= np.sqrt(np.sum(ir ** 2)) + 1e-12
        wet = fftconvolve(a[:, ch], ir)
        d = int(predelay * SR)
        out[d:d + len(wet), ch] += wet * mix
        out[:len(a), ch] += a[:, ch] * (1 - mix)
    return out


def place(bus: np.ndarray, a: np.ndarray, at: float) -> None:
    i0 = int(round(at * SR))
    if i0 >= len(bus):
        return
    if i0 < 0:
        a, i0 = a[-i0:], 0
    n = min(len(a), len(bus) - i0)
    bus[i0:i0 + n] += a[:n]


def true_peak_db(a: np.ndarray) -> float:
    return 20 * np.log10(np.max(np.abs(resample_poly(a, 4, 1, axis=0))) + 1e-12)


def limit(a: np.ndarray, ceiling_db: float) -> np.ndarray:
    c = 10 ** (ceiling_db / 20)
    up = np.max(np.abs(resample_poly(a, 4, 1, axis=0)), axis=1).reshape(-1, 4).max(axis=1)[: len(a)]
    need = np.minimum(1.0, c / np.maximum(up, 1e-9))
    if need.min() >= 1.0:
        return a
    w = int(0.004 * SR)
    g = minimum_filter1d(need, size=2 * w + 1, mode="nearest")
    k = np.hanning(2 * w + 1); k /= k.sum()
    g = np.minimum(np.convolve(g, k, mode="same"), need)
    return a * g[:, None]


def main() -> None:
    spec_p, out = sys.argv[1:3]
    os.makedirs(out, exist_ok=True)
    sp = json.load(open(spec_p, encoding="utf-8"))
    N = int(round(sp["duration"] * SR))
    fx = np.zeros((N, 2))
    report = {"beds": [], "cues": []}
    for b in sp.get("beds", []):
        dur = b["end"] - b["start"]
        af = [f"atempo={b['tempo']}"] if abs(b.get("tempo", 1.0) - 1) > 1e-3 else []
        a = decode(b["file"], b.get("src_in", 0.0), dur * b.get("tempo", 1.0) + 0.3, ",".join(af + filters(b)) or None)[: int(dur * SR)]
        if "rms_db" in b:
            a *= 10 ** ((b["rms_db"] - rms_db(a)) / 20)
        a *= 10 ** (b.get("gain_db", 0) / 20) * env(len(a), b.get("fade_in", 0.05), b.get("fade_out", 0.05))[:, None]
        a *= keyed(b, b["start"], len(a))[:, None]
        place(fx, a, b["start"])
        report["beds"].append({"file": os.path.basename(b["file"]), "start": b["start"], "end": b["end"], "rms_db": round(rms_db(a), 1)})
    for c in sp.get("cues", []):
        af = filters(c)
        a = decode(c["file"], c.get("src_in", 0.0), c.get("dur"), ",".join(af) or None)
        if c.get("pitch"):
            r = 2 ** (c["pitch"] / 12)
            num, den = int(round(1000 / r)), 1000
            a = resample_poly(a, num, den, axis=0)
        if c.get("reverse"):
            a = a[::-1].copy()
        if c.get("reverb"):
            rv = c["reverb"]
            a = reverb(a, rv.get("rt60", 3.0), rv.get("mix", 0.5), rv.get("predelay", 0.02))
        if "rms_db" in c:
            a *= 10 ** ((c["rms_db"] - rms_db(a)) / 20)
        a *= 10 ** (c.get("gain_db", 0) / 20) * env(len(a), c.get("fade_in", 0.005), c.get("fade_out", 0.05))[:, None]
        at = c["at"] - (len(a) / SR if c.get("align") == "end" else 0.0)
        a *= keyed(c, at, len(a))[:, None]
        place(fx, a, at)
        report["cues"].append({"file": os.path.basename(c["file"]), "at": round(at, 3), "len": round(len(a) / SR, 3), "rms_db": round(rms_db(a), 1)})
    tks = sp.get("ticks") or []
    if isinstance(tks, dict):
        tks = [tks]
    for tk in tks:
        tick = decode(tk["file"], tk["tick_in"], tk["dur"], ",".join(filters(tk)) or None)
        tock = decode(tk["file"], tk.get("tock_in", tk["tick_in"]), tk["dur"], ",".join(filters(tk)) or None)
        n = min(len(tick), len(tock))
        e = env(n, 0.001, 0.04)[:, None]
        for k, t in enumerate(tk["times"]):
            g = tk.get("gain_db", 0) + (np.interp(t, [q[0] for q in tk["gain_keys"]], [q[1] for q in tk["gain_keys"]]) if tk.get("gain_keys") else 0)
            src = tick if k % 2 == 0 else tock
            place(fx, src[:n] * e * 10 ** (g / 20), t - tk.get("pre", 0.0))
    for t0, t1, db in sp.get("ducks", []):
        i0, i1 = int(t0 * SR), int(t1 * SR)
        fx[i0:i1] *= 10 ** (db / 20)
    sc = sp.get("score")
    mus = np.zeros((N, 2))
    if sc:
        if sc.get("stems"):
            for name, (f, g) in sc["stems"].items():
                a = decode(f)[:N]
                place(mus, a * 10 ** (g / 20), 0.0)
        else:
            place(mus, decode(sc["file"])[:N] * 10 ** (sc.get("gain_db", 0) / 20), 0.0)
    for t0, t1 in sp.get("silence", []):
        i0, i1 = int(t0 * SR), int(t1 * SR)
        f = int(0.004 * SR)
        for bus in (fx, mus):
            bus[i0:i1] = 0
            if i0 - f > 0:
                bus[i0 - f:i0] *= np.linspace(1, 0, f)[:, None]
            if i1 + f < N:
                bus[i1:i1 + f] *= np.linspace(0, 1, f)[:, None]
    meter = pyln.Meter(SR)

    def master(x: np.ndarray, lufs: float, name: str) -> dict:
        x = x.copy()
        tail = int(0.01 * SR)
        x[-tail:] *= np.linspace(1, 0, tail)[:, None]
        g = lufs - meter.integrated_loudness(x)
        x = limit(x * 10 ** (g / 20), -1.5)
        sf.write(os.path.join(out, name), x.astype(np.float32), SR, subtype="PCM_24")
        return {"file": name, "lufs": round(meter.integrated_loudness(x), 2), "true_peak_dbtp": round(true_peak_db(x), 2), "gain_db": round(g, 2)}

    report["mix"] = master(fx + mus, -14.0, "mix.wav")
    report["sfx_only"] = master(fx, -16.0, "sfx_only.wav")
    sf.write(os.path.join(out, "fx_bus.wav"), fx.astype(np.float32), SR, subtype="PCM_24")
    sf.write(os.path.join(out, "music_bus.wav"), mus.astype(np.float32), SR, subtype="PCM_24")
    json.dump(report, open(os.path.join(out, "sound_report.json"), "w"), indent=1)
    print(json.dumps({k: report[k] for k in ("mix", "sfx_only")}))


if __name__ == "__main__":
    main()
