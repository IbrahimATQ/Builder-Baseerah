#!/usr/bin/env python3
"""Line up two shots for a dissolve: the framing of shot B that puts its static background exactly where shot A's is.

Measures the similarity transform (scale + translation, no rotation) between a frame of A and a frame of B from
ORB features on the static parts of the picture (RANSAC rejects what moves: water, hands, walkers), then turns A's
framing (z, cx, cy of render2's warp) into B's: if a point x_A of A is x_B = s * x_A + t in B, then
z_B = z_A / s and c_B = s * c_A + t.

Usage: python align.py A.mp4 FRAME_A B.mp4 FRAME_B [zA cxA cyA]
Prints JSON: s, t (pixels of the full frame), inlier count, and B's framing.
"""
from __future__ import annotations

import json
import subprocess
import sys

import cv2
import numpy as np


def grab(path: str, k: int, W: int = 1080, H: int = 1920) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"select=eq(n\\,{k}),scale={W}:{H}", "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(H, W)


def main() -> None:
    a_p, ka, b_p, kb = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4])
    zA, cxA, cyA = (float(x) for x in sys.argv[5:8]) if len(sys.argv) >= 8 else (1.0, 0.5, 0.5)
    A, B = grab(a_p, ka), grab(b_p, kb)
    orb = cv2.ORB_create(6000)
    ka_, da = orb.detectAndCompute(A, None)
    kb_, db = orb.detectAndCompute(B, None)
    m = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(da, db)
    pa = np.float32([ka_[x.queryIdx].pt for x in m])
    pb = np.float32([kb_[x.trainIdx].pt for x in m])
    M, inl = cv2.estimateAffinePartial2D(pa, pb, method=cv2.RANSAC, ransacReprojThreshold=2.0, maxIters=5000, confidence=0.999)
    s = float(np.hypot(M[0, 0], M[1, 0]))
    rot = float(np.degrees(np.arctan2(M[1, 0], M[0, 0])))
    f = 2160 / A.shape[1]
    t = M[:, 2] * f                                  # in full-frame pixels
    cA = np.array([cxA * 2160, cyA * 3840])
    cB = s * cA + t
    out = {"s": round(s, 5), "rot_deg": round(rot, 3), "t_px": [round(float(t[0]), 1), round(float(t[1]), 1)],
           "inliers": int(inl.sum()), "matches": len(m),
           "B_framing": {"z": round(zA / s, 4), "cx": round(float(cB[0] / 2160), 4), "cy": round(float(cB[1] / 3840), 4)}}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
