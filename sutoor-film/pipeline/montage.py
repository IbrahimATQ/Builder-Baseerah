#!/usr/bin/env python3
"""Montage picture engine (the Blades edition): real footage cut fast, the way an editor would.

What it adds to build_picture.py (whose grade and look it reuses):
  * time remapping: "time": [[film_t, src_t], ...] keys with smooth interpolation, so a shot can ramp
    from slow motion into a rush and back (speed ramps)
  * a real shutter: when a shot runs fast (2.5x or more), every source frame that falls inside the output
    frame's exposure is averaged in linear light, so a rush carries motion blur instead of strobing;
    near real time the nearest source frame is shown whole (no doubled edges)
  * designed transitions centred on the cut: whip (a push with directional motion blur), zoom
    (continuous punch-through with radial blur, edges mirrored), flash (a soft warm exposure
    bloom), matte (the luma of a REAL clip, such as ink blooming in water, wipes one shot into the next),
    dissolve, dip, cut
  * a small organic handheld drift on any shot ("shake"), so stock tripod shots breathe alike
  * real overlays on top of the cut (light leaks, dust: clips shot on black, screen-blended)

Plan (JSON):
  {"fps": 24, "w": 2160, "h": 3840, "duration": 31.0, "look": {grade keys},
   "shots": [{"id", "src", "start": cut time on the film timeline (shown until the next shot's start),
              "in": s, "speed": 1.0   |   "time": [[film_t, src_t], ...],
              "shutter": 0.6, "blend": true,
              "window": {"cx": .5, "cy": .5, "fill": 1.0},
              "move": {"keys": [[film_t, zoom, cx, cy], ...]} | {"z": [a, b], "dx": [a, b], "dy": [a, b]},
              "shake": {"amp": 3.0, "rot": 0.15, "seed": 1},
              "flip": false, "rotate": 0 | 90 | 270, "grade": {overrides}, "sharpen": 0.2,
              "shock": {"at": film_t, "dur": 0.3, "amount": 0.015, "gain": 0.2}, "soften": px,
              "trans": {"type": "cut|dissolve|dip|whip|zoom|flash|matte", "dur": 0.25, ...}}],
   "overlays": [{"src", "start", "end", "in": 0, "speed": 1.0, "mode": "screen", "gain": 1.0, "fade": 0.2,
                 "fade_in": s, "fade_out": s, "flip": false, "rotate": 0, "black": 0.02, "tint": [r, g, b],
                 "mono": false, "r2g": 0.0, "soften": px}]}
A transition belongs to the incoming shot and spans [start - dur/2, start + dur/2].
  whip : "dir": "left|right|up|down" (the way the picture travels), "ease": 3.0
  zoom : "factor": 3.0, "centre": [0.5, 0.5]
  flash: "gain": 0.7, "rgb": [1.0, 0.86, 0.7]
  matte: "src": clip, "in": s, "span": seconds of the clip used, "lo": 0.1, "hi": 0.5, "invert": false

Writes OUT.mp4 (H.264, BT.709, CRF 14) and OUT.light.json (per frame: mean luminance and warmth of the
middle of the frame, and the index of the shot on screen) for the typography and for QC.

Usage: python montage.py plan.json OUT.mp4 [--scale 0.5] [--from T] [--to T] [--jobs 3]
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor

import cv2
import numpy as np
from scipy.interpolate import PchipInterpolator

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_picture import LOOK_DEFAULT, ease, grade, lerp2, probe  # noqa: E402

LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)


def smoother(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * x * (x * (6 * x - 15) + 10)


def smooth_noise(n: int, seed: int, period: float) -> np.ndarray:
    """n samples of smooth 1-D noise in -1..1 with roughly the given period (in samples)."""
    rng = np.random.default_rng(seed)
    k = max(2, int(n / max(period, 1.0)) + 3)
    pts = rng.uniform(-1, 1, k)
    xs = np.linspace(0, k - 1, n)
    i = np.floor(xs).astype(int).clip(0, k - 2)
    f = xs - i
    f = f * f * (3 - 2 * f)
    return (pts[i] * (1 - f) + pts[i + 1] * f).astype(np.float32)


# ---------------------------------------------------------------- shots

class Shot:
    def __init__(self, d: dict, start: float, end: float, out_w: int, out_h: int, fps: int, scale: float):
        self.d = d
        self.start, self.end = start, end
        self.W, self.H, self.fps_src, self.dur_src = probe(d["src"])
        self.rot = int(d.get("rotate", 0)) % 360  # 90 or 270: a top-down shot has no "up", so a landscape one can fill a vertical frame uncropped
        if self.rot in (90, 270):
            self.W, self.H = self.H, self.W
        self.out_w, self.out_h, self.fps, self.scale = out_w, out_h, fps, scale
        win = d.get("window", {})
        self.cx, self.cy, self.fill = win.get("cx", 0.5), win.get("cy", 0.5), win.get("fill", 1.0)
        aspect = out_w / out_h
        if self.W / self.H > aspect:
            self.ww0, self.wh0 = self.H * aspect, float(self.H)
        else:
            self.ww0, self.wh0 = float(self.W), self.W / aspect
        keys = d.get("time")
        if keys:
            ks = sorted(keys)
            ts, ss = [k[0] for k in ks], [k[1] for k in ks]
            self._interp = PchipInterpolator(ts, ss) if len(ks) > 2 else None
            self._ks = ks
        else:
            self._ks = None
        sh = d.get("shake")
        self._shake = None
        if sh:
            n = int((end - start + 2.0) * fps) + 8
            seed = int(sh.get("seed", 1))
            per = float(sh.get("period", 1.1)) * fps
            self._shake = (smooth_noise(n, seed, per) + 0.35 * smooth_noise(n, seed + 11, per / 3.1),
                           smooth_noise(n, seed + 23, per * 1.2) + 0.35 * smooth_noise(n, seed + 37, per / 2.7),
                           smooth_noise(n, seed + 51, per * 1.6))

    # --- time
    def src_time(self, t: float) -> float:
        if self._ks is None:
            return self.d.get("in", 0.0) + (t - self.start) * float(self.d.get("speed", 1.0))
        ks = self._ks
        if t <= ks[0][0]:
            v = (ks[1][1] - ks[0][1]) / max(ks[1][0] - ks[0][0], 1e-6) if self._interp is None else float(self._interp.derivative()(ks[0][0]))
            return ks[0][1] + (t - ks[0][0]) * v
        if t >= ks[-1][0]:
            v = (ks[-1][1] - ks[-2][1]) / max(ks[-1][0] - ks[-2][0], 1e-6) if self._interp is None else float(self._interp.derivative()(ks[-1][0]))
            return ks[-1][1] + (t - ks[-1][0]) * v
        if self._interp is None:
            a, b = ks[0], ks[1]
            return a[1] + (b[1] - a[1]) * (t - a[0]) / max(b[0] - a[0], 1e-6)
        return float(self._interp(t))

    # --- framing
    def window(self, t: float) -> tuple[float, float, float, float, float]:
        """Source window at film time t: centre x, centre y, width, height (source px) and rotation (deg)."""
        mv = self.d.get("move", {})
        keys = mv.get("keys")
        if keys:
            ks = sorted(keys)
            if t <= ks[0][0]:
                z, kx, ky = ks[0][1:4]
            elif t >= ks[-1][0]:
                z, kx, ky = ks[-1][1:4]
            else:
                j = max(i for i in range(len(ks)) if ks[i][0] <= t)
                a_, b_ = ks[j], ks[j + 1]
                u = ease((t - a_[0]) / max(b_[0] - a_[0], 1e-6))
                z, kx, ky = [a_[i] + (b_[i] - a_[i]) * u for i in (1, 2, 3)]
            z *= self.fill
            w, h = self.ww0 / z, self.wh0 / z
            cx, cy = kx * self.W, ky * self.H
        else:
            k = min(1.0, max(0.0, (t - self.start) / max(self.end - self.start, 1e-3)))
            if mv.get("ease", False):
                k = ease(k)
            z = self.fill * lerp2(mv.get("z", [1.0, 1.05]), k)
            w, h = self.ww0 / z, self.wh0 / z
            cx = self.cx * self.W + lerp2(mv.get("dx", [0, 0]), k) * w
            cy = self.cy * self.H + lerp2(mv.get("dy", [0, 0]), k) * h
        rot = 0.0
        if self._shake is not None:
            sh = self.d["shake"]
            i = int(round((t - self.start + 1.0) * self.fps))
            i = min(max(i, 0), len(self._shake[0]) - 1)
            px = float(sh.get("amp", 3.0)) * (w / 1080.0)  # amplitude given in px of a 1080-wide frame
            cx += self._shake[0][i] * px
            cy += self._shake[1][i] * px
            rot = self._shake[2][i] * float(sh.get("rot", 0.12))
        cx = min(max(cx, w / 2), self.W - w / 2)
        cy = min(max(cy, h / 2), self.H - h / 2)
        return cx, cy, w, h, rot

    def bbox(self, t0: float, t1: float) -> tuple[int, int, int, int]:
        xs, ys, xe, ye = [], [], [], []
        for t in np.linspace(t0, t1, 48):
            cx, cy, w, h, rot = self.window(t)
            pad = 6 + (abs(math.sin(math.radians(rot))) * max(w, h) * 0.6)
            xs.append(cx - w / 2 - pad); ys.append(cy - h / 2 - pad); xe.append(cx + w / 2 + pad); ye.append(cy + h / 2 + pad)
        x0, y0 = max(0, int(min(xs))), max(0, int(min(ys)))
        x1, y1 = min(self.W, int(math.ceil(max(xe)))), min(self.H, int(math.ceil(max(ye))))
        x0 -= x0 % 2; y0 -= y0 % 2
        return x0, y0, (x1 - x0) // 2 * 2, (y1 - y0) // 2 * 2


class Reader:
    """Sequential decode of one shot's crop. Serves averaged exposures over increasing source time."""

    def __init__(self, shot: Shot, t0: float, t1: float):
        self.shot = shot
        self.bx, self.by, self.bw, self.bh = shot.bbox(t0, t1)
        self.s0 = max(0.0, shot.src_time(t0) - 2.0 / shot.fps_src)
        s1 = min(shot.dur_src, shot.src_time(t1 + 1.0 / shot.fps) + 4.0 / shot.fps_src)
        self.proc = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-ss", f"{self.s0:.4f}", "-i", shot.d["src"], "-t", f"{max(s1 - self.s0, 0.2):.4f}",
             "-vf", {90: "transpose=1,", 270: "transpose=2,", 180: "hflip,vflip,"}.get(shot.rot, "") + f"crop={self.bw}:{self.bh}:{self.bx}:{self.by},format=rgb24",
             "-f", "rawvideo", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=self.bw * self.bh * 3 * 2)
        self.k = -1
        self.buf: dict[int, np.ndarray] = {}
        self.keep = 20

    def _frame(self, k: int) -> np.ndarray:
        n = self.bw * self.bh * 3
        k = max(k, 0)
        while self.k < k:
            raw = self.proc.stdout.read(n)
            if len(raw) < n:
                break
            self.k += 1
            self.buf[self.k] = np.frombuffer(raw, np.uint8).reshape(self.bh, self.bw, 3)
            for old in [i for i in self.buf if i < self.k - self.keep]:
                del self.buf[old]
        if not self.buf:
            return np.zeros((self.bh, self.bw, 3), np.uint8)
        return self.buf.get(min(k, self.k), self.buf[max(self.buf)])

    def exposure(self, s_a: float, s_b: float, rate: float = 1.0) -> np.ndarray:
        """The picture seen while the source runs from s_a to s_b (one output frame's open shutter).

        rate = source frames per output frame. Near real time (0.8..2.5) the nearest source frame is shown
        whole: mixing two neighbours doubles every moving edge. Only a real rush (>= 2.5) is integrated
        into motion blur, and only real slow motion (< 0.8) is blended. "blend": true forces the mixing
        (soft things: flames), "blend": false forbids it."""
        fa = (s_a - self.s0) * self.shot.fps_src
        fb = (s_b - self.s0) * self.shot.fps_src
        ka, kb = int(math.floor(fa + 1e-6)), int(math.floor(fb + 1e-6))
        mix = self.shot.d.get("blend")
        if mix is not True and (mix is False or 0.8 <= rate < 2.5):
            return self._frame(int(round(fa)))
        if kb - ka >= 2:  # fast: integrate the frames in between, in linear light
            ks = list(range(ka, kb + 1))
            if len(ks) > 12:
                ks = [ks[int(round(i))] for i in np.linspace(0, len(ks) - 1, 12)]
            self.keep = max(self.keep, kb - ka + 8)
            self._frame(ks[-1])
            acc = np.zeros((self.bh, self.bw, 3), np.float32)
            for k in ks:
                f = self._frame(k).astype(np.float32) * (1 / 255.0)
                acc += f * f
            return (np.sqrt(acc / len(ks)) * 255.0 + 0.5).astype(np.uint8)
        frac = fa - ka
        a = self._frame(ka)
        if frac < 0.15:
            return a
        if frac > 0.85:
            return self._frame(ka + 1)
        return cv2.addWeighted(a, 1 - frac, self._frame(ka + 1), frac, 0)

    def close(self) -> None:
        try:
            self.proc.stdout.close()
            self.proc.kill()
        except Exception:
            pass


class Clip:
    """A whole-frame helper clip (matte or overlay), decoded sequentially and fitted to the output frame."""

    def __init__(self, src: str, s0: float, W: int, H: int, flip: bool = False, gray: bool = False, rotate: int = 0):
        w, h, self.fps, self.dur = probe(src)
        self.W, self.H, self.s0 = W, H, s0
        aspect = W / H
        vf = []
        if rotate % 360 in (90, 270):
            vf.append("transpose=1" if rotate % 360 == 90 else "transpose=2")
            w, h = h, w
        if w / h > aspect:
            cw = int(h * aspect) // 2 * 2
            vf.append(f"crop={cw}:{h}:{(w - cw) // 2}:0")
        else:
            ch = int(w / aspect) // 2 * 2
            vf.append(f"crop={w}:{ch}:0:{(h - ch) // 2}")
        if flip:
            vf.append("hflip")
        self.c = 1 if gray else 3
        vf.append(f"scale={W}:{H}:flags=bilinear,format={'gray' if gray else 'rgb24'}")
        self.proc = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{s0:.4f}", "-i", src, "-vf", ",".join(vf), "-f", "rawvideo", "-"],
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=W * H * self.c * 2)
        self.k = -1
        self.last = np.zeros((H, W, self.c), np.uint8)

    def at(self, s: float) -> np.ndarray:
        k = int(math.floor((s - self.s0) * self.fps + 1e-6))
        n = self.W * self.H * self.c
        while self.k < k:
            raw = self.proc.stdout.read(n)
            if len(raw) < n:
                break
            self.k += 1
            self.last = np.frombuffer(raw, np.uint8).reshape(self.H, self.W, self.c)
        return self.last

    def close(self) -> None:
        try:
            self.proc.stdout.close()
            self.proc.kill()
        except Exception:
            pass


# ---------------------------------------------------------------- transitions

def dir_blur(img: np.ndarray, length: float, horizontal: bool) -> np.ndarray:
    L = int(length)
    if L < 3:
        return img
    k = (L | 1, 1) if horizontal else (1, L | 1)
    out = cv2.blur(img, k, borderType=cv2.BORDER_REFLECT)
    return cv2.blur(out, ((L // 2) | 1, 1) if horizontal else (1, (L // 2) | 1), borderType=cv2.BORDER_REFLECT)


def t_whip(a: np.ndarray, b: np.ndarray, p: float, tr: dict, dp: float) -> np.ndarray:
    """A push with motion blur: one continuous fast pan across the two shots laid side by side."""
    h, w = a.shape[:2]
    d = tr.get("dir", "left")
    horizontal = d in ("left", "right")
    span = w if horizontal else h
    e = float(tr.get("ease", 3.0))
    pos = lambda q: (q ** e) / (q ** e + (1 - q) ** e) if 0 < q < 1 else float(q >= 1)  # noqa: E731
    x = pos(p) * span
    v = abs(pos(min(1, p + dp / 2)) - pos(max(0, p - dp / 2))) * span  # px travelled during this frame
    xi = int(round(x))
    out = np.empty_like(a)
    if d == "left":
        out[:, :w - xi] = a[:, xi:]; out[:, w - xi:] = b[:, :xi]
    elif d == "right":
        out[:, xi:] = a[:, :w - xi]; out[:, :xi] = b[:, w - xi:]
    elif d == "up":
        out[:h - xi] = a[xi:]; out[h - xi:] = b[:xi]
    else:
        out[xi:] = a[:h - xi]; out[:xi] = b[h - xi:]
    return dir_blur(out, v * float(tr.get("shutter", 0.9)), horizontal)


def zoom_blur(img: np.ndarray, s: float, ds: float, centre: tuple[float, float], n: int = 18) -> np.ndarray:
    """img scaled by s about centre, integrated over scales s..s*exp(ds) (radial motion blur), mirrored edges."""
    h, w = img.shape[:2]
    cx, cy = centre[0] * w, centre[1] * h
    acc = np.zeros_like(img)
    steps = n if abs(ds) > 0.01 else 1
    for i in range(steps):
        si = s * math.exp(ds * (i / max(steps - 1, 1) - 0.5))
        M = np.array([[si, 0, cx - si * cx], [0, si, cy - si * cy]], np.float32)
        acc += cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    return acc / steps


def t_zoom(a: np.ndarray, b: np.ndarray, p: float, tr: dict, dp: float) -> np.ndarray:
    """Punch through: both shots ride one continuous push-in, crossing in the blur."""
    Z = math.log(float(tr.get("factor", 3.0)))
    e = lambda q: smoother(q)  # noqa: E731
    centre = tuple(tr.get("centre", [0.5, 0.5]))
    de = e(min(1, p + dp / 2)) - e(max(0, p - dp / 2))
    ds = Z * de * float(tr.get("shutter", 1.0))
    sa, sb = math.exp(Z * e(p)), math.exp(Z * (e(p) - 1))
    k = smoother((p - 0.5) / 0.24 + 0.5)
    out = np.zeros_like(a)
    if k < 1:
        out += (1 - k) * zoom_blur(a, sa, ds, centre)
    if k > 0:
        out += k * zoom_blur(b, sb, ds, centre)
    return out


def t_flash(a: np.ndarray, b: np.ndarray, p: float, tr: dict, dp: float) -> np.ndarray:
    """A soft warm bloom over the cut (one rise and one fall; never a strobe)."""
    g = float(tr.get("gain", 0.7))
    rgb = np.array(tr.get("rgb", [1.0, 0.86, 0.70]), np.float32)
    if p < 0.5:
        f = g * (2 * p) ** 2
        base = a
    else:
        f = g * (2 * (1 - p)) ** 1.6
        base = b * (1 + 0.5 * f)
    veil = f * rgb
    return 1 - (1 - np.clip(base, 0, 1)) * (1 - np.clip(veil, 0, 1))


def composite(a: np.ndarray, b: np.ndarray, p: float, tr: dict, dp: float, matte: np.ndarray | None) -> np.ndarray:
    kind = tr.get("type", "cut")
    if kind == "cut":
        return b if p >= 0.5 else a
    if kind == "dissolve":
        k = ease(p)
        return a * (1 - k) + b * k
    if kind == "dip":
        return a * ease(1 - 2 * p) if p < 0.5 else b * ease(2 * p - 1)
    if kind == "whip":
        return t_whip(a, b, p, tr, dp)
    if kind == "zoom":
        return t_zoom(a, b, p, tr, dp)
    if kind == "flash":
        return t_flash(a, b, p, tr, dp)
    if kind == "matte" and matte is not None:
        m = matte.astype(np.float32) * (1 / 255.0)
        lo, hi = float(tr.get("lo", 0.1)), float(tr.get("hi", 0.5))
        m = np.clip((m - lo) / max(hi - lo, 1e-3), 0, 1)
        if tr.get("invert"):
            m = 1 - m
        m = m * m * (3 - 2 * m)
        # make sure the wipe completes: lean on progress at both ends
        m = np.clip(m + (smoother((p - 0.75) / 0.25) - (1 - smoother(p / 0.2))), 0, 1)
        return a * (1 - m) + b * m
    k = ease(p)
    return a * (1 - k) + b * k


# ---------------------------------------------------------------- render

def spans(plan: dict) -> list[tuple[dict, float, float]]:
    shots = plan["shots"]
    return [(s, s["start"], shots[i + 1]["start"] if i + 1 < len(shots) else plan["duration"]) for i, s in enumerate(shots)]


def render_range(plan_p: str, out_p: str, f0: int, f1: int, scale: float) -> list[tuple]:
    plan = json.load(open(plan_p, encoding="utf-8"))
    fps = plan["fps"]
    W, H = int(plan["w"] * scale) // 2 * 2, int(plan["h"] * scale) // 2 * 2
    look = {**LOOK_DEFAULT, **plan.get("look", {})}
    sp = spans(plan)
    half = [float(s.get("trans", {}).get("dur", 0.0)) / 2 if (i > 0 and s.get("trans", {}).get("type", "cut") != "cut") else 0.0
            for i, (s, _, _) in enumerate(sp)]
    lo, hi = f0 / fps, (f1 - 1) / fps
    vis = []  # visible span of each shot including the halves of its two transitions
    for i, (s, a, b) in enumerate(sp):
        vis.append((a - half[i], b + (half[i + 1] if i + 1 < len(sp) else 0.0)))
    shots = [Shot(s, a, b, W, H, fps, scale) if (vis[i][1] > lo - 1e-6 and vis[i][0] <= hi + 1e-6) else None for i, (s, a, b) in enumerate(sp)]
    readers: dict[int, Reader] = {}
    mattes: dict[int, Clip] = {}
    overlays = plan.get("overlays", [])
    ov_clips: dict[int, Clip] = {}
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(fps), "-i", "-", "-vf", "scale=in_range=pc:out_range=tv:out_color_matrix=bt709",
                            "-c:v", "libx264", "-preset", "medium", "-crf", "14",
                            "-x264-params", "threads=2", "-pix_fmt", "yuv420p", "-color_range", "tv",
                            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", out_p],
                           stdin=subprocess.PIPE)

    def image(i: int, t: float) -> np.ndarray:
        sh = shots[i]
        if i not in readers:
            readers[i] = Reader(sh, max(t, vis[i][0]), min(vis[i][1], f1 / fps + 0.05))
        r = readers[i]
        shutter = float(sh.d.get("shutter", 0.6))
        rate = (sh.src_time(t + 1.0 / fps) - sh.src_time(t)) * sh.fps_src
        src = r.exposure(sh.src_time(t), sh.src_time(t + shutter / fps), rate)
        cx, cy, w, h, rot = sh.window(t)
        sx, sy = w / W, h / H
        k = 1.0
        if sx > 1.6:  # large reduction: prefilter so the warp does not alias
            pre = cv2.resize(src, (max(2, int(src.shape[1] / sx * 1.25)), max(2, int(src.shape[0] / sy * 1.25))), interpolation=cv2.INTER_AREA)
            k = src.shape[1] / pre.shape[1]
            src = pre
        c, s_ = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        # output pixel (u, v) -> source pixel: centre + R * S * (uv - output centre)
        A = np.array([[c * sx, -s_ * sy], [s_ * sx, c * sy]], np.float32) / k
        ctr = np.array([(cx - r.bx) / k, (cy - r.by) / k], np.float32)
        off = ctr - A @ np.array([W / 2 - 0.5, H / 2 - 0.5], np.float32)
        M = np.hstack([A, off[:, None]]).astype(np.float32)
        fr = cv2.warpAffine(src, M, (W, H), flags=cv2.INTER_LANCZOS4 | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT)
        if sh.d.get("flip"):
            fr = fr[:, ::-1]
        sof = float(sh.d.get("soften", 0.0))  # px at full size: a shot held slightly out of focus (and a compressed source's blocks with it)
        if sof > 0:
            fr = cv2.GaussianBlur(fr, (0, 0), sof * scale)
        shp = 0.0 if sof > 0 else float(sh.d.get("sharpen", 0.3 if sx < 0.4 else 0.12))
        if shp > 0:
            bl = cv2.GaussianBlur(fr, (0, 0), 1.6 * scale + 0.4)
            fr = cv2.addWeighted(fr, 1 + shp, bl, -shp, 0)
        g = {**look, **sh.d.get("grade", {})}
        gk = sh.d.get("grade_keys")  # [[film_t, {"ev": ..}], ...]: an exposure or colour ride inside the shot
        if gk:
            ks = sorted(gk, key=lambda q: q[0])
            if t <= ks[0][0]:
                g = {**g, **ks[0][1]}
            elif t >= ks[-1][0]:
                g = {**g, **ks[-1][1]}
            else:
                j = max(q for q in range(len(ks)) if ks[q][0] <= t)
                u = ease((t - ks[j][0]) / max(ks[j + 1][0] - ks[j][0], 1e-6))
                g = {**g, **{key: ks[j][1].get(key, g.get(key, 0)) + (ks[j + 1][1].get(key, g.get(key, 0)) - ks[j][1].get(key, g.get(key, 0))) * u
                            for key in set(ks[j][1]) | set(ks[j + 1][1])}}
        out = grade(np.ascontiguousarray(fr), g)
        sk = sh.d.get("shock")  # a hit: the lens jolts (colour fringes that close, a breath of overexposure), then settles
        if sk:
            u = (t - float(sk.get("at", sh.start))) / max(float(sk.get("dur", 0.3)), 1e-3)
            if 0 <= u < 1:
                k = (1 - u) ** 2
                am = float(sk.get("amount", 0.015)) * k
                for c, sc in ((0, 1 + am), (2, 1 - am)):
                    M = np.array([[sc, 0, W / 2 * (1 - sc)], [0, sc, H / 2 * (1 - sc)]], np.float32)
                    out[..., c] = cv2.warpAffine(np.ascontiguousarray(out[..., c]), M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
                out = np.clip(out * (1 + float(sk.get("gain", 0.2)) * k), 0, 1)
        return out

    light = []
    for fi in range(f0, f1):
        t = fi / fps
        cur = max((i for i, (s, a, b) in enumerate(sp) if a <= t + 1e-9), default=0)
        img = None
        for j in (cur, cur + 1):  # inside the transition into shot j?
            if 0 < j < len(sp) and half[j] > 0 and abs(t - sp[j][1]) < half[j] - 1e-9 and shots[j] is not None and shots[j - 1] is not None:
                tr = sp[j][0]["trans"]
                dur = 2 * half[j]
                p = (t - (sp[j][1] - half[j])) / dur
                m = None
                if tr.get("type") == "matte":
                    if j not in mattes:
                        mattes[j] = Clip(tr["src"], float(tr.get("in", 0.0)), W, H, bool(tr.get("flip")), gray=True, rotate=int(tr.get("rotate", 0)))
                    m = mattes[j].at(float(tr.get("in", 0.0)) + p * float(tr.get("span", dur)))
                    m = m[..., :1]
                img = composite(image(j - 1, t), image(j, t), p, tr, 1.0 / (dur * fps), m)
                break
        if img is None:
            img = image(cur, t)
        for j in list(readers):
            if vis[j][1] < t - 1e-6:
                readers.pop(j).close()
        for oi, ov in enumerate(overlays):
            if ov["start"] <= t < ov["end"]:
                if oi not in ov_clips:
                    ov_clips[oi] = Clip(ov["src"], float(ov.get("in", 0.0)) + (t - ov["start"]) * float(ov.get("speed", 1.0)), W, H, bool(ov.get("flip")),
                                        rotate=int(ov.get("rotate", 0)))
                o = ov_clips[oi].at(float(ov.get("in", 0.0)) + (t - ov["start"]) * float(ov.get("speed", 1.0))).astype(np.float32) * (1 / 255.0)
                blk = float(ov.get("black", 0.02))
                o = np.clip((o - blk) / (1 - blk), 0, 1)
                fd = float(ov.get("fade", 0.2))  # "fade_in" / "fade_out" override it (0 = the layer is cut with the picture)
                env = min(1.0, (t - ov["start"] + 1e-6) / max(float(ov.get("fade_in", fd)), 1e-3), (ov["end"] - t) / max(float(ov.get("fade_out", fd)), 1e-3))
                o = o * (float(ov.get("gain", 1.0)) * max(0.0, env))
                if ov.get("mono"):  # keep only the layer's light (a prism leak without its rainbow)
                    o = np.repeat((o @ LUMA)[..., None], 3, axis=2)
                if ov.get("r2g"):  # red sparks towards orange and gold: their red also feeds green
                    o[..., 1] = np.minimum(1.0, o[..., 1] + float(ov["r2g"]) * o[..., 0])
                if ov.get("soften"):
                    o = cv2.GaussianBlur(o, (0, 0), float(ov["soften"]) * scale)
                if ov.get("tint"):
                    o = o * np.array(ov["tint"], np.float32)
                img = (1 - (1 - np.clip(img, 0, 1)) * (1 - np.clip(o, 0, 1))) if ov.get("mode", "screen") == "screen" else img + o
        img = np.clip(img, 0, 1)
        enc.stdin.write((img * 255 + 0.5).astype(np.uint8).tobytes())
        mid = img[int(H * 0.25):int(H * 0.75):8, ::8]
        light.append((round(float((mid @ LUMA).mean()), 4), round(float(mid[..., 0].mean() - mid[..., 2].mean()), 4), cur))
    for r in list(readers.values()) + list(mattes.values()) + list(ov_clips.values()):
        r.close()
    enc.stdin.close()
    enc.wait()
    return light


def main() -> None:
    args = sys.argv[1:]
    opts = {"--scale": 1.0, "--from": None, "--to": None, "--jobs": 3}
    for k in list(opts):
        if k in args:
            i = args.index(k); opts[k] = float(args[i + 1]); del args[i:i + 2]
    plan_p, out_p = args
    plan = json.load(open(plan_p, encoding="utf-8"))
    fps = plan["fps"]
    f0 = int(round((opts["--from"] or 0) * fps))
    f1 = int(round((opts["--to"] if opts["--to"] is not None else plan["duration"]) * fps))
    jobs = max(1, int(opts["--jobs"]))
    edges = [f0 + (f1 - f0) * j // jobs for j in range(jobs + 1)]
    tmp = tempfile.mkdtemp(prefix="mon_", dir=os.path.dirname(os.path.abspath(out_p)))
    parts = [os.path.join(tmp, f"part{j}.mp4") for j in range(jobs)]
    with ProcessPoolExecutor(jobs) as ex:
        futs = [ex.submit(render_range, plan_p, parts[j], edges[j], edges[j + 1], opts["--scale"]) for j in range(jobs) if edges[j + 1] > edges[j]]
        lights = [f.result() for f in futs]
    lst = os.path.join(tmp, "list.txt")
    open(lst, "w").write("".join(f"file '{p}'\n" for p, e0, e1 in zip(parts, edges, edges[1:]) if e1 > e0))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", out_p], check=True)
    for p in parts:
        if os.path.exists(p):
            os.remove(p)
    os.remove(lst); os.rmdir(tmp)
    light = [x for part in lights for x in part]
    json.dump({"fps": fps, "from_frame": f0, "lum": [x[0] for x in light], "warm": [x[1] for x in light], "shot": [x[2] for x in light],
               "cuts": [s["start"] for s in plan["shots"]]},
              open(os.path.splitext(out_p)[0] + ".light.json", "w"))
    print(json.dumps({"out": out_p, "frames": f1 - f0, "size_px": [int(plan["w"] * opts["--scale"]) // 2 * 2, int(plan["h"] * opts["--scale"]) // 2 * 2]}))


if __name__ == "__main__":
    main()
