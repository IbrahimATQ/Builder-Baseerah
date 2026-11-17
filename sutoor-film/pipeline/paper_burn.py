#!/usr/bin/env python3
"""Render a strip of paper carrying handwritten Arabic verse that burns, for a 9:16 reel.

Everything that belongs to the paper is computed in the paper's own (u, v) space and then put
into the frame with a perspective warp, so ink, scorch, ember rim, char and holes stay locked to
the paper. Real flame footage (on black) is screen-blended along the burning edge, and the fire
lights the paper and the ground. A faint handheld drift imitates a phone camera.

Config JSON keys (all optional except lines/out/duration):
  lines            list of strings (one per line on the paper, top to bottom; exact verse text)
  out              output .mp4 path (1080x1920, 30 fps, no audio)
  duration         seconds
  ignite_at        seconds when the fire starts (default 0.6)
  burn_time        seconds for the front to cross the paper (default 4.5)
  origin           [u, v] ignition point on the paper, 0..1 (default [0.92, 0.85])
  flames           list of flame clips on black (mp4)
  font             TTF path (default Aref Ruqaa); font_size (default 78)
  paper_wh         [w, h] paper size in px before warp (default [940, 360])
  center           [x, y] paper centre in the frame (default [540, 880]); tilt_deg (default -3)
  seed             int
  candle           true to add a warm static key light (opening "presentation" scenes)
Usage: python paper_burn.py config.json
"""
from __future__ import annotations

import json
import math
import subprocess
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30


def fbm(shape, rng, octaves=5, base=8):
    """Smooth fractal noise in [0,1] (sum of upsampled random grids)."""
    h, w = shape
    acc = np.zeros(shape, np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        n = base * (2 ** o)
        g = rng.random((max(2, int(n * h / max(h, w))) + 1, n + 1)).astype(np.float32)
        acc += amp * cv2.resize(g, (w, h), interpolation=cv2.INTER_CUBIC)
        tot += amp
        amp *= 0.5
    acc /= tot
    return (acc - acc.min()) / (np.ptp(acc) + 1e-6)


def render_ink(lines, font_path, size, pw, ph):
    """Exact text, shaped with HarfBuzz/raqm, right-aligned like a handwritten line; alpha mask 0..1."""
    img = Image.new("L", (pw, ph), 0)
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, size, layout_engine=ImageFont.Layout.RAQM)
    n = len(lines)
    for i, line in enumerate(lines):
        bbox = d.textbbox((0, 0), line, font=font, direction="rtl", language="ar")
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (pw - tw) / 2 - bbox[0]
        y = ph * (i + 0.5) / n - th / 2 - bbox[1] - ph * 0.02
        d.text((x, y), line, font=font, fill=255, direction="rtl", language="ar")
    return np.asarray(img, np.float32) / 255.0


def main(cfg_p: str) -> None:
    cfg = json.load(open(cfg_p, encoding="utf-8"))
    rng = np.random.default_rng(cfg.get("seed", 7))
    dur = float(cfg["duration"])
    n_frames = int(round(dur * FPS))
    pw, ph = cfg.get("paper_wh", [940, 360])
    font = cfg.get("font", "/home/user/Builder-Baseerah/sutoor-film/remotion/public/fonts/arefruqaa-ArefRuqaa-Regular.ttf")

    # ---------------- paper albedo (u, v space) ----------------
    fib = fbm((ph, pw), rng, 6, 12)
    streak = cv2.GaussianBlur(rng.random((ph, pw)).astype(np.float32), (0, 0), sigmaX=6, sigmaY=0.6)
    streak = (streak - streak.mean()) / (streak.std() + 1e-6)
    base = np.array([0.93, 0.885, 0.80], np.float32)
    albedo = base[None, None, :] * (0.95 + 0.06 * fib[..., None] + 0.012 * streak[..., None])
    yy, xx = np.mgrid[0:ph, 0:pw].astype(np.float32)
    edge = np.minimum.reduce([xx, pw - 1 - xx, yy, ph - 1 - yy])
    albedo *= (0.9 + 0.1 * np.clip(edge / 18.0, 0, 1))[..., None]  # slight edge wear
    # rough cut edges: alpha eaten by a little noise near the border
    rough = fbm((ph, pw), rng, 3, 40)
    paper_a0 = np.clip((edge - 1.5 - 2.5 * rough) / 1.5, 0, 1)

    # ---------------- ink ----------------
    ink = render_ink(cfg["lines"], font, cfg.get("font_size", 78), pw, ph)
    ink_tex = 0.82 + 0.18 * fbm((ph, pw), rng, 4, 30)
    ink = np.clip(cv2.GaussianBlur(ink, (0, 0), 0.7) * ink_tex, 0, 1)
    bleed = cv2.GaussianBlur(ink, (0, 0), 2.2) * 0.18
    ink_a = np.clip(ink + bleed, 0, 1)
    ink_col = np.array([0.07, 0.055, 0.05], np.float32)
    paper_rgb = albedo * (1 - ink_a[..., None]) + ink_col * ink_a[..., None]

    # ---------------- burn field ----------------
    u0, v0 = cfg.get("origin", [0.92, 0.85])
    du = (xx / pw - u0) * (pw / ph)
    dv = yy / ph - v0
    dist = np.sqrt(du * du + dv * dv)
    dist /= dist.max()
    burn = dist + 0.16 * fbm((ph, pw), rng, 5, 6) + 0.035 * fbm((ph, pw), rng, 3, 60)
    burn = (burn - burn.min()) / (np.ptp(burn) + 1e-6)
    ign, btime = float(cfg.get("ignite_at", 0.6)), float(cfg.get("burn_time", 4.5))
    crumple = fbm((ph, pw), rng, 5, 10)
    gy, gx = np.gradient(cv2.GaussianBlur(crumple, (0, 0), 2.0))
    bump = np.clip(0.75 + 9.0 * (gx * 0.6 - gy * 0.8), 0.35, 1.35).astype(np.float32)  # lit from top-right
    cracks = fbm((ph, pw), rng, 4, 26)
    cracks = np.clip(1 - np.abs(cracks - 0.5) / 0.035, 0, 1)  # thin glowing vein network

    # ---------------- placement (perspective) ----------------
    cx, cy = cfg.get("center", [540, 880])
    tilt = math.radians(cfg.get("tilt_deg", -3.0))
    sw, sh_top, sh_bot = pw * 0.98, ph * 0.86, ph * 1.0  # mild keystone: camera above, tilted
    corners = np.array([[-sw / 2 * 0.94, -sh_top / 2], [sw / 2 * 0.94, -sh_top / 2], [sw / 2, sh_bot / 2], [-sw / 2, sh_bot / 2]], np.float32)
    rot = np.array([[math.cos(tilt), -math.sin(tilt)], [math.sin(tilt), math.cos(tilt)]], np.float32)
    dst0 = corners @ rot.T + np.array([cx, cy], np.float32)
    src = np.array([[0, 0], [pw, 0], [pw, ph], [0, ph]], np.float32)

    # ---------------- ground ----------------
    g1 = fbm((H, W), rng, 6, 10)
    grit = rng.random((H, W)).astype(np.float32)
    grit = cv2.GaussianBlur(grit, (0, 0), 0.8)
    ground = (0.035 + 0.035 * g1 + 0.03 * (grit - 0.5))[..., None] * np.array([1.0, 0.93, 0.85], np.float32)

    # ---------------- flames ----------------
    flame_caps = [cv2.VideoCapture(f) for f in cfg.get("flames", [])]
    flame_frames = []
    for cap in flame_caps:
        fr = []
        ok, im = cap.read()
        while ok:
            fr.append(im)
            ok, im = cap.read()
        flame_frames.append(fr)
    anchors_uv = [(rng.uniform(0.03, 0.97), rng.uniform(0.1, 0.95)) for _ in range(int(cfg.get("n_flames", 30)))]
    smoke_frames = []
    if cfg.get("smoke"):
        cap = cv2.VideoCapture(cfg["smoke"])
        ok, im = cap.read()
        while ok and len(smoke_frames) < 400:
            ex = im[:, 1150:1850]  # the rising column in Mixkit 50956
            smoke_frames.append(cv2.resize(ex, (560, 860)))
            ok, im = cap.read()
    anchor_clip = [int(rng.integers(len(flame_frames))) if flame_frames else 0 for _ in anchors_uv]
    anchor_off = [int(rng.integers(0, 200)) for _ in anchors_uv]
    anchor_scale = [rng.uniform(0.55, 0.95) for _ in anchors_uv]
    anchor_flip = [bool(rng.integers(2)) for _ in anchors_uv]

    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                             "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p", cfg["out"]], stdin=subprocess.PIPE)
    jitter = fbm((4, n_frames + 8), rng, 2, 6)
    for f in range(n_frames):
        t = f / FPS
        # front position: slow catch, then steady spread (ease-in)
        p = np.clip((t - ign) / btime, 0, 1.2)
        front = (p ** 1.35) * 1.15 - 0.02 if t >= ign else -1.0
        s = front - burn  # >0: burnt
        scorch = np.clip((s + 0.09) / 0.09, 0, 1) ** 1.6 * (s < 0)
        rim = np.exp(-((s - 0.008) / 0.009) ** 2) * (s > -0.006)
        rim_core = np.exp(-((s - 0.006) / 0.0035) ** 2) * (s > -0.004)
        charred = np.clip((s - 0.008) / 0.01, 0, 1)
        gone_thr = (0.22 + 0.22 * rough) * np.clip(edge / 55.0, 0.12, 1.0)  # edges crumble first
        gone = np.clip((s - gone_thr) / 0.03, 0, 1)
        cooling = np.clip(1 - (s - 0.012) / 0.16, 0, 1) * charred
        flick = 0.65 + 0.35 * fbm((ph // 8, pw // 8), np.random.default_rng(f), 2, 4)
        flick = cv2.resize(flick, (pw, ph))
        col = paper_rgb * (1 + 0.07 * (bump - 0.85))[..., None]  # faint crumple relief
        brown = np.array([0.42, 0.26, 0.12], np.float32)
        col = col * (1 - 0.85 * scorch[..., None]) + brown * (0.85 * scorch[..., None])
        charc = np.array([0.05, 0.043, 0.038], np.float32) * (0.6 + 0.8 * rough[..., None]) * bump[..., None]
        ash = np.clip((rough - 0.62) / 0.2, 0, 1) * charred * np.clip((s - 0.05) / 0.1, 0, 1) * 0.12
        col = col * (1 - charred[..., None]) + (charc + ash[..., None]) * charred[..., None]
        emis = (rim * flick)[..., None] * np.array([1.25, 0.42, 0.08], np.float32)
        emis += (rim_core * flick)[..., None] * np.array([1.0, 0.85, 0.45], np.float32)
        emis += (cracks * cooling * flick * 0.9)[..., None] * np.array([1.0, 0.28, 0.04], np.float32)
        emis += (cooling * 0.18 * flick)[..., None] * np.array([0.8, 0.16, 0.03], np.float32)
        alpha = paper_a0 * (1 - gone)

        # handheld drift
        jx, jy = 4.0 * (jitter[0, f] - 0.5), 4.0 * (jitter[1, f] - 0.5)
        ja = math.radians(0.35 * (jitter[2, f] - 0.5))
        R = np.array([[math.cos(ja), -math.sin(ja)], [math.sin(ja), math.cos(ja)]], np.float32)
        dst = (dst0 - [W / 2, H / 2]) @ R.T + [W / 2 + jx, H / 2 + jy]
        M = cv2.getPerspectiveTransform(src, dst.astype(np.float32))
        warp = lambda a, flags=cv2.INTER_LINEAR: cv2.warpPerspective(a, M, (W, H), flags=flags, borderValue=0)  # noqa: E731
        p_rgb, p_a, p_em = warp(col), warp(alpha), warp(emis)

        # real flames along the burning edge -> a separate screen layer (also used as a light source)
        fl = np.zeros((H, W, 3), np.float32)
        if flame_frames and t >= ign:
            for k, (au, av) in enumerate(anchors_uv):
                iu, iv = int(au * (pw - 1)), int(av * (ph - 1))
                sv = s[iv, iu]
                if sv < -0.01 or sv > 0.2:
                    continue
                life = np.clip((sv + 0.01) / 0.03, 0, 1) * np.clip((0.2 - sv) / 0.1, 0, 1)
                fr = flame_frames[anchor_clip[k]]
                im = fr[(anchor_off[k] + int(t * 24)) % len(fr)]
                if anchor_flip[k]:
                    im = im[:, ::-1]
                sc = anchor_scale[k] * 0.62
                fh, fw = int(im.shape[0] * sc), int(im.shape[1] * sc)
                spr = cv2.resize(im, (fw, fh))[..., ::-1].astype(np.float32) / 255.0
                spr = np.clip((spr - 0.13) / 0.85, 0, 1) ** 1.25  # key out the clip's not-quite-black
                ex = np.minimum(np.linspace(0, 1, fw), np.linspace(1, 0, fw))
                ey = np.linspace(0, 1, fh)
                feather = np.clip(np.minimum(ex[None, :] / 0.25, 1) * np.minimum(ey[:, None] / 0.25, 1)
                                  * np.minimum((1 - ey[:, None]) / 0.18, 1), 0, 1)
                spr *= (feather * life)[..., None]
                pt = cv2.perspectiveTransform(np.array([[[iu, iv]]], np.float32), M)[0, 0]
                x0, y0 = int(pt[0] - fw / 2), int(pt[1] - fh * 0.86)
                xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + fw), min(H, y0 + fh)
                if xb <= xa or yb <= ya:
                    continue
                sub = spr[ya - y0:yb - y0, xa - x0:xb - x0]
                fl[ya:yb, xa:xb] = 1 - (1 - fl[ya:yb, xa:xb]) * (1 - sub)

        # faint real smoke rising off the burnt area
        if smoke_frames and t >= ign:
            burnt_frac = float((s > 0.02).mean())
            if burnt_frac > 0.01:
                cols = np.where((s > 0.0) & (s < 0.3))[1]
                cu = (cols.mean() / pw) if cols.size else 0.5
                pt = cv2.perspectiveTransform(np.array([[[cu * pw, ph * 0.4]]], np.float32), M)[0, 0]
                sm = smoke_frames[int(t * 24) % len(smoke_frames)]
                sm = np.clip((sm[..., ::-1].astype(np.float32) / 255.0 - 0.06) / 0.9, 0, 1)
                sh_, sw_ = sm.shape[:2]
                x0, y0 = int(pt[0] - sw_ / 2), int(pt[1] - sh_ * 0.95)
                xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + sw_), min(H, y0 + sh_)
                if xb > xa and yb > ya:
                    a_ = min(0.35, 0.12 + 0.4 * burnt_frac)
                    fl[ya:yb, xa:xb] = 1 - (1 - fl[ya:yb, xa:xb]) * (1 - a_ * sm[ya - y0:yb - y0, xa - x0:xb - x0] * np.array([0.8, 0.75, 0.7], np.float32))

        # light from the fire (rim + flames) and an optional candle/lighter key
        src_l = p_em.sum(axis=2) + 1.4 * fl.mean(axis=2)
        heat = cv2.resize(src_l, (W // 8, H // 8), interpolation=cv2.INTER_AREA)
        near = cv2.resize(cv2.GaussianBlur(heat, (0, 0), 6), (W, H))
        far = cv2.resize(cv2.GaussianBlur(heat, (0, 0), 26), (W, H))
        light = (0.9 * near + 2.2 * far)[..., None] * np.array([1.0, 0.56, 0.22], np.float32)
        amb = np.full((H, W, 1), float(cfg.get("ambient", 0.22)), np.float32)
        if cfg.get("candle"):
            ky, kx = np.mgrid[0:H, 0:W].astype(np.float32)
            amb = amb + 0.75 * np.exp(-(((kx - W * 0.82) / 520) ** 2 + ((ky - cy + 120) / 640) ** 2))[..., None]
        shade = amb * np.array([1.0, 0.82, 0.6], np.float32) + 2.2 * light
        frame = ground * (0.6 + 2.5 * shade)
        frame = frame * (1 - p_a[..., None]) + (p_rgb * shade) * p_a[..., None] + p_em
        frame = 1 - (1 - np.clip(frame, 0, 1)) * (1 - fl)

        # phone-like optics: gentle vignette, slight softness away from the paper
        frame = np.clip(frame, 0, 1)
        out = (frame ** (1 / 1.05) * 255).astype(np.uint8)
        proc.stdin.write(out.tobytes())
    proc.stdin.close()
    proc.wait()
    print(f"{cfg['out']}: {n_frames} frames")


if __name__ == "__main__":
    main(sys.argv[1])
