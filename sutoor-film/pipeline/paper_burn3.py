#!/usr/bin/env python3
"""Burning-paper scene, v3 (second revision after independent realism reviews of v1 and v2).

Changes from v2, each answering a judge finding:
  * ground: visible asphalt around the strip, lit by the fire with per-frame flicker (no black void)
  * burn: no noise "holes" in intact paper and no edge bites; the hole grows from the ignition point
    as the OLDEST ash crumbles away first; the edge glow is thin, broken and red
  * curl: burnt flaps are displaced off the paper plane (lift), shaded from the fire, with a dark gap
    and a shadow under them
  * flames: emitters live only on the burning edge and track it; flames are keyed and composited
    "over" (they hide the ink behind them); plates play at 2x so they move like small paper flames
  * light: paper brighter (reference-like), strong flickering fire light on paper and ground
  * phone feel: temporal luma/chroma noise in every frame, softness, stronger jump-cut reframing
  * handwriting: every word is drawn differently (size, slant, weight, wobble, ink density), so
    repeated words do not share outlines

Config JSON as in paper_burn2.py (line, out, duration, segments with optional "pre", preroll,
origin, speed_px, flames, font, font_size, paper_wh, center, tilt_deg, wind_deg, n_flames, seed,
burn_cap). Usage: python paper_burn3.py config.json
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


def hand_word(word, font, size, rng):
    """One word as a pen would write it: own scale, slant, weight, wobble and ink density."""
    b = font.getbbox(word, direction="rtl", language="ar")
    pad = 30
    im = Image.new("L", (b[2] - b[0] + 2 * pad, int(size * 2.3)), 0)
    ImageDraw.Draw(im).text((pad - b[0], int(size * 0.5)), word, font=font, fill=255, direction="rtl", language="ar")
    a = np.asarray(im, np.float32) / 255.0
    h, w = a.shape
    sc = rng.uniform(0.95, 1.05)
    shear = rng.uniform(-0.07, 0.05)
    ang = math.radians(rng.uniform(-1.6, 1.6))
    M = np.float32([[sc * math.cos(ang), -sc * math.sin(ang) + shear, 0], [sc * math.sin(ang), sc * math.cos(ang), 0]])
    M[:, 2] = np.float32([w / 2, h / 2]) - M[:, :2] @ np.float32([w / 2, h / 2])
    a = cv2.warpAffine(a, M, (w, h), flags=cv2.INTER_CUBIC)
    wob = 1.3
    dx = (noise((h, w), rng, 18, 2) - 0.5) * 2 * wob
    dy = (noise((h, w), rng, 18, 2) - 0.5) * 2 * wob
    gy, gx = np.mgrid[0:h, 0:w].astype(np.float32)
    a = cv2.remap(a, gx + dx, gy + dy, cv2.INTER_LINEAR)
    k = rng.choice([-1, 0, 0, 1])  # pen weight
    if k:
        a = (cv2.dilate if k > 0 else cv2.erode)(a, np.ones((2, 2), np.uint8))
    press = np.linspace(rng.uniform(0.85, 1.0), rng.uniform(0.75, 0.95), w)[None, :]  # pressure fades along the stroke
    dens = 0.78 + 0.22 * noise((h, w), rng, 5, 2)
    return np.clip(a * press * dens, 0, 1)


def handwritten_line(text, font_path, size, pw, ph, rng):
    font = ImageFont.truetype(font_path, size, layout_engine=ImageFont.Layout.RAQM)
    words = [hand_word(w, font, size, rng) for w in text.split(" ")]
    gaps = [int(size * rng.uniform(0.25, 0.42)) for _ in words]
    total = sum(w.shape[1] for w in words) + sum(gaps[:-1])
    canvas = np.zeros((ph, pw), np.float32)
    x = (pw + total) // 2
    base = int(rng.uniform(-3, 3))
    for i, wd in enumerate(words):
        x -= wd.shape[1]
        y = (ph - wd.shape[0]) // 2 + base + int(rng.uniform(-3, 3)) + int(i * rng.uniform(-0.6, 1.2))  # line drifts a little
        ya, yb = max(0, y), min(ph, y + wd.shape[0])
        xa, xb = max(0, x), min(pw, x + wd.shape[1])
        canvas[ya:yb, xa:xb] = np.maximum(canvas[ya:yb, xa:xb], wd[ya - y:yb - y, xa - x:xb - x])
        x -= gaps[i]
    return canvas


def asphalt(rng):
    stones = np.zeros((H, W), np.float32)
    n = 30000
    for x, y, r, v in zip(rng.integers(0, W, n), rng.integers(0, H, n), rng.uniform(1.0, 3.8, n), rng.uniform(0.35, 1.0, n)):
        cv2.circle(stones, (int(x), int(y)), int(round(r)), float(v), -1)
    stones = cv2.GaussianBlur(stones, (0, 0), 0.8)
    binder = 0.34 + 0.14 * noise((H, W), rng, 40, 3)
    grit = cv2.GaussianBlur(rng.random((H, W)).astype(np.float32), (0, 0), 0.7)
    mott = noise((H, W), rng, 260, 4)
    albedo = np.maximum(binder, stones * 0.8) * (0.75 + 0.5 * mott) * (0.85 + 0.3 * grit)
    crack = np.zeros((H, W), np.float32)
    x, y = float(rng.uniform(0, W)), 0.0
    while y < H:
        nx, ny = x + rng.uniform(-30, 30), y + rng.uniform(20, 60)
        cv2.line(crack, (int(x), int(y)), (int(nx), int(ny)), 1.0, 2)
        x, y = nx, ny
    albedo *= 1 - 0.55 * cv2.GaussianBlur(crack, (0, 0), 1.0)
    for _ in range(6):
        cx, cy = int(rng.uniform(80, W - 80)), int(rng.uniform(200, H - 200))
        cv2.ellipse(albedo, (cx, cy), (int(rng.uniform(5, 11)), int(rng.uniform(2, 4))), float(rng.uniform(0, 180)), 0, 360, float(rng.uniform(1.1, 1.4)), -1)
    return (albedo[..., None] * np.array([1.0, 0.72, 0.52], np.float32) * 0.55).astype(np.float32)


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
    albedo = np.array([0.9, 0.84, 0.76], np.float32)[None, None] * (0.96 + 0.05 * fib[..., None]) * (0.95 + 0.1 * low[..., None])
    edge_jit = (noise((ph, pw), rng, 30, 2) - 0.5) * 2.0
    edge = np.minimum(np.minimum(xx, pw - 1 - xx), np.minimum(yy, ph - 1 - yy)) + edge_jit
    paper_a0 = np.clip(edge - 0.5, 0, 1)
    thickness = np.clip(1 - edge / 1.6, 0, 1) * paper_a0
    ink = handwritten_line(cfg["line"], font, int(cfg.get("font_size", 64)), pw, ph, rng)
    ink = np.clip(cv2.GaussianBlur(ink, (0, 0), 0.5), 0, 1)
    ink_col = np.array([30, 24, 20], np.float32) / 255

    # ---------- fire arrival time ----------
    u0, v0 = cfg.get("origin", [0.55, 1.0])
    wx = (noise((ph, pw), rng, 90, 3) - 0.5) * 70
    wy = (noise((ph, pw), rng, 90, 3) - 0.5) * 70
    d = np.sqrt((xx + wx - u0 * pw) ** 2 + ((yy + wy - v0 * ph) * 1.2) ** 2)
    speed = float(cfg.get("speed_px", 60)) * (0.5 + 1.0 * noise((ph, pw), rng, 70, 3)) * (1 + 0.3 * (1 - yy / ph))
    T = d / speed - float(cfg.get("preroll", 1.2))
    cap = float(cfg.get("burn_cap", 1.0))
    if cap < 1.0:
        thr = np.quantile(T, cap)
        T = np.where(T > thr, thr + (T - thr) * 6.0, T)  # the fire slows to a crawl instead of freezing
    t_gone = 1.5 + 1.6 * noise((ph, pw), rng, 30, 3)  # oldest ash breaks away first, from the ignition point
    crinkle = noise((ph, pw), rng, 7, 3)
    flapn = noise((ph, pw), rng, 45, 2)

    # ---------- placement ----------
    cx, cy = cfg.get("center", [540, 990])
    tilt = math.radians(cfg.get("tilt_deg", -0.8))
    corners = np.array([[-pw / 2 * 0.985, -ph / 2], [pw / 2 * 0.985, -ph / 2], [pw / 2, ph / 2], [-pw / 2, ph / 2]], np.float32)
    rot = np.array([[math.cos(tilt), -math.sin(tilt)], [math.sin(tilt), math.cos(tilt)]], np.float32)
    dst = corners @ rot.T + np.array([cx, cy], np.float32)
    M0 = cv2.getPerspectiveTransform(np.array([[0, 0], [pw, 0], [pw, ph], [0, ph]], np.float32), dst)

    ground = asphalt(rng)
    gy, gx = np.mgrid[0:H, 0:W].astype(np.float32)
    vign = np.clip(1 - 0.8 * smooth(np.hypot((gx - cx) / W, (gy - cy) / (H * 0.5)), 0.25, 0.85), 0.12, 1)[..., None]

    # ---------- flame plates: dense cores ----------
    plates = []
    for f in cfg.get("flames", []):
        cap_ = cv2.VideoCapture(f)
        fr, ok = [], True
        while ok and len(fr) < 380:
            ok, im = cap_.read()
            if ok:
                h0 = im.shape[0]
                core = im[int(h0 * 0.5):int(h0 * 0.97)]
                fr.append(cv2.resize(core, (core.shape[1] // 2, core.shape[0] // 2)))
        plates.append(fr)
    n_em = int(cfg.get("n_flames", 5))
    em_pos = [None] * n_em  # tracked position on the paper (u, v)
    em_level = np.zeros(n_em, np.float32)
    em_plate = rng.integers(0, max(1, len(plates)), n_em)
    em_off = rng.integers(0, 200, n_em)
    em_scale = rng.uniform(0.8, 1.15, n_em)
    wind = math.radians(cfg.get("wind_deg", 28))

    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                             "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", cfg["out"]], stdin=subprocess.PIPE)
    I_s, exposure = 0.0, 1.0
    for fo in range(n_out):
        ot = fo / FPS
        k, acc = 0, 0.0
        while k < len(segs) - 1 and ot >= acc + seg_len[k]:
            acc += seg_len[k]
            k += 1
        t = segs[k][0] + (ot - acc)
        lit = cfg.get("lighter", False) or (len(segs[k]) > 2 and segs[k][2] == "pre")
        # jump cut reframing (the reference's phone is re-aimed between takes)
        cr = np.random.default_rng(500 + k)
        shift = np.float32([cr.uniform(-12, 12), cr.uniform(-10, 10)]) if k else np.float32([0, 0])
        zoom = 1.0 + (cr.uniform(-0.025, 0.03) if k else 0.0)
        ev = 1.0 + (cr.uniform(-0.07, 0.07) if k else 0.0)
        Mk = M0.copy()
        S = np.float32([[zoom, 0, (1 - zoom) * cx + shift[0]], [0, zoom, (1 - zoom) * cy + shift[1]], [0, 0, 1]])
        Mk = S @ Mk

        st = (t - T) if not lit else np.full_like(T, -10.0)
        scorch = smooth(st, -0.28, 0.0)
        rim = np.exp(-((st - 0.035) / 0.03) ** 2) * (st > -0.02)
        q = int(t * 12)
        flick = cv2.resize(noise((ph // 6, pw // 6), np.random.default_rng(1000 + q), 6, 2), (pw, ph))
        rim_vis = rim * smooth(flick, 0.35, 0.7)
        char = smooth(st, 0.05, 0.12)
        ash = smooth(st, 0.6, 1.0)
        gone = st > t_gone
        alpha = paper_a0 * (~gone)

        col = albedo.copy()
        sc1 = np.array([170, 120, 70], np.float32) / 255
        sc2 = np.array([60, 35, 20], np.float32) / 255
        col = col * (1 - scorch[..., None]) + (sc1 * (1 - scorch[..., None] ** 2) + sc2 * scorch[..., None] ** 2) * scorch[..., None]
        inkv = ink * (1 - 0.65 * ash)
        col = col * (1 - inkv[..., None]) + ink_col * inkv[..., None]
        charc = (np.array([28, 15, 12], np.float32) / 255) * (0.8 + 0.4 * crinkle[..., None])
        ashc = (np.array([70, 52, 42], np.float32) / 255) * (0.75 + 0.5 * crinkle[..., None])
        burnt = charc * (1 - ash[..., None]) + ashc * ash[..., None]
        burnt = burnt * (1 - 0.3 * ink[..., None] * ash[..., None])
        col = col * (1 - char[..., None]) + burnt * char[..., None]
        col = col * (1 - 0.35 * thickness[..., None])
        em = rim_vis[..., None] * np.array([230, 60, 30], np.float32) / 255 * 2.0
        em += cv2.GaussianBlur(rim_vis, (0, 0), 3)[..., None] * np.array([1.0, 0.33, 0.1], np.float32) * 0.5
        sparks = (rng.random((ph, pw)) > 0.9994) & (st > 0.08) & (st < 0.45)
        em += cv2.GaussianBlur(sparks.astype(np.float32), (0, 0), 0.8)[..., None] * np.array([3.0, 1.2, 0.3], np.float32)

        # curl: burnt flaps are a separate layer lifted off the ground plane; intact paper stays put,
        # and where a flap curls up, the ground under its old position shows (in its shadow)
        lift = 22.0 * smooth(st, 0.05, 0.7) * (0.4 + 0.8 * flapn) * paper_a0 * (~gone)
        hy, hx = np.gradient(cv2.GaussianBlur(lift, (0, 0), 3))
        flap_m = (char * alpha).astype(np.float32)
        base_a = (alpha * (1 - char)).astype(np.float32)
        mapy = (yy + lift * 0.9).astype(np.float32)
        lifted = lambda a: cv2.remap(a, xx, mapy, cv2.INTER_LINEAR, borderValue=0)  # noqa: E731
        shade = np.clip(1 + 0.09 * (hx * 0.3 - hy) * 4, 0.6, 1.5)
        flap_col = lifted(col * shade[..., None])
        flap_a = lifted(flap_m)
        flap_em = lifted(em)
        # merge: flaps over the flat base (same paper space, then one perspective warp)
        col_l = col * (1 - flap_a[..., None]) + flap_col * flap_a[..., None]
        alpha_l = np.clip(base_a + flap_a - base_a * flap_a, 0, 1)
        em_l = em * (base_a > 0)[..., None] * (1 - flap_a[..., None]) + flap_em * flap_a[..., None]
        flap_shadow = np.clip(lift / 22.0, 0, 1) * 0.6 * (1 - base_a)

        # ---------- flames: emitters live on the burning edge and track it ----------
        fl_rgb = np.zeros((H, W, 3), np.float32)
        fl_a = np.zeros((H, W), np.float32)
        active = (st > 0.0) & (st < 0.28) & (paper_a0 > 0) & (~gone)
        pts = []
        if not lit and plates and active.any():
            ys_, xs_ = np.nonzero(active[::3, ::3])
            ys_, xs_ = ys_ * 3, xs_ * 3
            for e in range(n_em):
                if em_pos[e] is None:  # spawn on a random part of the edge, away from the others
                    j = int(rng.integers(len(xs_)))
                    cand = np.float32([xs_[j], ys_[j]])
                    if all(p is None or np.hypot(*(cand - p)) > 140 for p in em_pos):
                        em_pos[e] = cand
                    continue
                dd = np.hypot(xs_ - em_pos[e][0], ys_ - em_pos[e][1])
                j = int(np.argmin(dd))
                if dd[j] > 60:  # the edge moved on: this flame dies down and respawns elsewhere
                    em_level[e] *= 0.75
                    if em_level[e] < 0.05:
                        em_pos[e] = None
                    continue
                em_pos[e] = em_pos[e] * 0.7 + np.float32([xs_[j], ys_[j]]) * 0.3
                em_level[e] += (1.0 - em_level[e]) * 0.2
        for e in range(n_em):
            if em_pos[e] is None or em_level[e] < 0.03 or lit or not plates:
                continue
            p = cv2.perspectiveTransform(np.array([[em_pos[e]]], np.float32), Mk)[0, 0]
            p[1] -= 10  # bases sit on the lifted burning lip
            pts.append(p)
            fr = plates[em_plate[e]]
            im = fr[(em_off[e] + 2 * fo) % len(fr)][..., ::-1].astype(np.float32) / 255.0  # 2x: small flames move fast
            im = np.clip((im - 0.035) / 0.95, 0, 1)
            a = smooth(im.max(axis=2), 0.05, 0.28)
            hh = int(ph * 0.48 * em_scale[e])
            ww = int(hh * im.shape[1] / im.shape[0] / 0.45 * 0.5)
            spr = cv2.resize(im, (max(8, ww), max(8, hh)))
            sa = cv2.resize(a, (max(8, ww), max(8, hh)))
            fh_, fw_ = sa.shape
            ex = np.minimum(np.linspace(0, 1, fw_), np.linspace(1, 0, fw_))
            ey = np.linspace(0, 1, fh_)
            sa = sa * np.minimum(ex / 0.3, 1)[None, :] * np.minimum(ey / 0.35, 1)[:, None] * np.minimum((1 - ey) / 0.15, 1)[:, None]
            pad = int(max(fw_, fh_) * 0.9)
            cv_rgb = np.zeros((fh_ + 2 * pad, fw_ + 2 * pad, 3), np.float32)
            cv_a = np.zeros((fh_ + 2 * pad, fw_ + 2 * pad), np.float32)
            cv_rgb[pad:pad + fh_, pad:pad + fw_] = spr
            cv_a[pad:pad + fh_, pad:pad + fw_] = sa
            R = cv2.getRotationMatrix2D((pad + fw_ / 2, pad + fh_), math.degrees(wind), 1.0)
            cv_rgb = cv2.warpAffine(cv_rgb, R, (cv_rgb.shape[1], cv_rgb.shape[0]))
            cv_a = cv2.warpAffine(cv_a, R, (cv_a.shape[1], cv_a.shape[0])) * em_level[e]
            x0, y0 = int(p[0] - pad - fw_ / 2), int(p[1] - pad - fh_ * 0.92)
            xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + cv_a.shape[1]), min(H, y0 + cv_a.shape[0])
            if xb <= xa or yb <= ya:
                continue
            a_ = cv_a[ya - y0:yb - y0, xa - x0:xb - x0]
            c_ = cv_rgb[ya - y0:yb - y0, xa - x0:xb - x0]
            fl_rgb[ya:yb, xa:xb] = fl_rgb[ya:yb, xa:xb] * (1 - a_[..., None]) + c_ * a_[..., None]
            fl_a[ya:yb, xa:xb] = 1 - (1 - fl_a[ya:yb, xa:xb]) * (1 - a_)

        # ---------- light: strong, flickering, from the actual flames and edge ----------
        warp = lambda a: cv2.warpPerspective(a, Mk, (W, H), flags=cv2.INTER_LINEAR, borderValue=0)  # noqa: E731
        p_col, p_a, p_em = warp(col_l), warp(alpha_l), warp(em_l)
        p_fsh = warp(flap_shadow.astype(np.float32))
        I_now = float((fl_rgb * fl_a[..., None]).mean() * 90 + p_em.mean() * 40)
        I_s = I_s * 0.35 + I_now * 0.65
        I_f = I_s * (0.85 + 0.3 * np.random.default_rng(7000 + fo).random())  # frame-to-frame flicker
        if pts:
            centroid = np.mean(pts, axis=0)
        else:
            centroid = np.float32([cx, cy])
        dd = np.hypot(gx - centroid[0], gy - (centroid[1] - 40))
        q4 = lambda a: cv2.resize(a, (W // 4, H // 4), interpolation=cv2.INTER_AREA)  # noqa: E731
        light = (I_f / (1 + (dd / 340.0) ** 2))[..., None] * np.array([1.0, 0.5, 0.26], np.float32)
        near = cv2.resize(cv2.GaussianBlur(q4(p_em.sum(axis=2) + fl_a * 0.8), (0, 0), 8), (W, H))[..., None] * np.array([1.0, 0.45, 0.2], np.float32) * 1.4
        ambient = 0.30 if not lit else 0.36
        key = 0.0
        if lit:
            key = 1.0 * np.exp(-(((gx - W * 0.9) / 600) ** 2 + ((gy - cy) / 500) ** 2))[..., None] * np.array([1.0, 0.62, 0.32], np.float32)
        illum = ambient * np.array([0.92, 0.78, 0.62], np.float32) + light + near + key

        # contact shadow (strip and lifted flaps), away from the fire
        off = np.float32([cx, cy]) - centroid
        off = off / (np.hypot(*off) + 1e-3) * 8
        sh_src = cv2.warpAffine(p_a, np.float32([[1, 0, off[0]], [0, 1, off[1]]]), (W, H))
        shadow = cv2.GaussianBlur(sh_src, (0, 0), 10) * 0.5 + cv2.GaussianBlur(sh_src, (0, 0), 2) * 0.25
        shadow = np.clip(shadow * (0.8 + 0.2 / (1 + I_s)), 0, 0.7)[..., None]

        g = ground * illum * vign * (1 - shadow) * (1 - 0.5 * p_fsh[..., None])
        frame = g * (1 - p_a[..., None]) + (p_col * illum) * p_a[..., None] + p_em * p_a[..., None]
        frame = frame * (1 - fl_a[..., None]) + np.clip(fl_rgb * 1.2, 0, 1) * fl_a[..., None]
        fq = q4(fl_rgb * fl_a[..., None])
        frame += cv2.resize(cv2.GaussianBlur(fq, (0, 0), 6) * 0.35 + cv2.GaussianBlur(fq, (0, 0), 28) * 0.18 * np.array([1.0, 0.4, 0.18], np.float32), (W, H))

        target = 1.0 / (1 + 0.12 * I_s)
        exposure += (target - exposure) * 0.12
        frame = frame * exposure * ev
        frame = frame / (1 + 0.4 * np.maximum(frame - 0.78, 0))
        # phone sensor: live luma + chroma noise, a little softness, lifted floor
        nr = np.random.default_rng(90000 + fo)
        luma_n = nr.normal(0, 0.011, (H // 2, W // 2)).astype(np.float32)
        chroma_n = nr.normal(0, 0.006, (H // 4, W // 4, 3)).astype(np.float32)
        frame = cv2.GaussianBlur(frame, (0, 0), 0.6)
        frame += cv2.resize(luma_n, (W, H))[..., None] * (0.6 + 0.8 * (1 - np.clip(frame.mean(axis=2, keepdims=True) * 3, 0, 1)))
        frame += cv2.resize(chroma_n, (W, H))
        frame = 0.008 + np.clip(frame, 0, 1) * 0.992
        frame = np.clip(frame, 0, 1) ** (1 / 1.04)
        proc.stdin.write((frame * 255).astype(np.uint8).tobytes())
    proc.stdin.close()
    proc.wait()
    print(f"{cfg['out']}: {n_out} frames, segments {segs}")


if __name__ == "__main__":
    main(sys.argv[1])
