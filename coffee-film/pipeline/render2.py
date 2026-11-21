#!/usr/bin/env python3
"""Picture engine of the coffee film's director's cut.

Per output frame (24 fps, 2160x3840 or a fraction of it):
  * SHOTS read their prepared stretch (pipeline/prep.py: one real frame per 1/24 s) through ffmpeg: optional
    denoise, scale, the shot's 3D LUT applied in 16 bit (grade.py).
  * TIME REMAP: "time": [[film_t, prep_t], ...] (monotone cubic between keys). When an output frame spans more
    than ~1.6 prep frames (a timelapse or a speed ramp), every prep frame inside its shutter interval is
    averaged in linear light: real motion blur, people becoming streaks. Otherwise the nearest real frame is
    shown, whole. A constant prep_t is a freeze frame.
  * MOVE: "move": {"keys": [[film_t, z, cx, cy], ...]} eased between keys, or {"z": [a, b], "cx", "cy"}.
  * PER-SHOT LOOK KEYS: "ev_keys" (exposure, stops), "sat_keys" (saturation multiplier), "defocus" (lens blur
    radius in px at 4K, with bokeh from the highlights), "streak" (anamorphic flare on highlights),
    "key_green" (an LED glow taken out), "light" (a soft window of light that follows a subject).
  * TRANSITIONS into a shot ("trans"): cut, dissolve, whip (a fast pan: both shots slide with directional
    motion blur, centred on the shot's start), black (the shot is black: "black": true).
  * OVERLAYS: real elements shot on black (steam, light leaks), screen-blended with black point, gain, tint,
    scale, position and a soft mask.
  * FINISH: bloom, clarity (large-radius local contrast), fine sharpening, vignette, titles (animated tracking,
    focus pull, rise), fine luminance grain, 16-bit out to the encoder.
Long renders are split into parallel jobs joined without re-encoding.

Usage: python render2.py PLAN.json LUT_DIR OUT.mp4 [--scale 0.5] [--from T] [--to T] [--jobs 2]
                         [--codec h264|h264_10|hevc10] [--crf 16] [--frames DIR]   (--frames: also write PNG stills of every frame there)
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.interpolate import PchipInterpolator

LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)
PREP_FPS = 24.0


def smooth(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def keyed(keys, t: float, default: float = 0.0) -> float:
    if not keys:
        return default
    ks = sorted(keys)
    if t <= ks[0][0]:
        return float(ks[0][1])
    if t >= ks[-1][0]:
        return float(ks[-1][1])
    for (a, va), (b, vb) in zip(ks, ks[1:]):
        if a <= t <= b:
            return float(va + (vb - va) * smooth((t - a) / max(b - a, 1e-6)))
    return default


def to_lin(x):
    return np.power(np.clip(x, 0, None), 2.2)


def to_disp(x):
    return np.power(np.clip(x, 0, None), 1 / 2.2)


class Timing:
    def __init__(self, s: dict):
        self.s = s
        ks = s.get("time")
        if ks:
            ks = sorted(ks)
            self.ts = np.array([k[0] for k in ks], np.float64)
            self.ps = np.array([k[1] for k in ks], np.float64)
            self.f = PchipInterpolator(self.ts, self.ps) if len(ks) > 2 and s.get("interp", "smooth") != "linear" else None
        else:
            self.ts = None

    def prep_t(self, t: float) -> float:
        s = self.s
        if self.ts is None:
            return s.get("in", 0.0) + (t - s["start"]) * s.get("speed", 1.0)
        if t <= self.ts[0]:
            return float(self.ps[0])
        if t >= self.ts[-1]:
            return float(self.ps[-1])
        if self.f is None:
            return float(np.interp(t, self.ts, self.ps))
        return float(self.f(t))


LIN16 = np.power(np.arange(65536, dtype=np.float64) / 65535.0, 2.2).astype(np.float32)   # uint16 display -> linear


def shift_img(img: np.ndarray, dx: float, dy: float, border: int = cv2.BORDER_CONSTANT) -> np.ndarray:
    M = np.array([[1, 0, dx], [0, 1, dy]], np.float32)
    return cv2.warpAffine(img, M, (img.shape[1], img.shape[0]), flags=cv2.INTER_LINEAR, borderMode=border)


class Reader:
    """Sequential, graded frames of one prepared stretch: single frames, a blend of two neighbours, weighted
    averages of a range (a shutter), or a trail exposure (a running, camera-aligned exposure)."""

    def __init__(self, shot: dict, lut: str, p0: float, W: int, H: int, hist: int = 1, store: bool = False):
        self.W, self.H = W, H
        self.hist: list[tuple[int, np.ndarray]] = []   # recent frames in linear light (float16), for long exposures
        self.maxhist = max(1, hist)
        self.store = store
        self.trail = shot.get("trail")
        k0 = int(math.floor(p0 * PREP_FPS)) - 1
        if self.trail:   # start early, so the exposure already holds its history on the shot's first frame
            k0 -= int(self.trail.get("frames", 24))
        self.k0 = max(0, k0)
        den = shot.get("denoise")
        vf = (f"{den + ',' if den else ''}scale={W}:{H}:flags=lanczos:in_color_matrix=bt709:in_range=tv,format=gbrp16le," +
              (f"lut3d=file='{lut}':interp=tetrahedral," if lut else "") + "format=rgb48le")
        self.p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{self.k0 / PREP_FPS:.4f}", "-i", shot["src"], "-vf", vf,
                                   "-f", "rawvideo", "-"], stdout=subprocess.PIPE, bufsize=W * H * 6 * 2)
        self.n = W * H * 6
        self.k = self.k0 - 1      # index of self.cur
        self.cur = None
        self.prev = None          # the frame before self.cur (for blends of two neighbours)
        self.lin = None           # self.cur in linear light (kept when a trail or a history needs it)
        self.acc = self.wacc = None
        self.small_prev = None
        self.off = np.zeros(2)    # where the current frame's content sits relative to the trail's reference frame
        self.last_vec = (0.0, 0.0)

    def _small(self, disp: np.ndarray) -> np.ndarray:
        return cv2.resize(disp @ LUMA, (self.W // 4, self.H // 4), interpolation=cv2.INTER_AREA)

    def _advance(self) -> bool:
        b = self.p.stdout.read(self.n)
        if len(b) < self.n:
            return False
        u = np.frombuffer(b, np.uint16).reshape(self.H, self.W, 3)
        self.prev = self.cur
        self.cur = u.astype(np.float32) * (1 / 65535.0)
        self.k += 1
        self.lin = None
        if self.store or self.trail:
            self.lin = LIN16[u]
        if self.store:
            self.hist.append((self.k, self.lin.astype(np.float16)))
            if len(self.hist) > self.maxhist:
                self.hist.pop(0)
        if self.trail:
            self._trail_update()
        return True

    def _trail_update(self) -> None:
        """A running exposure: acc <- acc*d + frame*(1-d), kept in one fixed reference frame. Each new frame is moved
        into it by the camera's measured travel (so the city stays sharp and only what moves through it leaves a
        trail) and the exposure is moved back once when shown: every frame is resampled twice, not once per frame.
        wacc tracks how much exposure each pixel holds (the edges the camera has just uncovered hold less)."""
        tr = self.trail
        d = 1.0 - 1.0 / max(2.0, float(tr.get("frames", 24)))
        sm = cv2.resize(self.cur @ LUMA, (self.W // 2, self.H // 2), interpolation=cv2.INTER_AREA)
        if self.acc is None:
            self.acc = self.lin.copy()
            self.wacc = np.ones((self.H, self.W), np.float32)
        else:
            if tr.get("align", True) and self.small_prev is not None:
                (dx, dy), resp = cv2.phaseCorrelate(self.small_prev.astype(np.float32), sm.astype(np.float32))
                if resp > 0.05 and abs(dx) < sm.shape[1] / 4 and abs(dy) < sm.shape[0] / 4:
                    self.off += (dx * self.W / sm.shape[1], dy * self.H / sm.shape[0])
            if np.abs(self.off).max() > 0.01:
                f_ref = cv2.warpAffine(self.lin, np.array([[1, 0, -self.off[0]], [0, 1, -self.off[1]]], np.float32), (self.W, self.H),
                                       flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT)
                m_ref = shift_img(np.ones((self.H, self.W), np.float32), -self.off[0], -self.off[1])
            else:
                f_ref, m_ref = self.lin, 1.0
            self.acc *= d
            self.acc += f_ref * (m_ref[..., None] if isinstance(m_ref, np.ndarray) else 1.0) * (1 - d)
            self.wacc *= d
            self.wacc += m_ref * (1 - d)
        self.small_prev = sm

    def trail_frame(self, k: int) -> np.ndarray:
        self.frame(k)
        mix = float(self.trail.get("mix", 0.6))
        w = self.wacc
        expo = self.acc / np.maximum(w, 1e-4)[..., None]
        if np.abs(self.off).max() > 0.01:
            M = np.array([[1, 0, self.off[0]], [0, 1, self.off[1]]], np.float32)
            expo = cv2.warpAffine(expo, M, (self.W, self.H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            w = cv2.warpAffine(w, M, (self.W, self.H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        # where the exposure holds little (an edge just uncovered by the camera), the current frame stands in
        mx = mix * np.clip(w / 0.5, 0, 1)[..., None]
        return to_disp(np.clip((1 - mx) * self.lin + mx * np.clip(expo, 0, None), 0, None))

    def frame(self, k: int) -> np.ndarray:
        while self.k < k or self.cur is None:   # a time before the stretch's first frame shows its first frame
            if not self._advance():
                break
        if self.cur is None:
            raise RuntimeError("no frame")
        if k == self.k - 1 and self.prev is not None:
            return self.prev
        if k < self.k - 1:
            for kk, f in self.hist:
                if kk == k:
                    return to_disp(f.astype(np.float32))
        return self.cur

    def blend(self, kf: int, w: float) -> np.ndarray:
        """Frame kf and kf+1 mixed by w (0..1): sub-real-time motion without repeated frames."""
        b = self.frame(kf + 1)
        a = self.prev if (self.k == kf + 1 and self.prev is not None) else self.frame(kf)
        return a * (1 - w) + b * w

    def average(self, A: float, B: float) -> tuple[np.ndarray, int, np.ndarray | None, np.ndarray | None]:
        """Exposure over prep-frame positions [A, B] (frame k covers [k-0.5, k+0.5]): every frame weighted by how
        much of it falls inside, averaged in linear light (frames already passed come from a short history, so
        exposures may overlap: a long shutter). Also returns the number of frames used and small grey copies of
        the first and last (to measure how far the picture moved in between)."""
        k_lo, k_hi = int(math.floor(A + 0.5)), int(math.floor(B + 0.5))
        self.frame(k_hi)
        use = []
        for k, f in self.hist:
            w = min(B, k + 0.5) - max(A, k - 0.5)
            if w > 1e-4 and k_lo <= k <= k_hi:
                use.append((k, f, w))
        if len(use) < 2:
            return self.frame(k_hi), 1, None, None
        acc = np.zeros(use[0][1].shape, np.float32)
        wsum = 0.0
        for _, f, w in use:
            acc += f.astype(np.float32) * w
            wsum += w
        small = lambda lin: self._small(to_disp(lin.astype(np.float32)))
        return to_disp(acc / wsum), len(use), small(use[0][1]), small(use[-1][1])

    def close(self) -> None:
        for lr in getattr(self, "layers", []):
            lr.close()
        self.p.stdout.close()
        self.p.kill()
        self.p.wait()


class Overlay:
    def __init__(self, o: dict, W: int, H: int, t0: float):
        self.o = o
        w = int(round(o.get("scale", 1.0) * W)) // 2 * 2
        h = int(round(w * o.get("aspect", 16 / 9 if o.get("rotate") not in (90, 270) else 9 / 16))) // 2 * 2 if o.get("aspect") else None
        rot = {90: "transpose=1,", 270: "transpose=2,"}.get(o.get("rotate", 0), "")
        vf = f"{rot}fps=24,scale={w}:-2:flags=bicubic,format=rgb24"
        s0 = o.get("in", 0.0) + (t0 - o["start"]) * o.get("speed", 1.0)
        self.p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{max(s0, 0):.4f}", "-i", o["src"], "-vf", vf, "-f", "rawvideo", "-"],
                                  stdout=subprocess.PIPE)
        pr = subprocess.run(["ffmpeg", "-v", "error", "-i", o["src"], "-vf", f"{rot}scale={w}:-2", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                            capture_output=True).stdout
        self.w, self.h = w, len(pr) // w
        self.n = self.w * self.h * 3
        self.last = None

    def next(self) -> np.ndarray | None:
        b = self.p.stdout.read(self.n)
        if len(b) == self.n:
            self.last = np.frombuffer(b, np.uint8).reshape(self.h, self.w, 3).astype(np.float32) * (1 / 255.0)
        return self.last

    def close(self) -> None:
        self.p.stdout.close()
        self.p.kill()
        self.p.wait()


def warp(img: np.ndarray, z: float, cx: float, cy: float, dx_px: float = 0.0) -> np.ndarray:
    if abs(z - 1) < 1e-4 and abs(cx - 0.5) < 1e-4 and abs(cy - 0.5) < 1e-4 and abs(dx_px) < 0.01:
        return img
    H, W = img.shape[:2]
    M = np.array([[z, 0, W / 2 - z * cx * W + dx_px], [0, z, H / 2 - z * cy * H]], np.float32)
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)


def dir_blur(img: np.ndarray, length: float) -> np.ndarray:
    """Horizontal motion blur of `length` px (a tent kernel: soft ends, like a real shutter's smear of a pan),
    computed at quarter size (the result is a blur anyway)."""
    if length < 1.0:
        return img
    H, W = img.shape[:2]
    f = 1 if length < 16 else (2 if length < 64 else 4)   # a short smear keeps full resolution
    small = cv2.resize(img, (W // f, H // f), interpolation=cv2.INTER_AREA) if f > 1 else img
    hl = length / f / 2
    L = int(math.ceil(hl)) * 2 + 1
    x = np.arange(L, dtype=np.float32) - L // 2
    k = np.clip(1.0 - np.abs(x) / max(hl, 0.5), 0, None)[None, :]
    small = cv2.filter2D(small, -1, k / k.sum(), borderType=cv2.BORDER_REFLECT)
    return cv2.resize(small, (W, H), interpolation=cv2.INTER_LINEAR) if f > 1 else small


_GRID: dict = {}


def flow_smear(fr: np.ndarray, g0: np.ndarray, g1: np.ndarray, n: int, scale: float = 1.0) -> np.ndarray:
    """Motion blur along the measured motion of every pixel (optical flow between the first and last frame of the
    exposure, at quarter size): joins the stepped copies an average of a fast pan leaves, also where near and far
    things move at different speeds."""
    a = np.clip(g0 * 255, 0, 255).astype(np.uint8)
    b = np.clip(g1 * 255, 0, 255).astype(np.uint8)
    flow = cv2.calcOpticalFlowFarneback(a, b, None, 0.5, 4, 21, 3, 7, 1.5, 0) * (scale / max(n - 1, 1))
    H, W = fr.shape[:2]
    fx, fy = W / a.shape[1], H / a.shape[0]
    fl = cv2.resize(flow, (W, H), interpolation=cv2.INTER_LINEAR)
    fl[..., 0] *= fx
    fl[..., 1] *= fy
    mag = float(np.percentile(np.hypot(fl[..., 0], fl[..., 1]), 99))
    if mag < 1.5:
        return fr
    taps = int(min(12, max(3, math.ceil(mag / 2))))
    if (W, H) not in _GRID:
        _GRID.clear()
        _GRID[(W, H)] = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    xx, yy = _GRID[(W, H)]
    lin = to_lin(fr)
    acc = np.zeros_like(lin)
    for j in range(taps):
        s = j / (taps - 1) - 0.5
        acc += cv2.remap(lin, xx + fl[..., 0] * s, yy + fl[..., 1] * s, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return to_disp(acc / taps)


def _lens_core(img: np.ndarray, r: float, boost: float) -> np.ndarray:
    H, W = img.shape[:2]
    f = 4 if r >= 8 else (2 if r >= 3 else 1)
    small = cv2.resize(img, (W // f, H // f), interpolation=cv2.INTER_AREA) if f > 1 else img
    lin = to_lin(small)
    lum = lin @ LUMA
    lin = lin * (1 + boost * np.clip((lum - 0.55) / 0.45, 0, 1) ** 2)[..., None]
    rr = max(1.0, r / f)
    n = int(math.ceil(rr)) * 2 + 1
    yy, xx = np.mgrid[0:n, 0:n] - n // 2
    k = np.clip(rr + 0.5 - np.sqrt(xx ** 2 + yy ** 2), 0, 1).astype(np.float32)
    k /= k.sum()
    out = cv2.filter2D(lin, -1, k, borderType=cv2.BORDER_REFLECT)
    out = to_disp(out / (1 + boost / 16.0 * np.clip(out - 1, 0, None)))
    return cv2.resize(out, (W, H), interpolation=cv2.INTER_LINEAR) if f > 1 else out


def lens_blur(img: np.ndarray, r: float, S: float) -> np.ndarray:
    """Defocus with a round aperture: highlights become bokeh discs. r in px at 4K, S = output scale.
    The highlight boost grows with the radius (a tiny blur must not brighten the sky), and small radii are a
    cross-fade from the sharp image, so the defocus starts and ends without a pop."""
    rp = r * S
    if rp < 0.05:
        return img
    boost = 4.0 * min(1.0, r / 24.0)
    m = min(1.0, rp / 2.0)
    out = _lens_core(img, max(rp, 1.0), boost)
    return out if m >= 1.0 else img * (1 - m) + out * m


class Title:
    """Lines of text, each re-laid out per frame so its letter spacing can breathe. Letters are set on a 4x canvas
    (advances in fractions of a pixel) and the block is placed with sub-pixel precision, so a slow tracking
    animation glides instead of stepping a pixel at a time."""

    SS = 4

    def __init__(self, t: dict, fonts: str, W: int, H: int):
        self.t, self.W, self.H = t, W, H
        self.s = W / 2160.0
        self.fonts = {}
        for ln in t["lines"]:
            key = (ln["font"], ln["size"])
            if key not in self.fonts:
                self.fonts[key] = ImageFont.truetype(os.path.join(fonts, ln["font"]), max(8, int(round(ln["size"] * self.s * self.SS))))
        self.color = np.array(t.get("color", [0.96, 0.94, 0.9]), np.float32)

    def mask(self, track_k: float) -> tuple[np.ndarray, float, float]:
        t, s, q = self.t, self.s, self.SS
        rows = []
        for ln in t["lines"]:
            f = self.fonts[(ln["font"], ln["size"])]
            tr0, tr1 = ln.get("track", [0.0, 0.0]) if isinstance(ln.get("track"), list) else (ln.get("track", 0.0), ln.get("track", 0.0))
            track = (tr0 + (tr1 - tr0) * track_k) * ln["size"] * s * q
            chars = list(ln["text"])
            ws = [f.getlength(c) for c in chars]
            tw = int(math.ceil(sum(ws) + track * (len(chars) - 1))) + 8 * q
            asc, desc = f.getmetrics()
            im = Image.new("L", (max(tw, 8 * q), asc + desc + 8 * q), 0)
            d = ImageDraw.Draw(im)
            x = 4.0 * q
            for c, w in zip(chars, ws):
                d.text((x, 4 * q), c, font=f, fill=255)
                x += w + track
            rows.append((np.asarray(im, np.float32) / 255.0, int(ln.get("gap", 0) * s * q)))
        width = max(r.shape[1] for r, _ in rows)
        height = sum(r.shape[0] + g for r, g in rows)
        pad = int(max(60, 3 * t.get("shadow_sigma", 6)) * s) * q
        A = np.zeros((height + 2 * pad, width + 2 * pad), np.float32)
        y = pad
        for r, g in rows:
            y += g
            x = pad + (width - r.shape[1]) / 2.0
            xi = int(round(x))
            A[y:y + r.shape[0], xi:xi + r.shape[1]] = np.maximum(A[y:y + r.shape[0], xi:xi + r.shape[1]], r)
            y += r.shape[0]
        hq, wq = (A.shape[0] // q) * q, (A.shape[1] // q) * q
        A = cv2.resize(A[:hq, :wq], (wq // q, hq // q), interpolation=cv2.INTER_AREA)
        x0 = t.get("x", 0.5) * self.W - A.shape[1] / 2
        y0 = t.get("y", 0.5) * self.H - A.shape[0] / 2
        return A, x0, y0

    def draw(self, img: np.ndarray, time: float) -> None:
        t = self.t
        if time < t["in"] or time >= t["out"]:   # never on the frame of a cut (e.g. a cut to black at `out`)
            return
        life = (time - t["in"]) / max(t["out"] - t["in"], 1e-3)
        a_in = smooth((time - t["in"]) / max(t.get("fade_in", 1.0), 1e-3))
        a_out = 1.0 if t.get("fade_out", 0) <= 0 else smooth((t["out"] - time) / t["fade_out"])
        a = min(a_in, a_out) * t.get("opacity", 1.0)
        if a <= 0.003:
            return
        A, x0f, y0f = self.mask(1 - (1 - life) ** 2)
        blur = t.get("focus", 0) * self.s * (1 - a_in) ** 1.5 + t.get("focus_out", 0) * self.s * (1 - a_out) ** 1.5
        if blur > 0.3:
            A = cv2.GaussianBlur(A, (0, 0), blur)
        y0f += t.get("rise", 0) * self.s * (1 - a_in)
        x0, y0 = int(math.floor(x0f)), int(math.floor(y0f))
        fx, fy = x0f - x0, y0f - y0
        A = cv2.warpAffine(A, np.array([[1, 0, fx], [0, 1, fy]], np.float32), (A.shape[1] + 1, A.shape[0] + 1),
                           flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        H, W = img.shape[:2]
        ya, yb, xa, xb = max(0, y0), min(H, y0 + A.shape[0]), max(0, x0), min(W, x0 + A.shape[1])
        if yb <= ya or xb <= xa:
            return
        m = A[ya - y0:yb - y0, xa - x0:xb - x0]
        roi = img[ya:yb, xa:xb]
        if t.get("glow", 0) > 0:  # a soft halo of the letters' own light
            g = cv2.GaussianBlur(m, (0, 0), 14 * self.s)[..., None] * t["glow"] * a
            roi[:] = 1 - (1 - roi) * (1 - g * self.color)
        if t.get("shadow", 0) > 0:  # a soft dark bed under the letters, wide enough to separate them from a busy plate
            sh = cv2.GaussianBlur(m, (0, 0), t.get("shadow_sigma", 6) * self.s)
            sh = np.clip(sh / max(float(sh.max()), 1e-3), 0, 1)[..., None] * t["shadow"] * a
            roi *= (1 - sh)
        mm = m[..., None] * a
        roi[:] = roi * (1 - mm) + self.color * mm


def shot_frame(s: dict, rd: Reader, tm: Timing, t: float, fps: int, S: float, W: int, H: int) -> np.ndarray:
    if s.get("black"):
        return np.zeros((H, W, 3), np.float32)
    shutter = s.get("shutter", 1.0)
    pa, pb = tm.prep_t(t - shutter / fps), tm.prep_t(t)
    span = (pb - pa) * PREP_FPS          # prep frames inside this output frame's shutter
    kpos = pb * PREP_FPS
    if s.get("trail") and span >= 0.02:
        fr = rd.trail_frame(int(round(kpos)))
    elif span < 0.02:                    # a freeze: one whole, crisp frame
        fr = rd.frame(int(round(kpos)))
    elif span <= 1.02 or not s.get("accumulate", True):
        kf = int(math.floor(kpos))
        w = kpos - kf
        if abs(span - 1) <= 0.02 or w < 0.03 or w > 0.97 or not s.get("blend", True):
            fr = rd.frame(int(round(kpos)))
        else:                            # slower than real time: the two real frames around this moment, mixed
            fr = rd.blend(kf, w)
    else:
        # the exposure opens with the speed: just above real time it is still nearly one whole frame, and it reaches
        # the full shutter at ~1.8x (a fast move is smeared, a slow one stays crisp, with nothing switching on suddenly)
        e = span * min(1.0, max(0.0, (span - 1.0) / 0.8)) if s.get("shutter_ramp", True) else span
        fr, n, g0, g1 = rd.average(kpos - e, kpos)
        mf = s.get("motion_fill", True)
        if n >= 2 and g0 is not None and mf:
            if mf == "flow":
                fr = flow_smear(fr, g0, g1, n, min(1.0, e))
            else:
                # averaged frames of a fast camera move leave stepped copies; a real shutter smears continuously, so
                # blur along the measured travel of one frame interval to join the copies (continuous in length,
                # and the last good measurement is kept when one is unreliable, so the blur never toggles)
                (dx, dy), resp = cv2.phaseCorrelate(g0.astype(np.float32), g1.astype(np.float32), cv2.createHanningWindow(g0.shape[::-1], cv2.CV_32F))
                if resp < 0.2:
                    dx, dy = rd.last_vec
                else:
                    dx, dy = dx * W / g0.shape[1] / (n - 1), dy * H / g0.shape[0] / (n - 1)
                    rd.last_vec = (dx, dy)
                dx, dy = dx * min(1.0, e), dy * min(1.0, e)
                L = math.hypot(dx, dy)
                if L >= 1.0:
                    f2 = 2
                    small = cv2.resize(fr, (W // f2, H // f2), interpolation=cv2.INTER_AREA)
                    hl = L / f2 / 2
                    n_ = int(math.ceil(hl)) * 2 + 3
                    k = np.zeros((n_, n_), np.float32)
                    c = (n_ - 1) / 2
                    ux, uy = dx / L, dy / L
                    sh = 16
                    p1 = (int(round((c - ux * hl) * sh)), int(round((c - uy * hl) * sh)))
                    p2 = (int(round((c + ux * hl) * sh)), int(round((c + uy * hl) * sh)))
                    cv2.line(k, p1, p2, 1.0, 1, cv2.LINE_AA, 4)
                    small = cv2.filter2D(small, -1, k / max(float(k.sum()), 1e-6), borderType=cv2.BORDER_REFLECT)
                    fr = cv2.resize(small, (W, H), interpolation=cv2.INTER_LINEAR)
    fr = fr.copy()
    for pl, lr in zip(s.get("plate_layers", []), getattr(rd, "layers", [])):
        # an element tracked to the subject in the clip's own coordinates (e.g. steam over the cup), screen-blended
        kl = int(round(kpos)) - int(pl["first_prep_frame"])
        if 0 <= kl < int(pl.get("frames", 10 ** 6)):
            lf = lr.frame(kl)
            g = float(np.interp(t, [q[0] for q in pl["gain_keys"]], [q[1] for q in pl["gain_keys"]])) if pl.get("gain_keys") else pl.get("gain", 1.0)
            if g > 1e-3:
                lay = np.clip(lf * g * np.array(pl.get("tint", [1, 1, 1]), np.float32), 0, 1)
                fr = 1 - (1 - np.clip(fr, 0, 1)) * (1 - lay)
    lt = s.get("light")
    if lt:  # a soft window of light on the subject, in the picture's own coordinates (it moves with the framing)
        ks = sorted(lt["keys"])
        lt_t = t - s["start"]
        kt = [q[0] for q in ks]
        cx_, cy_, rx_, ry_ = (float(np.interp(lt_t, kt, [q[i] for q in ks])) for i in (1, 2, 3, 4))
        ev_l = float(np.interp(lt_t, kt, [q[5] if len(q) > 5 else lt.get("ev", 0.5) for q in ks]))
        if abs(ev_l) > 1e-3:
            yy_, xx_ = np.ogrid[0:H, 0:W]
            d2 = ((xx_ / W - cx_) / rx_) ** 2 + ((yy_ / H - cy_) / ry_) ** 2
            m = np.exp(-d2 * 1.4).astype(np.float32)[..., None]
            warm = np.array(lt.get("tint", [1.0, 0.985, 0.95]), np.float32)
            fr = to_disp(to_lin(fr) * (1 + m * ((2 ** ev_l) * warm - 1)))
    mv = s.get("move", {})
    if "keys" in mv:
        ks = sorted(mv["keys"])
        z, cx, cy = (keyed([[k[0], k[i]] for k in ks], t) for i in (1, 2, 3))
    else:
        k = (t - s["start"]) / max(s["end"] - s["start"], 1e-3)
        z0, z1 = mv.get("z", [1.0, 1.0])
        z, cx, cy = z0 + (z1 - z0) * min(max(k, -0.3), 1.3), mv.get("cx", 0.5), mv.get("cy", 0.5)
    fr = warp(fr, z, cx, cy)
    kg = s.get("key_green")
    if kg:
        g_ = fr[..., 1] - np.maximum(fr[..., 0], fr[..., 2])
        m = np.clip((g_ / np.maximum(fr[..., 1], 1e-3) - kg.get("lo", 0.06)) / (kg.get("hi", 0.22) - kg.get("lo", 0.06)), 0, 1)
        ramp = np.clip((np.arange(H, dtype=np.float32) / H - kg.get("y0", 0.35)) / 0.08, 0, 1)[:, None]
        m = cv2.GaussianBlur(m * ramp, (0, 0), 2.0 * S)[..., None] * kg.get("strength", 1.0)
        lum_ = (fr @ LUMA)[..., None]
        fr = fr * (1 - m) + lum_ * (1 - kg.get("dim", 0.5) * m) * m
    gr = s.get("grad")
    if gr:  # a graduated ND filter: -ev stops at the top edge, easing to nothing at y1
        ys = np.arange(H, dtype=np.float32) / H
        w = np.clip(1 - (ys - gr.get("y0", 0.0)) / max(gr["y1"] - gr.get("y0", 0.0), 1e-3), 0, 1) ** 1.5
        fr = to_disp(to_lin(fr) * (2.0 ** (gr["ev"] * w))[:, None, None])
    ev = keyed(s.get("ev_keys"), t, 0.0)
    if abs(ev) > 1e-3:
        fr = to_disp(to_lin(fr) * 2 ** ev)
    sat = keyed(s.get("sat_keys"), t, 1.0)
    if abs(sat - 1) > 1e-3:
        lum = (fr @ LUMA)[..., None]
        fr = lum + (fr - lum) * sat
    st = s.get("streak")
    if st:
        small = cv2.resize(fr, (W // 8, H // 8), interpolation=cv2.INTER_AREA)
        hi = np.clip((small @ LUMA - st.get("threshold", 0.85)) / (1 - st.get("threshold", 0.85)), 0, 1)[..., None] * small
        L = max(3, int(st.get("length", 0.3) * W / 8) | 1)
        hi = cv2.filter2D(hi, -1, np.ones((1, L), np.float32) / L * 3.0)
        fr = fr + st.get("gain", 0.12) * cv2.resize(hi, (W, H), interpolation=cv2.INTER_LINEAR) * np.array(st.get("tint", [0.75, 0.88, 1.0]), np.float32)
    dfk = s.get("defocus")
    if dfk:
        r = keyed(dfk, t, 0.0)
        if r > 0.0:
            fr = lens_blur(fr, r, S)
    return fr


def render_range(plan: dict, luts: str, out: str, f0: int, f1: int, scale: float, codec: str, crf: str, frames_dir: str | None) -> None:
    fps = plan["fps"]
    W, H = int(plan["w"] * scale) // 2 * 2, int(plan["h"] * scale) // 2 * 2
    S = W / 2160.0
    shots = plan["shots"]
    tims = [Timing(s) for s in shots]
    fin = plan["finish"]
    titles = [Title(t, plan["fonts"], W, H) for t in plan.get("titles", [])]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    rv = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 * 0.7 + ((yy - H / 2) / (H / 2)) ** 2)
    vign = (1 - fin.get("vignette", 0.18) * np.clip(rv - 0.4, 0, None) ** 1.7).astype(np.float32)[..., None]
    del yy, xx, rv
    rng = np.random.default_rng(11)
    gs = fin.get("grain", {}).get("size", 1.0) * W / 1080.0   # grain size in pixels of a 1080-wide picture: the same grain at every size
    grains = []
    for _ in range(10):
        g = rng.standard_normal((max(2, int(H / gs)), max(2, int(W / gs)))).astype(np.float32)
        if abs(gs - 1.0) > 1e-3:
            g = cv2.resize(g, (W, H), interpolation=cv2.INTER_CUBIC)
        grains.append((g / (g.std() + 1e-6)).astype(np.float16))
    if codec == "hevc10":
        venc = ["-c:v", "libx265", "-preset", "slow", "-crf", crf, "-pix_fmt", "yuv420p10le",
                "-x265-params", "aq-mode=3:psy-rd=2.0:psy-rdoq=1.0:deblock=-1,-1:rc-lookahead=20:log-level=error", "-tag:v", "hvc1"]
    elif codec == "h264_10":   # a near-lossless 10-bit intermediate (the delivery file is encoded from it, with the sound)
        venc = ["-c:v", "libx264", "-preset", "medium", "-crf", crf, "-pix_fmt", "yuv420p10le", "-x264-params", "rc-lookahead=20:deblock=-1,-1"]
    else:
        venc = ["-c:v", "libx264", "-preset", "slow", "-crf", crf, "-pix_fmt", "yuv420p", "-x264-params", "aq-mode=3:rc-lookahead=20:deblock=-1,-1:ipratio=1.1:pbratio=1.1"]
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb48le", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
                            "-vf", "scale=out_color_matrix=bt709:out_range=tv"] + venc +
                           ["-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv", "-movflags", "+faststart", out],
                           stdin=subprocess.PIPE)
    readers: dict[int, Reader] = {}
    ovs: dict[int, Overlay] = {}

    def window(i: int) -> tuple[float, float]:
        s = shots[i]
        tr = s.get("trans", {})
        half = tr.get("dur", 0) / 2 if tr.get("type") in ("dissolve", "whip") else 0
        nxt = shots[i + 1] if i + 1 < len(shots) else None
        ntr = nxt.get("trans", {}) if nxt else {}
        nhalf = ntr.get("dur", 0) / 2 if ntr.get("type") in ("dissolve", "whip") else 0
        return s["start"] - half, s["end"] + nhalf

    for f in range(f0, f1):
        t = f / fps
        live = [i for i in range(len(shots)) if window(i)[0] <= t < window(i)[1]]
        for i in list(readers):
            if i not in live:
                readers.pop(i).close()
        frs = {}
        for i in live:
            s = shots[i]
            if not s.get("black") and i not in readers:
                sh_ = s.get("shutter", 1.0)
                pa = tims[i].prep_t(t - sh_ / fps)   # not clamped to the shot's start: its first frame already has a full exposure
                a_, b_ = window(i)
                tt = np.arange(a_, b_, 1.0 / fps)
                vmax = max([(tims[i].prep_t(x) - tims[i].prep_t(x - sh_ / fps)) * PREP_FPS for x in tt] + [1.0])
                store = vmax > 1.02 and not s.get("trail") and s.get("accumulate", True)
                readers[i] = Reader(s, os.path.join(luts, f"{s['id']}.cube"), pa, W, H, hist=int(math.ceil(vmax)) + 3, store=store)
                readers[i].layers = []
                for pl in s.get("plate_layers", []):
                    k_first = max(0, int(round(pa * PREP_FPS)) - int(pl["first_prep_frame"]))
                    readers[i].layers.append(Reader({"src": pl["src"]}, None, k_first / PREP_FPS, W, H))
            frs[i] = shot_frame(s, readers.get(i), tims[i], t, fps, S, W, H)
        img = None
        for i in live:
            s, fr = shots[i], frs[i]
            if img is None:
                img = fr
                continue
            tr = s.get("trans", {})
            d = tr.get("dur", 0.3)
            p = min(1.0, max(0.0, (t - (s["start"] - d / 2)) / d))
            if tr.get("type") == "whip":
                # a whip pan: the outgoing shot accelerates away, the incoming one decelerates in; the smear is
                # proportional to the speed (a 180-degree shutter), so it grows from nothing and dies to nothing
                dirn = -1 if tr.get("dir", "left") == "left" else 1
                amp, ex = tr.get("travel", 0.75) * W, tr.get("ease", 2.2)
                sh_out = lambda q: dirn * amp * (max(q, 0.0) / 0.5) ** ex
                sh_in = lambda q: -dirn * amp * max(0.0, 1 - (q - 0.5) / 0.5) ** ex
                dp = 1.0 / (fps * d)
                a = b = None
                if p < 0.62:
                    L = 0.5 * abs(sh_out(p) - sh_out(p - dp)) * tr.get("blur", 1.0)
                    a = dir_blur(warp(img, 1, 0.5, 0.5, sh_out(p)), L)
                if p > 0.38:
                    L = 0.5 * abs(sh_in(p) - sh_in(p - dp)) * tr.get("blur", 1.0)
                    b = dir_blur(warp(fr, 1, 0.5, 0.5, sh_in(p)), L)
                mix = smooth((p - 0.38) / 0.24)
                if a is None:
                    img = b
                elif b is None:
                    img = a
                else:
                    img = to_disp(to_lin(a) * (1 - mix) + to_lin(b) * mix)
            else:
                a = smooth(p)
                img = img * (1 - a) + fr * a
        b = fin.get("bloom")
        if b:
            small = cv2.resize(img, (W // 8, H // 8), interpolation=cv2.INTER_AREA)
            hi = np.clip((small @ LUMA - b["threshold"]) / (1 - b["threshold"]), 0, 1)[..., None] * small
            hi = cv2.GaussianBlur(hi, (0, 0), b["radius"] * W / 8)
            img = img + b["gain"] * cv2.resize(hi, (W, H), interpolation=cv2.INTER_LINEAR) * np.array(b["tint"], np.float32)
        for oi, o in enumerate(plan.get("overlays", [])):
            if o["start"] <= t < o["end"]:
                if oi not in ovs:
                    ovs[oi] = Overlay(o, W, H, t)
                ol = ovs[oi].next()
                if ol is None:
                    continue
                blk = o.get("black", 0.05)
                ol = np.clip((ol - blk) / (1 - blk), 0, 1) ** o.get("gamma", 1.0)
                env = min(1.0, (t - o["start"]) / max(o.get("fade_in", 0.3), 1e-3), (o["end"] - t) / max(o.get("fade_out", 0.3), 1e-3))
                if o.get("gain_keys"):   # an envelope in film time instead of the fades
                    env = keyed(o["gain_keys"], t, 0.0)
                if o.get("mono"):
                    ol = np.repeat((ol @ LUMA)[..., None], 3, axis=2)
                ol = ol * o.get("gain", 1.0) * max(0.0, env) * np.array(o.get("tint", [1, 1, 1]), np.float32)
                oh, ow = ol.shape[:2]
                fe = o.get("feather", 0.12)
                ex = np.clip(np.minimum(np.arange(ow), np.arange(ow)[::-1]) / max(fe * ow, 1), 0, 1)
                ey = np.clip(np.minimum(np.arange(oh), np.arange(oh)[::-1]) / max(fe * oh, 1), 0, 1)
                ol = ol * (np.outer(ey, ex) ** 1.5).astype(np.float32)[..., None]
                x0 = int(round(o.get("cx", 0.5) * W - ow / 2))
                y0 = int(round(o.get("cy", 0.5) * H - oh / 2))
                ya, yb, xa, xb = max(0, y0), min(H, y0 + oh), max(0, x0), min(W, x0 + ow)
                if yb <= ya or xb <= xa:
                    continue
                part = ol[ya - y0:yb - y0, xa - x0:xb - x0]
                mk = o.get("mask")
                if mk:  # vertical: fully visible below y_full, gone above y_zero (frame fractions); soft side edges
                    ys = (np.arange(ya, yb, dtype=np.float32) / H)[:, None]
                    vm = np.clip((ys - mk["y_zero"]) / max(mk["y_full"] - mk["y_zero"], 1e-3), 0, 1)
                    vm = vm * np.clip((mk.get("y_bottom", 2.0) - ys) / 0.03, 0, 1)
                    xs = (np.arange(xa, xb, dtype=np.float32) - (xa + xb) / 2) / max((xb - xa) / 2, 1)
                    hm = np.clip((1 - np.abs(xs)) / mk.get("edge", 0.35), 0, 1)[None, :]
                    part = part * (vm * hm)[..., None]
                rm = o.get("radial")
                if rm:  # full inside r0, nothing beyond r1 (frame-height units, from a centre in frame fractions)
                    yy_ = (np.arange(ya, yb, dtype=np.float32)[:, None] - rm["cy"] * H) / H
                    xx_ = (np.arange(xa, xb, dtype=np.float32)[None, :] - rm["cx"] * W) / H
                    rr_ = np.sqrt(xx_ ** 2 + yy_ ** 2)
                    part = part * (np.clip((rm["r1"] - rr_) / max(rm["r1"] - rm["r0"], 1e-3), 0, 1) ** 1.5)[..., None]
                roi = img[ya:yb, xa:xb]
                roi[:] = 1 - (1 - np.clip(roi, 0, 1)) * (1 - np.clip(part, 0, 1))
        img = np.clip(img, 0, 1.5)
        cl = fin.get("clarity")
        if cl:
            lum = img @ LUMA
            small = cv2.resize(lum, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
            lb = cv2.resize(cv2.GaussianBlur(small, (0, 0), cl["sigma"] * W / 4), (W, H), interpolation=cv2.INTER_LINEAR)
            lc = np.clip(lum, 0, 1)
            img = img + (cl["amount"] * (lum - lb) * (0.05 + lc * (1 - lc) * 3))[..., None]   # midtones only: highlights keep their roll-off
        sh = fin.get("sharpen")
        if sh:
            lum = img @ LUMA
            img = img + (sh["amount"] * (lum - cv2.GaussianBlur(lum, (0, 0), sh["sigma"] * S)))[..., None]
        ro = fin.get("rolloff")
        if ro:  # a soft shoulder after the sharpening: no new flat whites
            kn = ro.get("knee", 0.9)
            img = np.where(img > kn, kn + (1 - kn) * np.tanh((img - kn) / (1 - kn)), img)
        img *= vign
        for tl in titles:
            tl.draw(img, t)
        for a0, a1, kind in fin.get("fades", []):
            if a0 <= t <= a1:
                k = smooth((t - a0) / max(a1 - a0, 1e-3))
                img *= (k if kind == "in" else 1 - k)
        g = fin.get("grain")
        if g:
            lum = np.clip(img @ LUMA, 0, 1)[..., None]
            img = img + grains[f % len(grains)].astype(np.float32)[..., None] * g["amount"] * (0.3 + 1.4 * lum * (1 - lum))
        out16 = (np.clip(img, 0, 1) * 65535 + 0.5).astype(np.uint16)
        enc.stdin.write(out16.tobytes())
        if frames_dir:
            cv2.imwrite(os.path.join(frames_dir, f"f{f:05d}.jpg"), (out16[..., ::-1] >> 8).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 92])
    for r in list(readers.values()) + list(ovs.values()):
        r.close()
    enc.stdin.close()
    enc.wait()


def main() -> None:
    args = sys.argv[1:]
    opts = {"--scale": "1.0", "--from": None, "--to": None, "--jobs": "2", "--crf": "16", "--codec": "h264", "--frames": None}
    for k in list(opts):
        if k in args:
            i = args.index(k); opts[k] = args[i + 1]; del args[i:i + 2]
    plan_p, luts, out = args[0], args[1], args[2]
    plan = json.load(open(plan_p, encoding="utf-8"))
    fps = plan["fps"]
    f0 = int(round(float(opts["--from"] or 0) * fps))
    f1 = int(round(float(opts["--to"] or plan["duration"]) * fps))
    scale, jobs = float(opts["--scale"]), max(1, int(opts["--jobs"]))
    if opts["--frames"]:
        os.makedirs(opts["--frames"], exist_ok=True)
    if os.environ.get("COFFEE_RANGE"):
        a, b = map(int, os.environ["COFFEE_RANGE"].split(","))
        render_range(plan, luts, out, a, b, scale, opts["--codec"], opts["--crf"], opts["--frames"])
        return
    tmp = tempfile.mkdtemp(prefix="render2_", dir=os.path.dirname(os.path.abspath(out)))
    cuts = [f0 + (f1 - f0) * k // jobs for k in range(jobs + 1)]
    procs, parts = [], []
    for k in range(jobs):
        part = os.path.join(tmp, f"part{k}.mp4")
        parts.append(part)
        env = {**os.environ, "COFFEE_RANGE": f"{cuts[k]},{cuts[k + 1]}", "OMP_NUM_THREADS": "2"}
        cmd = [sys.executable, __file__, plan_p, luts, part, "--scale", str(scale), "--crf", opts["--crf"], "--codec", opts["--codec"]]
        if opts["--frames"]:
            cmd += ["--frames", opts["--frames"]]
        procs.append(subprocess.Popen(cmd, env=env))
    if any(p.wait() for p in procs):
        sys.exit("a render job failed")
    lst = os.path.join(tmp, "parts.txt")
    open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", out], check=True)
    for p in parts:
        os.remove(p)
    os.remove(lst)
    os.rmdir(tmp)
    print(json.dumps({"out": out, "frames": f1 - f0, "from": f0 / fps, "to": f1 / fps, "scale": scale}))


if __name__ == "__main__":
    main()
