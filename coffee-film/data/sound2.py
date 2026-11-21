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


# ---- the scene's own sound ---------------------------------------------------------------------------
beds = [
    # cold open: the coffee falling into the mug, close (pourcup prep 2.55 s = source 3.64 s, at 0.8x)
    {"id": "cold_pour", "file": raw("IMG_5422"), "src_in": 3.64, "start": 0.0, "end": 2.0, "tempo": 0.8,
     "hp": 120, "notch": HUM, "rms_db": -21.0, "fade_in": 0.35, "fade_out": 0.006},
    # the window opens: the room, then the city floods in (3.3-4.0) and stays until time stops at 13.5
    {"id": "room_reveal", "file": raw("IMG_5417"), "src_in": 0.0, "start": 3.0, "end": 4.2, "tempo": 0.8,
     "hp": 80, "rms_db": -40.0, "fade_in": 0.02, "fade_out": 0.5},
    {"id": "city", "file": raw("IMG_5417"), "src_in": 6.0, "start": 3.3, "end": 13.5, "hp": 90, "rms_db": -31.0,
     "fade_in": 0.7, "fade_out": 0.008, "gain_keys": [[3.3, 0.0], [7.0, 0.0], [13.4, 3.0]]},
    # time speeds up: the city's murmur gets denser (the same street and the square, faster, layered)
    {"id": "city_fast", "file": raw("IMG_5417"), "src_in": 12.0, "start": 6.6, "end": 13.5, "tempo": 1.6, "hp": 120,
     "rms_db": -33.0, "fade_in": 0.6, "fade_out": 0.008, "gain_keys": [[6.6, -2.0], [13.4, 3.0]]},
    {"id": "square_fast", "file": raw("IMG_5416"), "src_in": 6.0, "start": 10.9, "end": 13.5, "tempo": 2.0, "hp": 140,
     "rms_db": -31.0, "fade_in": 0.25, "fade_out": 0.008, "gain_keys": [[10.9, -1.0], [13.4, 3.0]]},
    # inside: the kettle's water on the coffee (source 5.1-9.9 s at 0.8x: after the knock at 4.1 s)
    {"id": "kettle", "file": raw("IMG_5421"), "src_in": 5.1, "start": 15.0, "end": 21.0, "tempo": 0.8,
     "hp": 150, "notch": HUM, "rms_db": -33.0, "fade_in": 0.6, "fade_out": 0.03},
    # the pour into the mug, with the picture (pourcup prep 2.0 s = source 3.2 s, at 0.8x)
    {"id": "pour", "file": raw("IMG_5422"), "src_in": 3.2, "start": 21.0, "end": 31.55, "tempo": 0.8,
     "hp": 120, "notch": HUM, "rms_db": -22.0, "fade_in": 0.02, "fade_out": 0.9,
     "gain_keys": [[21.0, 0.0], [26.0, 0.0], [27.2, -2.5], [29.0, -2.5], [30.0, 0.0]]},
    # the view through the window: the room, and the city faint through the glass
    {"id": "room_end", "file": raw("IMG_5420"), "src_in": 5.48, "start": 31.0, "end": 36.5, "tempo": 0.8,
     "hp": 100, "notch": HUM, "rms_db": -42.0, "fade_in": 1.0, "fade_out": 0.01},
    {"id": "city_glass", "file": raw("IMG_5417"), "src_in": 20.0, "start": 31.3, "end": 36.5, "hp": 150, "lp": 1800,
     "rms_db": -42.0, "fade_in": 1.2, "fade_out": 0.01},
]

# ---- sound design ------------------------------------------------------------------------------------
# PICKS: role -> {file, in, dur} from the sound-effects library (filled from the library's catalogue)
PICKS: dict[str, dict] = {}
cues: list[dict] = []
ticks: dict = {}


def cue(role: str, at: float, **kw) -> None:
    if role not in PICKS:
        return
    p = PICKS[role]
    c = {"role": role, "file": os.path.join(SFX, p["file"]), "src_in": p.get("in", 0.0), "dur": p.get("dur"), "at": at}
    c.update(p.get("defaults", {}))
    c.update(kw)
    cues.append(c)


def design() -> None:
    cue("boom", 2.0, rms_db=-20.0, lp=900, fade_out=0.6)
    cue("latch", 3.02, rms_db=-30.0)
    cue("whoosh_med", 6.45, align="end", rms_db=-28.0)
    cue("riser", 13.5, align="end", rms_db=-30.0, fade_out=0.004)
    cue("whoosh_fast", 11.15, align="end", rms_db=-24.0)
    cue("reverse", 13.5, align="end", rms_db=-24.0, fade_out=0.004)
    cue("boom", 13.5, rms_db=-18.0, lp=700, fade_out=0.9)
    cue("kettle_pour", 15.0, rms_db=-36.0, fade_in=0.6)
    cue("clink", 20.95, rms_db=-30.0)
    cue("cup_pour", 21.0, rms_db=-34.0, fade_out=0.8)
    cue("swell", 27.0, align="end", rms_db=-32.0)
    cue("bell", 33.0, rms_db=-38.0, lp=3500, fade_out=1.5)
    if "tick" in PICKS:
        t = PICKS["tick"]
        ticks.update({"file": os.path.join(SFX, t["file"]), "tick_in": t["tick_in"], "tock_in": t.get("tock_in", t["tick_in"]),
                      "dur": t.get("dur", 0.22), "hp": t.get("hp", 300), "times": CUES["ticks"], "gain_db": t.get("gain_db", -6.0),
                      "gain_keys": [[2.0, 0.0], [3.0, -6.0], [6.9, -4.0], [13.3, 0.0], [15.0, -8.0], [19.0, -9.0],
                                    [34.0, -8.0], [36.0, -6.0], [36.5, -2.0]]})


def build() -> dict:
    design()
    return {"duration": CUES["duration"], "beds": beds, "cues": cues, "ticks": ticks or None,
            "score": {"file": os.path.join(SCORE, "music.wav"), "gain_db": 0.0} if os.path.exists(os.path.join(SCORE, "music.wav")) else None,
            "silence": [[36.75, 37.5]]}


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    sp = build()
    json.dump(sp, open(os.path.join(here, "sound2.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote sound2.json:", len(sp["beds"]), "beds,", len(sp["cues"]), "cues,", "score" if sp["score"] else "no score")
