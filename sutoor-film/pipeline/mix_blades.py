#!/usr/bin/env python3
"""Sound-effects pass and master for the Blades edition: real recorded effects UNDER the untouched original mix.

What it does, in order (re-run it whenever plan.json or the cue list changes; nothing is cached):
  1. reads the picture plan (shot ids, start times, fps, duration, the original mix) and the cue list
     (data/blades/sfx_cues.json). Every cue is anchored to a shot id, so its film time is resolved from the
     plan on each run:      time = anchor(shot) + offset
     anchor "start" = the shot's `start` (the centre of a whip, zoom, flash, dissolve or matte transition);
     anchor "frame" = the first picture frame of the shot, ceil(start * fps) / fps, which is where a hard
     cut is SEEN (up to one frame after `start`).
  2. builds the effects bus from the cues (ffmpeg decodes any format; optional high-pass / low-pass per cue;
     raised-cosine fades; static gain). The recordings are never time-stretched or pitch-shifted.
  3. THE VOICE WINS: at every instant from the start to the end of every spoken word (timing.json
     words[].start/end, film time = recording time), of the spoken intro, and of any voiced stretch the
     word list does not cover (found by level in the original itself), the effects bus must sit at least
     14 dB under the original mix, both measured K-weighted (BS.1770) in the same 400 ms window centred on
     that instant. Where a window falls short, the EFFECTS are turned down by a smooth automatic gain
     (never the original). The cue gains are chosen so that this safety net stays idle on the current cut.
  4. sums the automated effects with the original mix. The original is not equalised, ducked, separated or
     re-timed: the only things that ever touch it are a static gain of at most +/-0.5 dB (0 dB by default)
     and a true-peak limiter whose gain is exactly 1 except around the few peaks above the ceiling.
  5. limits to -1 dBTP (detector at 4x oversampling, 1.5 ms look-ahead, gain applied at the native rate so
     the samples the limiter does not need to touch pass through unchanged), fades the last 0.6 s to
     silence, trims to exactly plan.duration (744 frames at 24 fps = 31.000 s) and writes 48 kHz 24-bit
     stereo.
  6. measures everything and writes it down, because nobody in this pipeline can listen: per-word margins,
     integrated loudness, true peak, limiter activity, where each cue's energy peak lands against its
     cut, a held-tone ("scream") check with a positive control, the cue table with resolved times, and
     the licences of the recordings used.

Usage:
  python mix_blades.py                       # plan, cues, timing and output folder from the defaults below
  python mix_blades.py --plan data/blades/plan.json --cues data/blades/sfx_cues.json \
                       --licences /home/user/film/v4/sound/sfx_licences.json --out /home/user/film/v4/sound
  options: --gain-db 0.0 (static gain on the sum, limited to +/-0.5)   --skip-missing (drop cues whose shot id
           is no longer in the plan instead of stopping)   --no-plot   --no-tonal
Writes OUT/effects.wav (the effects bus as mixed), OUT/mix.wav (the master), OUT/mix_report.json and
OUT/mix_overview.png. Exit status 0 = every check passed, 2 = a cue could not be resolved, 3 = a check failed
(the files are still written; read "verdict" and "failures" in the report).

sfx_cues.json: {"sfx_dir": folder, "protect": {"intro_end": s, "unlisted_lufs": level, "extra": [[start, end, name], ...]},
"cues": [cue, ...]}; `protect` names what is guarded besides the listed words: the spoken intro up to intro_end,
voiced stretches found by level, and any extra intervals. Cue fields:
  shot        shot id the cue is anchored to                      offset     seconds from the anchor (may be < 0)
  anchor      "start" (default) or "frame" (see above)            dur        length in seconds, or
  until_shot  end at another shot's anchor (+ until_offset; until_anchor "start"|"frame"); "@end" = the end of the film
  until_key   [shot id, n]: end at the film time of the n-th key of that shot's `time` remap (+ until_offset), for a
              sound tied to something that happens INSIDE a shot (the sand running out); falls back to dur
  src         recording (absolute, or relative to sfx_dir)        src_in     seconds into the recording
  gain_db     static gain                                         fade_in / fade_out   seconds (raised cosine)
  highpass_hz / lowpass_hz   optional zero-phase Butterworth (12 dB/octave each way)
  env         optional level ride inside the cue: [[seconds from the cue's start, dB], ...], straight lines in dB
  peak_on     shot id whose cut this cue's energy peak must land on (checked to one frame, 42 ms, and reported);
              peak_win_ms (30) is the energy window; a slow swell may set peak_win_ms / peak_tol_ms wider
  word        index into timing.json words[] of a word this cue is placed against, word_offset = designed distance
              of the cue's start from that word's start (s). Cues follow their SHOT; this only reports the drift
              from the word and warns beyond 60 ms (e.g. the heartbeat on «فُؤادي», fly-bys in a pause of the voice)
  shot_src    picture file the cue was designed against; a warning is printed if the plan now uses another
  sfx_id      Mixkit id (default: the file name), title, note
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time

import numpy as np
import soundfile as sf
from scipy.ndimage import maximum_filter1d, uniform_filter1d
from scipy.signal import butter, lfilter, resample_poly, sosfiltfilt

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SR = 48000

MARGIN_DB = 14.0          # the rule
SAFETY_DB = 0.3           # the automation aims this much above the rule
WIN_S = 0.400             # momentary window
HOP_S = 0.005             # spacing of the window centres that are checked inside each protected interval
AUTO_RAMP_S = 0.030       # the automatic gain moves over this long
INTRO_END_S = 1.70        # the spoken intro (not in timing.json) ends here
VOICE_ONSET_LUFS = -40.0  # first 50 ms window of the original above this = the first syllable of the intro
UNLISTED_LUFS = -18.0     # 50 ms level of the original above this, outside the word list, for >= 80 ms = voice
CEILING_DBTP = -1.0
FADE_OUT_S = 0.6
LUFS_RANGE = (-14.5, -13.5)
FRAME_TOL_S = 0.042

# BS.1770 K-weighting at 48 kHz: shelf, then high-pass
_K1 = ([1.53512485958697, -2.69169618940638, 1.19839281085285], [1.0, -1.69065929318241, 0.73248077421585])
_K2 = ([1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621])


# ---------------------------------------------------------------- measuring

def kpower(x: np.ndarray) -> np.ndarray:
    """K-weighted instantaneous power summed over the channels."""
    z = lfilter(*_K2, lfilter(*_K1, x, axis=0), axis=0)
    return (z * z).sum(axis=1)


def window_lufs(p: np.ndarray, centres: np.ndarray, win: int) -> np.ndarray:
    """Loudness of the windows [c - win/2, c + win/2) for centre samples c (zero-padded at the ends)."""
    c = np.concatenate([[0.0], np.cumsum(p)])
    a = np.clip(centres - win // 2, 0, len(p))
    b = np.clip(centres + win // 2, 0, len(p))
    return -0.691 + 10 * np.log10((c[b] - c[a]) / win + 1e-14)


def span_lufs(p: np.ndarray, a: float, b: float) -> float:
    i, j = max(0, int(round(a * SR))), min(len(p), int(round(b * SR)))
    return float(-0.691 + 10 * np.log10(p[i:j].mean() + 1e-14)) if j > i else -140.0


def integrated_lufs(x: np.ndarray) -> float:
    import pyloudnorm as pyln
    return float(pyln.Meter(SR).integrated_loudness(x))


def true_peak_db(x: np.ndarray) -> float:
    """4x oversampled peak (polyphase FIR), dBTP."""
    return float(20 * np.log10(np.abs(resample_poly(x, 4, 1, axis=0)).max() + 1e-12))


def ffmpeg_ebur128(path: str) -> dict:
    try:
        err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"],
                             capture_output=True, text=True, check=True).stderr
        tail = err[err.rindex("Summary:"):]
        return {"integrated_lufs": float(tail[tail.index("I:"):].split()[1]), "lra_lu": float(tail[tail.index("LRA:"):].split()[1]),
                "true_peak_dbtp": float(tail[tail.index("Peak:"):].split()[1])}
    except Exception as e:  # noqa: BLE001 - a cross-check only
        return {"error": str(e)}


def energy_peak_time(x: np.ndarray, t0: float, win_s: float = 0.030) -> float | None:
    """Film time of the centre of the loudest `win_s` window (K-weighted) of a rendered cue starting at t0."""
    if len(x) < 8 or not np.any(x):
        return None
    p = kpower(x)
    w = max(1, int(win_s * SR))
    c = np.concatenate([[0.0], np.cumsum(p)])
    e = c[w:] - c[:-w] if len(p) > w else np.array([c[-1]])
    return float(t0 + (int(np.argmax(e)) + w / 2) / SR)


# ---------------------------------------------------------------- cues

def decode(path: str, start: float, dur: float) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, start):.6f}", "-t", f"{dur:.6f}", "-i", path, "-vn",
                          "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)


def half_cos(n: int) -> np.ndarray:
    return 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, n)) if n > 1 else np.ones(max(n, 0))


def render_cue(c: dict) -> np.ndarray:
    """The cue's audio at the film sample rate: filtered, faded, gained. Length = c['_dur']."""
    dur = c["_dur"]
    pad = 0.25  # decoded on both sides so the filters settle outside the part that is used
    pre = min(pad, c.get("src_in", 0.0))
    x = decode(c["_src"], c.get("src_in", 0.0) - pre, dur + pre + pad)
    if c.get("highpass_hz"):
        x = sosfiltfilt(butter(2, float(c["highpass_hz"]), "highpass", fs=SR, output="sos"), x, axis=0)
    if c.get("lowpass_hz"):
        x = sosfiltfilt(butter(2, float(c["lowpass_hz"]), "lowpass", fs=SR, output="sos"), x, axis=0)
    i = int(round(pre * SR))
    n = int(round(dur * SR))
    x = x[i:i + n]
    if len(x) < n:  # the recording ended early: the rest is silence (reported)
        c["_short_by_s"] = round((n - len(x)) / SR, 3)
        x = np.vstack([x, np.zeros((n - len(x), 2))])
    fi, fo = int(round(c.get("fade_in", 0.01) * SR)), int(round(c.get("fade_out", 0.05) * SR))
    fi, fo = min(fi, n), min(fo, n)
    if fi > 0:
        x[:fi] *= half_cos(fi)[:, None]
    if fo > 0:
        x[n - fo:] *= half_cos(fo)[::-1][:, None]
    if c.get("env"):  # level ride inside the cue: [[seconds from the cue's start, dB], ...], straight lines in dB
        pts = np.array(sorted(c["env"]), float)
        x *= (10 ** (np.interp(np.arange(n) / SR, pts[:, 0], pts[:, 1]) / 20))[:, None]
    return x * 10 ** (c.get("gain_db", 0.0) / 20)


def resolve(cues: list[dict], plan: dict, sfx_dir: str, skip_missing: bool) -> tuple[list[dict], list[dict], list[str]]:
    fps = plan["fps"]
    shots = {s["id"]: s for s in plan["shots"]}
    warnings, missing, out = [], [], []

    def anchor(sid: str, kind: str) -> float:
        st = float(shots[sid]["start"])
        return math.ceil(st * fps - 1e-6) / fps if kind == "frame" else st

    for k, c in enumerate(cues):
        c = dict(c)
        c.setdefault("id", f"{c.get('shot', '?')}_{k}")
        need = [c.get("shot")] + ([c["until_shot"]] if c.get("until_shot") not in (None, "@end") else []) + ([c["peak_on"]] if c.get("peak_on") else []) \
            + ([c["until_key"][0]] if c.get("until_key") else [])
        gone = sorted({str(s) for s in need if s not in shots})
        if gone:
            missing.append({"id": c["id"], "missing_shots": gone})
            continue
        t0 = anchor(c["shot"], c.get("anchor", "start")) + float(c.get("offset", 0.0))
        keys = shots[c["until_key"][0]].get("time") if c.get("until_key") else None
        if c.get("until_key") and keys and 0 <= int(c["until_key"][1]) < len(keys):
            t1 = float(keys[int(c["until_key"][1])][0]) + float(c.get("until_offset", 0.0))   # a time-remap key of the picture, in film time
        elif c.get("until_shot") == "@end":
            t1 = float(plan["duration"])
        elif c.get("until_shot"):
            t1 = anchor(c["until_shot"], c.get("until_anchor", "start")) + float(c.get("until_offset", 0.0))
        else:
            if c.get("until_key"):
                warnings.append(f"cue {c['id']}: shot '{c['until_key'][0]}' has no time key {c['until_key'][1]} any more; using dur instead")
            t1 = t0 + float(c["dur"])
        if t0 < 0:  # a cue that would start before the film: start it at 0 and move into the recording
            c["src_in"] = c.get("src_in", 0.0) - t0
            t0 = 0.0
        t1 = min(t1, float(plan["duration"]))
        if t1 - t0 < 0.02:
            warnings.append(f"cue {c['id']}: resolved length {t1 - t0:.3f} s is too short; skipped")
            continue
        src = c["src"] if os.path.isabs(c["src"]) else os.path.join(sfx_dir, c["src"])
        if not os.path.exists(src):
            raise SystemExit(f"cue {c['id']}: recording not found: {src}")
        c.update(_t0=t0, _t1=t1, _dur=t1 - t0, _src=src)
        c.setdefault("sfx_id", os.path.splitext(os.path.basename(src))[0].split("_")[0])
        now = os.path.basename(str(shots[c["shot"]].get("src", "")))
        if c.get("shot_src") and now and c["shot_src"] != now:
            warnings.append(f"cue {c['id']}: shot '{c['shot']}' now shows {now}, the cue was designed against {c['shot_src']}; check that the sound still fits")
        out.append(c)
    if missing and not skip_missing:
        ids = ", ".join(f"{m['id']} -> {'/'.join(m['missing_shots'])}" for m in missing)
        print(f"cue(s) anchored to shot ids that are not in the plan: {ids}\nplan shots: {' '.join(shots)}\n"
              f"fix the cue list (or pass --skip-missing to mix without them); nothing was written", file=sys.stderr)
        sys.exit(2)
    return out, missing, warnings


# ---------------------------------------------------------------- the voice wins

def protected_intervals(orig_p: np.ndarray, timing: dict, protect: dict) -> list[dict]:
    """Word intervals, the spoken intro from its first syllable, and voiced stretches the word list misses."""
    iv = []
    # 50 ms level of the original, every 5 ms
    h = int(0.005 * SR)
    cen = np.arange(0, len(orig_p), h)
    l50 = window_lufs(orig_p, cen, int(0.05 * SR))
    intro_end = float(protect.get("intro_end", INTRO_END_S))
    if intro_end > 0:
        on = np.flatnonzero((l50 > VOICE_ONSET_LUFS) & (cen / SR < intro_end))
        if len(on):
            iv.append({"kind": "intro", "name": "intro (spoken, not in the word list)", "start": round(max(0.0, cen[on[0]] / SR - 0.025), 3), "end": intro_end})
    for i, w in enumerate(timing["words"]):
        iv.append({"kind": "word", "index": i, "name": w["word"], "roman": w.get("roman", ""), "line": w.get("line", ""),
                   "start": float(w["start"]), "end": float(w["end"])})
    for a, b, name in protect.get("extra", []):
        iv.append({"kind": "extra", "name": name, "start": float(a), "end": float(b)})
    # voiced stretches outside every listed interval
    listed = np.zeros(len(cen), bool)
    for v in iv:
        listed |= (cen / SR >= v["start"]) & (cen / SR <= v["end"])
    loud = (l50 > float(protect.get("unlisted_lufs", UNLISTED_LUFS))) & ~listed
    idx = np.flatnonzero(loud)
    runs = []
    if len(idx):
        a = p = idx[0]
        for q in idx[1:]:
            if q - p > int(0.06 / 0.005):
                runs.append((a, p)); a = q
            p = q
        runs.append((a, p))
    for a, b in runs:
        ta, tb = cen[a] / SR, cen[b] / SR
        if tb - ta >= 0.08:
            iv.append({"kind": "unlisted", "name": f"voiced stretch outside the word list {ta:.2f}-{tb:.2f}", "start": float(ta), "end": float(tb)})
    iv.sort(key=lambda v: v["start"])
    return iv


def centres_of(iv: list[dict], n: int) -> tuple[np.ndarray, np.ndarray]:
    """Window centres (samples) checked for each protected interval, and the interval each belongs to."""
    cs, owner = [], []
    hop = int(HOP_S * SR)
    for k, v in enumerate(iv):
        a, b = int(round(v["start"] * SR)), int(round(v["end"] * SR))
        c = np.unique(np.clip(np.concatenate([np.arange(a, b, hop), [b]]), 0, n - 1))
        cs.append(c); owner.append(np.full(len(c), k))
    return np.concatenate(cs), np.concatenate(owner)


def enforce(orig_p: np.ndarray, fx: np.ndarray, centres: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Automatic gain (dB <= 0, per sample) that puts the effects >= MARGIN + SAFETY under the original in
    every checked window. Returns (gain_db, fx * gain)."""
    n = len(fx)
    win = int(WIN_S * SR)
    lo = window_lufs(orig_p, centres, win)
    red = np.zeros(n)
    ramp = int(AUTO_RAMP_S * SR) | 1
    cur = fx
    for _ in range(25):
        lf = window_lufs(kpower(cur), centres, win)
        need = (MARGIN_DB + SAFETY_DB) - (lo - lf)
        need[lf < -100.0] = 0.0  # nothing of the effects in this window
        if need.max() <= 1e-3:
            break
        per = np.zeros(n)
        np.maximum.at(per, centres, np.maximum(need, 0.0))
        add = maximum_filter1d(per, size=win + 1, mode="constant")       # every sample of a short window
        add = uniform_filter1d(maximum_filter1d(add, size=ramp, mode="constant"), size=ramp, mode="constant")  # smooth, never less
        red += add
        cur = fx * (10 ** (-red / 20))[:, None]
    else:
        raise SystemExit("the 14 dB rule could not be enforced (no convergence): check the cue list")
    return -red, cur


# ---------------------------------------------------------------- master

def limit(x: np.ndarray, ceiling_db: float, look_ms: float = 1.5, release_db_s: float = 40.0) -> tuple[np.ndarray, dict]:
    """True-peak limiter: detector at 4x oversampling, gain applied at the native rate (unity away from peaks)."""
    up = resample_poly(x, 4, 1, axis=0)
    pk = np.abs(up).max(axis=1)
    need = np.maximum(0.0, 20 * np.log10(np.maximum(pk, 1e-12)) - ceiling_db)
    if need.max() <= 0:
        return x.copy(), {"max_gain_reduction_db": 0.0, "ms_changed": 0.0, "ms_above_0p1_db": 0.0, "events": 0, "samples_changed_pct": 0.0, "where": [],
                          "_mask": np.zeros(len(x), bool)}
    idx = np.arange(len(need), dtype=np.float64)
    slope = release_db_s / (SR * 4)
    gr = np.maximum(np.maximum.accumulate(need + slope * idx) - slope * idx, 0.0)   # instant attack, linear-in-dB release
    L = int(look_ms * 1e-3 * SR * 4) | 1
    gr = uniform_filter1d(maximum_filter1d(gr, size=L, mode="constant"), size=L, mode="constant")  # look-ahead, smooth, never less
    m = len(x) * 4
    gr = np.pad(gr[:m], (0, max(0, m - len(gr))))
    g1 = maximum_filter1d(gr, size=9, mode="constant")[::4][:len(x)]                # the deepest reduction around each native sample
    g1 = np.maximum(g1 - 1e-3, 0.0)                                                 # exactly unity gain away from the peaks, no step
    y = x.copy()
    hit = g1 > 0
    y[hit] = x[hit] * (10 ** (-g1[hit] / 20))[:, None]
    edge = np.diff(np.concatenate([[0], hit.astype(np.int8), [0]]))
    on, off = np.flatnonzero(edge == 1), np.flatnonzero(edge == -1)
    where = [{"at_s": round(float((a + int(np.argmax(g1[a:b]))) / SR), 3), "db": round(float(g1[a:b].max()), 2), "ms": round((b - a) / SR * 1000, 1)} for a, b in zip(on, off)]
    return y, {"max_gain_reduction_db": round(float(g1.max()), 3), "ms_changed": round(float(hit.sum() / SR * 1000), 1),
               "ms_above_0p1_db": round(float((g1 > 0.1).sum() / SR * 1000), 1), "events": len(where),
               "samples_changed_pct": round(float(hit.mean() * 100), 3), "where": where, "_mask": hit}


def master(pre: np.ndarray) -> tuple[np.ndarray, dict]:
    ceiling = CEILING_DBTP - 0.08
    for _ in range(12):
        y, st = limit(pre, ceiling)
        tp = true_peak_db(y)
        if tp <= CEILING_DBTP - 0.02:
            break
        ceiling -= max(0.03, tp - (CEILING_DBTP - 0.03))
    st["detector_ceiling_dbtp"] = round(ceiling, 3)
    return y, st


# ---------------------------------------------------------------- nothing voice-like

def tonal_check(fx: np.ndarray, orig: np.ndarray) -> dict:
    """No held pitched tone in the effects (the detector of scream_check.py), plus how periodic they are,
    plus a positive control so that "nothing found" means "nothing there"."""
    try:
        import librosa
        sys.path.insert(0, HERE)
        from scream_check import tonal_runs
    except Exception as e:  # noqa: BLE001
        return {"ran": False, "error": f"{e}"}

    def runs_of(x: np.ndarray) -> list[dict]:
        y = librosa.resample(x.mean(axis=1).astype(np.float32), orig_sr=SR, target_sr=16000)
        if not np.any(np.abs(y) > 1e-7):
            return []
        return [{"at_s": round(a, 2), "dur_s": round(d, 2), "hz": round(f)} for a, d, f in tonal_runs(y / (np.abs(y).max() + 1e-9) * 0.9)[:8]]

    def periodic(x: np.ndarray) -> dict:
        """Pitch periodicity: longest run of 50 ms frames (every 10 ms) whose normalised cross-correlation at a
        lag of 80-600 Hz exceeds 0.7, among frames within 35 dB of the loudest. Voiced speech holds this for
        hundreds of ms (the original mix: 40 % of frames, runs up to 0.7 s); whooshes, water, fire, wind and
        short hits do not."""
        y = librosa.resample(x.mean(axis=1).astype(np.float32), orig_sr=SR, target_sr=8000).astype(np.float64)
        y = sosfiltfilt(butter(2, (70, 3400), "bandpass", fs=8000, output="sos"), y)
        N, H, lmin, lmax = 400, 80, int(8000 / 600), int(8000 / 80)
        if len(y) < N + lmax + H:
            return {"longest_run_ms": 0, "at_s": None, "hz": None, "frames_pct": 0.0}
        fr = np.lib.stride_tricks.sliding_window_view(y, N + lmax)[::H]
        a0 = fr[:, :N]
        ea = (a0 * a0).sum(axis=1)
        best = np.zeros(len(fr)); lag = np.ones(len(fr), int)
        for L in range(lmin, lmax + 1):
            b0 = fr[:, L:L + N]
            r = (a0 * b0).sum(axis=1) / np.sqrt(ea * (b0 * b0).sum(axis=1) + 1e-20)
            m = r > best
            best[m] = r[m]; lag[m] = L
        act = ea > ea.max() * 10 ** (-35 / 10)
        hot = (best > 0.7) & act
        top, at, cur = 0, 0, 0
        for i, hflag in enumerate(hot):
            cur = cur + 1 if hflag else 0
            if cur > top:
                top, at = cur, i
        return {"longest_run_ms": int(top * H / 8), "at_s": round((at - top + 1) * H / 8000, 2) if top else None,
                "hz": round(float(np.median(8000 / lag[at - top + 1:at + 1]))) if top else None,
                "frames_pct": round(float(hot.sum() / max(1, act.sum()) * 100), 2)}

    rep = {"ran": True, "effects_held_pitch_runs": runs_of(fx), "effects_periodicity": periodic(fx)}
    # positive controls on the same bus: (a) a pulsing 2.9 kHz tone as loud as the bus's loudest second,
    # (b) two seconds of the film's own voice at the same level; each must be found.
    p = kpower(fx)
    sec = SR
    c = np.concatenate([[0.0], np.cumsum(p)])
    e = c[sec:] - c[:-sec]
    lvl = math.sqrt(max(e.max() / sec / 2, 1e-12))
    quiet = int(np.argmin(e[: max(1, len(e) - 2 * sec)]))
    t = np.arange(int(1.6 * SR)) / SR
    tone = lvl * 1.4 * np.sin(2 * np.pi * 2900 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 7 * t))
    a = fx.copy(); a[quiet:quiet + len(tone)] += tone[:, None][: len(a) - quiet]
    found = runs_of(a)
    rep["control_tone"] = {"planted_at_s": round(quiet / SR, 2), "hz": 2900, "found": bool([r for r in found if abs(r["hz"] - 2900) < 200])}
    op = kpower(orig)
    co = np.concatenate([[0.0], np.cumsum(op)])
    k = int(np.argmax(co[2 * sec:] - co[:-2 * sec]))
    v = orig[k:k + 2 * sec]
    v = v * (lvl * 1.4 / (np.sqrt((v ** 2).mean()) + 1e-12))
    b = fx.copy(); b[quiet:quiet + len(v)] += v[: len(b) - quiet]
    pv = periodic(b[quiet:quiet + len(v)])
    rep["control_voice"] = {"planted_at_s": round(quiet / SR, 2), "taken_from_s": round(k / SR, 2), "longest_run_ms": pv["longest_run_ms"],
                            "found": bool(pv["longest_run_ms"] >= 200)}
    rep["original_mix_periodicity_for_scale"] = periodic(orig)
    rep["pass_when"] = "no held pitched tone in the effects (scream_check.tonal_runs), longest periodic run of the effects < 150 ms, and both planted controls found"
    rep["verdict"] = "PASS" if (not rep["effects_held_pitch_runs"] and rep["effects_periodicity"]["longest_run_ms"] < 150
                               and rep["control_tone"]["found"] and rep["control_voice"]["found"]) else "FAIL"
    return rep


# ---------------------------------------------------------------- picture for people who cannot listen

def overview(path: str, orig_p, fx_p, iv, plan, cues) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:  # noqa: BLE001
        return
    n = len(orig_p)
    cen = np.arange(0, n, int(0.01 * SR))
    win = int(WIN_S * SR)
    lo, lf = window_lufs(orig_p, cen, win), window_lufs(fx_p, cen, win)
    lf50 = window_lufs(fx_p, cen, int(0.05 * SR))
    T = n / SR
    rows = 4
    fig, axs = plt.subplots(rows, 1, figsize=(22, 3.3 * rows))
    for r, ax in enumerate(axs):
        a, b = T * r / rows, T * (r + 1) / rows
        m = (cen / SR >= a) & (cen / SR <= b)
        for v in iv:
            if v["end"] > a and v["start"] < b:
                ax.axvspan(v["start"], v["end"], color="#9ad" if v["kind"] == "word" else "#fc8", alpha=0.28, lw=0)
        ax.plot(cen[m] / SR, lo[m], color="k", lw=1.2, label="original mix, 400 ms")
        ax.plot(cen[m] / SR, lo[m] - MARGIN_DB, color="k", lw=0.6, ls=":", label="original - 14 dB")
        ax.plot(cen[m] / SR, lf[m], color="#d22", lw=1.3, label="effects, 400 ms")
        ax.plot(cen[m] / SR, lf50[m], color="#d22", lw=0.5, alpha=0.5, label="effects, 50 ms")
        for s in plan["shots"]:
            if a <= s["start"] <= b:
                ax.axvline(s["start"], color="#2a2", lw=0.8)
                ax.text(s["start"], -9.5, s["id"], color="#2a2", fontsize=8, rotation=90, va="top")
        for k, c in enumerate(cues):
            if a <= c["_t0"] <= b:
                ax.text(c["_t0"], -62 + 3.2 * (k % 4), c["id"], fontsize=6, color="#a00")
        ax.set_xlim(a, b); ax.set_ylim(-65, -8); ax.grid(alpha=0.25)
        ax.set_xticks(np.arange(math.ceil(a * 4) / 4, b, 0.25)); ax.tick_params(labelsize=7)
        ax.set_ylabel("LUFS (K-weighted)")
        if r == 0:
            ax.legend(loc="lower right", fontsize=7, ncol=4)
    fig.suptitle("Blades: effects bus against the original mix (blue = spoken words, orange = intro / unlisted voice, green = cuts)", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=70)
    plt.close(fig)


# ---------------------------------------------------------------- main

def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--plan", default=os.path.join(REPO, "data", "blades", "plan.json"))
    ap.add_argument("--cues", default=os.path.join(REPO, "data", "blades", "sfx_cues.json"))
    ap.add_argument("--timing", default=None, help="default: the plan's `timing`, relative to the repository")
    ap.add_argument("--out", default="/home/user/film/v4/sound")
    ap.add_argument("--licences", default=None, help="default: OUT/sfx_licences.json")
    ap.add_argument("--gain-db", type=float, default=0.0)
    ap.add_argument("--skip-missing", action="store_true")
    ap.add_argument("--no-plot", action="store_true")
    ap.add_argument("--no-tonal", action="store_true")
    a = ap.parse_args()
    if abs(a.gain_db) > 0.5 + 1e-9:
        raise SystemExit("--gain-db is limited to +/-0.5 dB: the original mix is not to be touched")

    plan = json.load(open(a.plan, encoding="utf-8"))
    spec = json.load(open(a.cues, encoding="utf-8"))
    timing_p = a.timing or (plan["timing"] if os.path.isabs(plan["timing"]) else os.path.join(REPO, plan["timing"]))
    timing = json.load(open(timing_p, encoding="utf-8"))
    sfx_dir = spec.get("sfx_dir", os.path.dirname(os.path.abspath(a.cues)))
    os.makedirs(a.out, exist_ok=True)
    warnings: list[str] = []
    failures: list[str] = []

    fps, T = plan["fps"], float(plan["duration"])
    n = int(round(T * SR))
    if abs(T * fps - round(T * fps)) > 1e-6:
        warnings.append(f"plan.duration {T} s is not a whole number of frames at {fps} fps")
    orig, sr = sf.read(plan["audio"], always_2d=True, dtype="float64")
    if sr != SR or orig.shape[1] != 2:
        raise SystemExit(f"the original mix must be 48 kHz stereo, got {sr} Hz x {orig.shape[1]}")
    src_len = len(orig)
    orig = orig[:n] if len(orig) >= n else np.vstack([orig, np.zeros((n - len(orig), 2))])
    orig_p = kpower(orig)

    # 1-2. the effects bus
    cues, missing, w = resolve(spec["cues"], plan, sfx_dir, a.skip_missing)
    warnings += w
    fx = np.zeros((n, 2))
    stems = []
    for c in cues:
        x = render_cue(c)
        s = int(round(c["_t0"] * SR))
        x = x[: n - s]
        fx[s:s + len(x)] += x
        stems.append((s, x))
        if c.get("_short_by_s"):
            warnings.append(f"cue {c['id']}: the recording ends {c['_short_by_s']} s before the cue does")

    # 3. the voice wins
    iv = protected_intervals(orig_p, timing, spec.get("protect", {}))
    centres, owner = centres_of(iv, n)
    win = int(WIN_S * SR)
    lo = window_lufs(orig_p, centres, win)
    lf_before = window_lufs(kpower(fx), centres, win)
    auto_db, fxa = enforce(orig_p, fx, centres)
    fxa_p = kpower(fxa)
    lf = window_lufs(fxa_p, centres, win)
    words = []
    for k, v in enumerate(iv):
        m = owner == k
        silent = lf[m] < -100.0
        mar = np.where(silent, 99.0, lo[m] - lf[m])
        mar_b = np.where(lf_before[m] < -100.0, 99.0, lo[m] - lf_before[m])
        j = int(np.argmin(mar))
        # the same comparison over the word's own interval (widened to 400 ms when the word is shorter)
        wa, wb = v["start"], v["end"]
        if wb - wa < WIN_S:
            mid = (wa + wb) / 2; wa, wb = mid - WIN_S / 2, mid + WIN_S / 2
        whole_fx = span_lufs(fxa_p, max(0, wa), wb)
        row = {**{kk: vv for kk, vv in v.items()}, "start": round(v["start"], 3), "end": round(v["end"], 3),
               "margin_db": round(float(mar[j]), 2), "worst_at_s": round(float(centres[m][j] / SR), 3),
               "original_lufs_there": round(float(lo[m][j]), 1), "effects_lufs_there": round(float(lf[m][j]), 1) if not silent[j] else None,
               "margin_before_automation_db": round(float(mar_b.min()), 2),
               "automation_db": round(float(auto_db[int(max(0, (v['start'] - WIN_S / 2) * SR)):int(min(n, (v['end'] + WIN_S / 2) * SR)) + 1].min()), 2),
               "margin_whole_word_db": round(span_lufs(orig_p, max(0, wa), wb) - whole_fx, 2) if whole_fx > -100 else 99.0}
        words.append(row)
    worst = min(words, key=lambda r: r["margin_db"])
    if worst["margin_db"] < MARGIN_DB:
        failures.append(f"margin {worst['margin_db']} dB < {MARGIN_DB} dB at {worst['name']}")
    if auto_db.min() < -0.05:
        warnings.append(f"the automatic gain acted: up to {auto_db.min():.1f} dB at {np.argmin(auto_db) / SR:.2f} s "
                        f"(for {np.count_nonzero(auto_db < -0.1) / SR:.2f} s in all); the cue gains were set for an idle safety net, so a cut has probably moved")

    # 4-5. sum, limit, fade
    g = 10 ** (a.gain_db / 20)
    pre = (orig + fxa) * g
    y, lim = master(pre)
    loud = integrated_lufs(y)
    if not (LUFS_RANGE[0] + 0.05 <= loud <= LUFS_RANGE[1] - 0.05):  # one static correction inside +/-0.5 dB, if it helps
        want = float(np.clip(a.gain_db + (np.clip(loud, LUFS_RANGE[0] + 0.15, LUFS_RANGE[1] - 0.15) - loud), -0.5, 0.5))
        if abs(want - a.gain_db) > 1e-3:
            warnings.append(f"static gain moved from {a.gain_db:+.2f} to {want:+.2f} dB to keep the loudness inside {LUFS_RANGE}")
            a.gain_db = want
            g = 10 ** (want / 20)
            pre = (orig + fxa) * g
            y, lim = master(pre)
    residual = y - pre
    lim_mask = lim.pop("_mask")
    lim["untouched_samples_pct"] = round(float((np.abs(residual).max(axis=1) == 0).mean() * 100), 3)
    lim["change_re_programme_db"] = round(float(10 * np.log10(kpower(residual).sum() / kpower(pre).sum() + 1e-20)), 1)  # K-weighted energy of (limited - unlimited) over the film
    fo = int(round(FADE_OUT_S * SR))
    y[n - fo:] *= half_cos(fo)[::-1][:, None]
    fx_out = fxa * g

    mix_p, fx_p_ = os.path.join(a.out, "mix.wav"), os.path.join(a.out, "effects.wav")
    sf.write(mix_p, y, SR, subtype="PCM_24")
    sf.write(fx_p_, fx_out, SR, subtype="PCM_24")

    # 6. measure what was written
    chk, sr2 = sf.read(mix_p, always_2d=True, dtype="float64")
    m_i = integrated_lufs(chk)
    m_tp = true_peak_db(chk)
    eb = ffmpeg_ebur128(mix_p)
    tail = chk[n - fo:]
    master_rep = {"file": mix_p, "sample_rate": sr2, "channels": chk.shape[1], "samples": len(chk), "seconds": len(chk) / sr2,
                  "frames_at_plan_fps": len(chk) / sr2 * fps, "integrated_lufs": round(m_i, 2), "true_peak_dbtp_4x": round(m_tp, 2),
                  "sample_peak_dbfs": round(float(20 * np.log10(np.abs(chk).max() + 1e-12)), 2), "ffmpeg_ebur128": eb,
                  "static_gain_db": round(a.gain_db, 3), "limiter": lim,
                  "fade_out": {"seconds": FADE_OUT_S, "shape": "raised cosine to zero", "last_sample_abs": float(np.abs(tail[-1]).max()),
                               "level_last_100ms_dbfs": round(float(20 * np.log10(np.sqrt((tail[-int(0.1 * SR):] ** 2).mean()) + 1e-12)), 1)},
                  "original_mix": {"file": plan["audio"], "sha256": sha256(plan["audio"]), "samples_in_file": src_len,
                                   "integrated_lufs_over_film": round(integrated_lufs(orig), 2), "true_peak_dbtp_4x": round(true_peak_db(orig), 2)}}
    # null test on the files as written: mix - effects - original must be nothing but the limiter's few moments and the end fade
    fxw, _ = sf.read(fx_p_, always_2d=True, dtype="float64")
    nul = chk - fxw - orig * g
    quiet = ~lim_mask
    quiet[n - fo:] = False
    lim_or_fade = ~quiet
    master_rep["null_test"] = {"what": "mix.wav - effects.wav - original (x static gain), on every sample outside the last 0.6 s and outside the samples the limiter changed",
                               "seconds_compared": round(float(quiet.sum() / SR), 3),
                               "max_abs_dbfs": round(float(20 * np.log10(np.abs(nul[quiet]).max() + 1e-12)), 1),
                               "one_24bit_step_dbfs": round(float(20 * np.log10(2.0 ** -23)), 1),
                               "seconds_excluded": round(float(lim_or_fade.sum() / SR), 3)}
    if master_rep["null_test"]["max_abs_dbfs"] > -120:
        failures.append(f"null test: the original is not passing through unchanged ({master_rep['null_test']['max_abs_dbfs']} dBFS residue)")
    if sr2 != SR or chk.shape[1] != 2 or len(chk) != n:
        failures.append(f"master is {len(chk)} samples at {sr2} Hz x {chk.shape[1]}, wanted {n} at {SR} x 2")
    if not (LUFS_RANGE[0] <= m_i <= LUFS_RANGE[1]):
        failures.append(f"integrated loudness {m_i:.2f} LUFS outside {LUFS_RANGE}")
    if m_tp > CEILING_DBTP or (isinstance(eb.get("true_peak_dbtp"), float) and eb["true_peak_dbtp"] > CEILING_DBTP):
        failures.append(f"true peak {m_tp:.2f} dBTP (ffmpeg {eb.get('true_peak_dbtp')}) above {CEILING_DBTP}")

    # cue table, peaks against cuts, words the cues are locked to
    shots = {s["id"]: s for s in plan["shots"]}
    lic = {}
    lic_p = a.licences or os.path.join(a.out, "sfx_licences.json")
    if os.path.exists(lic_p):
        L = json.load(open(lic_p, encoding="utf-8"))
        lic = {str(e["id"]): e for e in (L["items"] if isinstance(L, dict) else L)}
    else:
        warnings.append(f"no licence record at {lic_p}")
    table, peak_checks = [], []
    gain = 10 ** (auto_db / 20) * g
    for c, (s, x) in zip(cues, stems):
        xa = x * gain[s:s + len(x), None]
        pk_t = energy_peak_time(xa, c["_t0"], float(c.get("peak_win_ms", 30)) / 1000)
        xp = kpower(xa)
        cc = np.arange(0, len(xa), int(0.01 * SR))
        row = {"id": c["id"], "shot": c["shot"], "anchor": c.get("anchor", "start"), "offset": c.get("offset", 0.0),
               "start_s": round(c["_t0"], 4), "end_s": round(c["_t1"], 4), "sfx_id": c["sfx_id"],
               "title": c.get("title") or lic.get(str(c["sfx_id"]), {}).get("title"), "src": c["_src"], "src_in": c.get("src_in", 0.0),
               "gain_db": c.get("gain_db", 0.0), "fade_in": c.get("fade_in", 0.01), "fade_out": c.get("fade_out", 0.05),
               "highpass_hz": c.get("highpass_hz"), "lowpass_hz": c.get("lowpass_hz"),
               "energy_peak_s": round(pk_t, 4) if pk_t is not None else None,
               "max_momentary_lufs": round(float(window_lufs(xp, cc, win).max()), 1) if len(cc) else None,
               "max_50ms_lufs": round(float(window_lufs(xp, cc, int(0.05 * SR)).max()), 1) if len(cc) else None,
               "automation_db_min": round(float(auto_db[s:s + len(x)].min()), 2) if len(x) else 0.0, "note": c.get("note", "")}
        if c.get("peak_on"):
            st = float(shots[c["peak_on"]]["start"])
            seen = math.ceil(st * fps - 1e-6) / fps
            hard = shots[c["peak_on"]].get("trans", {}).get("type", "cut") in ("cut", "flash")
            ref = seen if hard else st
            d_ref, d_nom = pk_t - ref, pk_t - st
            tol = float(c.get("peak_tol_ms", FRAME_TOL_S * 1000)) / 1000
            ok = abs(d_ref) <= tol and abs(d_nom) <= tol + 1e-9
            peak_checks.append({"cue": c["id"], "shot": c["peak_on"], "transition": shots[c["peak_on"]].get("trans", {}).get("type", "cut"),
                                "plan_start_s": st, "cut_seen_s": round(seen, 4), "energy_peak_s": round(pk_t, 4),
                                "peak_minus_cut_as_seen_ms": round(d_ref * 1000, 1), "peak_minus_plan_start_ms": round(d_nom * 1000, 1),
                                "energy_window_ms": float(c.get("peak_win_ms", 30)), "tolerance_ms": round(tol * 1000, 1),
                                "within_one_frame": bool(abs(d_ref) <= FRAME_TOL_S and abs(d_nom) <= FRAME_TOL_S + 1e-9), "within_tolerance": bool(ok)})
            row["peak_on"] = c["peak_on"]
            if not ok:
                failures.append(f"cue {c['id']}: energy peak {d_ref * 1000:+.0f} ms from the cut of {c['peak_on']} as seen ({d_nom * 1000:+.0f} ms from its plan start)")
        if c.get("word") is not None:
            wd = timing["words"][int(c["word"])]
            want = float(c.get("word_offset", 0.0))
            d = c["_t0"] - float(wd["start"])
            row["word"] = {"index": int(c["word"]), "word": wd["word"], "word_start_s": wd["start"], "cue_start_minus_word_start_ms": round(d * 1000, 1),
                           "designed_ms": round(want * 1000, 1), "drift_ms": round((d - want) * 1000, 1)}
            if abs(d - want) > 0.06:
                warnings.append(f"cue {c['id']} was placed {want * 1000:+.0f} ms from the start of «{wd['word']}» ({wd['start']} s) and has drifted "
                                f"{(d - want) * 1000:+.0f} ms with the picture; move its offset if it should stay with the word")
        table.append(row)

    tonal = {"ran": False, "skipped": True} if a.no_tonal else tonal_check(fx_out, orig)
    if tonal.get("ran") and tonal.get("verdict") != "PASS":
        failures.append("held-tone / periodicity check on the effects bus did not pass")
    if not a.no_tonal and not tonal.get("ran"):
        warnings.append(f"tonal check did not run: {tonal.get('error')}")

    used = sorted({str(c["sfx_id"]) for c in cues}, key=lambda s: (len(s), s))
    lic_rows = []
    for sid in used:
        e = lic.get(sid)
        if not e:
            failures.append(f"no licence record for recording {sid}")
            lic_rows.append({"id": sid, "licence": None})
        else:
            lic_rows.append({k: e.get(k) for k in ("id", "title", "page", "download_page", "asset_url", "licence", "licence_code", "statement_on_page", "checked", "sha256")})
            if e.get("licence_code") != "sfxFree":
                failures.append(f"recording {sid}: the page does not state the Mixkit Sound Effects Free License")

    fx_i = float(-0.691 + 10 * np.log10(kpower(fx_out)[np.abs(fx_out).max(axis=1) > 1e-6].mean() + 1e-14)) if np.any(fx_out) else -140.0
    rep = {
        "verdict": "PASS" if not failures else "FAIL", "failures": failures, "warnings": warnings,
        "made": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "inputs": {"plan": os.path.abspath(a.plan), "plan_sha256": sha256(a.plan), "plan_mtime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(a.plan))),
                   "cues": os.path.abspath(a.cues), "cues_sha256": sha256(a.cues), "timing": os.path.abspath(timing_p), "fps": fps, "duration": T},
        "master": master_rep,
        "rule": {"text": "at every instant from the start to the end of each protected interval, the 400 ms K-weighted loudness of the effects bus "
                         "is at least 14 dB under that of the original mix in the same window (window centred on the instant; centres every 5 ms "
                         "and at both ends of the interval). margin_whole_word_db is the same comparison over the interval itself, widened to 400 ms "
                         "when the word is shorter. A margin of 99 means no effect sounds in any window of that interval.",
                 "margin_db": MARGIN_DB, "automation_target_db": MARGIN_DB + SAFETY_DB, "window_s": WIN_S, "centre_spacing_s": HOP_S,
                 "protected": {"words": sum(v["kind"] == "word" for v in iv), "intro": [v for v in iv if v["kind"] == "intro"],
                               "voiced_outside_word_list": [{"start": round(v["start"], 3), "end": round(v["end"], 3)} for v in iv if v["kind"] == "unlisted"],
                               "extra": [v for v in iv if v["kind"] == "extra"]}},
        "worst_margin": {"db": worst["margin_db"], "name": worst["name"], "roman": worst.get("roman"), "index": worst.get("index"), "at_s": worst["worst_at_s"]},
        "automation": {"deepest_db": round(float(auto_db.min()), 2), "seconds_below_0p1_db": round(float(np.count_nonzero(auto_db < -0.1) / SR), 3)},
        "effects_bus": {"file": fx_p_, "loudness_while_sounding_lufs": round(fx_i, 1), "max_momentary_lufs": round(float(window_lufs(kpower(fx_out), np.arange(0, n, 480), win).max()), 1),
                        "peak_dbfs": round(float(20 * np.log10(np.abs(fx_out).max() + 1e-12)), 1), "cues": len(cues), "recordings": len(used)},
        "per_word": words,
        "peaks_on_cuts": peak_checks,
        "nothing_voice_like": tonal,
        "cues": table,
        "unresolved_cues": missing,
        "licences": lic_rows,
    }
    json.dump(rep, open(os.path.join(a.out, "mix_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if not a.no_plot:
        overview(os.path.join(a.out, "mix_overview.png"), orig_p, kpower(fx_out), iv, plan, cues)

    print(f"mix.wav: {len(chk)} samples ({len(chk) / sr2:.3f} s), {m_i:.2f} LUFS, true peak {m_tp:.2f} dBTP "
          f"(ffmpeg: {eb.get('integrated_lufs')} LUFS, {eb.get('true_peak_dbtp')} dBTP); limiter max {lim['max_gain_reduction_db']} dB in {lim['events']} places")
    print(f"worst margin {worst['margin_db']} dB at «{worst['name']}» ({worst['worst_at_s']} s); automation deepest {auto_db.min():.2f} dB; "
          f"{len(cues)} cues from {len(used)} recordings; peaks on cuts {sum(p['within_tolerance'] for p in peak_checks)}/{len(peak_checks)}; tonal {tonal.get('verdict', 'not run')}")
    for wmsg in warnings:
        print("warning:", wmsg)
    for f in failures:
        print("FAIL:", f)
    return 2 if missing else (3 if failures else 0)


if __name__ == "__main__":
    sys.exit(main())
