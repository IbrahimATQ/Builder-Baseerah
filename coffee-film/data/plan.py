#!/usr/bin/env python3
"""The edit of "a slow morning in Warsaw", written down once. Running it writes data/plan.json.

Picture: the prepared stretches (pipeline/prep.py) play at 0.8x, frame for frame, 24 fps, 2160x3840.
`in` is a time inside a prepared stretch ((source time - from) / 0.8).

Music: Mixkit 599 "Possible Dreams" (Eugenio Mininni), Mixkit Stock Music Free License, entered at 5.5 s of
the track so that its quiet piano phrases fall at film 1.0, 6.2 and 12.0 s, its swell at 16.93 s and its
pulse at 19.36, 20.40, 21.54, 22.68, 23.83, 24.71, 25.58, 26.59, 27.50, 28.44, 29.36 ... s, and its first
section dies away from about 36.3 s. The cuts are placed on those moments:
  1.0  6.2  12.0    piano phrases       window -> the square -> street (soft dissolves)
  14.4              the music thins     inside: the counter under the window
  16.93             the swell           the kettle's stream meets the coffee
  23.83             a pulse             the spiral pour, closer
  28.44             a pulse             the pour into the WARSZAWA mug; it lands on 29.36
  36.0 -> 40.0      the music's tail    the camera draws back to the window: "the city can wait."
"""
from __future__ import annotations

import json
import os

PREP = os.environ.get("COFFEE_PREP", "/home/user/coffee/prep")
FPS = 24


def clip(i: str) -> str:
    return f"{PREP}/{i}.mp4"


look = {"black": 0.028, "sat": 0.9, "shoulder": 0.82}

shots = [
    {"id": "window", "src": clip("window"), "in": 0.0, "start": 0.0, "end": 6.2,
     "move": {"z": [1.0, 1.035]}, "grade": {"ev": 0.0, "temp": 0.15}, "sound": {"db": -27}},
    {"id": "square", "src": clip("square"), "in": 0.5, "start": 6.2, "end": 12.0, "trans": {"type": "dissolve", "dur": 0.8},
     # the red houses and the square below, people crossing, a stone volute in front; held still (a pan across the
     # painted facade failed the flicker screen: rows of white window frames sliding through the picture)
     "move": {"z": [1.0, 1.04]}, "grade": {"ev": 0.0, "temp": 0.12}, "sound": {"db": -27}},
    {"id": "street", "src": clip("street"), "in": 2.5, "start": 12.0, "end": 14.4, "trans": {"type": "dissolve", "dur": 0.8},
     "move": {"z": [1.0, 1.05]}, "grade": {"ev": 0.05, "temp": 0.1}, "sound": {"db": -25}},
    {"id": "kitchen", "src": clip("kitchen"), "in": 1.25, "start": 14.4, "end": 16.93, "trans": {"type": "dissolve", "dur": 0.5},
     "move": {"z": [1.0, 1.02]}, "grade": {"ev": 0.6, "temp": 0.5, "contrast": 1.06, "reds": 1.1}, "sound": {"db": -34}},
    {"id": "bloom", "src": clip("bloom"), "in": 1.0, "start": 16.93, "end": 23.83,
     "move": {"z": [1.0, 1.06]}, "grade": {"ev": 0.4, "temp": 0.55, "contrast": 1.08, "greens": 0.15, "reds": 1.12},
     "sound": {"db": -24, "hp": 160, "lead": 0.25}},
    {"id": "spiral", "src": clip("spiral"), "in": 1.75, "start": 23.83, "end": 28.44,
     "move": {"z": [1.42, 1.5], "cx": 0.5, "cy": 0.54}, "grade": {"ev": 0.4, "temp": 0.55, "contrast": 1.08, "greens": 0.15, "reds": 1.12},
     "sound": {"db": -24, "hp": 160}},
    {"id": "pourcup", "src": clip("pourcup"), "in": 0.75, "start": 28.44, "end": 40.0,
     "move": {"z": [1.03, 1.0]}, "grade": {"ev": 0.55, "temp": 0.6, "contrast": 1.08, "reds": 1.15},
     "sound": {"db": -19, "hp": 90, "lead": 0.2, "fade_out": [38.6, 40.0]}},
]

titles = [
    {"id": "open", "lines": [{"text": "Warszawa", "font": "cormorant-garamond-latin-500-italic.woff", "size": 300, "track": 0.0},
                             {"text": "STARE MIASTO", "font": "cormorant-garamond-latin-500-normal.woff", "size": 66, "track": 0.45, "gap": 34}],
     "y": 0.42, "rule": {"width": 0.10, "gap": 54}, "in": 0.6, "out": 5.3, "fade_in": 1.4, "fade_out": 0.9, "rise": 26, "focus": 7.0,
     "shade": 0.34},
    {"id": "close", "lines": [{"text": "the city can wait.", "font": "cormorant-garamond-latin-500-italic.woff", "size": 190, "track": 0.0}],
     "y": 0.375, "in": 36.0, "out": 40.0, "fade_in": 1.6, "fade_out": 0.0, "rise": 18, "focus": 6.0, "shade": 0.3},
]

finish = {"bloom": {"threshold": 0.72, "gain": 0.32, "radius": 0.035, "tint": [1.0, 0.82, 0.62]},
          "vignette": 0.22, "grain": 0.022, "fade_in": 0.35, "fade_out": [39.0, 40.0]}

music = {"file": "/home/user/coffee/music/599.mp3", "id": 599, "title": "Possible Dreams", "artist": "Eugenio Mininni",
         "licence": "Mixkit Stock Music Free License", "page": "https://mixkit.co/free-stock-music/possible-dreams-599/",
         "offset": 5.5, "fade_in": 1.0, "fade_out": [36.6, 38.6], "db": 0.0,
         "keys": [[0, 0.0], [28.9, 0.0], [29.5, -3.5], [34.6, -3.5], [35.6, 0.0]]}


def build() -> dict:
    return {"fps": FPS, "w": 2160, "h": 3840, "duration": 40.0, "look": look, "shots": shots, "titles": titles,
            "finish": finish, "music": music, "fonts": os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")}


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    json.dump(build(), open(os.path.join(here, "plan.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote plan.json:", len(shots), "shots,", len(titles), "titles")
