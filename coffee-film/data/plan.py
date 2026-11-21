#!/usr/bin/env python3
"""The edit of "a slow morning in Warsaw", written down once. Running it writes data/plan.json.

Picture: the prepared stretches (pipeline/prep.py) play at 0.8x, frame for frame, 24 fps, 2160x3840.
`in` is a time inside a prepared stretch ((source time - from) / 0.8).

Music: Mixkit 599 "Possible Dreams" (Eugenio Mininni), Mixkit Stock Music Free License, entered at 9.83 s of
the track. Its quiet piano phrases fall at film 1.9 and 7.7 s, its swell at 12.6 s, its pulse at 15.03, 16.07,
17.21, 18.35, 19.50, 20.38 ... s.
  0.0               the square: red houses, the castle square below, a stone volute; "Warszawa / STARE MIASTO" in the sky
  6.2               the long street (dissolve)
  12.6              the swell: dissolve inside, the kettle's stream meets the coffee
  19.5              a pulse: the stream of coffee into the WARSZAWA mug
  26.9 -> 31.5      dissolve to the view through the kitchen window; the music fades, the city's sound stays:
                    "the city can wait." in the sky pane; 0.4 s of black at the end
Third cut, after a second independent review: opens on the square (the strongest frame) instead of the window
bars; the closer brew shot and its double-image dissolve are gone; the green LED is keyed out in the lower part
of the brew frame only; the pour starts as the coffee enters the cup and leaves before the hand and the late
bubbles; the mug is warmer; the last line holds 2.5 s and the film rests on black.
"""
from __future__ import annotations

import json
import os

PREP = os.environ.get("COFFEE_PREP", "/home/user/coffee/prep")
FPS = 24


def clip(i: str) -> str:
    return f"{PREP}/{i}.mp4"


look = {"black": 0.028, "sat": 0.9, "shoulder": 0.82}
NEUTRAL_LOWS = {"cool_lo": [0.98, 0.99, 0.99]}  # inside, the shadows lose their cool cast
BREW = {"ev": 0.6, "temp": 1.9, "tint": 3.0, "contrast": 1.08, "greens": 0.1, "led": 1.0, "reds": 1.12, **NEUTRAL_LOWS}

shots = [
    {"id": "square", "src": clip("square"), "in": 0.6, "start": 0.0, "end": 6.2,
     # the film opens on its most beautiful frame: the red houses and the castle square below, a stone volute in front
     "move": {"z": [1.0, 1.05]}, "grade": {"ev": 0.0, "temp": 0.15}, "sound": {"db": -24}},
    {"id": "street", "src": clip("street"), "in": 2.5, "start": 6.2, "end": 12.6, "trans": {"type": "dissolve", "dur": 0.8},
     "move": {"z": [1.0, 1.06]}, "grade": {"ev": 0.05, "temp": 0.15}, "sound": {"db": -23}},
    {"id": "bloom", "src": clip("bloom"), "in": 1.0, "start": 12.6, "end": 19.5, "trans": {"type": "dissolve", "dur": 0.5},
     # inside, on the swell: the kettle's stream meets the coffee, the window and the red roofs behind
     "move": {"z": [1.0, 1.07]}, "grade": BREW, "key_green": {"y0": 0.42, "strength": 1.0}, "sound": {"db": -27, "hp": 160}},
    {"id": "pourcup", "src": clip("pourcup"), "in": 1.9, "start": 19.5, "end": 26.9,
     # from the moment the stream enters the cup; cropped so the hand stays out of the top and the dish rack out of the left
     "move": {"z": [1.22, 1.2], "cx": 0.62, "cy": 0.56},
     "grade": {"ev": 1.05, "temp": 3.2, "tint": 4.5, "contrast": 1.05, "reds": 1.12, **NEUTRAL_LOWS},
     "light": {"ev": 0.65, "tint": [1.0, 0.97, 0.9], "keys": [[0.0, 0.32, 0.62, 0.32, 0.18], [8.0, 0.32, 0.62, 0.32, 0.18]]},
     "sound": {"db": -20, "hp": 90, "lead": 0.2}},
    {"id": "roofs", "src": clip("roofs"), "in": 0.5, "start": 26.9, "end": 31.5, "trans": {"type": "dissolve", "dur": 1.0},
     "move": {"z": [1.08, 1.12], "cx": 0.5, "cy": 0.45}, "grade": {"ev": 0.1, "temp": 1.4, "tint": -0.5},
     "sound": {"db": -27, "hp": 100, "src": "street", "in": 0.5, "fade_out": [30.6, 31.4]}},  # the city, heard through the window
]

titles = [
    {"id": "open", "lines": [{"text": "Warszawa", "font": "cormorant-garamond-latin-500-italic.woff", "size": 215, "track": 0.0},
                             {"text": "STARE MIASTO", "font": "cormorant-garamond-latin-500-normal.woff", "size": 72, "track": 0.26, "gap": 24}],
     "y": 0.138, "x": 0.47, "rule": {"width": 0.08, "gap": 40}, "in": 0.1, "out": 5.4, "fade_in": 0.8, "fade_out": 0.6, "rise": 16,
     "focus": 5.0, "shade": 0.0, "shadow": 0.0, "color": [0.16, 0.13, 0.11]},  # warm charcoal on the pale sky, like the last line
    {"id": "close", "lines": [{"text": "the city can wait.", "font": "cormorant-garamond-latin-500-italic.woff", "size": 180, "track": 0.0}],
     "y": 0.30, "x": 0.575, "in": 27.2, "out": 31.5, "fade_in": 1.0, "fade_out": 0.0, "rise": 16, "focus": 6.0, "shade": 0.0, "shadow": 0.0,
     "color": [0.16, 0.13, 0.11]},  # in the sky pane of the window
]

finish = {"bloom": {"threshold": 0.72, "gain": 0.32, "radius": 0.035, "tint": [1.0, 0.82, 0.62]},
          "vignette": 0.22, "grain": 0.022, "fade_in": 0.2, "fade_out": [30.6, 31.1]}

music = {"file": "/home/user/coffee/music/599.mp3", "id": 599, "title": "Possible Dreams", "artist": "Eugenio Mininni",
         "licence": "Mixkit Stock Music Free License", "page": "https://mixkit.co/free-stock-music/classical/",
         "offset": 9.83, "fade_in": 0.6, "fade_out": [29.6, 31.1], "db": 0.0,
         # the quiet piano half up 4 dB (the film's loudness range was 10.8 LU); room for the pour into the mug
         "keys": [[0, 4.0], [11.4, 4.0], [12.6, 0.0], [19.3, 0.0], [19.8, -3.0], [25.8, -3.0], [26.8, 0.0]]}


def build() -> dict:
    return {"fps": FPS, "w": 2160, "h": 3840, "duration": 31.5, "look": look, "shots": shots, "titles": titles,
            "finish": finish, "music": music, "fonts": os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")}


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    json.dump(build(), open(os.path.join(here, "plan.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote plan.json:", len(shots), "shots,", len(titles), "titles")
