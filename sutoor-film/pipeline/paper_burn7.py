#!/usr/bin/env python3
"""Burning paper on a REAL photographed plate (v7, the Journey edition's three burns).

Only the paper is simulated (its fibres, ink, scorch, char, curl, ember strokes); the world it lies in
is real footage, and so are the flames, smoke and sparks:
  * plate: a still or a moving shot (optionally rotated / cropped) graded to the scene's light; the
    fire relights it (plate colour taken as albedo) and the paper casts a contact shadow on it
  * the sheet is placed with a perspective quad, so it sits in the plate's own ground plane
  * flames are sprites cut from real flames-on-black plates, standing upright on the burning edge,
    plus an optional whole-sheet flame plate (a letter that catches all at once)
  * smoke and sparks are real plates screen-composited around the fire
  * burn timing: the front reads the line right to left and passes each word at a given film time;
    optional "wounds" (arrow holes) that ignite just ahead of the front; optional "catch" (whole sheet
    at once at a time) after a slow scorch from beneath
  * ember_word: one word's ink survives as glowing strokes that breathe with gusts and cool (thin
    strokes and dots first) after a quench
  * depth of field: the sheet takes the plate's focus (blur rising toward its ends), and its grain
    and softness match the plate

Usage: python paper_burn7.py config.json     (keys: see data/journey/burn*.json)
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
import paper_burn6 as v6  # noqa: E402
from paper_burn3 import noise, smooth  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402

lin = lambda x: np.power(np.clip(x, 0, None), 2.2)  # noqa: E731
disp = lambda x: np.power(np.clip(x, 0, None), 1 / 2.2)  # noqa: E731


class Plate:
    """Frames of a real shot (or one still), rotated/cropped and resized to the output frame."""

    def __init__(self, cfg: dict, W: int, H: int, fps: int, n: int):
        self.W, self.H = W, H
        self.still = bool(cfg.get("still", False))
        rot = int(cfg.get("rotate", 0))
        vf = []
        if cfg.get("crop"):
            x, y, w, h = cfg["crop"]
            vf.append(f"crop={w}:{h}:{x}:{y}")
        if rot == 90:
            vf.append("transpose=1")
        elif rot == 270:
            vf.append("transpose=2")
        if cfg.get("flip"):
            vf.append("hflip")
        vf.append(f"scale={W}:{H}:flags=lanczos,format=rgb24")
        rate = cfg.get("rate", 1.0)
        dur = (1 if self.still else n / fps * rate + 0.5)
        args = ["ffmpeg", "-v", "error", "-ss", str(cfg.get("in", 0)), "-i", cfg["src"], "-t", f"{dur:.3f}"]
        if not self.still:
            vf.insert(0, f"fps={fps / rate:.6f}")
            if rate != 1.0:
                vf.insert(1, f"setpts={1 / rate:.6f}*PTS")
        args += ["-vf", ",".join(vf), "-f", "rawvideo", "-"]
        self.proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.last = None

    def next(self) -> np.ndarray:
        if self.still and self.last is not None:
            return self.last
        raw = self.proc.stdout.read(self.W * self.H * 3)
        if len(raw) == self.W * self.H * 3:
            self.last = np.frombuffer(raw, np.uint8).reshape(self.H, self.W, 3).astype(np.float32) / 255.0
        return self.last


def load_frames(path: str, crop_frac=(0.0, 1.0), scale: float = 1.0, max_n: int = 400, rgb=True, skip: int = 0) -> list[np.ndarray]:
    cap = cv2.VideoCapture(path)
    for _ in range(skip):
        cap.grab()
    out = []
    while len(out) < max_n:
        ok, im = cap.read()
        if not ok:
            break
        h0 = im.shape[0]
        im = im[int(h0 * crop_frac[0]):int(h0 * crop_frac[1])]
        if scale != 1.0:
            im = cv2.resize(im, (int(im.shape[1] * scale), int(im.shape[0] * scale)), interpolation=cv2.INTER_AREA)
        out.append(im[..., ::-1] if rgb else im)
    return out


def main(cfg_p: str) -> None:
    cfg = json.load(open(cfg_p, encoding="utf-8"))
    W, H = cfg.get("size", [2160, 3840])
    FPS = int(cfg.get("fps", 24))
    S = W / 1080.0
    v6.W, v6.H, v6.S = W, H, S
    rng = np.random.default_rng(cfg.get("seed", 3))
    dur = float(cfg["duration"])
    t0 = float(cfg.get("film_t0", 0.0))
    n_out = int(round(dur * FPS))
    pw, ph = [int(v * S) for v in cfg.get("paper_wh", [960, 230])]
    font = cfg.get("font", "/home/user/Builder-Baseerah/sutoor-film/remotion/public/fonts/amiri-Amiri-Bold.ttf")

    # ---------- paper ----------
    yy, xx = np.mgrid[0:ph, 0:pw].astype(np.float32)
    alb_d, paper_a0, curl = v6.paper_maps(rng, cfg.get("paper", "plain"), pw, ph)
    if cfg.get("paper_tint"):
        alb_d = alb_d * np.array(cfg["paper_tint"], np.float32)
    fold = cfg.get("fold")
    if fold:
        fy = float(fold.get("at", 0.5)) * ph
        curl = curl + fold.get("height", 12) * S * np.clip(1 - np.abs(yy - fy) / (ph * 0.5), 0, 1) ** 1.3
        crease = np.exp(-((yy - fy) / (1.5 * S)) ** 2)
        alb_d = alb_d * (1 - 0.10 * crease[..., None])
    lg = cfg.get("light_grad")  # [left, right] light multipliers across the sheet, plus mottling
    sheet_light = np.ones((ph, pw), np.float32)
    if lg:
        sheet_light = (lg[0] + (lg[1] - lg[0]) * (xx / (pw - 1))) * (1 + float(lg[2] if len(lg) > 2 else 0.12) * (noise((ph, pw), rng, 90 * S, 2) - 0.5))
        if len(lg) > 3:  # top edge (towards the low sun) catches more light
            sheet_light *= 1 + lg[3] * smooth(1 - yy / ph, 0.6, 1.0)
    ink, boxes = v6.pen_line(cfg["line"], font, int(cfg.get("font_size", 66) * S), pw, ph, rng)
    if cfg.get("ink_y_shift"):
        ink = np.roll(ink, int(cfg["ink_y_shift"] * S), axis=0)
    ink = np.clip(cv2.GaussianBlur(ink, (0, 0), 0.4 * S), 0, 1)
    ink_rgb = np.array(cfg.get("ink_rgb", [12, 10, 10]), np.float32) / 255
    ink_density = float(cfg.get("ink_density", 1.0))

    # arrow holes ("wounds")
    holes = cfg.get("wounds")
    hole_mask = np.zeros((ph, pw), np.float32)
    hole_rim = np.zeros((ph, pw), np.float32)
    hole_pts = []
    if holes:
        hr = np.random.default_rng(holes.get("seed", 7))
        r_lo, r_hi = holes.get("r", [5, 9])
        # keep-out: no wound may touch a letter, a dot or a haraka (a stray hole reads as a dot and
        # changes the word; a hole on a dot deletes it). Distance from the hole's edge to any ink.
        dist_ink = cv2.distanceTransform((ink < 0.08).astype(np.uint8), cv2.DIST_L2, 5)
        need = (r_hi * 1.2 + float(holes.get("keepout_px", 12))) * S
        tries = 0
        while len(hole_pts) < holes.get("n", 20) and tries < 20000:
            tries += 1
            p = np.float32([hr.uniform(0.05, 0.95) * pw, hr.uniform(0.10, 0.90) * ph])
            if dist_ink[int(p[1]), int(p[0])] < need:
                continue
            if any(np.hypot(*(p - q)) < float(holes.get("min_gap_px", 40)) * S for q in hole_pts):
                continue
            hole_pts.append(p)
        hole_r = []
        for p in hole_pts:
            r = hr.uniform(r_lo, r_hi) * S
            hole_r.append(r)
            pts = []
            nk = 64
            # a torn puncture: an irregular lobed outline (a few low harmonics with random phase) and
            # 1-3 short tears where the head split the fibre; each hole its own shape and size
            harm = [(k, hr.uniform(0.05, 0.22) / k ** 0.6, hr.uniform(0, 2 * np.pi)) for k in range(2, 6)]
            tears = [(hr.uniform(0, 2 * np.pi), hr.uniform(0.5, 1.1), hr.uniform(0.10, 0.22)) for _ in range(int(hr.integers(1, 4)))]
            for k in range(nk):
                a = 2 * np.pi * k / nk
                rr = 1.0 + sum(am * math.cos(kk * a + ph_) for kk, am, ph_ in harm) + 0.06 * (hr.random() - 0.5)
                for ta, tl, tw in tears:
                    da = math.atan2(math.sin(a - ta), math.cos(a - ta))
                    rr += tl * max(0.0, 1 - abs(da) / tw) ** 1.5
                pts.append([p[0] + r * rr * math.cos(a), p[1] + r * rr * math.sin(a)])
            cv2.fillPoly(hole_mask, [np.int32(np.round(np.float32(pts) * 4))], 1.0, cv2.LINE_AA, shift=2)
        dist_h = cv2.distanceTransform((1 - (hole_mask > 0.5)).astype(np.uint8), cv2.DIST_L2, 3)
        rim_n = noise((ph, pw), rng, 6 * S, 2)
        hole_rim = np.exp(-dist_h / ((3 + 5 * rim_n) * S)) * (1 - hole_mask)  # irregular scorched rim
        paper_a0 = paper_a0 * (1 - hole_mask)
        ink = ink * (1 - hole_mask)
        meta_holes = {"min_dist_to_ink_px": float(min([dist_ink[int(p[1]), int(p[0])] - r for p, r in zip(hole_pts, hole_r)] or [0]))}

    # ---------- burn arrival time T (film seconds) ----------
    u0, v0 = cfg.get("origin", [1.0, 0.55])
    phi = np.hypot(xx - u0 * (pw - 1), yy - v0 * (ph - 1)) - 6.0 * S
    sp = (0.35 + 1.3 * noise((ph, pw), rng, 120 * S, 3)) * (0.55 + 0.9 * noise((ph, pw), rng, 28 * S, 3))
    sp *= 0.45 + 1.1 * noise((ph, pw), rng, 5 * S, 2)
    sp *= np.where(noise((ph, pw), rng, 14 * S, 2) > 0.72, 2.2, 1.0)
    Te = np.ma.filled(skfmm.travel_time(phi, sp.astype(np.float64), dx=1.0), 0).astype(np.float32)
    word_times = cfg.get("word_times")
    catch = cfg.get("catch")
    if catch:  # the whole sheet catches at once (spread over a fraction of a second)
        Tn = (Te - Te.min()) / (np.ptp(Te) + 1e-6)
        T = catch["t"] + catch.get("spread", 0.35) * Tn
    elif word_times:
        cols = np.where(paper_a0 > 0.5, Te, np.nan)
        m = np.nanmedian(cols, axis=0)
        m = np.where(np.isfinite(m), m, np.nanmedian(m))
        m = cv2.GaussianBlur(m[None, :].astype(np.float32), (0, 0), 25 * S)[0]
        ctr = [(a + b) / 2 for a, b in boxes]
        xs_k = [pw - 1] + ctr + [0]
        ts_k = [cfg.get("t_ignite", word_times[0] - 0.8)] + list(word_times) + [cfg.get("t_end_left", word_times[-1] + 1.0)]
        D = np.interp(np.arange(pw), xs_k[::-1], ts_k[::-1]).astype(np.float32)
        dev = Te - m[None, :]
        dev = dev / (np.percentile(np.abs(dev[paper_a0 > 0.5]), 90) + 1e-6)
        T = D[None, :] + float(cfg.get("ragged_s", 0.35)) * dev
    else:
        T = Te / float(cfg.get("speed_px", 55) * S) + float(cfg.get("t_ignite", t0))
    wig = cfg.get("wound_ignite")
    if wig and hole_pts:  # every arrow hole catches at once and the fire grows outward from each
        # one organic front from all wounds at once: travel time through the paper's own uneven
        # fibre (the same streaky speed field as the line burns), so the fronts merge and finger
        phi_h = np.where(hole_mask > 0.5, -1.0, 1.0)
        Th = np.ma.filled(skfmm.travel_time(phi_h, sp.astype(np.float64), dx=1.0), 0).astype(np.float32)
        T = float(wig["t"]) + Th / (float(wig.get("spread_px_s", 160)) * S) + float(wig.get("jitter", 0.3)) * noise((ph, pw), rng, 70 * S, 2)
        T = T + float(wig.get("jitter_fine", 0.0)) * noise((ph, pw), rng, 9 * S, 3)  # ragged fronts, never round rings
        pre = wig.get("pre")  # a few wounds far from the script already smoulder when the shot opens
        if pre:
            far = sorted(range(len(hole_pts)), key=lambda i: -dist_ink[int(hole_pts[i][1]), int(hole_pts[i][0])])[: int(pre.get("n", 3))]
            for i in far:
                p = hole_pts[i]
                d = np.hypot(xx - p[0], yy - p[1])
                tp = float(pre["t"]) + d / (float(pre.get("speed_px_s", 14)) * S * (0.6 + 0.8 * noise((ph, pw), rng, 12 * S, 2)))
                T = np.where(d < float(pre.get("max_r", 60)) * S, np.minimum(T, tp), T)
        meta_pre = True
    elif holes and hole_pts:  # wounds catch just ahead of the front: fire breaks out of each arrow hole
        lead = float(holes.get("lead_s", 0.35))
        for p in hole_pts:
            ti = T[int(p[1]), int(p[0])] - lead
            d = np.hypot(xx - p[0], yy - p[1])
            T = np.minimum(T, ti + d / (float(holes.get("spread_px_s", 160)) * S))
    T += 0.03 * (noise((ph, pw), rng, 5 * S, 2) - 0.5)
    T = T.astype(np.float32)
    scorch_pre = None
    if catch and catch.get("underheat"):  # slow scorch from beneath before the catch (coal pattern)
        uh = catch["underheat"]
        scorch_pre = (uh["t0"], uh["t1"])

    ew = cfg.get("ember_word")
    ew_mask = np.zeros((ph, pw), np.float32)
    keep_zone = np.zeros((ph, pw), bool)
    thin = np.zeros((ph, pw), np.float32)
    if ew is not None:
        k = int(ew["index"]) % len(boxes)
        xa, xb = boxes[k]
        ew_mask[:, xa:xb] = ink[:, xa:xb]
        ew_mask = np.clip(cv2.GaussianBlur(ew_mask, (0, 0), 0.5 * S) * 1.2, 0, 1)
        kp = float(ew.get("keep_px", 34)) * S
        dw = cv2.distanceTransform((ew_mask < 0.3).astype(np.uint8), cv2.DIST_L2, 5)
        ragged = kp * (0.55 + 0.9 * noise((ph, pw), rng, 26 * S, 3))
        keep_zone = (dw < ragged) & (paper_a0 > 0.5)
        # stroke thickness: thin strokes and dots cool first
        dt = cv2.distanceTransform((ew_mask > 0.3).astype(np.uint8), cv2.DIST_L2, 5)
        local = cv2.dilate(dt, np.ones((int(9 * S), int(9 * S)), np.uint8))
        thin = np.clip(1 - local / (local.max() + 1e-6), 0, 1)
    heat_k = np.array(ew["heat"] if ew else [[0, 0]], np.float32)
    gusts = ew.get("gusts", []) if ew else []
    quench = cfg.get("quench")

    crinkle = noise((ph, pw), rng, 7 * S, 3)
    n_frag = max(8, int(420 * float(cfg.get("frag_n_scale", 1.0)) * (pw * ph) / (930 * 277 * S * S)))
    frag_pts = np.column_stack([rng.uniform(0, pw, n_frag), rng.uniform(0, ph, n_frag)])
    fw_amp = float(cfg.get("frag_warp_px", 14)) * S
    wx = xx + fw_amp * (noise((ph, pw), rng, 18 * S, 3) - 0.5) * 2
    wy = yy + fw_amp * (noise((ph, pw), rng, 18 * S, 3) - 0.5) * 2
    fd, fidx = cKDTree(frag_pts).query(np.column_stack([wx.ravel(), wy.ravel()]), k=2)
    del wx, wy
    frag_edge = smooth(((fd[:, 1] - fd[:, 0]).reshape(ph, pw)), 0.0, 2.5 * S)
    keep = rng.random(len(frag_pts)) < float(cfg.get("char_keep", 0.45))
    drop_lo, drop_hi = cfg.get("drop_after", [0.9, 2.2])
    t_drop = np.where(keep[fidx[:, 0]], 99.0, rng.uniform(drop_lo, drop_hi, len(frag_pts))[fidx[:, 0]]).reshape(ph, pw).astype(np.float32)
    t_drop = np.where(keep_zone, 99.0, t_drop)
    drop_glow = (rng.random(len(frag_pts)) < 0.3)[fidx[:, 0]].reshape(ph, pw).astype(np.float32)
    gTy, gTx = np.gradient(cv2.GaussianBlur(T, (0, 0), 2 * S))
    front_speed = 1.0 / (np.hypot(gTx, gTy) + 1e-4) / S
    domen = noise((ph, pw), rng, 55 * S, 2)
    cracks = np.clip(1 - np.abs(noise((ph, pw), rng, 22 * S, 3) - 0.5) / 0.012, 0, 1) * (noise((ph, pw), rng, 60 * S, 2) > 0.62)
    edge_d = cv2.distanceTransform((paper_a0 > 0.5).astype(np.uint8), cv2.DIST_L2, 3)
    b_lo, b_hi = cfg.get("bite_px", [10, 40])
    bite = (edge_d < (b_lo + (b_hi - b_lo) * noise((ph, pw), rng, 25 * S, 2)) * S) & ~keep_zone
    t_bite = float(cfg.get("bite_after", 3.0)) + float(cfg.get("bite_spread", 2.0)) * noise((ph, pw), rng, 20 * S, 2)
    flake_life = cfg.get("flakes")  # ash flakes that lift off and drift away
    rim_l = None
    if cfg.get("rim_light"):
        er = cv2.erode((paper_a0 > 0.5).astype(np.uint8), np.ones((3, 3), np.uint8), iterations=max(1, int(float(cfg["rim_light"].get("width", 3)) * S)))
        band = np.clip((paper_a0 > 0.5).astype(np.float32) - er, 0, 1)
        rim_l = (cv2.GaussianBlur(band, (0, 0), 1.0 * S) * smooth(1 - yy / ph, 0.55, 0.85) * (0.6 + 0.8 * noise((ph, pw), rng, 15 * S, 2))).astype(np.float32)
    rim_w = ((0.015 + 0.06 * noise((ph, pw), rng, 30 * S, 2)) * float(cfg.get("rim_w_scale", 1.0))).astype(np.float32)  # the glowing edge varies in width
    rim_b = (0.30 + 1.15 * noise((ph, pw), rng, 18 * S, 3)).astype(np.float32)   # ... and in brightness
    speck = (smooth(noise((ph, pw), rng, 3 * S, 2), 0.72, 0.9) * smooth(noise((ph, pw), rng, 28 * S, 2), 0.55, 0.8)).astype(np.float32)  # clustered embers in fresh char
    wo = cfg.get("water_over")  # real water from the plate itself washing over the sheet (a luma matte)
    wet = np.zeros((ph, pw), np.float32)
    near_w = np.zeros((ph, pw), np.float32)

    # ---------- placement: the sheet's corners in the output frame (1080-scale units) ----------
    quad = np.float32(cfg["quad"]) * S  # TL, TR, BR, BL of the sheet as seen
    M = cv2.getPerspectiveTransform(np.float32([[0, 0], [pw, 0], [pw, ph], [0, ph]]), quad)
    warp0 = lambda a: cv2.warpPerspective(a, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=0)  # noqa: E731
    bend = cfg.get("bend")  # {"amp": px, "waves": n, "phase": rad, "shade": k}: the strip lies over a curved leaf
    bend_shade = None
    if bend:
        sgy, sgx = np.mgrid[0:H, 0:W].astype(np.float32)
        Mi = np.linalg.inv(M)
        den = Mi[2, 0] * sgx + Mi[2, 1] * sgy + Mi[2, 2]
        pu = np.clip((Mi[0, 0] * sgx + Mi[0, 1] * sgy + Mi[0, 2]) / den / pw, -0.2, 1.2)
        ph_ = 2 * np.pi * float(bend.get("waves", 1.0)) * pu + float(bend.get("phase", 0.0))
        dyb = (float(bend["amp"]) * S * np.sin(ph_)).astype(np.float32)
        bmx, bmy = sgx, (sgy - dyb).astype(np.float32)
        bend_shade = (1 + float(bend.get("shade", 0.2)) * np.cos(ph_)).astype(np.float32)[..., None]
        warp = lambda a: cv2.remap(warp0(a), bmx, bmy, cv2.INTER_LINEAR, borderValue=0)  # noqa: E731
        del sgy, sgx, den, pu, ph_
    else:
        warp = warp0
    cx, cy = quad.mean(axis=0)
    lift_dir = np.float32(cfg.get("lift_dir", [0, -1]))  # screen direction a raised point moves
    lift_k = float(cfg.get("lift_k", 0.30))

    # ---------- plate ----------
    pc = cfg["plate"]
    plate = Plate(pc, W, H, FPS, n_out)
    p_gain = float(pc.get("gain", 1.0))
    p_tint = np.array(pc.get("tint", [1, 1, 1]), np.float32)
    p_sat = float(pc.get("sat", 1.0))
    fire_on_plate = float(pc.get("fire_relight", 1.0))
    patch = cfg.get("stone_patch")  # a dry stone patch under the sheet built from the plate's own texture
    patch_mask = None
    gy, gx = np.mgrid[0:H, 0:W].astype(np.float32)
    if patch:
        pr = np.random.default_rng(patch.get("seed", 3))
        rx, ry = patch["radius"][0] * S, patch["radius"][1] * S
        ang = np.arctan2(gy - cy, gx - cx)
        rad = np.hypot((gx - cx) / rx, (gy - cy) / ry)
        wob = 1 + 0.12 * (cv2.resize(pr.random((8, 8)).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC) - 0.5) * 2
        patch_mask = np.clip((1.0 * wob - rad) / 0.04, 0, 1).astype(np.float32)
        patch_rim = np.exp(-((rad - wob) / 0.035) ** 2).astype(np.float32)
    amb = cfg.get("ambient", {"rgb": [1, 1, 1], "level": 0.3})
    amb_rgb = np.array(amb["rgb"], np.float32) * float(amb["level"])
    key = cfg.get("key")  # a directional key (low sun): brightens the sheet's lit side
    under = cfg.get("underlight")  # light from beneath (coals) transmitted through the sheet

    # ---------- flame, smoke, spark plates ----------
    fscale = float(cfg.get("flame_scale", 1.0))
    plates_f = []
    for f in cfg.get("flames", []):
        f = f if isinstance(f, dict) else {"src": f}
        plates_f.append(load_frames(f["src"], tuple(f.get("crop", [0.0, 1.0])), float(f.get("scale", 0.6)), int(cfg.get("flame_max_frames", min(300, n_out + 210)))))
    max_em = int(cfg.get("max_flames", 10))
    em_pos = [None] * max_em
    em_level = np.zeros(max_em, np.float32)
    # every flame is its own piece of real fire: its own plate, its own window across that plate, its
    # own start frame anywhere in the clip, mirror, scale and lean (no two flames share a silhouette)
    frng = np.random.default_rng(int(cfg.get("flame_seed", 17)))
    em_plate = frng.integers(0, max(1, len(plates_f)), max_em)
    em_off = frng.integers(0, 10_000, max_em)
    em_scale = frng.uniform(*cfg.get("flame_scale_range", [0.6, 1.4]), max_em)
    em_lean = frng.uniform(-15, 15, max_em)
    em_flip = frng.random(max_em) < 0.5
    win_w = float(cfg.get("flame_win_w", 0.4))  # fraction of the flame plate's width one flame takes
    em_win = frng.uniform(0.0, 1.0 - win_w, max_em)

    def respawn(e: int) -> None:  # a flame that died comes back as a different flame
        em_plate[e] = frng.integers(0, max(1, len(plates_f)))
        em_off[e] = frng.integers(0, 10_000)
        em_scale[e] = frng.uniform(*cfg.get("flame_scale_range", [0.6, 1.4]))
        em_lean[e] = frng.uniform(-15, 15)
        em_flip[e] = frng.random() < 0.5
        em_win[e] = frng.uniform(0.0, 1.0 - win_w)
    wind0 = float(cfg.get("wind_deg", 20))
    wind_drift = noise((1, n_out + 10), rng, 40, 2)[0]
    spacing = float(cfg.get("flame_spacing", 55)) * S
    sheet_fire = cfg.get("sheet_fire")  # one big real flame plate over the whole sheet (a catch)
    sf_frames = (load_frames(sheet_fire["src"], tuple(sheet_fire.get("crop", [0.0, 1.0])), 1.0, n_out + 2, skip=int(sheet_fire.get("in_frame", 0)))
                 if sheet_fire else [])
    smokes = cfg.get("smokes") or ([cfg["smoke"]] if cfg.get("smoke") else [])
    sm_caps = []
    for smoke in smokes:
        c_ = cv2.VideoCapture(smoke["src"])
        c_.set(cv2.CAP_PROP_POS_MSEC, smoke.get("in", 0) * 1000)
        sm_caps.append((smoke, c_))
    sparks = cfg.get("sparks")
    sp_cap = None
    if sparks:
        sp_cap = cv2.VideoCapture(sparks["src"])
        sp_cap.set(cv2.CAP_PROP_POS_MSEC, sparks.get("in", 0) * 1000)

    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                             "-c:v", "libx264", "-preset", "medium", "-crf", "13", "-pix_fmt", "yuv420p",
                             "-movflags", "+frag_keyframe+empty_moov", "-g", "24",  # a killed render still leaves a playable file
                             "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", cfg["out"]], stdin=subprocess.PIPE)
    nlf = noise((1, n_out + 10), rng, 3, 3)[0]
    q = 4
    gyq, gxq = np.mgrid[0:H // q, 0:W // q].astype(np.float32) * q
    flakes = []  # [x, y, vx, vy, life, size]
    cam = noise((3, n_out + 10), rng, 60, 3)
    dof = cfg.get("dof")  # {"ends_px": blur at the sheet's ends, "all_px": overall softness}
    if dof:
        u_out = cv2.warpPerspective(np.repeat((np.abs(np.arange(pw, dtype=np.float32) / (pw - 1) - float(dof.get("focus_u", 0.5))) * 2)[None, :], ph, 0), M, (W, H))
    meta = {"word_boxes": boxes, "fps": FPS,
            # film time the fire first touches each word's ink (reading order): QC checks it is after the word is spoken
            "word_first_burn_s": [round(float(T[:, xa:xb][ink[:, xa:xb] > 0.3].min()), 3) if (ink[:, xa:xb] > 0.3).any() else None for xa, xb in boxes]}
    if holes:
        meta.update(meta_holes)
    for fo in range(n_out):
        t = t0 + fo / FPS
        raw = plate.next()
        m_scr = None
        if wo and t >= float(wo.get("t0", 0)):
            lum_ = raw @ np.array([0.2126, 0.7152, 0.0722], np.float32)
            m_scr = smooth(cv2.GaussianBlur(lum_, (0, 0), float(wo.get("blur", 1.2)) * S), float(wo.get("lo", 0.45)), float(wo.get("hi", 0.75))).astype(np.float32)
            m_scr *= float(wo.get("gain", 1.0))
            mp_ = cv2.warpPerspective(m_scr, np.linalg.inv(M), (pw, ph))
            wet = np.maximum(wet, cv2.GaussianBlur(mp_, (0, 0), 3 * S))
            if wo.get("near_px"):  # spray ahead of the water: the ember starts to die before the foam touches it
                sm_ = cv2.resize(mp_, (pw // 4, ph // 4), interpolation=cv2.INTER_AREA)
                sm_ = cv2.GaussianBlur(sm_, (0, 0), float(wo["near_px"]) * S / 4)
                near_w = np.maximum(near_w, np.clip(cv2.resize(sm_, (pw, ph)) * float(wo.get("near_gain", 3.0)), 0, 1))
        st = t - T
        scorch = smooth(st, -0.3, 0.0)
        if scorch_pre is not None:  # brown blooms where the coals beneath are hottest
            a0, a1 = scorch_pre
            uh_map = under_heat_paper if fo > 0 else None
            if uh_map is not None:
                grow = smooth(np.float32(t), a0, a1)
                if "uh_eff" not in locals():
                    eb = float(catch["underheat"].get("edge_bias", 0.45))
                    gr_ = float(catch["underheat"].get("grain_px", 9))
                    gk_ = float(catch["underheat"].get("grain_k", 0.9))
                    uh_eff = np.clip((1 - eb) * uh_map + eb * (yy / ph) ** 1.6, 0, 1) * (1 - gk_ / 2 + gk_ * noise((ph, pw), np.random.default_rng(57), gr_ * S, 3))
                    uh_eff = (uh_eff / (uh_eff.max() + 1e-6)).astype(np.float32)
                scorch = np.maximum(scorch, float(catch["underheat"].get("amount", 0.8)) * smooth(uh_eff, 0.85 - 0.75 * grow, 1.2 - 0.6 * grow))
        rim = np.exp(-((st - rim_w) / rim_w) ** 2) * (st > -0.02) * (1 - wet)
        flick = cv2.resize(noise((ph // 6, pw // 6), np.random.default_rng(1000 + int(t * 12)), 6, 2), (pw, ph))
        rim_vis = rim * rim_b * smooth(flick, 0.25, 0.75) * float(cfg.get("rim_gain", 1.0))
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
        char_alb = float(cfg.get("char_level", 0.030)) * (0.75 + 0.5 * crinkle[..., None]) * np.array([1.0, 0.9, 0.84], np.float32)
        # the script survives on the ash as gloss on matte
        char_alb = char_alb * (1 - ink[..., None]) + ink[..., None] * float(cfg.get("ash_ink_gloss", 0.012)) * np.array([1, 1, 1.05], np.float32)
        ash_alb = 0.22 * np.array([1.0, 0.95, 0.9], np.float32)
        char_alb = char_alb * (1 - (cracks * old)[..., None]) + ash_alb * (cracks * old)[..., None]
        if ew is not None and cfg.get("ember_bed"):
            eb_ = cfg["ember_bed"]
            ash_k = (keep_zone * smooth(st, float(eb_.get("t0", 0.6)), float(eb_.get("t1", 1.8)))).astype(np.float32)
            ash_k = cv2.GaussianBlur(ash_k, (0, 0), 3 * S) * (0.6 + 0.8 * crinkle)
            char_alb = char_alb * (1 - ash_k[..., None]) + float(eb_.get("ash", 0.07)) * np.array([1.0, 0.96, 0.92], np.float32) * ash_k[..., None] * (1 - ink[..., None])
        a_lin = a_lin * (1 - char[..., None]) + char_alb * char[..., None]
        if holes:
            a_lin = a_lin * (1 - 0.75 * hole_rim[..., None] * np.array([0.55, 0.75, 0.9], np.float32))  # scorched rims

        z = 35.0 * S * smooth(st, 0.05, 0.8) * (0.5 + domen) * (1 - 0.7 * keep_zone) + 4.0 * S * smooth(st, -0.4, 0.0) + curl
        z = z * float(cfg.get("curl_gain", 1.0))
        lift_px = (z * lift_k).astype(np.float32)
        mapx = (xx - lift_px * char * lift_dir[0]).astype(np.float32)
        mapy = (yy - lift_px * char * lift_dir[1]).astype(np.float32)
        upl = lambda a: cv2.remap(a, mapx, mapy, cv2.INTER_LINEAR, borderValue=0)  # noqa: E731
        char_l = upl(char.astype(np.float32))
        base = (1 - char)
        a_lin = a_lin * base[..., None] + upl(a_lin) * char_l[..., None] * (1 - base[..., None])
        alpha = np.clip(alpha * base + upl(alpha.astype(np.float32)) * char_l, 0, 1)
        nzy, nzx = np.gradient(cv2.GaussianBlur(z, (0, 0), 4 * S))

        em = rim_vis[..., None] * lin(np.array([230, 60, 30], np.float32) / 255) * 6.0
        em += ((1 - frag_edge) * dropping * drop_glow)[..., None] * lin(np.array([220, 70, 25], np.float32) / 255) * float(cfg.get("frag_glow", 0.0))
        afterglow = smooth(st, 0.0, 0.06) * (1 - smooth(st, 0.25, float(cfg.get("afterglow_s", 1.4)))) * (1 - wet)
        em += (speck * afterglow * smooth(flick, 0.2, 0.8))[..., None] * np.array([0.9, 0.18, 0.03], np.float32) * float(cfg.get("afterglow", 0.8))
        spk = (rng.random((ph, pw)) > 1 - float(cfg.get("sparkle_rate", 0.0006)) * 2.5 * speck / (S * S)) & (st > 0.08) & (st < 0.35)
        em += cv2.GaussianBlur(spk.astype(np.float32), (0, 0), 0.8 * S)[..., None] * np.array([4.0, 1.4, 0.3], np.float32)
        if holes:  # a glowing ring round each wound while the fire is near it
            near = smooth(st, -0.45, -0.05) * (1 - smooth(st, 0.1, 0.4))
            em += (hole_rim ** 2 * near * rim_b * speck * (1 - wet))[..., None] * np.array([1.1, 0.24, 0.04], np.float32) * float(holes.get("ring_glow", 0.6))
        if ew is not None:
            heat = float(np.interp(t, heat_k[:, 0], heat_k[:, 1]))
            for g in gusts:  # wind gusts make the ember breathe
                heat *= 1 + 0.22 * math.exp(-((t - g) / 0.18) ** 2)
            cool_map = np.ones((ph, pw), np.float32)
            if quench:  # after the seawater: thin strokes and dots go dark first
                qa = float(quench["t"])
                qd = float(quench.get("dur", 1.6))
                ql = np.clip((t - qa) / qd, 0, 1)
                cool_map = np.clip(1 - ql * (1.0 + 1.6 * thin), 0, 1) ** 1.5
            if wo:  # the sea puts it out: where the water has been, the strokes die (thin ones at once)
                cool_map = cool_map * np.clip(1 - wet * (1.3 + 1.5 * thin), 0, 1) ** 1.5
                cool_map = cool_map * np.clip(1 - near_w * (0.55 + 0.4 * thin), 0, 1)
            if heat > 0.001:
                charred_here = smooth(st, -0.08, 0.15)
                core = cv2.GaussianBlur(ew_mask, (0, 0), 0.6 * S)
                if "ew_tex" not in locals():
                    ew_tex = (0.45 + 0.75 * noise((ph, pw), np.random.default_rng(91), 4 * S, 3)) * (1 - 0.6 * np.clip(1 - np.abs(noise((ph, pw), np.random.default_rng(92), 9 * S, 2) - 0.5) / 0.04, 0, 1))
                    ew_tex = ew_tex.astype(np.float32)
                core = np.clip(core * np.maximum(ew_tex, 0.75 * thin) * (1 + 0.7 * thin), 0, 1.25)
                halo = cv2.GaussianBlur(ew_mask, (0, 0), 5 * S)
                fl_n = 0.88 + 0.12 * smooth(flick, 0.2, 0.8)
                gain = float(ew.get("gain", 0.8))
                hmap = heat * core * fl_n * cool_map
                em += (v6.blackbody(hmap) * gain + v6.blackbody(heat * 0.45 * halo * cool_map) * 0.25 * gain) * charred_here[..., None]

        # ---------- flame emitters on the burning edge ----------
        active = (st > 0.0) & (st < float(cfg.get("flame_window", 0.3))) & (paper_a0 > 0) & (~gone) & (wet < 0.3)
        if ew is not None and cfg.get("no_flames_on_word", True):
            active &= ~keep_zone
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
                    respawn(e)
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

        fl = np.zeros((H, W, 3), np.float32)
        lights = []
        wind = wind0 + 10 * (wind_drift[fo] - 0.5)
        for e in range(max_em):
            if em_pos[e] is None or em_level[e] < 0.03 or not plates_f:
                continue
            p = cv2.perspectiveTransform(np.array([[em_pos[e]]], np.float32), M)[0, 0]
            fr = plates_f[em_plate[e]]
            src = fr[(em_off[e] + fo) % len(fr)]
            x0w = int(em_win[e] * src.shape[1])
            src = src[:, x0w:x0w + max(8, int(win_w * src.shape[1]))]
            if em_flip[e]:
                src = src[:, ::-1]
            im = lin(src.astype(np.float32) / 255.0)
            im = np.clip((im - 0.003) / 0.98, 0, None)
            hh = int(np.clip(130 * S * fscale * em_scale[e] * (0.5 + 0.5 * em_level[e]), 30 * S, 320 * S * fscale))
            ww = int(hh * im.shape[1] / im.shape[0] * float(cfg.get("flame_aspect", 0.75)))
            spr = cv2.resize(im, (max(8, ww), max(8, hh)), interpolation=cv2.INTER_AREA)
            fh_, fw_ = spr.shape[:2]
            ey = np.linspace(0, 1, fh_)
            exx = np.minimum(np.linspace(0, 1, fw_), np.linspace(1, 0, fw_))
            # alpha from the flame's own light, feathered on every side (an elliptical window), so no
            # edge of the source clip can show, rotated or not
            ell = np.clip(1 - (((np.linspace(-1, 1, fw_)[None, :]) / 1.0) ** 2 + ((np.linspace(-1, 1, fh_)[:, None] + 0.15) / 1.15) ** 2), 0, 1)
            win = smooth(ell, 0.0, 0.45) * smooth(1 - ey, 0.0, 0.28)[:, None] * smooth(ey, 0.0, 0.2)[:, None] * smooth(exx, 0, 0.3)[None, :]
            spr *= smooth(spr.max(axis=2, keepdims=True), 0.02, 0.15) * win[..., None]
            pad = int(max(fw_, fh_) * 0.9)
            canvas = np.zeros((fh_ + 2 * pad, fw_ + 2 * pad, 3), np.float32)
            canvas[pad:pad + fh_, pad:pad + fw_] = spr
            R = cv2.getRotationMatrix2D((pad + fw_ / 2, pad + fh_), wind + em_lean[e], 1.0)
            canvas = cv2.warpAffine(canvas, R, (canvas.shape[1], canvas.shape[0])) * em_level[e]
            x0, y0 = int(p[0] - pad - fw_ / 2), int(p[1] - pad - fh_ * 0.94)
            xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + canvas.shape[1]), min(H, y0 + canvas.shape[0])
            if xb > xa and yb > ya:
                fl[ya:yb, xa:xb] += canvas[ya - y0:yb - y0, xa - x0:xb - x0]
            lights.append((p, float(canvas.sum()) / (1500.0 * S * S)))

        if sheet_fire and t >= sheet_fire["t"]:  # the whole letter in real slow flames
            k = int((t - sheet_fire["t"]) * FPS)
            if k < len(sf_frames):
                im = lin(sf_frames[k].astype(np.float32) / 255.0)
                bw, bh = [int(v * S) for v in sheet_fire["box"][2:]]
                bx, by = [int(v * S) for v in sheet_fire["box"][:2]]
                im = cv2.resize(im, (bw, bh), interpolation=cv2.INTER_AREA)
                fy_ = np.linspace(0, 1, bh)[:, None]
                fx_ = np.linspace(0, 1, bw)[None, :]
                soft = smooth(1 - fy_, 0.0, float(sheet_fire.get("fade_bottom", 0.22))) * smooth(np.minimum(fx_, 1 - fx_), 0.0, float(sheet_fire.get("fade_sides", 0.14))) * smooth(fy_, 0.0, 0.08)
                lum_all = im.max(axis=2)
                lum_all = lum_all / (np.percentile(lum_all, 99) + 1e-6)
                env = float(np.interp(t, *zip(*sheet_fire["env"])))
                xa, ya, xb, yb = max(0, bx), max(0, by), min(W, bx + bw), min(H, by + bh)
                patch_f = im[ya - by:yb - by, xa - bx:xb - bx]
                f_ = soft[ya - by:yb - by, xa - bx:xb - bx] * np.ones_like(lum_all[ya - by:yb - by, xa - bx:xb - bx])
                if sheet_fire.get("follow_burn", False):
                    # the flames rise from where the letter is actually burning: a mask of the burning
                    # paper, smeared upward (flames climb) and feathered, so fire never floats in a box
                    burn_now = (smooth(st, -0.05, 0.12) * (1 - smooth(st, 0.9, 1.8)) * paper_a0).astype(np.float32)
                    bq_ = cv2.resize(warp(burn_now), (W // 4, H // 4), interpolation=cv2.INTER_AREA)
                    up_ = bq_.copy()
                    rise = int(float(sheet_fire.get("rise_px", 420)) * S / 4)
                    cur_ = bq_.copy()
                    tap = max(1, int(sheet_fire.get("taper_every", 3)))
                    for k_ in range(1, rise):  # flames climb and draw in as they rise (no vertical walls)
                        if k_ % tap == 0:
                            cur_ = cv2.erode(cur_, np.ones((1, 3), np.uint8))
                        up_[:-k_] = np.maximum(up_[:-k_], cur_[k_:] * (1 - k_ / rise) ** 1.3)
                    up_ = cv2.dilate(up_, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (max(3, int(60 * S / 4)) | 1, max(3, int(20 * S / 4)) | 1)))
                    # turbulence: a horizontal sway field that scrolls upward with the hot air, so the
                    # fire's sides waver instead of standing as straight walls
                    if "sway_f" not in locals():
                        hq_, wq_ = up_.shape
                        sway_f = ((noise((hq_ * 3 // 8, wq_ // 8), np.random.default_rng(611), 3, 3) - 0.5) * 2).astype(np.float32)
                        sway_f = cv2.resize(sway_f, (wq_, hq_ * 3))
                        sgyq, sgxq = np.mgrid[0:hq_, 0:wq_].astype(np.float32)
                    off_ = int((fo * 14 * S / 4)) % (sway_f.shape[0] - up_.shape[0])
                    sw_ = sway_f[sway_f.shape[0] - up_.shape[0] - off_: sway_f.shape[0] - off_]
                    up_ = cv2.remap(up_, sgxq + sw_ * float(sheet_fire.get("sway_px", 55)) * S / 4, sgyq, cv2.INTER_LINEAR, borderValue=0)
                    up_ = cv2.GaussianBlur(up_, (0, 0), float(sheet_fire.get("feather_px", 40)) * S / 4)
                    # an irregular, moving boundary: the flame's own bright tongues reach past the
                    # region's edge and its dim veils stop short, so the edge is the fire's, not a mask's
                    wob = cv2.resize(noise((H // 32, W // 32), np.random.default_rng(500 + fo // 2), 3, 2), (W, H))
                    reg = np.clip(cv2.resize(up_, (W, H)) * 1.6 * (0.65 + 0.7 * wob), 0, 1)[ya:yb, xa:xb]
                    f_ = f_ * reg
                # toward any edge of the fire's region only its brightest tongues survive, so the boundary
                # is drawn by the flames' own shapes, never by a straight fade
                lumc = lum_all[ya - by:yb - by, xa - bx:xb - bx]
                patch_f = patch_f * (smooth(lumc - 0.9 * (1 - f_), 0.0, 0.25) * np.power(np.clip(f_, 0, 1), 0.3))[..., None]
                fl[ya:yb, xa:xb] += patch_f * env * float(sheet_fire.get("gain", 1.0))
                lights.append((np.float32([cx, cy - 80 * S]), env * float(sheet_fire.get("light", 30.0))))

        # ---------- fire light (1/q resolution) ----------
        flick_state = 0.8 + 0.4 * nlf[fo]
        Eq = np.zeros((H // q, W // q), np.float32)
        hgt = float(cfg.get("light_height", 80.0)) * S
        for (p, I) in lights:
            r2 = (gxq - p[0]) ** 2 + (gyq - p[1]) ** 2
            Eq += I * flick_state * hgt / (hgt ** 2 + r2) ** 1.5 * 1.3e4 * S
        p_em = warp(em)
        emq = cv2.resize(p_em.sum(axis=2), (W // q, H // q), interpolation=cv2.INTER_AREA)
        Eq += float(cfg.get("glow_light", 0.25)) * cv2.GaussianBlur(emq, (0, 0), 5 * S)
        E = cv2.resize(Eq, (W, H), interpolation=cv2.INTER_LINEAR)[..., None]
        fire = E * np.array([1.0, 0.32, 0.10], np.float32) * float(cfg.get("fire_light_gain", 1.0))

        # ---------- the world: plate, relit by the fire ----------
        bg_alb = lin(raw)
        if p_sat != 1.0:
            l_ = bg_alb @ np.array([0.2126, 0.7152, 0.0722], np.float32)
            bg_alb = l_[..., None] + (bg_alb - l_[..., None]) * p_sat
        if fo == 0:
            if patch:
                patch_tex = bg_alb.copy()  # the dry stone: the plate's own texture, frozen (no caustics)
            if under:
                # heat map of the coals under the sheet: the plate's red luminance, in paper space
                red = cv2.GaussianBlur(bg_alb[..., 0] - 0.5 * bg_alb[..., 2], (0, 0), 25 * S)
                Minv = np.linalg.inv(M)
                uh = cv2.warpPerspective(np.clip(red, 0, None), Minv, (pw, ph))
                under_heat_paper = (uh / (uh.max() + 1e-6)).astype(np.float32)
                em_ = float(under.get("edge_mix", 0.0))
                if em_ > 0:
                    eg = np.exp(-edge_d / (float(under.get("edge_px", 45)) * S)) * (0.5 + 0.5 * (yy / ph) ** 1.5)
                    under_light_map = ((1 - em_) * under_heat_paper * (0.7 + 0.3 * (yy / ph)) + em_ * eg).astype(np.float32)
                else:
                    under_light_map = under_heat_paper
        ground = bg_alb * p_gain * p_tint
        if patch:
            dry = patch_tex * float(patch.get("dry_gain", 0.7)) * np.array(patch.get("dry_tint", [1, 0.96, 0.9]), np.float32)
            ground = ground * (1 - patch_mask[..., None]) + dry * p_gain * p_tint * patch_mask[..., None]
            ground += (patch_rim * float(patch.get("rim_wet", 0.4)))[..., None] * fire * 0.4
        ground = ground + bg_alb * fire * fire_on_plate * (patch_mask[..., None] * 1.0 + 0.6 if patch is not None else 1.0)
        # contact shadow, falling away from the main light
        p_a = warp(alpha.astype(np.float32))
        sd = np.float32(cfg.get("shadow_dir", [0.0, 1.0]))
        off = sd * float(cfg.get("shadow_px", 8)) * S
        shp = cv2.warpAffine(p_a, np.float32([[1, 0, off[0]], [0, 1, off[1]]]), (W, H))
        shadow = np.clip(cv2.GaussianBlur(shp, (0, 0), float(cfg.get("shadow_soft", 7)) * S) * 0.6 + cv2.GaussianBlur(p_a, (0, 0), 2 * S) * float(cfg.get("shadow_core", 0.35)), 0, 0.8)
        if holes:
            if "hole_open" not in locals():
                hole_open = warp(cv2.GaussianBlur(hole_mask, (0, 0), 2 * S).astype(np.float32))
            shadow = shadow * (1 - 0.7 * hole_open)
        shadow = shadow[..., None]
        ground = ground * (1 - shadow * float(cfg.get("shadow_gain", 1.0)))

        # ---------- the sheet ----------
        p_alb = warp(a_lin)
        p_nx, p_ny, p_char = warp(nzx), warp(nzy), warp(char.astype(np.float32))
        p_scorch = warp(smooth(st, -0.25, 0.0).astype(np.float32)) if rim_l is not None else 0.0
        lp = np.mean([p for p, _ in lights], axis=0) if lights else np.float32([cx, cy - 60 * S])
        lx, ly = (lp[0] - gx), (lp[1] - gy)
        ln = np.hypot(lx, ly) + 1e-3
        lam = np.clip(1 + 0.25 * (p_nx * lx + p_ny * ly) / ln * -1, 0.4, 1.6)[..., None]
        spec = (0.2 * p_char * np.clip(-(p_nx * lx + p_ny * ly) / ln, 0, 1) ** 2)[..., None]
        illum = amb_rgb + fire * lam
        if key:
            kd = np.float32(key["dir"])
            kshade = np.clip(1 + key.get("relief", 0.6) * (p_nx * kd[0] + p_ny * kd[1]) / (S * 2), 0.3, 1.8)[..., None]
            k_env = float(np.interp(t, *zip(*key["env"]))) if "env" in key else 1.0
            illum = illum + np.array(key["rgb"], np.float32) * float(key["level"]) * k_env * kshade
        if bend_shade is not None:
            illum = illum * bend_shade
        paper = p_alb * illum * warp(sheet_light)[..., None] + spec * fire + p_em
        if rim_l is not None:  # the low sun behind catches the torn top edge
            paper += (warp(rim_l) * (1 - p_char) * (1 - p_scorch))[..., None] * np.array(cfg["rim_light"].get("rgb", [1.0, 0.75, 0.45]), np.float32) * float(cfg["rim_light"]["level"])
        if under:  # light from the coals shows through the thin sheet (strongest where unburnt)
            uh_o = warp(under_light_map)[..., None]
            u_env = float(np.interp(t, *zip(*under["env"]))) if "env" in under else 1.0
            paper += uh_o * float(under["gain"]) * u_env * np.array(under.get("rgb", [1.0, 0.35, 0.10]), np.float32) * (1 - p_char[..., None]) * p_alb.mean(axis=2, keepdims=True) * 3
        if dof:  # the sheet takes the plate's focus: blur rises toward its ends
            ends = float(dof.get("ends_px", 6)) * S
            allb = float(dof.get("all_px", 0.6)) * S
            pa3 = p_a[..., None]
            prem = paper * pa3
            b1 = cv2.GaussianBlur(prem, (0, 0), allb + 0.01)
            b2 = cv2.GaussianBlur(prem, (0, 0), ends)
            a1 = cv2.GaussianBlur(p_a, (0, 0), allb + 0.01)[..., None]
            a2 = cv2.GaussianBlur(p_a, (0, 0), ends)[..., None]
            wv = np.clip(cv2.GaussianBlur(u_out, (0, 0), 4 * S), 0, 1)[..., None] ** 1.5
            prem = b1 * (1 - wv) + b2 * wv
            pa = a1 * (1 - wv) + a2 * wv
            frame = ground * (1 - pa) + prem
        else:
            frame = ground * (1 - p_a[..., None]) + paper * p_a[..., None]

        # flames (light), smoke and sparks (real plates, screen)
        fl = fl * float(cfg.get("flame_gain", 4.0))
        fl = np.stack([fl[..., 0], fl[..., 1] * 0.95, fl[..., 2] * 0.85], axis=2)
        frame = frame + fl
        frontp = None
        if lights:
            frontp = np.mean([p for p, _ in lights[:max_em]], axis=0)
        for smoke, sm_cap in sm_caps:
            ok, smf = sm_cap.read()
            if ok:
                if smoke.get("flip"):
                    smf = smf[:, ::-1]
                smf = lin(cv2.resize(smf[..., ::-1], (W, H)).astype(np.float32) / 255.0)
                if smoke.get("black"):  # luma key: keep only what is brighter than the plate's own background
                    smf = np.clip(smf - float(smoke["black"]), 0, None) / (1 - float(smoke["black"]))
                    smf = smf.mean(axis=2, keepdims=True).repeat(3, axis=2)
                env = float(np.interp(t, *zip(*smoke["env"]))) if "env" in smoke else 1.0
                ctr = frontp if (frontp is not None and smoke.get("follow", True)) else np.float32([cx, cy])
                ox, oy = smoke.get("offset", [0, -300])
                mx = np.exp(-(((gx - ctr[0] - ox * S) / (smoke.get("rx", 700) * S)) ** 2 + ((gy - ctr[1] - oy * S) / (smoke.get("ry", 900) * S)) ** 2))[..., None]
                sm = smf * mx * env * float(smoke.get("gain", 0.6)) * np.array(smoke.get("tint", [0.9, 0.9, 0.95]), np.float32)
                sm = sm + 0.12 * sm * fire  # lit from below by the fire
                frame = 1 - (1 - np.clip(frame, 0, 1)) * (1 - np.clip(sm, 0, 1)) if smoke.get("mode", "screen") == "screen" else frame + sm
        if sp_cap is not None:
            ok, spf = sp_cap.read()
            if ok:
                spf = lin(cv2.resize(spf[..., ::-1], (W, H)).astype(np.float32) / 255.0)
                env = float(np.interp(t, *zip(*sparks["env"]))) if "env" in sparks else 1.0
                ctr = frontp if frontp is not None else np.float32([cx, cy])
                mx = np.exp(-(((gx - ctr[0]) / (sparks.get("rx", 600) * S)) ** 2 + ((gy - ctr[1] + 500 * S) / (sparks.get("ry", 1100) * S)) ** 2))[..., None]
                frame = frame + spf * mx * env * float(sparks.get("gain", 0.8))
        if flake_life:  # ash flakes lifting off the char and drifting downwind
            if fo % 2 == 0 and n_act > 0:
                gone_now = (st > t_drop) & (st < t_drop + 2.0 / FPS) & (paper_a0 > 0)
                ys2, xs2 = np.nonzero(gone_now[::7, ::7])
                for j in rng.permutation(len(xs2))[: int(flake_life.get("per_frame", 6))]:
                    pp = cv2.perspectiveTransform(np.array([[[xs2[j] * 7, ys2[j] * 7]]], np.float32), M)[0, 0]
                    flakes.append([pp[0], pp[1], rng.normal(flake_life.get("vx", 3.0), 1.5) * S, rng.normal(flake_life.get("vy", -4.0), 1.5) * S, 1.0,
                                   rng.uniform(2, 7) * S, float(rng.random() < float(flake_life.get("glow_frac", 0.3))), rng.uniform(0, 180)])
            fk = np.zeros((H, W), np.float32)
            fg = np.zeros((H, W), np.float32)
            for f_ in flakes:
                f_[0] += f_[2]; f_[1] += f_[3]; f_[3] -= 0.05 * S; f_[4] -= 1.0 / (FPS * flake_life.get("life_s", 1.6)); f_[7] += 9
                if f_[4] > 0 and 0 <= f_[0] < W and 0 <= f_[1] < H:
                    ax = (max(1, int(f_[5])), max(1, int(f_[5] * (0.25 + 0.5 * abs(math.sin(math.radians(f_[7])))))))  # tumbling
                    cv2.ellipse(fg if f_[6] else fk, (int(f_[0]), int(f_[1])), ax, f_[7], 0, 360, float(f_[4]), -1, cv2.LINE_AA)
            flakes = [f_ for f_ in flakes if f_[4] > 0]
            fkb = cv2.GaussianBlur(fk, (0, 0), 1.6 * S)[..., None]
            frame = frame * (1 - 0.55 * fkb) + fkb * 0.012 * np.array([1, 0.97, 0.95], np.float32)
            frame = frame + cv2.GaussianBlur(fg, (0, 0), 1.2 * S)[..., None] * np.array([1.4, 0.35, 0.06], np.float32) * (fg.max() > 0)
        if quench:  # seawater slides over the stone: a moving wet front with a bright edge, then steam
            qa = float(quench["t"])
            if t >= qa - 0.2:
                prog = np.clip((t - qa) / float(quench.get("slide", 0.6)), 0, 1)
                d_ = (gx * quench.get("dir", [1, 0])[0] + gy * quench.get("dir", [1, 0])[1]) / (W * abs(quench.get("dir", [1, 0])[0]) + H * abs(quench.get("dir", [1, 0])[1]))
                if "q_wave" not in locals():  # a ragged water edge, not a ruler line
                    q_wave = (cv2.resize(noise((H // 16, W // 16), np.random.default_rng(77), 5, 3), (W, H)) - 0.5) * 0.16
                d_ = d_ + q_wave + 0.02 * np.sin(gy / H * 2 * np.pi * 4 + t * 3)
                wf = np.clip((prog * 1.3 - d_) / 0.08, 0, 1)[..., None]
                edge_ = 0.6 * np.exp(-((prog * 1.3 - d_) / 0.03) ** 2)[..., None]
                region = (patch_mask[..., None] if patch_mask is not None else 1.0)
                frame = frame * (1 - 0.18 * wf * region) + edge_ * region * (0.05 + 0.3 * fire)
        if m_scr is not None:
            water = bg_alb * p_gain * p_tint * float(wo.get("water_gain", 1.0)) + bg_alb * fire * fire_on_plate * 0.5
            mm = m_scr[..., None]
            frame = frame * (1 - mm) + water * mm
            p_em = p_em * (1 - mm)
            fl = fl * (1 - mm)
        bq = cv2.resize(fl + p_em * p_a[..., None], (W // q, H // q), interpolation=cv2.INTER_AREA)
        frame += cv2.resize(cv2.GaussianBlur(bq, (0, 0), 6 * S / 2) * 0.25 + cv2.GaussianBlur(bq, (0, 0), 28 * S / 2) * 0.12, (W, H))

        frame = frame * float(cfg.get("exposure", 1.0))
        out = disp(frame)
        out = np.where(out > 0.80, 0.80 + (out - 0.80) / (1 + (out - 0.80) / 0.18), out)
        fade = cfg.get("fade_in")
        if fade and t < t0 + fade:
            out *= ((t - t0) / fade) ** 1.5
        dx = float(cfg.get("drift_px", 1.2)) * S * (cam[0, fo] - 0.5)
        dy = float(cfg.get("drift_px", 1.2)) * S * (cam[1, fo] - 0.5)
        A = np.float32([[1, 0, dx], [0, 1, dy]])
        out = cv2.warpAffine(out, A, (W, H), borderMode=cv2.BORDER_REFLECT)
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
