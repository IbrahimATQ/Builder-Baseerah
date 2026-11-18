#!/usr/bin/env python3
"""Join picture sections built separately by build_picture.py (--from/--to) into one file, without
re-encoding, and merge their per-frame light measurements.
Usage: python assemble_picture.py OUT.mp4 PART.mp4 [PART.mp4 ...]   (parts in time order)"""
import json
import os
import subprocess
import sys

out, parts = sys.argv[1], sys.argv[2:]
lst = out + ".txt"
open(lst, "w").write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", out], check=True)
os.remove(lst)
lights = [json.load(open(os.path.splitext(p)[0] + ".light.json")) for p in parts]
lights.sort(key=lambda j: j["from_frame"])
keys = [k for k in ("lum", "warm", "band_a", "band_b", "foam") if all(k in j for j in lights)]
merged, nxt = {k: [] for k in keys}, 0
for j in lights:
    assert j["from_frame"] == nxt, f"gap or overlap at frame {nxt} (part starts at {j['from_frame']})"
    for k in keys:
        merged[k] += j[k]
    nxt += len(j["lum"])
lum = merged["lum"]
json.dump({"fps": lights[0]["fps"], "from_frame": 0, **merged}, open(os.path.splitext(out)[0] + ".light.json", "w"))
n = subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries", "stream=nb_read_packets",
                    "-of", "csv=p=0", out], capture_output=True, text=True).stdout.strip()
print(json.dumps({"out": out, "frames": int(n), "light_frames": len(lum)}))
