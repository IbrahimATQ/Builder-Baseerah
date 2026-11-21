#!/usr/bin/env python3
"""WARSZAWA: the sound design layer and the re-recording mix, laid to the picture through the cue sheet.

Spec: data/sound3.json (written by data/sound3.py). Every film time in it is a number or a reference to the cue
sheet (data/cuesheet3.json), resolved HERE, at mix time, so that a re-run follows any nudge of the picture:
    "@latch", "@latch+0.15", "@climax-1.5"     an event of the cue sheet (+- seconds)
    "@cup", "@cup.film_in", "@open.start"      a shot (its first visible frame) or one of its attributes
    "@duration"                                the film's length
Top level:
  {"cuesheet": "cuesheet3.json" (relative to the spec), "duration": "@duration", "buses": ["city", ...],
   "score": {"file", "gain_db", "auto": {"t0", "t1", "city_under_db"}, "end_fade": [t0, t1]}
            (used only if the file exists at mix time: the score is composed in parallel; "auto" sets the score's
            gain so that the city stem sits `city_under_db` under it in that window, i.e. at the climax),
   "music_ducks": [[t0, t1, dB]], "ceiling_db": -2.0, "targets": {"mix": -14.0, "sfx_only": -16.0},
   "sections": [[name, t0, t1]], "elements": [...]}
An element is one sound on one bus (stem):
  "id", "bus", "what", "file", "licence"
  where it comes from in the file and where it lies in the film, one of:
    "src": [in, out], "start": t             the part [in, out] from film time `start` (at real speed, or `tempo`)
    "src": [in, out], "sync": [file_t, t]    the same, placed so that the moment file_t lands on film time t
    "start", "end", "timemap": {...}         follows a shot's speed curve (slow motion, 0.8x): file time =
                                             anchor + rate x (the shot's source time - its value at the anchor);
                                             {"shot": id} alone is the clip's own sound in sync with its picture;
                                             {"shot", "rate", "anchor": [t, file_t]} or {"shot", "fit": [[t0, f0],
                                             [t1, f1]]} lays a library sound on the same curve
    "start", "end", "splice": [[in, out], ...], "xfade": s   pieces of one file joined by crossfades (room tone),
                                             looped if the pieces are shorter than the span
  Time is never changed by resampling: "tempo" and every timemap are rendered with rubberband (pitch kept), one
  render per constant-speed run, crossfaded across the speed ramps (sync error < 15 ms inside a ramp).
  "pitch" (semitones, by resampling, for a library sound that should sound smaller), "repair": [[t0, t1, donor_t0]]
  (source spans replaced by clean material of the same file), "notch": [Hz], "hp", "lp" (2nd order),
  "detone": {"thr_db", "fmin", "fmax", "tlen"} (sustained tonal lines - street music, appliance whine - pulled
  down to the noise floor around them), "polarity": "flip_right", "width" (side gain), "pan" (-1..1),
  "reverb": {"rt60", "mix", "predelay"}, "slap": {"delays": [s], "gains_db": [dB], "lp": Hz} (facade reflections),
  "rms_db" | "peak_db" (level of the processed sound before gain), "crest_db" (peaks held to RMS + this), "match": {"to": id, "at": t, "win": s} (gain
  that makes this sound as loud just after `at` as `to` just before it: an inaudible hand-over between takes),
  "gain_db", "gain_keys": [[t, dB]], "fade_in", "fade_out", "fade_shape": "gain" (sin^2) | "power" (sin: for a
  crossfade between two different takes),
  "lp_keys": [[t, Hz]], "lp_order": THE GLASS - a low-pass whose cutoff moves with film time (interpolated in
  log-frequency), applied as an STFT mask with a cutoff per 5 ms frame, so it sweeps without zipper noise;
  >= 18 kHz is fully open (no filter at all),
  "onset": t (the report measures the sound's onset against this film time; +-20 ms is in sync), "onset_mode",
  "step": t (the report measures a level step of the sound, e.g. the clip's own jump, against this film time),
  "skip_after": t (the element is left out if it would start after t: a drip that would cross a cut).
Outputs in OUT_DIR: mix.wav (score + sound; -14 LUFS, true peak <= -2 dBTP), sfx_only.wav (all but the score,
-16 LUFS), one stem per bus <bus>.wav (float, before normalisation: the stems sum to the sound bus that sfx_only and
the mix are made from), music_bus.wav (only with a score: the score after its gain, ducks and end fade, on the same
scale, so stems + music_bus = the mix before its master gain and limiter), sound_report.json.
Usage: python pipeline/sound3.py data/sound3.json OUT_DIR [--no-score]
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy.ndimage import median_filter, uniform_filter
from scipy.signal import butter, istft, iirnotch, resample_poly, sosfilt, stft, tf2sos

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sound2 import SR, decode, env, limit, place, reverb, rms_db, true_peak_db  # noqa: E402  (the previous mixer)

_CACHE: dict[str, np.ndarray] = {}


def load(path: str) -> np.ndarray:
    """The whole file, decoded once to 48 kHz stereo (float32 in the cache)."""
    if path not in _CACHE:
        _CACHE[path] = decode(path).astype(np.float32)
    return _CACHE[path]


def take(x: np.ndarray, i0: int, i1: int) -> np.ndarray:
    """x[i0:i1] in float64, zero-padded where the range leaves the array."""
    out = np.zeros((max(i1 - i0, 0), 2))
    a, b = max(i0, 0), min(i1, len(x))
    if b > a:
        out[a - i0:b - i0] = x[a:b]
    return out


# ---- the cue sheet ------------------------------------------------------------------------------------------------
class Cues:
    def __init__(self, path: str):
        cs = json.load(open(path, encoding="utf-8"))
        self.path = path
        self.duration = float(cs["duration"])
        self.fps = cs["fps"]
        self.ramp = float(cs.get("ramp_s", 0.3))
        self.events = {e["key"]: float(e["t"]) for e in cs["events"]}
        self.shots = {s["id"]: s for s in cs["shots"]}

    def t(self, v) -> float:
        if isinstance(v, (int, float)):
            return float(v)
        m = re.fullmatch(r"@([A-Za-z0-9_]+)(?:\.([a-z_]+))?\s*([+-]\s*\d+(?:\.\d+)?)?", v.strip())
        if not m:
            raise ValueError(f"bad time {v!r}")
        ref, attr, off = m.groups()
        if ref == "duration":
            base = self.duration
        elif attr:
            base = float(self.shots[ref][attr])
        elif ref in self.events:
            base = self.events[ref]
        elif ref in self.shots:
            base = float(self.shots[ref]["film_in"])
        else:
            raise KeyError(f"{v!r}: no event or shot {ref!r} in {self.path}")
        return base + (float(off.replace(" ", "")) if off else 0.0)

    def keys(self, ks):
        return [[self.t(a), float(b)] for a, b in ks]

    def runs(self, sid: str) -> list[list[float]]:
        """The shot's speed curve as straight runs [film t0, film t1, ref film t, source t at ref, speed]: source(t) =
        ref source + speed x (t - ref t). The first and last runs are extended beyond the shot. Away from the eased
        ramps the runs are exact (the cue sheet eases speed changes with a symmetric box filter)."""
        s = self.shots[sid]
        t, out = float(s["film_in"]), []
        for a, b, v in s["segs"]:
            d = (b - a) / v
            out.append([t, t + d, t, a, v])
            t += d
        out[0][0], out[-1][1] = -1e9, 1e9
        return out

    def src(self, sid: str, t: float) -> float:
        """The source position the picture shows at film time t (the cue sheet's per-frame table, eased ramps)."""
        s = self.shots[sid]
        tab = np.asarray(s["src_at_frame"])
        ft = (s["first_frame"] + np.arange(len(tab))) / self.fps
        if ft[0] <= t <= ft[-1]:
            return float(np.interp(t, ft, tab))
        r = self.runs(sid)[0 if t < ft[0] else -1]
        return r[3] + r[4] * (t - r[2])

    def check_runs(self, sid: str) -> float:
        """Largest gap (s) between the straight runs and the cue sheet's per-frame table, away from the ramps."""
        s = self.shots[sid]
        tab = np.asarray(s["src_at_frame"])
        ft = (s["first_frame"] + np.arange(len(tab))) / self.fps
        rs = self.runs(sid)
        bounds = [r[1] for r in rs[:-1]]
        err = 0.0
        for t, v in zip(ft, tab):
            if any(abs(t - b) < self.ramp / 2 + 1.5 / self.fps for b in bounds):
                continue
            for r in rs:
                if r[0] <= t < r[1]:
                    err = max(err, abs(r[3] + r[4] * (t - r[2]) - v))
        return err


# ---- signal processing ---------------------------------------------------------------------------------------------
def sos_filters(e: dict) -> list:
    out = []
    for hz in e.get("notch", []):
        b, a = iirnotch(hz, e.get("notch_q", 12.0), fs=SR)
        out.append(tf2sos(b, a))
    if e.get("hp"):
        out.append(butter(2, e["hp"], "high", fs=SR, output="sos"))
    if e.get("lp"):
        out.append(butter(2, e["lp"], "low", fs=SR, output="sos"))
    return out


def apply_sos(x: np.ndarray, sos_list: list) -> np.ndarray:
    for sos in sos_list:
        x = sosfilt(sos, x, axis=0)
    return x


def rubberband(x: np.ndarray, tempo: float) -> np.ndarray:
    """Pitch-preserving time stretch (librubberband through ffmpeg). tempo < 1 = slower/longer."""
    p = subprocess.run(["ffmpeg", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                        "-af", f"rubberband=tempo={tempo:.6f}", "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                       input=np.ascontiguousarray(x, dtype=np.float32).tobytes(), capture_output=True, check=True)
    return np.frombuffer(p.stdout, np.float32).reshape(-1, 2).astype(np.float64)


def detone(x: np.ndarray, thr_db: float = 1.5, fmin: float = 60.0, fmax: float = 7000.0, tlen: float = 0.15,
           flen: float = 200.0, ratio: float = 2.0, max_db: float = 36.0) -> tuple[np.ndarray, dict]:
    """Pull sustained tonal lines down to the noise floor around them (the street musician's notes, the kitchen's
    appliance whine and mains harmonics), leaving noise and transients (footsteps, voices' breath, water) alone.
    A bin's excess over the median of its neighbouring frequencies, held for `tlen` (median over time), is reduced
    by `ratio` x (excess - thr_db); the gain is smoothed over 3 frames x 3 bins. On stationary noise it changes the
    level by < 0.5 dB and leaves the noise's fluctuation as it was (checked), so it does not "swirl"."""
    n_fft, hop = 4096, 512
    f, _, Z = stft(x.T, SR, nperseg=n_fft, noverlap=n_fft - hop, boundary="even", padded=True)
    M = np.abs(Z).mean(axis=0) + 1e-12
    kf = max(3, int(round(flen / (SR / n_fft))) | 1)
    kt = max(3, int(round(tlen * SR / hop)) | 1)
    F = median_filter(M, size=(kf, 1), mode="nearest")
    E = 20 * np.log10(median_filter(M / F, size=(1, kt), mode="nearest"))
    red = np.clip((E - thr_db) * ratio, 0.0, max_db)
    red[(f < fmin) | (f > fmax)] = 0.0
    red = uniform_filter(red, size=(3, 3), mode="nearest")
    g = 10 ** (-red / 20)
    _, y = istft(Z * g[None], SR, nperseg=n_fft, noverlap=n_fft - hop, boundary=True)
    y = y.T[: len(x)]
    if len(y) < len(x):
        y = np.vstack([y, np.zeros((len(x) - len(y), 2))])
    return y, {"mean_reduction_db_80_4k": round(float(red[(f > 80) & (f < 4000)].mean()), 2),
               "max_reduction_db": round(float(red.max()), 1), "level_change_db": round(rms_db(y) - rms_db(x), 2)}


def glass(a: np.ndarray, t0: float, keys: list[list[float]], order: int = 2) -> np.ndarray:
    """THE GLASS: a low-pass whose cutoff follows `keys` [[film s, Hz], ...] (log-interpolated, held outside).
    STFT mask, Butterworth magnitude of `order`, one cutoff per 256-sample frame (5.3 ms) under 75 % overlap-add,
    so the sweep is smooth. Cutoffs from 12 to 18 kHz fade the filter out; >= 18 kHz is no filter at all."""
    n_fft, hop = 1024, 256
    f, tt, Z = stft(a.T, SR, nperseg=n_fft, noverlap=n_fft - hop, boundary="even", padded=True)
    tk = np.array([k[0] for k in keys])
    hk = np.log(np.array([k[1] for k in keys]))
    fc = np.exp(np.interp(t0 + tt, tk, hk))
    H = 1.0 / np.sqrt(1.0 + (f[:, None] / fc[None, :]) ** (2 * order))
    w = np.clip((np.log(18000.0) - np.log(fc)) / (np.log(18000.0) - np.log(12000.0)), 0.0, 1.0)
    H = H ** w[None, :]
    _, y = istft(Z * H[None], SR, nperseg=n_fft, noverlap=n_fft - hop, boundary=True)
    y = y.T[: len(a)]
    if len(y) < len(a):
        y = np.vstack([y, np.zeros((len(a) - len(y), 2))])
    return y


def fc_at(keys: list[list[float]], t: float) -> float:
    return float(np.exp(np.interp(t, [k[0] for k in keys], np.log([k[1] for k in keys]))))


def slap(a: np.ndarray, delays: list[float], gains_db: list[float], lp: float = 3500.0, hp: float = 150.0) -> np.ndarray:
    """Discrete reflections off the facades: each a delayed, darker copy, alternately leaning left and right."""
    n = int(max(delays) * SR) + 1
    out = np.vstack([a, np.zeros((n, 2))])
    sos = [butter(2, lp, "low", fs=SR, output="sos"), butter(1, hp, "high", fs=SR, output="sos")]
    src = apply_sos(a.mean(axis=1, keepdims=True).repeat(2, axis=1), sos)
    for k, (d, g) in enumerate(zip(delays, gains_db)):
        i = int(round(d * SR))
        lean = np.array([0.8, 0.45]) if k % 2 == 0 else np.array([0.45, 0.8])
        out[i:i + len(src)] += src * 10 ** (g / 20) * lean[None, :] * 1.1
    return out


def pan(a: np.ndarray, p: float, width: float | None) -> np.ndarray:
    if width is not None:
        m, s = (a[:, 0] + a[:, 1]) / 2, (a[:, 0] - a[:, 1]) / 2 * width
        a = np.stack([m + s, m - s], axis=1)
    if p:
        th = (p + 1) * np.pi / 4
        a = a * (np.array([np.cos(th), np.sin(th)]) * np.sqrt(2))[None, :]
    return a


def splice(x: np.ndarray, pieces: list[list[float]], xfade: float, need: float) -> np.ndarray:
    """Pieces [in, out] of one file joined by equal-power crossfades, repeated until `need` seconds are covered."""
    f = int(xfade * SR)
    out = None
    k = 0
    while out is None or len(out) < need * SR + f:
        a, b = pieces[k % len(pieces)]
        seg = take(x, int(a * SR), int(b * SR))
        if out is None:
            out = seg
        else:
            ramp = np.sin(np.linspace(0, np.pi / 2, f))[:, None]
            head = out[-f:] * np.cos(np.linspace(0, np.pi / 2, f))[:, None] + seg[:f] * ramp
            out = np.vstack([out[:-f], head, seg[f:]])
        k += 1
        if k > 400:
            raise RuntimeError("splice: pieces too short")
    return out


def repair(x: np.ndarray, x0: float, spans: list[list[float]]) -> np.ndarray:
    """Replace source spans [t0, t1] with donor material from donor_t0, matched in level, 20 ms crossfades."""
    x = x.copy()
    f = int(0.02 * SR)
    for t0, t1, d0 in spans:
        i0, i1 = int((t0 - x0) * SR), int((t1 - x0) * SR)
        j0 = int((d0 - x0) * SR)
        donor = take(x, j0 - f, j0 + (i1 - i0) + f)
        around = np.vstack([take(x, i0 - int(0.3 * SR), i0), take(x, i1, i1 + int(0.3 * SR))])
        donor *= 10 ** ((rms_db(around) - rms_db(donor)) / 20)
        w = np.ones(len(donor))
        w[:2 * f] = np.sin(np.linspace(0, np.pi / 2, 2 * f)) ** 2
        w[-2 * f:] = np.cos(np.linspace(0, np.pi / 2, 2 * f)) ** 2
        a, b = i0 - f, i1 + f
        cur = take(x, a, b)
        new = cur * (1 - w)[:, None] + donor * w[:, None]
        aa, bb = max(a, 0), min(b, len(x))
        x[aa:bb] = new[aa - a:bb - a]
    return x


def render_runs(x: np.ndarray, x0: float, runs: list[list[float]], t_start: float, t_end: float,
                xfade: float) -> np.ndarray:
    """Film [t_start, t_end] from source x (sample 0 = file time x0), following straight runs
    [film t0, film t1, ref film t, file t at ref, file seconds per film second]. One rubberband render per run
    (pitch kept), equal-power crossfades `xfade` long centred on the run boundaries (the speed ramps)."""
    N = int(round((t_end - t_start) * SR))
    out = np.zeros((N, 2))
    runs = [r for r in runs if r[1] + xfade / 2 > t_start and r[0] - xfade / 2 < t_end]
    pad = 0.35
    for k, (Ta, Tb, Tr, fr, r) in enumerate(runs):
        first, last = k == 0, k == len(runs) - 1
        lo = t_start if first else max(t_start, Ta - xfade / 2)
        hi = t_end if last else min(t_end, Tb + xfade / 2)
        if hi <= lo:
            continue
        n = int(round((hi - lo) * SR))
        f_lo = fr + r * (lo - Tr)
        i0 = int(round((f_lo - pad * r - x0) * SR))
        i1 = i0 + int(round((n / SR + 2 * pad) * r * SR)) + 1
        seg = take(x, i0, i1)
        y = seg if abs(r - 1.0) < 1e-4 else rubberband(seg, r)
        j0 = int(round(pad * SR))
        y = y[j0:j0 + n]
        if len(y) < n:
            y = np.vstack([y, np.zeros((n - len(y), 2))])
        t = lo + np.arange(n) / SR
        w = np.ones(n)
        if not first:
            w *= np.sin(np.pi / 2 * np.clip((t - (Ta - xfade / 2)) / xfade, 0, 1))
        if not last:
            w *= np.cos(np.pi / 2 * np.clip((t - (Tb - xfade / 2)) / xfade, 0, 1))
        o0 = int(round((lo - t_start) * SR))
        m = min(n, N - o0)
        out[o0:o0 + m] += (y * w[:, None])[:m]
    return out


def fades(n: int, fi: float, fo: float, shape: str = "gain") -> np.ndarray:
    """Fade in/out envelope: "gain" = sin^2/cos^2 (sound2's, for crossfades between correlated takes), "power" =
    sin/cos (equal power: two different takes crossfaded keep their summed level)."""
    if shape != "power":
        return env(n, fi, fo)
    e = np.ones(n)
    a, b = min(n, int(fi * SR)), min(n, int(fo * SR))
    if a > 0:
        e[:a] = np.sin(np.linspace(0, np.pi / 2, a))
    if b > 0:
        e[-b:] *= np.cos(np.linspace(0, np.pi / 2, b))
    return e


def keyed(keys: list[list[float]], t0: float, n: int) -> np.ndarray:
    t = t0 + np.arange(n) / SR
    return 10 ** (np.interp(t, [k[0] for k in keys], [k[1] for k in keys]) / 20)


def env_db(a: np.ndarray, w: float = 0.001) -> np.ndarray:
    m = a.mean(axis=1) if a.ndim > 1 else a
    h = int(w * SR)
    n = len(m) // h
    return 10 * np.log10(np.mean(m[: n * h].reshape(n, h) ** 2, axis=1) + 1e-14)


def onset_near(a: np.ndarray, t0: float, target: float, before: float = 0.12, after: float = 0.25,
               mode: str = "level") -> dict:
    """Onset of element signal `a` (starting at film t0) near `target`. The envelope's peak (5 ms smoothing) is
    found in [target - before, target + after]; mode "level": the onset is the first moment in the window where the
    envelope comes within 20 dB of that peak (a click, a stream that starts, a bell blooming behind glass and reverb);
    mode "attack": the start of the steepest 2 ms rise of the 1 ms envelope in the 60 ms before the peak (a latch
    whose handle clicks just before it, a cup whose light pre-touch precedes the contact)."""
    e = env_db(a)                                    # 1 ms frames
    sm = 10 * np.log10(uniform_filter(10 ** (e / 10), 5, mode="nearest") + 1e-14)
    i0 = max(int((target - before - t0) * 1000), 0)
    i1 = min(int((target + after - t0) * 1000), len(sm))
    if i1 - i0 < 3:
        return {"onset": None}
    pk = i0 + int(np.argmax(sm[i0:i1]))
    if mode == "attack":
        j0 = max(pk - 60, i0, 2)
        rise = np.array([e[j] - e[j - 2] for j in range(j0, pk + 1)]) if pk >= j0 else np.zeros(1)
        on = j0 + int(np.argmax(rise)) - 2
    else:
        on = i0 + int(np.argmax(sm[i0:pk + 1] >= sm[pk] - 20.0))
    to = t0 + on / 1000
    return {"onset": round(to, 4), "peak": round(t0 + pk / 1000, 4), "peak_dbfs_5ms": round(float(sm[pk]), 1),
            "mode": mode, "error_ms": round((to - target) * 1000, 1), "in_sync": bool(abs(to - target) <= 0.020)}


# ---- one element --------------------------------------------------------------------------------------------------
def element_runs(e: dict, cues: Cues) -> tuple[list[list[float]], float, float]:
    """Straight runs [film t0, film t1, ref film t, file t at ref, rate] and the element's film span."""
    if "timemap" in e:
        tm = e["timemap"]
        sid = tm["shot"]
        t_start, t_end = cues.t(e["start"]), cues.t(e["end"])
        if "fit" in tm:
            (ta, fa), (tb, fb) = [(cues.t(a), b) for a, b in tm["fit"]]
            R = (fb - fa) / (cues.src(sid, tb) - cues.src(sid, ta))
        elif "anchor" in tm:
            ta, fa, R = cues.t(tm["anchor"][0]), tm["anchor"][1], tm.get("rate", 1.0)
        else:
            ta = None
        runs = []
        for T0, T1, Tr, sr, v in cues.runs(sid):
            if ta is None:
                runs.append([T0, T1, Tr, sr, v])
            else:
                runs.append([T0, T1, Tr, fa + R * (sr - cues.src(sid, ta)), R * v])
        return runs, t_start, t_end
    if "splice" in e:
        t_start, t_end = cues.t(e["start"]), cues.t(e["end"])
        return [[-1e9, 1e9, t_start, 0.0, e.get("tempo", 1.0)]], t_start, t_end
    if "fit" in e:   # [[film t0, file f0], [film t1, file f1]]: the part f0..f1 squeezed or stretched into t0..t1
        (t0, f0), (t1, f1) = [(cues.t(t), f) for t, f in e["fit"]]
        rate = (f1 - f0) / (t1 - t0)
        return [[-1e9, 1e9, t0, f0, rate]], t0, t1
    a, b = e["src"]
    rate = e.get("tempo", 1.0) * (2 ** (e.get("pitch", 0) / 12))
    if "sync" in e:
        ft, t = e["sync"][0], cues.t(e["sync"][1])
        t_start = t - (ft - a) / rate
    else:
        t_start = cues.t(e["start"])
    t_end = cues.t(e["end"]) if "end" in e else t_start + (b - a) / rate
    return [[-1e9, 1e9, t_start, a, rate]], t_start, t_end


def render_element(e: dict, cues: Cues, sp_dir: str, peers: dict) -> tuple[np.ndarray, float, dict]:
    path = e["file"] if os.path.isabs(e["file"]) else os.path.join(sp_dir, e["file"])
    full = load(path)
    info: dict = {}
    runs, t_start, t_end = element_runs(e, cues)
    live = [r for r in runs if r[1] + cues.ramp > t_start and r[0] - cues.ramp < t_end]
    p = 2 ** (e.get("pitch", 0) / 12)
    # --- the source, in file time: what belongs to the recording (repair, filters, detone) ---
    if "splice" in e:
        x, x0 = np.asarray(full, dtype=np.float64), 0.0
    else:
        ends = [fr + r * (max(t_start, T0) - Tr) for T0, T1, Tr, fr, r in live] + \
               [fr + r * (min(t_end, T1) - Tr) for T0, T1, Tr, fr, r in live]
        lo, hi = min(ends) - 0.4, max(ends) + 0.4
        for t0_, t1_, d in e.get("repair", []):
            lo, hi = min(lo, d - 0.4, t0_ - 0.4), max(hi, d + (t1_ - t0_) + 0.4, t1_ + 0.4)
        x0 = max(lo - 0.6, 0.0)
        x = take(full, int(round(x0 * SR)), int(round((hi + 0.6) * SR)))
    if e.get("repair"):
        x = repair(x, x0, e["repair"])
    x = apply_sos(x, sos_filters(e))
    if e.get("detone") is not None and e.get("detone") is not False:
        x, info["detone"] = detone(x, **(e["detone"] if isinstance(e["detone"], dict) else {}))
    if e.get("polarity") == "flip_right":
        x[:, 1] *= -1
    if e.get("mono") == "left":
        x[:, 1] = x[:, 0]
    if "splice" in e:
        x = splice(x, e["splice"], e.get("xfade", 0.5), (t_end - t_start) * e.get("tempo", 1.0) + 1.0)
    if p != 1.0:   # pitch by resampling: the file's timeline shrinks by p (rates already include p)
        x = resample_poly(x, 1000, int(round(1000 * p)), axis=0)
        x0 /= p
        runs = [[T0, T1, Tr, fr / p, r / p] for T0, T1, Tr, fr, r in runs]
    a = render_runs(x, x0, runs, t_start, t_end, cues.ramp)
    k = p if p != 1.0 else 1.0
    info["runs"] = [[round(max(T0, t_start), 3), round(min(T1, t_end), 3), round((fr + r * (max(T0, t_start) - Tr)) * k, 4),
                     round(r * k, 4)] for T0, T1, Tr, fr, r in runs if T1 > t_start and T0 < t_end]
    # --- dry level, fades ---
    if "rms_db" in e:
        act = a[np.abs(a).max(axis=1) > 0] if np.any(a) else a
        a *= 10 ** ((e["rms_db"] - rms_db(act)) / 20)
    if "crest_db" in e:   # tame a hot recording's spikes: peaks held to RMS + crest_db (look-ahead limiter)
        act = a[np.abs(a).max(axis=1) > 0] if np.any(a) else a
        a = limit(a, rms_db(act) + e["crest_db"])
    if "peak_db" in e:
        a *= 10 ** ((e["peak_db"] - 20 * np.log10(np.abs(a).max() + 1e-12)) / 20)
    a *= fades(len(a), e.get("fade_in", 0.005), e.get("fade_out", 0.02), e.get("fade_shape", "gain"))[:, None]
    if e.get("reverb"):
        rv = e["reverb"]
        a = reverb(a, rv.get("rt60", 3.0), rv.get("mix", 0.5), rv.get("predelay", 0.02))
    if e.get("slap"):
        s = e["slap"]
        a = slap(a, s["delays"], s["gains_db"], s.get("lp", 3500.0), s.get("hp", 150.0))
    if e.get("reverb") or e.get("slap"):
        a *= env(len(a), 0.0, 0.05)[:, None]
    g = e.get("gain_db", 0.0)
    if e.get("match"):
        m = e["match"]
        ref = peers[m["to"]]
        at, win, gap = cues.t(m["at"]), m.get("win", 1.0), m.get("gap", 0.3)
        mine = take(a, int((at + gap - t_start) * SR), int((at + gap + win - t_start) * SR))
        theirs = take(ref[0], int((at - gap - win - ref[1]) * SR), int((at - gap - ref[1]) * SR))
        g_match = rms_db(theirs) - rms_db(mine)
        g += g_match
        info["match_gain_db"] = round(g_match, 2)
    a *= 10 ** (g / 20)
    if e.get("gain_keys"):
        a *= keyed(cues.keys(e["gain_keys"]), t_start, len(a))[:, None]
    if e.get("lp_keys"):
        a = glass(a, t_start, cues.keys(e["lp_keys"]), e.get("lp_order", 2))
    a = pan(a, e.get("pan", 0.0), e.get("width"))
    return a, t_start, info


# ---- the mix ------------------------------------------------------------------------------------------------------
def loud(meter, a: np.ndarray) -> float | None:
    if len(a) < int(0.45 * SR) or not np.any(a):
        return None
    v = meter.integrated_loudness(a)
    return None if not np.isfinite(v) else round(float(v), 1)


def short_term(a: np.ndarray, win: float = 3.0, hop: float = 0.5) -> tuple[np.ndarray, np.ndarray]:
    """Loudness of `win`-second windows every `hop` seconds (BS.1770, gated as integrated): (centres, LUFS)."""
    meter = pyln.Meter(SR)
    w, h = int(win * SR), int(hop * SR)
    cs, ls = [], []
    for i in range(0, len(a) - w + 1, h):
        v = meter.integrated_loudness(a[i:i + w])
        cs.append((i + w / 2) / SR)
        ls.append(v if np.isfinite(v) else -70.0)
    return np.array(cs), np.array(ls)


def main() -> None:
    spec_p, out = sys.argv[1:3]
    no_score = "--no-score" in sys.argv
    os.makedirs(out, exist_ok=True)
    sp = json.load(open(spec_p, encoding="utf-8"))
    sp_dir = os.path.dirname(os.path.abspath(spec_p))
    cues = Cues(os.path.join(sp_dir, sp.get("cuesheet", "cuesheet3.json")))
    D = cues.t(sp.get("duration", "@duration"))
    N = int(round(D * SR))
    buses = {b: np.zeros((N, 2)) for b in sp["buses"]}
    rep: dict = {"cuesheet": os.path.relpath(cues.path, sp_dir), "duration": D, "elements": [], "sync": [],
                 "speed_runs_vs_cuesheet_max_err_ms": {sid: round(cues.check_runs(sid) * 1000, 2)
                                                       for sid, s in cues.shots.items() if s.get("segs")}}
    peers: dict = {}
    for e in sp["elements"]:
        if e.get("skip_after") is not None and element_runs(e, cues)[1] > cues.t(e["skip_after"]):
            rep.setdefault("skipped", []).append(e["id"])
            continue
        a, t0, info = render_element(e, cues, sp_dir, peers)
        peers[e["id"]] = (a, t0)
        place(buses[e["bus"]], a, t0)
        row = {"id": e["id"], "bus": e["bus"], "what": e.get("what", ""), "file": os.path.basename(e["file"]),
               "licence": e.get("licence", ""), "film_in": round(t0, 3), "film_out": round(t0 + len(a) / SR, 3),
               "source_runs": info.get("runs"), "source_span": e.get("splice") or
               [round(min(min(r[2], r[2] + r[3] * (r[1] - r[0])) for r in info["runs"]), 3),
                round(max(max(r[2], r[2] + r[3] * (r[1] - r[0])) for r in info["runs"]), 3)],
               "gain_db": e.get("gain_db", 0.0),
               "level": {k: e[k] for k in ("rms_db", "peak_db") if k in e},
               "rms_dbfs_placed": round(rms_db(a[np.abs(a).max(axis=1) > 1e-7]) if np.any(a) else -120.0, 1),
               "peak_dbfs_placed": round(20 * np.log10(np.abs(a).max() + 1e-12), 1)}
        for k in ("tempo", "pitch", "timemap", "splice", "repair", "notch", "hp", "lp", "pan", "reverb", "slap",
                  "gain_keys", "lp_keys"):
            if k in e:
                row[k] = e[k]
        row.update({k: v for k, v in info.items() if k != "runs"})
        if e.get("lp_keys"):
            row["lp_keys_resolved"] = [[round(t, 3), hz] for t, hz in cues.keys(e["lp_keys"])]
        if e.get("gain_keys"):
            row["gain_keys_resolved"] = [[round(t, 3), db] for t, db in cues.keys(e["gain_keys"])]
        if e.get("onset") is not None:
            tgt = cues.t(e["onset"])
            s = onset_near(a, t0, tgt, e.get("onset_before", 0.12), e.get("onset_after", 0.25), e.get("onset_mode", "level"))
            rep["sync"].append({"id": e["id"], "event": e["onset"], "target": round(tgt, 4), **s})
        if e.get("step") is not None:   # a level step that belongs to the picture (he leans out: the city doubles)
            tgt = cues.t(e["step"])
            e_ = env_db(a, 0.05)
            sm = np.convolve(e_, np.ones(5) / 5, mode="same")           # 250 ms
            i0, i1 = max(int((tgt - 1.0 - t0) / 0.05), 5), min(int((tgt + 1.0 - t0) / 0.05), len(sm) - 6)
            d = sm[i0 + 5:i1 + 5] - sm[i0 - 5:i1 - 5]                     # 0.5 s after minus 0.5 s before
            k = int(np.argmax(d))
            before = float(np.mean(e_[max(i0 + k - 30, 0):i0 + k - 5]))
            after = float(np.mean(e_[i0 + k + 5:i0 + k + 30]))
            rep["sync"].append({"id": e["id"], "event": e["step"], "target": round(tgt, 4), "kind": "level step",
                                "step_at": round(t0 + (i0 + k) * 0.05, 3), "step_db": round(after - before, 1),
                                "error_ms": round((t0 + (i0 + k) * 0.05 - tgt) * 1000, 0)})
        rep["elements"].append(row)
        print(f"  {e['id']:22s} {e['bus']:8s} {t0:7.3f}-{t0 + len(a) / SR:7.3f}  rms {row['rms_dbfs_placed']:6.1f}  pk {row['peak_dbfs_placed']:6.1f}", flush=True)
    for t0, t1, db in sp.get("ducks", []):
        i0, i1 = int(cues.t(t0) * SR), int(cues.t(t1) * SR)
        for b in buses.values():
            b[i0:i1] *= 10 ** (db / 20)
    fx = sum(buses.values())
    # ---- the score (optional) ----
    sc = sp.get("score") or {}
    mus = np.zeros((N, 2))
    have_score = bool(sc.get("file")) and os.path.exists(sc["file"]) and not no_score
    meter = pyln.Meter(SR)
    rep["score"] = {"file": sc.get("file"), "present": have_score}
    if have_score:
        m = decode(sc["file"])[:N]
        place(mus, m, 0.0)
        g = sc.get("gain_db", 0.0)
        if sc.get("auto"):
            au = sc["auto"]
            i0, i1 = int(cues.t(au["t0"]) * SR), int(cues.t(au["t1"]) * SR)
            Lm = meter.integrated_loudness(mus[i0:i1])
            Lc = meter.integrated_loudness(buses[au.get("bus", "city")][i0:i1])
            g = float(np.clip(Lc + au["city_under_db"] - Lm, -24.0, 24.0))
            rep["score"]["auto"] = {"window": [round(i0 / SR, 3), round(i1 / SR, 3)], "score_lufs": round(Lm, 2),
                                    "city_lufs": round(Lc, 2), "city_under_db": au["city_under_db"]}
        mus *= 10 ** (g / 20)
        rep["score"]["gain_db"] = round(g, 2)
        tt = np.arange(N) / SR
        for t0, t1, db in sp.get("music_ducks", []):
            t0, t1, r = cues.t(t0), cues.t(t1), 0.3
            w = np.clip(np.minimum((tt - (t0 - r)) / r, ((t1 + r) - tt) / r), 0, 1)
            mus *= (1 - w * (1 - 10 ** (db / 20)))[:, None]
        if sc.get("end_fade"):
            a_, b_ = cues.t(sc["end_fade"][0]), cues.t(sc["end_fade"][1])
            w = np.clip((b_ - tt) / max(b_ - a_, 1e-3), 0, 1) ** 2
            mus *= w[:, None]

    def master(x: np.ndarray, lufs: float, name: str) -> dict:
        x = x.copy()
        tail = int(0.01 * SR)
        x[-tail:] *= np.linspace(1, 0, tail)[:, None]
        g = lufs - meter.integrated_loudness(x)
        src = x
        for _ in range(6):   # the limiter takes a little loudness: converge on the target
            x = limit(src * 10 ** (g / 20), sp.get("ceiling_db", -2.0))
            err = lufs - meter.integrated_loudness(x)
            if abs(err) < 0.05:
                break
            g += err
        else:
            x = limit(src * 10 ** (g / 20), sp.get("ceiling_db", -2.0))
        sf.write(os.path.join(out, name), x.astype(np.float32), SR, subtype="PCM_24")
        pre = np.abs(src * 10 ** (g / 20)).max(axis=1)
        live = pre > 10 ** (-40 / 20)    # gain reduction where there is signal (not the ratio of two near-zeros)
        red = 20 * np.log10(np.maximum(np.abs(x).max(axis=1)[live], 1e-9) / pre[live]) if live.any() else np.zeros(1)
        return {"file": name, "lufs": round(meter.integrated_loudness(x), 2), "true_peak_dbtp": round(true_peak_db(x), 2),
                "gain_db": round(g, 2), "limiter_max_reduction_db": round(float(-red.min()), 2), "_x": x}

    tg = sp.get("targets", {"mix": -14.0, "sfx_only": -16.0})
    mix = master(fx + mus, tg["mix"], "mix.wav")
    sfo = master(fx, tg["sfx_only"], "sfx_only.wav")
    for b, a in buses.items():
        sf.write(os.path.join(out, f"{b}.wav"), a.astype(np.float32), SR, subtype="FLOAT")
    if have_score:
        sf.write(os.path.join(out, "music_bus.wav"), mus.astype(np.float32), SR, subtype="FLOAT")
    elif os.path.exists(os.path.join(out, "music_bus.wav")):
        os.remove(os.path.join(out, "music_bus.wav"))
    rep["mix"] = {k: v for k, v in mix.items() if k != "_x"}
    rep["mix"]["with_score"] = have_score
    rep["sfx_only"] = {k: v for k, v in sfo.items() if k != "_x"}
    rep["stems"] = {b: f"{b}.wav" for b in buses}
    # ---- per-section loudness (in the mix's scale: stems and score x the mix's master gain) ----
    gm = 10 ** (mix["gain_db"] / 20)
    secs = []
    for name, t0, t1 in sp.get("sections", []):
        i0, i1 = int(cues.t(t0) * SR), int(cues.t(t1) * SR)
        row = {"section": name, "t0": round(i0 / SR, 3), "t1": round(i1 / SR, 3),
               "mix_lufs": loud(meter, mix["_x"][i0:i1]), "sfx_only_lufs": loud(meter, sfo["_x"][i0:i1])}
        for b, a in buses.items():
            row[f"{b}_lufs_in_mix"] = loud(meter, a[i0:i1] * gm)
        if have_score:
            row["score_lufs_in_mix"] = loud(meter, mus[i0:i1] * gm)
        secs.append(row)
    rep["sections"] = secs
    # ---- the glass: the cutoff and the level of the city behind the glass, sampled, and what the city stem shows ----
    gl = {}
    for gid in sp.get("glass_report", []):
        e = next((x for x in sp["elements"] if x["id"] == gid), None)
        if not e or not e.get("lp_keys"):
            continue
        lk, gk = cues.keys(e["lp_keys"]), cues.keys(e.get("gain_keys", [[0, 0]]))
        t0, t1 = cues.t(e.get("start", 0.0)), cues.t(e.get("end", D))
        gl[gid] = {"lp_keys": [[round(t, 3), hz] for t, hz in lk], "gain_keys": [[round(t, 3), db] for t, db in gk],
                   "curve_every_0.5s": [[round(t, 2), round(fc_at(lk, t)), round(float(np.interp(t, [k[0] for k in gk],
                                        [k[1] for k in gk])), 1)] for t in np.arange(np.ceil(t0 * 2) / 2, t1, 0.5)]}
    if "city" in buses:   # share of the city stem's energy above 1 kHz and above 4 kHz, per section: the glass at work
        meas = []
        for name, a_, b_ in sp.get("sections", []):
            i0, i1 = int(cues.t(a_) * SR), int(cues.t(b_) * SR)
            seg = buses["city"][i0:i1].mean(axis=1)
            if len(seg) < SR // 4 or not np.any(seg):
                continue
            P = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) ** 2
            fq = np.fft.rfftfreq(len(seg), 1 / SR)
            tot = P[fq > 40].sum() + 1e-20
            meas.append({"section": name, "above_1k_db": round(10 * np.log10(P[fq > 1000].sum() / tot + 1e-12), 1),
                         "above_4k_db": round(10 * np.log10(P[fq > 4000].sum() / tot + 1e-12), 1)})
        gl["city_stem_highs_by_section"] = meas
    rep["glass"] = gl
    lic = {}
    for e in sp["elements"]:
        lic.setdefault(os.path.basename(e["file"]), e.get("licence", ""))
    rep["sources_and_licences"] = lic
    rep["notes"] = sp.get("notes", [])
    # ---- QC ----
    qc = {}
    ssum = sum(buses.values())
    qc["stems_sum_to_sound_bus_max_abs_err"] = float(np.abs(ssum - fx).max())
    qc["mix_lufs_ok"] = abs(mix["lufs"] - tg["mix"]) <= 0.1
    qc["mix_true_peak_ok"] = mix["true_peak_dbtp"] <= sp.get("ceiling_db", -2.0) + 0.05
    qc["sfx_only_lufs_ok"] = abs(sfo["lufs"] - tg["sfx_only"]) <= 0.1
    qc["sfx_only_true_peak_ok"] = sfo["true_peak_dbtp"] <= sp.get("ceiling_db", -2.0) + 0.05
    qc["length_samples"] = N
    qc["sync_all_within_20ms"] = all(s.get("in_sync") for s in rep["sync"] if s.get("onset") is not None)
    qc["level_steps_within_250ms"] = all(abs(s["error_ms"]) <= 250 for s in rep["sync"] if s.get("kind") == "level step")
    qc["mono_fold_mix_corr"] = round(float(np.corrcoef(mix["_x"][:, 0], mix["_x"][:, 1])[0, 1]), 3)
    # the latch: the loudest close transient of the first half
    latch_t = cues.t("@latch")
    pk_first = []
    for row in rep["elements"]:
        if row["bus"] == "foley" and row["film_in"] < latch_t + 0.05:
            pk_first.append((row["peak_dbfs_placed"], row["id"]))
    pk_first.sort(reverse=True)
    qc["first_half_foley_peaks"] = [[i, p] for p, i in pk_first[:6]]
    qc["latch_is_loudest_close_transient"] = bool(pk_first and "latch" in pk_first[0][1])
    # the end: the city is the last sound
    tail0 = int((D - 0.6) * SR)
    city_tail = rms_db(buses.get("city", np.zeros((1, 2)))[tail0:])
    other_tail = rms_db((fx - buses.get("city", 0) + mus)[tail0:]) if True else -120
    qc["last_0.6s_city_rms_db"], qc["last_0.6s_rest_rms_db"] = round(city_tail, 1), round(other_tail, 1)
    qc["city_is_last_sound"] = bool(city_tail > other_tail + 6)
    # the city after the latch against the score (short-term, 3 s windows)
    if have_score:
        tc, Lc = short_term(buses["city"] * gm)
        tm_, Lm = short_term(mus * gm)
        after = (tc >= cues.t("@sash_clear")) & (tc <= cues.t("@end"))
        diff = Lm[after] - Lc[after]
        qc["score_minus_city_after_latch_db"] = {"min": round(float(diff.min()), 1), "max": round(float(diff.max()), 1),
                                                  "at_max": round(float(tc[after][np.argmax(diff)]), 2)}
        cl = cues.t("@climax")
        k = np.argmin(np.abs(tc - (cl + 1.0)))
        qc["score_minus_city_at_climax_db"] = round(float(Lm[k] - Lc[k]), 1)
        rel = (tc >= cues.t("@bell4")) & (tc <= cues.t("@end"))
        qc["score_minus_city_release_db"] = [round(float(v), 1) for v in (Lm[rel] - Lc[rel])[::2]]
        qc["city_never_buried"] = bool(diff.max() <= 14.0)
    rep["qc"] = qc
    json.dump(rep, open(os.path.join(out, "sound_report.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False,
              default=lambda o: o.item() if hasattr(o, "item") else str(o))
    print(json.dumps({"mix": rep["mix"], "sfx_only": rep["sfx_only"], "qc": {k: v for k, v in qc.items() if k != "first_half_foley_peaks"}},
                     indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))


if __name__ == "__main__":
    main()
