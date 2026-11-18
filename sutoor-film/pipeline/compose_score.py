#!/usr/bin/env python3
"""Original score for «النِصالُ عَلى النِصالِ», rendered from CC0 VSCO-2 CE samples.

Tonal centre E (the reciter's voice centres just below E). Maqam Kurd on E
(E F G A B C D) for the elegiac acts; Hijaz on E (E F G# A B C D) for the
wounds of Act V; resolution on an open E-B fifth lit by Hijaz's G#.

Musical ideas
  * The sigh: F -> E semitone (Kurd's flat second falling to the tonic).
  * The trot (خَبَب): a dotted pizzicato gait in Act III that quickens — the
    "trotting of the nights" literally outrunning the tethered horses.
  * Act IV withdraws to near-silence (indifference): one piano voice, a
    held high violin.
  * Act V swells (timpani roll, tremolo, Hijaz harmony) under the arrows.
  * Act VI arrives: open fifths, horn, a single timpani stroke on
    «تَكَسَّرَتِ النِصالُ», then a long decaying resolution.

Every event is placed relative to hemistich timings from the forced
alignment, so the music breathes with the recitation.

Usage: python compose_score.py edl_timing.json OUT_DIR
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(__file__))
from sampler import SR, Bus, Instrument, hall_ir, highpass, lowpass, render_note, reverb, wind  # noqa: E402

VSCO = os.environ.get("VSCO_DIR", "/home/user/sgossner/vsco-2-ce")


def m(name: str) -> int:
    names = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    base, acc, octv = name[0], name[1:-1], int(name[-1])
    return 12 * (octv + 1) + names[base] + (1 if acc == "#" else -1 if acc == "b" else 0)


def load_instruments() -> dict[str, Instrument]:
    s = os.path.join(VSCO, "Strings")
    piano_map = {}
    with open(os.path.join(VSCO, "Keys/Upright Piano/MappingChart.txt")) as f:
        for line in f:
            if "=" in line and line[:3].isdigit():
                k, v = line.strip().split("=")
                piano_map[k] = int(v)
    return {
        "cello": Instrument(s, "Cello Section/susvib/*.wav", octave_offset=1),
        "viola": Instrument(s, "Viola Section/susvib/*.wav", octave_offset=1),
        "violin": Instrument(s, "Violin Section/susVib/*.wav", octave_offset=1),
        "cbass": Instrument(s, "Solo Contrabass/SusNV/*.wav", octave_offset=1),
        "cbtrem": Instrument(s, "Solo Contrabass/Trem/*.wav", octave_offset=1),
        "cellotrem": Instrument(s, "Cello Section/trem/*.wav", octave_offset=1),
        "cbpizz": Instrument(s, "Solo Contrabass/Pizz/*.wav", octave_offset=1, loopable=False),
        "cellopizz": Instrument(s, "Cello Section/pizzT/*.wav", octave_offset=1, layer_re=r"_v(\d)_", loopable=False),
        "harp": Instrument(s, "Harp/*.wav", octave_offset=0, loopable=False),
        "horn": Instrument(os.path.join(VSCO, "Brass/F Horn"), "sus/*.wav", octave_offset=1),
        "piano": Instrument(os.path.join(VSCO, "Keys/Upright Piano"), "Player_dyn1_rr1_*.wav", mapping=piano_map, loopable=False),
    }


def timpani(kind: str, idx: int = 2, layer: int = 3) -> np.ndarray:
    from sampler import load

    base = os.path.join(VSCO, "Percussion/Timpani")
    path = (
        os.path.join(base, "Rolls", f"Timpani{idx}_Roll_v{layer}_rr1_Sum.wav")
        if kind == "roll"
        else os.path.join(base, f"Timpani{idx}_Hit_v{layer}_rr1_Sum.wav")
    )
    return load(path)


def compose(timing: dict, out_dir: str) -> dict:
    T = timing["duration"]
    h = {k: (v["start"], v["end"]) for k, v in timing["hemistichs"].items()}  # film-time seconds
    v_start = lambda n: h[f"v{n}a"][0]  # noqa: E731
    v_mid = lambda n: h[f"v{n}b"][0]  # noqa: E731
    v_end = lambda n: h[f"v{n}b"][1]  # noqa: E731
    voice_end = v_end(6)

    journey = os.environ.get("SCORE_EDITION", "") == "journey"
    I = load_instruments()
    low, mid, high, pulse, keys, perc = (Bus(T) for _ in range(6))

    # ---------------- PROLOGUE: darkness, a held breath ----------------
    t0 = 0.0
    low.add(render_note(I["cbass"], m("E2"), v_start(1) + 2.0, layer=1, attack=2.5, release=2.0), t0, 0.55)
    keys.add(render_note(I["piano"], m("E1"), 7.0, attack=0.002, release=3.0), 0.55, 0.32)
    keys.add(render_note(I["piano"], m("B1"), 6.0, attack=0.002, release=3.0), 2.6, 0.16)

    # ---------------- ACT I: mortality (Kurd, very low, restrained) ----------------
    a1 = v_start(1) - 0.6
    mid.add(render_note(I["cello"], m("E3"), v_end(1) - a1 + 0.6, layer=1, attack=1.4, release=1.2), a1, 0.36, -0.25)
    mid.add(render_note(I["cello"], m("B2"), v_end(1) - a1 + 0.6, layer=1, attack=1.8, release=1.2), a1 + 0.3, 0.30, 0.2)
    # the sigh F -> E under «أَواخِرُنا عَلى هامِ الأَوالي»
    s = v_mid(1)
    mid.add(render_note(I["viola"], m("F3"), 1.5, layer=1, attack=0.6, release=0.8), s, 0.24, 0.35)
    mid.add(render_note(I["viola"], m("E3"), v_end(1) - s, layer=1, attack=0.5, release=1.6), s + 1.35, 0.24, 0.35)
    low.add(render_note(I["cbass"], m("E2"), v_end(2) - v_end(1) + 1.0, layer=1, attack=1.0, release=1.5), v_end(1) - 0.8, 0.5)

    # ---------------- ACT II: futile preparation (tension over E pedal) ----------------
    a2 = v_start(2) - 0.2
    # «نُعِدُّ المَشرَفِيَّةَ وَالعَوالي»: E minor colour, violas pulse quietly
    for n, pan in (("G3", -0.3), ("B3", 0.3)):
        mid.add(render_note(I["viola"], m(n), v_mid(2) - a2 + 0.4, layer=1, attack=0.8, release=0.9), a2, 0.2, pan)
    mid.add(render_note(I["cello"], m("E3"), v_end(2) - a2 + 0.5, layer=1, attack=0.9, release=1.0), a2, 0.32, -0.2)
    # «وَتَقتُلُنا المَنونُ بِلا قِتالِ»: F major over E — the cold dissonance of fate
    b2 = v_mid(2) - 0.15
    for n, pan, g in (("F3", -0.3, 0.26), ("A3", 0.25, 0.2), ("C4", 0.4, 0.15)):
        mid.add(render_note(I["viola" if n != "F3" else "cello"], m(n), v_end(2) - b2 + 0.6, layer=1, attack=0.7, release=1.4), b2, g, pan)
    perc.add(timpani("hit", 4, 1), b2 + 0.55, 0.32)  # one muffled stroke on «المَنونُ» (drum 4 is tuned to E)
    low.add(render_note(I["cbass"], m("E2"), v_end(3) - v_start(3) + 2.0, layer=1, attack=0.8, release=1.5), v_start(3) - 0.6, 0.48)

    # ---------------- ACT III: the trot of the nights (pizzicato gait quickens) ----------------
    p0, p1 = v_start(3) - 0.1, v_end(3) + 0.35
    beat0, beat1 = 0.52, 0.36  # seconds per gait cycle, accelerating
    t = p0
    cycle = 0
    while t < p1 and not journey:  # the Journey edition uses real distant hooves instead
        frac = (t - p0) / max(p1 - p0, 0.1)
        beat = beat0 + (beat1 - beat0) * frac
        vel = 0.2 + 0.35 * frac
        note_a, note_b = ("E2", "B2") if cycle % 4 != 3 else ("E2", "C3")
        pulse.add(render_note(I["cbpizz"], m(note_a), 0.9, layer=3, attack=0.002, release=0.5), t, vel * 0.6, -0.15)  # v3 layer is pitch-clean; v1 smears
        pulse.add(render_note(I["cellopizz"], m(note_b), 0.7, layer=1, attack=0.002, release=0.4), t + beat * 0.62, vel * 0.8, 0.2)
        t += beat
        cycle += 1
    # high violins: the night sky
    b4 = v_mid(3) - (1.1 if journey else 0.4)
    mid.add(render_note(I["violin"], m("B4"), v_end(3) - b4 + 0.6, layer=1, attack=1.2, release=1.4), b4, 0.13, 0.3)
    mid.add(render_note(I["cello"], m("E3"), v_end(3) - v_start(3) + 0.6, layer=1, attack=0.6, release=1.2), v_start(3), 0.24, -0.2)

    # ---------------- ACT IV: indifference (withdrawal) ----------------
    a4 = v_start(4)
    high.add(render_note(I["violin"], m("E5"), v_end(4) - a4 + 1.2, layer=1, attack=1.6, release=1.6), a4 - 0.3, 0.085, 0.25)
    keys.add(render_note(I["piano"], m("E4"), 4.0, attack=0.002, release=2.5), a4 + 0.05, 0.22, 0.1)
    keys.add(render_note(I["piano"], m("B3"), 4.0, attack=0.002, release=2.5), v_mid(4) - 0.05, 0.16, -0.1)
    keys.add(render_note(I["piano"], m("G3"), 4.0, attack=0.002, release=2.5), v_mid(4) - 0.05, 0.12, -0.15)
    keys.add(render_note(I["piano"], m("F4"), 2.0, attack=0.002, release=1.5), v_end(4) - 0.25, 0.14, 0.15)
    keys.add(render_note(I["piano"], m("E4"), 4.0, attack=0.002, release=2.5), v_end(4) + 0.25, 0.13, 0.15)
    low.add(render_note(I["cbass"], m("E2"), v_end(4) - a4 + 0.5, layer=1, attack=1.5, release=1.0), a4, 0.22)

    # ---------------- ACT V: arrows of time (Hijaz, swelling) ----------------
    a5 = v_start(5) - (0.9 if journey else 0.2)  # the Journey edition bridges the pause into each act
    e5 = v_end(5) + 0.15
    roll = timpani("roll", 4, 3)[: int((e5 - a5 + 0.4) * SR)]  # drum 4 roll sounds E (verified); drum 1 is F#
    env = np.linspace(0.0, 1.0, len(roll), dtype=np.float32) ** 1.8
    perc.add(roll * env[:, None], a5, 0.5)
    # (the VSCO contrabass tremolo E sample measures strong C#/C/A# partials, so the clean sustain is used)
    low.add(render_note(I["cbass"], m("E2"), e5 - a5, layer=3, attack=1.5, release=0.6), a5, 0.42)
    mid.add(render_note(I["cellotrem"], m("E3"), e5 - a5, layer=1, attack=1.2, release=0.6), a5 + 0.2, 0.3, -0.25)
    # Hijaz colour: F -> G# -> (D) building
    mid.add(render_note(I["viola"], m("F3"), v_mid(5) - a5 + 0.3, layer=1, attack=0.9, release=0.6), a5, 0.22, 0.3)
    mid.add(render_note(I["viola"], m("G#3"), e5 - v_mid(5) + 0.3, layer=1, attack=0.6, release=0.7), v_mid(5) - 0.1, 0.27, 0.3)
    high.add(render_note(I["violin"], m("D5"), e5 - v_mid(5), layer=1, attack=1.2, release=0.7), v_mid(5), 0.11, -0.3)
    high.add(render_note(I["violin"], m("B4"), e5 - v_mid(5), layer=1, attack=1.0, release=0.7), v_mid(5) + 0.4, 0.12, 0.3)
    mid.add(render_note(I["horn"], m("E3"), e5 - v_mid(5) + 0.2, layer=1, attack=1.0, release=0.6), v_mid(5) + 0.3, 0.13, -0.1)

    # ---------------- ACT VI: blades upon blades (arrival, resolution) ----------------
    a6 = v_start(6) - (0.9 if journey else 0.05)
    end_all = T - 0.2
    if journey:  # the score drops out after «النِصالِ»; only ember and wind remain
        end_all = voice_end + 2.6
    hold = end_all - a6
    low.add(render_note(I["cbass"], m("E2"), hold - 1.5, layer=3, attack=0.25, release=4.5), a6, 0.55)
    for n, inst, g, pan in (
        ("E3", "cello", 0.36, -0.3), ("B3", "viola", 0.26, 0.3), ("E4", "violin", 0.16, -0.2),
        ("G#4", "violin", 0.10, 0.35), ("B4", "violin", 0.08, 0.1),
    ):
        mid_or_high = high if inst == "violin" else mid
        mid_or_high.add(render_note(I[inst], m(n), hold - 1.2, layer=1, attack=0.45, release=4.5), a6, g, pan)
    mid.add(render_note(I["horn"], m("B2"), voice_end - a6 + 2.0, layer=2, attack=0.6, release=3.0), a6 + 0.2, 0.16, -0.15)
    mid.add(render_note(I["horn"], m("E3"), voice_end - a6 + 2.5, layer=2, attack=0.8, release=3.0), a6 + 0.6, 0.13, 0.15)
    strike = v_mid(6) + 0.35  # «تَكَسَّرَتِ النِصالُ»
    perc.add(timpani("hit", 4, 3), strike, 0.5)
    keys.add(render_note(I["piano"], m("E1"), 7.0, attack=0.002, release=4.0), strike, 0.26)
    keys.add(render_note(I["piano"], m("E2"), 7.0, attack=0.002, release=4.0), strike, 0.18)
    if journey:
        q = float(os.environ.get("QUENCH_T", voice_end + 3.35))  # the seawater quench
        from scipy.signal import resample_poly
        anvil, asr = sf.read(os.path.join(VSCO, "Percussion/Anvil_Hit1_v2_Sum.wav"), dtype="float32", always_2d=True)
        if asr != SR:
            anvil = resample_poly(anvil, SR, asr, axis=0).astype(np.float32)
        anvil = np.repeat(anvil[:, :1], 2, axis=1) if anvil.shape[1] == 1 else anvil[:, :2]
        perc.add(highpass(anvil, 300), q, 0.16)
        keys.add(render_note(I["piano"], m("E1"), 6.0, attack=0.002, release=4.0), q, 0.24)
        low.add(render_note(I["cbass"], m("E2"), 3.5, layer=1, attack=0.05, release=3.0), q, 0.3)
        c0 = float(os.environ.get("CREDITS_T", T - 3.4))
        mid.add(render_note(I["cello"], m("E3"), T - c0 - 0.4, layer=1, attack=1.0, release=1.8), c0, 0.22, -0.25)
        mid.add(render_note(I["viola"], m("B3"), T - c0 - 0.4, layer=1, attack=1.2, release=1.8), c0 + 0.15, 0.17, 0.25)
    # coda: the line rises and settles, then a last single high note
    if not journey:
      high.add(render_note(I["violin"], m("E5"), end_all - voice_end - 0.5, layer=1, attack=1.4, release=3.0), voice_end + 0.2, 0.09, 0.2)
      keys.add(render_note(I["harp"], m("E4"), 6.0, attack=0.002, release=4.0), voice_end + 1.6, 0.2, 0.25)
      keys.add(render_note(I["harp"], m("B4"), 6.0, attack=0.002, release=4.0), voice_end + 2.3, 0.14, -0.2)
      keys.add(render_note(I["piano"], m("E5"), 5.0, attack=0.002, release=3.5), voice_end + 3.3, 0.11, 0.1)

    # ---------------- AMBIENCE: wind that rises with the drama ----------------
    w = wind(T, seed=5)
    tt = np.arange(len(w)) / SR
    wenv = np.interp(tt, [0, 1.5, v_start(1), v_start(4), v_end(4), v_start(5), v_start(6), voice_end, T - 2, T],
                     [0, 0.9, 0.55, 0.4, 0.3, 0.5, 0.65, 0.6, 0.35, 0])
    amb = (w * wenv[:, None]).astype(np.float32)

    # ---------------- MIX: reverb, tone, stems ----------------
    ir = hall_ir(3.4)
    stems = {
        "low": reverb(lowpass(low.buf, 1800), ir, 0.35),
        "mid": reverb(mid.buf, ir, 0.45),
        "high": reverb(lowpass(high.buf, 9000), ir, 0.55),
        "pulse": reverb(pulse.buf, ir, 0.3),
        "keys": reverb(keys.buf, ir, 0.5),
        "perc": reverb(highpass(perc.buf, 35), ir, 0.4),
        "ambience": highpass(amb, 90),
    }
    gains = {"low": 1.0, "mid": 1.0, "high": 1.0, "pulse": 1.0, "keys": 1.0, "perc": 0.9, "ambience": 0.10}
    n = int(T * SR)
    music = sum(stems[k][:n] * gains[k] for k in stems if k != "ambience")
    os.makedirs(out_dir, exist_ok=True)
    peak = float(np.max(np.abs(music))) or 1.0
    music = music / peak * 0.7
    sf.write(os.path.join(out_dir, "score.wav"), music, SR, subtype="FLOAT")
    sf.write(os.path.join(out_dir, "ambience.wav"), stems["ambience"][:n] * gains["ambience"], SR, subtype="FLOAT")
    for k, v in stems.items():
        sf.write(os.path.join(out_dir, f"stem_{k}.wav"), v[:n] / peak * 0.7, SR, subtype="FLOAT")
    return {"duration": T, "peak_norm": peak}


if __name__ == "__main__":
    timing = json.load(open(sys.argv[1], encoding="utf-8"))
    print(compose(timing, sys.argv[2]))
