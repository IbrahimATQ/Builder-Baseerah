#!/usr/bin/env python3
"""Original cinematic score for "THE CITY CAN WAIT" (director's cut), rendered offline.

Usage:
    python compose.py CUESHEET.json OUT_DIR

Writes, in OUT_DIR:
    organ.wav, piano.wav, strings.wav, perc.wav   stems (they sum exactly to music.wav)
    music.wav                                      the mix: 48 kHz / 24-bit / stereo, exactly the
                                                   cue-sheet duration, -16 LUFS, <= -2 dBTP
    score_report.json                              key, tempo, bar-by-bar description, measured
                                                   onsets vs the cue sheet, tuning (cents),
                                                   loop-seam check, per-segment LUFS, QC
    spectrogram.png                                whole piece with the cue-sheet hits marked
    stops.png                                      zoom on the two hard stops (2.000 / 13.500)

Musical idea (D minor, 60 bpm = one clock tick per second): a pipe-organ ostinato in a 3+3+2
grouping whose note values halve with every cue (8ths -> 16ths -> 32nds) over a tonic pedal
that starts to move (D - Bb - G - F - G - A).  The city's rise F-G-A is cut dead on the
dominant at 13.500; the coffee's rise Bb-C-D (27-29 s) completes it and resolves to D major,
whose top line D-E-F# is the kitchen piano motif (A-D-E-F) turned from minor to major.
Nothing is quoted from any existing score.

Instruments: VSCO-2 Community Edition (CC0; organ and upright piano sampled by Simon Dalzell /
Ivy Audio).  Every sample's pitch, level, onset and stereo correlation is measured here (file
names are not trusted); notes are pitch-shifted from the nearest measured sample with
polyphase resampling and corrected to A=440 equal temperament.  Reverb is a synthetic church
impulse response.  Deterministic: the only noise is seeded (reverb IR).
Only numpy / scipy / soundfile / pyloudnorm / librosa / matplotlib are imported.
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "2"

import glob
import json
import re
import sys
import time
from collections import OrderedDict
from dataclasses import dataclass
from fractions import Fraction

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy.ndimage import minimum_filter1d, uniform_filter1d
from scipy.signal import butter, fftconvolve, find_peaks, resample_poly, sosfilt

SR = 48000
VSCO = "/home/user/sgossner/vsco-2-ce"
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:7.1f}s]", *a, flush=True)


# ----------------------------------------------------------------------------- pitch helpers
_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def N(name: str) -> int:
    """'D4' -> 62, 'F#3' -> 54, 'Bb2' -> 46 (C4 = 60)."""
    m = re.fullmatch(r"([A-G])(#|b)?(-?\d)", name)
    if not m:
        raise ValueError(name)
    return 12 * (int(m.group(3)) + 1) + _PC[m.group(1)] + {"#": 1, "b": -1, None: 0}[m.group(2)]


def NAME(m: float) -> str:
    m = int(round(m))
    return ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "G#", "A", "Bb", "B"][m % 12] + str(m // 12 - 1)


def hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def midi_of(f: float) -> float:
    return 69 + 12 * np.log2(f / 440.0)


def dbv(x) -> float:
    return float(20 * np.log10(max(float(x), 1e-12)))


# ----------------------------------------------------------------------------- sample library
@dataclass
class Smp:
    path: str
    nominal: float          # nominal sounding MIDI from the verified mapping (checked by measurement)
    layer: int = 1
    rr: int = 1
    meas: float = 0.0       # measured sounding MIDI (fractional)
    gain: float = 1.0       # level normalisation
    mono: int = -1          # -1 keep stereo, else fold to this channel (mono compatibility)
    sr: int = 44100
    phys: int = 0           # physical start (source samples)
    att: int = 0            # perceptual attack point (source samples)
    s0: int = 0             # steady region (for loops), source samples
    s1: int = 0
    lufs: float = -99.0
    corr: float = 1.0
    sub16: float = -99.0    # level (dB) of a harmonic series one octave below nominal (16' rank check)


_METERS: dict[int, pyln.Meter] = {}


def meter(sr):
    if sr not in _METERS:
        _METERS[sr] = pyln.Meter(sr)
    return _METERS[sr]


def load(path):
    x, sr = sf.read(path, dtype="float32", always_2d=True)
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    return x[:, :2], sr


def _peak_centroid(P, freqs, i0, i1):
    seg = P[i0:i1]
    if len(seg) == 0 or seg.max() <= 0:
        return None, 0.0
    m = seg >= 0.25 * seg.max()
    return float(np.sum(freqs[i0:i1][m] * seg[m]) / np.sum(seg[m])), float(seg.max())


def harmonic_f0(mono, sr, f_nom, kmax=8, win_cents=35):
    """Fundamental of the harmonic series nearest f_nom: power-weighted centroid of each
    partial k*f_nom (+-win_cents), divided by k; amplitude-weighted over the 4 strongest."""
    n = len(mono)
    nfft = 1 << int(np.ceil(np.log2(max(n, 1) * 4)))
    P = np.abs(np.fft.rfft(mono * np.hanning(n), nfft)) ** 2
    freqs = np.arange(len(P)) * sr / nfft
    ests, ws = [], []
    for k in range(1, kmax + 1):
        fk = k * f_nom
        if fk > min(7000.0, sr / 2 - 200):
            break
        i0 = int(fk * 2 ** (-win_cents / 1200) * nfft / sr)
        i1 = int(fk * 2 ** (win_cents / 1200) * nfft / sr) + 2
        fc, w = _peak_centroid(P, freqs, i0, i1)
        if fc:
            ests.append(fc / k)
            ws.append(w)
    if not ests:
        return f_nom
    idx = np.argsort(ws)[::-1][:4]
    return float(np.average(np.array(ests)[idx], weights=np.sqrt(np.array(ws)[idx])))


def sub_octave_level(mono, sr, f_nom):
    """dB of the odd partials of f_nom/2 relative to the partials of f_nom (16' rank detector)."""
    n = len(mono)
    nfft = 1 << int(np.ceil(np.log2(n * 2)))
    X = np.abs(np.fft.rfft(mono * np.hanning(n), nfft))
    fr = np.arange(len(X)) * sr / nfft

    def amp(f):
        i0, i1 = int(f * 0.985 * nfft / sr), int(f * 1.015 * nfft / sr) + 2
        return X[i0:i1].max() if i1 > i0 else 0.0

    odd = np.sqrt(sum(amp(f_nom / 2 * k) ** 2 for k in (1, 3, 5, 7) if f_nom / 2 * k < 8000))
    harm = np.sqrt(sum(amp(f_nom * k) ** 2 for k in (1, 2, 3, 4) if f_nom * k < 8000))
    return dbv(odd / (harm + 1e-12))


def timp_principal(mono, sr, t0=0.12, t1=1.8):
    """Principal (1,1) mode of a timpani: peak f with partners near 1.5f and 2f."""
    on = int(np.argmax(np.abs(mono) > 0.1 * np.abs(mono).max()))
    seg = mono[on + int(t0 * sr): on + int(t1 * sr)]
    nfft = 1 << 18
    X = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), nfft))
    fr = np.arange(len(X)) * sr / nfft

    def amp(f):
        i0, i1 = int(f * 0.975 * nfft / sr), int(f * 1.025 * nfft / sr) + 2
        return X[i0:i1].max()

    band = (fr > 55) & (fr < 260)
    pk, _ = find_peaks(np.where(band, X, 0), height=X[band].max() * 0.06, distance=int(6 / (sr / nfft)))
    best, bf = -1, None
    for i in pk:
        f = fr[i]
        s = amp(f) + 0.8 * amp(1.5 * f) + 0.6 * amp(1.98 * f)
        if s > best:
            best, bf = s, i
    i = bf
    a, b, c = np.log(X[i - 1] + 1e-12), np.log(X[i] + 1e-12), np.log(X[i + 1] + 1e-12)
    p = 0.5 * (a - c) / (a - 2 * b + c)
    return (i + p) * sr / nfft


class Inst:
    """A sampled instrument: kind 'sustain' (loopable), 'pluck' (decays) or 'timp'."""

    def __init__(self, name, samples, kind="sustain", kmax=8, normalise=True, level_lufs=-20.0):
        self.name, self.samples, self.kind, self.kmax = name, samples, kind, kmax
        self.normalise, self.level_lufs = normalise, level_lufs
        self.loopable = kind == "sustain"
        self.ready = False
        self.rr_count: dict = {}

    def calibrate(self):
        if self.ready:
            return
        for s in self.samples:
            x, sr = load(s.path)
            s.sr = sr
            e2 = uniform_filter1d((x.astype(np.float64) ** 2).mean(1), int(0.005 * sr))
            env = np.sqrt(np.maximum(e2, 0))
            peak0 = env[: int(1.0 * sr)].max() + 1e-12
            above = np.nonzero(env > peak0 * 10 ** (-45 / 20))[0]
            s.phys = max(0, int(above[0]) - int(0.002 * sr)) if len(above) else 0
            s.att = int(np.argmax(env >= peak0 * 10 ** (-12 / 20)))
            # steady region (sustained samples)
            mid = env[int(0.5 * sr): max(int(0.5 * sr) + 1, len(env) - int(1.5 * sr))]
            med = np.median(mid) if len(mid) else peak0
            hi = np.nonzero(env >= med * 10 ** (-6 / 20))[0]
            rel = int(hi[-1]) if len(hi) else len(env) - 1
            s.s0 = min(s.att + int(0.45 * sr), rel)
            s.s1 = max(s.s0 + int(0.5 * sr), rel - int(0.3 * sr))
            # stereo safety: fold to one channel if the mono sum loses > 3 dB
            if self.kind == "timp":
                st = x[s.att: s.att + int(1.5 * sr)]
            else:
                st = x[s.s0: s.s1] if s.s1 - s.s0 > sr else x[s.att: s.att + int(2 * sr)]
            eL, eR = float(np.mean(st[:, 0] ** 2)), float(np.mean(st[:, 1] ** 2))
            eM = float(np.mean(((st[:, 0] + st[:, 1]) / 2) ** 2))
            s.corr = float(np.corrcoef(st[:, 0], st[:, 1])[0, 1]) if eL > 0 and eR > 0 else 1.0
            if eM < 10 ** (-3 / 10) * (eL + eR) / 2:
                s.mono = 0 if eL >= eR else 1
            xm = x[:, s.mono] if s.mono >= 0 else x.mean(1)
            # level (K-weighted loudness of the steady part / first second of a hit)
            if self.kind == "sustain":
                seg = x[s.s0: min(s.s1, s.s0 + int(6 * sr))]
            else:
                seg = x[s.att: s.att + int(1.0 * sr)]
            if s.mono >= 0:
                seg = np.repeat(seg[:, [s.mono]], 2, axis=1)
            try:
                s.lufs = float(meter(sr).integrated_loudness(seg.astype(np.float64)))
            except Exception:
                s.lufs = -70.0
            # pitch
            if self.kind == "timp":
                f = timp_principal(xm, sr)
                s.meas = float(midi_of(f))
            else:
                if self.kind == "sustain":
                    a, b = s.s0, min(s.s1, s.s0 + int(5 * sr))
                else:
                    a, b = s.att + int(0.05 * sr), s.att + int(1.2 * sr)
                seg_m = xm[a:b].astype(np.float64)
                f = harmonic_f0(seg_m, sr, hz(s.nominal), self.kmax)
                s.meas = float(midi_of(f))
                if abs(s.meas - s.nominal) > 0.5:
                    log(f"WARNING {self.name} {os.path.basename(s.path)} nominal {s.nominal} measured {s.meas:.2f}")
                if self.kind == "sustain":
                    s.sub16 = sub_octave_level(seg_m, sr, hz(s.nominal))
        # level normalisation to a smooth trend over pitch (per layer)
        if self.normalise:
            lay_mean = {L: np.mean([s.lufs for s in self.samples if s.layer == L and s.lufs > -69])
                        for L in sorted({s.layer for s in self.samples})}
            softest = min(lay_mean.values())
            for L in sorted({s.layer for s in self.samples}):
                grp = [s for s in self.samples if s.layer == L and s.lufs > -69]
                if len(grp) >= 3:
                    m = np.array([s.meas for s in grp])
                    v = np.array([s.lufs for s in grp])
                    c = np.polyfit(m, v, 1)
                    for _ in range(2):  # robust refit
                        r = v - np.polyval(c, m)
                        keep = np.abs(r) < max(2.5 * np.median(np.abs(r)), 1.0)
                        if keep.sum() >= 3:
                            c = np.polyfit(m[keep], v[keep], 1)
                    # louder layers keep part of their extra level (raw differences include recording gain)
                    lay_off = float(np.clip(0.35 * (lay_mean[L] - softest), 0.0, 7.0))
                    for s in grp:
                        trend = np.polyval(c, s.meas)
                        # level -> instrument reference, keep the natural tilt (half of it) and layer offset
                        target = self.level_lufs + 0.5 * (trend - np.mean(v)) + lay_off
                        s.gain = float(10 ** ((target - s.lufs) / 20))
                else:
                    for s in grp:
                        s.gain = float(10 ** ((self.level_lufs - s.lufs) / 20))
        self.ready = True

    def pick(self, midi, layer=None):
        self.calibrate()
        c = self.samples
        if layer is not None:
            Ls = sorted({s.layer for s in c}, key=lambda l: (abs(l - layer), l))
            c = [s for s in c if s.layer == Ls[0]]
        best = min(abs(s.meas - midi) for s in c)
        c = sorted([s for s in c if abs(s.meas - midi) <= best + 0.3], key=lambda s: (abs(s.meas - midi), s.path))
        base = c[0]
        rrs = sorted([s for s in c if os.path.basename(s.path).replace(f"rr{s.rr}", "") ==
                      os.path.basename(base.path).replace(f"rr{base.rr}", "")], key=lambda s: s.rr)
        if len(rrs) > 1:
            k = (round(midi, 2), layer)
            i = self.rr_count.get(k, 0)
            self.rr_count[k] = i + 1
            return rrs[i % len(rrs)]
        return base


def _files(pattern, regex, nominal_fn, layer_fn=lambda m: 1, rr_fn=lambda m: 1):
    out = []
    for p in sorted(glob.glob(os.path.join(VSCO, pattern))):
        m = re.search(regex, os.path.basename(p))
        if m:
            out.append(Smp(p, nominal_fn(m), layer_fn(m), rr_fn(m)))
    if not out:
        raise FileNotFoundError(pattern)
    return out


def _name_midi(m, g=1):
    return N(m.group(g))


def build_library():
    lib = {}
    O = "Keys/Organ"
    # organ: mappings established by partial analysis (see report "sample_mapping")
    lib["open"] = Inst("open", _files(f"{O}/Loud/Rode_Man3Open_*.wav", r"_(\d+)\.wav$", lambda m: int(m.group(1)) + 35))
    lib["ped16"] = Inst("ped16", _files(f"{O}/Loud/Rode_Pedal_*.wav", r"_(\d+)\.wav$", lambda m: int(m.group(1)) + 23))
    lib["ged"] = Inst("ged", _files(f"{O}/Quiet/NT5_Man3Quiet_*_rr1.wav", r"_(\d+)_rr1\.wav$", lambda m: int(m.group(1)) - 86))
    lib["ped8"] = Inst("ped8", _files(f"{O}/Quiet/NT5_PedalQuiet_*_rr1.wav", r"_(\d+)_rr1\.wav$", lambda m: int(m.group(1)) - 28))
    # strings (library names are one octave low: measured)
    nre = r"([A-G]#?-?\d)"
    lib["vln_sus"] = Inst("vln_sus", _files("Strings/Violin Section/susVib/*.wav", rf"susVib_{nre}_v(\d)\.wav$",
                                            lambda m: N(m.group(1)) + 12, lambda m: int(m.group(2))))
    lib["vln_trem"] = Inst("vln_trem", _files("Strings/Violin Section/Trem/*.wav", rf"Trem_{nre}_v(\d)\.wav$",
                                              lambda m: N(m.group(1)) + 12, lambda m: int(m.group(2))))
    lib["va_sus"] = Inst("va_sus", _files("Strings/Viola Section/susvib/*.wav", rf"susvib_{nre}_v(\d)_1\.wav$",
                                          lambda m: N(m.group(1)) + 12, lambda m: int(m.group(2))))
    lib["va_trem"] = Inst("va_trem", _files("Strings/Viola Section/trem/*.wav", rf"trem_{nre}_v(\d)_rr1\.wav$",
                                            lambda m: N(m.group(1)) + 12, lambda m: int(m.group(2))))
    lib["vc_sus"] = Inst("vc_sus", _files("Strings/Cello Section/susvib/*.wav", rf"^susvib_{nre}_v(\d)_1\.wav$",
                                          lambda m: N(m.group(1)) + 12, lambda m: int(m.group(2))))
    lib["vc_trem"] = Inst("vc_trem", _files("Strings/Cello Section/trem/*.wav", rf"^trem_{nre}_v(\d)_1\.wav$",
                                            lambda m: N(m.group(1)) + 12, lambda m: int(m.group(2))))
    lib["cb_sus"] = Inst("cb_sus", _files("Strings/Solo Contrabass/SusVib/*.wav", rf"SusVib_{nre}_v(\d)_rr1\.wav$",
                                          lambda m: N(m.group(1)) + 12, lambda m: int(m.group(2))))
    lib["cb_trem"] = Inst("cb_trem", _files("Strings/Solo Contrabass/Trem/*.wav", rf"Trem_{nre}_v(\d)_rr1\.wav$",
                                            lambda m: N(m.group(1)) + 12, lambda m: int(m.group(2))))
    lib["harp"] = Inst("harp", _files("Strings/Harp/KSHarp_*.wav", rf"KSHarp_{nre}_(mf|mp|f)\.wav$",
                                      lambda m: N(m.group(1))), kind="pluck", kmax=4)
    # piano (mapping chart: file number -> key number)
    chart = {}
    with open(os.path.join(VSCO, "Keys/Upright Piano/MappingChart.txt")) as fh:
        for line in fh:
            mm = re.match(r"\s*(\d{3})=(\d+)", line)
            if mm:
                chart[mm.group(1)] = int(mm.group(2))
    pn = [s for s in _files("Keys/Upright Piano/Player_dyn*_rr1_*.wav", r"dyn(\d)_rr1_(\d{3})\.wav$",
                            lambda m: chart[m.group(2)], lambda m: int(m.group(1)))
          if 33 <= s.nominal <= 96]
    lib["piano"] = Inst("piano", pn, kind="pluck", kmax=3)
    # timpani hits / rolls
    lib["timp"] = Inst("timp", _files("Percussion/Timpani/Timpani*_Hit_v*_rr*_Sum.wav", r"Timpani(\d)_Hit_v(\d)_rr(\d)",
                                      lambda m: 0, lambda m: int(m.group(2)), lambda m: int(m.group(3))),
                       kind="timp", normalise=False)
    lib["timproll"] = Inst("timproll", _files("Percussion/Timpani/Rolls/Timpani*_Roll_v*_rr1_Sum.wav",
                                              r"Timpani(\d)_Roll_v(\d)", lambda m: 0, lambda m: int(m.group(2))),
                           kind="timp", normalise=False)
    return lib


# ----------------------------------------------------------------------------- resampling / notes
_RS: "OrderedDict[tuple, tuple]" = OrderedDict()
_RS_MAX = 140


def resampled(s: Smp, ratio: float):
    """Sample s pitch-shifted by `ratio` and converted to SR (polyphase, exact to ~0.002 cent)."""
    key = (s.path, round(ratio, 9))
    if key in _RS:
        _RS.move_to_end(key)
        return _RS[key]
    x, sr = load(s.path)
    if s.mono >= 0:
        x = np.repeat(x[:, [s.mono]], 2, axis=1)
    x = x[s.phys:] * np.float32(s.gain)
    f = Fraction(SR / (sr * ratio)).limit_denominator(1000)
    y = resample_poly(x, f.numerator, f.denominator, axis=0).astype(np.float32)
    k = f.numerator / f.denominator
    info = dict(att=int(round((s.att - s.phys) * k)), s0=int((s.s0 - s.phys) * k), s1=int((s.s1 - s.phys) * k),
                ratio_exact=SR / (sr * k))
    _RS[key] = (y, info)
    if len(_RS) > _RS_MAX:
        _RS.popitem(last=False)
    return y, info


LOOPS: list = []  # (instrument, note, seam times in note-local seconds, rho)


def loop_extend(y, a, b, need, xf_s=0.25, tag=""):
    """Extend y to `need` samples by looping its steady region [a, b] with power-preserving
    crossfades (equal-power, compensated for the measured correlation) at upward zero crossings."""
    X = int(xf_s * SR)
    mono = y.mean(1).astype(np.float64)
    zc = np.nonzero((mono[:-1] <= 0) & (mono[1:] > 0))[0] + 1
    a = max(a, X + 1)
    ls = int(zc[np.argmin(np.abs(zc - (a + X)))])
    cand = zc[(zc > b - int(0.04 * SR)) & (zc <= b) & (zc > ls + 3 * X)]
    if len(cand) == 0:
        cand = zc[(zc > ls + 3 * X) & (zc < len(y) - 1)][-40:]
    ref = mono[ls - X: ls]
    best, le, rho = -2, int(cand[-1]), 0.0
    for c in cand:
        seg = mono[c - X: c]
        r = float(np.dot(seg, ref) / (np.linalg.norm(seg) * np.linalg.norm(ref) + 1e-12))
        if r > best:
            best, le, rho = r, int(c), r
    rc = float(np.clip(rho, 0.0, 0.98))
    xx = (np.arange(X) + 0.5) / X
    u = 0.5 - 0.5 * np.cos(np.pi * xx)
    d = 1 - u
    g = 1 / np.sqrt(d * d + u * u + 2 * rc * d * u)
    fo, fi = (d * g)[:, None].astype(np.float32), (u * g)[:, None].astype(np.float32)
    parts, seams, pos = [y[: le - X]], [], le - X
    while pos < need:
        parts.append(y[le - X: le] * fo + y[ls - X: ls] * fi)
        seams.append(pos + X // 2)
        parts.append(y[ls: le - X])
        pos += X + (le - X - ls)
    LOOPS.append(dict(tag=tag, seams_s=[round(s_ / SR, 4) for s_ in seams], rho=round(rho, 3),
                      loop_len_s=round((le - ls) / SR, 3)))
    return np.concatenate(parts, axis=0)


def raised_cos(n, rising=True):
    if n <= 0:
        return np.zeros(0, np.float32)
    w = (0.5 - 0.5 * np.cos(np.pi * (np.arange(n) + 0.5) / n)).astype(np.float32)
    return w if rising else w[::-1]


def render_note(inst: Inst, midi, dur, layer=None, attack=0.004, release=0.08, skip=0.0, align=True, tag=None):
    """Return (stereo audio, pre-roll samples).  The perceptual attack lands on the event time."""
    s = inst.pick(midi, layer)
    ratio = 2 ** ((midi - s.meas) / 12)
    y, info = resampled(s, ratio)
    if skip > 0:
        begin, pre = int(skip * SR), 0
    else:
        begin, pre = 0, (info["att"] if align else 0)
    need = pre + int(round((dur + release) * SR))
    seg = y[begin:]
    if len(seg) < need:
        if inst.loopable:
            seg = loop_extend(seg, info["s0"] - begin, info["s1"] - begin, need,
                              tag=tag or f"{inst.name} {NAME(midi)}")
        else:
            seg = np.concatenate([seg, np.zeros((need - len(seg), 2), np.float32)])
    seg = seg[:need].copy()
    env = np.ones(need, np.float32)
    na = max(int(attack * SR), int(0.002 * SR))
    env[: min(na, need)] *= raised_cos(na)[: min(na, need)]
    r0 = pre + int(round(dur * SR))
    nr = need - r0
    if nr > 0:
        env[r0:] *= raised_cos(nr, rising=False)
    return seg * env[:, None], pre


def render_gliss(inst: Inst, curve, dur, layer=None, attack=0.05, release=0.08):
    """Continuous glissando (variable-rate read of a 2x-oversampled sample)."""
    tt = np.arange(int((dur + release) * SR)) / SR
    m = curve(np.minimum(tt, dur))
    s = inst.pick(float(np.median(m)), layer)
    y, info = resampled(s, 1.0)
    y2 = resample_poly(y, 2, 1, axis=0)
    rate = 2 ** ((m - s.meas) / 12)
    pos = (info["att"] * 2 + np.concatenate([[0.0], np.cumsum(rate[:-1]) * 2]))
    pos = np.minimum(pos, len(y2) - 2)
    out = np.stack([np.interp(pos, np.arange(len(y2)), y2[:, c]) for c in range(2)], 1).astype(np.float32)
    env = np.ones(len(tt), np.float32)
    na = int(attack * SR)
    env[:na] = raised_cos(na)
    nr = int(release * SR)
    env[-nr:] *= raised_cos(nr, rising=False)
    return out * env[:, None]


def perc_sample(path, ratio=1.0, gain_lufs=-20.0):
    x, sr = load(path)
    on = int(np.argmax(np.abs(x).max(1) > 10 ** (-45 / 20) * np.abs(x).max()))
    x = x[max(0, on - int(0.001 * sr)):]
    e2 = uniform_filter1d((x.astype(np.float64) ** 2).mean(1), int(0.05 * sr))
    pk = int(np.argmax(e2))
    a = max(0, min(pk - int(0.75 * sr), len(x) - int(1.5 * sr)))
    try:
        L = meter(sr).integrated_loudness(x[a: a + int(1.5 * sr)].astype(np.float64))
        x = x * np.float32(10 ** ((gain_lufs - L) / 20))
    except Exception:
        pass
    f = Fraction(SR / (sr * ratio)).limit_denominator(1000)
    return resample_poly(x, f.numerator, f.denominator, axis=0).astype(np.float32)


def sub_boom(dur=3.0, f0=58.0, f1=36.0, tau=0.85):
    t = np.arange(int(dur * SR)) / SR
    f = f1 + (f0 - f1) * np.exp(-t / 0.22)
    ph = 2 * np.pi * np.cumsum(f) / SR
    env = (1 - np.exp(-t / 0.003)) * np.exp(-t / tau)
    y = np.tanh(2.2 * np.sin(ph) * env) / np.tanh(2.2)
    y *= raised_cos(len(t), rising=False) ** 0.3
    return np.repeat(y[:, None].astype(np.float32), 2, axis=1) * 0.5


# ----------------------------------------------------------------------------- reverb
def bandpass_sos(lo, hi):
    if lo is None:
        return butter(4, hi, btype="low", fs=SR, output="sos")
    if hi is None:
        return butter(4, lo, btype="high", fs=SR, output="sos")
    return butter(4, [lo, hi], btype="band", fs=SR, output="sos")


def church_ir(seed=1931, length=7.5, predelay=0.024):
    """Synthetic stereo church IR: early reflections + decorrelated exponentially decaying noise
    with per-octave RT60 (~4.8 s in the low mids, darker in the highs)."""
    rng = np.random.default_rng(seed)
    n = int(length * SR)
    t = np.arange(n) / SR
    edges = [None, 90, 180, 355, 710, 1400, 2800, 5600, 11200, None]
    rts = [4.4, 4.8, 5.0, 4.8, 4.4, 3.6, 2.5, 1.5, 0.8]
    late = np.zeros((n, 2), np.float64)
    for i, rt in enumerate(rts):
        lo, hi = edges[i], edges[i + 1]
        noise = rng.standard_normal((n, 2))
        band = sosfilt(bandpass_sos(lo, hi), noise, axis=0)
        late += band * np.exp(-6.9078 * t / rt)[:, None]
    onset = np.clip((t - predelay) / 0.07, 0, 1)
    late *= (onset * onset * (3 - 2 * onset))[:, None]
    late /= np.sqrt(np.mean(late[: int(0.3 * SR)] ** 2) + 1e-12)
    early = np.zeros((n, 2))
    for c in range(2):
        times = np.sort(rng.uniform(0.007, 0.115, 22))
        for tt in times:
            k = int(tt * SR)
            early[k, c] += rng.choice([-1, 1]) * 0.9 * np.exp(-tt / 0.06) * rng.uniform(0.5, 1.0)
    early = sosfilt(butter(2, 6500, btype="low", fs=SR, output="sos"), early, axis=0)
    early /= np.sqrt(np.mean(early[: int(0.12 * SR)] ** 2) + 1e-12)
    ir = 0.55 * early + late * 0.6
    ir /= np.sqrt(np.sum(ir ** 2) / 2)
    return ir.astype(np.float32), dict(rt60_bands_s=dict(zip(["<90", "90-180", "180-355", "355-710", "710-1.4k",
                                                              "1.4-2.8k", "2.8-5.6k", "5.6-11k", ">11k"], rts)),
                                       predelay_s=predelay, length_s=length,
                                       lr_corr=float(np.corrcoef(ir[:, 0], ir[:, 1])[0, 1]))


def room_ir(seed=7, length=0.25, rt=0.12):
    rng = np.random.default_rng(seed)
    n = int(length * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal((n, 2)) * np.exp(-6.9078 * t / rt)[:, None]
    ir = sosfilt(butter(2, 5000, btype="low", fs=SR, output="sos"), ir, axis=0)
    ir[: int(0.003 * SR)] = 0
    ir *= raised_cos(n, rising=False)[:, None] ** 0.5
    ir /= np.sqrt(np.sum(ir ** 2) / 2)
    return ir.astype(np.float32)


def convolve(x, ir):
    return np.stack([fftconvolve(x[:, c], ir[:, c]) for c in range(2)], axis=1).astype(np.float32)


# ----------------------------------------------------------------------------- score
CELL_MINOR = [N("A4"), N("D5"), N("F5"), N("A4"), N("D5"), N("G5"), N("A4"), N("E5")]


def ramp(points):
    """Piecewise-linear gain curve in dB over absolute time -> callable returning linear gain."""
    ts = np.array([p[0] for p in points], float)
    ds = np.array([p[1] for p in points], float)
    return lambda t: (10 ** (np.interp(t, ts, ds) / 20)).astype(np.float32)


def powcurve(t0, t1, p, floor_db=-80):
    def f(t):
        x = np.clip((t - t0) / (t1 - t0), 0, 1)
        return np.maximum(x ** p, 10 ** (floor_db / 20)).astype(np.float32) * (t >= t0)
    return f


def res_decay(t):
    """Resolution chord: hold to 29.6 s, then a slow concave decay to -42 dB at 35.5 s."""
    x = np.maximum(t - 29.6, 0)
    return (10 ** (-2.20 * x ** 1.6 / 20)).astype(np.float32)


def build_score():
    E = []

    def ev(stem, inst, note, t, dur, g=0.0, pan=0.0, **kw):
        E.append(dict(stem=stem, inst=inst, midi=N(note) if isinstance(note, str) else note, t=float(t),
                      dur=float(dur), g=float(g), pan=float(pan), **kw))

    def cell(notes, t0, step, inst, g_from, g_to, dur_frac=0.88, rel=0.05, pan_alt=0.22, oct=0, stem="organ"):
        n = len(notes)
        for i, m in enumerate(notes):
            g = g_from + (g_to - g_from) * (i / max(n - 1, 1))
            ev(stem, inst, m + oct, t0 + i * step, step * dur_frac, g, pan=pan_alt * (1 if i % 2 else -1),
               attack=0.003, release=rel, role="ostinato")

    # ---------------- 0.0-2.0 cold open: pedal D from nothing + one high tone; CUT at 2.000
    sw = powcurve(0.0, 2.0, 2.3)
    ev("organ", "ped16", "D1", 0.0, 2.0, 0, skip=1.0, attack=0.002, release=0.0, env=sw, role="pedal")
    ev("organ", "ped8", "D2", 0.0, 2.0, -5, skip=1.0, attack=0.002, release=0.0, env=sw, role="pedal")
    ev("organ", "ged", "A5", 0.15, 1.85, -9, skip=0.9, attack=0.002, release=0.0, env=powcurve(0.15, 2.0, 1.5),
       pan=0.1, role="high tone")
    ev("strings", "vln_sus", "A5", 0.30, 1.70, -21, layer=1, attack=1.1, release=0.0, pan=-0.35, role="high tone")

    # ---------------- 3.0-7.0 reveal: ostinato in 8ths, pp, pedal D, crescendo
    ev("organ", "ped16", "D1", 3.0, 3.97, 0, attack=0.004, release=0.05, env=ramp([(3, -13), (7, -4)]), role="pedal")
    ev("organ", "ped8", "D2", 3.0, 3.97, 0, attack=0.004, release=0.05, env=ramp([(3, -17), (7, -8)]), role="pedal")
    cell(CELL_MINOR, 3.0, 0.5, "ged", -15, -7, dur_frac=0.9, rel=0.07)
    cell(CELL_MINOR, 3.0, 0.5, "open", -31, -16, dur_frac=0.9, rel=0.07)

    # ---------------- 7.0-11.0 street: 16ths, pedal pulses, string tremolo at 9.0
    cell_bb = [N("Bb4"), N("D5"), N("F5"), N("Bb4"), N("D5"), N("G5"), N("Bb4"), N("E5")]
    cell_gm = [N("G4"), N("D5"), N("F5"), N("G4"), N("D5"), N("G5"), N("G4"), N("E5")]
    cell(cell_bb, 7.0, 0.25, "ged", -8, -7, rel=0.05)
    cell(cell_bb, 7.0, 0.25, "open", -15, -12, rel=0.05)
    cell(cell_gm, 9.0, 0.25, "ged", -7, -6, rel=0.05)
    cell(cell_gm, 9.0, 0.25, "open", -11, -8, rel=0.05)
    cell(cell_gm, 9.0, 0.25, "ged", -20, -14, rel=0.05, oct=12)
    for t in (7.0, 8.0):
        ev("organ", "ped16", "Bb1", t, 0.9, -4, release=0.08, role="pedal")
        ev("organ", "ped8", "Bb2", t, 0.9, -9, release=0.08, role="pedal")
    for t in (9.0, 9.5, 10.0, 10.5):
        ev("organ", "ped16", "G1", t, 0.44, -3, release=0.06, role="pedal")
        ev("organ", "ped8", "G2", t, 0.44, -8, release=0.06, role="pedal")
    trem_up = ramp([(9.0, -26), (11.0, -12)])
    for inst, note, pan in (("vc_trem", "G2", 0.5), ("vc_trem", "D3", 0.45), ("va_trem", "Bb3", 0.2), ("va_trem", "D4", 0.25)):
        ev("strings", inst, note, 9.0, 2.0, 0, layer=1, attack=0.25, release=0.05, pan=pan, env=trem_up, role="trem")

    # ---------------- 11.0-13.5 square: 32nds, rising F-G-A, cluster + riser, CUT at 13.500
    cell_f = [N("C5"), N("F5"), N("A5"), N("C5"), N("F5"), N("Bb5"), N("C5"), N("G5")]
    cell_g = [N("D5"), N("G5"), N("B5"), N("D5"), N("G5"), N("C6"), N("D5"), N("A5")]
    cell_a = [N("E5"), N("A5"), N("C#6"), N("E5")]
    for c, t0, g0, g1 in ((cell_f, 11.0, -6, -5), (cell_g, 12.0, -5, -4), (cell_a, 13.0, -4, -3)):
        cell(c, t0, 0.125, "open", g0, g1, dur_frac=0.85, rel=0.035)
        cell(c, t0, 0.125, "ged", g0 - 3, g1 - 3, dur_frac=0.85, rel=0.035)
        cell(c, t0, 0.125, "open", g0 - 8, g1 - 7, dur_frac=0.85, rel=0.035, oct=-12)
    for t, note in ((11.0, "F"), (11.5, "F"), (12.0, "G"), (12.5, "G")):
        ev("organ", "ped16", note + "1", t, 0.45, -1, release=0.06, role="pedal")
        ev("organ", "ped8", note + "2", t, 0.45, -6, release=0.06, role="pedal")
    ev("organ", "ped16", "A1", 13.0, 0.55, 0, release=0.0, role="pedal")
    ev("organ", "ped8", "A2", 13.0, 0.55, -5, release=0.0, role="pedal")
    cluster = ["A3", "E4", "A4", "B4", "D5", "E5", "A5", "B5", "D6", "E6"]
    for i, note in enumerate(cluster):
        t = 11.0 + 0.25 * i
        ev("organ", "open", note, t, 13.6 - t, 0, attack=0.12, release=0.0,
           env=ramp([(t, -24), (13.5, -9)]), pan=(-0.5 + i / 9.0) * 0.8, role="rising cluster")
    for (inst, notes, pan) in (("vc_trem", ("F2", "C3", "G2", "D3", "A2", "E3"), 0.5),
                               ("va_trem", ("A3", "C4", "B3", "D4", "C#4", "E4"), 0.2),
                               ("vln_trem", ("F4", "A4", "G4", "B4", "A4", "C#5"), -0.25)):
        for k, t in enumerate((11.0, 12.0, 13.0)):
            for j in range(2):
                ev("strings", inst, notes[2 * k + j], t, 1.0 if t < 13 else 0.6, 0, layer=2, attack=0.02,
                   release=0.04, pan=pan, env=ramp([(11.0, -12), (13.5, -5)]), role="trem")
    for k, (t, note) in enumerate(((11.0, "F1"), (12.0, "G1"), (13.0, "A1"))):
        ev("strings", "cb_trem", note, t, 1.0 if t < 13 else 0.6, -6, layer=2, attack=0.02, release=0.04, pan=0.55,
           role="trem")
    E.append(dict(stem="strings", inst="vln_trem", gliss=lambda tt: N("D5") + 12 * (tt / 2.5) ** 2.0, t=11.0, dur=2.6,
                  g=0.0, pan=-0.45, layer=2, env=ramp([(11.0, -16), (13.5, -5)]), role="string riser"))
    E.append(dict(stem="strings", inst="va_trem", gliss=lambda tt: N("D4") + 12 * (tt / 2.5) ** 2.0, t=11.0, dur=2.6,
                  g=0.0, pan=0.3, layer=2, env=ramp([(11.0, -18), (13.5, -7)]), role="string riser"))

    # percussion of the city
    ev("perc", "timp", "Bb2", 7.0, 3.0, -15, layer=3, release=0.5, role="timpani")
    ev("perc", "timp", "G2", 9.0, 2.0, -12, layer=3, release=0.5, role="timpani")
    for t, note, g in ((11.0, "F2", 0), (11.5, "F2", -8), (12.0, "G2", -3), (12.5, "G2", -7)):
        ev("perc", "timp", note, t, 2.5, g, layer=4, release=0.3, role="timpani")
    ev("perc", "timproll", "A2", 13.0, 0.6, 0, layer=5, attack=0.01, release=0.0, env=ramp([(13.0, -14), (13.5, -1)]),
       role="timpani roll")
    E.append(dict(stem="perc", kind="sample", path=f"{VSCO}/Percussion/BDrumNewhit_v7_rr1_Sum.wav", t=11.0, g=-3,
                  ratio=0.89, role="gran cassa"))
    E.append(dict(stem="perc", kind="sample", path=f"{VSCO}/Percussion/BDrumNewhit_v5_rr1_Sum.wav", t=12.0, g=-9,
                  ratio=0.89, role="gran cassa"))
    E.append(dict(stem="perc", kind="sub", t=11.0, g=-10, role="sub boom"))
    E.append(dict(stem="perc", kind="sample", path=f"{VSCO}/Percussion/susCymb1-hit_mp_rr1.wav", t=11.0, g=-14,
                  role="cymbal"))
    E.append(dict(stem="perc", kind="swell", path=f"{VSCO}/Percussion/susCymb1-cresc-Long_v1.wav", peak_at=13.5,
                  g=-9, role="cymbal riser"))

    # ---------------- 13.5-15.0 time stops: one very low, very quiet organ D breathing
    br = ramp([(13.5, -70), (13.95, -24), (14.45, -19), (15.0, -25), (15.6, -23), (16.6, -70)])
    ev("organ", "ped16", "D1", 13.5, 3.1, 0, skip=1.5, attack=0.002, release=0.0, env=br, role="breath")
    ev("organ", "ped8", "D2", 13.5, 3.1, -10, skip=1.5, attack=0.002, release=0.0, env=br, role="breath")

    # ---------------- 15.0-21.0 bloom: warmth (Gedackt chords, sparse piano motif, strings pp)
    bloom = [(15.0, "Bb2", ["F3", "A3", "C4", "D4"]), (17.0, "A2", ["F3", "A3", "C4", "E4"]),
             (19.0, "G2", ["F3", "Bb3", "D4", "A4"])]
    for t, bass, ch in bloom:
        ev("organ", "ped8", bass, t, 2.05, -13, attack=0.09, release=0.45, role="bloom bass")
        for i, n_ in enumerate(ch):
            ev("organ", "ged", n_, t, 2.05, -12 + (2 if i == 3 else 0), attack=0.09, release=0.45,
               pan=(-0.3 + 0.2 * i), role="bloom chord")
    for t, n1, n2 in ((15.0, "Bb2", "D4"), (17.0, "A2", "C4"), (19.0, "G2", "D4")):
        ev("strings", "vc_sus", n1, t, 2.05, -21, layer=1, attack=0.45, release=0.6, pan=0.45, role="strings pp")
        ev("strings", "va_sus", n2, t, 2.05, -23, layer=1, attack=0.45, release=0.6, pan=0.2, role="strings pp")
    ev("strings", "vln_sus", "A5", 15.0, 6.1, -26, layer=1, attack=1.4, release=0.4, pan=-0.4, role="strings pp halo")
    ev("strings", "harp", "Bb2", 15.0, 2.5, -16, release=0.6, pan=-0.1, role="harp")
    ev("strings", "harp", "F3", 15.0, 2.5, -20, release=0.6, pan=-0.1, role="harp")
    motif = [(15.5, "A4", 1.0, -9), (16.0, "D5", 1.0, -7), (16.5, "E5", 1.4, -8), (17.5, "F5", 2.0, -6),
             (19.5, "E5", 0.9, -8), (20.0, "D5", 2.4, -7)]
    for t, n_, d, g in motif:
        ev("piano", "piano", n_, t, d, g, layer=1, release=0.7, pan=-0.15, role="piano motif")
    ev("piano", "piano", "F4", 17.5, 2.0, -17, layer=1, release=0.7, pan=-0.15, role="piano motif")
    ev("piano", "piano", "D4", 20.0, 2.4, -17, layer=1, release=0.7, pan=-0.15, role="piano motif")

    # ---------------- 21.0-29.0 pour: build pp -> climax 27-29 (timpani roll into 27.0)
    ev("strings", "harp", "D2", 21.0, 3.0, -12, release=0.6, pan=0.0, role="harp")
    ev("strings", "harp", "D3", 21.0, 3.0, -16, release=0.6, pan=0.0, role="harp")
    build = [  # t, dur, ped16, ped8, ged chord, open chord, gain offset
        (21.0, 2.0, "D1", "D2", ["F3", "A3", "D4", "E4"], [], -16),
        (23.0, 2.0, "Bb1", "Bb2", ["F3", "Bb3", "D4", "F4"], ["Bb3", "D4", "F4"], -12),
        (25.0, 1.0, "G1", "G2", ["G3", "Bb3", "D4", "G4"], ["G3", "D4", "G4", "Bb4"], -8),
        (26.0, 1.0, "A1", "A2", ["A3", "C#4", "E4", "G4"], ["A3", "E4", "G4", "C#5"], -5),
        (27.0, 1.0, "Bb1", "Bb2", ["Bb4", "D5", "F5", "D6"], ["Bb3", "D4", "F4", "Bb4", "D5", "F5"], 0),
        (28.0, 1.0, "C2", "C3", ["C5", "E5", "G5", "E6"], ["C4", "E4", "G4", "C5", "E5", "G5"], 0),
    ]
    for t, d, p16, p8, gch, och, go in build:
        a = 0.3 if t < 25 else 0.02
        ev("organ", "ped16", p16, t, d + 0.03, go - 4 + (0 if t >= 27 else -2), attack=a, release=0.05, role="pedal")
        ev("organ", "ped8", p8, t, d + 0.03, go - 8, attack=a, release=0.05, role="pedal")
        for i, n_ in enumerate(gch):
            ev("organ", "ged", n_, t, d + 0.03, go - 8 + (3 if i == len(gch) - 1 and t >= 27 else 0), attack=a,
               release=0.05, pan=-0.3 + 0.2 * i, role="chord")
        for i, n_ in enumerate(och):
            ev("organ", "open", n_, t, d + 0.03, go - 9, attack=min(a, 0.08), release=0.05,
               pan=-0.4 + 0.8 * i / max(len(och) - 1, 1), role="chord")
    # ostinato returns: 8ths (23-25), 16ths (25-29)
    cell([N("Bb4"), N("D5"), N("F5"), N("Bb4")], 23.0, 0.5, "ged", -17, -14, rel=0.06)
    cell([N("Bb4"), N("D5"), N("F5"), N("Bb4")], 23.0, 0.5, "open", -26, -22, rel=0.06)
    seq16 = [N(x) for x in ("G4", "D5", "F5", "G4", "A4", "C#5", "E5", "G5",
                            "Bb4", "D5", "F5", "D5", "C5", "E5", "G5", "E5")]
    cell(seq16, 25.0, 0.25, "ged", -12, -8, rel=0.05)
    cell(seq16, 25.0, 0.25, "open", -18, -10, rel=0.05)
    # resolution 29.0: D major, slow decay to silence by ~35.7
    ev("organ", "ped16", "D1", 29.0, 6.5, -2, attack=0.02, release=0.4, env=res_decay, role="resolution")
    ev("organ", "ped8", "D2", 29.0, 6.5, -7, attack=0.02, release=0.4, env=res_decay, role="resolution")
    for i, n_ in enumerate(["D3", "A3", "D4", "F#4", "A4", "D5", "F#5"]):
        ev("organ", "open", n_, 29.0, 6.5, -9, attack=0.02, release=0.4, env=res_decay, pan=-0.45 + 0.15 * i,
           role="resolution")
    for i, n_ in enumerate(["F#5", "A5", "D6", "F#6"]):
        ev("organ", "ged", n_, 29.0, 6.5, -8 + (3 if n_ == "F#6" else 0), attack=0.02, release=0.4, env=res_decay,
           pan=-0.3 + 0.2 * i, role="resolution")
    # strings of the pour
    st_build = [  # t, dur, cb, vc pair, va pair, vln2 pair, vln1 melody (octave pair), gain
        (21.0, 2.0, "D2", ("D3",), ("A3", "F4"), ("F4", "A4"), None, -24),
        (23.0, 2.0, "Bb1", ("Bb2",), ("Bb3", "F4"), ("F4", "D5"), ("Bb4", "Bb5"), -20),
        (25.0, 1.0, "G1", ("G2", "D3"), ("Bb3", "D4"), ("G4", "D5"), ("Bb4", "Bb5"), -15),
        (26.0, 1.0, "A1", ("A2", "E3"), ("C#4", "E4"), ("A4", "E5"), ("A4", "A5"), -12),
        (27.0, 1.0, "Bb1", ("Bb2", "F3"), ("D4", "F4"), ("F5", "Bb5"), ("D5", "D6"), -8),
        (28.0, 1.0, "C2", ("C3", "G3"), ("E4", "G4"), ("G5", "C6"), ("E5", "E6"), -8),
    ]
    for t, d, cb, vc, va, v2, v1, g in st_build:
        L = 1 if t < 25 else 2
        a = 0.5 if t < 25 else 0.06
        ev("strings", "cb_sus", cb, t, d + 0.05, g, layer=1 if t < 25 else 3, attack=a, release=0.15, pan=0.6, role="strings")
        for n_ in vc:
            ev("strings", "vc_sus", n_, t, d + 0.05, g, layer=1 if t < 25 else 3, attack=a, release=0.15, pan=0.45,
               role="strings")
        for n_ in va:
            ev("strings", "va_sus", n_, t, d + 0.05, g - 1, layer=L, attack=a, release=0.15, pan=0.2, role="strings")
        for n_ in v2:
            ev("strings", "vln_sus", n_, t, d + 0.05, g - 1, layer=L, attack=a, release=0.15, pan=-0.25, role="strings")
        if v1:
            for n_ in v1:
                ev("strings", "vln_sus", n_, t, d + 0.05, g, layer=L, attack=a, release=0.15, pan=-0.5,
                   role="strings melody")
    ev("strings", "vln_sus", "A5", 21.0, 2.05, -24, layer=1, attack=0.3, release=0.3, pan=-0.5, role="strings melody")
    for inst, notes, pan in (("cb_sus", ["D2"], 0.6), ("vc_sus", ["D3", "A3"], 0.45), ("va_sus", ["F#4", "A4"], 0.2),
                             ("vln_sus", ["A5", "D6"], -0.25), ("vln_sus", ["F#5", "F#6"], -0.5)):
        for n_ in notes:
            ev("strings", inst, n_, 29.0, 6.4, -8, layer=2 if inst != "cb_sus" and inst != "vc_sus" else 3,
               attack=0.05, release=0.5, pan=pan, env=res_decay, role="resolution")
    # piano: the motif once more over the match cut, then it gives way
    for t, n_, d, g in ((21.5, "A4", 1.0, -8), (22.0, "D5", 1.0, -6), (22.5, "E5", 1.0, -7), (23.5, "F5", 2.5, -5)):
        ev("piano", "piano", n_, t, d, g, layer=2, release=0.8, pan=-0.15, role="piano motif")
        ev("piano", "piano", N(n_) + 12, t, d, g - 11, layer=1, release=0.8, pan=-0.2, role="piano motif 8va")
    # percussion of the pour
    ev("perc", "timproll", "A2", 25.5, 1.52, 0, layer=5, attack=0.05, release=0.03,
       env=ramp([(25.5, -24), (26.3, -14), (27.0, -2)]), role="timpani roll")
    for t, note, g in ((27.0, "Bb2", 0), (27.5, "Bb2", -9), (28.0, "C3", -2), (28.5, "C3", -9), (29.0, "D2", 0)):
        ev("perc", "timp", note, t, 4.0 if t < 29 else 6.0, g, layer=4, release=0.6, role="timpani")
    for t, g, v in ((27.0, -2, 7), (28.0, -8, 6), (29.0, -2, 7)):
        E.append(dict(stem="perc", kind="sample", path=f"{VSCO}/Percussion/BDrumNewhit_v{v}_rr2_Sum.wav", t=t, g=g,
                      ratio=0.89, role="gran cassa"))
    E.append(dict(stem="perc", kind="sub", t=27.0, g=-7, role="sub boom"))
    E.append(dict(stem="perc", kind="sub", t=29.0, g=-5, role="sub boom"))
    E.append(dict(stem="perc", kind="swell", path=f"{VSCO}/Percussion/susCymb1-cresc-Median_v1.wav", peak_at=27.0,
                  g=-10, role="cymbal riser"))
    E.append(dict(stem="perc", kind="sample", path=f"{VSCO}/Percussion/gongHit_mf.wav", t=29.0, g=-13,
                  fade=(30.5, 35.6), role="tam-tam"))

    # ---------------- 31.5-36.0: the last quiet organ note (the opening's high A returns)
    ev("organ", "ged", "A5", 32.5, 2.6, -21, attack=0.5, release=1.0, pan=0.15, role="last note")
    return E


# swell-box brightness of the organ (0 = closed/dark, 1 = open)
BRIGHT = [(0, 0.15), (2.0, 0.75), (2.9, 0.25), (7.0, 0.6), (11.0, 0.9), (13.5, 1.0), (13.5001, 0.05), (15.0, 0.1),
          (15.0001, 0.35), (21.0, 0.35), (27.0, 1.0), (29.0, 1.0), (31.0, 0.75), (36.0, 0.25), (40, 0.25)]

BLOCKS = [  # name, start, end (gate), short room tail after the gate
    ("A", 0.0, 2.0, True),
    ("B", 2.5, 13.5, False),
    ("C", 13.5, None, False),
]
SENDS = {"organ": 0.52, "strings": 0.48, "piano": 0.38, "perc": 0.42}
STEM_GAIN_DB = {"organ": 0.0, "strings": 0.0, "piano": 0.0, "perc": 0.0}


def block_of(t):
    for name, a, b, _ in BLOCKS:
        if t >= a - 0.6 and (b is None or t < b):
            return name
    return "C"


# ----------------------------------------------------------------------------- render
def render(lib, events, dur_total):
    n = int(round(dur_total * SR))
    pad = int(8.0 * SR)
    buses = {}
    used = {}

    def bus(stem, blk):
        k = (stem, blk)
        if k not in buses:
            buses[k] = np.zeros((n + pad, 2), np.float32)
        return buses[k]

    def add(buf, sig, start, gain, pan, env=None):
        i0 = start
        if i0 < 0:
            sig, i0 = sig[-i0:], 0
        sig = sig[: len(buf) - i0]
        if env is not None:
            tt = (i0 + np.arange(len(sig))) / SR
            sig = sig * env(tt)[:, None]
        gl = np.cos((pan + 1) * np.pi / 4) * np.sqrt(2)
        gr = np.sin((pan + 1) * np.pi / 4) * np.sqrt(2)
        buf[i0: i0 + len(sig), 0] += sig[:, 0] * gain * gl
        buf[i0: i0 + len(sig), 1] += sig[:, 1] * gain * gr

    for e in events:
        if e.get("kind") == "swell":
            e["t"] = e["peak_at"] - 0.001
        blk = block_of(e["t"])
        b = bus(e["stem"], blk)
        g = 10 ** (e.get("g", 0) / 20)
        kind = e.get("kind")
        if kind == "sample":
            sig = perc_sample(e["path"], e.get("ratio", 1.0))
            if "fade" in e:
                f0, f1 = e["fade"]
                tt = e["t"] + np.arange(len(sig)) / SR
                w = np.clip((f1 - tt) / (f1 - f0), 0, 1)
                sig = sig * (w * w * (3 - 2 * w))[:, None].astype(np.float32)
                sig = sig[: int((f1 - e["t"]) * SR)]
            add(b, sig, int(round(e["t"] * SR)), g, e.get("pan", 0.0))
        elif kind == "sub":
            add(b, sub_boom(), int(round(e["t"] * SR)), g, 0.0)
        elif kind == "swell":
            sig = perc_sample(e["path"])
            e2 = uniform_filter1d((sig ** 2).mean(1), int(0.05 * SR))
            pk = int(np.argmax(e2))
            start = int(round(e["peak_at"] * SR)) - pk
            add(b, sig, start, g, 0.0)
            e["peak_offset_s"] = pk / SR
        elif "gliss" in e:
            inst = lib[e["inst"]]
            sig = render_gliss(inst, e["gliss"], e["dur"], layer=e.get("layer"))
            add(b, sig, int(round(e["t"] * SR)), g, e.get("pan", 0.0), e.get("env"))
        else:
            inst = lib[e["inst"]]
            sig, pre = render_note(inst, e["midi"], e["dur"], layer=e.get("layer"), attack=e.get("attack", 0.004),
                                   release=e.get("release", 0.08), skip=e.get("skip", 0.0))
            add(b, sig, int(round(e["t"] * SR)) - pre, g, e.get("pan", 0.0), e.get("env"))
            used.setdefault(e["inst"], set()).add(e["midi"])
    return buses, used, n


def organ_box(x, n0):
    """Swell box: crossfade between the open sound and a darkened (closed-box) version."""
    tt = (n0 + np.arange(len(x))) / SR
    bb = np.interp(tt, [p[0] for p in BRIGHT], [p[1] for p in BRIGHT]).astype(np.float32)[:, None]
    dark = sosfilt(butter(2, 1100, btype="low", fs=SR, output="sos"), x, axis=0).astype(np.float32)
    return x * bb + dark * (1 - bb)


def mixdown(buses, n, ir, rir):
    hp = butter(4, 28.0, btype="high", fs=SR, output="sos")
    stems = {s: np.zeros((n, 2), np.float32) for s in SENDS}
    fade = int(0.004 * SR)
    for (stem, blk), x in buses.items():
        name, a, b, room = [bl for bl in BLOCKS if bl[0] == blk][0]
        if stem == "organ":
            x = organ_box(x, 0)
        wet = convolve(x, ir)[: len(x)]
        y = x + wet * SENDS[stem]
        y = sosfilt(hp, y, axis=0).astype(np.float32)
        if b is not None:
            ib = int(round(b * SR))
            w = np.ones(len(y), np.float32)
            w[ib - fade: ib] = raised_cos(fade, rising=False)
            w[ib:] = 0
            dry_cut = sosfilt(hp, x, axis=0).astype(np.float32) * w[:, None]
            y = y * w[:, None]
            if room:  # only a short room reflection survives the cut (< 0.25 s)
                r = convolve(dry_cut, rir)[: len(y)] * 0.30
                tail = int(0.25 * SR)
                rw = np.zeros(len(y), np.float32)
                rw[ib - fade: ib] = 1 - w[ib - fade: ib]  # crossfade into the room tail: no step at the cut
                rw[ib: ib + tail] = raised_cos(tail, rising=False) ** 0.5
                y = y + r * rw[:, None]
        stems[stem] += y[:n]
    end_fade = int(0.25 * SR)
    for s in stems:
        stems[s][-end_fade:] *= raised_cos(end_fade, rising=False)[:, None]
        stems[s] *= np.float32(10 ** (STEM_GAIN_DB[s] / 20))
    return stems


# ----------------------------------------------------------------------------- mastering
def true_peak_db(x):
    up = resample_poly(x.astype(np.float64), 4, 1, axis=0)
    return dbv(np.abs(up).max())


def master(stems, target_lufs=-16.0, tp_ceiling=-2.0):
    m = pyln.Meter(SR)
    names = list(stems)
    mix = sum(stems[s] for s in names).astype(np.float64)
    L = m.integrated_loudness(mix)
    g = 10 ** ((target_lufs - L) / 20)
    gain_env = np.full(len(mix), g)
    hist = []
    for it in range(6):
        y = mix * gain_env[:, None]
        up = np.abs(resample_poly(y, 4, 1, axis=0)).max(1)
        peak = up[: 4 * len(y)].reshape(-1, 4).max(1)
        lim = 10 ** ((tp_ceiling - 0.25) / 20)
        need = np.minimum(1.0, lim / np.maximum(peak, 1e-9))
        W = int(0.004 * SR)
        mf = minimum_filter1d(need, 2 * W + 1, mode="nearest")
        sm = uniform_filter1d(mf, W, mode="nearest")
        # slow recovery (release ~150 ms), never above the instantaneous need
        rel = 1 - np.exp(-1 / (0.15 * SR))
        out = np.empty_like(sm)
        cur = 1.0
        for i0 in range(0, len(sm), 4096):  # vectorised in chunks: recovery is rarely active
            seg = sm[i0: i0 + 4096]
            o = np.empty_like(seg)
            for j, v in enumerate(seg):
                cur = v if v < cur else cur + (min(1.0, v) - cur) * rel
                o[j] = cur
            out[i0: i0 + 4096] = o
        gain_env = gain_env * out
        y = mix * gain_env[:, None]
        Ly = m.integrated_loudness(y)
        tp = true_peak_db(y)
        hist.append(dict(iter=it, lufs=round(Ly, 3), true_peak_dbtp=round(tp, 3),
                         max_gr_db=round(-dbv(out.min()), 2)))
        log(f"master iter {it}: {Ly:.2f} LUFS, TP {tp:.2f} dBTP, GR {-dbv(out.min()):.2f} dB")
        if abs(Ly - target_lufs) < 0.05 and tp <= tp_ceiling - 0.02:
            break
        gain_env = gain_env * 10 ** ((target_lufs - Ly) / 20)
    total_gain = gain_env.astype(np.float32)[:, None]
    out_stems = {s: stems[s] * total_gain for s in names}
    gr = gain_env / g if False else gain_env
    return out_stems, hist, float(dbv(gain_env.max())), float(dbv(gain_env.min()))


# ----------------------------------------------------------------------------- analysis
def env_db(x, win=0.005):
    e = uniform_filter1d((x.astype(np.float64) ** 2).mean(1), max(1, int(win * SR)))
    return 10 * np.log10(e + 1e-20)


def detect_onsets(x, t_lo, t_hi):
    import librosa
    a, b = int(t_lo * SR), int(t_hi * SR)
    y = x[a:b].mean(1).astype(np.float32)
    hop = 128
    oenv = librosa.onset.onset_strength(y=y, sr=SR, hop_length=hop, n_mels=96, fmax=12000)
    on = librosa.onset.onset_detect(onset_envelope=oenv, sr=SR, hop_length=hop, units="time", backtrack=False,
                                    delta=0.08, wait=2)
    return [round(t_lo + float(t), 4) for t in on]


def onset_near(onsets, t, tol=0.06):
    c = [o for o in onsets if abs(o - t) <= tol]
    return min(c, key=lambda o: abs(o - t)) if c else None


def stop_metrics(mix, t_stop):
    i = int(round(t_stop * SR))
    pre = mix[i - int(0.1 * SR): i - int(0.005 * SR)]
    e = env_db(mix, 0.001)
    pre_db = 10 * np.log10(np.mean(pre.astype(np.float64) ** 2) + 1e-20)
    seg = e[i - int(0.01 * SR): i + int(0.5 * SR)]
    t = (np.arange(len(seg)) - int(0.01 * SR)) / SR + t_stop
    drop40 = next((float(tt) for tt, v in zip(t, seg) if tt > t_stop - 0.01 and v < pre_db - 40), None)
    drop60 = next((float(tt) for tt, v in zip(t, seg) if tt > t_stop - 0.01 and v < pre_db - 60), None)

    def lvl(a_, b_):
        s_ = mix[int(a_ * SR): int(b_ * SR)].astype(np.float64)
        return round(10 * np.log10(np.mean(s_ ** 2) + 1e-20), 1)

    return dict(stop_time=t_stop, rms_before_dbfs=round(pre_db, 1),
                level_drop_40db_at=round(drop40, 4) if drop40 else None,
                level_drop_60db_at=round(drop60, 4) if drop60 else None,
                rms_0_to_10ms_after=lvl(t_stop, t_stop + 0.01), rms_10_to_50ms_after=lvl(t_stop + 0.01, t_stop + 0.05),
                rms_50_to_250ms_after=lvl(t_stop + 0.05, t_stop + 0.25))


def click_scan(x, thresh=10.0):
    """Sample-to-sample discontinuities: |2nd difference| far above its local (±25 ms) level."""
    out = []
    for c in range(2):
        d2 = np.abs(np.diff(x[:, c].astype(np.float64), 2))
        loc = np.sqrt(uniform_filter1d(d2 ** 2, int(0.05 * SR), mode="nearest")) + 1e-9
        pk = np.nonzero((d2 > thresh * loc) & (d2 > 10 ** (-60 / 20)))[0]
        out += [round((p + 1) / SR, 4) for p in pk]
    out = sorted(set(out))
    merged = []
    for t in out:
        if not merged or t - merged[-1] > 0.01:
            merged.append(t)
    return merged


def seam_metrics(sig, seams_s, win=0.15):
    e = env_db(sig, 0.010)
    res = []
    import librosa
    S = np.abs(librosa.stft(sig.mean(1).astype(np.float32), n_fft=2048, hop_length=480))
    L = np.log(S + 1e-6)
    flux = np.r_[0, np.maximum(np.diff(L, axis=1), 0).sum(0)]
    med_flux = float(np.median(flux[int(1.0 * SR / 480):]))
    for s in seams_s:
        i = int(s * SR)
        a, b = i - int(0.4 * SR), i + int(0.4 * SR)
        if a < 0 or b > len(e):
            continue
        tt = np.arange(a, b)
        near = np.abs(tt - i) < int(win * SR)
        fit = np.polyfit(tt[~near], e[a:b][~near], 1)
        dev = float(np.max(np.abs(e[a:b][near] - np.polyval(fit, tt[near]))))
        j = int(s * SR / 480)
        fl = float(flux[max(0, j - 3): j + 4].max() / (med_flux + 1e-9))
        res.append(dict(seam_s=round(s, 3), envelope_dev_db=round(dev, 2), flux_ratio=round(fl, 2)))
    return res


def tuning_test(lib, used):
    """Render isolated notes and measure them with pYIN (independent of the FFT calibration)."""
    import librosa
    rep = {}
    for name in ("ped16", "ped8", "open", "ged", "vln_sus", "va_sus", "vc_sus", "cb_sus", "piano", "harp",
                 "vln_trem", "va_trem", "vc_trem"):
        if name not in used:
            continue
        inst = lib[name]
        notes = sorted(used[name])
        rows = []
        for m in notes:
            layer = 1
            sig, pre = render_note(inst, m, 1.7, layer=layer, attack=0.004, release=0.05)
            f = hz(m)
            if inst.kind == "pluck":
                seg = sig[pre + int(0.06 * SR): pre + int(1.0 * SR)].mean(1)
            else:
                seg = sig[pre + int(0.45 * SR): pre + int(1.65 * SR)].mean(1)
            fl = 2 ** (int(np.ceil(np.log2(4 * SR / (f * 0.94)))))
            fl = int(min(max(fl, 2048), 16384))
            f0, vf, _ = librosa.pyin(seg.astype(np.float32), fmin=f * 2 ** (-1 / 12), fmax=f * 2 ** (1 / 12), sr=SR,
                                     frame_length=fl, hop_length=fl // 4, resolution=0.01)
            v = f0[~np.isnan(f0)]
            if len(v) < 3:
                rows.append(dict(note=NAME(m), cents=None))
                continue
            c = float(1200 * np.log2(np.median(v) / f))
            rows.append(dict(note=NAME(m), cents=round(c, 1)))
        cs = [abs(r["cents"]) for r in rows if r["cents"] is not None]
        rep[name] = dict(notes=rows, n=len(rows), measured=len(cs),
                         mean_abs_cents=round(float(np.mean(cs)), 2) if cs else None,
                         max_abs_cents=round(float(np.max(cs)), 2) if cs else None)
        log(f"tuning {name}: mean |c| {rep[name]['mean_abs_cents']} max {rep[name]['max_abs_cents']} ({len(cs)}/{len(rows)})")
    # timpani: principal mode of the rendered hits
    trows = []
    for m in sorted(used.get("timp", [])):
        sig, pre = render_note(lib["timp"], m, 2.0, layer=4, release=0.1)
        f = timp_principal(sig.mean(1).astype(np.float64), SR)
        trows.append(dict(note=NAME(m), principal_hz=round(f, 2), cents=round(float(1200 * np.log2(f / hz(m))), 1)))
    rep["timp"] = dict(notes=trows, method="principal (1,1) mode located by its 1 : 1.5 : 2 partners")
    return rep


def loop_test(lib):
    out = {}
    for name, note in (("ged", "D4"), ("ped16", "D1"), ("vln_sus", "A5")):
        LOOPS.clear()
        sig, pre = render_note(lib[name], N(note), 26.0, layer=1, attack=0.004, release=0.2, tag=f"test {name} {note}")
        seams = [s_ + 0.0 for s_ in (LOOPS[0]["seams_s"] if LOOPS else [])]
        out[f"{name} {note} 26 s"] = dict(loop=LOOPS[0] if LOOPS else None, seams=seam_metrics(sig, seams),
                                          clicks=click_scan(sig))
    return out


def plots(mix, cue, out_dir, stops):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from scipy.signal import stft

    mono = mix.mean(1).astype(np.float64)
    f, t, Z = stft(mono, fs=SR, nperseg=4096, noverlap=4096 - 480)
    S = 20 * np.log10(np.abs(Z) + 1e-9)
    S -= S.max()
    keep = (f >= 25) & (f <= 16000)
    fig, ax = plt.subplots(2, 1, figsize=(24, 10), dpi=100, gridspec_kw=dict(height_ratios=[4, 1]), sharex=True)
    ax[0].pcolormesh(t, f[keep], S[keep], shading="auto", cmap="magma", vmin=-90, vmax=0, rasterized=True)
    ax[0].set_yscale("log")
    ax[0].set_ylim(25, 16000)
    ax[0].set_ylabel("Hz")
    for h in cue["hits"]:
        for a_ in ax:
            a_.axvline(h, color="cyan", lw=1.0, alpha=0.85)
        ax[0].text(h + 0.05, 17500, f"{h:g}", color="cyan", fontsize=10, va="bottom")
    for tk in cue.get("ticks", []):
        ax[0].plot([tk, tk], [25, 32], color="white", lw=1.5)
    for sgm in cue["segments"]:
        ax[0].text(sgm["start"] + 0.05, 30, sgm["id"], color="white", fontsize=8, rotation=90, va="bottom")
    e = env_db(mix, 0.05)
    tt = np.arange(len(e)) / SR
    ax[1].plot(tt[::240], e[::240], color="black", lw=0.8)
    ax[1].set_ylim(-80, 0)
    ax[1].set_ylabel("dBFS (50 ms)")
    ax[1].set_xlabel("seconds")
    ax[1].set_xlim(0, len(mono) / SR)
    ax[0].set_title("THE CITY CAN WAIT - original score (music.wav). Cyan: cue-sheet hits; white marks at the "
                    "bottom: clock ticks (SFX)")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "spectrogram.png"))
    plt.close(fig)
    # zoom on the stops
    fig, ax = plt.subplots(2, 2, figsize=(16, 8), dpi=100)
    for k, ts in enumerate(stops):
        a, b = int((ts - 0.3) * SR), int((ts + 0.35) * SR)
        seg = mono[a:b]
        tt = ts - 0.3 + np.arange(len(seg)) / SR
        e1 = env_db(mix[a:b], 0.001)
        ax[0, k].plot(tt, e1, lw=0.8)
        ax[0, k].axvline(ts, color="r", lw=0.8)
        ax[0, k].set_ylim(-120, 0)
        ax[0, k].set_title(f"stop at {ts:.3f} s: 1 ms RMS envelope (dBFS)")
        f2, t2, Z2 = stft(seg, fs=SR, nperseg=1024, noverlap=1024 - 96)
        S2 = 20 * np.log10(np.abs(Z2) + 1e-9)
        ax[1, k].pcolormesh(t2 + ts - 0.3, f2[1:], S2[1:], shading="auto", cmap="magma", vmin=S2.max() - 100,
                            vmax=S2.max())
        ax[1, k].set_yscale("log")
        ax[1, k].set_ylim(30, 20000)
        ax[1, k].axvline(ts, color="cyan", lw=0.8)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "stops.png"))
    plt.close(fig)


DESCRIPTION = [
    dict(t="0.0-2.0", bar="cold open", harmony="D (open)", what="16' + 8' pedal D1/D2 swells out of silence "
         "(swell box opening); one high quiet tone A5 (stopped-flute rank + violins pp) above. No pulse. "
         "Everything (dry, hall, strings) cut dead at 2.000 with a 4 ms fade; only a 0.12 s RT60 room reflection "
         "(gone by 2.25) survives."),
    dict(t="2.0-3.0", bar="silence", harmony="-", what="Digital silence from 2.25 s (room for the SFX boom + first tick)."),
    dict(t="3.0-7.0", bar="1 (4/4, 8ths)", harmony="Dm over pedal D", what="Original 3+3+2 ostinato in 8ths "
         "(A4 D5 F5 | A4 D5 G5 | A4 E5) on the stopped flute 8', the principal chorus (Man III Open, 16'+8') "
         "creeping in underneath; pedal D1+D2 held; crescendo pp -> mp; swell box opening."),
    dict(t="7.0-9.0", bar="2a (16ths)", harmony="Bb (lydian colour: the cell's E5 is the #11)", what="The same "
         "upper figure doubles to 16ths with its anchor moved to Bb4; pedal Bb1 pulses on 7 and 8; soft timpani Bb."),
    dict(t="9.0-11.0", bar="2b (16ths)", harmony="Gm6", what="Anchor G4; pedal G1 pulses in 8ths; stopped flute "
         "doubles an octave higher; cello + viola tremolo enter at 9.000 and crescendo; timpani G."),
    dict(t="11.0", bar="lift", harmony="F", what="Accent on 11.000: timpani F + gran cassa + sub boom + "
         "suspended-cymbal hit; strings jump to loud tremolo with violins; ostinato doubles again to 32nds."),
    dict(t="11.0-13.5", bar="3 (32nds)", harmony="F -> G -> A (rising whole steps, bIII-IV-V)", what="The cell "
         "transposed up a whole step each beat (C5 F5 A5 ..., D5 G5 B5 ..., E5 A5 C#6 E5), Open 16'+8' + flute + "
         "lower octave; pedal F1/G1 in 8ths then A1 held; a quartal organ cluster (A3 E4 A4 B4 D5 E5 A5 B5 D6 E6) "
         "stacks upward one note every 0.25 s; violins and violas glissando up an octave (riser); timpani 8ths, "
         "timpani roll on A from 13.0; suspended-cymbal crescendo peaking exactly at 13.5. Peak = unresolved A "
         "(dominant) at 13.500."),
    dict(t="13.500", bar="HARD STOP", harmony="-", what="Everything (dry and reverb returns, all stems) cut "
         "dead with a 4 ms raised-cosine; no room tail."),
    dict(t="13.5-15.0", bar="time stops", harmony="D", what="Only the 16' pedal D1 (+ 8' D2), dark (swell box "
         "closed), breathing in from silence (13.5 -> 13.95), swelling to 14.45, ebbing at 15.0, then fading out "
         "by 16.6 under the kitchen."),
    dict(t="15.0-21.0", bar="bloom (3 x 2 bars of 2 s)", harmony="Bbmaj9 - F/A - Gm9", what="Warmth: stopped-flute "
         "chords (quiet ranks) over the quiet 8' pedal (Bb2-A2-G2), cellos/violas pp, violins hold a high A5 halo "
         "(the cold open's tone); harp Bb at 15.0; the ORIGINAL piano motif, sparse, between the ticks: "
         "A4 (15.5) D5 (16.0) E5 (16.5) F5 (17.5) ... E5 (19.5) D5 (20.0)."),
    dict(t="21.0-25.0", bar="pour, build", harmony="Dm(add9) - Bb", what="Match cut: harp + bass D on 21.000, "
         "piano restates A-D-E-F (21.5-23.5) in octaves, ostinato returns in 8ths at 23.0, strings and organ "
         "crescendo from pp, Open chorus added."),
    dict(t="25.0-27.0", bar="build", harmony="Gm - A7", what="Ostinato in 16ths, pedal G1 then A1, strings to "
         "loud layers, timpani roll on A from 25.5 crescendo into 27.0, cymbal crescendo peaking at 27.0."),
    dict(t="27.0-29.0", bar="CLIMAX", harmony="Bb - C (bVI - bVII)", what="Full organ (16' pedal, 8' pedal, "
         "Open 16'+8' chords, flute), strings tutti, timpani Bb (27.0) and C (28.0) + gran cassa + sub boom; top line "
         "D6 - E6 in organ and violins (the piano motif in augmentation)."),
    dict(t="29.0", bar="RESOLUTION", harmony="D major (Picardy)", what="D-major chord, full organ + strings, "
         "top F#6 completes the motif D-E-F#; timpani D2, gran cassa, sub boom, tam-tam. The rise that was cut at "
         "13.5 finally resolves."),
    dict(t="29.0-36.0", bar="decay", harmony="D major", what="Chord held to 29.6 then decays slowly (about -7 dB "
         "at 31.5, -17 dB at 33, -42 dB at 35.5, swell box closing); one last quiet organ note A5 (32.5-35.1, "
         "the opening's high tone); notes end by 35.9, church reverb dies out; tam-tam faded out by 35.6."),
    dict(t="36.0-37.5", bar="silence", harmony="-", what="Reverb residue only, below -60 dBFS after 36.5; "
         "exact digital silence at the end (final 0.25 s fade)."),
]


# ----------------------------------------------------------------------------- main
def _json_default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, (set, tuple)):
        return sorted(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    cue_path, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    cue = json.load(open(cue_path))
    dur = float(cue["duration"])
    lib = build_library()
    events = build_score()
    for e in events:  # calibrate only what the score uses
        if "inst" in e:
            lib[e["inst"]].calibrate()
    log("calibration done")
    ir, ir_info = church_ir()
    rir = room_ir()
    LOOPS.clear()
    buses, used, n = render(lib, events, dur)
    score_loops = list(LOOPS)
    log(f"rendered {len(events)} events into {len(buses)} buses")
    # dry organ ostinato onsets (timing check before reverb)
    org_dry = sum(v[:n] for (s, b), v in buses.items() if s == "organ")
    stems = mixdown(buses, n, ir, rir)
    del buses
    log("mixdown done")
    stems, mhist, gmax, gmin = master(stems)
    mix = sum(stems[s] for s in ("organ", "piano", "strings", "perc"))
    for s in ("organ", "piano", "strings", "perc"):
        sf.write(os.path.join(out_dir, f"{s}.wav"), stems[s], SR, subtype="PCM_24")
    sf.write(os.path.join(out_dir, "music.wav"), mix, SR, subtype="PCM_24")
    log("wrote wavs")

    # ---------------- QC / report
    m = pyln.Meter(SR)
    rd, _ = sf.read(os.path.join(out_dir, "music.wav"), dtype="float64", always_2d=True)
    lufs = m.integrated_loudness(rd)
    tp = true_peak_db(rd)
    seg_lufs = []
    for sg in cue["segments"]:
        a, b = int(sg["start"] * SR), int(sg["end"] * SR)
        if b - a < int(0.4 * SR):
            seg_lufs.append(dict(id=sg["id"], start=sg["start"], end=sg["end"], lufs=None, note="shorter than 0.4 s"))
            continue
        v = m.integrated_loudness(rd[a:b])
        seg_lufs.append(dict(id=sg["id"], start=sg["start"], end=sg["end"],
                             lufs=round(v, 2) if np.isfinite(v) else None,
                             peak_dbfs=round(dbv(np.abs(rd[a:b]).max()), 2)))
    ons_mix = detect_onsets(rd, 2.5, 31.0)
    hits = []
    for h in cue["hits"]:
        o = onset_near(ons_mix, h)
        hits.append(dict(cue=h, onset_in_mix=o, error_ms=round((o - h) * 1000, 1) if o is not None else None))
    # ostinato grid on the dry organ
    ons_org = detect_onsets(org_dry, 2.8, 13.45)
    grid = sorted({round(e["t"], 4) for e in events if e.get("role") == "ostinato" and e["t"] < 13.5})
    errs = []
    for g in grid:
        o = onset_near(ons_org, g, tol=0.05)
        if o is not None:
            errs.append((o - g) * 1000)
    stops = [stop_metrics(rd, 2.0), stop_metrics(rd, 13.5)]
    clicks = click_scan(rd)
    expected = sorted({round(e["t"], 3) for e in events if "t" in e} | {2.0, 13.5})
    clicks_unexpl = [c for c in clicks if min(abs(c - x) for x in expected) > 0.03]
    tun = tuning_test(lib, used)
    lt = loop_test(lib)
    seam_score = []
    for L_ in score_loops:
        seam_score.append(L_)
    plots(rd, cue, out_dir, [2.0, 13.5])
    silence = dict(
        rms_2_25_to_3_0_dbfs=round(10 * np.log10(np.mean(rd[int(2.25 * SR): int(2.97 * SR)] ** 2) + 1e-20), 1),
        rms_36_0_to_36_5_dbfs=round(10 * np.log10(np.mean(rd[int(36.0 * SR): int(36.5 * SR)] ** 2) + 1e-20), 1),
        rms_36_5_to_37_5_dbfs=round(10 * np.log10(np.mean(rd[int(36.5 * SR):] ** 2) + 1e-20), 1),
        last_sample_abs=float(np.abs(rd[-1]).max()))
    mapping = {}
    for name, inst in lib.items():
        if not inst.ready:
            continue
        mapping[name] = [dict(file=os.path.relpath(s.path, VSCO), nominal=NAME(s.nominal), layer=s.layer,
                              measured_midi=round(s.meas, 3),
                              cents_vs_nominal=round(100 * (s.meas - s.nominal), 1) if inst.kind != "timp" else None,
                              gain_db=round(dbv(s.gain), 1), mono_fold=s.mono >= 0, lr_corr=round(s.corr, 2),
                              sub_octave_db=round(s.sub16, 1) if s.sub16 > -98 else None)
                         for s in inst.samples]
    report = dict(
        title=cue.get("title"), file="music.wav", duration_s=round(len(rd) / SR, 6), samples=len(rd), sample_rate=SR,
        bit_depth=24, channels=2, key="D minor -> D major (Picardy resolution at 29.0)", tempo_bpm=60,
        meter="4/4, one beat = 1 s = one clock tick; note values halve per cue: 8ths (3-7), 16ths (7-11), 32nds (11-13.5)",
        grid_s=dict(ostinato_8ths=[3.0 + 0.5 * i for i in range(8)],
                    ostinato_16ths=[7.0 + 0.25 * i for i in range(16)],
                    ostinato_32nds=[11.0 + 0.125 * i for i in range(20)],
                    pour_8ths=[23.0, 23.5, 24.0, 24.5], pour_16ths=[25.0 + 0.25 * i for i in range(16)]),
        stops=dict(hard_stop_1=2.0, hard_stop_2=13.5, climax=[27.0, 29.0], resolution=29.0,
                   music_silent_from=36.0, measurements=stops),
        bar_by_bar=DESCRIPTION,
        loudness=dict(integrated_lufs=round(lufs, 2), true_peak_dbtp_4x=round(tp, 2),
                      sample_peak_dbfs=round(dbv(np.abs(rd).max()), 2), master_iterations=mhist,
                      master_gain_db_range=[round(gmin, 2), round(gmax, 2)],
                      note="limiter gain envelope applied identically to all stems, so stems sum exactly to the mix"),
        per_segment_lufs=seg_lufs,
        hit_onsets_vs_cue=dict(method="librosa onset detection on music.wav (hop 2.7 ms), nearest onset within 60 ms",
                               hits=hits,
                               note="2.0 and 13.5 are stops (see stops); 31.5 and 36.5 carry no musical attack by design"),
        ostinato_timing=dict(method="onsets detected on the dry organ bus (before reverb) vs the grid",
                             grid_notes=len(grid), detected=len(errs),
                             mean_error_ms=round(float(np.mean(errs)), 2) if errs else None,
                             mean_abs_error_ms=round(float(np.mean(np.abs(errs))), 2) if errs else None,
                             max_abs_error_ms=round(float(np.max(np.abs(errs))), 2) if errs else None),
        tuning_cents=tun,
        loops=dict(in_score=seam_score, test_renders=lt,
                   method="power-preserving crossfade (equal-power, compensated for the measured correlation rho of "
                          "the two overlapping segments) of 0.25 s at upward zero crossings; seam check = 10 ms RMS "
                          "envelope deviation from a local linear fit (+-150 ms) and spectral-flux ratio vs median"),
        clicks=dict(method="|2nd difference| > 10x its +-25 ms RMS and > -60 dBFS", count=len(clicks),
                    times=clicks[:80], unexplained=clicks_unexpl[:80],
                    note="flagged times that coincide (+-30 ms) with scheduled note/hit onsets are instrument attacks"),
        silence=silence,
        reverb=dict(type="synthetic church IR (early reflections + decorrelated exponential noise, per-octave RT60)",
                    **ir_info, gates="hall + dry gated at 2.000 and 13.500 (4 ms raised cosine); room tail RT60 0.12 s "
                                     "only after 2.000"),
        highpass="4th-order Butterworth 28 Hz on every bus (before the gates)",
        stems=["organ.wav", "piano.wav", "strings.wav", "perc.wav"],
        instruments=dict(
            organ="VSCO-2 CE pipe organ (Ivy Audio / S. Dalzell): Man III Open plenum (Loud, labelled at 8' pitch, 16' "
                  "rank audible in the treble), Man III quiet stopped flute 8' (Quiet), Pedal 16' (Loud), Pedal 8' (Quiet)",
            strings="VSCO-2 CE violin/viola/cello sections (sustain vibrato, tremolo), solo contrabass, harp",
            piano="VSCO-2 CE upright piano (Ivy Audio)",
            perc="VSCO-2 CE timpani (hits, rolls), gran cassa, suspended cymbal (hit, crescendos), tam-tam; synthetic sub boom",
            licence="VSCO-2 Community Edition: CC0 1.0 (LICENSE in /home/user/sgossner/vsco-2-ce); organ/piano Info.txt: "
                    "'Bearer is granted right to redistribute'; credit to Simon Dalzell (Ivy Audio) and Versilian "
                    "Studios encouraged"),
        sample_mapping=dict(
            method="nominal octave per rank established by partial analysis (odd partials of f/2 present or not), "
                   "then fine pitch = power-weighted centroid of the 4 strongest partials (FFT of the steady part)",
            ranks={"open": "Rode_Man3Open_NN: sounding 8' pitch = NN+35 (C2..C7); a 16' series (NN+23) is present, "
                           "strong above C4", "ped16": "Rode_Pedal_NN: NN+23 (16', C1..F#3)",
                   "ged": "NT5_Man3Quiet_NNN: NNN-86 (stopped flute 8', C2..C7; odd harmonics only)",
                   "ped8": "NT5_PedalQuiet_NNN: NNN-28 (C2..F#4)",
                   "strings": "VSCO string files are named one octave low: sounding = name + 12",
                   "piano": "MappingChart.txt (file number -> key)", "harp": "names correct"},
            samples=mapping),
        not_verified_by_ear=[
            "I cannot listen. Musical quality, balance, realism of the sampled instruments, the feel of the "
            "accelerating ostinato and the emotional effect were judged only from spectrograms, loudness curves, "
            "onset and pitch measurements.",
            "Whether the Open plenum is perceived at 8' or with a strong 16' colour in the treble is a perceptual "
            "question; measured: both series present.",
            "String vibrato samples pitch-shifted by up to 4 semitones (top of the violin line, F#6) may sound "
            "slightly thin; organ and flute double them.",
        ],
        rendered_by="compose.py (deterministic)", render_seconds=round(time.time() - T0, 1),
    )
    with open(os.path.join(out_dir, "score_report.json"), "w") as fh:
        json.dump(report, fh, indent=1, default=_json_default)
    log(f"done: {lufs:.2f} LUFS, TP {tp:.2f} dBTP")


if __name__ == "__main__":
    main()
