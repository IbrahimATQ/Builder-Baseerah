#!/usr/bin/env python3
"""Checks on a finished file of the coffee film.

  file       size, frame rate, codec, colour tags, duration (the plan's)
  privacy    no location or device tags left in the file (the iPhone wrote GPS coordinates into the originals)
  motion     no repeated or dropped frames inside a shot (every frame differs from the one before it,
             outside the fades from and to black), and no step in motion bigger than 2.5x its neighbours
  levels     luma inside the EBU R103 tolerance 5..246 in every frame, measured after a light low-pass (sigma 0.8 px)
  black      no black frames except the fade in and the fade out
  sound      AAC 48 kHz stereo; loudness and true peak of the file's own sound; the sound is the intended
             master, in sync (cross-correlation with the WAV it was made from)
  titles     every title's ink inside 8 %..84 % of the height and clear of the right-hand button column
  flashes    the photosensitivity screen (sutoor-film/pipeline/flash_check.py), if present

Usage: python qc.py FILM.mp4 PLAN.json MASTER.wav OUT.json [--scale 1.0]
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

import numpy as np


def run(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def main() -> None:
    args = sys.argv[1:]
    film, plan_p, wav, out_p = args[:4]
    plan = json.load(open(plan_p, encoding="utf-8"))
    fps, dur = plan["fps"], plan["duration"]
    checks = []

    def check(name: str, ok: bool, detail) -> None:
        checks.append({"check": name, "pass": bool(ok), "detail": detail})
        print(("PASS " if ok else "FAIL ") + name, flush=True)

    pr = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", film]))
    v = next(s for s in pr["streams"] if s["codec_type"] == "video")
    a = next((s for s in pr["streams"] if s["codec_type"] == "audio"), None)
    W, H = int(v["width"]), int(v["height"])
    fdur = float(pr["format"]["duration"])
    check("picture: 9:16, 24 fps, H.264 High, BT.709, 4:2:0", W * 16 == H * 9 and v["r_frame_rate"] == "24/1" and v["codec_name"] == "h264"
          and v.get("profile") == "High" and v.get("pix_fmt") == "yuv420p" and v.get("color_space") == "bt709",
          {"size": [W, H], "fps": v["r_frame_rate"], "codec": v["codec_name"], "profile": v.get("profile"), "pix_fmt": v.get("pix_fmt"),
           "colour": [v.get("color_space"), v.get("color_primaries"), v.get("color_transfer"), v.get("color_range")]})
    check("duration is the plan's", abs(fdur - dur) <= 1.5 / fps, {"file_s": round(fdur, 3), "plan_s": dur})
    tags = {**pr["format"].get("tags", {}), **v.get("tags", {}), **(a.get("tags", {}) if a else {})}
    leaky = {k: tags[k] for k in tags if re.search(r"location|ISO6709|gps|model|make|software|creation", k, re.I)}
    check("no location or device tags in the file", not leaky, leaky or "none")

    # ---- motion, levels and black: one pass over a small grey copy
    w, h = 270, 480
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", film, "-vf", f"scale={w}:{h}:flags=area,format=gray", "-f", "rawvideo", "-"],
                         capture_output=True).stdout
    F = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)
    d = np.abs(np.diff(F, axis=0)).mean(axis=(1, 2))
    mean = F.mean(axis=(1, 2))
    fo0, fo1 = plan["finish"]["fade_out"]
    inside = [k for k in range(len(d)) if (k + 1) / fps > plan["finish"]["fade_in"] + 0.05 and k / fps < fo0 - 0.05]
    frozen = [round((k + 1) / fps, 3) for k in inside if d[k] < 0.02]
    jumps = []
    for k in inside:
        nb = [d[j] for j in (k - 2, k - 1, k + 1, k + 2) if j in inside]
        cut = any(abs((k + 1) / fps - s["start"]) < 1.5 / fps for s in plan["shots"])
        if nb and not cut and d[k] > 2.5 * np.median(nb) and d[k] > 3.0:
            jumps.append(round((k + 1) / fps, 3))
    check("motion: no repeated frames and no jumps inside shots", not frozen and not jumps,
          {"frames": len(F), "repeated_at_s": frozen[:20], "jumps_at_s": jumps[:20], "median_step": round(float(np.median(d)), 2)})
    blacks = [round(k / fps, 3) for k in range(len(mean)) if mean[k] < 6 and plan["finish"]["fade_in"] < k / fps < fo0]
    check("no black frames outside the fades", not blacks, blacks[:20])
    # measured, as EBU R103 measures, after a light low-pass: single pixels of encoder ringing on the grain do not count
    st = run(["ffmpeg", "-v", "error", "-i", film, "-vf", "gblur=sigma=0.8,signalstats,metadata=print:file=-", "-an", "-f", "null", "-"])
    ymin = [float(x) for x in re.findall(r"signalstats\.YMIN=([\d.]+)", st)]
    ymax = [float(x) for x in re.findall(r"signalstats\.YMAX=([\d.]+)", st)]
    check("levels inside EBU R103 tolerance (luma 5..246, after a light low-pass)", bool(ymin) and min(ymin) >= 5 and max(ymax) <= 246,
          {"min": min(ymin) if ymin else None, "max": max(ymax) if ymax else None})

    # ---- sound
    check("sound stream: AAC, 48 kHz, stereo", a is not None and a["codec_name"] == "aac" and int(a["sample_rate"]) == 48000 and int(a["channels"]) == 2,
          None if a is None else {"codec": a["codec_name"], "rate": a["sample_rate"], "channels": a["channels"]})
    if a is not None:
        eb = subprocess.run(["ffmpeg", "-nostats", "-i", film, "-map", "0:a", "-af", "ebur128=peak=true", "-f", "null", "-"],
                            capture_output=True, text=True).stderr
        summ = eb[eb.rfind("Summary:"):]
        I = float(re.search(r"I:\s+(-?[\d.]+) LUFS", summ).group(1))
        TP = float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", summ).group(1))
        target = -16.0 if "natural" in os.path.basename(wav) else -14.0
        check(f"loudness {target:g} LUFS (+/-1), true peak <= -0.9 dBTP", abs(I - target) <= 1.0 and TP <= -0.9, {"integrated_lufs": I, "true_peak_dbtp": TP})
        dec = lambda p: np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-map", "0:a", "-ac", "1", "-ar", "8000", "-f", "f32le", "-"],
                                                      capture_output=True).stdout, np.float32)
        x, y = dec(film), dec(wav)
        n = min(len(x), len(y))
        x, y = x[:n] - x[:n].mean(), y[:n] - y[:n].mean()
        X, Y = np.fft.rfft(x, 2 * n), np.fft.rfft(y, 2 * n)
        cc = np.fft.irfft(X * np.conj(Y))
        lag = int(np.argmax(np.abs(np.concatenate([cc[-400:], cc[:401]])))) - 400
        corr = float(np.max(np.abs(cc)) / (np.sqrt((x ** 2).sum() * (y ** 2).sum()) + 1e-12))
        check("the sound is the intended master, in sync", abs(lag) <= 8 and corr > 0.95, {"lag_ms": lag / 8.0, "correlation": round(corr, 4)})

    # ---- titles: measure the ink of each title at full opacity in the finished frame's geometry
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from render import Title  # noqa: E402
    bad = []
    boxes = []
    for t in plan["titles"]:
        tl = Title(t, plan["fonts"], W, H, W / plan["w"])
        ys, xs = np.where(tl.A > 0.25)
        top = (tl.yc - tl.A.shape[0] / 2 + ys.min()) / H
        bot = (tl.yc - tl.A.shape[0] / 2 + ys.max()) / H
        left, right = (tl.x0 + xs.min()) / W, (tl.x0 + xs.max()) / W
        boxes.append({"id": t["id"], "top": round(top, 3), "bottom": round(bot, 3), "left": round(left, 3), "right": round(right, 3)})
        if top < 0.08 or bot > 0.84 or (right > 0.86 and bot > 0.5) or left < 0.04 or right > 0.96:
            bad.append(t["id"])
    check("titles inside the safe area (8 %..84 % of the height, clear of the button column)", not bad, boxes)

    fc = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "sutoor-film", "pipeline", "flash_check.py")
    if os.path.exists(fc):
        r = subprocess.run([sys.executable, fc, film], capture_output=True, text=True).stdout.strip().splitlines()
        j = json.loads(r[-1]) if r else {}
        check("photosensitivity screen", j.get("verdict") == "PASS", {k: j.get(k) for k in ("max_flashing_area_fraction", "threshold_area_fraction", "verdict")})
    json.dump({"film": film, "checks": checks, "passed": sum(c["pass"] for c in checks), "total": len(checks)},
              open(out_p, "w"), indent=1, ensure_ascii=False)
    print(f"{sum(c['pass'] for c in checks)}/{len(checks)} passed -> {out_p}")


if __name__ == "__main__":
    main()
