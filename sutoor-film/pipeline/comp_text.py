#!/usr/bin/env python3
"""Set the letters INTO the picture (Blades edition), instead of laying them over it.

Inputs: the cut picture (montage.py), a transparent text pass (Remotion BladesText, PNG sequence
"element-<frame>.png"), and a comp plan that says, per time range, how the type lives in that shot:

  {"fps": 24,
   "default": {"mode": "light", "soft": 0.7, "shade": 0.5, "texture": 0.5, "glow": 0.3, "wrap": 0.25},
   "ranges": [{"from": t0, "to": t1,
               "mode": "light" | "ink",          # letters as light (dark plates) or as ink (bright surfaces)
               "occlude": {"type": "depth", "near": 0.55, "soft": 0.10, "gain": 1.0}
                        | {"type": "luma", "lo": 0.35, "hi": 0.6, "invert": false},
               "track": {"layer": "far" | "all"},    # the letters ride the shot's own camera motion
               "soft": px blur at 4K, "shade": 0..1, "texture": 0..1, "glow": 0..1, "wrap": 0..1,
               "level": 1.0, "ink_rgb": [20, 14, 10],
               "reveal": {"src": clip, "in": s, "at": film_t, "dur": s, "lo": .1, "hi": .5, "invert": false}}]}

  occlude: what is nearer than the letters hides them (depth from depth_cache.py; 1 = nearest), so a
           line can stand behind a horse's head or a rider; edges are refined on the picture itself.
  track:   global camera motion measured on the picture (features + RANSAC) moves the letters with the
           world, so they sit in the space and not on the glass.
  shade / texture: the letters take the brightness and the grain of what is under them.
  pool:    0..1, a soft darkening pooled under the line ONLY where the plate there is bright (measured),
           so the line stays readable over a white blaze or a sky without a caption box.
  lit:     {"lo": .03, "hi": .14}: the letters are only as visible as the light around them (a match, a
           candle, a fire brings the line out of the dark and takes it back).
  reveal:  the luma of a REAL clip (ink blooming in water) lets the line appear.

Usage: python comp_text.py PICTURE.mp4 TEXT_DIR COMP.json OUT.mp4 [--from T] [--to T] [--depth DIR] [--pic-start T]
       (--pic-start: film time of the picture file's first frame, when the picture is only a section of the film;
        --from/--to are film times; depth files are indexed by the picture file's own frames)
"""
from __future__ import annotations

import glob
import json
import math
import os
import re
import subprocess
import sys

import cv2
import numpy as np

LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)


def probe(src: str) -> tuple[int, int, float, int]:
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
                                   "stream=width,height,r_frame_rate,nb_read_packets", "-of", "json", src],
                                  capture_output=True, text=True, check=True).stdout)["streams"][0]
    n, d = j["r_frame_rate"].split("/")
    return int(j["width"]), int(j["height"]), float(n) / float(d), int(j["nb_read_packets"])


def smoothstep(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    t = np.clip((x - lo) / max(hi - lo, 1e-6), 0, 1)
    return t * t * (3 - 2 * t)


def guided(guide: np.ndarray, src: np.ndarray, r: int, eps: float) -> np.ndarray:
    """Guided filter (He et al.): src follows the edges of guide. Both float32, single channel."""
    k = (2 * r + 1, 2 * r + 1)
    mI, mp = cv2.blur(guide, k), cv2.blur(src, k)
    cov = cv2.blur(guide * src, k) - mI * mp
    var = cv2.blur(guide * guide, k) - mI * mI
    a = cov / (var + eps)
    b = mp - a * mI
    return cv2.blur(a, k) * guide + cv2.blur(b, k)


class Depth:
    def __init__(self, d: str | None):
        self.files = []
        for f in glob.glob(os.path.join(d, "depth_*_*.npy")) if d else []:
            m = re.search(r"depth_(\d+)_(\d+)\.npy$", f)
            self.files.append((int(m.group(1)), int(m.group(2)), f))
        self.cur = None

    def at(self, fi: int) -> np.ndarray | None:
        for f0, f1, f in self.files:
            if f0 <= fi < f1:
                if self.cur is None or self.cur[0] != f:
                    self.cur = (f, np.load(f, mmap_mode="r"))
                return np.asarray(self.cur[1][fi - f0], np.float32) / 255.0
        return None


class Tracker:
    """Cumulative similarity transform of the plate since the range began (features + RANSAC)."""

    def __init__(self, W: int, H: int):
        self.s = 4
        self.W, self.H = W, H
        self.prev = None
        self.A = np.eye(3, dtype=np.float64)

    def update(self, gray_small: np.ndarray, mask: np.ndarray | None) -> np.ndarray:
        if self.prev is not None:
            p0 = cv2.goodFeaturesToTrack(self.prev, maxCorners=500, qualityLevel=0.01, minDistance=7, mask=mask)
            if p0 is not None and len(p0) >= 12:
                p1, st, _ = cv2.calcOpticalFlowPyrLK(self.prev, gray_small, p0, None, winSize=(21, 21), maxLevel=3)
                ok = st.ravel() == 1
                if ok.sum() >= 10:
                    M, inl = cv2.estimateAffinePartial2D(p0[ok], p1[ok], method=cv2.RANSAC, ransacReprojThreshold=1.5)
                    if M is not None and inl is not None and inl.sum() >= 8:
                        S = np.eye(3)
                        S[:2] = M
                        S[0, 2] *= self.s; S[1, 2] *= self.s  # translation back to full-res pixels
                        self.A = S @ self.A
        self.prev = gray_small
        return self.A


def main() -> None:
    args = sys.argv[1:]
    opts = {"--from": None, "--to": None, "--pic-start": 0.0}
    depth_dir = None
    if "--depth" in args:
        i = args.index("--depth"); depth_dir = args[i + 1]; del args[i:i + 2]
    for k in list(opts):
        if k in args:
            i = args.index(k); opts[k] = float(args[i + 1]); del args[i:i + 2]
    pic, text_dir, comp_p, out_p = args
    comp = json.load(open(comp_p, encoding="utf-8"))
    W, H, fps, n_pic = probe(pic)
    S = W / 2160.0  # all pixel radii below are given for a 2160-wide frame
    off = int(round(opts["--pic-start"] * fps))  # film frame of the picture file's first frame
    f0 = max(0, int(round((opts["--from"] if opts["--from"] is not None else opts["--pic-start"]) * fps)) - off)
    f1 = min(n_pic, int(round(opts["--to"] * fps)) - off) if opts["--to"] is not None else n_pic
    dflt = {"mode": "light", "soft": 0.7, "shade": 0.5, "texture": 0.5, "glow": 0.3, "wrap": 0.25, "level": 1.0, **comp.get("default", {})}
    ranges = comp.get("ranges", [])
    depth = Depth(depth_dir)
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{f0 / fps:.5f}", "-i", pic, "-frames:v", str(f1 - f0), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE, bufsize=W * H * 3 * 2)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
                            "-vf", "scale=in_range=pc:out_range=tv:out_color_matrix=bt709",
                            "-c:v", "libx264", "-preset", "medium", "-crf", "12", "-pix_fmt", "yuv420p", "-color_range", "tv",
                            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-movflags", "+faststart", out_p], stdin=subprocess.PIPE)
    trackers: dict[int, Tracker] = {}
    reveals: dict[int, object] = {}
    stats = {"frames": 0, "with_text": 0, "occluded_frames": 0, "tracked_frames": 0}
    for pf in range(f0, f1):
        buf = dec.stdout.read(W * H * 3)
        if len(buf) < W * H * 3:
            break
        fi = pf + off  # film frame
        t = fi / fps
        P8 = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        ri = next((i for i, r in enumerate(ranges) if r["from"] <= t < r["to"]), None)
        cfg = {**dflt, **(ranges[ri] if ri is not None else {})}
        # the tracker must see every frame of its range, text or not
        A = None
        if ri is not None and cfg.get("track"):
            small = cv2.cvtColor(cv2.resize(P8, (W // 4, H // 4), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY)
            mask = None
            if isinstance(cfg["track"], dict) and cfg["track"].get("layer", "far") == "far":
                d = depth.at(pf)
                if d is not None:
                    occ = cfg.get("occlude", {})
                    mask = (cv2.resize(d, (W // 4, H // 4)) < float(occ.get("near", 0.5))).astype(np.uint8) * 255
            if ri not in trackers:
                trackers = {ri: Tracker(W, H)}
            A = trackers[ri].update(small, mask)
            stats["tracked_frames"] += 1
        tp = os.path.join(text_dir, f"element-{fi}.png")
        T = cv2.imread(tp, cv2.IMREAD_UNCHANGED) if os.path.exists(tp) else None
        stats["frames"] += 1
        if T is None or T.shape[2] < 4 or not T[..., 3].any():
            enc.stdin.write(buf)
            continue
        if T.shape[0] != H or T.shape[1] != W:
            T = cv2.resize(T, (W, H), interpolation=cv2.INTER_AREA)
        if A is not None:
            T = cv2.warpAffine(T, A[:2].astype(np.float32), (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        ys, xs = np.nonzero(T[..., 3] > 2)
        if len(xs) == 0:
            enc.stdin.write(buf)
            continue
        stats["with_text"] += 1
        pad = int(220 * S)
        x0, x1 = max(0, xs.min() - pad), min(W, xs.max() + pad + 1)
        y0, y1 = max(0, ys.min() - pad), min(H, ys.max() + pad + 1)
        Pc = P8[y0:y1, x0:x1].astype(np.float32) * (1 / 255.0)
        Tc = T[y0:y1, x0:x1].astype(np.float32) * (1 / 255.0)
        a = Tc[..., 3]
        C = Tc[..., 2::-1]  # BGR -> RGB
        soft = float(cfg["soft"]) * S
        if soft > 0.05:
            a = cv2.GaussianBlur(a, (0, 0), soft)
            C = cv2.GaussianBlur(C * Tc[..., 3:4], (0, 0), soft) / np.maximum(a[..., None], 1e-4)
        lum = Pc @ LUMA
        # ---- what is nearer than the letters hides them
        occ = cfg.get("occlude")
        if occ:
            if occ.get("type", "depth") == "depth":
                d = depth.at(pf)
                fg = None
                if d is not None:
                    dc = cv2.resize(d, (W, H), interpolation=cv2.INTER_LINEAR)[y0:y1, x0:x1]
                    near, sf = float(occ.get("near", 0.55)), float(occ.get("soft", 0.10))
                    fg = smoothstep(dc, near - sf / 2, near + sf / 2)
                    fg = np.clip(guided(lum, fg.astype(np.float32), max(2, int(10 * S)), 4e-4), 0, 1)
            else:
                fg = smoothstep(lum, float(occ.get("lo", 0.35)), float(occ.get("hi", 0.6)))
                if occ.get("invert"):
                    fg = 1 - fg
            if fg is not None:
                a = a * (1 - float(occ.get("gain", 1.0)) * fg)
                stats["occluded_frames"] += 1
        # ---- a real clip lets the line appear (ink in water)
        rv = cfg.get("reveal")
        if rv and ri is not None:
            from montage import Clip  # late import: only when a reveal is used
            if ri not in reveals:
                reveals = {ri: Clip(rv["src"], float(rv.get("in", 0.0)), W, H, bool(rv.get("flip")), gray=True)}
            p = (t - float(rv["at"])) / max(float(rv["dur"]), 1e-3)
            if p < 1:
                m = reveals[ri].at(float(rv.get("in", 0.0)) + max(0.0, p) * float(rv.get("span", rv["dur"])))[y0:y1, x0:x1, 0].astype(np.float32) / 255.0
                m = smoothstep(m, float(rv.get("lo", 0.1)), float(rv.get("hi", 0.5)))
                if rv.get("invert"):
                    m = 1 - m
                a = a * np.clip(m + max(0.0, (p - 0.7) / 0.3), 0, 1) * float(p >= 0)
        a = np.clip(a * float(cfg["level"]), 0, 1)
        a3 = a[..., None]
        if cfg["mode"] == "ink":
            ink = np.array(cfg.get("ink_rgb", [20, 14, 10]), np.float32) / 255.0
            tex = 1 + float(cfg["texture"]) * (lum - cv2.GaussianBlur(lum, (0, 0), 5 * S)) * 3.0
            dens = np.clip(a * np.clip(tex, 0.6, 1.2), 0, 1)[..., None]
            out = Pc * (1 - dens * (1 - ink))
        else:
            big = cv2.GaussianBlur(lum, (0, 0), 70 * S)
            pool = float(cfg.get("pool", 0.0))
            if pool > 0:  # darken softly under the line where the plate is bright there
                near_a = cv2.GaussianBlur(a, (0, 0), 46 * S)
                near_a = near_a / max(float(near_a.max()), 1e-4)
                bright = smoothstep(cv2.GaussianBlur(lum, (0, 0), 30 * S), 0.30, 0.62)
                Pc = Pc * (1 - pool * 0.62 * (near_a * bright)[..., None])
                lum = Pc @ LUMA
            lit = cfg.get("lit")
            if lit:
                a = a * smoothstep(big, float(lit.get("lo", 0.03)), float(lit.get("hi", 0.14)))
                a3 = a[..., None]
            ref = float(cfg.get("shade_ref", 0.22))
            shade = np.clip(1 + float(cfg["shade"]) * (big - ref) * 1.6, 0.72, 1.22)
            tex = 1 + float(cfg["texture"]) * (lum - cv2.GaussianBlur(lum, (0, 0), 4 * S)) * 2.2
            Cc = np.clip(C * (shade * np.clip(tex, 0.75, 1.25))[..., None], 0, 1)
            out = Pc * (1 - a3) + Cc * a3
            g = float(cfg["glow"])
            if g > 0:
                src = Cc * a3
                halo = cv2.GaussianBlur(src, (0, 0), 14 * S) * 0.55 + cv2.GaussianBlur(src, (0, 0), 48 * S) * 0.45
                halo = halo * np.array([1.0, 0.86, 0.68], np.float32) * g
                out = 1 - (1 - np.clip(out, 0, 1)) * (1 - np.clip(halo, 0, 1))
            wv = float(cfg["wrap"])
            if wv > 0:  # the plate's light creeps over the letters' rims
                rim = np.clip(a - cv2.GaussianBlur(a, (0, 0), 3.0 * S) * 0.92, 0, 1)[..., None]
                out = out + wv * rim * cv2.GaussianBlur(Pc, (0, 0), 9 * S)
        res = P8.copy()
        res[y0:y1, x0:x1] = (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)
        enc.stdin.write(res.tobytes())
    dec.stdout.close(); dec.wait()
    enc.stdin.close(); enc.wait()
    print(json.dumps({"out": out_p, **stats}))


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
