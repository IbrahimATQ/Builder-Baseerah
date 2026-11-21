#!/usr/bin/env python3
"""Render the coffee film's picture from data/plan.json.

For every output frame: the shot (or the two shots of a dissolve) is read from its prepared stretch through
ffmpeg with the shot's LUT applied in 16-bit (grade.py), pushed in or out by a slow sub-pixel zoom, mixed,
then finished as one image: a soft bloom around the highlights (the window light), a vignette, the titles
(fading in with a small rise and a focus pull), fades from and to black, and fine luminance grain that
also dithers the 16-bit picture down to 8 bits. Frames are written as H.264 by ffmpeg; long renders are
split into parallel jobs whose segments are joined without re-encoding.

Usage: python render.py PLAN.json LUT_DIR OUT.mp4 [--scale 0.5] [--from T] [--to T] [--jobs 3] [--crf 16]
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

LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)


def smooth(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


class Reader:
    """Sequential frames of one shot, graded, at the output size."""

    def __init__(self, shot: dict, lut: str, t0: float, W: int, H: int, fps: int):
        self.W, self.H, self.fps = W, H, fps
        local = shot["in"] + (t0 - shot["start"])
        vf = (f"scale={W}:{H}:flags=lanczos:in_color_matrix=bt709:in_range=tv,format=gbrp16le,"
              f"lut3d=file='{lut}':interp=tetrahedral,format=rgb48le")
        self.p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{max(local, 0):.4f}", "-i", shot["src"], "-vf", vf,
                                   "-f", "rawvideo", "-"], stdout=subprocess.PIPE, bufsize=W * H * 6 * 2)
        self.n = W * H * 6
        self.last = None

    def next(self) -> np.ndarray:
        b = self.p.stdout.read(self.n)
        if len(b) == self.n:
            self.last = np.frombuffer(b, np.uint16).reshape(self.H, self.W, 3).astype(np.float32) * (1 / 65535.0)
        if self.last is None:
            raise RuntimeError("no frame")
        return self.last

    def close(self) -> None:
        self.p.stdout.close()
        self.p.kill()
        self.p.wait()


def zoomed(img: np.ndarray, z: float, cx: float, cy: float) -> np.ndarray:
    if abs(z - 1.0) < 1e-4 and abs(cx - 0.5) < 1e-4 and abs(cy - 0.5) < 1e-4:
        return img
    H, W = img.shape[:2]
    px, py = cx * W, cy * H
    M = np.array([[z, 0, W / 2 - z * px], [0, z, H / 2 - z * py]], np.float32)
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)


class Title:
    """A block of centred lines drawn once at full quality; animated per frame."""

    def __init__(self, t: dict, fonts: str, W: int, H: int, scale: float):
        self.t = t
        s = W / 2160.0
        imgs = []
        for ln in t["lines"]:
            f = ImageFont.truetype(os.path.join(fonts, ln["font"]), max(8, int(ln["size"] * s)), layout_engine=ImageFont.Layout.RAQM)
            track = ln.get("track", 0.0) * ln["size"] * s
            chars = list(ln["text"])
            widths = [f.getlength(c) for c in chars]
            tw = int(sum(widths) + track * (len(chars) - 1)) + 4
            asc, desc = f.getmetrics()
            im = Image.new("L", (max(tw, 4), asc + desc + 8), 0)
            d = ImageDraw.Draw(im)
            if track <= 0:
                d.text((2, 4), ln["text"], font=f, fill=255)
            else:
                x = 2.0
                for c, w in zip(chars, widths):
                    d.text((x, 4), c, font=f, fill=255)
                    x += w + track
            imgs.append((np.asarray(im, np.float32) / 255.0, int(ln.get("gap", 0) * s)))
        rule = t.get("rule")
        rule_h = max(1, int(3 * s)) if rule else 0
        rule_gap = int(rule.get("gap", 30) * s) if rule else 0
        width = max(i.shape[1] for i, _ in imgs)
        if rule:
            width = max(width, int(rule["width"] * W))
        height = sum(i.shape[0] + g for i, g in imgs) + (rule_h + rule_gap if rule else 0)
        pad = int(260 * s)  # room for the soft shade around the block
        A = np.zeros((height + 2 * pad, width + 2 * pad), np.float32)
        y = pad
        for k, (im, g) in enumerate(imgs):
            y += g
            x = pad + (width - im.shape[1]) // 2
            A[y:y + im.shape[0], x:x + im.shape[1]] = np.maximum(A[y:y + im.shape[0], x:x + im.shape[1]], im)
            y += im.shape[0]
            if k == 0 and rule:
                y += rule_gap // 2
                rw = int(rule["width"] * W)
                x0 = pad + (width - rw) // 2
                A[y:y + rule_h, x0:x0 + rw] = 0.8
                y += rule_h + rule_gap // 2
        self.A = A
        self.shadow = cv2.GaussianBlur(A, (0, 0), 6 * s)
        box = np.zeros_like(A)
        box[pad:pad + height, pad:pad + width] = 1.0
        sh = cv2.GaussianBlur(box, (0, 0), 85 * s)
        self.shade = (sh / max(float(sh.max()), 1e-6)).astype(np.float32)  # a soft pool of shade under the words
        self.x0 = int(round(t.get("x", 0.5) * W - A.shape[1] / 2))  # "x": the block's centre, a fraction of the width
        self.yc = int(t["y"] * H)
        self.s = s
        self.color = np.array(t.get("color", [0.965, 0.94, 0.895]), np.float32)

    def draw(self, img: np.ndarray, time: float) -> None:
        t = self.t
        if time < t["in"] or time > t["out"]:
            return
        a_in = smooth((time - t["in"]) / max(t["fade_in"], 1e-3))
        a_out = 1.0 if t["fade_out"] <= 0 else smooth((t["out"] - time) / t["fade_out"])
        a = min(a_in, a_out)
        if a <= 0.002:
            return
        rise = t.get("rise", 0) * self.s * (1 - a_in)
        blur = t.get("focus", 0) * self.s * (1 - a_in) ** 1.5
        A, Sh = self.A, self.shadow
        if blur > 0.3:
            A = cv2.GaussianBlur(A, (0, 0), blur)
        h, w = A.shape
        y0 = int(round(self.yc - h / 2 + rise))
        H, W = img.shape[:2]
        ya, yb = max(0, y0), min(H, y0 + h)
        xa, xb = max(0, self.x0), min(W, self.x0 + w)
        if yb <= ya or xb <= xa:
            return
        a_crop = A[ya - y0:yb - y0, xa - self.x0:xb - self.x0][..., None] * a
        s_crop = Sh[ya - y0:yb - y0, xa - self.x0:xb - self.x0][..., None] * a * float(t.get("shadow", 0.6))
        p_crop = self.shade[ya - y0:yb - y0, xa - self.x0:xb - self.x0][..., None] * a * float(t.get("shade", 0.0))
        roi = img[ya:yb, xa:xb]
        roi *= (1 - p_crop) * (1 - s_crop * 0.9)   # a pool of shade and a soft shadow keep the letters clear on bright walls
        roi[:] = roi * (1 - a_crop) + self.color * a_crop


def render_range(plan: dict, luts: str, out: str, f0: int, f1: int, scale: float, crf: str) -> None:
    fps = plan["fps"]
    W, H = int(plan["w"] * scale) // 2 * 2, int(plan["h"] * scale) // 2 * 2
    shots = plan["shots"]
    fin = plan["finish"]
    titles = [Title(t, plan["fonts"], W, H, scale) for t in plan["titles"]]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 * 0.75 + ((yy - H / 2) / (H / 2)) ** 2)
    vign = (1 - fin["vignette"] * np.clip(r - 0.35, 0, None) ** 1.6).astype(np.float32)[..., None]
    rng = np.random.default_rng(7)
    gh, gw = H // 2, W // 2
    grains = []
    for _ in range(12):  # film grain: a little larger than a pixel, regenerated per frame from a bank
        g = rng.standard_normal((gh, gw)).astype(np.float32)
        g = cv2.resize(g, (W, H), interpolation=cv2.INTER_CUBIC)
        grains.append((g / (g.std() + 1e-6)).astype(np.float16))
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
                            "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p,lutyuv=y='clip(val,20,230)'",  # room for the encoder's ringing "-c:v", "libx264", "-preset", "slow", "-crf", crf,
                            "-x264-params", "aq-mode=3:rc-lookahead=20", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                            "-color_range", "tv", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    readers: dict[int, Reader] = {}
    for f in range(f0, f1):
        t = f / fps
        live = []
        for i, s in enumerate(shots):
            tr = s.get("trans", {})
            half = tr.get("dur", 0) / 2 if tr.get("type") == "dissolve" else 0
            nxt = shots[i + 1] if i + 1 < len(shots) else None
            nhalf = (nxt.get("trans", {}).get("dur", 0) / 2 if nxt and nxt.get("trans", {}).get("type") == "dissolve" else 0)
            if s["start"] - half <= t < s["end"] + nhalf:
                live.append(i)
        for i in list(readers):
            if i not in live:
                readers.pop(i).close()
        img = None
        for i in live:
            s = shots[i]
            if i not in readers:
                readers[i] = Reader(s, os.path.join(luts, f"{s['id']}.cube"), t, W, H, fps)
            fr = readers[i].next()
            mv = s.get("move", {})
            k = (t - s["start"]) / max(s["end"] - s["start"], 1e-3)
            z0, z1 = mv.get("z", [1.0, 1.0])
            fr = zoomed(fr, z0 + (z1 - z0) * min(max(k, -0.2), 1.2), mv.get("cx", 0.5), mv.get("cy", 0.5))
            kg = s.get("key_green")
            if kg:  # an LED glowing green through glass: inside a soft band of the frame, take its colour and half its light
                g_ = fr[..., 1] - np.maximum(fr[..., 0], fr[..., 2])
                m = np.clip((g_ / np.maximum(fr[..., 1], 1e-3) - kg.get("lo", 0.06)) / (kg.get("hi", 0.22) - kg.get("lo", 0.06)), 0, 1)
                ramp = np.clip((np.arange(H, dtype=np.float32) / H - kg.get("y0", 0.35)) / 0.08, 0, 1)[:, None]
                m = cv2.GaussianBlur(m * ramp, (0, 0), 2.0 * W / 2160)[..., None] * kg.get("strength", 1.0)
                lum_ = (fr @ LUMA)[..., None]
                fr = fr * (1 - m) + lum_ * (1 - 0.5 * m) * m
            lt = s.get("light")
            if lt:  # a soft window of light that follows a subject (keys: [shot-local s, cx, cy, rx, ry] in frame fractions)
                ks = sorted(lt["keys"])
                lt_t = t - s["start"]
                cx_, cy_, rx_, ry_ = (float(np.interp(lt_t, [q[0] for q in ks], [q[i] for q in ks])) for i in (1, 2, 3, 4))
                yy_, xx_ = np.ogrid[0:H, 0:W]
                d2 = ((xx_ / W - cx_) / rx_) ** 2 + ((yy_ / H - cy_) / ry_) ** 2
                m = np.exp(-d2 * 1.4).astype(np.float32)[..., None]
                warm = np.array(lt.get("tint", [1.0, 0.985, 0.95]), np.float32)
                fr = fr * (1 + m * ((2 ** lt.get("ev", 0.5)) * warm - 1))
            if img is None:
                img = fr.copy()
            else:  # the later shot dissolves in
                tr = s.get("trans", {})
                a = smooth((t - (s["start"] - tr["dur"] / 2)) / tr["dur"])
                img = img * (1 - a) + fr * a
        # bloom: the window light breathes into its surroundings, warm
        b = fin["bloom"]
        small = cv2.resize(img, (W // 8, H // 8), interpolation=cv2.INTER_AREA)
        hi = np.clip((small @ LUMA - b["threshold"]) / (1 - b["threshold"]), 0, 1)[..., None] * small
        hi = cv2.GaussianBlur(hi, (0, 0), b["radius"] * W / 8)
        img = img + b["gain"] * cv2.resize(hi, (W, H), interpolation=cv2.INTER_LINEAR) * np.array(b["tint"], np.float32)
        img *= vign
        for tl in titles:
            tl.draw(img, t)
        fade = min(1.0, smooth(t / fin["fade_in"]) if fin["fade_in"] > 0 else 1.0)
        fo0, fo1 = fin["fade_out"]
        if t > fo0:
            fade *= smooth((fo1 - t) / (fo1 - fo0))
        img *= fade
        lum = np.clip(img @ LUMA, 0, 1)[..., None]
        g = grains[f % len(grains)].astype(np.float32)[..., None]
        img = img + g * fin["grain"] * (0.35 + 1.3 * lum * (1 - lum))
        out8 = np.clip(img * 255.0 + 0.5, 0, 255).astype(np.uint8)
        enc.stdin.write(out8.tobytes())
    for rd in readers.values():
        rd.close()
    enc.stdin.close()
    enc.wait()


def main() -> None:
    args = sys.argv[1:]
    opts = {"--scale": "1.0", "--from": None, "--to": None, "--jobs": "3", "--crf": "16"}
    for k in list(opts):
        if k in args:
            i = args.index(k); opts[k] = args[i + 1]; del args[i:i + 2]
    plan_p, luts, out = args[0], args[1], args[2]
    plan = json.load(open(plan_p, encoding="utf-8"))
    fps = plan["fps"]
    f0 = int(round(float(opts["--from"] or 0) * fps))
    f1 = int(round(float(opts["--to"] or plan["duration"]) * fps))
    scale, jobs = float(opts["--scale"]), max(1, int(opts["--jobs"]))
    if os.environ.get("COFFEE_RANGE"):
        a, b = map(int, os.environ["COFFEE_RANGE"].split(","))
        render_range(plan, luts, out, a, b, scale, opts["--crf"])
        return
    tmp = tempfile.mkdtemp(prefix="render_", dir=os.path.dirname(os.path.abspath(out)))
    cuts = [f0 + (f1 - f0) * k // jobs for k in range(jobs + 1)]
    procs, parts = [], []
    for k in range(jobs):
        part = os.path.join(tmp, f"part{k}.mp4")
        parts.append(part)
        env = {**os.environ, "COFFEE_RANGE": f"{cuts[k]},{cuts[k + 1]}"}
        procs.append(subprocess.Popen([sys.executable, __file__, plan_p, luts, part, "--scale", str(scale), "--crf", opts["--crf"]], env=env))
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
