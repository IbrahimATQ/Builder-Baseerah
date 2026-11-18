#!/usr/bin/env python3
"""Re-time a real plate with a piecewise-linear time map, blending neighbouring source frames.

Used where a burn must meet a real event in the footage on a given word or beat, e.g. Burn III's
sheet waits on the boulder in slow motion until the sea's own surge arrives at the quench.

Usage: python plate_remap.py SRC OUT --size 1620x2880 --map "0:0,5.35:2.2,6.6:3.15,7.45:3.4"
                              [--rotate 90] [--hflip] [--fps 24]
  --map  pairs of output_seconds:source_seconds; the output lasts as long as the last pair
"""
from __future__ import annotations

import argparse
import subprocess

import numpy as np


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--size", default="1620x2880")
    ap.add_argument("--map", required=True)
    ap.add_argument("--rotate", type=int, default=0)
    ap.add_argument("--hflip", action="store_true")
    ap.add_argument("--fps", type=int, default=24)
    a = ap.parse_args()
    W, H = (int(v) for v in a.size.split("x"))
    km = np.array([[float(x) for x in p.split(":")] for p in a.map.split(",")])
    src_fps = eval(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=r_frame_rate",
                                   "-of", "csv=p=0", a.src], capture_output=True, text=True).stdout.strip())
    n_out = int(round(km[-1, 0] * a.fps))
    p_of = np.interp(np.arange(n_out) / a.fps, km[:, 0], km[:, 1])
    need = int(np.ceil(p_of.max() * src_fps)) + 2
    vf = []
    if a.rotate == 90:
        vf.append("transpose=1")
    elif a.rotate == 270:
        vf.append("transpose=2")
    if a.hflip:
        vf.append("hflip")
    vf.append(f"scale={W}:{H}:flags=lanczos,format=rgb24")
    rd = subprocess.Popen(["ffmpeg", "-v", "error", "-i", a.src, "-frames:v", str(need), "-vf", ",".join(vf), "-f", "rawvideo", "-"],
                          stdout=subprocess.PIPE)
    frames = []
    while len(frames) < need:
        raw = rd.stdout.read(W * H * 3)
        if len(raw) < W * H * 3:
            break
        frames.append(np.frombuffer(raw, np.uint8).reshape(H, W, 3))
    rd.wait()
    wr = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(a.fps), "-i", "-",
                          "-c:v", "libx264", "-preset", "medium", "-crf", "12", "-pix_fmt", "yuv420p", a.out], stdin=subprocess.PIPE)
    for p in p_of:
        x = p * src_fps
        i = min(int(np.floor(x)), len(frames) - 1)
        j = min(i + 1, len(frames) - 1)
        f = x - np.floor(x)
        im = frames[i] if f < 0.02 or i == j else (frames[i].astype(np.float32) * (1 - f) + frames[j].astype(np.float32) * f + 0.5).astype(np.uint8)
        wr.stdin.write(im.tobytes())
    wr.stdin.close()
    wr.wait()
    print(f"{a.out}: {n_out} frames from source {p_of[0]:.2f}-{p_of[-1]:.2f} s")


if __name__ == "__main__":
    main()
