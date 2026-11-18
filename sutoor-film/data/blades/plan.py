#!/usr/bin/env python3
"""The Blades edition's edit, written down once: every shot, cut, ramp, transition and word placement.

Run it to (re)write data/blades/plan.json, which pipeline/render_blades.py builds from:
    python data/blades/plan.py            (footage root: $BLADES_FOOTAGE, default /home/user/film)

Film time is the original recording's own time (the film runs on the untouched original soundtrack), so
every number below can be read against data/timing.json. Cuts fall on a spoken word's onset or on a
music accent (3.76 4.37 6.55 7.01 8.13 10.63 12.82 13.56 14.95 17.46 18.34 18.95 19.74 20.32 21.18
21.78 22.64 23.96 24.78 25.36 26.12 26.8 27.47 28.19 28.61).

The chain of images
  1  a hand smooths earth over; bare feet walk on over wet sand; a footprint stays behind and the sea comes for it
  2  metal is poured, embers rise among trunks as tall as spears; an hourglass runs out and the light with it
  3  a tethered horse, an eye, a horse behind bars; a horse runs; a night passes in half a second
  4  a man, a black profile against smoke, lifts his face; the sky shuts; he looks, and turns away
  5  a train out of the dark, a clock that goes out, a storm of sparks; one coal; a low sun behind branches
  6  the man again and the sparks reach him; splinters of rock in the surf, a blade of rock, the rock that stays

Lettering rules (1080-wide frame units):
  * the words belong to the shot they are spoken over: a hemistich is split into blocks, one per shot
  * one or two words per row, large (140-230): a row never exceeds 84 % of the width
  * the image-word of a line is gold and lands (large, then settling); everything else is cream and rises
  * the words sit in the picture's own dark space (a man's shoulders, a horse's flank, the black of a glass),
    never across the thing the line is about; nothing reaches below 84 % of the height, and nothing right of
    86 % of the width in the lower half (the platforms draw their buttons there, and an Arabic row starts at the right)
  * where a subject crosses a word it passes in front of it: bright things by their brightness, skin by its warmth
  * bright things (flame, sparks, falling sand) pass in front of the letters, dark branches too, and the
    letters are lit by the shot's own light
  * a line's rhyme word is brought on with the word before it when it would otherwise have under half a second
"""
from __future__ import annotations

import json
import math
import os

ROOT = os.environ.get("BLADES_FOOTAGE", "/home/user/film")
V4 = f"{ROOT}/v4/src"
MIXKIT = "Mixkit {} — Mixkit Stock Video Free License (item page data-license=videoFree, verified)"
CREAM, GOLD = "#F6EEDD", "#FFD79A"
MAN = {"window": {"cx": 0.75, "cy": 0.56, "fill": 1.08}, "grade": {"ev": -0.15, "sat": 0.35, "contrast": 1.08}}  # one man, one frame, three moments


def clip(i: int | str, folder: str = V4) -> str:
    return f"{folder}/{i}.mp4"


def first_frame_time(start: float, fps: int = 24) -> float:
    """The time of the first picture frame of a shot that starts at `start`."""
    return math.ceil(start * fps - 1e-6) / fps


def in_at_frame(frame: int, start: float, fps: int = 24) -> float:
    """The in-point that puts source frame `frame` (of a 24 fps clip) on the shot's first picture frame."""
    return round(frame / fps - (first_frame_time(start, fps) - start) + 0.004, 4)


def lock_keys(track_file: str, frame0: int, start: float, fill: float, px: float, py: float, z=(1.0, 1.03),
              W: int = 3840, H: int = 2160, fps: int = 24) -> list:
    """Window keys that hold one point of the ground (tracked by pipeline/ground_lock.py) at (px, py) of the frame:
    the camera of a tracking shot travels on, the frame stays behind with the footprint."""
    here = os.path.dirname(os.path.abspath(__file__))
    tr = {int(k): (x, y) for k, x, y in json.load(open(os.path.join(here, track_file), encoding="utf-8"))["track"]}
    t0, last = first_frame_time(start, fps), max(tr)
    keys = []
    for k in range(frame0, last + 1):
        zz = z[0] + (z[1] - z[0]) * (k - frame0) / max(last - frame0, 1)
        w, h = (H * 9 / 16) / (fill * zz), H / (fill * zz)
        x, y = tr[k]
        keys.append([round(t0 + (k - frame0) / fps, 5), round(zz, 4), round((x + (0.5 - px) * w) / W, 5), round((y + (0.5 - py) * h) / H, 5)])
    return keys


shots = [
    # ---------------------------------------------------------------- the name, behind a real fire
    {"id": "fire", "src": clip(3468), "lic": 3468, "start": 0.0, "in": 2.0, "window": {"cx": 0.2},
     # a flame stands among ash-covered logs, at its own speed: sharp wood, tall fire and a lit first frame. This stretch and
     # framing keep the flicker inside the photosensitivity limit (0.08 against 0.11; 0.09 at cx 0.22); from 1.7 s it does not
     "move": {"z": [1.0, 1.08]}, "grade": {"ev": -0.9, "sat": 0.62, "temp": 0.0, "contrast": 1.1, "halation": 0.3},  # ash grey, not violet
     "text": {"glow": 0.5, "pool": 0.5, "occlude": {"type": "luma", "lo": 0.7, "hi": 0.96, "gain": 0.75, "blur": 2.0}}},
    # ---------------------------------------------------------------- 1  we bury one another; the last walk on the first
    {"id": "earth", "src": clip(2851), "lic": 2851, "start": 1.78, "in": 16.85, "speed": 0.8008, "window": {"cx": 0.6, "cy": 0.615, "fill": 1.3},
     # bare earth at dusk; the first word lands on it; then a hand comes, presses the earth down over that word and holds it
     # there to the cut: the word that means "buries" is buried (a 29.97 fps clip played frame for frame, so 0.8 speed)
     "move": {"z": [1.0, 1.06]}, "grade": {"ev": -0.7, "sat": 0.3, "temp": 1.2, "tint": 3.5, "contrast": 1.2},
     "text": {"glow": 0.4, "pool": 0.6, "occlude": {"type": "luma", "lo": 0.34, "hi": 0.5, "gain": 0.97, "blur": 2.5}}},  # the pale hand is in front of the words (the lit clods are not)
    {"id": "walk", "src": clip("1013-22"), "lic": 1013, "start": 3.76, "in": in_at_frame(88, 3.76), "window": {"cx": 0.33, "cy": 0.63, "fill": 1.35},
     # 1013 from 0.4 s at its true cadence (true_cadence.py: every real frame, the dropped ones rebuilt), so 0.71 speed:
     # the foot comes down on «وَتَمشي»; white cloth, skin and sand kept apart by the grade
     "move": {"z": [1.0, 1.04]}, "shake": {"amp": 2, "seed": 5}, "grade": {"ev": 0.95, "sat": 0.78, "temp": -2.0, "tint": 1.6, "contrast": 1.18},
     "text": {"pool": 0.9, "glow": 0.3, "occlude": {"type": "warm", "lo": 0.10, "hi": 0.25, "gain": 0.95, "blur": 2.0}}},  # the foot steps in front of the word
    {"id": "foam", "src": clip("1013-21"), "lic": 1013, "start": 5.34, "in": in_at_frame(56, 5.34), "window": {"fill": 1.25},
     # 1013 from 9.3 s at its true cadence, and the frame held on the sand (ground_lock.py): the walker leaves, the footprint
     # stays, the edge of the sea comes for it. The foot lifts off the print as «الأَوالي» lands
     "move": {"keys": lock_keys("footprint_lock.json", 56, 5.34, 1.25, 0.40, 0.76)},
     "grade": {"ev": 0.55, "sat": 0.8, "temp": -2.0, "tint": 1.6, "contrast": 1.12},
     "text": {"pool": 0.8, "glow": 0.35, "occlude": [{"type": "warm", "lo": 0.10, "hi": 0.25, "gain": 0.95, "blur": 2.0},      # the lifting foot,
                                                      {"type": "luma", "lo": 0.5, "hi": 0.78, "gain": 0.85, "blur": 2.0}]}},   # and the foam, pass in front
    # ---------------------------------------------------------------- 2  we ready the swords; death needs no fight
    {"id": "pour", "src": clip(2861), "lic": 2861, "start": 6.34, "in": 0.72, "speed": 0.961, "decimate": 6, "window": {"cx": 0.6, "cy": 0.6, "fill": 1.22},
     # the file repeats every sixth frame (25 fps in a 30 fps file): dropped, then played frame for frame; the stream starts on the cut, the sparks burst on «المَشرَفِيَّةَ»
     "move": {"keys": [[6.34, 1.0, 0.6, 0.6], [6.96, 1.05, 0.6, 0.6], [7.08, 1.13, 0.6, 0.6], [7.4, 1.16, 0.6, 0.6]]},  # a push on the accent at 7.01
     "grade": {"ev": -0.5, "sat": 1.0, "contrast": 1.05, "halation": 0.4, "temp": 0.6, "tint": -4.0}, "trans": {"type": "flash", "dur": 0.25, "gain": 0.5},  # orange, not lemon
     "text": {"pool": 0.8, "glow": 0.4, "occlude": {"type": "luma", "lo": 0.7, "hi": 0.95, "gain": 0.8, "blur": 1.5}}},
    {"id": "forge", "src": clip(51634), "lic": 51634, "start": 7.4, "in": 2.25, "window": {"cx": 0.46},  # embers rising among trunks as tall as spears
     "move": {"z": [1.0, 1.1]}, "grade": {"ev": 0.7, "sat": 1.0, "halation": 0.4}, "trans": {"type": "zoom", "dur": 0.26, "factor": 2.2},
     "text": {"pool": 0.6, "glow": 0.4, "occlude": {"type": "luma", "lo": 0.5, "hi": 0.85, "gain": 0.8, "blur": 1.5}}},
    {"id": "glass", "src": clip(28894), "lic": 28894, "start": 8.13, "time": [[8.13, 4.2], [9.5, 5.9], [9.68, 10.9], [10.63, 12.75]],
     "window": {"cx": 0.44}, "move": {"z": [1.0, 1.07]}, "grade": {"ev": 0.2, "sat": 0.6, "temp": -0.2},
     "text": {"lit": {"global": True, "lo": 0.008, "hi": 0.035, "floor": 0.62}, "glow": 0.32, "pool": 0.0,
              "occlude": {"type": "luma", "lo": 0.5, "hi": 0.8, "gain": 0.7}}},
    # ---------------------------------------------------------------- 3  the swift horses, tethered close; the nights trot on
    {"id": "tether", "src": clip(100663), "lic": 100663, "start": 10.63, "in": 1.3, "move": {"z": [1.0, 1.08]},
     "shake": {"amp": 2, "seed": 9}, "grade": {"ev": -0.3, "sat": 0.5, "contrast": 1.06}, "text": {"pool": 0.9}},
    {"id": "eye", "src": clip(100645), "lic": 100645, "start": 11.42, "in": 0.8, "move": {"z": [1.05, 1.13]},
     "shake": {"amp": 2, "seed": 10}, "grade": {"ev": -0.85, "sat": 0.14, "temp": -0.25, "contrast": 1.08}, "text": {"pool": 1.3}},  # in the cold of its neighbours
    {"id": "grey", "src": clip(100646), "lic": 100646, "start": 12.08, "in": 4.3, "window": {"cx": 0.48}, "move": {"z": [1.0, 1.07]},
     "shake": {"amp": 2, "seed": 11}, "grade": {"ev": -0.4, "sat": 0.4, "contrast": 1.05}, "text": {"pool": 1.0}},
    {"id": "canter", "src": clip(1154), "lic": 1154, "start": 12.82, "in": 6.05, "speed": 2.0, "window": {"cx": 0.66},
     "move": {"z": [1.0, 1.05]}, "shake": {"amp": 3, "seed": 12}, "grade": {"ev": -0.55, "sat": 0.7, "temp": -0.1},
     "trans": {"type": "whip", "dur": 0.25, "dir": "left"},  # the one whip of the film: from the still head to the running horse
     "text": {"pool": 0.5, "glow": 0.4}},
    {"id": "night", "src": clip(4357), "lic": 4357, "start": 14.38, "time": [[14.38, 1.2], [14.95, 3.9], [15.2, 4.8]], "shutter": 1.0,  # a whole night in half a second
     "window": {"cx": 0.47}, "move": {"z": [1.0, 1.1]}, "grade": {"ev": 0.9, "sat": 0.42, "temp": 0.2}, "trans": {"type": "dissolve", "dur": 0.3},
     "text": {"glow": 0.5, "pool": 0.3}},
    # ---------------------------------------------------------------- 4  it grew light; I no longer care
    {"id": "man", "src": clip("948-11"), "lic": 948, "start": 14.95, "in": 0.35, **MAN,  # 948 from 10.2 s, evened; real time: a still profile, then he lifts his face
     "move": {"z": [1.0, 1.09]}, "trans": {"type": "dissolve", "dur": 0.4},
     "text": {"glow": 0.45, "wrap": 0.35, "pool": 0.0}},
    {"id": "sky", "src": clip(118), "lic": 118, "start": 16.7, "time": [[16.7, 6.0], [17.42, 15.0]], "shutter": 1.0,  # what he looks up at: the sky shuts
     "move": {"z": [1.0, 1.12]}, "grade": {"ev": -0.75, "sat": 0.45, "temp": -0.15, "contrast": 1.15}, "text": {"pool": 0.5, "glow": 0.4}},
    {"id": "man_b", "src": clip("948-12"), "lic": 948, "start": 17.42, "in": 0.35, **MAN,  # 948 from 14.4 s, evened: his face to that sky; then he lowers it and turns away
     "move": {"z": [1.0, 1.16]}, "trans": {"type": "dissolve", "dur": 0.4},
     "text": {"glow": 0.45, "wrap": 0.35, "pool": 0.6}},
    # ---------------------------------------------------------------- 5  time pelted me; my heart in a sheath of arrows
    {"id": "train", "src": clip(1622), "lic": 1622, "start": 19.5, "time": [[19.5, 2.3], [20.17, 4.2]], "shutter": 0.9,
     "window": {"cx": 0.54, "cy": 0.58, "fill": 1.25}, "move": {"z": [1.0, 1.14]}, "grade": {"ev": -0.3, "sat": 0.6, "temp": -0.1},
     "text": {"pool": 0.8}},
    {"id": "clock", "src": clip(28885), "lic": 28885, "start": 20.17, "time": [[20.17, 8.5], [20.52, 8.95], [20.6, 9.6]], "window": {"cx": 0.72},
     # the dial stays lit for the whole word and goes out into the cut
     "move": {"z": [1.0, 1.08]}, "grade": {"ev": 0.8, "sat": 0.5, "temp": -0.2}, "trans": {"type": "flash", "dur": 0.2, "gain": 0.55, "rgb": [1.0, 0.95, 0.88]},
     "text": {"mode": "ink", "ink_rgb": [10, 10, 14], "texture": 0.3}},  # the word printed on the dial like its numerals
    {"id": "volley", "src": clip(4426), "lic": 4426, "start": 20.6, "in": 1.4, "speed": 0.8, "rotate": 90, "move": {"z": [1.0, 1.12]},
     "soften": 3.5, "grade": {"ev": 0.45, "sat": 0.95, "r2g": 0.3, "halation": 0.5}, "trans": {"type": "dissolve", "dur": 0.2},  # embers, not red pixels
     "text": {"pool": 0.7, "glow": 0.45, "occlude": {"type": "luma", "lo": 0.6, "hi": 0.92, "gain": 0.8, "blur": 1.5}}},
    {"id": "coal", "src": clip(3462), "lic": 3462, "start": 21.56, "in": 4.6, "window": {"cx": 0.62, "cy": 0.42, "fill": 1.6},  # arrives on «حَتّى»: "until..." and the heart is there
     "move": {"z": [1.0, 1.1]}, "grade": {"ev": 0.55, "sat": 0.95, "r2g": 0.25, "halation": 0.4}, "trans": {"type": "dissolve", "dur": 0.3},
     "text": {"glow": 0.5, "pool": 0.4}},
    {"id": "thorns", "src": clip(3969), "lic": 3969, "start": 22.46, "in": 10.0, "window": {"cx": 0.45, "cy": 0.36, "fill": 1.4},
     "move": {"z": [1.0, 1.1]}, "soften": 3.5,  # the branches are foreground, a little out of focus; the words behind them are sharp
     "grade": {"ev": -2.6, "sat": 1.0, "temp": 0.5, "contrast": 1.15}, "trans": {"type": "dissolve", "dur": 0.36},
     "text": {"glow": 0.5, "pool": 1.0, "occlude": {"type": "luma", "lo": 0.055, "hi": 0.14, "invert": True, "gain": 0.9, "blur": 2.5}}},
    # ---------------------------------------------------------------- 6  now the blades break upon the blades
    {"id": "man2", "src": clip("948-13"), "lic": 948, "start": 23.7, "in": 0.2, **{**MAN, "window": {"cx": 0.715, "cy": 0.55, "fill": 1.18}}, "flip": True,
     # 948 from 16.8 s, evened, seen from the other side and closer, his whole head in frame: not the frame the last line ended on
     "move": {"z": [1.0, 1.1]},
     "text": {"glow": 0.45, "wrap": 0.35, "pool": 0.3, "occlude": {"type": "luma", "lo": 0.8, "hi": 1.0, "gain": 0.6, "blur": 1.5}}},
    {"id": "shards", "src": clip(1956), "lic": 1956, "start": 25.52, "in": 13.75, "speed": 1.1, "rotate": 90,  # splinters of rock in exploding water
     "move": {"z": [1.14, 1.02]}, "shake": {"amp": 9, "rot": 0.3, "seed": 22, "period": 0.3}, "shock": {"at": 25.52, "dur": 0.35, "amount": 0.02, "gain": 0.3},
     "grade": {"ev": -0.5, "sat": 0.4, "temp": -0.2, "contrast": 1.15}, "text": {"pool": 1.2, "glow": 0.4}},
    {"id": "blade", "src": clip(51455), "lic": 51455, "start": 26.22, "in": 17.1, "speed": 1.2, "rotate": 90,  # the long rock, stood up: a blade
     "move": {"z": [1.1, 1.0]}, "shake": {"amp": 5, "rot": 0.2, "seed": 21, "period": 0.4},
     "grade": {"ev": -1.35, "sat": 0.22, "temp": -0.3, "contrast": 1.15}, "text": {"pool": 1.4, "glow": 0.4}},  # foam kept grey so the gold word stands on it
    {"id": "rock", "src": clip(44398), "lic": 44398, "start": 26.84, "time": [[26.84, 1.0], [27.8, 13.0], [28.5, 14.8], [31.0, 18.0]], "shutter": 1.0,  # the fall onto the rock, then it stays
     "rotate": 90, "grade": {"ev": -0.35, "sat": 0.45, "temp": -0.15, "contrast": 1.12},
     "grade_keys": [[26.84, {"ev": -0.35}], [30.15, {"ev": -0.35}], [30.95, {"ev": -9.0}]], "text": {"pool": 1.2, "glow": 0.4}},
]

# the hemistichs, block by block: (first word, one past the last word, y, size, extra)
# A block leaves with its shot: on a hard cut it is gone on the cut frame; into a transition it fades over the
# transition's first half. "clear"/"out" in extra override that. "at": {word: time} shows a word before it is
# spoken (a rhyme word brought on with the word before it).
lines = {
    "v1a": {"em": [0], "parts": [(0, 1, 0.625, 190, {"x": 0.33}),                                 # on the earth where the hand will press: it is buried
                                 (1, 3, 0.79, 140, {"x": 0.42}),                                  # below the hand's reach, in the soft foreground
                                 (3, 4, 0.762, 170, {"clear": 4.62, "out": 0.1})]},               # beneath the foot that comes down
    "v1b": {"em": [3], "parts": [(0, 1, 0.766, 165, {"x": 0.6}),                                  # its marks clear of the planted toes
                                 (1, 3, 0.52, 132, {"x": 0.21, "clear": 6.31, "out": 0.08}),      # on the sand the sea is about to reach, clear of his ankle
                                 (3, 4, 0.64, 200, {"x": 0.42, "at": {3: 5.78}, "clear": 6.31, "out": 0.08})]},  # over the footprint, as the foot lifts off it; gone before the flash
    "v2a": {"em": [1], "parts": [(0, 1, 0.645, 180, {"lead": 0.0}), (1, 2, 0.76, 180, {}), (2, 3, 0.5, 210, {})]},  # «نُعِدُّ» comes with the pour, not over the flash
    "v2b": {"em": [1], "parts": [(0, 2, 0.41, 160, {"clear": 10.58, "out": 0.3}), (2, 4, 0.525, 160, {"clear": 10.58, "out": 0.3})]},
    "v3a": {"em": [1], "parts": [(0, 1, 0.735, 180, {}), (1, 2, 0.735, 180, {}), (2, 3, 0.735, 180, {})]},
    "v3b": {"em": [4], "parts": [(0, 2, 0.31, 175, {}), (2, 4, 0.425, 175, {}), (4, 5, 0.42, 230, {})]},  # on the horse's dark flank; the hooves stay clear
    "v4a": {"em": [3], "parts": [(0, 1, 0.64, 220, {"x": 0.4}), (1, 3, 0.77, 160, {"x": 0.4, "at": {2: 15.971}}), (3, 4, 0.62, 220, {})]},  # inside his shoulders, wherever he leans
    "v4b": {"parts": [(0, 3, 0.625, 130, {"x": 0.38}), (3, 5, 0.768, 165, {"x": 0.38})]},
    "v5a": {"em": [1], "parts": [(0, 1, 0.71, 210, {}), (1, 2, 0.52, 230, {"x": 0.37, "lead": 0.0}),  # «الدَهرُ» is printed on the dial: it cannot come before the dial
                                 (2, 3, 0.7, 200, {"lead": 0.0}), (3, 4, 0.318, 150, {})]},
    "v5b": {"em": [0, 4], "parts": [(0, 1, 0.44, 220, {}), (1, 3, 0.43, 190, {}), (3, 5, 0.685, 200, {"at": {4: 23.156}})]},  # the sun (the heart) sits between the two rows
    "v6a": {"em": [3], "parts": [(0, 2, 0.632, 130, {"x": 0.58}), (2, 4, 0.765, 160, {"x": 0.53})]},  # both rows inside his shoulders, clear of the smoke and of the button column at the right edge
    "v6b": {"em": [1, 3], "parts": [(0, 1, 0.72, 200, {"breakAt": 25.95}),  # the word that means "shattered" cracks before the cut takes it
                                    (1, 2, 0.72, 220, {}), (2, 4, 0.735, 200, {"clear": 28.25, "out": 0.45})]},
}

extra_lines = [
    {"id": "title", "words": [{"text": "المُتَنَبّي", "start": 0.0}], "allAt": -0.3, "rise": 0.3, "clear": 1.76, "out": 0.1,  # up on the first frame
     "y": 0.535, "x": 0.42, "size": 210, "family": "ArefRuqaaB", "weight": 700, "color": "#FFE2B0"},  # in the dark between two logs, the flame beside it
    {"id": "credit1", "words": [{"text": "شِعر: أبو الطيّب المتنبّي", "start": 28.45}], "allAt": 28.45, "rise": 0.6, "clear": 30.55, "out": 0.5,
     "y": 0.715, "size": 84, "color": "#F2E6CF", "push": 0.0},
    {"id": "credit2", "words": [{"text": "إلقاء: عبدالله العنزي", "start": 28.75}], "allAt": 28.75, "rise": 0.6, "clear": 30.55, "out": 0.5,
     "y": 0.785, "size": 76, "color": "#F2E6CF", "push": 0.0},
]

overlays = [
    # the arrows reach him: real embers cross the man's silhouette, at working level from the first frame of his shot and
    # held there (a steady stretch of the clip, played frame for frame: it is a 30 fps file), blurred along their flight so
    # they read as shafts, with a little of their own light on what they cross; gone with the cut
    {"src": clip(4426), "rotate": 90, "start": 23.7, "end": 25.52, "in": 2.6, "speed": 0.8, "gain": 1.6, "fade_in": 0.0, "fade_out": 0.0, "black": 0.55,  # only the bright cores: sparks in flight, not a haze of fire
     "r2g": 0.35, "soften": 1.2, "tint": [1.0, 0.92, 0.8], "streak": {"length": 46, "angle": -37}, "glow": {"sigma": 46, "gain": 0.25}},
]


def build() -> dict:
    out_shots = []
    for s in shots:
        d = {k: v for k, v in s.items() if k != "lic"}
        d["licence"] = MIXKIT.format(s["lic"])
        out_shots.append(d)
    here = os.path.dirname(os.path.abspath(__file__))
    words = json.load(open(os.path.join(here, "..", "timing.json"), encoding="utf-8"))["words"]
    starts = [s["start"] for s in shots]

    def leaves(onset: float) -> dict:
        """When a block spoken from `onset` leaves: with its shot."""
        i = max(k for k, t0 in enumerate(starts) if t0 <= onset + 1e-6)
        if i + 1 >= len(shots):
            return {}
        nxt = shots[i + 1]
        tr = nxt.get("trans", {})
        if tr.get("type", "cut") == "cut":
            return {"clear": nxt["start"], "out": 0.0}
        d = float(tr.get("dur", 0.25))
        return {"clear": round(nxt["start"] + min(0.02, d / 4), 3), "out": round(min(d / 2, 0.12), 3)}

    def arrives(onset: float) -> dict:
        """A word normally shows 0.06 s before its onset; never before a hard cut into its own shot."""
        i = max(k for k, t0 in enumerate(starts) if t0 <= onset + 1e-6)
        st = shots[i]
        if i > 0 and st.get("trans", {}).get("type", "cut") == "cut" and onset - 0.06 < st["start"] + 1.0 / 24:
            return {"lead": round(max(0.0, onset - st["start"] - 1.0 / 24), 3)}
        return {}

    out_lines = {}
    for lid, spec in lines.items():
        ws = [w for w in words if w["line"] == lid]
        out_lines[lid] = {"em": spec.get("em", []),
                          "parts": [{"words": [a, b], "y": y, "size": size, **leaves(ws[a]["start"]), **arrives(ws[a]["start"]), **extra}
                                    for a, b, y, size, extra in spec["parts"]]}
    return {"fps": 24, "w": 2160, "h": 3840, "duration": 31.0, "audio": f"{ROOT}/v4/audio/original_mix_48k.wav", "timing": "data/timing.json",
            "look": {"pre": 0.8, "vignette": 0.3, "halation": 0.24, "split": 0.5, "sat": 0.86},
            "text_default": {"mode": "light", "soft": 0.8, "shade": 0.5, "texture": 0.45, "glow": 0.34, "wrap": 0.22, "pool": 0.5},
            "line_default": {"out": 0.06, "color": CREAM, "emColor": GOLD},
            "lines": out_lines, "extra_lines": extra_lines, "shots": out_shots, "overlays": overlays}


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    json.dump(build(), open(os.path.join(here, "plan.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote", os.path.join(here, "plan.json"), len(shots), "shots")
