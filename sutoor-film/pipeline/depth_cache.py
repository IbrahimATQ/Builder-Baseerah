#!/usr/bin/env python3
"""Per-frame depth of a finished picture, for setting type INTO a shot (behind what is near the lens).

Model: Depth Anything V2 Small (Apache-2.0, safetensors weights) through transformers, on CPU.
Depth is relative, so each time range is normalised over its own frames (2nd..98th percentile) and
smoothed over time; 255 = nearest. One .npy per range, at a quarter of the picture's size or less.

Usage: python depth_cache.py PICTURE.mp4 OUT_DIR T0:T1 [T0:T1 ...] [--long 518] [--ema 0.6]
       (times in film seconds; OUT_DIR/depth_<f0>_<f1>.npy holds frames f0..f1-1, uint8, HxW)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import cv2
import numpy as np
import torch
from transformers import AutoModelForDepthEstimation

MODEL = os.environ.get("DEPTH_MODEL_DIR", "/home/user/film/v4/models/dav2s")  # depth-anything/Depth-Anything-V2-Small-hf, fetched by plain HTTPS


def probe(src: str) -> tuple[int, int, float]:
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate",
                                   "-of", "json", src], capture_output=True, text=True, check=True).stdout)["streams"][0]
    n, d = j["r_frame_rate"].split("/")
    return int(j["width"]), int(j["height"]), float(n) / float(d)


def main() -> None:
    args = sys.argv[1:]
    opts = {"--long": 518.0, "--ema": 0.6}
    for k in list(opts):
        if k in args:
            i = args.index(k); opts[k] = float(args[i + 1]); del args[i:i + 2]
    pic, out_dir, ranges = args[0], args[1], args[2:]
    os.makedirs(out_dir, exist_ok=True)
    W, H, fps = probe(pic)
    long_side = int(opts["--long"])
    s = long_side / max(W, H)
    w, h = int(round(W * s / 14)) * 14, int(round(H * s / 14)) * 14  # the ViT patch grid
    torch.set_num_threads(max(1, (os.cpu_count() or 4) - 1))
    model = AutoModelForDepthEstimation.from_pretrained(MODEL).eval()
    mean = np.array([0.485, 0.456, 0.406], np.float32)[None, None]  # the model's own preprocessing (ImageNet statistics)
    std = np.array([0.229, 0.224, 0.225], np.float32)[None, None]
    for rg in ranges:
        t0, t1 = [float(x) for x in rg.split(":")]
        f0, f1 = int(round(t0 * fps)), int(round(t1 * fps))
        p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{f0 / fps:.5f}", "-i", pic, "-frames:v", str(f1 - f0),
                              "-vf", f"scale={w}:{h}:flags=area,format=rgb24", "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
        raw_d = []
        for _ in range(f1 - f0):
            buf = p.stdout.read(w * h * 3)
            if len(buf) < w * h * 3:
                break
            im = np.frombuffer(buf, np.uint8).reshape(h, w, 3).astype(np.float32) / 255.0
            x = torch.from_numpy(((im - mean) / std).transpose(2, 0, 1)[None].copy())
            with torch.no_grad():
                d = model(pixel_values=x).predicted_depth[0].numpy()
            raw_d.append(d.astype(np.float32))
        p.stdout.close(); p.wait()
        if not raw_d:
            continue
        D = np.stack(raw_d)
        lo, hi = np.percentile(D, 2), np.percentile(D, 98)
        D = np.clip((D - lo) / max(hi - lo, 1e-6), 0, 1)
        a = float(opts["--ema"])
        if a > 0 and len(D) > 1:  # two-way smoothing over time: no lag, no flicker
            fwd = D.copy()
            for i in range(1, len(D)):
                fwd[i] = a * fwd[i - 1] + (1 - a) * D[i]
            bwd = D.copy()
            for i in range(len(D) - 2, -1, -1):
                bwd[i] = a * bwd[i + 1] + (1 - a) * D[i]
            D = 0.5 * (fwd + bwd)
        out = os.path.join(out_dir, f"depth_{f0}_{f0 + len(D)}.npy")
        np.save(out, (D * 255 + 0.5).astype(np.uint8))
        print(json.dumps({"range": [f0, f0 + len(D)], "shape": list(D.shape[1:]), "file": out}), flush=True)


if __name__ == "__main__":
    main()
