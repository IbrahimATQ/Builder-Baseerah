#!/usr/bin/env python3
"""The look of the coffee film, as one function on display RGB, baked into 3D LUTs for ffmpeg.

The footage is iPhone SDR (BT.709, already tone mapped), shot on a grey November afternoon. The look:
  * a little exposure where a shot is dark (in linear light, so it reads as more light, not as grey),
  * white balance nudged per shot, then one shared film curve: a gentle S, highlights that roll off
    instead of clipping (the windows), and blacks lifted a touch with a cool cast (a soft matte),
  * split toning: cool shadows, warm cream highlights, so the coffee and the brick glow against the
    grey daylight,
  * colour by hue: reds and oranges (roofs, brick, coffee) kept rich, greens and blues held back
    (a cold sky), and overall saturation a little below the phone's; where `led` is set, the scale's green
    LED loses its colour and half its light.
Spatial parts of the look (bloom around highlights, vignette, grain) are added by render.py.

Usage: python grade.py PLAN.json OUT_DIR       -> one .cube per shot (65 points), named <shot id>.cube
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

LOOK = {"ev": 0.0, "temp": 0.0, "tint": 0.0, "contrast": 1.0, "sat": 0.9, "black": 0.028, "shoulder": 0.82,
        "split": 1.0, "warm_hi": [1.0, 0.965, 0.9], "cool_lo": [0.9, 0.98, 1.04], "reds": 1.06, "greens": 0.62, "blues": 0.85}

LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)


def to_lin(x):
    return np.power(np.clip(x, 0, 1), 2.2)


def to_disp(x):
    return np.power(np.clip(x, 0, None), 1 / 2.2)


def hue_weights(rgb):
    """Soft memberships of each pixel in the red-orange, green and blue hue families (0..1), times chroma."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx, mn = np.max(rgb, axis=-1), np.min(rgb, axis=-1)
    c = mx - mn
    h = np.zeros_like(mx)
    nz = c > 1e-6
    rr = np.where(nz & (mx == r), ((g - b) / np.maximum(c, 1e-6)) % 6, 0)
    gg = np.where(nz & (mx == g) & (mx != r), (b - r) / np.maximum(c, 1e-6) + 2, 0)
    bb = np.where(nz & (mx == b) & (mx != r) & (mx != g), (r - g) / np.maximum(c, 1e-6) + 4, 0)
    h = (rr + gg + bb) * 60.0  # degrees
    chroma = np.clip(c / np.maximum(mx, 1e-3), 0, 1)

    def band(center, width):
        d = np.abs((h - center + 180) % 360 - 180)
        return np.clip(1 - d / width, 0, 1) * chroma

    return band(25, 45), band(130, 65), band(215, 45)  # the green band is wide: the scale's LED glows from green to cyan-green


def grade(rgb: np.ndarray, p: dict) -> np.ndarray:
    """rgb: float32 display values 0..1, any shape (..., 3). Returns display values 0..1."""
    p = {**LOOK, **p}
    lin = to_lin(rgb) * (2.0 ** p["ev"])
    t, m = p["temp"], p["tint"]
    lin = lin * np.array([1 + 0.10 * t, 1 - 0.05 * m, 1 - 0.12 * t], np.float32)
    x = to_disp(lin)
    # film curve: S around 0.42, then a shoulder that rolls highlights off toward 0.97
    k = p["contrast"]
    # above the pivot a straight contrast line; below it a toe computed from the value before the contrast, so the
    # shadows fall smoothly to black instead of a whole range of dark values being cut to exactly 0
    x0 = x
    x = np.where(x0 < 0.42, 0.42 * np.power(np.clip(x0 / 0.42, 0, None), k + 0.25 * (k - 1.0) + 0.06), 0.42 + (x0 - 0.42) * k)
    s = p["shoulder"]
    over = np.clip(x - s, 0, None)
    x = np.where(x > s, s + (0.975 - s) * (1 - np.exp(-over / (0.975 - s) * 1.15)), x)
    x = np.clip(x, 0, 1)
    # colour by hue, then overall saturation
    w_red, w_green, w_blue = hue_weights(x)
    lum = (x @ LUMA)[..., None]
    sat = p["sat"] * (1 + (p["reds"] - 1) * w_red + (p["greens"] - 1) * w_green + (p["blues"] - 1) * w_blue)[..., None]
    x = lum + (x - lum) * sat
    if p.get("led", 0) > 0:  # the scale's green LED: take its colour out and half its light
        x = x * (1 - 0.5 * p["led"] * np.clip(w_green * 1.6, 0, 1))[..., None]
    # split toning by luminance
    lum = (np.clip(x, 0, 1) @ LUMA)[..., None]
    hi = np.clip((lum - 0.45) / 0.45, 0, 1) ** 1.2
    lo = np.clip((0.45 - lum) / 0.45, 0, 1) ** 1.2
    sp = p["split"]
    x = x * (1 + sp * hi * (np.array(p["warm_hi"], np.float32) - 1)) * (1 + sp * lo * (np.array(p["cool_lo"], np.float32) - 1))
    # matte: lift the blacks a touch, with a cool cast
    blk = p["black"] * np.array([0.85, 1.0, 1.15], np.float32)
    x = blk + (1 - blk) * np.clip(x, 0, 1)
    return np.clip(x, 0, 1).astype(np.float32)


def write_cube(path: str, p: dict, n: int = 65) -> None:
    g = np.linspace(0, 1, n, dtype=np.float32)
    b, gg, r = np.meshgrid(g, g, g, indexing="ij")  # .cube order: red changes fastest
    rgb = np.stack([r, gg, b], axis=-1).reshape(-1, 3)
    out = grade(rgb, p)
    with open(path, "w") as f:
        f.write(f"TITLE \"coffee {os.path.basename(path)}\"\nLUT_3D_SIZE {n}\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n")
        np.savetxt(f, out, fmt="%.6f")


def main() -> None:
    plan_p, out = sys.argv[1:3]
    os.makedirs(out, exist_ok=True)
    plan = json.load(open(plan_p, encoding="utf-8"))
    look = plan.get("look", {})
    for s in plan["shots"]:
        write_cube(os.path.join(out, f"{s['id']}.cube"), {**look, **s.get("grade", {})})
    print(f"{len(plan['shots'])} LUTs -> {out}")


if __name__ == "__main__":
    main()
