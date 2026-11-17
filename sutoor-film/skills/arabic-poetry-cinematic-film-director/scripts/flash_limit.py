#!/usr/bin/env python3
"""Limit flash frequency in a clip (photosensitive-epilepsy safety) without changing its length.

Finds flash events (frames whose brightest-area luminance jumps >= 0.1 above the clip's dark
baseline), keeps the strongest ones subject to "at most N flashes in any 1 s window", and replaces
the frames of every other flash with the last non-flash frame before it. Lightning stays lightning;
it just strikes less often. Audio is dropped (shot intermediates carry no audio).

Usage: python flash_limit.py IN.mp4 OUT.mp4 [--max-per-second 2] [--keep-first]
--keep-first always keeps the first flash (e.g. a strike timed to a word).
"""
from __future__ import annotations

import json
import subprocess
import sys

import numpy as np


def probe(path: str) -> tuple[int, int, str]:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    s = json.loads(out)["streams"][0]
    return s["width"], s["height"], s["r_frame_rate"]


def rel_lum(rgb: np.ndarray) -> np.ndarray:
    c = rgb.astype(np.float32) / 255.0
    lin = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]


def flash_events(frames: np.ndarray, gw: int = 32, gh: int = 18) -> tuple[list[tuple[int, int, float]], np.ndarray]:
    T, H, W, _ = frames.shape
    small = frames[:, : H - H % gh, : W - W % gw].reshape(T, gh, (H - H % gh) // gh, gw, (W - W % gw) // gw, 3).mean(axis=(2, 4))
    L = rel_lum(small).reshape(T, -1)
    top = np.argsort(L.max(axis=0))[-max(1, int(0.15 * L.shape[1])):]  # brightest 15 % of the area
    m = L[:, top].mean(axis=1)
    base = float(np.percentile(m, 30))
    hot = m - base >= 0.1
    events, i = [], 0
    while i < T:
        if hot[i]:
            j = i
            while j + 1 < T and hot[j + 1]:
                j += 1
            events.append((i, j, float(m[i:j + 1].max())))
            i = j + 1
        else:
            i += 1
    return events, m


def choose(events: list[tuple[int, int, float]], fps: float, max_per_s: int, keep_first: bool) -> list[tuple[int, int, float]]:
    win = int(round(fps))
    kept: list[tuple[int, int, float]] = []
    order = sorted(events, key=lambda e: -e[2])
    if keep_first and events:
        order.remove(events[0])
        order.insert(0, events[0])
    for e in order:
        trial = sorted(kept + [e])
        ok = all(sum(1 for f in trial if t0 <= f[0] < t0 + win) <= max_per_s for t0 in range(max(0, e[0] - win + 1), e[0] + 1))
        if ok:
            kept = trial
    return kept


def main() -> None:
    args = sys.argv[1:]
    max_per_s = 2
    keep_first = "--keep-first" in args
    args = [a for a in args if a != "--keep-first"]
    if "--max-per-second" in args:
        i = args.index("--max-per-second"); max_per_s = int(args[i + 1]); del args[i:i + 2]
    src, dst = args
    w, h, rate = probe(src)
    num, den = map(int, rate.split("/"))
    fps = num / den
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3).copy()
    events, _ = flash_events(frames)
    kept = choose(events, fps, max_per_s, keep_first)
    dropped = [e for e in events if e not in kept]
    for (a, b, _) in dropped:
        hold = frames[a - 1] if a > 0 else frames[b + 1]
        frames[a:b + 1] = hold
    enc = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", rate,
                          "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "12", "-g", "15", "-pix_fmt", "yuv420p", dst],
                         input=frames.tobytes(), capture_output=True)
    if enc.returncode:
        raise SystemExit(enc.stderr.decode()[-500:])
    print(json.dumps({"flashes_found": len(events), "kept": [round(a / fps, 2) for a, _, _ in kept],
                      "suppressed": [round(a / fps, 2) for a, _, _ in dropped], "max_per_second": max_per_s}))


if __name__ == "__main__":
    main()
