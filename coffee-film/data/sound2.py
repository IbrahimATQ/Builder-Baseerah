#!/usr/bin/env python3
"""THE CITY CAN WAIT: the sound, written down once. Running it writes data/sound2.json for pipeline/sound2.py.

Three layers, all lined up with data/cuesheet.json:
  * the scene's own sound, recorded with the pictures (the pour into the mug, the kettle, the city below the
    window), slowed with the picture to 0.8x where the picture is slowed (pitch kept), cleaned of the kitchen's
    mains hum (notches at 50/100/150 Hz) and rumble;
  * sound design: the clock (single ticks cut from a real recording), sub booms on the two hard stops,
    whooshes on the swing and the whip, a riser into the stop, a reverse swell that sucks the city out,
    the window latch, the glass server, the bell;
  * the score (pipeline/compose.py), placed at 0.0.
Sound-effect picks name their file under SFX (the licensed library assembled for this film; see
data/licences.json) and the useful part of it.
"""
from __future__ import annotations

import json
import os

RAW = os.environ.get("COFFEE_RAW", "/home/user/coffee/raw")
SFX = os.environ.get("COFFEE_SFX", "/home/user/coffee/sfx")
SCORE = os.environ.get("COFFEE_SCORE", "/home/user/coffee/score")
CUES = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cuesheet.json"), encoding="utf-8"))

HUM = [50, 100, 150]


def raw(i: str) -> str:
    return f"{RAW}/{i}.MOV"


def sfx(i: str) -> str:
    """The library file of Mixkit sound effect `i` (named <id>_<slug>.wav)."""
    return next(os.path.join(SFX, f) for f in sorted(os.listdir(SFX)) if f.startswith(f"{i}_") and f.endswith(".wav"))


# ---- the scene's own sound ---------------------------------------------------------------------------
beds = [
    # the window opens: the room, then the city floods in (3.3-4.0) and stays until time stops at 13.5
    {"id": "room_reveal", "file": raw("IMG_5417"), "src_in": 0.0, "start": 3.0, "end": 4.2, "tempo": 0.8,
     "hp": 80, "rms_db": -40.0, "fade_in": 0.02, "fade_out": 0.5},
    {"id": "city", "file": raw("IMG_5417"), "src_in": 6.0, "start": 3.3, "end": 13.5, "hp": 90, "rms_db": -31.0,
     "fade_in": 0.7, "fade_out": 0.008, "gain_keys": [[3.3, 0.0], [7.0, 0.0], [13.4, 3.0]]},
    # time speeds up: the murmur gets denser (the same street, the square and a crowd recording, faster, layered)
    {"id": "city_fast", "file": raw("IMG_5417"), "src_in": 12.0, "start": 6.6, "end": 13.5, "tempo": 1.6, "hp": 120,
     "rms_db": -33.0, "fade_in": 0.6, "fade_out": 0.008, "gain_keys": [[6.6, -2.0], [13.4, 3.0]]},
    {"id": "crowd_fast", "file": sfx("361"), "src_in": 4.0, "start": 7.0, "end": 13.5, "tempo": 1.7, "hp": 150, "lp": 9000,
     "rms_db": -36.0, "fade_in": 0.8, "fade_out": 0.008, "gain_keys": [[7.0, -4.0], [13.4, 3.0]]},
    {"id": "square_fast", "file": raw("IMG_5416"), "src_in": 6.0, "start": 10.9, "end": 13.5, "tempo": 2.0, "hp": 140,
     "rms_db": -31.0, "fade_in": 0.25, "fade_out": 0.008, "gain_keys": [[10.9, -1.0], [13.4, 3.0]]},
    # the old town's own sound under the swing: hooves of a carriage on the cobbles, far below
    {"id": "carriage", "file": sfx("353"), "src_in": 0.0, "start": 4.0, "end": 7.6, "hp": 120, "lp": 7000,
     "rms_db": -40.0, "fade_in": 0.6, "fade_out": 0.6},
    # the black after the first cut: only the room
    {"id": "room_black", "file": sfx("3199"), "src_in": 1.0, "start": 2.0, "end": 3.2, "rms_db": -52.0, "fade_in": 0.15, "fade_out": 0.3},
    # inside: the kettle's water on the coffee (source 5.1-9.9 s at 0.8x: after the knock at 4.1 s)
    {"id": "kettle", "file": raw("IMG_5421"), "src_in": 5.1, "start": 15.0, "end": 21.0, "tempo": 0.8,
     "hp": 150, "notch": HUM, "rms_db": -34.0, "fade_in": 0.6, "fade_out": 0.03},
    # the pour into the mug, with the picture (pourcup prep 2.0 s = source 3.2 s; from 29 the picture slows to 0.82)
    {"id": "pour", "file": raw("IMG_5422"), "src_in": 3.2, "start": 21.0, "end": 31.55, "tempo": 0.8,
     "hp": 120, "notch": HUM, "rms_db": -22.0, "fade_in": 0.015, "fade_out": 0.9,
     "gain_keys": [[21.0, 0.0], [26.0, 0.0], [27.2, -2.5], [29.0, -2.5], [30.0, 0.0]]},
    # the view through the window: the room, and the city faint through the glass
    {"id": "room_end", "file": raw("IMG_5420"), "src_in": 5.48, "start": 31.0, "end": 36.5, "tempo": 0.8,
     "hp": 100, "notch": HUM, "rms_db": -42.0, "fade_in": 1.0, "fade_out": 0.01},
    {"id": "city_glass", "file": raw("IMG_5417"), "src_in": 20.0, "start": 31.3, "end": 36.5, "hp": 150, "lp": 1800,
     "rms_db": -42.0, "fade_in": 1.2, "fade_out": 0.01},
]


# ---- sound design ------------------------------------------------------------------------------------
cues: list[dict] = []


def cue(i: str, at: float, src_in: float, dur: float, sync: float | None = None, **kw) -> None:
    """Place library sound `i` (its part from src_in, dur long) so that its moment `sync` (seconds in the file)
    lands on film time `at` (without sync, the part starts at `at`)."""
    c = {"file": sfx(i) if not i.startswith("/") else i, "src_in": src_in, "dur": dur, "at": at - ((sync - src_in) if sync is not None else 0.0)}
    c.update(kw)
    cues.append(c)


def design() -> None:
    # 0.0-2.0 the cold open: the pour, close and slowed (lower, like a high-speed camera's sound)
    cue(raw("IMG_5422"), 0.0, 3.60, 1.45, pitch=-5, hp=110, notch=HUM, rms_db=-23.0, fade_in=0.3, fade_out=0.004)
    cue("1324", 0.0, 0.50, 1.55, pitch=-4, hp=90, rms_db=-27.0, fade_in=0.25, fade_out=0.004)
    # 2.000 the smash cut: a deep hit with a chest punch
    cue("553", 2.0, 0.29, 2.6, sync=0.30, rms_db=-19.0, fade_in=0.002, fade_out=0.8)
    cue("2299", 2.0, 0.04, 0.9, sync=0.05, rms_db=-20.0, fade_in=0.002, fade_out=0.3)
    # 3.0 the latch, then the sash creaks open as the air and the city rush in
    cue("2856", 3.0, 0.03, 0.59, sync=0.238, rms_db=-30.0, hp=200)
    cue("195", 3.15, 0.38, 1.67, rms_db=-36.0, hp=150, fade_out=0.3)
    cue("1163", 3.3, 1.35, 1.4, rms_db=-38.0, hp=120, fade_in=0.2, fade_out=0.5)
    # 5.3-7.0 the speed-ramped turn: a vacuum whoosh peaking on the fastest part of the swing
    cue("1465", 6.45, 0.08, 2.09, sync=1.495, rms_db=-27.0, fade_out=0.4)
    # 9.0-13.5 a riser whose own hard stop lands on 13.5
    cue("1144", 9.0, 2.0, 4.5, rms_db=-31.0, fade_in=0.4, fade_out=0.004)
    # 11.0 the whip
    cue("1492", 11.0, 0.0, 1.3, sync=1.075, rms_db=-26.0, fade_out=0.15)
    # 13.5 TIME STOPS: everything sucked back into one hard stop, then a deep hit
    cue("1490", 13.5, 0.06, 0.70, sync=0.76, rms_db=-23.0, fade_in=0.05, fade_out=0.004)
    cue("553", 13.5, 0.29, 2.6, sync=0.30, rms_db=-17.0, fade_in=0.002, fade_out=1.0)
    cue("2299", 13.5, 0.04, 0.9, sync=0.05, rms_db=-19.0, fade_in=0.002, fade_out=0.3)
    # 15-21 inside: a thin kettle stream on the coffee, the bed breathing (soft bubbles and fizz)
    cue("1318", 15.0, 4.0, 6.0, rms_db=-37.0, hp=200, notch=[590], fade_in=0.7, fade_out=0.05)
    cue("1817", 16.2, 38.0, 4.8, rms_db=-45.0, hp=250, fade_in=1.2, fade_out=0.8)
    cue("2833", 17.0, 2.5, 3.9, rms_db=-46.0, hp=1500, fade_in=0.8, fade_out=0.8)
    # 21-29 the pour: a ceramic layer under the real pour, the cup filling up, a deep swell into the climax
    cue("1310", 21.0, 0.10, 4.25, rms_db=-36.0, hp=150, fade_in=0.01, fade_out=0.8)
    cue("2826", 24.3, 0.30, 4.4, rms_db=-37.0, hp=200, fade_in=0.8, fade_out=0.5)
    cue("2664", 27.0, 5.725, 5.0, sync=9.725, rms_db=-31.0, fade_in=2.5, fade_out=1.2)
    # 33.0 a church bell somewhere across the roofs
    cue("617", 33.0, 0.07, 6.2, sync=0.098, rms_db=-40.0, lp=3500, hp=180, reverb={"rt60": 3.8, "mix": 0.55, "predelay": 0.04}, fade_out=1.5)
    # the clock: a wall clock outside that doubles and doubles again; a pendulum clock inside and at the end
    T = CUES["ticks"]
    city = [t for t in T if t <= 13.3]
    fast = [t for t in T if 11.0 <= t <= 13.3]
    slow = [t for t in T if t >= 15.0]
    ticks.extend([
        {"file": sfx("1063"), "tick_in": 0.103, "tock_in": 0.396, "dur": 0.225, "pre": 0.005, "times": city, "gain_db": -9.0,
         "gain_keys": [[2.0, 0.0], [3.0, -5.0], [6.9, -4.0], [10.5, -2.0], [13.25, 0.0]]},
        {"file": sfx("1059"), "tick_in": 0.105, "tock_in": 0.595, "dur": 0.123, "pre": 0.003, "times": fast, "gain_db": -17.0, "hp": 500},
        {"file": sfx("1072"), "tick_in": 1.865, "tock_in": 0.841, "dur": 0.30, "pre": 0.005, "times": slow, "gain_db": -7.0, "hp": 300,
         "gain_keys": [[15.0, -2.0], [19.0, -4.0], [34.0, -5.0], [36.0, -3.0], [36.5, 2.0]]},
    ])


ticks: list[dict] = []


def build() -> dict:
    design()
    return {"duration": CUES["duration"], "beds": beds, "cues": cues, "ticks": ticks,
            "score": {"file": os.path.join(SCORE, "music.wav"), "gain_db": 0.0} if os.path.exists(os.path.join(SCORE, "music.wav")) else None,
            "silence": [[36.75, 37.5]]}


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    sp = build()
    json.dump(sp, open(os.path.join(here, "sound2.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote sound2.json:", len(sp["beds"]), "beds,", len(sp["cues"]), "cues,", "score" if sp["score"] else "no score")
