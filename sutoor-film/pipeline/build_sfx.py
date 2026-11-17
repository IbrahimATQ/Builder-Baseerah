#!/usr/bin/env python3
"""Assemble a sound-effects or ambience track on the film timeline from a cue list.

Spec JSON: {"duration": seconds, "cues": [{"src": path, "src_in": s, "start": film_s, "end": film_s,
            "gain_db": 0, "fade_in": 0.03, "fade_out": 0.12}], "automation": [[t, dB], ...] (optional)}
Picture-synced cues (e.g. a clip's own hammer strikes) use the same src_in as the picture, so sound
and image stay locked. Any input format ffmpeg reads is accepted.

Usage: python build_sfx.py spec.json OUT.wav
"""
from __future__ import annotations

import json
import subprocess
import sys

import numpy as np
import soundfile as sf

SR = 48000


def read(path: str, start: float, dur: float) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{start:.4f}", "-t", f"{dur:.4f}", "-i", path, "-vn",
                          "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def main(spec_p: str, out_p: str) -> None:
    spec = json.load(open(spec_p, encoding="utf-8"))
    n = int(spec["duration"] * SR)
    out = np.zeros((n, 2), np.float32)
    for c in spec["cues"]:
        dur = c["end"] - c["start"]
        x = read(c["src"], c.get("src_in", 0.0), dur)
        fi, fo = int(c.get("fade_in", 0.03) * SR), int(c.get("fade_out", 0.12) * SR)
        if fi:
            x[:fi] *= np.linspace(0, 1, min(fi, len(x)))[:, None]
        if fo:
            x[-fo:] *= np.linspace(1, 0, min(fo, len(x)))[:, None]
        x *= 10 ** (c.get("gain_db", 0.0) / 20)
        s = int(c["start"] * SR)
        e = min(n, s + len(x))
        out[s:e] += x[: e - s]
    if spec.get("automation"):
        pts = np.array(spec["automation"], float)
        g = 10 ** (np.interp(np.arange(n) / SR, pts[:, 0], pts[:, 1]) / 20)
        out *= g[:, None].astype(np.float32)
    sf.write(out_p, out, SR, subtype="FLOAT")
    print(f"{out_p}: {len(spec['cues'])} cues, peak {20 * np.log10(np.abs(out).max() + 1e-9):.1f} dBFS")


if __name__ == "__main__":
    main(*sys.argv[1:3])
