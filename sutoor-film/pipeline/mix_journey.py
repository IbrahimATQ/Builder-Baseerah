#!/usr/bin/env python3
"""Mix and master the Journey edition so the voice sits in ONE steady place over everything.

  * voice bus: the finished voice (voice_edges.py), -16 LUFS integrated, no other processing
  * music: a presence dip at 2.8 kHz; a gentle duck driven by the VOICE ITSELF (not by word times):
    150 ms look-ahead, 5 dB, held through any pause shorter than 1.5 s and released over 1.3 s, so it
    never pumps in the pauses; then per-hemistich automation that holds the music a steady 14 dB
    (K-weighted) under the voice in every line
  * beds (ambience + effects): pulled down only in lines where the voice would otherwise be less
    than 12 dB over voice-free music + beds
  * master: static gain to -14 LUFS, then a 4x-oversampled peak limiter at -1.6 dBFS (true peak about
    -1.5 dBTP), and a fade to silence over the last 1.8 s; no dynamic loudness normalisation
  * the report lists, per hemistich, the voice's margin over music and over everything else

Usage: python mix_journey.py timing.json voice.wav score.wav ambience.wav sfx.wav OUT_DIR
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy.ndimage import maximum_filter1d
from scipy.signal import resample_poly

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mix_master import load_stereo_48k, peaking  # noqa: E402

SR = 48000
MUSIC_UNDER_VOICE_DB = 14.0
BEDS_UNDER_VOICE_DB = 12.0


def lufs(meter: pyln.Meter, x: np.ndarray) -> float:
    if len(x) < int(0.4 * SR):
        return -70.0
    v = meter.integrated_loudness(x)
    return float(v) if np.isfinite(v) else -70.0


def ramp_automation(n: int, spans: list[tuple[float, float, float]], ramp: float = 0.5) -> np.ndarray:
    """Per-span gains (dB), held across each span, crossfading in the pauses between spans."""
    knots_t, knots_g = [0.0], [spans[0][2]]
    for a, b, g in spans:
        knots_t += [a - ramp * 0.5, b + ramp * 0.5]
        knots_g += [g, g]
    knots_t.append(n / SR)
    knots_g.append(spans[-1][2])
    order = np.argsort(knots_t, kind="stable")
    t = np.arange(n) / SR
    return (10 ** (np.interp(t, np.array(knots_t)[order], np.array(knots_g)[order]) / 20)).astype(np.float32)


def voice_duck(vbus: np.ndarray, depth_db: float = -5.0, look: float = 0.15, hold: float = 1.5, release: float = 1.3) -> np.ndarray:
    hop = 240
    m = vbus.mean(axis=1)
    rms = np.sqrt(np.convolve(m ** 2, np.ones(hop * 4) / (hop * 4), mode="same"))[::hop]
    ref = np.percentile(rms[rms > 1e-5], 95) if np.any(rms > 1e-5) else 1.0
    act = (rms > ref * 10 ** (-35 / 20)).astype(np.float32)
    k_hold = int(hold * SR / hop)
    # fill pauses shorter than `hold`, and start `look` seconds early
    filled = act.copy()
    idx = np.where(act > 0)[0]
    for a, b in zip(idx[:-1], idx[1:]):
        if 1 < b - a <= k_hold:
            filled[a:b] = 1
    filled = maximum_filter1d(filled, size=int(look * SR / hop) * 2 + 1)
    out = np.zeros_like(filled)
    att, rel = np.exp(-hop / (0.15 * SR)), np.exp(-hop / (release * SR))
    v = 0.0
    for i, c in enumerate(filled):
        v = c + (v - c) * (att if c > v else rel)
        out[i] = v
    return np.repeat(10 ** (out * depth_db / 20), hop)[: len(vbus)].astype(np.float32)


def main(timing_p: str, voice_p: str, score_p: str, amb_p: str, sfx_p: str, out_dir: str) -> None:
    timing = json.load(open(timing_p, encoding="utf-8"))
    T = timing["duration"]
    n = int(T * SR)
    meter = pyln.Meter(SR)
    voice, score, amb, sfx = (load_stereo_48k(p, n)[:n] for p in (voice_p, score_p, amb_p, sfx_p))
    vs = timing["voice_film_start"]
    vbus = np.zeros((n, 2), np.float32)
    s = int(vs * SR)
    vbus[s:s + len(voice[: n - s])] = voice[: n - s]
    act = np.abs(vbus).max(axis=1) > 1e-3
    vbus *= 10 ** ((-16.0 - lufs(meter, vbus[act])) / 20)

    music = peaking(score, 2800, -3.5, 0.8)
    music *= 10 ** ((-25.0 - lufs(meter, music)) / 20)
    pro = 10 ** (np.interp(np.arange(n) / SR, [0.0, vs - 0.7, vs - 0.1, T], [6.0, 6.0, 0.0, 0.0]) / 20)  # the prologue carries the opening
    music *= pro[:, None].astype(np.float32)
    duck = voice_duck(vbus)
    music *= duck[:, None]

    a_act = np.abs(amb).max(axis=1) > 1e-5
    amb = amb * 10 ** ((float(os.environ.get("AMBIENCE_LUFS", "-32")) - lufs(meter, amb[a_act])) / 20)
    f_act = np.abs(sfx).max(axis=1) > 1e-4
    sfx = sfx * 10 ** ((-25.0 - lufs(meter, sfx[f_act])) / 20)

    H = timing["hemistichs"]
    spans = [(h["start"], h["end"]) for h in H.values()]

    def seg(x: np.ndarray, a: float, b: float) -> np.ndarray:
        return x[int(a * SR):int(b * SR)]

    # music: hold it MUSIC_UNDER_VOICE_DB under the voice in every line (two passes, clamped)
    m_gain = np.ones(n, np.float32)
    for _ in range(2):
        g = []
        for a, b in spans:
            margin = lufs(meter, seg(vbus, a, b)) - lufs(meter, seg(music * m_gain[:, None], a, b))
            g.append(float(np.clip(margin - MUSIC_UNDER_VOICE_DB, -8.0, 8.0)))
        prev = 20 * np.log10(np.array([m_gain[int((a + b) / 2 * SR)] for a, b in spans]))
        m_gain = ramp_automation(n, [(a, b, p + d) for (a, b), p, d in zip(spans, prev, g)])
    music = music * m_gain[:, None]

    # beds: only where the voice would be under BEDS_UNDER_VOICE_DB over everything else
    beds0 = amb + sfx
    b_db = [0.0] * len(spans)
    for _ in range(3):
        beds = beds0 * ramp_automation(n, [(a, b, d) for (a, b), d in zip(spans, b_db)], ramp=0.6)[:, None]
        for i, (a, b) in enumerate(spans):
            margin = lufs(meter, seg(vbus, a, b)) - lufs(meter, seg(music + beds, a, b))
            b_db[i] = float(np.clip(b_db[i] + min(0.0, margin - BEDS_UNDER_VOICE_DB) * 1.6, -10.0, 0.0))
    beds = beds0 * ramp_automation(n, [(a, b, d) for (a, b), d in zip(spans, b_db)], ramp=0.6)[:, None]

    mix = vbus + music + beds
    os.makedirs(out_dir, exist_ok=True)
    sf.write(os.path.join(out_dir, "voice_bus.wav"), vbus, SR, subtype="FLOAT")
    sf.write(os.path.join(out_dir, "music_ducked.wav"), music, SR, subtype="FLOAT")
    sf.write(os.path.join(out_dir, "beds.wav"), beds, SR, subtype="FLOAT")
    sf.write(os.path.join(out_dir, "mix_premaster.wav"), mix, SR, subtype="FLOAT")

    # master: static gain, oversampled limiter, end fade
    mix = mix * 10 ** ((-14.0 - lufs(meter, mix)) / 20)
    up = resample_poly(mix, 4, 1, axis=0).astype(np.float32)
    lim_in = os.path.join(out_dir, "_lim_in.wav")
    lim_out = os.path.join(out_dir, "_lim_out.wav")
    sf.write(lim_in, up, SR * 4, subtype="FLOAT")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", lim_in, "-af", "alimiter=limit=0.832:attack=3:release=60:level=disabled:asc=1",
                    "-c:a", "pcm_f32le", lim_out], check=True)
    y, _ = sf.read(lim_out, dtype="float32", always_2d=True)
    y = resample_poly(y, 1, 4, axis=0).astype(np.float32)[:n]
    os.remove(lim_in)
    os.remove(lim_out)
    fade_n = int(1.8 * SR)
    y[-fade_n:] *= (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, fade_n)))[:, None]
    master = os.path.join(out_dir, "mix_master.wav")
    sf.write(master, y, SR, subtype="PCM_24")
    eb = subprocess.run(["ffmpeg", "-hide_banner", "-i", master, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    tp = float(eb[eb.rindex("Peak:"):].split()[1]) if "Peak:" in eb else None
    I_ = float(eb[eb.rindex(" I: "):].split()[1])

    rep = {"master_integrated_lufs": I_, "master_true_peak_dbtp": tp, "per_hemistich": {}}
    for (k, h), (a, b) in zip(H.items(), spans):
        v = lufs(meter, seg(vbus, a, b))
        rep["per_hemistich"][k] = {"voice_over_music_db": round(v - lufs(meter, seg(music, a, b)), 1),
                                   "voice_over_all_else_db": round(v - lufs(meter, seg(music + beds, a, b)), 1)}
    json.dump(rep, open(os.path.join(out_dir, "mix_report.json"), "w"), indent=1)
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:7])
