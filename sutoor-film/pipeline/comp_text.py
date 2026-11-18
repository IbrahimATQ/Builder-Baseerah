#!/usr/bin/env python3
"""Set the letters INTO the picture (Blades edition), instead of laying them over it.

Inputs: the cut picture (montage.py), a transparent text pass (Remotion BladesText, PNG sequence
"element-<frame>.png"), per-frame depth where needed (depth_cache.py), and a comp plan that says,
per time range, how the type lives in that shot:

  {"fps": 24,
   "default": {"mode": "light", "soft": 0.7, "shade": 0.5, "texture": 0.5, "glow": 0.3, "wrap": 0.25},
   "ranges": [{"from": t0, "to": t1,
               "mode": "light" | "ink",          # letters as light (dark plates) or as ink (bright surfaces)
               "depth": 0.45,                    # the plane the letters stand on (0 far .. 1 near)
               "occlude": {"type": "depth", "near": 0.55, "soft": 0.10, "gain": 1.0}
                        | {"type": "luma", "lo": 0.35, "hi": 0.6, "invert": false},
               "track": {"layer": "far" | "all"},    # the letters ride the shot's own camera motion
               "dof": {"focus": [[t, depth], ...], "strength": 26, "zone": 0.05, "max": 22},
               "atmo": {"src": clip, "in": s, "depth": 0.5, "soft": 0.12, "gain": 0.8, "tint": [r, g, b]},
               "soft": px blur at 4K, "shade": 0..1, "texture": 0..1, "glow": 0..1, "wrap": 0..1, "pool": 0..1,
               "lit": {"lo": .03, "hi": .14, "floor": 0.0, "global": false}, "level": 1.0, "ink_rgb": [20, 14, 10],
               "reveal": {"src": clip, "in": s, "at": film_t, "dur": s, "lo": .1, "hi": .5, "invert": false}}]}

  occlude: what is nearer than the letters hides them (depth 1 = nearest), so a line can stand behind a
           horse's head or a rider; edges are refined on the picture itself. With "depth" set and no
           "occlude", everything nearer than the letters' plane hides them.
  track:   global camera motion measured on the picture (features + RANSAC) moves the letters with the
           world, so they sit in the space and not on the glass.
  dof:     a lens for the shot: blur grows with distance from the focus plane, and the focus plane can
           travel (a rack focus). Letters on their plane go soft and sharp with everything else there.
  atmo:    a REAL smoke or mist clip hung at a depth: nearer things stand in front of it.
  shade / texture: the letters take the brightness and the grain of what is under them.
  pool:    a soft darkening pooled under the line ONLY where the plate there is bright (measured),
           so the line stays readable over a white blaze or a sky without a caption box.
  lit:     the letters are only as visible as the light around them (a match, a candle, a fire brings
           the line out of the dark and takes it back). "floor" is what they keep when the light has gone.
  reveal:  the luma of a REAL clip (ink blooming in water) lets the line appear.

Usage: python comp_text.py PICTURE.mp4 TEXT_DIR COMP.json OUT.mp4 [--from T] [--to T] [--depth DIR] [--pic-start T]
       (--pic-start: film time of the picture file's first frame, when the picture is only a section of the film;
        --from/--to are film times; depth files are indexed by the picture file's own frames)
"""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)


def probe(src: str) -> tuple[int, int, float, int]:
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
                                   "stream=width,height,r_frame_rate,nb_read_packets", "-of", "json", src],
                                  capture_output=True, text=True, check=True).stdout)["streams"][0]
    n, d = j["r_frame_rate"].split("/")
    return int(j["width"]), int(j["height"]), float(n) / float(d), int(j["nb_read_packets"])


def smoothstep(x, lo: float, hi: float):
    t = np.clip((x - lo) / max(hi - lo, 1e-6), 0, 1)
    return t * t * (3 - 2 * t)


def keyed(keys, t: float, default: float) -> float:
    if not keys:
        return default
    if isinstance(keys, (int, float)):
        return float(keys)
    ks = sorted(keys)
    if t <= ks[0][0]:
        return float(ks[0][1])
    if t >= ks[-1][0]:
        return float(ks[-1][1])
    j = max(i for i in range(len(ks)) if ks[i][0] <= t)
    u = (t - ks[j][0]) / max(ks[j + 1][0] - ks[j][0], 1e-6)
    u = u * u * (3 - 2 * u)
    return float(ks[j][1] + (ks[j + 1][1] - ks[j][1]) * u)


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

    def at(self, pf: int) -> np.ndarray | None:
        for f0, f1, f in self.files:
            if f0 <= pf < f1:
                if self.cur is None or self.cur[0] != f:
                    self.cur = (f, np.load(f, mmap_mode="r"))
                return np.asarray(self.cur[1][pf - f0], np.float32) / 255.0
        return None


class Tracker:
    """Cumulative similarity transform of the plate since the range began (features + RANSAC)."""

    def __init__(self) -> None:
        self.s = 4
        self.prev = None
        self.A = np.eye(3, dtype=np.float64)

    def update(self, gray_small: np.ndarray, mask: np.ndarray | None) -> np.ndarray:
        if self.prev is not None:
            p0 = cv2.goodFeaturesToTrack(self.prev, maxCorners=500, qualityLevel=0.01, minDistance=7, mask=mask)
            if p0 is None or len(p0) < 40:  # a soft, empty background: use the whole frame instead
                p0 = cv2.goodFeaturesToTrack(self.prev, maxCorners=500, qualityLevel=0.01, minDistance=7)
            if p0 is not None and len(p0) >= 20:
                p1, st, _ = cv2.calcOpticalFlowPyrLK(self.prev, gray_small, p0, None, winSize=(21, 21), maxLevel=3)
                ok = st.ravel() == 1
                if ok.sum() >= 16:
                    M, inl = cv2.estimateAffinePartial2D(p0[ok], p1[ok], method=cv2.RANSAC, ransacReprojThreshold=1.5)
                    if M is not None and inl is not None and inl.sum() >= max(12, 0.3 * ok.sum()):
                        sc = float(np.hypot(M[0, 0], M[1, 0]))
                        rot = abs(float(np.degrees(np.arctan2(M[1, 0], M[0, 0]))))
                        h_, w_ = gray_small.shape
                        # one frame of real camera motion is small; anything else is a bad fit and is skipped
                        if abs(sc - 1) < 0.04 and rot < 1.2 and abs(M[0, 2] + (sc - 1) * w_ / 2) < 0.05 * w_ and abs(M[1, 2] + (sc - 1) * h_ / 2) < 0.05 * h_:
                            Sm = np.eye(3)
                            Sm[:2] = M
                            Sm[0, 2] *= self.s; Sm[1, 2] *= self.s  # translation back to full-res pixels
                            self.A = Sm @ self.A
        self.prev = gray_small
        return self.A


def depth_full(d: np.ndarray, P8: np.ndarray, W: int, H: int) -> np.ndarray:
    """Depth at picture size, its edges pulled onto the picture's own edges (guided, at half size)."""
    hw, hh = W // 2, H // 2
    g = cv2.cvtColor(cv2.resize(P8, (hw, hh), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    dd = cv2.resize(d, (hw, hh), interpolation=cv2.INTER_LINEAR)
    dd = np.clip(guided(g, dd, max(2, hw // 180), 6e-4), 0, 1)
    return cv2.resize(dd, (W, H), interpolation=cv2.INTER_LINEAR)


def lens_blur(P: np.ndarray, r: np.ndarray, S: float) -> np.ndarray:
    """Per-pixel blur of radius r (sigma px) from a small stack of blurs; large sigmas at reduced size."""
    sig = [0.0, 2.5 * S, 6.0 * S, 12.0 * S, 24.0 * S]
    H, W = P.shape[:2]
    out = P
    prev = 0.0
    for s_ in sig[1:]:
        if float(r.max()) <= prev:
            break
        f = 1 if s_ < 4 else (2 if s_ < 10 else 4)
        if f == 1:
            b = cv2.GaussianBlur(P, (0, 0), s_)
        else:
            sm = cv2.resize(P, (W // f, H // f), interpolation=cv2.INTER_AREA)
            b = cv2.resize(cv2.GaussianBlur(sm, (0, 0), s_ / f), (W, H), interpolation=cv2.INTER_LINEAR)
        w = np.clip((r - prev) / (s_ - prev), 0, 1)[..., None]
        out = out * (1 - w) + b * w
        prev = s_
    return out


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
    text_index: dict[int, str] = {}  # film frame -> PNG (Remotion zero-pads the frame number to the sequence's width)
    for f in glob.glob(os.path.join(text_dir, "element-*.png")):
        m = re.search(r"element-(\d+)\.png$", f)
        if m:
            text_index[int(m.group(1))] = f
    trackers: dict[int, Tracker] = {}
    clips: dict[tuple[int, str], object] = {}
    stats = {"frames": 0, "with_text": 0, "occluded_frames": 0, "tracked_frames": 0, "lens_frames": 0, "atmo_frames": 0}

    def clip_for(ri: int, key: str, spec: dict, gray: bool):
        from montage import Clip
        if (ri, key) not in clips:
            for k_ in [k_ for k_ in clips if k_[0] != ri]:
                clips.pop(k_).close()
            clips[(ri, key)] = Clip(spec["src"], float(spec.get("in", 0.0)), W, H, bool(spec.get("flip")), gray=gray)
        return clips[(ri, key)]

    def atmosphere(img8: np.ndarray, cfg: dict, ri: int, t: float, D: np.ndarray | None) -> np.ndarray:
        at = cfg["atmo"]
        c = clip_for(ri, "atmo", at, gray=False)
        sm = c.at(float(at.get("in", 0.0)) + (t - cfg["from"]) * float(at.get("speed", 1.0))).astype(np.float32) * (1 / 255.0)
        blk = float(at.get("black", 0.03))
        sm = np.clip((sm - blk) / (1 - blk), 0, 1) * float(at.get("gain", 0.8))
        if at.get("tint"):
            sm = sm * np.array(at["tint"], np.float32)
        fd = float(at.get("fade", 0.3))
        sm = sm * max(0.0, min(1.0, (t - cfg["from"]) / max(fd, 1e-3), (cfg["to"] - t) / max(fd, 1e-3)))
        if D is not None:  # what is nearer than the smoke stands in front of it
            dp, sf = float(at.get("depth", 0.5)), float(at.get("soft", 0.12))
            sm = sm * (1 - smoothstep(D, dp - sf / 2, dp + sf / 2))[..., None]
        base = img8.astype(np.float32) * (1 / 255.0)
        stats["atmo_frames"] += 1
        return ((1 - (1 - base) * (1 - np.clip(sm, 0, 1))) * 255 + 0.5).astype(np.uint8)

    for pf in range(f0, f1):
        buf = dec.stdout.read(W * H * 3)
        if len(buf) < W * H * 3:
            break
        fi = pf + off  # film frame
        t = fi / fps
        P8 = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        ri = next((i for i, r in enumerate(ranges) if r["from"] <= t < r["to"]), None)
        cfg = {**dflt, **(ranges[ri] if ri is not None else {})}
        stats["frames"] += 1
        d_small = depth.at(pf) if ri is not None else None
        text_depth = cfg.get("depth")
        occ = cfg.get("occlude")
        if occ is None and text_depth is not None:
            occ = {"type": "depth", "near": float(text_depth) + 0.06, "soft": 0.10}
        # the tracker must see every frame of its range, text or not
        A = None
        if ri is not None and cfg.get("track"):
            small = cv2.cvtColor(cv2.resize(P8, (W // 4, H // 4), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY)
            mask = None
            if isinstance(cfg["track"], dict) and cfg["track"].get("layer", "far") == "far" and d_small is not None and occ:
                mask = (cv2.resize(d_small, (W // 4, H // 4)) < float(occ.get("near", 0.5))).astype(np.uint8) * 255
            if ri not in trackers:
                trackers = {ri: Tracker()}
            A = trackers[ri].update(small, mask)
            stats["tracked_frames"] += 1
        # ---- the shot's lens and air (whole frame)
        D = None
        focus = None
        dof = cfg.get("dof")
        atmo = cfg.get("atmo")
        if d_small is not None and (dof or atmo):
            D = depth_full(d_small, P8, W, H)
        if dof and D is not None:
            focus = keyed(dof.get("focus"), t, 0.5)
            r = np.clip(np.abs(D - focus) - float(dof.get("zone", 0.05)), 0, None) * float(dof.get("strength", 26)) * S
            r = np.minimum(r, float(dof.get("max", 22)) * S)
            if float(r.max()) > 0.3:
                P8 = (np.clip(lens_blur(P8.astype(np.float32), r, S), 0, 255) + 0.5).astype(np.uint8)
                stats["lens_frames"] += 1
        atmo_first = bool(atmo) and (text_depth is None or float(atmo.get("depth", 0.5)) <= float(text_depth))
        if atmo and atmo_first:
            P8 = atmosphere(P8, cfg, ri, t, D)
        tp = text_index.get(fi)
        T = cv2.imread(tp, cv2.IMREAD_UNCHANGED) if tp else None
        if T is not None and T.ndim == 3 and T.shape[2] == 4 and T[..., 3].any():
            if T.shape[0] != H or T.shape[1] != W:
                T = cv2.resize(T, (W, H), interpolation=cv2.INTER_AREA)
            if A is not None:
                T = cv2.warpAffine(T, A[:2].astype(np.float32), (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            ys, xs = np.nonzero(T[..., 3] > 2)
        else:
            xs = ys = np.zeros(0, int)
        if len(xs):
            stats["with_text"] += 1
            pad = int(220 * S)
            x0, x1 = max(0, xs.min() - pad), min(W, xs.max() + pad + 1)
            y0, y1 = max(0, ys.min() - pad), min(H, ys.max() + pad + 1)
            Pc = P8[y0:y1, x0:x1].astype(np.float32) * (1 / 255.0)
            Tc = T[y0:y1, x0:x1].astype(np.float32) * (1 / 255.0)
            a = Tc[..., 3]
            C = Tc[..., 2::-1]  # BGR -> RGB
            soft = float(cfg["soft"]) * S
            if dof and focus is not None and text_depth is not None:  # the letters share the lens
                soft += min(float(dof.get("max", 22)), max(0.0, abs(float(text_depth) - focus) - float(dof.get("zone", 0.05))) * float(dof.get("strength", 26))) * S
            if soft > 0.05:
                a_s = cv2.GaussianBlur(a, (0, 0), soft)
                C = cv2.GaussianBlur(C * a[..., None], (0, 0), soft) / np.maximum(a_s[..., None], 1e-4)
                a = a_s
            lum = Pc @ LUMA
            # ---- what is nearer than the letters hides them
            if occ:
                fg = None
                if occ.get("type", "depth") == "depth":
                    if d_small is not None:
                        dc = (D[y0:y1, x0:x1] if D is not None else cv2.resize(d_small, (W, H), interpolation=cv2.INTER_LINEAR)[y0:y1, x0:x1])
                        near, sf = float(occ.get("near", 0.55)), float(occ.get("soft", 0.10))
                        fg = smoothstep(dc, near - sf / 2, near + sf / 2).astype(np.float32)
                        if D is None:
                            fg = np.clip(guided(lum, fg, max(2, int(10 * S)), 4e-4), 0, 1)
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
                p = (t - float(rv["at"])) / max(float(rv["dur"]), 1e-3)
                if p < 1:
                    c = clip_for(ri, "reveal", rv, gray=True)
                    m = c.at(float(rv.get("in", 0.0)) + max(0.0, p) * float(rv.get("span", rv["dur"])))[y0:y1, x0:x1, 0].astype(np.float32) / 255.0
                    m = smoothstep(m, float(rv.get("lo", 0.1)), float(rv.get("hi", 0.5)))
                    if rv.get("invert"):
                        m = 1 - m
                    a = a * np.clip(m + max(0.0, (p - 0.7) / 0.3), 0, 1) * float(p >= 0)
            a = np.clip(a * float(cfg["level"]), 0, 1)
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
                    src_l = float(P8[::8, ::8].mean()) / 255.0 if lit.get("global") else big  # the whole frame's light, or the light just there
                    vis = smoothstep(src_l, float(lit.get("lo", 0.03)), float(lit.get("hi", 0.14)))
                    fl = float(lit.get("floor", 0.0))  # the least the letters keep when the light has gone (they stay readable in the dark)
                    a = a * (fl + (1 - fl) * vis)
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
            P8 = res
        if atmo and not atmo_first:
            P8 = atmosphere(P8, cfg, ri, t, D)
        enc.stdin.write(P8.tobytes())
    for c in clips.values():
        c.close()
    dec.stdout.close(); dec.wait()
    enc.stdin.close(); enc.wait()
    print(json.dumps({"out": out_p, **stats}))


if __name__ == "__main__":
    main()
