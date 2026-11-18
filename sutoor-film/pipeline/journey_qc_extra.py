#!/usr/bin/env python3
"""Extra checks for the Journey edition (after qc_film.py):
  * per shot: share of pixels at or below video black (Y <= 18 of 16-235); more than 25 % reads as
    crushed / composited
  * per shot: mean luma (catches a shot graded too dark to read)
  * a still at every hemistich onset + 0.6 s and at its end + 0.3 s, tiled into one review sheet
    (text placement, harakat not clipped, nothing in the bottom 20 %)
  * burns (optional): the fire may not touch a word's ink before that word's end + 0.3 s
    (from each burn's render meta, `word_first_burn_s`, against the aligned word times)
Usage: python journey_qc_extra.py FILM.mp4 picture_plan.json timing.json OUT_DIR [BURN.meta.json:LINE ...]
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import numpy as np


def frame(film: str, t: float, w: int = 540, h: int = 960) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", film, "-frames:v", "1", "-vf", f"scale={w}:{h}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(h, w, 3)


def luma_limited(film: str, t: float) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", film, "-frames:v", "1", "-vf", "scale=540:960,format=yuv420p,extractplanes=y",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8)  # the file is tagged limited range: gray keeps 16-235 codes


def main(film: str, plan_p: str, timing_p: str, out_dir: str, *burns: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    plan = json.load(open(plan_p, encoding="utf-8"))
    timing = json.load(open(timing_p, encoding="utf-8"))
    shots = plan["shots"]
    rep: dict = {"shots": []}
    for i, s in enumerate(shots):
        a = s["start"]
        b = shots[i + 1]["start"] if i + 1 < len(shots) else plan["end"]
        ts = np.linspace(a + 0.1, b - 0.1, 4)
        ys = [luma_limited(film, float(t)) for t in ts]
        crushed = float(np.mean([np.mean(y <= 18) for y in ys]))
        rep["shots"].append({"id": s["id"], "from": a, "to": b, "crushed_pct": round(100 * crushed, 1),
                             "mean_Y": round(float(np.mean([y.mean() for y in ys])), 1)})
    rep["crushed_max_pct"] = max(x["crushed_pct"] for x in rep["shots"])
    rep["burns"] = []
    for arg in burns:
        mp, line = arg.rsplit(":", 1)
        meta = json.load(open(mp))
        ws = [w for w in timing["words"] if w["line"] == line]
        for w, fb in zip(ws, meta.get("word_first_burn_s", [])):
            margin = None if fb is None else round(fb - w["film_end"], 3)
            rep["burns"].append({"burn": os.path.basename(mp), "word": w["word"], "spoken_end": w["film_end"], "first_burn": fb,
                                 "margin_s": margin, "ok": margin is None or margin >= 0.3})
    rep["burns_ok"] = all(b["ok"] for b in rep["burns"])
    # stills at every hemistich
    tiles = []
    for k, h in timing["hemistichs"].items():
        for t in (h["start"] + 0.6, h["end"] + 0.3):
            tiles.append(frame(film, t)[: int(960 * 0.55)])
    rows = [np.hstack(tiles[i:i + 6]) for i in range(0, len(tiles), 6)]
    w = max(r.shape[1] for r in rows)
    rows = [np.pad(r, ((0, 0), (0, w - r.shape[1]), (0, 0))) for r in rows]
    sheet = np.vstack(rows)
    import cv2
    cv2.imwrite(os.path.join(out_dir, "hemistich_stills.jpg"), cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 88])
    json.dump(rep, open(os.path.join(out_dir, "journey_qc_extra.json"), "w"), indent=1)
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:])
