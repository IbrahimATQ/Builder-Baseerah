#!/usr/bin/env python3
"""Give a stock clip an even cadence again.

Some stock clips were conformed to 24 fps by picking the nearest frame of a faster original, so the
action advances in uneven steps (1, 2, 1, 2 ... or 1, 2, 1, 1, 2 ...): on a hard-edged slow subject
that is a stutter. Others carry a repeated frame every few frames. This tool
  * measures the frame-to-frame motion of a stretch of the clip and finds the step pattern and its phase
  * writes the frames back with their TRUE spacing and lets ffmpeg's motion-compensated interpolation
    (minterpolate, mci) rebuild evenly spaced frames at the clip's own frame rate
  * measures the result, so the report says whether the steps are now even
The stretch keeps its duration and speed. It is a repair for simple pictures (a silhouette, a slow pan);
look at the result before using it, and prefer --decimate N for clips that merely repeat every N-th frame
(that needs no interpolation: montage.py does it per shot with "decimate": N).

Usage: python even_cadence.py SRC.mp4 START DUR OUT.mp4 [--pattern 1,2 | 1,2,1,1,2 | auto] [--crf 12] [--check-only]
"""
from __future__ import annotations

import json
import subprocess
import sys

import numpy as np

PATTERNS = [[1, 2], [1, 2, 1, 1, 2], [1, 1, 2], [2, 3]]


def probe(src: str) -> tuple[int, int, float]:
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate",
                                   "-of", "json", src], capture_output=True, text=True, check=True).stdout)["streams"][0]
    n, d = j["r_frame_rate"].split("/")
    return int(j["width"]), int(j["height"]), float(n) / float(d)


def motion(src: str, start: float | None, dur: float | None) -> np.ndarray:
    """Mean absolute change between consecutive frames, on a small grey copy."""
    w, h, _ = probe(src)
    H = int(round(192 * h / w / 2)) * 2
    cmd = ["ffmpeg", "-v", "error"] + (["-ss", f"{start}", "-t", f"{dur}"] if start is not None else []) + \
          ["-i", src, "-vf", f"scale=192:{H},format=gray", "-f", "rawvideo", "-"]
    a = np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.uint8).reshape(-1, H, 192).astype(np.float32)
    return np.abs(np.diff(a, axis=0)).mean(axis=(1, 2))


def unevenness(d: np.ndarray) -> dict:
    out = {"frames": int(len(d) + 1), "median_step": round(float(np.median(d)), 3), "near_duplicates": int((d < 0.15 * np.median(d)).sum())}
    worst = (1, 1.0)
    for c in (2, 3, 4, 5, 6):
        ph = [float(d[k::c].mean()) for k in range(c)]
        r = max(ph) / max(min(ph), 1e-6)
        if r > worst[1]:
            worst = (c, r)
    out["worst_cycle"], out["worst_ratio"] = worst[0], round(worst[1], 2)
    return out


def fit(d: np.ndarray, pattern: list[int] | None) -> tuple[list[int], int, float]:
    """The step pattern and rotation under which motion per unit of true time is most constant."""
    best = None
    for p in ([pattern] if pattern else PATTERNS):
        for rot in range(len(p)):
            q = np.array([(p[(i + rot) % len(p)]) for i in range(len(d))], np.float32)
            v = d / q
            cv = float(v.std() / max(v.mean(), 1e-6))
            if best is None or cv < best[2]:
                best = (p, rot, cv)
    return best


def main() -> None:
    args = sys.argv[1:]
    opts = {"--pattern": "auto", "--crf": "12"}
    for k in list(opts):
        if k in args:
            i = args.index(k); opts[k] = args[i + 1]; del args[i:i + 2]
    check_only = "--check-only" in args
    args = [a for a in args if a != "--check-only"]
    src, start, dur, out = args[0], float(args[1]), float(args[2]), args[3]
    _, _, fps = probe(src)
    d = motion(src, start, dur)
    rep = {"src": src, "start": start, "dur": dur, "before": unevenness(d)}
    flat = float(d.std() / max(d.mean(), 1e-6))
    pat = None if opts["--pattern"] == "auto" else [int(x) for x in opts["--pattern"].split(",")]
    p, rot, cv = fit(d, pat)
    rep.update({"pattern": p, "rotation": rot, "cv_as_is": round(flat, 3), "cv_with_pattern": round(cv, 3)})
    if check_only or cv > 0.8 * flat:
        rep["action"] = "none" if not check_only else "check only"
        print(json.dumps(rep, ensure_ascii=False))
        return
    # true time of frame n, in units; the mean step of the pattern is one frame period
    L, S = len(p), sum(p)
    seq = [p[(i + rot) % L] for i in range(L)]
    cum = [0] + list(np.cumsum(seq))  # units at frame index 0..L within one cycle
    # ffmpeg expression: floor(N/L)*S + cum[mod(N,L)]
    terms = "+".join(f"eq(mod(N,{L}),{k})*{int(cum[k])}" for k in range(1, L))
    unit = L / S / fps  # seconds per unit
    expr = f"(floor(N/{L})*{S}+{terms})*{unit:.9f}/TB"
    vf = f"setpts='{expr}',minterpolate=fps={fps:.6f}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1:scd=none"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start}", "-t", f"{dur}", "-i", src, "-an", "-vf", vf, "-c:v", "libx264", "-preset", "medium",
                    "-crf", opts["--crf"], "-pix_fmt", "yuv420p", out], check=True)
    rep["after"] = unevenness(motion(out, None, None))
    rep["out"] = out
    print(json.dumps(rep, ensure_ascii=False))


if __name__ == "__main__":
    main()
