#!/usr/bin/env python3
"""The coffee film's sound: the scene's own sound under a quiet piano piece.

Each shot carries the sound recorded with it, slowed to the picture's 0.8x with the pitch kept (ffmpeg
atempo), so the city murmur, the room, the kettle's stream and the coffee falling into the mug are where
the picture shows them. Shots overlap in sound as they do in picture (equal-power crossfades over the
dissolves, short ones at cuts). Each shot's sound is set to a level of its own (`db`, RMS dBFS before the
master gain), cleaned of rumble (high-pass) and, where asked, of hiss (low-pass).

The music (plan["music"]) enters at its offset, fades in over a second and out where the plan says.
Two masters are written:
  mix.wav      music + scene sound, -14 LUFS integrated, true peak <= -1.5 dBTP
  natural.wav  scene sound alone, -16 LUFS, for posting with a platform's own music
Usage: python sound.py PLAN.json SOURCES.json RAW_DIR OUT_DIR
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


def decode(path: str, start: float | None = None, dur: float | None = None, af: str | None = None) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error"] + (["-ss", f"{start:.4f}"] if start is not None else []) + (["-t", f"{dur:.4f}"] if dur else []) + \
          ["-i", path, "-vn"] + (["-af", af] if af else []) + ["-ac", "2", "-ar", str(SR), "-f", "f32le", "-"]
    a = np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32)
    return a.reshape(-1, 2).copy()


def rms_db(a: np.ndarray) -> float:
    return 20 * np.log10(np.sqrt(np.mean(a.astype(np.float64) ** 2)) + 1e-12)


def true_peak_db(a: np.ndarray) -> float:
    up = resample_poly(a, 4, 1, axis=0)
    return 20 * np.log10(np.max(np.abs(up)) + 1e-12)


def limit(a: np.ndarray, ceiling_db: float = -1.0) -> np.ndarray:
    """A gentle look-ahead peak limiter on 4x-oversampled peaks (rarely acts on this material)."""
    c = 10 ** (ceiling_db / 20)
    up = np.max(np.abs(resample_poly(a, 4, 1, axis=0)), axis=1).reshape(-1, 4).max(axis=1)[: len(a)]
    need = np.minimum(1.0, c / np.maximum(up, 1e-9))
    if need.min() >= 1.0:
        return a
    w = int(0.004 * SR)
    g = minimum_filter1d(need, size=2 * w + 1, mode="nearest")  # look-ahead and hold
    k = np.hanning(2 * w + 1); k /= k.sum()
    g = np.minimum(np.convolve(g, k, mode="same"), need)
    return a * g[:, None]


def main() -> None:
    plan_p, src_p, raw, out = sys.argv[1:5]
    os.makedirs(out, exist_ok=True)
    plan = json.load(open(plan_p, encoding="utf-8"))
    stretches = {s["id"]: s for s in json.load(open(src_p, encoding="utf-8"))["stretches"]}
    N = int(round(plan["duration"] * SR))
    scene = np.zeros((N, 2), np.float64)
    shots = plan["shots"]
    report = []
    for i, s in enumerate(shots):
        snd = s.get("sound", {})
        st = stretches[snd.get("src", s["id"])]  # a shot may carry another stretch's sound (e.g. the city heard through the window)
        s_in = snd.get("in", s["in"])
        tr = s.get("trans", {})
        xin = tr.get("dur", 0.0) if tr.get("type") == "dissolve" else snd.get("xfade", 0.12)
        nxt = shots[i + 1] if i + 1 < len(shots) else None
        ntr = nxt.get("trans", {}) if nxt else {}
        xout = (ntr.get("dur", 0.0) if ntr.get("type") == "dissolve" else (nxt.get("sound", {}).get("xfade", 0.12) if nxt else 0.0))
        t0 = max(0.0, s["start"] - xin / 2 - snd.get("lead", 0.0))
        t1 = min(plan["duration"], s["end"] + xout / 2)
        src0 = st["from"] + (s_in + (t0 - s["start"])) * 0.8
        af = [f"atempo=0.8", f"highpass=f={snd.get('hp', 120)}"]
        if snd.get("lp"):
            af.append(f"lowpass=f={snd['lp']}")
        a = decode(os.path.join(raw, st["file"]), max(src0, 0.0), (t1 - t0) * 0.8 + 0.2, ",".join(af))
        n = min(len(a), int(round((t1 - t0) * SR)))
        a = a[:n].astype(np.float64)
        level = rms_db(a)
        a *= 10 ** ((snd.get("db", -30.0) - level) / 20)
        env = np.ones(n)
        fi, fo = int((xin + snd.get("lead", 0.0)) * SR), int(xout * SR)
        if fi > 0:
            env[:fi] = np.sin(np.linspace(0, np.pi / 2, fi)) ** 2 if i else np.linspace(0, 1, fi)
        if fo > 0 and nxt:
            env[-fo:] = np.cos(np.linspace(0, np.pi / 2, fo)) ** 2
        if "fade_out" in snd:
            a0, a1 = snd["fade_out"]
            tt = t0 + np.arange(n) / SR
            env *= np.clip((a1 - tt) / max(a1 - a0, 1e-3), 0, 1)
        i0 = int(round(t0 * SR))
        scene[i0:i0 + n] += a * env[:, None]
        report.append({"shot": s["id"], "film": [round(t0, 2), round(t1, 2)], "source": [round(src0, 2), round(src0 + (t1 - t0) * 0.8, 2)],
                       "raw_rms_db": round(level, 1), "set_db": snd.get("db", -30.0)})
    m = plan["music"]
    mus = decode(m["file"], m["offset"], plan["duration"] + 0.5)[:N].astype(np.float64)
    mus = np.pad(mus, ((0, max(0, N - len(mus))), (0, 0)))
    tt = np.arange(N) / SR
    menv = np.clip(tt / m.get("fade_in", 1.0), 0, 1) ** 2
    a0, a1 = m["fade_out"]
    menv *= np.clip((a1 - tt) / (a1 - a0), 0, 1) ** 1.5
    if m.get("keys"):  # level automation in dB, e.g. a few dB of room for the pour into the mug
        ks = sorted(m["keys"])
        menv *= 10 ** (np.interp(tt, [k[0] for k in ks], [k[1] for k in ks]) / 20)
    mus *= menv[:, None] * 10 ** (m.get("db", 0.0) / 20)
    meter = pyln.Meter(SR)

    def master(x: np.ndarray, lufs: float, name: str) -> dict:
        tail = int(0.02 * SR)
        x = x.copy()
        x[-tail:] *= np.linspace(1, 0, tail)[:, None]
        g = lufs - meter.integrated_loudness(x)
        x = limit(x * 10 ** (g / 20), -1.5)  # -1.5 so the AAC encode stays under -1 dBTP
        sf.write(os.path.join(out, name), x.astype(np.float32), SR, subtype="PCM_24")
        return {"file": name, "lufs": round(meter.integrated_loudness(x), 2), "true_peak_dbtp": round(true_peak_db(x), 2), "gain_db": round(g, 2)}

    res = {"shots": report, "mix": master(scene + mus, -14.0, "mix.wav"), "natural": master(scene, -16.0, "natural.wav"),
           "music_vs_scene_db": round(rms_db(mus) - rms_db(scene), 1)}
    json.dump(res, open(os.path.join(out, "sound_report.json"), "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("mix", "natural", "music_vs_scene_db")}))


if __name__ == "__main__":
    main()
