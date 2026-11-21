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
VFX = os.environ.get("COFFEE_VFX", "/home/user/coffee/vfx") + "/deliver"
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
ACUTANCE = {"amount": 0.28, "sigma": 2.5}   # mid-scale detail for the soft interior plates (sigma in 4K px)
STREET_MOVE = {"keys": [[7.0, 1.0, 0.5, 0.5], [11.0, 1.12, 0.47, 0.5]]}
STREET_TRAIL = {"frames": 48, "mix": 0.72, "align": True}
SQUARE_TRAIL = {"frames": 14, "mix": 0.55, "align": True}   # shorter: the square plate is handheld (drift + rotation)
STREET_GRAD = {"y0": 0.06, "y1": 0.34, "ev": -1.4}   # the same overcast sky in every city shot: no jumps at the cuts
SQUARE_GRAD = {"y0": 0.0, "y1": 0.30, "ev": -1.6}

shots = [
    # a flash-forward in real slow motion: 0.4x real time (pipeline/slowmo.py, RIFE 2x on pourcup frames 62-101); only the
    # clean, laminar stretch is used (source frames 62-86: one distinct frame per output frame), before the glug
    {"id": "cold", "src": SLOWMO_A2X, "start": 0.0, "end": 2.0, "in": 0.0, "acutance": ACUTANCE,
     "move": {"keys": [[0.0, 1.14, 0.45, 0.49], [2.0, 1.18, 0.44, 0.49]]}, "grade": CUP, "denoise": "hqdn3d=1.2:1.2:3:3",
     "light": {"keys": [[0.0, 0.338, 0.562, 0.27, 0.154, 0.3], [2.0, 0.338, 0.562, 0.27, 0.154, 0.3]]},
     "ev_keys": [[0.0, -4.0], [0.4, 0.0]]},
    {"id": "black1", "black": True, "start": 2.0, "end": 3.0},
    {"id": "reveal", "src": clip("reveal"), "start": 3.0, "end": 7.0,
     # the swing eases into its landing on the street
     "time": [[3.0, 0.0], [4.3, 1.3], [4.4, 1.4], [4.8, 1.83], [5.3, 2.7], [6.3, 8.2], [6.8, 10.6], [7.0, 11.2]], "shutter": 1.0, "motion_fill": "flow",
     # a longer exposure through the fastest part of the swing: the facade's windows smear into motion instead of
     # strobing past (photosensitivity: no area may flash more than three times a second)
     "shutter_keys": [[5.0, 1.0], [5.4, 2.2], [6.6, 2.2], [7.0, 1.0]],
     "move": {"keys": [[3.0, 1.03, 0.5, 0.5], [7.0, 1.0, 0.5, 0.5]]}, "grade": CITY,
     "grad": {"y0": 0.0, "y1": 0.30, "ev_keys": [[6.3, 0.0], [7.0, -1.4]]},   # the sky settles to the street's before the cut
     # out of black, then a daylight overshoot as the sash clears the frame
     "ev_keys": [[3.0, -3.0], [3.25, 0.0], [3.45, 0.0], [3.85, 0.3], [4.6, 0.0]]},
    {"id": "street", "src": clip("street_long"), "start": 7.0, "end": 11.0,
     # the steady wide part of the take; a trail exposure: the camera's drift is taken out, so the city stays sharp
     # and the walkers leave streaks
     "time": [[6.9, 5.07], [11.0, 23.3]], "interp": "linear", "trail": STREET_TRAIL, "motion_fill": False,
     "move": STREET_MOVE, "grade": CITY, "grad": STREET_GRAD},
    # 11.0-13.5 the race: the square and the street cut against each other ever faster, on the ostinato's grid
    # (1 s, 0.5, 0.25, 0.25, 0.125, 0.125), each insert arriving already streaked, into the dead stop on 13.5
    {"id": "sqA", "src": clip("square_long"), "start": 11.0, "end": 12.0, "trans": {"type": "whip", "dur": 0.54, "dir": "left", "blur": 1.15},
     "time": [[10.958, 0.2], [11.0, 0.3], [12.0, 2.3]], "interp": "linear", "trail": SQUARE_TRAIL, "motion_fill": False,
     "move": {"keys": [[11.0, 1.03, 0.5, 0.5], [12.0, 1.05, 0.5, 0.5]]}, "grade": CITY, "grad": SQUARE_GRAD},
    {"id": "stB", "src": clip("street_long"), "start": 12.0, "end": 12.5, "time": [[11.958, 11.708], [12.0, 12.0], [12.5, 15.5]], "interp": "linear",
     "trail": STREET_TRAIL, "motion_fill": False, "move": {"keys": [[12.0, 1.08, 0.5, 0.5], [12.5, 1.10, 0.47, 0.5]]}, "grade": CITY, "grad": STREET_GRAD},
    {"id": "sqC", "src": clip("square_long"), "start": 12.5, "end": 12.75, "time": [[12.458, 2.3], [12.5, 2.6], [12.75, 4.4]], "interp": "linear",
     "trail": SQUARE_TRAIL, "motion_fill": False, "move": {"keys": [[12.5, 1.08, 0.5, 0.5], [12.75, 1.09, 0.5, 0.5]]}, "grade": CITY, "grad": SQUARE_GRAD},
    {"id": "stD", "src": clip("street_long"), "start": 12.75, "end": 13.0, "time": [[12.708, 15.583], [12.75, 16.0], [13.0, 18.5]], "interp": "linear",
     "trail": STREET_TRAIL, "motion_fill": False, "move": {"keys": [[12.75, 1.18, 0.47, 0.5], [13.0, 1.19, 0.47, 0.5]]}, "grade": CITY, "grad": STREET_GRAD},
    {"id": "sqE", "src": clip("square_long"), "start": 13.0, "end": 13.125, "time": [[12.958, 4.133], [13.0, 4.6], [13.125, 6.0]], "interp": "linear",
     "trail": SQUARE_TRAIL, "motion_fill": False, "move": {"keys": [[13.0, 1.12, 0.5, 0.5], [13.125, 1.12, 0.5, 0.5]]}, "grade": CITY, "grad": SQUARE_GRAD},
    {"id": "stF", "src": clip("street_long"), "start": 13.125, "end": 13.25, "time": [[13.083, 18.333], [13.125, 19.0], [13.25, 21.0]], "interp": "linear",
     "trail": STREET_TRAIL, "motion_fill": False, "move": {"keys": [[13.125, 1.22, 0.47, 0.5], [13.25, 1.22, 0.47, 0.5]]}, "grade": CITY, "grad": STREET_GRAD},
    # 13.5 TIME STOPS: the streaks snap into sharp, frozen people; the colour drains on the frame; the push-in goes to them
    {"id": "sqG", "src": clip("square_long"), "start": 13.25, "end": 15.0, "time": [[13.208, 5.62], [13.25, 6.4], [13.458, 10.3], [15.0, 10.3]], "interp": "linear",
     "trail": SQUARE_TRAIL, "motion_fill": False, "grade": CITY, "grad": SQUARE_GRAD,
     "move": {"keys": [[13.25, 1.10, 0.5, 0.52], [13.5, 1.14, 0.47, 0.55], [14.45, 1.20, 0.45, 0.57], [15.0, 1.22, 0.45, 0.58]]},
     # time stops on the hit (13.5 is the first frozen frame); the lens goes soft while the frozen square is still
     # bright enough for its highlights to bloom into discs, then it falls to black
     "sat_keys": [[13.5, 1.0], [13.55, 0.35], [14.3, 0.1]], "defocus": [[14.1, 0.0], [14.6, 30.0], [15.0, 46.0]],
     "ev_keys": [[13.45, 0.0], [13.5, 0.35], [13.62, 0.0], [14.5, 0.0], [14.8, -2.5], [15.0, -16.0]]},
    # 21.0 lands on the kettle's long arc (prep 6.6); the push-in puts where it lands on screen exactly where the
    # coffee's arc lands after the match cut (output 0.50, 0.66)
    {"id": "bloom", "src": clip("bloom"), "start": 15.0, "end": 21.0, "in": 0.6, "grade": BREW, "denoise": "hqdn3d=1.5:1.5:4:4", "acutance": ACUTANCE,
     "key_green": {"y0": 0.42, "strength": 1.0, "lo": 0.015, "hi": 0.08, "dim": 0.15},
     "move": {"keys": [[15.0, 1.0, 0.5, 0.5], [17.5, 1.03, 0.51, 0.52], [21.0, 1.15, 0.555, 0.56]]},
     "defocus": [[15.0, 44.0], [15.8, 0.0]], "ev_keys": [[15.0, -14.0], [15.45, 0.0]]},
    # real speed (every real frame, whole) through the pour; a slow push into the rising crema peaks on the 27.0
    # timpani; on the 29.0 resolution the full cup is held while it is still sharp (the phone refocuses after it)
    # and the frame draws back from it instead, into the dissolve
    {"id": "pour", "src": clip("pourcup"), "start": 21.0, "end": 32.0, "interp": "linear",
     "time": [[21.0, 2.0], [29.0, 10.0], [29.083, 10.083], [32.0, 10.083]],   # frame 242: the last sharp one (refocus from 243)
     "grade": CUP, "denoise": "hqdn3d=1.2:1.2:3:3", "acutance": ACUTANCE,
     # (the pull-back stays framed right of the departing server's edge, top left of the held frame)
     "move": {"keys": [[21.0, 1.10, 0.465, 0.49], [27.0, 1.18, 0.50, 0.55], [29.0, 1.18, 0.50, 0.55], [32.0, 1.12, 0.55, 0.49]]},   # one continuous pull-back
     "light": {"tint": [1.0, 0.97, 0.9], "keys": [[0.0, 0.38, 0.64, 0.29, 0.16, 0.35], [8.0, 0.38, 0.64, 0.29, 0.16, 0.35],
                                                  [11.0, 0.38, 0.64, 0.29, 0.16, 0.2]]},
     "streak": {"threshold": 0.9, "gain": 0.08, "length": 0.22},
     # real steam (two filmed smoke elements on black, composited over the held cup in the clip's own coordinates),
     # rising in film time from the resolution chord
     "plate_layers": [{"src": f"{VFX}/steam_hold_1964_4k.mp4", "clock": "film", "t0": 29.0, "frames": 75, "credit_ids": ["1964"],
                       "gain_keys": [[29.0, 0.0], [29.4, 1.3], [32.0, 1.3]], "tint": [1.0, 0.95, 0.88]},
                      {"src": f"{VFX}/steam_hold_50956_4k.mp4", "clock": "film", "t0": 29.0, "frames": 75, "credit_ids": ["50956"],
                       "gain_keys": [[29.0, 0.0], [29.4, 1.3], [32.0, 1.3]], "tint": [1.0, 0.95, 0.88]}]},
    # lands on a correctly exposed window still tilting up; the phone's focus snap becomes a rack on the 34.0 tick
    {"id": "roofs2", "src": clip("roofs2"), "start": 31.5, "end": 36.5, "time": [[31.0, 1.5], [33.9, 3.85], [36.5, 5.85]],
     "trans": {"type": "dissolve", "dur": 1.0},
     "grade": {"ev": 0.1, "temp": 0.4, "tint": 0.8, "contrast": 1.1, "split": 0.4},
     "move": {"keys": [[31.0, 1.04, 0.5, 0.485], [36.5, 1.08, 0.5, 0.47]]}},
    {"id": "black2", "black": True, "start": 36.5, "end": 37.5},
]

WARM_WHITE = [0.97, 0.95, 0.91]
WARSZAWA_Y = 0.175   # in the open sky between the dormers and the gutter, below the Reels top bar
CHARCOAL = [0.13, 0.11, 0.1]
titles = [
    # the same voice as the last line (Cormorant): one typographic family for the film
    {"id": "warszawa", "lines": [{"text": "WARSZAWA", "font": "cormorant-garamond-latin-500-normal.woff", "size": 125, "track": [0.14, 0.18]},
                                 {"text": "stare miasto", "font": "cormorant-garamond-latin-500-italic.woff", "size": 64, "track": [0.04, 0.06], "gap": 18}],
     "x": 0.46, "y": WARSZAWA_Y, "in": 7.5, "out": 10.75, "fade_in": 0.5, "fade_out": 0.35, "rise": 0, "focus": 6.0, "focus_out": 6.0,
     "glow": 0.0, "shadow": 0.35, "shadow_sigma": 18, "color": WARM_WHITE},
    # the last line, set in the clear pane, fully in on the 34.0 tick, gone before the cut to black
    {"id": "wait", "lines": [{"text": "the city", "font": "cormorant-garamond-latin-500-italic.woff", "size": 160, "track": [0.02, 0.04]},
                             {"text": "can wait.", "font": "cormorant-garamond-latin-500-italic.woff", "size": 160, "track": [0.02, 0.04], "gap": 6}],
     "x": 0.585, "y": 0.29, "in": 33.0, "out": 36.5, "fade_in": 1.0, "fade_out": 0.0, "focus": 8.0, "color": [0.10, 0.09, 0.085]},
]

overlays = [
    # real light (a filmed prism leak, regraded amber) blooming from the window side: as the sash opens, and through
    # the dissolve from the cup to the window
    {"src": f"{VFX}/leak_3987_amber_4k.mp4", "credit_ids": ["3987"], "start": 3.1, "end": 5.1, "in": 0.0, "speed": 1.0, "black": 0.0,
     "mono": False, "scale": 1.0, "cx": 0.5, "cy": 0.5, "feather": 0.02, "radial": {"cx": 0.85, "cy": 0.25, "r0": 0.35, "r1": 1.1},
     "gain_keys": [[3.1, 0.0], [3.45, 0.35], [3.9, 0.6], [4.5, 0.35], [5.1, 0.0]]},
    {"src": f"{VFX}/leak_3987_amber_4k.mp4", "credit_ids": ["3987"], "start": 30.6, "end": 32.6, "in": 1.5, "speed": 1.0, "black": 0.0,
     "mono": False, "scale": 1.0, "cx": 0.5, "cy": 0.5, "feather": 0.02, "radial": {"cx": 0.85, "cy": 0.25, "r0": 0.35, "r1": 1.1},
     "gain_keys": [[30.6, 0.0], [31.0, 0.5], [31.5, 0.85], [32.0, 0.5], [32.6, 0.0]]},
]

finish = {"bloom": {"threshold": 0.90, "gain": 0.12, "radius": 0.03, "tint": [1.0, 0.93, 0.85]},
          "clarity": {"amount": 0.28, "sigma": 0.012}, "sharpen": {"amount": 0.45, "sigma": 1.0}, "rolloff": {"knee": 0.9},
          "vignette": 0.16, "grain": {"amount": 0.012, "size": 1.0}, "fades": []}


# what the checks (pipeline/qc2.py) must accept as intended: the black cards and the dips to black around them,
# the frozen moment, and the whip (one big step of motion by design)
qc = {"black_ok": [[0.0, 0.3], [2.0, 3.0], [14.6, 15.4], [36.5, 37.5]], "still_ok": [[13.45, 15.0]],
      "cut_ok": [[0.0, 0.45], [3.0, 3.3], [10.7, 11.3], [15.0, 15.5]]}   # the whip, and the fades up from black


def build() -> dict:
    here = os.path.dirname(os.path.abspath(__file__))
    return {"fps": 24, "w": 2160, "h": 3840, "duration": 37.5, "look": look, "shots": shots, "titles": titles,
            "overlays": overlays, "finish": finish, "qc": qc, "fonts": os.path.join(os.path.dirname(here), "fonts")}


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    json.dump(build(), open(os.path.join(here, "plan2.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote plan2.json:", len(shots), "shots,", len(titles), "titles,", len(overlays), "overlays")
