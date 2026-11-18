#!/usr/bin/env python3
"""Hold a point of the ground still inside a tracking shot: the camera travels on, the frame stays behind.

A tracking shot follows a walker; the ground slides through the frame. This tool measures that slide frame
by frame (large patches of bare ground matched to a fraction of a pixel, in the band of the picture the
point lies in, since nearer ground slides faster) and writes the window centres that keep one ground point
at a fixed place in the output frame. The film then shows what a camera left standing would have seen: the
walker leaves, the footprint stays.

Usage: python ground_lock.py CLIP.mp4 OUT.json --point X,Y --at FRAME --frames A,B [--band 180] [--strip X0,X1]
  --point   the ground point in source pixels, as seen in frame FRAME (0-based frame index of the clip)
  --frames  first and last frame to lock
  --band    height in source px of the band around the point's row that is tracked
  --strip   the stretch of the row (source px, in frame FRAME) that is bare ground; it rides with the point and is
            held inside the picture where the point nears an edge
Writes {"clip", "fps", "point", "at", "track": [[frame, x, y], ...]}: where the point is in each frame.
montage.py plans use it through plan.py (move.keys built from the track).
"""
from __future__ import annotations

import json
import subprocess
import sys

import cv2
import numpy as np


def frames_gray(clip: str, a: int, b: int, w: int, h: int) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", clip, "-vf", f"select=between(n\\,{a}\\,{b}),format=gray", "-vsync", "0",
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)


def shift(a: np.ndarray, b: np.ndarray, box: tuple[int, int, int, int], reach: int = 90) -> tuple[float, float, float]:
    """Where the patch `box` of a is found in b: (dx, dy, score), to a fraction of a pixel."""
    x0, y0, x1, y1 = box
    hp = lambda im: im - cv2.GaussianBlur(im, (0, 0), 16)
    tpl = hp(a[y0:y1, x0:x1])
    sx0, sy0 = max(0, x0 - reach), max(0, y0 - 12)
    win = hp(b[sy0:min(b.shape[0], y1 + 12), sx0:min(b.shape[1], x1 + reach)])
    m = cv2.matchTemplate(win, tpl, cv2.TM_CCOEFF_NORMED)
    _, mx, _, loc = cv2.minMaxLoc(m)
    px, py = float(loc[0]), float(loc[1])
    if 0 < loc[0] < m.shape[1] - 1:
        l, c, r = m[loc[1], loc[0] - 1], m[loc[1], loc[0]], m[loc[1], loc[0] + 1]
        if l - 2 * c + r < -1e-6:
            px += 0.5 * (l - r) / (l - 2 * c + r)
    if 0 < loc[1] < m.shape[0] - 1:
        u, c, d = m[loc[1] - 1, loc[0]], m[loc[1], loc[0]], m[loc[1] + 1, loc[0]]
        if u - 2 * c + d < -1e-6:
            py += 0.5 * (u - d) / (u - 2 * c + d)
    return px + sx0 - x0, py + sy0 - y0, float(mx)


def main() -> None:
    a = sys.argv[1:]
    opt = {"--point": None, "--at": None, "--frames": None, "--band": "180", "--strip": None}
    for k in list(opt):
        if k in a:
            i = a.index(k); opt[k] = a[i + 1]; del a[i:i + 2]
    clip, out = a[0], a[1]
    px, py = [float(v) for v in opt["--point"].split(",")]
    at = int(opt["--at"]); fa, fb = [int(v) for v in opt["--frames"].split(",")]
    band = int(opt["--band"])
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate",
                                   "-of", "json", clip], capture_output=True, text=True, check=True).stdout)["streams"][0]
    W, H = int(j["width"]), int(j["height"]); n, d = j["r_frame_rate"].split("/")
    F = frames_gray(clip, fa, fb, W, H)
    off0, off1 = ([float(v) - px for v in opt["--strip"].split(",")] if opt["--strip"] else (-520.0, 100.0))
    width = off1 - off0
    y0, y1 = int(max(0, py - band / 2)), int(min(H, py + band / 2))
    pos = {at: (px, py)}
    scores = []
    reach = 90
    for step in (1, -1):  # forward from `at`, then backward
        x, y = px, py
        k = at
        while fa <= k + step <= fb:
            i0, i1 = k - fa, k + step - fa
            # the strip rides with the point, but keeps clear of the picture's edges by the search reach
            bx0 = int(min(max(x + off0, reach + 20), W - reach - 20 - width))
            dx, dy, sc = shift(F[i0], F[i1], (bx0, y0, int(bx0 + width), y1), reach)
            x, y = x + float(dx), y + float(dy)
            k += step
            pos[k] = (x, y); scores.append(sc)
    track = [[k, round(float(pos[k][0]), 2), round(float(pos[k][1]), 2)] for k in range(fa, fb + 1)]
    json.dump({"clip": clip, "fps": float(n) / float(d), "size": [W, H], "point": [px, py], "at": at, "track": track,
               "min_score": round(min(scores), 3)}, open(out, "w"), indent=1)
    xs = [t[1] for t in track]
    steps = np.diff(xs)
    print(json.dumps({"frames": len(track), "x_first": xs[0], "x_last": xs[-1], "step_mean": round(float(steps.mean()), 2),
                      "step_min": round(float(steps.min()), 2), "step_max": round(float(steps.max()), 2), "min_score": round(min(scores), 3)}))


if __name__ == "__main__":
    main()
