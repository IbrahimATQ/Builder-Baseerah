#!/usr/bin/env python3
"""Photosensitive-epilepsy screen (general flash, WCAG 2.3.1 / Harding-style approximation).

A transition is a change in relative luminance of >= 0.1 (of max) where the darker state is < 0.8.
A flash is a pair of opposing transitions. FAIL if, in any 1 s window, more than 3 flashes (>= 7
transitions) occur over a combined area larger than ~11% of the screen (the 0.006 sr / 341x256-at-
1024x768 threshold). Red-flash rules are not evaluated. This is a screen, not a certified test.

Usage: python flash_check.py FILM.mp4 [START END] [--grid 32x18]
Prints JSON: verdict, worst window, max flashing area fraction.
"""
from __future__ import annotations

import json
import subprocess
import sys

import numpy as np


def frames(path: str, start: float | None, end: float | None, w: int, h: int):
    cmd = ["ffmpeg", "-v", "error"]
    if start is not None:
        cmd += ["-ss", f"{start}", "-t", f"{end - start}"]
    cmd += ["-i", path, "-vf", f"scale={w}:{h}:flags=area,format=rgb24", "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)


def rel_lum(rgb: np.ndarray) -> np.ndarray:
    c = rgb.astype(np.float32) / 255.0
    lin = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]


def transitions(series: np.ndarray) -> list[int]:
    """Frame indices at which a qualifying transition completes. After a rise, track the peak;
    a fall of >= 0.1 from it (ending below 0.8) is a transition, and vice versa."""
    out: list[int] = []
    hi = lo = float(series[0])
    direction = 0  # +1 after a rise, -1 after a fall, 0 before the first transition
    for i in range(1, len(series)):
        v = float(series[i])
        if direction >= 0 and hi - v >= 0.1 and v < 0.8:      # fall from the peak
            out.append(i); direction = -1; lo = hi = v
            continue
        if direction <= 0 and v - lo >= 0.1 and lo < 0.8:     # rise from the trough
            out.append(i); direction = 1; lo = hi = v
            continue
        hi, lo = max(hi, v), min(lo, v)
    return out


def main() -> None:
    args = [a for a in sys.argv[1:]]
    grid = "32x18"
    if "--grid" in args:
        i = args.index("--grid"); grid = args[i + 1]; del args[i:i + 2]
    path = args[0]
    start = float(args[1]) if len(args) > 2 else None
    end = float(args[2]) if len(args) > 2 else None
    gw, gh = map(int, grid.split("x"))
    fps = 30.0
    L = rel_lum(frames(path, start, end, gw, gh))  # (T, gh, gw): block means via area scaling
    T = L.shape[0]
    marks = np.zeros((T, gh, gw), bool)
    for y in range(gh):
        for x in range(gw):
            for t in transitions(L[:, y, x]):
                marks[t, y, x] = True
    win = int(fps)
    worst = {"area": 0.0, "t": None}
    for t0 in range(0, max(1, T - win + 1)):
        cnt = marks[t0:t0 + win].sum(axis=0)
        area = float((cnt >= 7).mean())
        if area > worst["area"]:
            worst = {"area": round(area, 4), "t": round((start or 0) + t0 / fps, 2)}
    full = L.reshape(T, -1).mean(axis=1)
    res = {
        "file": path, "range": [start, end], "grid": grid,
        "max_flashing_area_fraction": worst["area"], "worst_window_start_s": worst["t"],
        "threshold_area_fraction": 0.11,
        "verdict": "FAIL" if worst["area"] > 0.11 else "PASS",
        "whole_frame_transitions": len(transitions(full)),
    }
    print(json.dumps(res))


if __name__ == "__main__":
    main()
