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


def clip(i: str) -> str:
    return f"{PREP}/{i}.mp4"


look = {"black": 0.0, "sat": 0.92, "shoulder": 0.86, "contrast": 1.1, "split": 0.8,
        "warm_hi": [1.0, 0.97, 0.92], "cool_lo": [0.94, 0.985, 1.03], "reds": 1.06, "greens": 0.7, "blues": 0.88}
CITY = {"ev": 0.0, "temp": 0.2, "contrast": 1.12}
INSIDE = {"cool_lo": [0.99, 0.99, 0.985]}
BREW = {"ev": 0.55, "temp": 1.9, "tint": 3.0, "contrast": 1.12, "greens": 0.1, "led": 1.0, "reds": 1.12, **INSIDE}
CUP = {"ev": 0.95, "temp": 2.6, "tint": 4.2, "contrast": 1.1, "reds": 1.12, **INSIDE}

shots = [
    {"id": "cold", "src": clip("pourcup"), "start": 0.0, "end": 2.0, "time": [[0.0, 2.55], [2.0, 4.55]], "interp": "linear",
     "move": {"keys": [[0.0, 1.30, 0.40, 0.47], [2.0, 1.36, 0.40, 0.47]]}, "grade": CUP, "denoise": "hqdn3d=1.2:1.2:3:3",
     "light": {"ev": 0.5, "keys": [[0.0, 0.42, 0.62, 0.35, 0.2], [2.0, 0.42, 0.62, 0.35, 0.2]]},
     "ev_keys": [[0.0, -4.0], [0.4, 0.0]]},
    {"id": "black1", "black": True, "start": 2.0, "end": 3.0},
    {"id": "reveal", "src": clip("reveal"), "start": 3.0, "end": 7.0,
     "time": [[3.0, 0.0], [4.8, 1.8], [5.3, 2.7], [6.4, 8.6], [7.0, 11.2]], "shutter": 1.0,
     "move": {"keys": [[3.0, 1.03, 0.5, 0.5], [7.0, 1.0, 0.5, 0.5]]}, "grade": CITY, "ev_keys": [[3.0, -3.0], [3.25, 0.0]]},
    {"id": "street", "src": clip("street_long"), "start": 7.0, "end": 11.0,
     # the steady telephoto part only (the phone zooms in before it and swings away after it); a long exposure:
     # each frame gathers ~0.4 s of real time, so the people become streaks
     "time": [[7.0, 4.0], [11.0, 24.3]], "interp": "linear", "shutter": 2.4,
     "move": {"keys": [[7.0, 1.0, 0.5, 0.5], [11.0, 1.06, 0.5, 0.5]]}, "grade": CITY, "grad": {"y0": 0.0, "y1": 0.36, "ev": -1.5}},
    {"id": "square", "src": clip("square_long"), "start": 11.0, "end": 15.0, "trans": {"type": "whip", "dur": 0.32, "dir": "left"},
     "time": [[11.0, 0.3], [13.5, 8.3], [15.0, 8.3]], "interp": "linear", "shutter": 2.0,
     "move": {"keys": [[11.0, 1.02, 0.5, 0.5], [13.5, 1.05, 0.5, 0.5], [15.0, 1.12, 0.5, 0.48]]}, "grade": CITY,
     "sat_keys": [[13.5, 1.0], [14.2, 0.12]], "defocus": [[14.2, 0.0], [15.0, 46.0]], "ev_keys": [[14.35, 0.0], [15.0, -7.0]]},
    {"id": "bloom", "src": clip("bloom"), "start": 15.0, "end": 21.0, "in": 1.0, "grade": BREW, "denoise": "hqdn3d=1.5:1.5:4:4",
     "key_green": {"y0": 0.42, "strength": 1.0}, "move": {"keys": [[15.0, 1.0, 0.5, 0.5], [21.0, 1.07, 0.5, 0.5]]},
     "defocus": [[15.0, 44.0], [15.8, 0.0]], "ev_keys": [[15.0, -5.0], [15.4, 0.0]]},
    {"id": "pour", "src": clip("pourcup"), "start": 21.0, "end": 32.0, "in": 2.0, "grade": CUP, "denoise": "hqdn3d=1.2:1.2:3:3",
     "move": {"keys": [[21.0, 1.12, 0.52, 0.52], [29.0, 1.12, 0.52, 0.52], [32.0, 1.15, 0.54, 0.49]]},
     "light": {"ev": 0.6, "tint": [1.0, 0.97, 0.9], "keys": [[0.0, 0.34, 0.63, 0.32, 0.18], [11.0, 0.34, 0.63, 0.32, 0.18]]},
     "streak": {"threshold": 0.9, "gain": 0.08, "length": 0.22}},
    {"id": "roofs2", "src": clip("roofs2"), "start": 31.5, "end": 36.5, "in": 0.35, "trans": {"type": "dissolve", "dur": 1.0},
     "grade": {"ev": 0.1, "temp": 1.3, "tint": -0.5, "contrast": 1.1}, "move": {"keys": [[31.0, 1.08, 0.5, 0.45], [36.5, 1.13, 0.5, 0.45]]}},
    {"id": "black2", "black": True, "start": 36.5, "end": 37.5},
]

WARM_WHITE = [0.97, 0.95, 0.91]
CHARCOAL = [0.13, 0.11, 0.1]
titles = [
    {"id": "warszawa", "lines": [{"text": "WARSZAWA", "font": "montserrat-latin-300-normal.woff", "size": 150, "track": [0.5, 0.78]},
                                 {"text": "STARE MIASTO", "font": "montserrat-latin-400-normal.woff", "size": 54, "track": [0.55, 0.7], "gap": 30}],
     "x": 0.5, "y": 0.15, "in": 7.6, "out": 10.75, "fade_in": 0.9, "fade_out": 0.45, "rise": 0, "focus": 9.0, "focus_out": 6.0,
     "glow": 0.18, "shadow": 0.55, "color": WARM_WHITE},
    {"id": "wait", "lines": [{"text": "THE CITY", "font": "montserrat-latin-300-normal.woff", "size": 80, "track": [0.34, 0.44]},
                             {"text": "CAN WAIT.", "font": "montserrat-latin-300-normal.woff", "size": 80, "track": [0.34, 0.44], "gap": 24}],
     "x": 0.79, "y": 0.27, "in": 32.5, "out": 36.5, "fade_in": 1.3, "fade_out": 0.0, "focus": 8.0, "color": CHARCOAL},
]

overlays = [
    # the window opens and the light floods in: a real light leak, warm, screen-blended
    {"src": f"{SRC}/3987.mp4", "start": 3.05, "end": 4.6, "in": 0.6, "speed": 1.6, "gain": 0.6, "black": 0.1, "fade_in": 0.15, "fade_out": 0.9,
     "mono": True, "tint": [1.0, 0.8, 0.58], "scale": 1.6, "cx": 0.35, "cy": 0.45, "feather": 0.25},
]

finish = {"bloom": {"threshold": 0.78, "gain": 0.18, "radius": 0.03, "tint": [1.0, 0.86, 0.7]},
          "clarity": {"amount": 0.35, "sigma": 0.012}, "sharpen": {"amount": 0.45, "sigma": 1.0},
          "vignette": 0.16, "grain": {"amount": 0.011, "size": 1.0}, "fades": []}


def build() -> dict:
    here = os.path.dirname(os.path.abspath(__file__))
    return {"fps": 24, "w": 2160, "h": 3840, "duration": 37.5, "look": look, "shots": shots, "titles": titles,
            "overlays": overlays, "finish": finish, "fonts": os.path.join(os.path.dirname(here), "fonts")}


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    json.dump(build(), open(os.path.join(here, "plan2.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote plan2.json:", len(shots), "shots,", len(titles), "titles,", len(overlays), "overlays")
