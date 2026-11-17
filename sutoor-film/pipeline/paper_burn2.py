#!/usr/bin/env python3
"""Burning-paper scene, v2 (revised after an independent realism review of v1).

A strip of paper carrying ONE hemistich in hand-written-looking Naskh lies on night paving, seen
from above, and burns. Everything about the paper is computed in its own (u, v) pixel space from a
per-pixel ARRIVAL TIME of the fire, T(u, v), so the state of each point follows real burning:
  scorch (browning) -> thin, broken red-orange glowing edge -> opaque fresh char that lifts and curls
  -> matte grey ash that keeps its shape (ink still faintly visible) -> occasional holes.
Flames are real footage (dense bottom part of filmed flames on black), squashed for the overhead
view, leaning with one wind, riding the burning edge. The fire lights paper and ground together,
casts a contact shadow, and drives the exposure. The camera is locked off; jump cuts (as in the
reference) are made by skipping simulation time.

Config JSON:
  line (str, exact text), out (mp4), duration (s, output length), segments ([[sim_from, sim_to], ...]
  optional: jump cuts, in simulation seconds), preroll (s of fire before sim 0), origin [u, v],
  speed_px (mean front speed, px/s), flames [mp4...], font, seed, burn_cap (max burnt fraction),
  lighter (bool: no fire at all, warm key light only, for a 'presentation' shot); a segment written
  [from, to, "pre"] is such an unlit presentation segment (the reference opens on the unlit strip)
Usage: python paper_burn2.py config.json
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


def noise(shape, rng, scale, octaves=4):
    """Isotropic smooth noise in [0,1]; `scale` = feature size in px."""
    h, w = shape
    acc, amp, tot = np.zeros(shape, np.float32), 1.0, 0.0
    for o in range(octaves):
        s = max(2.0, scale / (2 ** o))
        g = rng.random((int(h / s) + 3, int(w / s) + 3)).astype(np.float32)
        acc += amp * cv2.resize(g, (w + int(2 * s), h + int(2 * s)), interpolation=cv2.INTER_CUBIC)[int(s):int(s) + h, int(s):int(s) + w]
        tot += amp
        amp *= 0.5
    acc /= tot
    return (acc - acc.min()) / (np.ptp(acc) + 1e-6)


def smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def handwritten_line(text, font_path, size, pw, ph, rng):
    """Exact text, shaped per word (raqm), each word with a little baseline and angle jitter."""
    font = ImageFont.truetype(font_path, size, layout_engine=ImageFont.Layout.RAQM)
    words = text.split(" ")
    imgs = []
    for w in words:
        b = font.getbbox(w, direction="rtl", language="ar")
        im = Image.new("L", (b[2] - b[0] + 40, int(size * 2.2)), 0)
        ImageDraw.Draw(im).text((20 - b[0], int(size * 0.45)), w, font=font, fill=255, direction="rtl", language="ar")
        im = im.rotate(float(rng.uniform(-1.2, 1.2)), resample=Image.BICUBIC, expand=False)
        imgs.append(im)
    gap = int(size * 0.32)
    total = sum(i.width for i in imgs) + gap * (len(imgs) - 1)
    canvas = Image.new("L", (pw, ph), 0)
    x = (pw + total) // 2  # right-to-left
    for im in imgs:
        x -= im.width
        y = (ph - im.height) // 2 + int(rng.uniform(-2, 2))
        canvas.paste(im, (x, y), im)
        x -= gap
    return np.asarray(canvas, np.float32) / 255.0


def paving(rng):
    """Night asphalt: dense small aggregate, fine grit, broad mottling, a hairline crack, a few bits of debris."""
    stones = np.zeros((H, W), np.float32)
    n = 26000
    xs, ys = rng.integers(0, W, n), rng.integers(0, H, n)
    rs, vs = rng.uniform(1.0, 3.6, n), rng.uniform(0.35, 1.0, n)
    for x, y, r, v in zip(xs, ys, rs, vs):
        cv2.circle(stones, (int(x), int(y)), int(round(r)), float(v), -1)
    stones = cv2.GaussianBlur(stones, (0, 0), 0.8)
    binder = 0.32 + 0.12 * noise((H, W), rng, 40, 3)
    grit = cv2.GaussianBlur(rng.random((H, W)).astype(np.float32), (0, 0), 0.7)
    mott = noise((H, W), rng, 260, 4)
    albedo = np.maximum(binder, stones * 0.75) * (0.75 + 0.5 * mott) * (0.85 + 0.3 * grit)
    crack = np.zeros((H, W), np.float32)
    x, y = float(rng.uniform(0, W)), 0.0
    while y < H:
        nx, ny = x + rng.uniform(-30, 30), y + rng.uniform(20, 60)
        cv2.line(crack, (int(x), int(y)), (int(nx), int(ny)), 1.0, 2)
        x, y = nx, ny
    albedo *= 1 - 0.6 * cv2.GaussianBlur(crack, (0, 0), 1.0)
    for _ in range(5):
        cx, cy = int(rng.uniform(80, W - 80)), int(rng.uniform(200, H - 200))
        cv2.ellipse(albedo, (cx, cy), (int(rng.uniform(5, 11)), int(rng.uniform(2, 4))), float(rng.uniform(0, 180)), 0, 360, float(rng.uniform(1.1, 1.4)), -1)
    tint = np.array([1.0, 0.74, 0.55], np.float32)
    return (albedo[..., None] * tint * 0.42).astype(np.float32)


def main(cfg_p: str) -> None:
    cfg = json.load(open(cfg_p, encoding="utf-8"))
    rng = np.random.default_rng(cfg.get("seed", 3))
    dur = float(cfg["duration"])
    n_out = int(round(dur * FPS))
    segs = cfg.get("segments") or [[0.0, dur]]
    seg_len = [sg[1] - sg[0] for sg in segs]
    pw, ph = cfg.get("paper_wh", [930, 277])
    font = cfg.get("font", "/home/user/film/typo/fonts/scheherazadenew-ScheherazadeNew-Medium.ttf")

    # ---------- paper ----------
    yy, xx = np.mgrid[0:ph, 0:pw].astype(np.float32)
    fib = noise((ph, pw), rng, 4, 3)
    low = noise((ph, pw), rng, 220, 3)
    albedo = np.array([0.88, 0.82, 0.74], np.float32)[None, None] * (0.96 + 0.05 * fib[..., None]) * (0.95 + 0.1 * low[..., None])
    edge_jit = (noise((ph, pw), rng, 30, 2) - 0.5) * 2.0
    dx_edge = np.minimum(xx, pw - 1 - xx)
    dy_edge = np.minimum(yy, ph - 1 - yy)
    edge = np.minimum(dx_edge, dy_edge) + edge_jit
    paper_a0 = np.clip(edge - 0.5, 0, 1)
    thickness = np.clip(1 - edge / 1.6, 0, 1) * paper_a0  # 1 px darker rim = paper thickness
    text_px = int(cfg.get("font_size", 64))
    ink = handwritten_line(cfg["line"], font, text_px, pw, ph, rng)
    ink = np.clip(cv2.GaussianBlur(ink, (0, 0), 0.55) * (0.82 + 0.18 * noise((ph, pw), rng, 6, 2)), 0, 1)
    ink_col = np.array([30, 24, 20], np.float32) / 255

    # ---------- fire arrival time T(u, v) ----------
    u0, v0 = cfg.get("origin", [0.58, 1.0])
    wx = (noise((ph, pw), rng, 90, 3) - 0.5) * 80
    wy = (noise((ph, pw), rng, 90, 3) - 0.5) * 80
    d = np.sqrt((xx + wx - u0 * pw) ** 2 + ((yy + wy - v0 * ph) * 1.25) ** 2)  # domain-warped distance (px)
    speed = float(cfg.get("speed_px", 75)) * (0.3 + 1.3 * noise((ph, pw), rng, 70, 3))
    speed *= 1 + 0.35 * (1 - yy / ph)  # a little faster up the strip (with the draught)
    speed *= 1 + 0.6 * np.clip(1 - edge / 25, 0, 1)  # edges catch faster
    T = d / speed - float(cfg.get("preroll", 1.2))
    cap = float(cfg.get("burn_cap", 1.0))
    if cap < 1.0:  # never let more than `cap` of the strip burn during the scene
        last = segs[-1][1]
        thr = np.quantile(T, cap)
        T = np.where(T > thr, np.maximum(T, last + 5.0), T)
    holes = noise((ph, pw), rng, 26, 3)
    hole_mask = holes > 0.72
    crinkle = noise((ph, pw), rng, 7, 3)

    # ---------- placement ----------
    cx, cy = cfg.get("center", [540, 990])
    tilt = math.radians(cfg.get("tilt_deg", -0.8))
    corners = np.array([[-pw / 2 * 0.985, -ph / 2], [pw / 2 * 0.985, -ph / 2], [pw / 2, ph / 2], [-pw / 2, ph / 2]], np.float32)
    rot = np.array([[math.cos(tilt), -math.sin(tilt)], [math.sin(tilt), math.cos(tilt)]], np.float32)
    dst = corners @ rot.T + np.array([cx, cy], np.float32)
    M = cv2.getPerspectiveTransform(np.array([[0, 0], [pw, 0], [pw, ph], [0, ph]], np.float32), dst)
    Minv = np.linalg.inv(M)

    ground = paving(rng)
    gy, gx = np.mgrid[0:H, 0:W].astype(np.float32)
    vign = np.clip(1 - 0.9 * smooth(np.hypot((gx - cx) / W, (gy - cy) / (H * 0.45)), 0.2, 0.8), 0.04, 1)[..., None]

    # ---------- flame plates (dense cores only) ----------
    plates = []
    for f in cfg.get("flames", []):
        cap_ = cv2.VideoCapture(f)
        fr, ok = [], True
        while ok and len(fr) < 360:
            ok, im = cap_.read()
            if ok:
                h0 = im.shape[0]
                core = im[int(h0 * 0.52):int(h0 * 0.97)]  # bottom part: dense flame body
                fr.append(cv2.resize(core, (core.shape[1] // 2, core.shape[0] // 2)))
        plates.append(fr)
    n_em = int(cfg.get("n_flames", 5))
    em_u = np.linspace(0.12, 0.88, n_em) + rng.uniform(-0.05, 0.05, n_em)
    em_plate = rng.integers(0, max(1, len(plates)), n_em)
    em_off = rng.integers(0, 200, n_em)
    em_scale = rng.uniform(0.85, 1.15, n_em)
    wind = math.radians(cfg.get("wind_deg", 28))  # flames lean up-left
    em_level = np.zeros(n_em, np.float32)

    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                             "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p", cfg["out"]], stdin=subprocess.PIPE)
    I_s, exposure = 0.0, 1.0
    for fo in range(n_out):
        # output time -> simulation time through the jump cuts
        ot = fo / FPS
        k, acc = 0, 0.0
        while k < len(segs) - 1 and ot >= acc + seg_len[k]:
            acc += seg_len[k]
            k += 1
        t = segs[k][0] + (ot - acc)
        cut_shift = np.array([[1.5 * k, -1.0 * k]], np.float32)  # tiny reframing at each jump cut

        st = t - T  # seconds since the fire reached this point (negative: not yet)
        lit = cfg.get("lighter", False) or (len(segs[k]) > 2 and segs[k][2] == "pre")
        if lit:
            st = np.full_like(T, -10.0)
        scorch = smooth(st, -0.3, 0.0)
        rim = np.exp(-((st - 0.03) / 0.035) ** 2) * (st > -0.02)
        q = int(t * 11)  # rim breaks up and flickers, refreshed ~11 Hz
        flick = noise((ph // 6, pw // 6), np.random.default_rng(1000 + q), 6, 2)
        flick = cv2.resize(flick, (pw, ph))
        rim_vis = rim * smooth(flick, 0.35, 0.7)
        char = smooth(st, 0.05, 0.12)
        ash = smooth(st, 0.6, 1.0)
        gone = (st > 1.0) & hole_mask
        gone = gone | ((st > 0.8) & (edge < 18 + 22 * holes))  # burnt edges shrink and crumble
        alpha = paper_a0 * (~gone)

        col = albedo.copy()
        sc1 = np.array([170, 120, 70], np.float32) / 255
        sc2 = np.array([60, 35, 20], np.float32) / 255
        col = col * (1 - scorch[..., None]) + (sc1 * (1 - scorch[..., None] ** 2) + sc2 * scorch[..., None] ** 2) * scorch[..., None]
        inkv = ink * (1 - 0.65 * ash)  # words still faintly visible on the ash
        col = col * (1 - inkv[..., None]) + ink_col * inkv[..., None]
        charc = (np.array([28, 15, 12], np.float32) / 255) * (0.8 + 0.4 * crinkle[..., None])
        ashc = (np.array([58, 42, 34], np.float32) / 255) * (0.75 + 0.5 * crinkle[..., None])
        burnt = charc * (1 - ash[..., None]) + ashc * ash[..., None]
        burnt = burnt * (1 - 0.35 * ink[..., None] * ash[..., None])
        col = col * (1 - char[..., None]) + burnt * char[..., None]
        col = col * (1 - 0.35 * thickness[..., None])

        # curl: burnt paper lifts behind the front; shade it from the fire
        hgt = 26 * smooth(st, 0.0, 0.6) + 8 * crinkle * char
        hy, hx = np.gradient(cv2.GaussianBlur(hgt, (0, 0), 3))
        em = (rim_vis[..., None] * np.array([230, 60, 30], np.float32) / 255 * 2.2)
        em += cv2.GaussianBlur(rim_vis, (0, 0), 4)[..., None] * np.array([1.0, 0.35, 0.1], np.float32) * 0.6
        sparks = (rng.random((ph, pw)) > 0.9993) & (st > 0.08) & (st < 0.5)
        em += cv2.GaussianBlur(sparks.astype(np.float32), (0, 0), 0.8)[..., None] * np.array([3.0, 1.2, 0.3], np.float32)

        # flames ride the active edge
        fl = np.zeros((H, W, 3), np.float32)
        active = (st > 0.0) & (st < 0.18) & (paper_a0 > 0)
        front_len = float(active.sum()) / pw
        centroid = None
        if not lit and plates:
            pts = []
            for e in range(n_em):
                cu = int(np.clip(em_u[e], 0, 1) * (pw - 1))
                band = active[:, max(0, cu - 12):cu + 12]
                rows = np.where(band.any(axis=1))[0]
                target = 1.0 if rows.size else 0.0
                em_level[e] += (target - em_level[e]) * 0.18
                if em_level[e] < 0.03 or not rows.size:
                    continue
                pu, pv = cu, int(rows.max())
                p = cv2.perspectiveTransform(np.array([[[pu, pv]]], np.float32), M)[0, 0] + cut_shift[0]
                pts.append(p)
                fr = plates[em_plate[e]]
                im = fr[(em_off[e] + fo) % len(fr)][..., ::-1].astype(np.float32) / 255.0
                im = np.clip((im - 0.035) / 0.95, 0, 1)
                a = smooth(im.max(axis=2), 0.06, 0.3)
                hh = int(ph * 0.42 * em_scale[e] * min(1.0, 0.5 + front_len / 2))
                ww = int(hh * im.shape[1] / im.shape[0] / 0.45 * 0.55)
                spr = cv2.resize(im * a[..., None], (max(8, ww), max(8, hh)))
                fh_, fw_ = spr.shape[:2]
                ex = np.minimum(np.linspace(0, 1, fw_), np.linspace(1, 0, fw_))
                ey = np.linspace(0, 1, fh_)
                spr *= (np.minimum(ex / 0.3, 1)[None, :] * np.minimum(ey / 0.35, 1)[:, None] * np.minimum((1 - ey) / 0.2, 1)[:, None])[..., None]
                pad = int(max(fw_, fh_) * 0.9)
                canvas = np.zeros((fh_ + 2 * pad, fw_ + 2 * pad, 3), np.float32)
                canvas[pad:pad + fh_, pad:pad + fw_] = spr
                R = cv2.getRotationMatrix2D((pad + fw_ / 2, pad + fh_), math.degrees(wind), 1.0)
                canvas = cv2.warpAffine(canvas, R, (canvas.shape[1], canvas.shape[0]))
                x0, y0 = int(p[0] - pad - fw_ / 2), int(p[1] - pad - fh_ * 0.9)
                xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + canvas.shape[1]), min(H, y0 + canvas.shape[0])
                if xb > xa and yb > ya:
                    sub = canvas[ya - y0:yb - y0, xa - x0:xb - x0] * em_level[e]
                    fl[ya:yb, xa:xb] = 1 - (1 - fl[ya:yb, xa:xb]) * (1 - np.clip(sub, 0, 1))
            if pts:
                centroid = np.mean(pts, axis=0)
        # flame cores clip warm-white; bloom
        fl = np.clip(fl * 1.15, 0, 1)
        fq = cv2.resize(fl, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
        bloom = cv2.resize(cv2.GaussianBlur(fq, (0, 0), 6) * 0.35 + cv2.GaussianBlur(fq, (0, 0), 30) * 0.15 * np.array([1.0, 0.35, 0.16], np.float32), (W, H))

        # shared light: intensity from flames + edge glow; falloff around the fire
        I_now = float(fl.mean() * 60 + em.mean() * 25)
        I_s += (I_now - I_s) * 0.45
        if centroid is None:
            ys_, xs_ = np.where(rim_vis > 0.3)
            if xs_.size:
                centroid = cv2.perspectiveTransform(np.array([[[xs_.mean(), ys_.mean()]]], np.float32), M)[0, 0] + cut_shift[0]
            else:
                centroid = np.array([cx, cy], np.float32)
        dd = np.hypot(gx - centroid[0], gy - centroid[1])
        light = (I_s / (1 + (dd / 300.0) ** 2))[..., None] * np.array([1.0, 0.45, 0.25], np.float32)
        ambient = 0.2 if not lit else 0.36
        key = 0.0
        if lit:  # a lighter just out of frame, right
            key = 1.1 * np.exp(-(((gx - W * 0.9) / 600) ** 2 + ((gy - cy) / 500) ** 2))[..., None] * np.array([1.0, 0.62, 0.32], np.float32)
        illum = ambient * np.array([0.9, 0.75, 0.6], np.float32) + light + key

        # warp paper layers into the frame (with the jump-cut reframing)
        Mk = M.copy()
        Mk[0, 2] += cut_shift[0, 0]
        Mk[1, 2] += cut_shift[0, 1]
        warp = lambda a: cv2.warpPerspective(a, Mk, (W, H), flags=cv2.INTER_LINEAR, borderValue=0)  # noqa: E731
        p_col, p_a, p_em = warp(col), warp(alpha.astype(np.float32)), warp(em)
        p_hx, p_hy = warp(hx), warp(hy)
        # facing the fire: brighter; away: darker (curled ash catches the light)
        lx, ly = (centroid[0] - gx), (centroid[1] - gy)
        ln = np.hypot(lx, ly) + 1e-3
        facing = np.clip(1 + 0.08 * (-(p_hx * lx + p_hy * ly) / ln) * 6, 0.55, 1.6)[..., None]
        # contact shadow, away from the fire, flickering against it
        off = (np.array([cx, cy]) - centroid)
        off = off / (np.hypot(*off) + 1e-3) * 7
        shadow_src = cv2.warpAffine(p_a, np.float32([[1, 0, off[0]], [0, 1, off[1]]]), (W, H))
        shadow = cv2.GaussianBlur(shadow_src, (0, 0), 9) * 0.55 + cv2.GaussianBlur(shadow_src, (0, 0), 2) * 0.25
        shadow = np.clip(shadow * (0.7 + 0.3 / (1 + I_s)), 0, 0.75)[..., None]

        g = ground * illum * vign * (1 - shadow)
        paper_lit = p_col * illum * facing
        frame = g * (1 - p_a[..., None]) + paper_lit * p_a[..., None] + p_em * p_a[..., None]
        frame = 1 - (1 - np.clip(frame, 0, None)) * (1 - fl)
        frame = frame + bloom
        # auto-exposure breathing (phone)
        target = 1.0 / (1 + 0.18 * I_s)
        exposure += (target - exposure) * 0.11
        frame = frame * exposure
        # filmic shoulder: nothing clips harshly except flame cores
        frame = frame / (1 + 0.35 * np.maximum(frame - 0.75, 0))
        frame = np.clip(frame, 0, 1) ** (1 / 1.04)
        proc.stdin.write((frame * 255).astype(np.uint8).tobytes())
    proc.stdin.close()
    proc.wait()
    print(f"{cfg['out']}: {n_out} frames, segments {segs}")


if __name__ == "__main__":
    main(sys.argv[1])
