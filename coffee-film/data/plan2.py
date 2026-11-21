#!/usr/bin/env python3
"""THE CITY CAN WAIT: the director's cut, written down once. Running it writes data/plan2.json.

The cut follows data/cuesheet.json (the contract shared with the score and the sound design):
   0.0  cold open: the coffee stream into the mug, a flash-forward       2.0  smash to black on the first tick
   3.0  the window swings open; 5.0 the camera's turn becomes a 4-5x motion-blurred swing onto the street
   7.0  the street, timelapse 6.4x: people become streaks; WARSZAWA in the sky
  11.0  whip pan to the square, timelapse 3.2x               13.5  TIME STOPS: freeze, colour drains, defocus to black
  15.0  inside: the kettle's stream on the coffee, racking into focus
  21.0  match cut on the stream: the coffee pours into the WARSZAWA mug; climax 27-29
  31.5  dissolve to the view through the window: THE CITY / CAN WAIT.        36.5  last tick, black
Picture times: `time` keys are [film s, prepared-stretch s]; a prepared stretch shows one real 30 fps frame per
1/24 s, so prep speed 1 = 0.8x real time. Faster than ~1.6 prep frames per output frame, frames are averaged
(motion blur).
"""
from __future__ import annotations

import json
import os

PREP = os.environ.get("COFFEE_PREP", "/home/user/coffee/prep")
SRC = "/home/user/film/v4/src"
SLOWMO_A2X = os.environ.get("COFFEE_SLOWMO", "/home/user/coffee/slowmo") + "/a_2x.mp4"


def clip(i: str) -> str:
    return f"{PREP}/{i}.mp4"


look = {"black": 0.0, "sat": 0.92, "shoulder": 0.86, "contrast": 1.1, "split": 0.8,
        "warm_hi": [1.0, 0.97, 0.92], "cool_lo": [0.94, 0.985, 1.03], "reds": 1.06, "greens": 0.7, "blues": 0.88}
# outside is cool and grey-blue (the city, the weather), inside is warm (the coffee, the kitchen light)
CITY = {"ev": 0.0, "temp": -1.0, "tint": 0.3, "contrast": 1.12, "split": 0.4, "sat": 0.88, "cool_lo": [0.92, 0.98, 1.06]}
INSIDE = {"cool_lo": [0.99, 0.99, 0.985]}
BREW = {"ev": 0.4, "temp": 2.2, "tint": 1.0, "contrast": 1.12, "greens": 0.1, "led": 0.4, "reds": 1.12, **INSIDE}
CUP = {"ev": 0.95, "temp": 2.9, "tint": 3.0, "contrast": 1.1, "reds": 1.06, **INSIDE}

# starts unzoomed: the swing lands on it with one step in the swing's own direction (scale matches within 3 %)
STREET_MOVE = {"keys": [[7.0, 1.0, 0.5, 0.5], [11.0, 1.12, 0.47, 0.5]]}

shots = [
    # a flash-forward in real slow motion: 0.4x real time (pipeline/slowmo.py, RIFE 2x on pourcup frames 62-101); only the
    # clean, laminar stretch is used (source frames 62-86: one distinct frame per output frame), before the glug
    {"id": "cold", "src": SLOWMO_A2X, "start": 0.0, "end": 2.0, "in": 0.0,
     "move": {"keys": [[0.0, 1.14, 0.45, 0.49], [2.0, 1.18, 0.44, 0.49]]}, "grade": CUP, "denoise": "hqdn3d=1.2:1.2:3:3",
     "light": {"keys": [[0.0, 0.338, 0.562, 0.27, 0.154, 0.3], [2.0, 0.338, 0.562, 0.27, 0.154, 0.3]]},
     "ev_keys": [[0.0, -4.0], [0.4, 0.0]]},
    {"id": "black1", "black": True, "start": 2.0, "end": 3.0},
    {"id": "reveal", "src": clip("reveal"), "start": 3.0, "end": 7.0,
     "time": [[3.0, 0.0], [4.4, 1.4], [4.8, 1.8], [5.3, 2.7], [6.4, 8.6], [7.0, 11.2]], "shutter": 1.0, "motion_fill": "flow",
     "move": {"keys": [[3.0, 1.03, 0.5, 0.5], [7.0, 1.0, 0.5, 0.5]]}, "grade": CITY,
     # out of black, then a daylight overshoot as the sash clears the frame
     "ev_keys": [[3.0, -3.0], [3.25, 0.0], [3.45, 0.0], [3.85, 0.5], [4.6, 0.0]]},
    {"id": "street", "src": clip("street_long"), "start": 7.0, "end": 11.0,
     # the steady telephoto part only (the phone zooms in before it and swings away after it); a long exposure:
     # each frame gathers ~0.4 s of real time, so the people become streaks
     "time": [[6.9, 5.07], [11.0, 23.3]], "interp": "linear", "trail": {"frames": 48, "mix": 0.72, "align": True}, "motion_fill": False,
     "move": STREET_MOVE, "grade": CITY, "grad": {"y0": 0.06, "y1": 0.34, "ev": -2.2}},
    {"id": "square", "src": clip("square_long"), "start": 11.0, "end": 15.0, "trans": {"type": "whip", "dur": 0.38, "dir": "left"},
     "time": [[11.0, 0.3], [12.0, 1.8], [12.75, 4.3], [13.5, 10.3], [15.0, 10.3]], "interp": "linear",
     "trail": {"frames": 36, "mix": 0.68, "align": True}, "motion_fill": False,
     "move": {"keys": [[11.0, 1.03, 0.5, 0.5], [13.5, 1.06, 0.5, 0.5], [15.0, 1.14, 0.5, 0.48]]}, "grade": CITY,
     "sat_keys": [[13.5, 1.0], [13.55, 0.35], [14.3, 0.1]], "defocus": [[14.2, 0.0], [15.0, 46.0]],
     "ev_keys": [[13.45, 0.0], [13.5, 0.35], [13.62, 0.0], [14.35, 0.0], [15.0, -16.0]]},
    # 21.0 lands on the kettle's long arc (prep 6.6); the push-in puts where it lands on screen exactly where the
    # coffee's arc lands after the match cut (output 0.50, 0.66)
    {"id": "bloom", "src": clip("bloom"), "start": 15.0, "end": 21.0, "in": 0.6, "grade": BREW, "denoise": "hqdn3d=1.5:1.5:4:4",
     "key_green": {"y0": 0.42, "strength": 1.0, "lo": 0.015, "hi": 0.08, "dim": 0.15},
     "move": {"keys": [[15.0, 1.0, 0.5, 0.5], [17.5, 1.03, 0.51, 0.52], [21.0, 1.15, 0.555, 0.56]]},
     "defocus": [[15.0, 44.0], [15.8, 0.0]], "ev_keys": [[15.0, -14.0], [15.45, 0.0]]},
    # real speed (every real frame, whole) through the pour; from 29, as the camera draws back, a little slower so
    # the take lasts through the dissolve; a slow push into the rising crema peaks on the 27.0 timpani, then releases
    {"id": "pour", "src": clip("pourcup"), "start": 21.0, "end": 32.0, "time": [[21.0, 2.0], [29.0, 10.0], [32.0, 12.45]], "interp": "linear",
     "grade": CUP, "denoise": "hqdn3d=1.2:1.2:3:3",
     "move": {"keys": [[21.0, 1.10, 0.465, 0.49], [27.0, 1.18, 0.50, 0.55], [28.6, 1.18, 0.50, 0.55], [31.0, 1.10, 0.52, 0.50], [32.0, 1.10, 0.53, 0.49]]},
     "light": {"tint": [1.0, 0.97, 0.9], "keys": [[0.0, 0.38, 0.64, 0.29, 0.16, 0.35], [8.0, 0.38, 0.64, 0.29, 0.16, 0.35],
                                                  [9.5, 0.48, 0.66, 0.22, 0.13, 0.0], [11.0, 0.52, 0.74, 0.17, 0.10, 0.0]]},
     "streak": {"threshold": 0.9, "gain": 0.08, "length": 0.22}},
    # lands on a correctly exposed window still tilting up; the phone's focus snap becomes a rack on the 34.0 tick
    {"id": "roofs2", "src": clip("roofs2"), "start": 31.5, "end": 36.5, "time": [[31.0, 1.5], [33.9, 3.85], [36.5, 5.85]],
     "trans": {"type": "dissolve", "dur": 1.0},
     "grade": {"ev": 0.1, "temp": 0.4, "tint": 0.8, "contrast": 1.1, "split": 0.4},
     "move": {"keys": [[31.0, 1.04, 0.5, 0.485], [36.5, 1.08, 0.5, 0.47]]}},
    {"id": "black2", "black": True, "start": 36.5, "end": 37.5},
]

WARM_WHITE = [0.97, 0.95, 0.91]
WARSZAWA_Y = 0.19   # in the open sky over the roofs, left of the window column
CHARCOAL = [0.13, 0.11, 0.1]
titles = [
    {"id": "warszawa", "lines": [{"text": "WARSZAWA", "font": "montserrat-latin-300-normal.woff", "size": 150, "track": [0.28, 0.34]},
                                 {"text": "STARE MIASTO", "font": "montserrat-latin-400-normal.woff", "size": 80, "track": [0.36, 0.42], "gap": 40}],
     "x": 0.385, "y": WARSZAWA_Y, "in": 7.5, "out": 10.75, "fade_in": 0.5, "fade_out": 0.35, "rise": 0, "focus": 6.0, "focus_out": 6.0,
     "glow": 0.0, "shadow": 0.35, "shadow_sigma": 18, "color": WARM_WHITE},
    # the last line, set in the clear pane, fully in on the 34.0 tick, gone before the cut to black
    {"id": "wait", "lines": [{"text": "the city", "font": "cormorant-garamond-latin-500-italic.woff", "size": 160, "track": [0.02, 0.04]},
                             {"text": "can wait.", "font": "cormorant-garamond-latin-500-italic.woff", "size": 160, "track": [0.02, 0.04], "gap": 6}],
     "x": 0.585, "y": 0.29, "in": 33.0, "out": 36.5, "fade_in": 1.0, "fade_out": 0.0, "focus": 8.0, "color": [0.10, 0.09, 0.085]},
]

overlays = [
    # the window opens and the light floods in: a real light leak, warm, screen-blended
    {"src": f"{SRC}/3987.mp4", "start": 3.05, "end": 4.6, "in": 0.6, "speed": 3.0, "gain": 0.75, "black": 0.25, "fade_in": 0.3, "fade_out": 0.6,
     "mono": False, "tint": [1.0, 0.8, 0.58], "scale": 1.6, "cx": 0.2, "cy": 0.45, "feather": 0.25},
]

finish = {"bloom": {"threshold": 0.90, "gain": 0.12, "radius": 0.03, "tint": [1.0, 0.93, 0.85]},
          "clarity": {"amount": 0.28, "sigma": 0.012}, "sharpen": {"amount": 0.45, "sigma": 1.0}, "rolloff": {"knee": 0.9},
          "vignette": 0.16, "grain": {"amount": 0.012, "size": 1.0}, "fades": []}


# what the checks (pipeline/qc2.py) must accept as intended: the black cards and the dips to black around them,
# the frozen moment, and the whip (one big step of motion by design)
qc = {"black_ok": [[0.0, 0.3], [2.0, 3.0], [14.6, 15.4], [36.5, 37.5]], "still_ok": [[13.45, 15.0]], "cut_ok": [[10.75, 11.25]]}


def build() -> dict:
    here = os.path.dirname(os.path.abspath(__file__))
    return {"fps": 24, "w": 2160, "h": 3840, "duration": 37.5, "look": look, "shots": shots, "titles": titles,
            "overlays": overlays, "finish": finish, "qc": qc, "fonts": os.path.join(os.path.dirname(here), "fonts")}


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    json.dump(build(), open(os.path.join(here, "plan2.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote plan2.json:", len(shots), "shots,", len(titles), "titles,", len(overlays), "overlays")
