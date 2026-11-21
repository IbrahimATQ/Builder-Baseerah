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
                         [--codec h264|hevc10] [--crf 16] [--frames DIR]   (--frames: also write PNG stills of every frame there)
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


class Reader:
    """Sequential, graded frames of one prepared stretch; serves single frames or averages of a range."""

    def __init__(self, shot: dict, lut: str, p0: float, W: int, H: int, hist: int = 1):
        self.W, self.H = W, H
        self.hist: list[tuple[int, np.ndarray]] = []   # recent frames in linear light (float16), for long exposures
        self.maxhist = max(1, hist)
        self.k0 = max(0, int(math.floor(p0 * PREP_FPS)) - 1)
        den = shot.get("denoise")
        vf = (f"{den + ',' if den else ''}scale={W}:{H}:flags=lanczos:in_color_matrix=bt709:in_range=tv,format=gbrp16le,"
              f"lut3d=file='{lut}':interp=tetrahedral,format=rgb48le")
        self.p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{self.k0 / PREP_FPS:.4f}", "-i", shot["src"], "-vf", vf,
                                   "-f", "rawvideo", "-"], stdout=subprocess.PIPE, bufsize=W * H * 6 * 2)
        self.n = W * H * 6
        self.k = self.k0 - 1      # index of self.cur
        self.cur = None

    def _advance(self) -> bool:
        b = self.p.stdout.read(self.n)
        if len(b) < self.n:
            return False
        self.cur = np.frombuffer(b, np.uint16).reshape(self.H, self.W, 3).astype(np.float32) * (1 / 65535.0)
        self.k += 1
        return True

    def frame(self, k: int) -> np.ndarray:
        while self.k < k or self.cur is None:   # a time before the stretch's first frame shows its first frame
            if not self._advance():
                break
        if self.cur is None:
            raise RuntimeError("no frame")
        return self.cur

    def average(self, k0: int, k1: int) -> tuple[np.ndarray, int, np.ndarray | None, np.ndarray | None]:
        """Mean of frames k0..k1 (inclusive) in linear light (frames already passed come from a short history,
        so shutter intervals may overlap: a long exposure), the number averaged, and small grey copies of the
        first and last of them (to measure how far the picture moved in between)."""
        while self.k < k1:
            if not self._advance():
                break
            self.hist.append((self.k, to_lin(self.cur).astype(np.float16)))
            if len(self.hist) > self.maxhist:
                self.hist.pop(0)
        use = [(k, f) for k, f in self.hist if k0 <= k <= k1]
        if not use:
            return self.frame(k1), 1, None, None
        acc = np.zeros(use[0][1].shape, np.float32)
        for _, f in use:
            acc += f
        small = lambda lin: cv2.resize(to_disp(lin.astype(np.float32)) @ LUMA, (self.W // 4, self.H // 4), interpolation=cv2.INTER_AREA)
        return to_disp(acc / len(use)), len(use), small(use[0][1]), small(use[-1][1])

    def close(self) -> None:
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
    """Horizontal motion blur of `length` px, computed at quarter size (the result is a blur anyway)."""
    if length < 2:
        return img
    H, W = img.shape[:2]
    small = cv2.resize(img, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    L = max(3, int(length / 4) | 1)
    k = np.ones((1, L), np.float32) / L
    small = cv2.filter2D(small, -1, k, borderType=cv2.BORDER_REFLECT)
    return cv2.resize(small, (W, H), interpolation=cv2.INTER_LINEAR)


def lens_blur(img: np.ndarray, r: float, S: float) -> np.ndarray:
    """Defocus with a round aperture: highlights become bokeh discs. r in px at 4K, S = output scale."""
    r = r * S
    if r < 0.8:
        return img
    H, W = img.shape[:2]
    f = 4 if r >= 8 else (2 if r >= 3 else 1)
    small = cv2.resize(img, (W // f, H // f), interpolation=cv2.INTER_AREA) if f > 1 else img
    lin = to_lin(small)
    lum = lin @ LUMA
    lin = lin * (1 + 4.0 * np.clip((lum - 0.55) / 0.45, 0, 1) ** 2)[..., None]
    rr = max(1.0, r / f)
    n = int(math.ceil(rr)) * 2 + 1
    yy, xx = np.mgrid[0:n, 0:n] - n // 2
    k = np.clip(rr + 0.5 - np.sqrt(xx ** 2 + yy ** 2), 0, 1).astype(np.float32)
    k /= k.sum()
    out = cv2.filter2D(lin, -1, k, borderType=cv2.BORDER_REFLECT)
    out = to_disp(out / (1 + 0.25 * np.clip(out - 1, 0, None)))
    return cv2.resize(out, (W, H), interpolation=cv2.INTER_LINEAR) if f > 1 else out


class Title:
    """Lines of text, each re-laid out per frame so its letter spacing can breathe."""

    def __init__(self, t: dict, fonts: str, W: int, H: int):
        self.t, self.W, self.H = t, W, H
        self.s = W / 2160.0
        self.fonts = {}
        for ln in t["lines"]:
            key = (ln["font"], ln["size"])
            if key not in self.fonts:
                self.fonts[key] = ImageFont.truetype(os.path.join(fonts, ln["font"]), max(8, int(ln["size"] * self.s)))
        self.color = np.array(t.get("color", [0.96, 0.94, 0.9]), np.float32)

    def mask(self, track_k: float) -> tuple[np.ndarray, int, int]:
        t, s = self.t, self.s
        rows = []
        for ln in t["lines"]:
            f = self.fonts[(ln["font"], ln["size"])]
            tr0, tr1 = ln.get("track", [0.0, 0.0]) if isinstance(ln.get("track"), list) else (ln.get("track", 0.0), ln.get("track", 0.0))
            track = (tr0 + (tr1 - tr0) * track_k) * ln["size"] * s
            chars = list(ln["text"])
            ws = [f.getlength(c) for c in chars]
            tw = int(sum(ws) + track * (len(chars) - 1)) + 8
            asc, desc = f.getmetrics()
            im = Image.new("L", (max(tw, 8), asc + desc + 8), 0)
            d = ImageDraw.Draw(im)
            x = 4.0
            for c, w in zip(chars, ws):
                d.text((x, 4), c, font=f, fill=255)
                x += w + track
            rows.append((np.asarray(im, np.float32) / 255.0, int(ln.get("gap", 0) * s)))
        width = max(r.shape[1] for r, _ in rows)
        height = sum(r.shape[0] + g for r, g in rows)
        pad = int(60 * s)
        A = np.zeros((height + 2 * pad, width + 2 * pad), np.float32)
        y = pad
        for r, g in rows:
            y += g
            x = pad + (width - r.shape[1]) // 2
            A[y:y + r.shape[0], x:x + r.shape[1]] = np.maximum(A[y:y + r.shape[0], x:x + r.shape[1]], r)
            y += r.shape[0]
        x0 = int(round(t.get("x", 0.5) * self.W - A.shape[1] / 2))
        y0 = int(round(t.get("y", 0.5) * self.H - A.shape[0] / 2))
        return A, x0, y0

    def draw(self, img: np.ndarray, time: float) -> None:
        t = self.t
        if time < t["in"] or time > t["out"]:
            return
        life = (time - t["in"]) / max(t["out"] - t["in"], 1e-3)
        a_in = smooth((time - t["in"]) / max(t.get("fade_in", 1.0), 1e-3))
        a_out = 1.0 if t.get("fade_out", 0) <= 0 else smooth((t["out"] - time) / t["fade_out"])
        a = min(a_in, a_out) * t.get("opacity", 1.0)
        if a <= 0.003:
            return
        A, x0, y0 = self.mask(1 - (1 - life) ** 2)
        blur = t.get("focus", 0) * self.s * (1 - a_in) ** 1.5 + t.get("focus_out", 0) * self.s * (1 - a_out) ** 1.5
        if blur > 0.3:
            A = cv2.GaussianBlur(A, (0, 0), blur)
        y0 += int(round(t.get("rise", 0) * self.s * (1 - a_in)))
        H, W = img.shape[:2]
        ya, yb, xa, xb = max(0, y0), min(H, y0 + A.shape[0]), max(0, x0), min(W, x0 + A.shape[1])
        if yb <= ya or xb <= xa:
            return
        m = A[ya - y0:yb - y0, xa - x0:xb - x0]
        roi = img[ya:yb, xa:xb]
        if t.get("glow", 0) > 0:  # a soft halo of the letters' own light
            g = cv2.GaussianBlur(m, (0, 0), 14 * self.s)[..., None] * t["glow"] * a
            roi[:] = 1 - (1 - roi) * (1 - g * self.color)
        if t.get("shadow", 0) > 0:
            sh = cv2.GaussianBlur(m, (0, 0), 6 * self.s)[..., None] * t["shadow"] * a
            roi *= (1 - sh)
        mm = m[..., None] * a
        roi[:] = roi * (1 - mm) + self.color * mm


def shot_frame(s: dict, rd: Reader, tm: Timing, t: float, fps: int, S: float, W: int, H: int) -> np.ndarray:
    if s.get("black"):
        return np.zeros((H, W, 3), np.float32)
    shutter = s.get("shutter", 1.0)
    pa, pb = tm.prep_t(t - shutter / fps), tm.prep_t(t)
    span = (pb - pa) * PREP_FPS
    if span > 1.6 and s.get("accumulate", True):
        k1 = int(round(pb * PREP_FPS))
        k0 = int(round(pa * PREP_FPS)) + 1
        fr, n, g0, g1 = rd.average(min(k0, k1), k1)
        if n >= 2 and g0 is not None and s.get("motion_fill", True):
            # averaged frames of a fast camera move leave stepped copies; a real shutter smears continuously, so
            # blur along the measured travel of one frame interval to join the copies
            (dx, dy), resp = cv2.phaseCorrelate(g0.astype(np.float32), g1.astype(np.float32), cv2.createHanningWindow(g0.shape[::-1], cv2.CV_32F))
            dx, dy = 4 * dx / (n - 1), 4 * dy / (n - 1)
            L = math.hypot(dx, dy)
            if L > 3 and resp > 0.05:
                f2 = 2
                small = cv2.resize(fr, (W // f2, H // f2), interpolation=cv2.INTER_AREA)
                n_ = max(3, int(L / f2) | 1)
                k = np.zeros((n_, n_), np.float32)
                c = (n_ - 1) / 2
                cv2.line(k, (int(round(c - dx / L * c)), int(round(c - dy / L * c))), (int(round(c + dx / L * c)), int(round(c + dy / L * c))), 1.0, 1, cv2.LINE_AA)
                small = cv2.filter2D(small, -1, k / max(float(k.sum()), 1e-6), borderType=cv2.BORDER_REFLECT)
                fr = cv2.resize(small, (W, H), interpolation=cv2.INTER_LINEAR)
    else:
        fr = rd.frame(int(round(pb * PREP_FPS)))
    fr = fr.copy()
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
        fr = fr * (1 - m) + lum_ * (1 - 0.5 * m) * m
    lt = s.get("light")
    if lt:
        ks = sorted(lt["keys"])
        lt_t = t - s["start"]
        cx_, cy_, rx_, ry_ = (float(np.interp(lt_t, [q[0] for q in ks], [q[i] for q in ks])) for i in (1, 2, 3, 4))
        yy_, xx_ = np.ogrid[0:H, 0:W]
        d2 = ((xx_ / W - cx_) / rx_) ** 2 + ((yy_ / H - cy_) / ry_) ** 2
        m = np.exp(-d2 * 1.4).astype(np.float32)[..., None]
        warm = np.array(lt.get("tint", [1.0, 0.985, 0.95]), np.float32)
        fr = fr * (1 + m * ((2 ** lt.get("ev", 0.5)) * warm - 1))
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
        if r > 0.8:
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
    gs = fin.get("grain", {}).get("size", 1.0)
    grains = []
    for _ in range(10):
        g = rng.standard_normal((max(2, int(H / gs)), max(2, int(W / gs)))).astype(np.float32)
        if gs != 1.0:
            g = cv2.resize(g, (W, H), interpolation=cv2.INTER_CUBIC)
        grains.append((g / (g.std() + 1e-6)).astype(np.float16))
    if codec == "hevc10":
        venc = ["-c:v", "libx265", "-preset", "slow", "-crf", crf, "-pix_fmt", "yuv420p10le",
                "-x265-params", "aq-mode=3:psy-rd=2.0:psy-rdoq=1.0:deblock=-1,-1:rc-lookahead=20:log-level=error", "-tag:v", "hvc1"]
    else:
        venc = ["-c:v", "libx264", "-preset", "slow", "-crf", crf, "-pix_fmt", "yuv420p", "-x264-params", "aq-mode=3:rc-lookahead=20:deblock=-1,-1"]
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
                pa = tims[i].prep_t(max(t - sh_ / fps, window(i)[0]))
                a_, b_ = window(i)
                tt = np.arange(a_, b_, 1.0 / fps)
                vmax = max([(tims[i].prep_t(x) - tims[i].prep_t(x - sh_ / fps)) * PREP_FPS for x in tt] + [1.0])
                readers[i] = Reader(s, os.path.join(luts, f"{s['id']}.cube"), pa, W, H, hist=int(math.ceil(vmax)) + 2)
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
                dirn = -1 if tr.get("dir", "left") == "left" else 1
                L = tr.get("blur", 0.9) * W * math.sin(math.pi * p)
                out_shift = dirn * W * 0.55 * smooth(p * 2) if p < 0.5 else 0
                in_shift = -dirn * W * 0.55 * (1 - smooth((p - 0.5) * 2)) if p >= 0.5 else 0
                a = dir_blur(warp(img, 1, 0.5, 0.5, out_shift), L) if p < 0.62 else None
                b = dir_blur(warp(fr, 1, 0.5, 0.5, in_shift), L) if p > 0.38 else None
                mix = smooth((p - 0.38) / 0.24)
                img = a if b is None else (b if a is None else a * (1 - mix) + b * mix)
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
                roi = img[ya:yb, xa:xb]
                roi[:] = 1 - (1 - np.clip(roi, 0, 1)) * (1 - np.clip(part, 0, 1))
        img = np.clip(img, 0, 1.5)
        cl = fin.get("clarity")
        if cl:
            lum = img @ LUMA
            small = cv2.resize(lum, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
            lb = cv2.resize(cv2.GaussianBlur(small, (0, 0), cl["sigma"] * W / 4), (W, H), interpolation=cv2.INTER_LINEAR)
            img = img + (cl["amount"] * (lum - lb) * (0.25 + lum * (1 - np.clip(lum, 0, 1)) * 3))[..., None]
        sh = fin.get("sharpen")
        if sh:
            lum = img @ LUMA
            img = img + (sh["amount"] * (lum - cv2.GaussianBlur(lum, (0, 0), sh["sigma"] * S)))[..., None]
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
