#!/usr/bin/env python3
"""Prepare the source stretches of the coffee film: upright 4K, slowed to 0.8x frame for frame, stabilised.

The iPhone files are 3840x2160 with a -90 degree display rotation and run at 30 fps (their timestamps were
checked: no dropped frames). Each stretch named in data/sources.json is
  * decoded upright (ffmpeg applies the rotation) from `from` to `to` seconds of the source,
  * given new timestamps at 24 fps, one per source frame: every real frame is kept, nothing is blended
    or interpolated, and the motion plays at 0.8x (a slow morning, and smoother handheld motion),
  * stabilised with vid.stab in two passes (`smoothing` in frames: higher keeps less of the hand's motion;
    `tripod` locks the frame to its first frame for shots that were meant to be still),
  * written as 2160x3840 10-bit H.264 (crf 12), so the grade has room to work without banding.
Times inside a prepared stretch are therefore (source time - from) / 0.8.

Usage: python prep.py SOURCES.json RAW_DIR OUT_DIR [id ...]
"""
from __future__ import annotations

import json
import os
import subprocess
import sys


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def main() -> None:
    src_p, raw, out = sys.argv[1:4]
    only = set(sys.argv[4:])
    os.makedirs(out, exist_ok=True)
    for s in json.load(open(src_p, encoding="utf-8"))["stretches"]:
        if only and s["id"] not in only:
            continue
        clip = os.path.join(raw, s["file"])
        dst = os.path.join(out, f"{s['id']}.mp4")
        trf = os.path.join(out, f"{s['id']}.trf")
        cut = ["-ss", f"{s['from']:.3f}", "-t", f"{s['to'] - s['from']:.3f}", "-i", clip]
        retime = "setpts=N/(24*TB)"
        st = s.get("stab", {})
        if st.get("off"):
            vf = f"{retime},scale=2160:3840:flags=lanczos"
        else:
            run(["ffmpeg", "-v", "error", "-y"] + cut + ["-vf", f"{retime},vidstabdetect=shakiness={st.get('shakiness', 6)}:accuracy=15:stepsize=6"
                 f":tripod={1 if st.get('tripod') else 0}:result={trf}", "-f", "null", "-"])
            mode = "tripod=1:" if st.get("tripod") else f"smoothing={st.get('smoothing', 30)}:"
            vf = (f"{retime},vidstabtransform=input={trf}:{mode}optzoom={st.get('optzoom', 1)}:zoomspeed=0.1:interpol=bicubic:crop=black,"
                  f"scale=2160:3840:flags=lanczos,unsharp=5:5:0.35:5:5:0.0")
        run(["ffmpeg", "-v", "error", "-y"] + cut + ["-an", "-vf", vf, "-r", "24", "-c:v", "libx264", "-preset", "medium", "-crf", str(s.get("crf", 12)),
             "-pix_fmt", "yuv420p10le", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-map_metadata", "-1", dst])
        n = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
                            "-of", "csv=p=0", dst], capture_output=True, text=True).stdout.strip()
        print(json.dumps({"id": s["id"], "frames": int(n), "film_seconds": round(int(n) / 24, 3)}), flush=True)


if __name__ == "__main__":
    main()
