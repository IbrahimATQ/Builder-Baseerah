#!/usr/bin/env python3
"""The edit of "a slow morning in Warsaw", written down once. Running it writes data/plan.json.

Picture: the prepared stretches (pipeline/prep.py) play at 0.8x, frame for frame, 24 fps, 2160x3840.
`in` is a time inside a prepared stretch ((source time - from) / 0.8).

Music: Mixkit 599 "Possible Dreams" (Eugenio Mininni), Mixkit Stock Music Free License, entered at 9.83 s of
the track. Its quiet piano phrases fall at film 1.9 and 7.7 s, its swell at 12.6 s, its pulse at 15.03, 16.07,
17.21, 18.35, 19.50, 20.38, 21.25, 22.26, 23.17 ... s, and its first section dies away from about 32 s.
  0.0               the window opens on the painted facade: "Warszawa / STARE MIASTO"
  3.8   7.7         the square, then the long street (soft dissolves; 7.7 is a piano phrase)
  12.6              the swell: dissolve inside, the kettle's stream meets the coffee
  18.35             a pulse: dissolve to the slow spiral, closer (time passing)
  21.25             a pulse: the WARSZAWA mug; the pour, then the camera draws back to the window
  31.75 -> 36.0     dissolve to the view through the kitchen window; the music ends, the city's sound stays:
                    "the city can wait."
Changed after an independent review of the first cut: the kitchen-counter shot is gone (the weakest frame),
the brew is 8.7 s instead of 11.5, the second half is warmer and brighter and the cup is lit, the opening
starts later in the window shot with the title up within the first second, the ending no longer lays its
line over the pouring glass, and the quiet first half is louder.
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
    {"id": "window", "src": clip("window"), "in": 1.6, "start": 0.0, "end": 3.8,
     "move": {"z": [1.0, 1.03]}, "grade": {"ev": 0.0, "temp": 0.15}, "sound": {"db": -24}},
    {"id": "square", "src": clip("square"), "in": 0.6, "start": 3.8, "end": 7.7, "trans": {"type": "dissolve", "dur": 0.8},
     # the red houses and the square below, people crossing, a stone volute in front; held still (a pan across the
     # painted facade failed the flicker screen: rows of white window frames sliding through the picture)
     "move": {"z": [1.0, 1.04]}, "grade": {"ev": 0.0, "temp": 0.12}, "sound": {"db": -24}},
    {"id": "street", "src": clip("street"), "in": 2.5, "start": 7.7, "end": 12.6, "trans": {"type": "dissolve", "dur": 0.8},
     "move": {"z": [1.0, 1.06]}, "grade": {"ev": 0.05, "temp": 0.1}, "sound": {"db": -23}},
    {"id": "bloom", "src": clip("bloom"), "in": 1.0, "start": 12.6, "end": 18.35, "trans": {"type": "dissolve", "dur": 0.5},
     "move": {"z": [1.0, 1.06]}, "grade": BREW, "sound": {"db": -27, "hp": 160}},
    {"id": "spiral", "src": clip("spiral"), "in": 1.75, "start": 18.35, "end": 21.25, "trans": {"type": "dissolve", "dur": 0.6},
     "move": {"z": [1.42, 1.5], "cx": 0.5, "cy": 0.54}, "grade": BREW, "sound": {"db": -27, "hp": 160}},
    {"id": "pourcup", "src": clip("pourcup"), "in": 1.0, "start": 21.25, "end": 31.75,
     # cropped in a little toward the mug: the dish rack stays out of the left edge
     "move": {"z": [1.18, 1.16], "cx": 0.6, "cy": 0.5},
     "grade": {"ev": 0.95, "temp": 2.6, "tint": 4.2, "contrast": 1.05, "reds": 1.12, **NEUTRAL_LOWS},
     "light": {"ev": 0.45, "keys": [[0.0, 0.35, 0.69, 0.30, 0.17], [8.6, 0.36, 0.69, 0.30, 0.17], [9.6, 0.40, 0.68, 0.27, 0.15],
                                    [10.5, 0.52, 0.73, 0.22, 0.13]]},
     "sound": {"db": -20, "hp": 90, "lead": 0.2}},
    {"id": "roofs", "src": clip("roofs"), "in": 0.9, "start": 31.75, "end": 36.0, "trans": {"type": "dissolve", "dur": 1.0},
     "move": {"z": [1.08, 1.12], "cx": 0.5, "cy": 0.45}, "grade": {"ev": 0.1, "temp": 0.8, "tint": 1.2},
     "sound": {"db": -27, "hp": 100, "src": "street", "in": 0.5, "fade_out": [35.0, 36.0]}},  # the city, heard through the window
]

titles = [
    {"id": "open", "lines": [{"text": "Warszawa", "font": "cormorant-garamond-latin-500-italic.woff", "size": 300, "track": 0.0},
                             {"text": "STARE MIASTO", "font": "cormorant-garamond-latin-500-normal.woff", "size": 80, "track": 0.42, "gap": 34}],
     "y": 0.42, "rule": {"width": 0.10, "gap": 54}, "in": 0.1, "out": 3.55, "fade_in": 0.9, "fade_out": 0.55, "rise": 22, "focus": 6.0,
     "shade": 0.1, "shadow": 0.65},
    {"id": "close", "lines": [{"text": "the city can wait.", "font": "cormorant-garamond-latin-500-italic.woff", "size": 190, "track": 0.0}],
     "y": 0.30, "x": 0.6, "in": 32.6, "out": 36.0, "fade_in": 1.4, "fade_out": 0.0, "rise": 16, "focus": 6.0, "shade": 0.0, "shadow": 0.0,
     "color": [0.16, 0.13, 0.11]},  # warm charcoal on the pale sky in the window
]

finish = {"bloom": {"threshold": 0.72, "gain": 0.32, "radius": 0.035, "tint": [1.0, 0.82, 0.62]},
          "vignette": 0.22, "grain": 0.022, "fade_in": 0.2, "fade_out": [34.9, 36.0]}

music = {"file": "/home/user/coffee/music/599.mp3", "id": 599, "title": "Possible Dreams", "artist": "Eugenio Mininni",
         "licence": "Mixkit Stock Music Free License", "page": "https://mixkit.co/free-stock-music/classical/",
         "offset": 9.83, "fade_in": 0.6, "fade_out": [32.4, 34.2], "db": 0.0,
         # the quiet piano half up 4 dB (the film's loudness range was 10.8 LU); room for the pour into the mug
         "keys": [[0, 4.0], [11.4, 4.0], [12.6, 0.0], [22.6, 0.0], [23.1, -3.0], [30.0, -3.0], [31.0, 0.0]]}


def build() -> dict:
    return {"fps": FPS, "w": 2160, "h": 3840, "duration": 36.0, "look": look, "shots": shots, "titles": titles,
            "finish": finish, "music": music, "fonts": os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")}


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    json.dump(build(), open(os.path.join(here, "plan.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote plan.json:", len(shots), "shots,", len(titles), "titles")
