#!/usr/bin/env python3
"""Build the picture of the 4K journey: real footage, moved, graded and joined as one film.

Every shot is a 9:16 window cut from its source that drifts and pushes slowly (a camera move over
moving footage, never a zoom on a still), graded into one shared look, and joined to the next
shot by its own transition:
  cut       hard cut
  dissolve  cross-dissolve
  dip       through black
  smoke     soft, uneven luma wipe (like smoke clearing)
  burn      the next shot burns through the last: a ragged front of glowing char crosses the frame
  ignite    the burn front grows from a point (a match, an ember) instead of from an edge

Plan (JSON):
  {"fps": 24, "w": 2160, "h": 3840, "duration": 41.5, "look": {grade...},
   "shots": [{"id", "src", "in": s, "start": t (fully on at t; shown until the next shot's start),
              "speed": 1, "flip": false, "window": {"cx": .5, "cy": .5, "fill": 1},
              "move": {"z": [1, 1.06], "dx": [0, 0], "dy": [0, 0]},
              "grade": {overrides}, "sharpen": 0.25,
              "trans": {"type": "burn", "dur": 0.9, "seed": 1, "origin": [0.5, 1.0]},
              "toBlack": 0}],
   "end": t (last shot's end)}
Grade keys: ev (stops), temp (-1..1, warm +), tint, sat, bw (0..1), contrast, floor (black point pulled down), black, halation,
            split (0..1 warm-highlight / cool-shadow amount), vignette.

Writes OUT.mp4 (H.264, BT.709, CRF 14) and OUT.light.json: per-frame scene light (mean
luminance and warmth of the middle of the frame) that the typography follows.

Usage: python build_picture.py plan.json OUT.mp4 [--scale 0.25] [--from T] [--to T] [--jobs 4]
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache

import cv2
import numpy as np

LOOK_DEFAULT = {"ev": 0.0, "temp": 0.0, "tint": 0.0, "sat": 0.92, "bw": 0.0, "contrast": 1.0, "black": 0.012,
                "halation": 0.22, "split": 0.5, "vignette": 0.30, "pre": 0.78}


# ---------------------------------------------------------------- sources

def probe(src: str) -> tuple[int, int, float, float]:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate:format=duration", "-of", "json", src],
                         capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    s = j["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    return int(s["width"]), int(s["height"]), float(num) / float(den), float(j["format"]["duration"])


def ease(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 0.5 - 0.5 * math.cos(math.pi * x)


def lerp2(pair, k: float) -> float:
    a, b = pair if isinstance(pair, (list, tuple)) else (pair, pair)
    return a + (b - a) * k


class Shot:
    def __init__(self, d: dict, t_on: float, t_off: float, out_w: int, out_h: int):
        self.d = d
        self.t_on, self.t_off = t_on, t_off  # visible span on the film timeline (transition included)
        self.W, self.H, self.fps_src, self.dur_src = probe(d["src"])
        self.out_w, self.out_h = out_w, out_h
        self.speed = float(d.get("speed", 1.0))
        win = d.get("window", {})
        self.cx, self.cy, self.fill = win.get("cx", 0.5), win.get("cy", 0.5), win.get("fill", 1.0)
        mv = d.get("move", {})
        self.z, self.dx, self.dy = mv.get("z", [1.0, 1.06]), mv.get("dx", [0, 0]), mv.get("dy", [0, 0])
        aspect = out_w / out_h
        if self.W / self.H > aspect:
            self.ww0, self.wh0 = self.H * aspect, float(self.H)
        else:
            self.ww0, self.wh0 = float(self.W), self.W / aspect
        need = d["in"] + (t_off - t_on) * self.speed
        if need > self.dur_src + 0.05:
            raise SystemExit(f"{d['id']}: needs source up to {need:.2f}s but {d['src']} is {self.dur_src:.2f}s")

    def window(self, t: float) -> tuple[float, float, float, float]:
        """Source-pixel window (x0, y0, w, h) at film time t. The move runs over the whole visible span,
        or follows "keys": [[film_t, zoom, cx, cy], ...] (absolute centre, eased between keys)."""
        keys = self.d.get("move", {}).get("keys")
        if keys:
            ks = sorted(keys)
            if t <= ks[0][0]:
                z, kx, ky = ks[0][1:]
            elif t >= ks[-1][0]:
                z, kx, ky = ks[-1][1:]
            else:
                j = max(i for i in range(len(ks)) if ks[i][0] <= t)
                a_, b_ = ks[j], ks[j + 1]
                u = ease((t - a_[0]) / max(b_[0] - a_[0], 1e-6))
                z, kx, ky = [a_[i] + (b_[i] - a_[i]) * u for i in (1, 2, 3)]
            z *= self.fill
            w, h = self.ww0 / z, self.wh0 / z
            x0 = min(max(kx * self.W - w / 2, 0), self.W - w)
            y0 = min(max(ky * self.H - h / 2, 0), self.H - h)
            return x0, y0, w, h
        k = ease((t - self.t_on) / max(self.t_off - self.t_on, 1e-3)) if self.d.get("easeMove", True) else \
            min(1, max(0, (t - self.t_on) / max(self.t_off - self.t_on, 1e-3)))
        z = self.fill * lerp2(self.z, k)
        w, h = self.ww0 / z, self.wh0 / z
        cx = self.cx * self.W + lerp2(self.dx, k) * w
        cy = self.cy * self.H + lerp2(self.dy, k) * h
        x0 = min(max(cx - w / 2, 0), self.W - w)
        y0 = min(max(cy - h / 2, 0), self.H - h)
        return x0, y0, w, h

    def src_time(self, t: float) -> float:
        return self.d["in"] + (t - self.t_on) * self.speed

    def bbox(self, t0: float, t1: float) -> tuple[int, int, int, int]:
        xs, ys, xe, ye = [], [], [], []
        for t in np.linspace(t0, t1, 24):
            x0, y0, w, h = self.window(t)
            xs.append(x0); ys.append(y0); xe.append(x0 + w); ye.append(y0 + h)
        x0, y0 = max(0, int(min(xs)) - 4), max(0, int(min(ys)) - 4)
        x1, y1 = min(self.W, int(math.ceil(max(xe))) + 4), min(self.H, int(math.ceil(max(ye))) + 4)
        x0 -= x0 % 2; y0 -= y0 % 2
        w, h = (x1 - x0) // 2 * 2, (y1 - y0) // 2 * 2
        return x0, y0, w, h


class Reader:
    """Sequential frames of one shot's crop; serves any increasing source time with optional blending."""

    def __init__(self, shot: Shot, t0: float, t1: float):
        self.shot = shot
        self.bx, self.by, self.bw, self.bh = shot.bbox(t0, t1)
        self.s0 = max(0.0, shot.src_time(t0) - 2.0 / shot.fps_src)
        s1 = shot.src_time(t1) + 3.0 / shot.fps_src
        self.proc = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-ss", f"{self.s0:.4f}", "-i", shot.d["src"], "-t", f"{s1 - self.s0:.4f}",
             "-vf", f"crop={self.bw}:{self.bh}:{self.bx}:{self.by},format=rgb24", "-f", "rawvideo", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=self.bw * self.bh * 3 * 2)
        self.k = -1
        self.buf: dict[int, np.ndarray] = {}

    def _frame(self, k: int) -> np.ndarray:
        n = self.bw * self.bh * 3
        while self.k < k:
            raw = self.proc.stdout.read(n)
            if len(raw) < n:
                break
            self.k += 1
            self.buf[self.k] = np.frombuffer(raw, np.uint8).reshape(self.bh, self.bw, 3)
            for old in [i for i in self.buf if i < self.k - 2]:
                del self.buf[old]
        return self.buf[min(k, self.k)]

    def at(self, s: float) -> np.ndarray:
        f = (s - self.s0) * self.shot.fps_src
        k = int(math.floor(f + 1e-6))
        frac = f - k
        a = self._frame(k)
        if frac < 0.2 or self.shot.d.get("blend", True) is False:
            return a
        if frac > 0.8:
            return self._frame(k + 1)
        b = self._frame(k + 1)
        return cv2.addWeighted(a, 1 - frac, b, frac, 0)

    def close(self) -> None:
        try:
            self.proc.stdout.close()
            self.proc.kill()
        except Exception:
            pass


# ---------------------------------------------------------------- look

@lru_cache(maxsize=8)
def vignette(w: int, h: int, amount: float) -> np.ndarray:
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    nx, ny = (x / w - 0.5) * 2, (y / h - 0.5) * 2
    r = np.sqrt((nx * 0.95) ** 2 + (ny * 0.78) ** 2)
    v = 1 - amount * np.clip((r - 0.45) / 0.85, 0, 1) ** 1.6
    return v[..., None].astype(np.float32)


def aces(x: np.ndarray) -> np.ndarray:
    return np.clip((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0, 1)


def grade(img: np.ndarray, g: dict) -> np.ndarray:
    """uint8 sRGB -> graded float32 display RGB (0..1)."""
    x = img.astype(np.float32) * (1 / 255.0)
    lin = x * x * (0.3 + 0.7 * x)  # cheap sRGB -> linear approximation (exact at 0 and 1)
    lin *= g["pre"] * 2.0 ** g["ev"]
    t, ti = g["temp"], g["tint"]
    lin *= np.array([1 + 0.12 * t - 0.03 * ti, 1 + 0.06 * ti, 1 - 0.14 * t - 0.03 * ti], np.float32)
    lum = lin @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    sat = g["sat"] * (1 - g["bw"])
    lin = lum[..., None] + (lin - lum[..., None]) * sat
    if g["halation"] > 0:
        h, w = lin.shape[:2]
        small = cv2.resize(lin, (w // 8, h // 8), interpolation=cv2.INTER_AREA)
        hi = np.clip(small - 0.55, 0, None)
        hi = cv2.GaussianBlur(hi, (0, 0), sigmaX=max(w, h) / 8 / 60)
        hi = hi.mean(axis=2, keepdims=True) * np.array([1.0, 0.32, 0.10], np.float32)
        lin += g["halation"] * cv2.resize(hi, (w, h), interpolation=cv2.INTER_LINEAR)
    out = aces(lin * g["contrast"]) ** (1 / 2.2)
    if g["split"] > 0:
        l = out @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        sh = np.clip(1 - l / 0.45, 0, 1)[..., None]
        hl = np.clip((l - 0.5) / 0.5, 0, 1)[..., None]
        s = g["split"]
        out = out + s * (sh * np.array([-0.012, 0.004, 0.022], np.float32) + hl * np.array([0.03, 0.008, -0.03], np.float32))
    if g.get("floor", 0.0) > 0:  # pull a milky shot's black point down to the film's common floor
        out = np.clip((out - g["floor"]) / (1 - g["floor"]), 0, 1)
    out = g["black"] + (1 - g["black"]) * out
    if g["vignette"] > 0:
        out *= vignette(out.shape[1], out.shape[0], g["vignette"])
    return np.clip(out, 0, 1)


# ---------------------------------------------------------------- transitions

@lru_cache(maxsize=16)
def fbm(w: int, h: int, seed: int, base: int = 6, octaves: int = 5) -> np.ndarray:
    rng = np.random.default_rng(seed)
    acc = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        cells = base * 2 ** o
        g = rng.random((max(2, int(cells * h / w)) + 1, cells + 1)).astype(np.float32)
        acc += amp * cv2.resize(g, (w, h), interpolation=cv2.INTER_CUBIC)
        tot += amp
        amp *= 0.5
    acc /= tot
    return (acc - acc.min()) / (acc.max() - acc.min() + 1e-6)


@lru_cache(maxsize=16)
def front_field(w: int, h: int, kind: str, seed: int, ox: float, oy: float) -> np.ndarray:
    """0..1 arrival order of the burn/smoke front over the frame."""
    n = fbm(w, h, seed)
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((x / w - ox) * w / h) ** 2 + (y / h - oy) ** 2)
    d = d / d.max()
    rag = {"burn": 0.22, "ignite": 0.16, "smoke": 0.45}[kind]
    f = d + rag * (n - 0.5)  # a coherent front from the origin, made ragged by the noise
    return ((f - f.min()) / (f.max() - f.min())).astype(np.float32)


def transition(a: np.ndarray, b: np.ndarray, p: float, tr: dict) -> np.ndarray:
    """Composite outgoing a and incoming b (float display RGB) at progress p (0..1)."""
    kind = tr.get("type", "dissolve")
    if kind == "dissolve":
        k = ease(p)
        return a * (1 - k) + b * k
    if kind == "dip":
        return a * ease(1 - 2 * p) if p < 0.5 else b * ease(2 * p - 1)
    h, w = a.shape[:2]
    sw, sh = max(64, w // 4), max(64, h // 4)
    ox, oy = tr.get("origin", [0.5, 1.0])
    F = front_field(sw, sh, kind if kind in ("burn", "ignite", "smoke") else "smoke", int(tr.get("seed", 1)), ox, oy)
    if kind == "smoke":
        soft = 0.22
        q = -soft + (1 + 2 * soft) * ease(p)
        m = np.clip((q - F) / soft + 0.5, 0, 1)
        m = cv2.resize(m, (w, h), interpolation=cv2.INTER_CUBIC)[..., None]
        return a * (1 - m) + b * m
    # burn / ignite: revealed where F < q; a hot rim just past the front, char just ahead of it.
    q = -0.04 + 1.10 * (p ** 0.9)
    edge = 0.018
    d = F - q
    reveal = np.clip(0.5 - d / edge, 0, 1)
    rim = np.exp(-np.clip(d, 0, None) / 0.008) * (d > -0.002)
    char = np.clip(1 - np.clip(d, 0, None) / 0.05, 0, 1) ** 1.5 * (1 - reveal)
    glow_noise = 0.6 + 0.4 * fbm(sw, sh, int(tr.get("seed", 1)) + 7, base=24, octaves=3)
    up = lambda z: cv2.resize(z.astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)[..., None]
    reveal, rim, char, gn = up(reveal), up(rim * glow_noise), up(char), up(glow_noise)
    hot = np.array([1.0, 0.40, 0.07], np.float32)
    soot = np.array([0.20, 0.13, 0.09], np.float32)  # browned, blackened paper just ahead of the fire
    strength = float(tr.get("glow", 0.85)) * (1 - ease((p - 0.85) / 0.15))
    old = a * (1 - char * (1 - soot))
    out = old * (1 - reveal) + b * reveal
    room = 1 - 0.7 * old.max(axis=2, keepdims=True)  # glow shows on dark/paper, does not white-out flames
    return np.clip(out + strength * rim * hot * (0.55 + 0.45 * gn) * room, 0, 1)


# ---------------------------------------------------------------- render

def timeline(plan: dict) -> list[tuple[dict, float, float]]:
    shots = plan["shots"]
    out = []
    for i, s in enumerate(shots):
        dur = float(s.get("trans", {}).get("dur", 0)) if i > 0 else 0.0
        t_on = s["start"] - dur
        t_off = shots[i + 1]["start"] if i + 1 < len(shots) else plan["end"]
        out.append((s, t_on, t_off))
    return out


def render_range(plan_p: str, out_p: str, f0: int, f1: int, scale: float) -> list[tuple[float, float]]:
    plan = json.load(open(plan_p, encoding="utf-8"))
    fps = plan["fps"]
    W, H = int(plan["w"] * scale) // 2 * 2, int(plan["h"] * scale) // 2 * 2
    look = {**LOOK_DEFAULT, **plan.get("look", {})}
    tl = timeline(plan)
    lo, hi = f0 / fps, (f1 - 1) / fps  # only shots seen in this frame range are opened (others may not exist yet)
    shots = [Shot(d, a, b, W, H) if (b > lo and a <= hi) else None for d, a, b in tl]
    readers: dict[int, Reader] = {}
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "14",
                            "-x264-params", "threads=2", "-pix_fmt", "yuv420p", "-color_range", "tv",
                            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", out_p],
                           stdin=subprocess.PIPE)
    light = []
    for fi in range(f0, f1):
        t = fi / fps
        layers = []
        for i, sh in enumerate(shots):
            if sh is None:
                continue
            if sh.t_on - 1e-6 <= t < sh.t_off + 1e-6 and (i == len(shots) - 1 or t < sh.t_off):
                if i not in readers:
                    readers[i] = Reader(sh, max(t, sh.t_on), min(sh.t_off, f1 / fps + 0.05))
                src = readers[i].at(sh.src_time(t))
                x0, y0, w, h = sh.window(t)
                r = readers[i]
                sx, sy = w / W, h / H
                M = np.array([[sx, 0, x0 - r.bx + 0.5 * sx - 0.5], [0, sy, y0 - r.by + 0.5 * sy - 0.5]], np.float32)
                if sx > 1.6:
                    pre = cv2.resize(src, (int(src.shape[1] / sx * 1.25), int(src.shape[0] / sy * 1.25)), interpolation=cv2.INTER_AREA)
                    k = src.shape[1] / pre.shape[1]
                    M = np.array([[sx / k, 0, (x0 - r.bx) / k + 0.5 * sx / k - 0.5], [0, sy / k, (y0 - r.by) / k + 0.5 * sy / k - 0.5]], np.float32)
                    src = pre
                fr = cv2.warpAffine(src, M, (W, H), flags=cv2.INTER_LANCZOS4 | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT)
                if sh.d.get("flip"):
                    fr = fr[:, ::-1]
                shp = float(sh.d.get("sharpen", 0.35 if sx < 0.4 else 0.15))
                if shp > 0:
                    bl = cv2.GaussianBlur(fr, (0, 0), 1.6 * scale + 0.4)
                    fr = cv2.addWeighted(fr, 1 + shp, bl, -shp, 0)
                dof = sh.d.get("dof")
                if dof:
                    yy = np.linspace(0, 1, H, dtype=np.float32)
                    m = np.clip((yy - dof["y0"]) / max(dof["y1"] - dof["y0"], 1e-3), 0, 1)
                    if dof.get("above"):
                        m = np.clip((dof["y1"] - yy) / max(dof["y1"] - dof["y0"], 1e-3), 0, 1)
                    bl = cv2.GaussianBlur(fr, (0, 0), dof["sigma"] * scale * 4)
                    m = m[:, None, None]
                    fr = (fr * (1 - m) + bl * m).astype(np.uint8)
                g = {**look, **sh.d.get("grade", {})}
                img = grade(fr, g)
                tb = float(sh.d.get("toBlack", 0))
                if tb > 0 and t > sh.t_off - tb:
                    img *= ease((sh.t_off - t) / tb)
                layers.append((i, img))
            elif i in readers and t >= sh.t_off:
                readers.pop(i).close()
        if not layers:
            img = np.zeros((H, W, 3), np.float32)
        elif len(layers) == 1:
            img = layers[0][1]
        else:
            (ia, a), (ib, b) = layers[-2], layers[-1]
            sb = shots[ib]
            tr = sb.d.get("trans", {"type": "dissolve", "dur": 0.5})
            p = (t - sb.t_on) / max(sb.d["start"] - sb.t_on, 1e-3)
            img = transition(a, b, min(1, max(0, p)), tr)
        u8 = (img * 255 + 0.5).astype(np.uint8)
        enc.stdin.write(u8.tobytes())
        mid = img[int(H * 0.25):int(H * 0.75):8, ::8]
        lum = float((mid @ np.array([0.2126, 0.7152, 0.0722], np.float32)).mean())
        warm = float(mid[..., 0].mean() - mid[..., 2].mean())
        # under the text: the brightest tenth of each line's band (does a bright plate wash out the words?)
        # and the share of foam-white pixels across the text zone (the sea washing over the words)
        lw = [0.2126, 0.7152, 0.0722]
        ba = img[int(H * 0.15):int(H * 0.23):6, ::6] @ np.array(lw, np.float32)
        bb = img[int(H * 0.23):int(H * 0.31):6, ::6] @ np.array(lw, np.float32)
        zone = img[int(H * 0.14):int(H * 0.32):6, ::6] @ np.array(lw, np.float32)
        light.append((round(lum, 4), round(warm, 4), round(float(np.percentile(ba, 90)), 4), round(float(np.percentile(bb, 90)), 4),
                      round(float((zone > 0.62).mean()), 4)))
    for r in readers.values():
        r.close()
    enc.stdin.close()
    enc.wait()
    return light


def main() -> None:
    args = sys.argv[1:]
    opts = {"--scale": 1.0, "--from": None, "--to": None, "--jobs": 4}
    for k in list(opts):
        if k in args:
            i = args.index(k); opts[k] = float(args[i + 1]); del args[i:i + 2]
    plan_p, out_p = args
    plan = json.load(open(plan_p, encoding="utf-8"))
    fps = plan["fps"]
    f0 = int(round((opts["--from"] or 0) * fps))
    f1 = int(round((opts["--to"] if opts["--to"] is not None else plan["duration"]) * fps))
    jobs = max(1, int(opts["--jobs"]))
    # split at whole frames; each chunk renders its own segment, then they are joined without re-encoding
    edges = [f0 + (f1 - f0) * j // jobs for j in range(jobs + 1)]
    tmp = tempfile.mkdtemp(prefix="pic_", dir=os.path.dirname(os.path.abspath(out_p)))
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
    json.dump({"fps": fps, "from_frame": f0, "lum": [x[0] for x in light], "warm": [x[1] for x in light],
               "band_a": [x[2] for x in light], "band_b": [x[3] for x in light], "foam": [x[4] for x in light]},
              open(os.path.splitext(out_p)[0] + ".light.json", "w"))
    print(json.dumps({"out": out_p, "frames": f1 - f0, "size_px": [int(plan["w"] * opts["--scale"]), int(plan["h"] * opts["--scale"])]}))


if __name__ == "__main__":
    main()
