#!/usr/bin/env python3
"""WARSZAWA (the window): the picture, written down once. Running it writes data/plan3.json for pipeline/render2.py.

The edit itself (which part of which clip, at what speed, where every cut and dissolve lands) is data/edit3.py ->
data/cuesheet3.json; this file adds how each shot looks: framing, grade, light, the rise from black, the title.
The grade follows the story: the kitchen is the dim, cool back of the flat (the window keeps its detail, the scale's
green LED is quietened); the coffee is the one warm thing in it; when the old front window opens, the picture opens
too: daylight, ochre and brick, the city at full colour.
Picture times: `in`/`speed` or `time` keys map film seconds to seconds of the prepared stretch (pipeline/prep.py:
one real 30 fps frame per 1/24 s); the slow-motion shots read a retimed clip with exactly one frame per film frame
(pipeline/retime.py).
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PREP = os.environ.get("COFFEE_PREP3", "/home/user/coffee/prep3")
PREP_OLD = os.environ.get("COFFEE_PREP", "/home/user/coffee/prep")
RETIME = os.environ.get("COFFEE_RETIME", "/home/user/coffee/retime")
CS = json.load(open(os.path.join(HERE, "cuesheet3.json"), encoding="utf-8"))
SOURCES = {s["id"]: s for s in json.load(open(os.path.join(HERE, "sources.json"), encoding="utf-8"))["stretches"]}
EV = {e["key"]: e["t"] for e in CS["events"]}
SH = {s["id"]: s for s in CS["shots"]}


def prep_path(pid: str) -> str:
    p = os.path.join(PREP, f"{pid}.mp4")
    return p if os.path.exists(p) else os.path.join(PREP_OLD, f"{pid}.mp4")


def timing(sid: str) -> dict:
    """Where the shot's frames come from: its retimed clip (one frame per film frame), or its prepared stretch."""
    s = SH[sid]
    if s.get("retime"):
        js = os.path.join(RETIME, f"{sid}.json")   # the film frame the retimed clip's first frame was made for
        first = json.load(open(js))["first_film_frame"] if os.path.exists(js) else s["first_frame"]
        return {"src": os.path.join(RETIME, f"{sid}.mp4"), "in": s["start"] - first / CS["fps"], "speed": 1.0}
    a, _, v = s["segs"][0]
    assert abs(v - 0.8) < 1e-9
    frm = SOURCES[s["prep"]]["from"]
    return {"src": prep_path(s["prep"]), "in": (a - frm) / 0.8 + (s["start"] - s["film_in"]), "speed": 1.0}


look = {"black": 0.0, "sat": 0.92, "shoulder": 0.86, "contrast": 1.1, "split": 0.8,
        "warm_hi": [1.0, 0.97, 0.92], "cool_lo": [0.94, 0.985, 1.03], "reds": 1.06, "greens": 0.7, "blues": 0.88}
# the back of the flat: dim, cool, the window holding its detail
KITCHEN = {"ev": -0.45, "temp": -0.8, "tint": 0.4, "contrast": 1.14, "sat": 0.82, "split": 0.9, "led": 0.6,
           "cool_lo": [0.9, 0.97, 1.06], "shoulder": 0.84}
# the coffee: the one warm thing in the cold room (a warm light window lifts the dripper / the mug)
BREW = {**KITCHEN, "ev": -0.3, "temp": -0.3, "sat": 0.88, "reds": 1.1}
CUP = {**KITCHEN, "ev": -0.25, "temp": -0.2, "sat": 0.9, "reds": 1.12}
# the front of the flat: daylight, natural ochre and brick, the overcast sky held
CITY = {"ev": 0.05, "temp": 0.3, "tint": 0.4, "contrast": 1.1, "split": 0.5, "sat": 0.96, "reds": 1.08,
        "cool_lo": [0.95, 0.985, 1.03]}
ACUTANCE = {"amount": 0.26, "sigma": 2.5}
DENOISE = "hqdn3d=1.4:1.4:4:4"
LED = {"y0": 0.40, "strength": 1.0, "lo": 0.015, "hi": 0.08, "dim": 0.2}
WARM = [1.0, 0.95, 0.86]


def inside(keys):
    """Keep every framing inside the picture: the warp's window (centre cx, cy, zoom z) may not cross the frame's edge
    (the renderer would mirror the image there)."""
    out = []
    for t, z, cx, cy in keys:
        lo, hi = 0.5 / z, 1 - 0.5 / z
        out.append([t, z, round(min(max(cx, lo), hi), 4), round(min(max(cy, lo), hi), 4)])
    return out


def shot(sid: str, **kw) -> dict:
    s = SH[sid]
    if "move" in kw and "keys" in kw["move"]:
        kw["move"] = {**kw["move"], "keys": inside(kw["move"]["keys"])}
    return {"id": sid, "start": s["start"], "end": s["end"], **timing(sid),
            **({"trans": s["trans"]} if s.get("trans", {}).get("type") == "dissolve" else {}), **kw}


shots = [
    {"id": "black_in", "black": True, "start": SH["black_in"]["start"], "end": SH["black_in"]["end"]},
    # his eyes adjusting to the dark room: the window appears first, then the counter
    shot("walk", grade=KITCHEN, denoise=DENOISE, acutance=ACUTANCE, key_green=LED,
         move={"keys": [[SH["walk"]["start"], 1.03, 0.5, 0.5], [SH["walk"]["end"], 1.05, 0.5, 0.48]]},
         ev_keys=[[1.0, -4.0], [2.5, 0.0]]),
    # the first water on the coffee; the slow motion is his attention narrowing to the thread of water
    shot("bloom", grade=BREW, denoise=DENOISE, acutance=ACUTANCE, key_green=LED,
         move={"keys": [[SH["bloom"]["start"], 1.08, 0.5, 0.56], [EV["stream"], 1.09, 0.5, 0.56], [EV["slow1_end"], 1.15, 0.5, 0.58],
                        [SH["brew"]["film_in"], 1.16, 0.5, 0.569], [SH["bloom"]["film_out"], 1.16, 0.5, 0.569]]},
         light={"tint": WARM, "keys": [[0.0, 0.5, 0.62, 0.34, 0.2, 0.35], [8.0, 0.5, 0.62, 0.34, 0.2, 0.35]]}),
    # same place, later: the last pours; he straightens and looks up (LOOK 2)
    shot("brew", grade=BREW, denoise=DENOISE, acutance=ACUTANCE, key_green=LED,
         # lined up on the dripper's static background for the dissolve (pipeline/align.py: bloom prep frame 150 vs k_brew 30,
         # s 1.025, t (-70, -105) px: bloom held at z 1.16, cy 0.569 through the dissolve), then eased toward the pull-back
         move={"keys": [[SH["brew"]["film_in"], 1.1317, 0.48, 0.5559], [SH["bloom"]["film_out"], 1.1317, 0.48, 0.5559], [EV["pullback"], 1.11, 0.49, 0.54],
                        [SH["brew"]["end"], 1.05, 0.5, 0.5]]},
         light={"tint": WARM, "keys": [[0.0, 0.5, 0.62, 0.34, 0.2, 0.35], [4.0, 0.5, 0.66, 0.3, 0.18, 0.3], [9.0, 0.5, 0.78, 0.24, 0.12, 0.15]]}),
    # vessel to vessel under the same window: the empty mug, the coffee into the printed city, LOOK 3
    shot("cup", grade=CUP, denoise=DENOISE, acutance=ACUTANCE, key_green=LED,
         move={"keys": [[SH["cup"]["start"], 1.12, 0.5, 0.6], [EV["server_in"], 1.15, 0.5, 0.6], [EV["slow2_end"], 1.1, 0.5, 0.58],
                        [EV["server_out"], 1.03, 0.5, 0.55], [SH["cup"]["end"], 1.02, 0.5, 0.52]]},
         light={"tint": WARM, "keys": [[0.0, 0.5, 0.64, 0.3, 0.17, 0.4], [12.0, 0.5, 0.66, 0.3, 0.17, 0.35], [15.6, 0.5, 0.72, 0.26, 0.14, 0.15]]}),
    # the latch: the old front window opens; the eye adapts from the dim kitchen as the sash clears
    # (a slow push into the street once it settles, ending where the next shot's framing can match it exactly)
    shot("open", grade=CITY, move={"keys": [[SH["open"]["start"], 1.04, 0.5, 0.5], [EV["street_settled"], 1.04, 0.5, 0.5],
                                            [SH["turn"]["film_in"], 1.07, 0.53, 0.5], [SH["open"]["film_out"], 1.07, 0.53, 0.5]]},
         ev_keys=[[SH["open"]["start"], -0.6], [EV["sash_clear"] - 0.6, -0.45], [EV["sash_clear"] + 0.4, 0.0]],
         grad={"y0": 0.0, "y1": 0.3, "ev": -0.6}),
    # same place, later; he turns away to the house opposite
    # not stabilised (its fast turn made the stabiliser zoom 1.45x); through the dissolve its framing follows the hand's
    # drift so the buildings hold still under the open shot (pipeline/align.py, w_open frames 339/351/363 vs w_turn 18/30/42)
    shot("turn", grade=CITY, move={"keys": [[SH["turn"]["film_in"], 1.085, 0.4601, 0.5217], [SH["turn"]["start"], 1.0827, 0.4832, 0.518],
                                            [SH["open"]["film_out"], 1.0815, 0.5035, 0.515], [SH["turn"]["end"], 1.0815, 0.5035, 0.515]]},
         grad={"y0": 0.0, "y1": 0.3, "ev": -0.6}),
    # his other window: the casement, the gaze left, the Castle Square behind the volute
    shot("square", grade=CITY,
         move={"keys": [[SH["square"]["start"], 1.12, 0.5, 0.5], [EV["casement_clear"], 1.04, 0.5, 0.5], [EV["climax"], 1.0, 0.5, 0.5],
                        [SH["square"]["end"], 1.04, 0.52, 0.5]]},
         grad={"y0": 0.0, "y1": 0.32, "ev": -0.7}),
    {"id": "black_out", "black": True, "start": SH["black_out"]["start"], "end": SH["black_out"]["end"]},
]

CHARCOAL = [0.12, 0.105, 0.095]
titles = [
    # the word printed on the mug, in the mug's charcoal ink, now above the real castle: the printed city becomes the
    # caption of the real one
    {"id": "warszawa", "lines": [{"text": "WARSZAWA", "font": "cormorant-garamond-latin-500-normal.woff", "size": 84, "track": [0.14, 0.17]}],
     # in the clear band of sky above the castle between the volute and the red house (measured over the title's frames:
     # sky from x 0.337 to 0.665 at y 0.08-0.12); the word spans x 0.37-0.63, y 0.097-0.112
     "x": 0.5, "y": 0.105, "in": EV["title_in"], "out": SH["square"]["end"], "fade_in": 1.2, "fade_out": 0.0, "rise": 0, "focus": 5.0,
     "focus_out": 0.0, "glow": 0.0, "shadow": 0.0, "color": CHARCOAL},
]

overlays = []

finish = {"bloom": {"threshold": 0.90, "gain": 0.10, "radius": 0.03, "tint": [1.0, 0.94, 0.86]},
          "clarity": {"amount": 0.24, "sigma": 0.012}, "sharpen": {"amount": 0.4, "sigma": 1.0}, "rolloff": {"knee": 0.9},
          "vignette": 0.16, "grain": {"amount": 0.011, "size": 1.0}, "fades": []}

# what the checks (pipeline/qc2.py) must accept: the black head and tail, the rise from black
qc = {"black_ok": [[0.0, 1.6], [SH["black_out"]["start"], CS["duration"]]], "still_ok": [],
      "cut_ok": [[0.95, 1.6]]}


def build() -> dict:
    return {"fps": CS["fps"], "w": 2160, "h": 3840, "duration": CS["duration"], "look": look, "shots": shots, "titles": titles,
            "overlays": overlays, "finish": finish, "qc": qc, "fonts": os.path.join(os.path.dirname(HERE), "fonts")}


if __name__ == "__main__":
    json.dump(build(), open(os.path.join(HERE, "plan3.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote plan3.json:", len(shots), "shots,", len(titles), "titles,", len(overlays), "overlays")
