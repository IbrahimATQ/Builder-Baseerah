#!/usr/bin/env python3
"""WARSZAWA (the window): the edit, written down once. Running it writes data/cuesheet3.json, the contract shared
by the picture (data/plan3.py), the score (pipeline/compose3.py) and the sound (data/sound3.py).

The film is one look that never turns back: from the dark back of the flat to the open front window.
  1.0   the kitchen, his eyes adjusting; the walk along the counter; LOOK 1 at the church behind the closed glass
  12.5  the kettle is ready: the first water on the coffee, in slow motion (his attention narrows to a thread)
  19.7  dissolve, same place later: the last pours, the spout withdraws, he straightens: LOOK 2
  28.9  vessel to vessel: the empty WARSZAWA mug; the coffee pours into the printed city (slow motion);
        a bell through the glass; the camera rises from the full cup to the window: LOOK 3
  44.5  the latch: the music stops dead, the old front window opens, the city floods in at full range;
        the turn right along the house opposite, his own pilaster sweeps past, the long street
  59.1  dissolve, same place later: he turns away past the pilaster to the sill and the medallion opposite
  63.9  cut on the look to his other window: the outer casement swings away, the gaze travels left along the
        sgraffito, the red houses, the Castle Square; the stone volute slides in like a curtain (75.1: the climax)
  77.5  WARSZAWA, the word from the mug, above the real castle            84.6  black; the city is the last sound
Source times are seconds of the iPhone clips. Prepared stretches (pipeline/prep.py) show one real 30 fps frame per
1/24 s, so 0.8x is "every real frame once". Slow motion below 0.8x is made of real frames plus learned in-between
frames (pipeline/retime.py, RIFE) at exactly the positions the speed curve asks for; speed changes are ramped.
"""
from __future__ import annotations

import json
import os

import numpy as np

FPS = 24
RAW_FPS = 30.0
RAMP = 0.30      # seconds over which a speed change is eased (a box filter on the speed curve: the source span is kept)

# Each shot: the part of a clip it shows, as source segments (src_in, src_out, speed vs real time), the film time
# its first visible frame lands on, and how it comes in. A dissolve overlaps the previous shot by `dur`: the incoming
# shot's first visible frame is at the dissolve's start, the outgoing shot's last visible frame at its end.
SHOTS = [
    {"id": "black_in", "black": True, "dur": 1.0},
    {"id": "walk", "clip": "IMG_5420", "prep": "k_walk", "segs": [(0.6, 8.8, 0.8)], "trans": {"type": "cut"}},
    {"id": "bloom", "clip": "IMG_5421", "prep": "bloom", "segs": [(1.2, 1.9, 0.8), (1.9, 1.9 + 14 / 6, 0.5), (1.9 + 14 / 6, 5.1, 0.8)],
     "trans": {"type": "cut"}, "retime": True},
    # (review 1: the dissolve lands on the finished, dripping bed: no second kettle, and "later" reads)
    {"id": "brew", "clip": "IMG_5421", "prep": "k_brew", "segs": [(18.4, 18.4 + 137 * 0.8 / FPS, 0.8)], "trans": {"type": "dissolve", "dur": 0.75}},
    {"id": "cup", "clip": "IMG_5422", "prep": "k_cup", "segs": [(1.0, 2.6, 0.8), (2.6, 2.6 + 5 / 6, 0.5), (2.6 + 5 / 6, 4.5 + 212 * 0.8 / FPS, 0.8)],
     "trans": {"type": "cut"}, "retime": True},
    {"id": "open", "clip": "IMG_5417", "prep": "w_open", "segs": [(0.0, 11.3, 0.8)], "trans": {"type": "cut"}},
    {"id": "turn", "clip": "IMG_5417", "prep": "w_turn", "segs": [(27.2, 27.2 + 87 * 0.8 / FPS, 0.8)], "trans": {"type": "dissolve", "dur": 1.0}},
    # (review 1: the turn is cut where his own pilaster fills the frame, and the square comes in with the casement
    # already crossing: a wipe into a wipe, not a jump inside one view)
    {"id": "square", "clip": "IMG_5416", "prep": "w_square", "segs": [(4.4, 20.6, 0.8)], "trans": {"type": "cut"}},
    {"id": "black_out", "black": True, "dur": 44 / FPS},
]

# Every shot lasts a whole number of frames, so every cut lands on a frame. A slow-motion segment starts and ends where
# the source frame and the film frame coincide (src = from + m/30 and film = n/24 at the same moment), so the 0.8x parts
# around it show only real frames, never interpolated ones.

# what happens in the pictures, in source time (checked on the frames), and the cues placed on them
SRC_EVENTS = [
    ("walk", 1.0, "walk", "his first step along the counter"),
    ("walk", 2.6, "church_in", "the brick church slides into the window at left"),
    ("walk", 5.5, "rise1", "the eye rises to the window"),
    ("walk", 6.5, "look1", "LOOK 1: settled on the church behind the closed glass"),
    ("bloom", 1.85, "stream", "the thin stream touches the coffee"),
    ("bloom", 4.3, "slow1_end", "the slow motion ends"),
    ("brew", 18.4, "spout_out", "the brew is done: the dripper drips alone (the shot dissolves in here)"),
    ("brew", 19.4, "pullback", "he straightens: the camera draws back and tilts up"),
    ("brew", 21.0, "look2", "LOOK 2: the church fills the window"),
    ("cup", 2.4, "server_in", "the glass server tips in"),
    ("cup", 3.3, "pour", "the coffee touches the printed city"),
    ("cup", 2.6 + 5 / 6, "slow2_end", "the slow motion ends (the glug at src 3.53-3.66 plays at 0.8x on real frames)"),
    ("cup", 5.2, "hand", "his hand appears"),
    ("cup", 9.0, "server_out", "the server lifts away; the cup is full"),
    ("cup", 9.75, "bell2", "a bell through the glass"),
    ("cup", 10.0, "rise3", "LOOK 3: the camera rises from the cup to the window"),
    ("open", 1.5, "sash_clear", "the inner sash clears: daylight"),
    ("open", 3.0, "turn_right", "his gaze turns right along the facade"),
    ("open", 5.0, "pilaster1", "his pilaster sweeps across the frame"),
    ("open", 6.0, "street", "the long street opens below"),
    ("open", 9.5, "street_settled", "the view settles on the street"),
    ("turn", 29.66, "turn_away", "he turns away from the street"),
    ("turn", 30.0, "pilaster2", "the pilaster rushes past the lens: the cut is inside it"),
    ("square", 4.4, "casement", "his other window: the outer casement swings across"),
    ("square", 5.5, "city_doubles", "he leans out: the city doubles (the clip's own sound jumps)"),
    ("square", 6.1, "casement_clear", "the casement is clear"),
    ("square", 9.0, "red_houses", "the red houses swing in"),
    ("square", 11.5, "square_in", "the Castle Square appears"),
    ("square", 12.5, "volute", "the stone volute slides in like a curtain"),
    ("square", 13.0, "climax", "CLIMAX: the most open view of the Castle Square, the volute top left"),
    ("square", 14.5, "settle", "the stone has closed in like a curtain; the frame stops"),
]
# cues in film time that are not tied to a frame (sound-led)
FILM_EVENTS = [
    (0.35, "bell1", "bell stroke 1, far off, through glass, over black"),
    (1.0, "fade_up", "picture rises from black"),
    ("@bloom-0.08", "kettle_click", "the kettle clicks off, just before the cut"),
    ("@open-0.10", "latch", "the window latch, a tenth before the picture: the music stops dead on it"),
    ("@open+0.15", "bell3", "bell stroke 3 starts behind the glass and opens out with the sash"),
    ("@climax+1.5", "cup_on_sill", "off screen: a cup set down on the stone sill"),
    ("@climax+2.45", "title_in", "WARSZAWA fades into the sky above the castle"),
    ("@climax+5.15", "bell4", "bell stroke 4 in open air, inside the last chord"),
    ("@black_out", "end", "cut to black on the release of the last chord"),
]


def speed_curve(segs, ramp: float):
    """Film-time sampling of one shot's source position: returns (film offsets at FPS, source seconds)."""
    durs = [(b - a) / v for a, b, v in segs]
    total = sum(durs)
    edges = np.cumsum([0.0] + durs)
    # V(g): the source position of the un-eased curve (piecewise linear, continued straight beyond both ends)
    V = lambda g: np.interp(g, edges, [segs[0][0]] + [b for _, b, _ in segs], left=np.nan, right=np.nan)

    def V_ext(g):
        g = np.asarray(g, np.float64)
        y = V(g)
        y = np.where(g < 0, segs[0][0] + g * segs[0][2], y)
        return np.where(g > total, segs[-1][1] + (g - total) * segs[-1][2], y)

    # the speed eased by a box filter of width `ramp` = the position averaged over +-ramp/2 (exact away from the
    # changes: the 0.8x parts keep their real frames, and the source span is preserved)
    off = np.linspace(-ramp / 2, ramp / 2, 2001) if ramp > 0 and len(segs) > 1 else np.zeros(1)

    def pos_at(g):
        g = np.atleast_1d(np.asarray(g, np.float64))
        return np.array([np.trapezoid(V_ext(x + off), off) / (off[-1] - off[0]) if len(off) > 1 else float(V_ext(x)) for x in g])

    grid = np.linspace(0.0, total, int(round(total * 960)) + 1)
    return grid, pos_at(grid), total, pos_at


def fr(x: float) -> float:
    """A film time snapped to its frame, as the renderer computes it (frame / fps): cuts compare exactly."""
    return round(x * FPS) / FPS


def build() -> dict:
    t = 0.0
    out = []
    for s in SHOTS:
        if s.get("black"):
            out.append({"id": s["id"], "black": True, "film_in": fr(t), "film_out": fr(t + s["dur"])})
            t = fr(t + s["dur"])
            continue
        tr = s.get("trans", {"type": "cut"})
        if tr["type"] == "dissolve":
            t = fr(t - tr["dur"])
        grid, pos, total, fpos = speed_curve(s["segs"], RAMP)
        assert abs(total * FPS - round(total * FPS)) < 1e-6, (s["id"], total * FPS)
        out.append({**{k: v for k, v in s.items() if k not in ("segs",)}, "segs": [list(x) for x in s["segs"]],
                    "film_in": fr(t), "film_out": fr(t + total), "_grid": grid, "_pos": pos, "_f": fpos})
        t = fr(t + total)
    duration = t
    by = {s["id"]: s for s in out}
    # where each shot takes over in the renderer: the middle of a dissolve, else the first visible frame
    for i, s in enumerate(out):
        tr = s.get("trans", {})
        s["start"] = fr(s["film_in"] + (tr["dur"] / 2 if tr.get("type") == "dissolve" else 0.0))
    for i, s in enumerate(out):
        s["end"] = out[i + 1]["start"] if i + 1 < len(out) else s["film_out"]
    events = []

    def src_to_film(sid, src):
        s = by[sid]
        i = int(np.searchsorted(s["_pos"], src))
        i = min(max(i, 1), len(s["_pos"]) - 1)
        a, b = s["_pos"][i - 1], s["_pos"][i]
        g = s["_grid"][i - 1] + (src - a) / max(b - a, 1e-9) * (s["_grid"][i] - s["_grid"][i - 1])
        return s["film_in"] + g

    for sid, src, key, what in SRC_EVENTS:
        events.append({"t": round(src_to_film(sid, src), 3), "key": key, "what": what, "shot": sid, "src": src})
    named = {e["key"]: e["t"] for e in events}
    for spec, key, what in FILM_EVENTS:
        if isinstance(spec, str):
            ref, off = spec[1:], 0.0
            for sign in ("+", "-"):
                if sign in ref:
                    ref, o = ref.split(sign)
                    off = float(o) * (1 if sign == "+" else -1)
            base = by[ref]["start"] if ref in by else named[ref]
            tt_ = base + off
        else:
            tt_ = spec
        events.append({"t": round(tt_, 3), "key": key, "what": what})
    events.sort(key=lambda e: e["t"])
    # per-frame source positions of each shot (film frame -> source seconds), for the retimed slow-motion clips
    shots = []
    for s in out:
        d = {k: v for k, v in s.items() if not k.startswith("_")}
        if not s.get("black"):
            f0 = int(np.floor(s["film_in"] * FPS + 1e-6))
            f1 = int(np.ceil(s["film_out"] * FPS - 1e-6))
            frames = []
            for f in range(f0, f1 + 1):
                g = f / FPS - s["film_in"]
                frames.append(round(float(s["_f"](g)[0]), 5))
            d["first_frame"] = f0
            d["src_at_frame"] = frames
        shots.append(d)
    return {"title": "WARSZAWA", "fps": FPS, "duration": duration, "ramp_s": RAMP, "shots": shots, "events": events}


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    cs = build()
    json.dump(cs, open(os.path.join(here, "cuesheet3.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for s in cs["shots"]:
        print(f"{s['id']:10s} visible {s['film_in']:7.3f}-{s['film_out']:7.3f}  render {s['start']:7.3f}-{s['end']:7.3f}")
    for e in cs["events"]:
        print(f"  {e['t']:7.3f}  {e['key']:15s} {e['what']}")
    print("duration", cs["duration"])
