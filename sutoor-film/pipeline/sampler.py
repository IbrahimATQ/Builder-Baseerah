"""Minimal offline orchestral sampler for CC0 VSCO-2 Community Edition samples.

Renders notes (pitch-shifted from the nearest recorded sample, enveloped, looped when
held longer than the recording) into stereo buses, then applies a synthetic hall reverb.
Pure numpy/scipy; deterministic; CPU only.
"""
from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache

import numpy as np
import soundfile as sf
from scipy.signal import butter, fftconvolve, resample_poly, sosfilt

SR = 48000
NOTE_RE = re.compile(r"(?<![A-Za-z])([A-G])(#|b)?(-?\d)(?=_)")
NAMES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def name_to_midi(name: str) -> int:
    m = re.fullmatch(r"([A-G])(#|b)?(-?\d)", name)
    if not m:
        raise ValueError(name)
    n = NAMES[m.group(1)] + (1 if m.group(2) == "#" else -1 if m.group(2) == "b" else 0)
    return 12 * (int(m.group(3)) + 1) + n


@dataclass
class Sample:
    path: str
    midi: int
    layer: int


class Instrument:
    """A set of samples; `octave_offset` corrects the library's naming convention."""

    def __init__(self, root: str, pattern: str, octave_offset: int = 0, layer_re: str = r"_v(\d)", mapping: dict | None = None,
                 loopable: bool = True):
        self.loopable = loopable  # sustained articulations may be looped; plucked/struck ones decay naturally
        self.samples: list[Sample] = []
        for p in sorted(glob.glob(os.path.join(root, pattern))):
            base = os.path.basename(p)
            if mapping is not None:
                num = re.search(r"_(\d{3})\.wav$", base)
                if not num or num.group(1) not in mapping:
                    continue
                midi = mapping[num.group(1)]
            else:
                m = NOTE_RE.search(base)
                if not m:
                    continue
                midi = name_to_midi(m.group(1) + (m.group(2) or "") + m.group(3)) + 12 * octave_offset
            lm = re.search(layer_re, base)
            self.samples.append(Sample(p, midi, int(lm.group(1)) if lm else 1))
        if not self.samples:
            raise FileNotFoundError(f"no samples for {pattern}")

    def pick(self, midi: int, layer: int | None = None) -> Sample:
        cands = self.samples
        if layer is not None:
            layers = sorted({s.layer for s in cands}, key=lambda l: abs(l - layer))
            cands = [s for s in cands if s.layer == layers[0]]
        return min(cands, key=lambda s: (abs(s.midi - midi), s.path))


@lru_cache(maxsize=512)
def load(path: str) -> np.ndarray:
    data, sr = sf.read(path, dtype="float32", always_2d=True)
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    if sr != SR:
        f = Fraction(SR, sr).limit_denominator(1000)
        data = resample_poly(data, f.numerator, f.denominator, axis=0).astype(np.float32)
    return data


def pitch_shift(data: np.ndarray, semitones: float) -> np.ndarray:
    if abs(semitones) < 1e-3:
        return data
    ratio = 2 ** (semitones / 12.0)  # >1 raises pitch -> fewer samples
    f = Fraction(1 / ratio).limit_denominator(400)
    return resample_poly(data, f.numerator, f.denominator, axis=0).astype(np.float32)


def envelope(n: int, attack: float, release: float, curve: float = 2.0) -> np.ndarray:
    env = np.ones(n, dtype=np.float32)
    a = min(int(attack * SR), n)
    r = min(int(release * SR), n - a)
    if a > 0:
        env[:a] = np.linspace(0, 1, a, dtype=np.float32) ** curve
    if r > 0:
        env[n - r :] *= np.linspace(1, 0, r, dtype=np.float32) ** curve
    return env


class Bus:
    def __init__(self, seconds: float):
        self.buf = np.zeros((int(seconds * SR) + SR, 2), dtype=np.float32)

    def add(self, audio: np.ndarray, start: float, gain: float = 1.0, pan: float = 0.0):
        i = int(start * SR)
        if i >= len(self.buf):
            return
        audio = audio[: len(self.buf) - i]
        lg, rg = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
        self.buf[i : i + len(audio), 0] += audio[:, 0] * gain * lg * 1.4142
        self.buf[i : i + len(audio), 1] += audio[:, 1] * gain * rg * 1.4142


def render_note(inst: Instrument, midi: int, dur: float, *, layer: int | None = None, attack: float = 0.4,
                release: float = 1.2, skip: float = 0.0, loop_xfade: float = 1.5) -> np.ndarray:
    s = inst.pick(midi, layer)
    raw = pitch_shift(load(s.path), midi - s.midi)[int(skip * SR) :]
    need = int((dur + release) * SR)
    if len(raw) < need and not inst.loopable:
        raw = np.concatenate([raw, np.zeros((need - len(raw), 2), dtype=np.float32)])
    elif len(raw) < need:  # crossfade-loop the stable middle of the sample
        xf = min(int(loop_xfade * SR), len(raw) // 3)
        body_start = min(int(1.0 * SR), len(raw) // 4)
        seg = raw[body_start:]
        out = raw.copy()
        while len(out) < need:
            fade = np.linspace(0, 1, xf, dtype=np.float32)[:, None]
            tail = out[-xf:] * (1 - fade) + seg[:xf] * fade
            out = np.concatenate([out[:-xf], tail, seg[xf:]])
        raw = out
    raw = raw[:need]
    return raw * envelope(len(raw), attack, release)[:, None]


def hall_ir(rt60: float = 3.2, predelay: float = 0.025, seed: int = 7) -> np.ndarray:
    """Synthetic stereo hall impulse response: decorrelated noise, exponential decay,
    frequency-dependent damping (highs decay faster)."""
    rng = np.random.default_rng(seed)
    n = int(rt60 * 1.4 * SR)
    t = np.arange(n) / SR
    ir = np.zeros((n, 2), dtype=np.float32)
    bands = [(None, 400, 1.0), (400, 2500, 0.75), (2500, None, 0.45)]
    for lo, hi, rt_scale in bands:
        noise = rng.standard_normal((n, 2)).astype(np.float32)
        if lo and hi:
            sos = butter(4, [lo, hi], btype="band", fs=SR, output="sos")
        elif hi:
            sos = butter(4, hi, btype="low", fs=SR, output="sos")
        else:
            sos = butter(4, lo, btype="high", fs=SR, output="sos")
        band = sosfilt(sos, noise, axis=0)
        decay = np.exp(-6.91 * t / (rt60 * rt_scale))[:, None]
        ir += band * decay
    ir[: int(predelay * SR)] = 0
    early = np.zeros_like(ir)
    for d, g in [(0.011, 0.5), (0.019, 0.35), (0.027, 0.3), (0.041, 0.22)]:
        k = int(d * SR)
        early[k, 0] += g
        early[int(k * 1.07), 1] += g
    ir = ir / np.max(np.abs(ir)) * 0.6 + early
    return ir / np.sqrt(np.sum(ir**2) / 2)


def reverb(dry: np.ndarray, ir: np.ndarray, wet: float) -> np.ndarray:
    w = np.stack([fftconvolve(dry[:, c], ir[:, c])[: len(dry)] for c in range(2)], axis=1)
    return (dry * (1 - wet) + w * wet * 0.35).astype(np.float32)


def lowpass(x: np.ndarray, hz: float, order: int = 2) -> np.ndarray:
    return sosfilt(butter(order, hz, btype="low", fs=SR, output="sos"), x, axis=0).astype(np.float32)


def highpass(x: np.ndarray, hz: float, order: int = 2) -> np.ndarray:
    return sosfilt(butter(order, hz, btype="high", fs=SR, output="sos"), x, axis=0).astype(np.float32)


def wind(seconds: float, seed: int = 3, base: float = 380.0) -> np.ndarray:
    """Synthetic desert wind: band-passed noise with slow gust modulation of level and colour."""
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    out = np.zeros((n, 2), dtype=np.float32)
    t = np.arange(n) / SR
    for c in range(2):
        noise = rng.standard_normal(n).astype(np.float32)
        gust = 0.55 + 0.45 * np.sin(2 * np.pi * (0.07 + 0.02 * c) * t + rng.uniform(0, 6)) * np.sin(2 * np.pi * 0.023 * t + 1.3 * c)
        lo = sosfilt(butter(2, [base * 0.4, base * 1.6], btype="band", fs=SR, output="sos"), noise)
        hi = sosfilt(butter(2, [base * 2.5, base * 7], btype="band", fs=SR, output="sos"), noise)
        out[:, c] = (lo * 0.8 + hi * 0.25 * gust) * gust
    return out / np.max(np.abs(out)) * 0.5
