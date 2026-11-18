#!/usr/bin/env python3
"""Build the Blades edition (or a section of it) end to end.

  plan -> build files (build_blades.py)
       -> the cut picture (montage.py)
       -> depth for the shots whose letters stand behind something (depth_cache.py)
       -> the letters alone, transparent (Remotion BladesText)
       -> the letters set into the picture (comp_text.py)
       -> finishing: one grain over picture and letters, levels clamped to 18..232 (room for the encoder), the soundtrack

Usage: python render_blades.py PLAN.json WORK_DIR OUT.mp4 [--from T] [--to T] [--scale 1.0] [--audio WAV]
                               [--skip picture,depth,text] [--crf 17] [--grain 10] [--share OUT_1080.mp4]
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable
BROWSER = os.environ.get("REMOTION_BROWSER", "/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell")


def run(cmd: list[str], **kw) -> None:
    print("+", " ".join(str(c) for c in cmd[:6]), "..." if len(cmd) > 6 else "", flush=True)
    subprocess.run(cmd, check=True, **kw)


def main() -> None:
    args = sys.argv[1:]
    opts = {"--from": None, "--to": None, "--scale": "1.0", "--audio": None, "--skip": "", "--crf": "17", "--grain": "10", "--share": None,
            "--jobs": "3"}
    for k in list(opts):
        if k in args:
            i = args.index(k); opts[k] = args[i + 1]; del args[i:i + 2]
    plan_p, work, out_p = args
    plan = json.load(open(plan_p, encoding="utf-8"))
    fps = plan["fps"]
    t0 = float(opts["--from"]) if opts["--from"] is not None else 0.0
    t1 = float(opts["--to"]) if opts["--to"] is not None else float(plan["duration"])
    f0, f1 = int(round(t0 * fps)), int(round(t1 * fps))
    t0, t1 = f0 / fps, f1 / fps
    scale = float(opts["--scale"])
    skip = set(filter(None, opts["--skip"].split(",")))
    os.makedirs(work, exist_ok=True)
    run([PY, os.path.join(HERE, "build_blades.py"), plan_p, work])
    pic = os.path.join(work, "picture.mp4")
    if "picture" not in skip:
        run([PY, os.path.join(HERE, "montage.py"), os.path.join(work, "montage.json"), pic, "--from", str(t0), "--to", str(t1),
             "--scale", str(scale), "--jobs", opts["--jobs"]])
    ddir = os.path.join(work, "depth")
    if "depth" not in skip:
        shutil.rmtree(ddir, ignore_errors=True)
        rgs = []
        for a, b in json.load(open(os.path.join(work, "depth_ranges.json"))):
            a, b = max(a, t0), min(b, t1)
            if b > a:
                rgs.append(f"{a - t0:.5f}:{b - t0:.5f}")  # times inside the picture file
        if rgs:
            run([PY, os.path.join(HERE, "depth_cache.py"), pic, ddir] + rgs)
    tdir = os.path.join(work, "text")
    if "text" not in skip:
        shutil.rmtree(tdir, ignore_errors=True)
        run(["npx", "remotion", "render", "BladesText", tdir, "--sequence", "--image-format=png", f"--scale={2 * scale:g}",
             f"--frames={f0}-{f1 - 1}", "--concurrency=3", f"--browser-executable={BROWSER}", "--log=error"], cwd=os.path.join(ROOT, "remotion"))
    comp = os.path.join(work, "comp.mp4")
    run([PY, os.path.join(HERE, "comp_text.py"), pic, tdir, os.path.join(work, "comp.json"), comp, "--pic-start", str(t0), "--depth", ddir])
    # ---- finishing
    audio = opts["--audio"] or plan.get("audio")
    W, H = int(plan["w"] * scale) // 2 * 2, int(plan["h"] * scale) // 2 * 2
    d = t1 - t0
    grain = (f"color=c=0x808080:s={W}x{H}:r={fps}:d={d:.5f},format=yuv420p,noise=c0s={opts['--grain']}:c0f=t")
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", comp, "-f", "lavfi", "-i", grain]
    if audio:
        cmd += ["-ss", f"{t0:.5f}", "-t", f"{d:.5f}", "-i", audio]
    cmd += ["-filter_complex", "[0:v]format=yuv420p[a];[a][1:v]blend=all_mode=overlay:all_opacity=0.55,format=yuv420p,lutyuv=y='clip(val,18,232)'[v]",
            "-map", "[v]"]
    if audio:
        fade = f"afade=t=in:st=0:d=0.02,afade=t=out:st={max(0.0, d - 0.05):.3f}:d=0.05" if (t0 > 0 or t1 < plan["duration"]) else "anull"
        cmd += ["-map", "2:a", "-af", fade, "-c:a", "aac", "-b:a", "320k"]
    cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", opts["--crf"], "-x264-params", "aq-mode=3", "-profile:v", "high", "-level", "5.1",
            "-pix_fmt", "yuv420p", "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
            "-tag:v", "avc1", "-movflags", "+faststart", "-t", f"{d:.5f}", out_p]
    run(cmd)
    if opts["--share"]:
        run(["ffmpeg", "-v", "error", "-y", "-i", out_p, "-vf", "scale=1080:1920:flags=lanczos", "-c:v", "libx264", "-preset", "slow", "-crf", "19",
             "-profile:v", "high", "-level", "4.1", "-pix_fmt", "yuv420p", "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709",
             "-color_trc", "bt709", "-tag:v", "avc1", "-c:a", "copy", "-movflags", "+faststart", opts["--share"]])
    print(json.dumps({"out": out_p, "from": t0, "to": t1, "frames": f1 - f0}))


if __name__ == "__main__":
    main()
