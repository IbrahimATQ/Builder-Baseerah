#!/usr/bin/env python3
"""Burning-paper scene, v6: cinema mode (4K, 24 fps) for the Journey edition.

What changed from v5 (night phone look, 1080x1920):
  * any output size; physical sizes scale with the frame (S = W/1080); full-resolution paper and ink
  * the fire READS the line: the burn front sweeps right to left in reading order and passes each
    word at a given film time (just after the reciter says it), with the eikonal raggedness kept
  * paper kinds: "manuscript" (aged ochre, foxing, one torn long edge, iron-gall ink) and "deckle"
    (thick handmade cream sheet, deckled edges, black ink)
  * grounds: "earth" (freshly turned grave soil: clods, pebbles, roots, damp patches, a soft
    out-of-focus grave marker) and "basalt" (black vesicular rock, salt in the cracks, wet sheen that
    mirrors the fire); v5 grounds still available
  * scene ambient light from config (blue hour, moonless night) plus an optional cold rim
  * "ember_word": one word's ink survives the burn as glowing strokes (blackbody orange with a hot
    core) on a char sheet that stays in place, then cools to black on a heat curve
  * bigger, scalable flames ("flame_scale"); fire light computed at quarter resolution
  * clean cinema finish (no phone downscale; grain is added once, in finishing)

Usage: python paper_burn6.py config.json
Config: see the Journey plan (data/journey/burn_*.json).
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys

import cv2
import numpy as np
import skfmm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paper_burn3 import noise, smooth  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402

W, H, FPS, S = 2160, 3840, 24, 2.0
lin = lambda x: np.power(np.clip(x, 0, None), 2.2)  # noqa: E731
disp = lambda x: np.power(np.clip(x, 0, None), 1 / 2.2)  # noqa: E731


def pen_line(text, font_path, size, pw, ph, rng):
    """Reed-pen line. Returns (ink alpha, [(x0, x1) per word in reading order, i.e. right to left])."""
    font = ImageFont.truetype(font_path, size * 2, layout_engine=ImageFont.Layout.RAQM)
    words = []
    for w in text.split(" "):
        b = font.getbbox(w, direction="rtl", language="ar")
        im = Image.new("L", (b[2] - b[0] + 40, int(size * 4.6)), 0)
        ImageDraw.Draw(im).text((20 - b[0], int(size * 1.0)), w, font=font, fill=255, direction="rtl", language="ar")
        a = np.asarray(im, np.float32) / 255.0
        h, w_ = a.shape
        ang = math.radians(rng.uniform(-1.2, 1.2)); sc = rng.uniform(0.97, 1.03); sh = rng.uniform(-0.05, 0.03)
        M = np.float32([[sc * math.cos(ang), -sc * math.sin(ang) + sh, 0], [sc * math.sin(ang), sc * math.cos(ang), 0]])
        M[:, 2] = np.float32([w_ / 2, h / 2]) - M[:, :2] @ np.float32([w_ / 2, h / 2])
        a = cv2.warpAffine(a, M, (w_, h), flags=cv2.INTER_CUBIC)
        gy_, gx_ = np.mgrid[0:h, 0:w_].astype(np.float32)
        wob = 2.5 * S
        a = cv2.remap(a, gx_ + (noise((h, w_), rng, 20 * S, 2) - 0.5) * wob, gy_ + (noise((h, w_), rng, 20 * S, 2) - 0.5) * wob, cv2.INTER_LINEAR)
        a = cv2.resize(a, (w_ // 2, h // 2), interpolation=cv2.INTER_AREA)
        ys, xs = np.nonzero(a > 0.05)
        if xs.size:
            a = a[:, max(0, xs.min() - 1):xs.max() + 2]
        words.append(a)
    gaps = [int(size * rng.uniform(0.18, 0.26)) for _ in words]
    total = sum(w.shape[1] for w in words) + sum(gaps[:-1])
    canvas = np.zeros((ph, pw), np.float32)
    x = (pw + total) // 2
    boxes = []
    for i, wd in enumerate(words):
        x -= wd.shape[1]
        y = (ph - wd.shape[0]) // 2 + int(rng.uniform(-2, 2) * S)
        ya, yb, xa, xb = max(0, y), min(ph, y + wd.shape[0]), max(0, x), min(pw, x + wd.shape[1])
        canvas[ya:yb, xa:xb] = np.maximum(canvas[ya:yb, xa:xb], wd[ya - y:yb - y, xa - x:xb - x])
        boxes.append((xa, xb))
        x -= gaps[i]
    return np.clip(canvas * 1.15, 0, 1), boxes


def bump_shade(h: np.ndarray, light_dir=(-0.55, -0.75), strength: float = 1.0) -> np.ndarray:
    gy_, gx_ = np.gradient(h)
    lx, ly = light_dir
    return np.clip(1 + strength * (gx_ * -lx + gy_ * -ly) * 40, 0.35, 1.8).astype(np.float32)


def ground(rng, kind: str):
    """Linear albedo (H,W,3) and optional wetness (H,W) and bump shading (H,W)."""
    gy, gx = np.mgrid[0:H, 0:W].astype(np.float32)
    wet = np.zeros((H, W), np.float32)
    if kind == "earth":
        # freshly turned dark grave soil
        base = 0.055 + 0.035 * noise((H, W), rng, 220 * S, 4)
        clods_h = noise((H // 2, W // 2), rng, 26 * S, 4)
        clods_h = cv2.resize(clods_h, (W, H))
        crumbs = cv2.GaussianBlur(rng.random((H, W)).astype(np.float32), (0, 0), 1.4 * S)
        hgt = 0.6 * clods_h + 0.25 * crumbs + 0.4 * noise((H, W), rng, 90 * S, 3)
        alb = base * (0.75 + 0.5 * crumbs) * (0.8 + 0.4 * clods_h)
        damp = smooth(noise((H, W), rng, 300 * S, 3), 0.55, 0.75)
        alb = alb * (1 - 0.35 * damp)
        wet = 0.5 * damp
        col = np.stack([alb * 1.0, alb * 0.80, alb * 0.62], axis=2)
        # pebbles: small pale stones half sunk in the soil
        img = np.zeros((H, W), np.float32)
        for _ in range(int(140)):
            cx_, cy_ = rng.uniform(0, W), rng.uniform(0, H)
            r = rng.uniform(5, 16) * S
            cv2.ellipse(img, (int(cx_), int(cy_)), (int(r), int(r * rng.uniform(0.6, 0.95))), rng.uniform(0, 180), 0, 360, float(rng.uniform(0.6, 1.0)), -1, cv2.LINE_AA)
        peb = cv2.GaussianBlur(img, (0, 0), 1.0 * S)
        hgt += 0.8 * peb
        pc = np.array([0.30, 0.27, 0.23], np.float32) * (0.85 + 0.3 * noise((H, W), rng, 8 * S, 2))[..., None]
        col = col * (1 - peb[..., None]) + pc * peb[..., None]
        # dry root threads
        roots = np.zeros((H, W), np.float32)
        for _ in range(26):
            p = np.float32([rng.uniform(0, W), rng.uniform(0, H)])
            ang = rng.uniform(0, 2 * np.pi)
            pts = []
            for _k in range(int(rng.uniform(20, 60))):
                ang += rng.normal(0, 0.25)
                p = p + np.float32([math.cos(ang), math.sin(ang)]) * 6 * S
                pts.append(p.copy())
            cv2.polylines(roots, [np.int32(pts)], False, float(rng.uniform(0.5, 1.0)), max(1, int(1.2 * S)), cv2.LINE_AA)
        roots = cv2.GaussianBlur(roots, (0, 0), 0.6 * S)
        col = col * (1 - roots[..., None]) + np.array([0.16, 0.12, 0.08], np.float32) * roots[..., None]
        hgt += 0.3 * roots
        shade = bump_shade(cv2.GaussianBlur(hgt, (0, 0), 1.5 * S), strength=1.1)
        return col.astype(np.float32), wet, shade
    if kind == "basalt":
        hgt = noise((H, W), rng, 160 * S, 4) * 0.7 + noise((H, W), rng, 18 * S, 3) * 0.3
        alb = 0.026 + 0.018 * noise((H, W), rng, 40 * S, 3)
        # vesicles: small pits
        pits = np.zeros((H, W), np.float32)
        for _ in range(int(1800)):
            cx_, cy_ = rng.uniform(0, W), rng.uniform(0, H)
            r = rng.gamma(1.6, 2.2) * S
            cv2.circle(pits, (int(cx_), int(cy_)), max(1, int(r)), 1.0, -1, cv2.LINE_AA)
        pits = cv2.GaussianBlur(pits, (0, 0), 0.8 * S)
        hgt -= 0.5 * pits
        alb = alb * (1 - 0.6 * pits)
        # cracks with salt crust
        pts = np.column_stack([rng.uniform(-100, W + 100, 60), rng.uniform(-100, H + 100, 60)])
        gyq, gxq = np.mgrid[0:H // 4, 0:W // 4]
        d, _ = cKDTree(pts / 4).query(np.column_stack([gxq.ravel(), gyq.ravel()]), k=2)
        gap = cv2.resize((d[:, 1] - d[:, 0]).reshape(H // 4, W // 4).astype(np.float32), (W, H)) * 4
        crack = np.clip(1 - gap / (3.0 * S), 0, 1) * smooth(noise((H, W), rng, 120 * S, 2), 0.35, 0.6)
        salt = crack * smooth(noise((H, W), rng, 6 * S, 2), 0.45, 0.7)
        hgt -= 0.4 * crack
        col = np.stack([alb, alb * 1.0, alb * 1.08], axis=2)
        col = col * (1 - salt[..., None]) + np.array([0.42, 0.42, 0.40], np.float32) * salt[..., None] * 0.7
        wet = np.clip(0.25 + 0.75 * smooth(gy / H, 0.55, 1.0) * smooth(noise((H, W), rng, 200 * S, 2), 0.3, 0.6), 0, 1)
        shade = bump_shade(cv2.GaussianBlur(hgt, (0, 0), 1.2 * S), strength=1.3)
        return col.astype(np.float32), wet.astype(np.float32), shade
    # v5 stone
    pts = np.column_stack([rng.uniform(-60, W + 60, 70), rng.uniform(-60, H + 60, 70)])
    gy_, gx_ = np.mgrid[0:H // 2, 0:W // 2]
    d, idx = cKDTree(pts / 2).query(np.column_stack([gx_.ravel(), gy_.ravel()]), k=2)
    gap = (d[:, 1] - d[:, 0]).reshape(H // 2, W // 2)
    joint = cv2.resize((1 - smooth(gap, 0.5, 3.0)).astype(np.float32), (W, H))
    stone = cv2.resize(rng.uniform(0.8, 1.15, len(pts))[idx[:, 0]].reshape(H // 2, W // 2).astype(np.float32), (W, H), interpolation=cv2.INTER_NEAREST)
    grit = cv2.GaussianBlur(rng.random((H, W)).astype(np.float32), (0, 0), 2.5)
    alb = 0.09 * stone * (0.8 + 0.4 * noise((H, W), rng, 50, 3)) * (0.85 + 0.3 * grit) * (1 - 0.35 * cv2.GaussianBlur(joint, (0, 0), 2.5))
    return np.repeat(alb[..., None], 3, axis=2).astype(np.float32), wet, np.ones((H, W), np.float32)


def paper_maps(rng, kind: str, pw: int, ph: int):
    """Albedo (display-ish 0..1 RGB), alpha, and a curl height map for the sheet."""
    yy, xx = np.mgrid[0:ph, 0:pw].astype(np.float32)
    fib = noise((ph, pw), rng, 3 * S, 3)
    low = noise((ph, pw), rng, 220 * S, 3)
    if kind == "manuscript":
        base = np.array([0.80, 0.66, 0.45], np.float32)
        alb = base[None, None] * (0.95 + 0.06 * fib[..., None]) * (0.9 + 0.16 * low[..., None])
        # foxing: scattered brown spots
        fox = smooth(noise((ph, pw), rng, 10 * S, 3), 0.80, 0.92) * smooth(noise((ph, pw), rng, 120 * S, 2), 0.4, 0.7)
        alb = alb * (1 - 0.45 * fox[..., None] * np.array([0.6, 0.8, 1.0], np.float32))
        # aged, darker margins
        dmar = np.minimum(np.minimum(xx, pw - 1 - xx), np.minimum(yy, ph - 1 - yy))
        alb *= (0.82 + 0.18 * smooth(dmar, 0, 40 * S))[..., None]
        # one torn long edge (top): fibrous, irregular
        tear = 10 * S + 22 * S * noise((1, pw), rng, 60 * S, 4)[0] + 5 * S * noise((1, pw), rng, 6 * S, 2)[0]
        top = yy - tear[None, :]
        fibres = (noise((ph, pw), rng, 1.5 * S, 2) - 0.5) * 4 * S
        edge = np.minimum(np.minimum(xx - 2 * S, pw - 1 - xx - 2 * S), np.minimum(top + fibres, ph - 1 - yy - 2 * S))
        edge += (noise((ph, pw), rng, 30 * S, 2) - 0.5) * 2.0 * S
        alpha = np.clip(edge / (1.2 * S) + 0.5, 0, 1)
        # torn edge is lighter (exposed fibres) and slightly translucent
        rim = smooth(top, 0, 5 * S) * (1 - smooth(top, 5 * S, 9 * S))
        alb = alb * (1 + 0.12 * rim[..., None])
        curl = 4.0 * S * smooth(yy / ph, 0.6, 1.0) + 2.5 * S * noise((ph, pw), rng, 160 * S, 2)
        return alb, alpha.astype(np.float32), curl.astype(np.float32)
    if kind == "deckle":
        base = np.array([0.91, 0.87, 0.78], np.float32)
        lumpy = noise((ph, pw), rng, 14 * S, 3)
        alb = base[None, None] * (0.95 + 0.07 * fib[..., None]) * (0.95 + 0.06 * lumpy[..., None]) * (0.96 + 0.06 * low[..., None])
        dk = 9 * S * noise((ph, pw), rng, 22 * S, 4) + 3 * S * noise((ph, pw), rng, 3 * S, 2)
        edge = np.minimum(np.minimum(xx, pw - 1 - xx), np.minimum(yy, ph - 1 - yy)) - dk
        alpha = np.clip(edge / (3.0 * S), 0, 1) ** 0.7  # soft, fibrous, slightly translucent deckle
        curl = 3.0 * S * noise((ph, pw), rng, 200 * S, 2) + 1.5 * S * lumpy
        return alb, alpha.astype(np.float32), curl.astype(np.float32)
    alb = np.array([0.9, 0.85, 0.78], np.float32)[None, None] * (0.96 + 0.05 * fib[..., None]) * (0.95 + 0.1 * low[..., None])
    edge = np.minimum(np.minimum(xx, pw - 1 - xx), np.minimum(yy, ph - 1 - yy)) + (noise((ph, pw), rng, 30, 2) - 0.5) * 2.0
    return alb, np.clip(edge - 0.5, 0, 1).astype(np.float32), (3.0 * noise((ph, pw), rng, 160, 2)).astype(np.float32)


def blackbody(h: np.ndarray) -> np.ndarray:
    """0..1 heat -> linear RGB emission (dull red -> orange -> yellow-white)."""
    h = np.clip(h, 0, 1)[..., None]
    c0 = np.array([0.35, 0.02, 0.0], np.float32)
    c1 = np.array([1.0, 0.22, 0.02], np.float32)
    c2 = np.array([1.0, 0.62, 0.20], np.float32)
    c3 = np.array([1.0, 0.93, 0.78], np.float32)
    out = np.where(h < 0.33, c0 + (c1 - c0) * (h / 0.33), np.where(h < 0.7, c1 + (c2 - c1) * ((h - 0.33) / 0.37), c2 + (c3 - c2) * ((h - 0.7) / 0.3)))
    return out * (0.05 * np.minimum(h * 25, 1) + 3.5 * h ** 2.2)  # zero heat emits nothing


def depth_of_field(img: np.ndarray, sig_rows: np.ndarray) -> np.ndarray:
    """Row-varying lens blur: blend a small stack of blurred copies by each row's blur radius."""
    levels = [0.0, 2.0, 5.0, 10.0, 20.0, 40.0]
    levels = [l * S / 2 for l in levels]
    stack = [img] + [cv2.GaussianBlur(cv2.resize(img, (img.shape[1] // 2, img.shape[0] // 2), interpolation=cv2.INTER_AREA), (0, 0), l / 2) for l in levels[1:]]
    stack = [stack[0]] + [cv2.resize(x, (img.shape[1], img.shape[0])) for x in stack[1:]]
    s = np.clip(sig_rows, 0, levels[-1])
    out = np.zeros_like(img)
    for i in range(len(levels) - 1):
        a, b = levels[i], levels[i + 1]
        sel = (s >= a) & (s < b) if i < len(levels) - 2 else (s >= a)
        wl = np.where(sel, np.clip((b - s) / (b - a), 0, 1), 0)[:, None, None]
        wh = np.where(sel, 1 - np.clip((b - s) / (b - a), 0, 1), 0)[:, None, None]
        out += stack[i] * wl + stack[i + 1] * wh
    return out


def main(cfg_p: str) -> None:
    global W, H, FPS, S
    cfg = json.load(open(cfg_p, encoding="utf-8"))
    OW, OH = cfg.get("size", [2160, 3840])
    FPS = int(cfg.get("fps", 24))
    S = OW / 1080.0
    view = cfg.get("view")  # oblique camera: render the ground plane flat on a canvas, then project it
    if view:
        W, H = [int(v * S) for v in view["canvas"]]
        trap = np.float32(view["trapezoid"]) * S  # canvas points seen at the output TL, TR, BR, BL
        Hcam = cv2.getPerspectiveTransform(trap, np.float32([[0, 0], [OW, 0], [OW, OH], [0, OH]]))
    else:
        W, H = OW, OH
        Hcam = None
    rng = np.random.default_rng(cfg.get("seed", 3))
    dur = float(cfg["duration"])
    t0 = float(cfg.get("film_t0", 0.0))  # film time of the first output frame
    n_out = int(round(dur * FPS))
    pw, ph = [int(v * S) for v in cfg.get("paper_wh", [960, 230])]
    font = cfg.get("font", "/home/user/Builder-Baseerah/sutoor-film/remotion/public/fonts/amiri-Amiri-Bold.ttf")

    # ---------- paper ----------
    yy, xx = np.mgrid[0:ph, 0:pw].astype(np.float32)
    alb_d, paper_a0, curl = paper_maps(rng, cfg.get("paper", "plain"), pw, ph)
    fold = cfg.get("fold")
    if fold:  # a crease across the sheet: two faces tented up along the fold line
        fy = float(fold.get("at", 0.5)) * ph
        curl = curl + fold.get("height", 12) * S * np.clip(1 - np.abs(yy - fy) / (ph * 0.5), 0, 1) ** 1.3
    ink, boxes = pen_line(cfg["line"], font, int(cfg.get("font_size", 66) * S), pw, ph, rng)
    ink = np.clip(cv2.GaussianBlur(ink, (0, 0), 0.4 * S), 0, 1)
    ink_rgb = np.array(cfg.get("ink_rgb", [12, 10, 10]), np.float32) / 255
    ink_density = float(cfg.get("ink_density", 1.0))

    # ---------- arrival time: eikonal raggedness, timed to the reading ----------
    u0, v0 = cfg.get("origin", [1.0, 0.55])
    phi = np.hypot(xx - u0 * (pw - 1), yy - v0 * (ph - 1)) - 6.0 * S
    sp = (0.35 + 1.3 * noise((ph, pw), rng, 120 * S, 3)) * (0.55 + 0.9 * noise((ph, pw), rng, 28 * S, 3))
    sp *= 0.45 + 1.1 * noise((ph, pw), rng, 5 * S, 2)
    sp *= np.where(noise((ph, pw), rng, 14 * S, 2) > 0.72, 2.2, 1.0)
    Te = np.ma.filled(skfmm.travel_time(phi, sp.astype(np.float64), dx=1.0), 0).astype(np.float32)
    word_times = cfg.get("word_times")  # film times at which the front reaches each word's centre (reading order)
    if word_times:
        cols = np.where(paper_a0 > 0.5, Te, np.nan)
        m = np.nanmedian(cols, axis=0)
        m = np.where(np.isfinite(m), m, np.nanmedian(m))
        m = cv2.GaussianBlur(m[None, :].astype(np.float32), (0, 0), 25 * S)[0]
        ctr = [(a + b) / 2 for a, b in boxes]
        xs_k = [pw - 1] + ctr + [0]
        ts_k = [cfg.get("t_ignite", word_times[0] - 0.8)] + list(word_times) + [cfg.get("t_end_left", word_times[-1] + 1.0)]
        D = np.interp(np.arange(pw), xs_k[::-1], ts_k[::-1]).astype(np.float32)
        rag = float(cfg.get("ragged_s", 0.35))
        dev = (Te - m[None, :])
        dev = dev / (np.percentile(np.abs(dev[paper_a0 > 0.5]), 90) + 1e-6)
        T = D[None, :] + rag * dev
    else:
        T = Te / float(cfg.get("speed_px", 55) * S) + float(cfg.get("t_ignite", t0))
    T += 0.03 * (noise((ph, pw), rng, 5 * S, 2) - 0.5)
    T = T.astype(np.float32)

    # surviving ember word
    ew = cfg.get("ember_word")
    ew_mask = np.zeros((ph, pw), np.float32)
    keep_zone = np.zeros((ph, pw), bool)
    if ew is not None:
        k = int(ew["index"]) % len(boxes)
        xa, xb = boxes[k]
        ew_mask[:, xa:xb] = ink[:, xa:xb]
        ew_mask = np.clip(cv2.GaussianBlur(ew_mask, (0, 0), 0.5 * S) * 1.2, 0, 1)
        keep_zone = np.zeros((ph, pw), np.float32)
        keep_zone[:, max(0, xa - int(60 * S)):min(pw, xb + int(60 * S))] = 1
        keep_zone = cv2.GaussianBlur(keep_zone, (0, 0), 20 * S) > 0.5
    heat_k = np.array(ew["heat"] if ew else [[0, 0]], np.float32)

    crinkle = noise((ph, pw), rng, 7 * S, 3)
    n_frag = int(420 * (pw * ph) / (930 * 277 * S * S))
    frag_pts = np.column_stack([rng.uniform(0, pw, n_frag), rng.uniform(0, ph, n_frag)])
    fd, fidx = cKDTree(frag_pts).query(np.column_stack([xx.ravel(), yy.ravel()]), k=2)
    frag_edge = smooth(((fd[:, 1] - fd[:, 0]).reshape(ph, pw)), 0.0, 2.5 * S)
    keep = rng.random(len(frag_pts)) < float(cfg.get("char_keep", 0.45))
    t_drop = np.where(keep[fidx[:, 0]], 99.0, rng.uniform(0.9, 2.2, len(frag_pts))[fidx[:, 0]]).reshape(ph, pw).astype(np.float32)
    t_drop = np.where(keep_zone, 99.0, t_drop)
    drop_glow = (rng.random(len(frag_pts)) < 0.3)[fidx[:, 0]].reshape(ph, pw).astype(np.float32)  # only some cracks glow
    gTy, gTx = np.gradient(cv2.GaussianBlur(T, (0, 0), 2 * S))
    front_speed = 1.0 / (np.hypot(gTx, gTy) + 1e-4) / S  # px/s at 1080 scale
    domen = noise((ph, pw), rng, 55 * S, 2)
    cracks = np.clip(1 - np.abs(noise((ph, pw), rng, 22 * S, 3) - 0.5) / 0.012, 0, 1) * (noise((ph, pw), rng, 60 * S, 2) > 0.62)
    edge_d = cv2.distanceTransform((paper_a0 > 0.5).astype(np.uint8), cv2.DIST_L2, 3)
    bite = (edge_d < (10 + 30 * noise((ph, pw), rng, 25 * S, 2)) * S) & ~keep_zone
    t_bite = 3.0 + 2.0 * noise((ph, pw), rng, 20 * S, 2)

    # ---------- placement ----------
    cx, cy = [v * S for v in cfg.get("center", [540, 1010])]
    tilt = math.radians(cfg.get("tilt_deg", -2.0))
    corners = np.array([[-pw / 2, -ph / 2], [pw / 2, -ph / 2], [pw / 2, ph / 2], [-pw / 2, ph / 2]], np.float32)
    rot = np.array([[math.cos(tilt), -math.sin(tilt)], [math.sin(tilt), math.cos(tilt)]], np.float32)
    M = cv2.getPerspectiveTransform(np.array([[0, 0], [pw, 0], [pw, ph], [0, ph]], np.float32), corners @ rot.T + np.array([cx, cy], np.float32))
    warp = lambda a: cv2.warpPerspective(a, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=0)  # noqa: E731

    g_alb, g_wet, g_shade = ground(rng, cfg.get("ground", "stone"))
    g_alb = g_alb * g_shade[..., None]
    gy, gx = np.mgrid[0:H, 0:W].astype(np.float32)
    amb = cfg.get("ambient", {"rgb": [0.95, 0.88, 0.8], "level": 0.03})
    amb_rgb = np.array(amb["rgb"], np.float32)
    amb_map = (amb["level"] * (0.55 + 0.45 * np.clip(1 - gx / W, 0, 1)) * (0.6 + 0.4 * smooth(gy / H, 0.0, 0.8)))[..., None] * amb_rgb
    rim_cfg = cfg.get("cold_rim")
    if rim_cfg:  # faint cold light off the surf, from the bottom edge
        amb_map += (rim_cfg["level"] * smooth(gy / H, 0.6, 1.0))[..., None] * np.array(rim_cfg.get("rgb", [0.6, 0.75, 1.0]), np.float32)
    marker = cfg.get("marker")
    g_marker = np.zeros((H, W), np.float32)
    if marker:  # a plain limestone grave marker, soft out of focus, entering a corner
        mx, my, mw, mh = [v * S for v in marker["rect"]]
        cv2.rectangle(g_marker, (int(mx), int(my)), (int(mx + mw), int(my + mh)), 1.0, -1)
        cv2.ellipse(g_marker, (int(mx + mw / 2), int(my)), (int(mw / 2), int(mw * 0.18)), 0, 180, 360, 1.0, -1)
        g_marker = cv2.GaussianBlur(g_marker, (0, 0), marker.get("blur", 38) * S)
    p_a0 = warp(paper_a0)
    sea = cfg.get("sea")
    sea_cap, sea_mask = None, None
    if sea:
        y_edge = sea["y_edge"] * S
        edge_n = (noise((1, W), rng, 120 * S, 3)[0] - 0.5) * 90 * S + (noise((1, W), rng, 12 * S, 2)[0] - 0.5) * 16 * S
        sea_mask = np.clip((y_edge + edge_n[None, :] - gy) / (6 * S), 0, 1)[..., None].astype(np.float32)
        sea_cap = cv2.VideoCapture(sea["plate"])
        sea_cap.set(cv2.CAP_PROP_POS_MSEC, sea.get("in", 0) * 1000)
        g_wet = np.maximum(g_wet, smooth(gy - y_edge, 0, 160 * S).astype(np.float32) * 0 + np.clip(1 - (gy - y_edge) / (260 * S), 0, 1) * 0.9)

    # ---------- flame plates ----------
    fscale = float(cfg.get("flame_scale", 1.0))
    plates = []
    for f in cfg.get("flames", []):
        cap_ = cv2.VideoCapture(f)
        fr, ok = [], True
        while ok and len(fr) < 380:
            ok, im = cap_.read()
            if ok:
                h0 = im.shape[0]
                core = im[int(h0 * 0.05):int(h0 * 0.62)]
                fr.append(cv2.resize(core, (int(core.shape[1] * 0.6 * S / 2), int(core.shape[0] * 0.6 * S / 2))))
        plates.append(fr)
    max_em = int(cfg.get("max_flames", 10))
    em_pos = [None] * max_em
    em_level = np.zeros(max_em, np.float32)
    em_plate = rng.integers(0, max(1, len(plates)), max_em)
    em_off = rng.integers(0, 200, max_em)
    em_scale = rng.uniform(0.75, 1.25, max_em)
    em_lean = rng.uniform(-14, 14, max_em)
    wind0 = float(cfg.get("wind_deg", 20))
    wind_drift = noise((1, n_out + 10), rng, 40, 2)[0]
    spacing = 55 * S

    dof_w, wet_o = None, None
    if Hcam is not None:
        # depth per output row from the projection: blur grows with distance from the focus row
        inv = np.linalg.inv(Hcam)
        rows = np.arange(OH, dtype=np.float32)
        pts = cv2.perspectiveTransform(np.stack([np.full_like(rows, OW / 2), rows], 1)[None], inv)[0]
        nxt = cv2.perspectiveTransform(np.stack([np.full_like(rows, OW / 2), rows + 1], 1)[None], inv)[0]
        dist = 1.0 / (np.hypot(*(nxt - pts).T) + 1e-6)  # output px per canvas px: larger = nearer
        pc_out = cv2.perspectiveTransform(np.array([[[cx, cy]]], np.float32), Hcam)[0, 0]
        focus = float(np.interp(view.get("focus_row", pc_out[1] / OH) * OH, rows, dist))  # default: focus on the paper
        coc = np.abs(dist / focus - 1)  # relative defocus
        dof_w = np.clip(coc * float(view.get("dof", 24)) * S, 0, float(view.get("dof_max", 40)) * S)
        wet_o = cv2.warpPerspective(g_wet, Hcam, (OW, OH), flags=cv2.INTER_LINEAR)
    cam = noise((3, n_out + 10), rng, 60, 3)
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OW}x{OH}", "-r", str(FPS), "-i", "-",
                             "-c:v", "libx264", "-preset", "medium", "-crf", "14", "-pix_fmt", "yuv420p",
                             "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", cfg["out"]], stdin=subprocess.PIPE)
    exposure, I_lag = float(cfg.get("exposure", 1.0)), 0.0
    nlf = noise((1, n_out + 10), rng, 3, 3)[0]
    q = 4  # lighting computed at 1/q resolution
    gyq, gxq = np.mgrid[0:H // q, 0:W // q].astype(np.float32) * q
    meta = {"word_boxes": boxes, "fps": FPS}
    for fo in range(n_out):
        t = t0 + fo / FPS
        st = t - T
        scorch = smooth(st, -0.3, 0.0)
        rim = np.exp(-((st - 0.03) / 0.03) ** 2) * (st > -0.02)
        flick = cv2.resize(noise((ph // 6, pw // 6), np.random.default_rng(1000 + int(t * 12)), 6, 2), (pw, ph))
        rim_vis = rim * smooth(flick, 0.3, 0.7)
        char = smooth(st, 0.05, 0.14)
        old = smooth(st, 1.2, 2.5)
        dropping = (st > t_drop - 0.2) & (st <= t_drop)
        gone = (bite & (st > t_bite)) | (st > t_drop)
        alpha = paper_a0 * (~gone)

        sc1, sc2 = lin(np.array([170, 115, 60], np.float32) / 255), lin(np.array([55, 32, 18], np.float32) / 255)
        a_lin = lin(alb_d)
        a_lin = a_lin * (1 - scorch[..., None]) + (sc1 * (1 - scorch[..., None] ** 2) + sc2 * scorch[..., None] ** 2) * scorch[..., None]
        inkl = lin(ink_rgb)
        ia = (ink * ink_density)[..., None]
        a_lin = a_lin * (1 - ia) + inkl * ia
        char_alb = 0.032 * (0.75 + 0.5 * crinkle[..., None]) * np.array([1.0, 0.85, 0.75], np.float32)
        char_alb = char_alb * (1 - 0.3 * ink[..., None])
        ash_alb = 0.22 * np.array([1.0, 0.95, 0.9], np.float32)
        char_alb = char_alb * (1 - (cracks * old)[..., None]) + ash_alb * (cracks * old)[..., None]
        a_lin = a_lin * (1 - char[..., None]) + char_alb * char[..., None]

        z = 35.0 * S * smooth(st, 0.05, 0.8) * (0.5 + domen) * (1 - 0.7 * keep_zone) + 4.0 * S * smooth(st, -0.4, 0.0) + curl
        lift_px = (z * 0.30).astype(np.float32)
        mapy = (yy + lift_px * char).astype(np.float32)
        upl = lambda a: cv2.remap(a, xx, mapy, cv2.INTER_LINEAR, borderValue=0)  # noqa: E731
        char_l = upl(char.astype(np.float32))
        base = (1 - char)
        a_lin = a_lin * base[..., None] + upl(a_lin) * char_l[..., None] * (1 - base[..., None])
        alpha = np.clip(alpha * base + upl(alpha.astype(np.float32)) * char_l, 0, 1)
        nzy, nzx = np.gradient(cv2.GaussianBlur(z, (0, 0), 4 * S))

        em = rim_vis[..., None] * lin(np.array([230, 60, 30], np.float32) / 255) * 6.0
        em += ((1 - frag_edge) * dropping * drop_glow)[..., None] * lin(np.array([220, 70, 25], np.float32) / 255) * 1.2
        sparks = (rng.random((ph, pw)) > 1 - 0.0006 / (S * S)) & (st > 0.08) & (st < 0.45)
        em += cv2.GaussianBlur(sparks.astype(np.float32), (0, 0), 0.8 * S)[..., None] * np.array([4.0, 1.4, 0.3], np.float32)
        heat = 0.0
        if ew is not None:
            heat = float(np.interp(t, heat_k[:, 0], heat_k[:, 1]))
            if heat > 0.001:
                charred_here = smooth(st, 0.0, 0.25)
                core = cv2.GaussianBlur(ew_mask, (0, 0), 0.6 * S)
                halo = cv2.GaussianBlur(ew_mask, (0, 0), 5 * S)
                fl_n = 0.85 + 0.15 * smooth(flick, 0.2, 0.8)
                gain = float(ew.get("gain", 0.8))
                em += (blackbody(heat * core * fl_n) * gain + blackbody(heat * 0.45 * halo) * 0.25 * gain) * charred_here[..., None]

        # ---------- flame emitters ----------
        active = (st > 0.0) & (st < 0.3) & (paper_a0 > 0) & (~gone)
        n_act = int(active.sum())
        want = int(np.clip(n_act / (spacing * 18 * S), 0, max_em))
        ys_, xs_ = np.nonzero(active[::3, ::3])
        ys_, xs_ = ys_ * 3, xs_ * 3
        for e in range(max_em):
            if e >= want or not xs_.size:
                em_level[e] *= 0.8
                if em_level[e] < 0.03:
                    em_pos[e] = None
                continue
            if em_pos[e] is None:
                j = int(rng.integers(len(xs_)))
                cand = np.float32([xs_[j], ys_[j]])
                if all(p is None or np.hypot(*(cand - p)) > spacing for p in em_pos):
                    em_pos[e] = cand
                continue
            dd = np.hypot(xs_ - em_pos[e][0], ys_ - em_pos[e][1])
            j = int(np.argmin(dd))
            if dd[j] > 50 * S:
                em_level[e] *= 0.75
                if em_level[e] < 0.05:
                    em_pos[e] = None
                continue
            em_pos[e] = em_pos[e] * 0.7 + np.float32([xs_[j], ys_[j]]) * 0.3
            iu, iv = int(np.clip(em_pos[e][0], 0, pw - 1)), int(np.clip(em_pos[e][1], 0, ph - 1))
            tgt = float(np.clip((front_speed[iv, iu] - 3) / 14, 0.35, 1))
            em_level[e] += (tgt - em_level[e]) * 0.25

        FW, FH = (OW, OH) if Hcam is not None else (W, H)
        fl = np.zeros((FH, FW, 3), np.float32)
        lights = []
        wind = wind0 + 10 * (wind_drift[fo] - 0.5)
        for e in range(max_em):
            if em_pos[e] is None or em_level[e] < 0.03 or not plates:
                continue
            p = cv2.perspectiveTransform(np.array([[em_pos[e]]], np.float32), M)[0, 0]
            p[1] -= 8 * S
            fr = plates[em_plate[e]]
            k0 = (em_off[e] + fo) % len(fr)
            im = lin(np.mean([fr[(k0 + j) % len(fr)] for j in range(2)], axis=0)[..., ::-1].astype(np.float32) / 255.0)
            im = np.clip((im - 0.002) / 0.98, 0, None)
            hh = int(np.clip(110 * S * fscale * em_scale[e] * (0.55 + 0.45 * em_level[e]), 40 * S, 260 * S * fscale))
            p_draw = p
            lean = wind + em_lean[e]
            if Hcam is not None:
                q_ = cv2.perspectiveTransform(np.array([[p]], np.float32), Hcam)[0, 0]
                d_ = cv2.perspectiveTransform(np.array([[p + np.float32([0, 10])]], np.float32), Hcam)[0, 0]
                loc = float(np.hypot(*(d_ - q_))) / 10 * float(view.get("flame_depth_k", 1.6))
                hh = int(hh * loc)
                p_draw = q_
                lean = 0.45 * (wind - wind0) + 0.6 * em_lean[e] + float(view.get("lean", 0))
            ww = int(hh * 0.55)
            spr = cv2.resize(im, (max(8, ww), max(8, hh)), interpolation=cv2.INTER_AREA)
            fh_, fw_ = spr.shape[:2]
            ey = np.linspace(0, 1, fh_)
            spr *= smooth(spr.max(axis=2, keepdims=True), 0.02, 0.15) * np.minimum((1 - ey) / 0.10, 1)[:, None, None]
            pad = int(max(fw_, fh_) * 0.9)
            canvas = np.zeros((fh_ + 2 * pad, fw_ + 2 * pad, 3), np.float32)
            canvas[pad:pad + fh_, pad:pad + fw_] = spr
            R = cv2.getRotationMatrix2D((pad + fw_ / 2, pad + fh_), lean, 1.0)
            canvas = cv2.warpAffine(canvas, R, (canvas.shape[1], canvas.shape[0])) * em_level[e]
            x0, y0 = int(p_draw[0] - pad - fw_ / 2), int(p_draw[1] - pad - fh_ * 0.92)
            xa, ya, xb, yb = max(0, x0), max(0, y0), min(FW, x0 + canvas.shape[1]), min(FH, y0 + canvas.shape[0])
            if xb > xa and yb > ya:
                fl[ya:yb, xa:xb] += canvas[ya - y0:yb - y0, xa - x0:xb - x0]
            lights.append((p, float(canvas.sum()) / (1500.0 * S * S)))

        # ---------- lighting (linear, at 1/q resolution) ----------
        flick_state = 0.8 + 0.4 * nlf[fo]
        Eq = np.zeros((H // q, W // q), np.float32)
        hgt = 80.0 * S
        for (p, I) in lights:
            r2 = (gxq - p[0]) ** 2 + (gyq - p[1]) ** 2
            Eq += I * flick_state * hgt / (hgt ** 2 + r2) ** 1.5 * 1.3e4 * S
        p_em = warp(em)
        emq = cv2.resize(p_em.sum(axis=2), (W // q, H // q), interpolation=cv2.INTER_AREA)
        Eq += 0.25 * cv2.GaussianBlur(emq, (0, 0), 5 * S)
        E = cv2.resize(Eq, (W, H), interpolation=cv2.INTER_LINEAR)[..., None]
        fire = E * np.array([1.0, 0.30, 0.09], np.float32)

        p_alb, p_a = warp(a_lin), warp(alpha.astype(np.float32))
        p_nx, p_ny, p_char = warp(nzx), warp(nzy), warp(char.astype(np.float32))
        lp = np.mean([p for p, _ in lights], axis=0) if lights else np.float32([cx, cy - 60 * S])
        lx, ly = (lp[0] - gx), (lp[1] - gy)
        ln = np.hypot(lx, ly) + 1e-3
        lam = np.clip(1 + 0.25 * (p_nx * lx + p_ny * ly) / ln * -1, 0.4, 1.6)[..., None]
        spec = (0.2 * p_char * np.clip(-(p_nx * lx + p_ny * ly) / ln, 0, 1) ** 2)[..., None]
        illum_paper = amb_map * 1.2 + fire * lam
        illum_ground = amb_map + fire

        off = np.float32([cx, cy]) - lp
        off = off / (np.hypot(*off) + 1e-3) * 6 * S * float(cfg.get("thickness", 1.0))
        sh = cv2.warpAffine(p_a, np.float32([[1, 0, off[0]], [0, 1, off[1]]]), (W, H))
        shadow = np.clip(cv2.GaussianBlur(sh, (0, 0), 8 * S) * 0.55 + cv2.GaussianBlur(sh, (0, 0), 1.5 * S) * 0.3, 0, 0.75)[..., None]

        frame = g_alb * illum_ground * (1 - shadow)
        if sea_cap is not None:
            ok, sf_ = sea_cap.read()
            if ok:
                sea_lin = lin(cv2.resize(sf_[..., ::-1], (W, H)).astype(np.float32) / 255.0) * float(sea.get("level", 0.35)) * np.array(sea.get("tint", [0.75, 0.85, 1.0]), np.float32)
                sea_lin = sea_lin + fire * 0.05
                frame = frame * (1 - sea_mask) + sea_lin * sea_mask
        if marker:
            frame = frame * (1 - g_marker[..., None]) + (np.array(marker.get("alb", [0.30, 0.29, 0.27]), np.float32) * (amb_map * 1.4 + fire * 0.3)) * g_marker[..., None]
        paper =p_alb * illum_paper + spec * fire + p_em
        frame = frame * (1 - p_a[..., None]) + paper * p_a[..., None]
        if Hcam is not None:
            frame = cv2.warpPerspective(frame, Hcam, (OW, OH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            frame = depth_of_field(frame, dof_w)
            p_a = cv2.warpPerspective(p_a, Hcam, (OW, OH), flags=cv2.INTER_LINEAR)
            g_wet_o = wet_o
            p_em_o = cv2.warpPerspective(p_em, Hcam, (OW, OH), flags=cv2.INTER_LINEAR)
            fire_o = cv2.warpPerspective(fire, Hcam, (OW, OH), flags=cv2.INTER_LINEAR)
        else:
            g_wet_o, p_em_o, fire_o = g_wet, p_em, fire
        fl = fl * float(cfg.get("flame_gain", 4.5))
        fl = np.stack([fl[..., 0], fl[..., 1] * 0.95, fl[..., 2] * 0.85], axis=2)
        FW, FH = frame.shape[1], frame.shape[0]
        if g_wet_o.any():  # wet sheen: a soft, vertically smeared mirror of the flames below them, plus a fire glint
            flq = cv2.resize(fl, (FW // q, FH // q), interpolation=cv2.INTER_AREA)
            down = np.zeros_like(flq)
            sh_ = int(18 * S / q)
            down[sh_:] = flq[:-sh_]
            smear = cv2.resize(cv2.GaussianBlur(down, (0, 0), sigmaX=2, sigmaY=10 * S / 2), (FW, FH))
            frame += float(cfg.get("wet_mirror", 0.35)) * smear * (g_wet_o * (1 - p_a))[..., None] + 0.18 * fire_o * (g_wet_o * (1 - p_a))[..., None]
        frame = frame + fl
        bq = cv2.resize(fl + p_em_o * p_a[..., None], (FW // q, FH // q), interpolation=cv2.INTER_AREA)
        frame += cv2.resize(cv2.GaussianBlur(bq, (0, 0), 6 * S / 2) * 0.25 + cv2.GaussianBlur(bq, (0, 0), 28 * S / 2) * 0.12, (FW, FH))

        I_tot = float(sum(I for _, I in lights))
        I_lag += (I_tot - I_lag) * 0.06
        target = float(cfg.get("exposure", 1.0)) / (1 + 0.35 * I_lag)
        exposure += (target - exposure) * 0.10
        frame = frame * exposure * 2.2
        out = disp(frame)
        out = np.where(out > 0.72, 0.72 + (out - 0.72) / (1 + (out - 0.72) / 0.22), out)

        # whole-frame camera: very slow handheld breathing (moves are added in the picture builder)
        dx = 2.0 * S * (cam[0, fo] - 0.5)
        dy = 2.0 * S * (cam[1, fo] - 0.5)
        A = cv2.getRotationMatrix2D((out.shape[1] / 2, out.shape[0] / 2), 0.12 * (cam[2, fo] - 0.5), 1.0)
        A[0, 2] += dx
        A[1, 2] += dy
        out = cv2.warpAffine(out, A, (out.shape[1], out.shape[0]), borderMode=cv2.BORDER_REFLECT)
        out = cv2.GaussianBlur(out, (0, 0), 0.55 * S)
        out = np.clip(out, 0, 1)
        proc.stdin.write((out * 255 + 0.5).astype(np.uint8).tobytes())
        if fo % 24 == 0:
            print(f"  frame {fo}/{n_out}", flush=True)
    proc.stdin.close()
    proc.wait()
    json.dump(meta, open(os.path.splitext(cfg["out"])[0] + ".meta.json", "w"))
    print(f"{cfg['out']}: {n_out} frames")


if __name__ == "__main__":
    main(sys.argv[1])
