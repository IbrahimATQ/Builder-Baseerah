#!/usr/bin/env python3
"""Burning-paper scene, v4 (third revision; answers the v3 judges' top fixes).

  * one continuous burn; camera motion is a whole-frame drift (paper never slides on the ground);
    optional single cut with a small time skip and a whole-frame re-aim
  * linear-light rendering: flames are ADDED as light (cores clip warm-white) and act as point lights
    above the paper, E = I*h/(h^2+r^2)^1.5, lighting paper and ground; lagged phone auto-exposure
  * fire arrival time solved with the eikonal equation from the ignition seed (scikit-fmm): the front
    only grows from burnt paper (no spot ignitions, no islands), with fibre-scale raggedness
  * char stays in place as a near-black satin sheet (domed, shaded by the fire); only small bites
    break away at the free edges; thin grey-white ash only along cracks of the oldest char
  * flames: one emitter per ~55 px of burning edge, each with its own lean around a drifting wind,
    drawn only where there is fuel
  * night-phone look: soft, temporally smooth noise with blotchy chroma, slight softness
Uses the paper, handwriting and ground helpers of paper_burn3.py.
Usage: python paper_burn4.py config.json   (same config keys as paper_burn3.py; "cut_at": output
seconds of an optional single jump cut, "cut_skip": simulation seconds skipped there)
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
from paper_burn3 import asphalt, handwritten_line, noise, smooth  # noqa: E402

W, H, FPS = 1080, 1920, 30
lin = lambda x: np.power(np.clip(x, 0, None), 2.2)  # noqa: E731
disp = lambda x: np.power(np.clip(x, 0, None), 1 / 2.2)  # noqa: E731


def main(cfg_p: str) -> None:
    cfg = json.load(open(cfg_p, encoding="utf-8"))
    rng = np.random.default_rng(cfg.get("seed", 3))
    dur = float(cfg["duration"])
    n_out = int(round(dur * FPS))
    pw, ph = cfg.get("paper_wh", [930, 277])
    font = cfg.get("font", "/home/user/film/typo/fonts/scheherazadenew-ScheherazadeNew-Medium.ttf")
    pre_len = float(cfg.get("pre_len", 0.0))  # unlit presentation at the start (output seconds)
    cut_at, cut_skip = cfg.get("cut_at"), float(cfg.get("cut_skip", 0.4))
    sim0 = float(cfg.get("sim_start", 0.0))

    # ---------- paper ----------
    yy, xx = np.mgrid[0:ph, 0:pw].astype(np.float32)
    fib = noise((ph, pw), rng, 4, 3)
    low = noise((ph, pw), rng, 220, 3)
    cockle = noise((ph, pw), rng, 160, 2)
    alb_d = np.array([0.9, 0.85, 0.78], np.float32)[None, None] * (0.96 + 0.05 * fib[..., None]) * (0.95 + 0.1 * low[..., None])
    edge_jit = (noise((ph, pw), rng, 30, 2) - 0.5) * 2.0
    edge = np.minimum(np.minimum(xx, pw - 1 - xx), np.minimum(yy, ph - 1 - yy)) + edge_jit
    paper_a0 = np.clip(edge - 0.5, 0, 1)
    ink = handwritten_line(cfg["line"], font, int(cfg.get("font_size", 64)), pw, ph, rng)
    ink = np.clip(cv2.GaussianBlur(ink, (0, 0), 0.5), 0, 1)

    # ---------- eikonal arrival time from the ignition seed ----------
    u0, v0 = cfg.get("origin", [0.55, 1.0])
    seed_r = 6.0
    phi = np.hypot(xx - u0 * (pw - 1), yy - min(v0 * (ph - 1), ph - 1)) - seed_r
    sp = float(cfg.get("speed_px", 55)) * (0.35 + 1.3 * noise((ph, pw), rng, 120, 3)) * (0.55 + 0.9 * noise((ph, pw), rng, 28, 3))
    sp *= 1 + 0.3 * (1 - yy / ph)
    sp *= 0.45 + 1.1 * noise((ph, pw), rng, 5, 2)  # fibre-scale raggedness
    sp *= np.where(noise((ph, pw), rng, 14, 2) > 0.72, 2.2, 1.0)  # a few fingers race ahead
    T = np.ma.filled(skfmm.travel_time(phi, sp, dx=1.0), 0).astype(np.float32)
    T += 0.06 * (noise((ph, pw), rng, 5, 2) - 0.5)
    T -= float(cfg.get("preroll", 1.2))
    cap = float(cfg.get("burn_cap", 1.0))
    if cap < 1.0:
        thr = np.quantile(T, cap)
        T = np.where(T > thr, thr + (T - thr) * 5.0, T)
    crinkle = noise((ph, pw), rng, 7, 3)
    domen = noise((ph, pw), rng, 55, 2)
    cracks = np.clip(1 - np.abs(noise((ph, pw), rng, 22, 3) - 0.5) / 0.012, 0, 1) * (noise((ph, pw), rng, 60, 2) > 0.62)
    bite = (edge < 10 + 30 * noise((ph, pw), rng, 25, 2))  # only free edges may crumble
    t_bite = 3.0 + 2.0 * noise((ph, pw), rng, 20, 2)

    # ---------- placement (fixed; camera moves the whole frame later) ----------
    cx, cy = cfg.get("center", [540, 990])
    tilt = math.radians(cfg.get("tilt_deg", -0.8))
    corners = np.array([[-pw / 2 * 0.985, -ph / 2], [pw / 2 * 0.985, -ph / 2], [pw / 2, ph / 2], [-pw / 2, ph / 2]], np.float32)
    rot = np.array([[math.cos(tilt), -math.sin(tilt)], [math.sin(tilt), math.cos(tilt)]], np.float32)
    M = cv2.getPerspectiveTransform(np.array([[0, 0], [pw, 0], [pw, ph], [0, ph]], np.float32), corners @ rot.T + np.array([cx, cy], np.float32))
    warp = lambda a: cv2.warpPerspective(a, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=0)  # noqa: E731

    ground_lin = lin(cv2.GaussianBlur(asphalt(rng), (0, 0), 1.1) * 1.05)
    gy, gx = np.mgrid[0:H, 0:W].astype(np.float32)
    # directional, neutral-cool ambient: brighter lower-left, dark top
    amb_map = (0.022 + 0.05 * np.clip(1 - gx / W, 0, 1) * smooth(gy / H, 0.3, 0.75))[..., None] * np.array([0.95, 0.88, 0.8], np.float32)
    p_a0 = warp(paper_a0.astype(np.float32))

    # ---------- flame plates ----------
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
    max_em = int(cfg.get("max_flames", 10))
    em_pos = [None] * max_em
    em_level = np.zeros(max_em, np.float32)
    em_plate = rng.integers(0, max(1, len(plates)), max_em)
    em_off = rng.integers(0, 200, max_em)
    em_scale = rng.uniform(0.75, 1.2, max_em)
    em_lean = rng.uniform(-15, 15, max_em)
    wind0 = float(cfg.get("wind_deg", 28))
    wind_drift = noise((1, n_out + 10), rng, 40, 2)[0]

    cam = noise((3, n_out + 10), rng, 50, 3)
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                             "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", cfg["out"]], stdin=subprocess.PIPE)
    exposure, I_lag = 1.0, 0.0
    flick_state = 0.0
    nlf = noise((1, n_out + 10), rng, 3, 3)[0]  # 1/f-ish flicker over time
    for fo in range(n_out):
        ot = fo / FPS
        presenting = ot < pre_len
        after_cut = cut_at is not None and ot >= cut_at
        t = sim0 + max(0.0, ot - pre_len) + (cut_skip if after_cut else 0.0)

        st = (t - T) if not presenting else np.full_like(T, -10.0)
        scorch = smooth(st, -0.25, 0.0)
        rim = np.exp(-((st - 0.03) / 0.028) ** 2) * (st > -0.02)
        flick = cv2.resize(noise((ph // 6, pw // 6), np.random.default_rng(1000 + int(t * 12)), 6, 2), (pw, ph))
        rim_vis = rim * smooth(flick, 0.3, 0.7)
        char = smooth(st, 0.05, 0.12)
        old = smooth(st, 1.2, 2.5)
        gone = bite & (st > t_bite)
        alpha = paper_a0 * (~gone)

        # albedo (linear)
        sc1, sc2 = lin(np.array([170, 120, 70], np.float32) / 255), lin(np.array([60, 35, 20], np.float32) / 255)
        a_lin = lin(alb_d)
        a_lin = a_lin * (1 - scorch[..., None]) + (sc1 * (1 - scorch[..., None] ** 2) + sc2 * scorch[..., None] ** 2) * scorch[..., None]
        inkl = lin(np.array([30, 24, 20], np.float32) / 255)
        a_lin = a_lin * (1 - ink[..., None]) + inkl * ink[..., None]
        char_alb = 0.035 * (0.75 + 0.5 * crinkle[..., None]) * np.array([1.0, 0.85, 0.75], np.float32)
        char_alb = char_alb * (1 - 0.3 * ink[..., None])  # glossier ink on char
        ash_alb = 0.22 * np.array([1.0, 0.95, 0.9], np.float32)
        char_alb = char_alb * (1 - (cracks * old)[..., None]) + ash_alb * (cracks * old)[..., None]
        a_lin = a_lin * (1 - char[..., None]) + char_alb * char[..., None]

        # dome: charred paper rises; paper near the front lifts a little; cockles everywhere
        z = 35.0 * smooth(st, 0.05, 0.8) * (0.5 + domen) + 4.0 * smooth(st, -0.4, 0.0) + 3.0 * cockle
        nzy, nzx = np.gradient(cv2.GaussianBlur(z, (0, 0), 4))
        # emission (linear): thin broken edge glow + sparks
        em = rim_vis[..., None] * lin(np.array([230, 60, 30], np.float32) / 255) * 6.0
        sparks = (rng.random((ph, pw)) > 0.9994) & (st > 0.08) & (st < 0.45)
        em += cv2.GaussianBlur(sparks.astype(np.float32), (0, 0), 0.8)[..., None] * np.array([4.0, 1.4, 0.3], np.float32)

        # ---------- flame emitters on the burning edge ----------
        active = (st > 0.0) & (st < 0.3) & (paper_a0 > 0) & (~gone)
        n_act = int(active.sum())
        want = 0 if presenting else int(np.clip(n_act / (55 * 18), 0, max_em))
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
                if all(p is None or np.hypot(*(cand - p)) > 55 for p in em_pos):
                    em_pos[e] = cand
                continue
            dd = np.hypot(xs_ - em_pos[e][0], ys_ - em_pos[e][1])
            j = int(np.argmin(dd))
            if dd[j] > 50:
                em_level[e] *= 0.75
                if em_level[e] < 0.05:
                    em_pos[e] = None
                continue
            em_pos[e] = em_pos[e] * 0.7 + np.float32([xs_[j], ys_[j]]) * 0.3
            em_level[e] += (1.0 - em_level[e]) * 0.25

        fl = np.zeros((H, W, 3), np.float32)
        lights = []
        wind = wind0 + 10 * (wind_drift[fo] - 0.5)
        for e in range(max_em):
            if em_pos[e] is None or em_level[e] < 0.03 or not plates:
                continue
            p = cv2.perspectiveTransform(np.array([[em_pos[e]]], np.float32), M)[0, 0]
            p[1] -= 8
            fr = plates[em_plate[e]]
            im = lin(fr[(em_off[e] + 2 * fo) % len(fr)][..., ::-1].astype(np.float32) / 255.0)
            im = np.clip((im - 0.002) / 0.98, 0, None)
            hh = int(ph * 0.42 * em_scale[e])
            ww = int(hh * im.shape[1] / im.shape[0] / 0.5 * 0.5)
            spr = cv2.resize(im, (max(8, ww), max(8, hh)))
            fh_, fw_ = spr.shape[:2]
            ex = np.minimum(np.linspace(0, 1, fw_), np.linspace(1, 0, fw_))
            ey = np.linspace(0, 1, fh_)
            spr *= (np.minimum(ex / 0.3, 1)[None, :] * np.minimum(ey / 0.35, 1)[:, None] * np.minimum((1 - ey) / 0.15, 1)[:, None])[..., None]
            pad = int(max(fw_, fh_) * 0.9)
            canvas = np.zeros((fh_ + 2 * pad, fw_ + 2 * pad, 3), np.float32)
            canvas[pad:pad + fh_, pad:pad + fw_] = spr
            R = cv2.getRotationMatrix2D((pad + fw_ / 2, pad + fh_), wind + em_lean[e], 1.0)
            canvas = cv2.warpAffine(canvas, R, (canvas.shape[1], canvas.shape[0])) * em_level[e]
            x0, y0 = int(p[0] - pad - fw_ / 2), int(p[1] - pad - fh_ * 0.92)
            xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + canvas.shape[1]), min(H, y0 + canvas.shape[0])
            if xb > xa and yb > ya:
                fl[ya:yb, xa:xb] += canvas[ya - y0:yb - y0, xa - x0:xb - x0]
            lights.append((p, float(canvas.sum()) / 4000.0))

        # ---------- lighting (linear) ----------
        flick_state = 0.8 + 0.4 * nlf[fo]
        E = np.zeros((H, W, 1), np.float32)
        hgt = 120.0
        for (p, I) in lights:
            r2 = (gx - p[0]) ** 2 + (gy - p[1]) ** 2
            E += (I * flick_state * hgt / (hgt ** 2 + r2) ** 1.5 * 3.5e4)[..., None]
        p_em = warp(em)
        near = cv2.resize(cv2.GaussianBlur(cv2.resize(p_em.sum(axis=2), (W // 4, H // 4), interpolation=cv2.INTER_AREA), (0, 0), 5), (W, H))[..., None]
        fire = (E + 0.25 * near) * np.array([1.0, 0.45, 0.2], np.float32)
        key = 0.0
        if presenting:  # a lighter just out of frame, right
            key = 0.12 * np.exp(-(((gx - W * 0.92) / 520) ** 2 + ((gy - cy) / 420) ** 2))[..., None] * np.array([1.0, 0.6, 0.3], np.float32)

        # paper shading from the fire (dome normals; Lambert + weak satin specular on char)
        p_alb, p_a = warp(a_lin), warp(alpha.astype(np.float32))
        p_nx, p_ny, p_char = warp(nzx), warp(nzy), warp(char.astype(np.float32))
        if lights:
            lp = np.mean([p for p, _ in lights], axis=0)
        else:
            lp = np.float32([cx, cy - 60])
        lx, ly = (lp[0] - gx), (lp[1] - gy)
        ln = np.hypot(lx, ly) + 1e-3
        lam = np.clip(1 + 0.25 * (p_nx * lx + p_ny * ly) / ln * -1, 0.4, 1.6)[..., None]
        spec = (0.2 * p_char * np.clip(-(p_nx * lx + p_ny * ly) / ln, 0, 1) ** 2)[..., None]
        illum_paper = amb_map * 1.25 + 0.06 + fire * lam + key
        illum_ground = amb_map + fire + key * 0.6

        # contact shadow of the strip on the ground, away from the fire
        off = np.float32([cx, cy]) - lp
        off = off / (np.hypot(*off) + 1e-3) * 6
        sh = cv2.warpAffine(p_a, np.float32([[1, 0, off[0]], [0, 1, off[1]]]), (W, H))
        shadow = np.clip(cv2.GaussianBlur(sh, (0, 0), 8) * 0.55 + cv2.GaussianBlur(sh, (0, 0), 1.5) * 0.3, 0, 0.75)[..., None]

        frame = ground_lin * illum_ground * (1 - shadow)
        paper = p_alb * illum_paper + spec * fire + p_em
        frame = frame * (1 - p_a[..., None]) + paper * p_a[..., None]
        frame = frame + fl * 1.8  # flames are light
        bq = cv2.resize(fl, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
        frame += cv2.resize(cv2.GaussianBlur(bq, (0, 0), 6) * 0.25 + cv2.GaussianBlur(bq, (0, 0), 28) * 0.12, (W, H))

        # lagged auto-exposure (blooms, then recovers)
        I_tot = float(sum(I for _, I in lights))
        I_lag += (I_tot - I_lag) * 0.06
        target = 1.0 / (1 + 0.5 * I_lag)
        exposure += (target - exposure) * 0.06
        frame = frame * exposure * 2.2
        out = disp(frame / (1 + 0.6 * np.maximum(frame - 0.85, 0)))

        # whole-frame camera: slow drift, roll, breathing; re-aim at the cut
        dx = 3.0 * (cam[0, fo] - 0.5) + (4.5 if after_cut else 0.0)
        dy = 3.0 * (cam[1, fo] - 0.5) + (-3.0 if after_cut else 0.0)
        rot_deg = 0.2 * (cam[2, fo] - 0.5)
        A = cv2.getRotationMatrix2D((W / 2, H / 2), rot_deg, 1.0 + 0.003 * (cam[2, fo] - 0.5))
        A[0, 2] += dx
        A[1, 2] += dy
        out = cv2.warpAffine(out, A, (W, H), borderMode=cv2.BORDER_REFLECT)

        # night phone: temporally smooth, soft noise; blotchy chroma; slight softness
        nr = np.random.default_rng(90000 + fo)
        luma = cv2.resize(nr.normal(0, 0.006, (H // 3, W // 3)).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
        chroma = cv2.resize(nr.normal(0, 0.006, (H // 16, W // 16, 3)).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
        out = cv2.GaussianBlur(out, (0, 0), 0.7) + luma[..., None] + chroma
        out = cv2.resize(cv2.resize(out, (720, 1280), interpolation=cv2.INTER_AREA), (W, H), interpolation=cv2.INTER_CUBIC)
        out = np.clip(0.012 + out * 0.988, 0, 1)
        proc.stdin.write((out * 255).astype(np.uint8).tobytes())
    proc.stdin.close()
    proc.wait()
    print(f"{cfg['out']}: {n_out} frames")


if __name__ == "__main__":
    main(sys.argv[1])
