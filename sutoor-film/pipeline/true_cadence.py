#!/usr/bin/env python3
"""Give a tracking shot back its true cadence, keeping every real frame.

Some stock clips were conformed to 24 fps by dropping frames of a faster original, so the camera travels
in uneven steps (1, 2, 1, 1, 2 ... units per frame). On a tracking shot over textured ground that is a
shudder, and a general re-interpolation (even_cadence.py) cannot cure it: every output frame would have to
be synthesized, and block motion search loses its way on sand, water and other repeating texture.

This tool does less, and so it holds:
  * it measures the real travel of the picture between consecutive frames by tracking patches of the frame
    (template matching; frame differences and coarse optical flow are fooled by ripples, see --check-only);
  * it finds the step pattern and its phase, i.e. how many units of true time each frame-to-frame step is;
  * it keeps EVERY original frame, and only where a step is two (or three) units long does it synthesize the
    missing in-between frame(s), from dense optical flow in both directions, taking each pixel from the
    neighbour in which it is really visible (a pixel is refused where the flow at the place it is fetched
    from disagrees with the flow that fetched it: that is the ghost at the edge of a foreground figure);
  * it writes all frames at the clip's own frame rate. The stretch therefore runs slower than the supplier's
    file by the mean step (1.4x longer for 1, 2, 1, 1, 2): slow motion made of real frames, evenly spaced.

Usage: python true_cadence.py SRC.mp4 START DUR OUT.mp4 [--pattern 1,2,1,1,2 | auto] [--crf 12] [--check-only]
                              [--report OUT.json] [--mark]   (--mark writes a small red square on synthesized frames, for inspection)
"""
from __future__ import annotations

import json
import subprocess
import sys

import cv2
import numpy as np

PATTERNS = [[1, 2, 1, 1, 2], [1, 2], [1, 1, 2], [1, 1, 1, 2], [1]]


def probe(src: str) -> tuple[int, int, float]:
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate",
                                   "-of", "json", src], capture_output=True, text=True, check=True).stdout)["streams"][0]
    n, d = j["r_frame_rate"].split("/")
    return int(j["width"]), int(j["height"]), float(n) / float(d)


def reader(src: str, start: float | None, dur: float | None, w: int, h: int, gray: bool = False):
    cmd = ["ffmpeg", "-v", "error"] + (["-ss", f"{start}", "-t", f"{dur}"] if start is not None else []) + \
          ["-i", src, "-vf", f"scale={w}:{h}" + (",format=gray" if gray else ""), "-f", "rawvideo", "-pix_fmt", "gray" if gray else "bgr24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=w * h * 3 * 2)
    n = w * h * (1 if gray else 3)
    while True:
        b = p.stdout.read(n)
        if len(b) < n:
            break
        yield np.frombuffer(b, np.uint8).reshape((h, w) if gray else (h, w, 3))
    p.wait()


def travel(a: np.ndarray, b: np.ndarray, grid=(7, 5), size: int = 128, reach: int = 110) -> tuple[float, float, int]:
    """Displacement of the moving part of the picture from a to b (grey, same size): median over tracked patches,
    each located to a fraction of a pixel."""
    H, W = a.shape
    a32, b32 = a.astype(np.float32), b.astype(np.float32)
    ds = []
    for gy in range(grid[1]):
        for gx in range(grid[0]):
            x = int((gx + 0.5) * W / grid[0] - size / 2)
            y = int((gy + 0.5) * H / grid[1] - size / 2)
            tpl = a32[y:y + size, x:x + size]
            if tpl.std() < 3.0:
                continue
            x0, y0, x1, y1 = max(0, x - reach), max(0, y - reach), min(W, x + size + reach), min(H, y + size + reach)
            m = cv2.matchTemplate(b32[y0:y1, x0:x1], tpl, cv2.TM_CCOEFF_NORMED)
            _, mx, _, loc = cv2.minMaxLoc(m)
            if mx <= 0.55:
                continue
            px, py = float(loc[0]), float(loc[1])
            if 0 < loc[0] < m.shape[1] - 1:  # parabola through the peak and its neighbours
                l, c, r = m[loc[1], loc[0] - 1], m[loc[1], loc[0]], m[loc[1], loc[0] + 1]
                px += 0.5 * (l - r) / (l - 2 * c + r) if (l - 2 * c + r) < -1e-6 else 0.0
            if 0 < loc[1] < m.shape[0] - 1:
                u, c, dn = m[loc[1] - 1, loc[0]], m[loc[1], loc[0]], m[loc[1] + 1, loc[0]]
                py += 0.5 * (u - dn) / (u - 2 * c + dn) if (u - 2 * c + dn) < -1e-6 else 0.0
            ds.append((px + x0 - x, py + y0 - y))
    if not ds:
        return 0.0, 0.0, 0
    d = np.array(ds, np.float32)
    mag = np.hypot(d[:, 0], d[:, 1])
    mov = d[mag >= np.median(mag)]  # the moving half: the ground under a tracking camera, not the figure it follows
    return float(np.median(mov[:, 0])), float(np.median(mov[:, 1])), len(ds)


def steps_of(src: str, start: float | None, dur: float | None) -> np.ndarray:
    w, h, _ = probe(src)
    W = min(w, 1920)
    H = int(round(W * h / w / 2)) * 2
    prev, out = None, []
    for f in reader(src, start, dur, W, H, gray=True):
        if prev is not None:
            dx, dy, _ = travel(prev, f)
            out.append(np.hypot(dx, dy) * w / W)
        prev = f.copy()
    return np.array(out, np.float32)


def unevenness(d: np.ndarray) -> dict:
    out = {"steps": int(len(d)), "mean_px": round(float(d.mean()), 1), "cv": round(float(d.std() / max(d.mean(), 1e-6)), 3)}
    worst = (1, 1.0)
    for c in (2, 3, 4, 5, 6, 7):
        if len(d) < 2 * c:
            continue
        ph = [float(d[k::c].mean()) for k in range(c)]
        r = max(ph) / max(min(ph), 1e-6)
        if r > worst[1]:
            worst = (c, r)
    out["worst_cycle"], out["worst_ratio"] = worst[0], round(worst[1], 2)
    return out


def fit(d: np.ndarray, pattern: list[int] | None) -> tuple[list[int], int, float]:
    """The pattern and rotation under which travel per unit of true time is smoothest (speed may drift slowly)."""
    best = None
    for p in ([pattern] if pattern else PATTERNS):
        for rot in range(len(p)):
            u = np.array([p[(i + rot) % len(p)] for i in range(len(d))], np.float32)
            v = d / u
            k = max(3, 2 * len(p) + 1)
            sm = np.convolve(np.pad(v, k // 2, mode="edge"), np.ones(k) / k, mode="valid")  # the slow drift of the camera's speed
            err = float(np.sqrt(np.mean((v / np.maximum(sm, 1e-6) - 1.0) ** 2))) + 0.004 * len(p)  # a simpler pattern wins a tie
            if best is None or err < best[2]:
                best = (p, rot, err)
    return best


_dis = None


def flow(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    global _dis
    if _dis is None:
        _dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
        _dis.setFinestScale(1)
    return _dis.calc(a, b, None)


def between(A: np.ndarray, B: np.ndarray, frac: float) -> np.ndarray:
    """The frame at `frac` of the way from A to B (BGR uint8, full size)."""
    H, W = A.shape[:2]
    hw, hh = W // 2, H // 2
    a = cv2.cvtColor(cv2.resize(A, (hw, hh), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    b = cv2.cvtColor(cv2.resize(B, (hw, hh), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    fab, fba = flow(a, b), flow(b, a)
    gx, gy = np.meshgrid(np.arange(hw, dtype=np.float32), np.arange(hh, dtype=np.float32))

    def fetch(img: np.ndarray, f: np.ndarray, k: float) -> tuple[np.ndarray, np.ndarray]:
        # the pixel that arrives at x came from x - k*f(x), IF the picture there moves the way x was told it moves
        mx, my = gx - k * f[..., 0], gy - k * f[..., 1]
        f_at = cv2.remap(f, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        mis = np.hypot(f_at[..., 0] - f[..., 0], f_at[..., 1] - f[..., 1])
        inside = ((mx >= 0) & (mx <= hw - 1) & (my >= 0) & (my <= hh - 1)).astype(np.float32)
        conf = cv2.GaussianBlur(np.exp(-(mis / 2.5) ** 2) * inside, (0, 0), 1.2)
        MX = cv2.resize(mx, (W, H), interpolation=cv2.INTER_LINEAR) * (W / hw)
        MY = cv2.resize(my, (W, H), interpolation=cv2.INTER_LINEAR) * (H / hh)
        return cv2.remap(img, MX, MY, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE).astype(np.float32), conf

    wa, ca = fetch(A, fab, frac)
    wb, cb = fetch(B, fba, 1.0 - frac)
    up = lambda m: cv2.resize(m, (W, H), interpolation=cv2.INTER_LINEAR)[..., None]
    qa, qb = up(ca) * (1.0 - frac) + 1e-4, up(cb) * frac + 1e-4
    sharp = (wa * qa + wb * qb) / (qa + qb)
    # Where the flow cannot be trusted (fast cloth, a swinging limb) a pixel-exact warp tears the picture. There the
    # frame is built from the broad motion only: both neighbours moved by a smoothed flow and mixed, which reads as a
    # little more motion blur on something already blurred. "Cannot be trusted" = neither neighbour's fetch was
    # consistent, or both were and they still show different things.
    g = lambda im: cv2.cvtColor(cv2.resize(im, (hw, hh), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    e = cv2.GaussianBlur(np.abs(g(wa) - g(wb)), (0, 0), 3.0)
    disagree = np.clip((e - 9.0) / 16.0, 0, 1)
    doubt = np.clip((1 - ca) * (1 - cb) + ca * cb * disagree, 0, 1)
    doubt = cv2.GaussianBlur(cv2.dilate(doubt, np.ones((5, 5), np.uint8)), (0, 0), 4.0)
    if float(doubt.max()) > 0.02:
        sa, _ = fetch(A, cv2.GaussianBlur(fab, (0, 0), 14.0), frac)
        sb, _ = fetch(B, cv2.GaussianBlur(fba, (0, 0), 14.0), 1.0 - frac)
        broad = sa * (1.0 - frac) + sb * frac
        m = up(np.clip(doubt * 1.6, 0, 1))
        sharp = sharp * (1 - m) + broad * m
    return np.clip(sharp + 0.5, 0, 255).astype(np.uint8)


def main() -> None:
    args = sys.argv[1:]
    opts = {"--pattern": "auto", "--crf": "12", "--report": ""}
    for k in list(opts):
        if k in args:
            i = args.index(k); opts[k] = args[i + 1]; del args[i:i + 2]
    check_only, mark = "--check-only" in args, "--mark" in args
    args = [a for a in args if a not in ("--check-only", "--mark")]
    src = args[0]
    start = float(args[1]) if len(args) > 1 else None
    dur = float(args[2]) if len(args) > 2 else None
    out = args[3] if len(args) > 3 else None
    w, h, fps = probe(src)
    d = steps_of(src, start, dur)
    rep = {"src": src, "start": start, "dur": dur, "before": unevenness(d), "steps_px": [round(float(x), 1) for x in d]}
    if check_only or out is None:
        print(json.dumps(rep, ensure_ascii=False)); return
    pat = None if opts["--pattern"] == "auto" else [int(x) for x in opts["--pattern"].split(",")]
    p, rot, err = fit(d, pat)
    units = [p[(i + rot) % len(p)] for i in range(len(d))]
    rep.update({"pattern": p, "rotation": rot, "fit_error": round(err, 3), "units": units, "slowdown": round(float(np.mean(units)), 3)})
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", f"{fps:.6f}", "-i", "-",
                            "-an", "-c:v", "libx264", "-preset", "medium", "-crf", opts["--crf"], "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    prev, made, total, synth_idx = None, 0, 0, []
    for i, f in enumerate(reader(src, start, dur, w, h)):
        f = f.copy()
        if prev is not None:
            u = units[i - 1] if i - 1 < len(units) else 1
            for k in range(1, u):
                m = between(prev, f, k / u)
                if mark:
                    m[8:40, 8:40] = (0, 0, 255)
                enc.stdin.write(m.tobytes()); synth_idx.append(total); total += 1; made += 1
        enc.stdin.write(f.tobytes()); total += 1
        prev = f
    enc.stdin.close(); enc.wait()
    rep.update({"out": out, "frames": total, "synthesized": made, "synthesized_at": synth_idx, "after": unevenness(steps_of(out, None, None))})
    if opts["--report"]:
        json.dump(rep, open(opts["--report"], "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in rep.items() if k not in ("steps_px", "units", "synthesized_at")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
