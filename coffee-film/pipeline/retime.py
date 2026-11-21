#!/usr/bin/env python3
"""Exact speed curves for the slow-motion shots of WARSZAWA: one output frame per film frame, at the source position
the edit asks for (data/cuesheet3.json, shots[].src_at_frame).

For every film frame of a shot marked "retime": the wanted position in the prepared stretch (prep frame index =
(source seconds - stretch start) * 30) is
  * a real frame when it lies within 0.03 of one: that frame, untouched (the 0.8x parts of the shot are all real);
  * inside a slow-motion stretch, a real frame is mixed half and half with RIFE's prediction of it from its two
    neighbours, so it is as smooth as the predicted frames around it;
  * otherwise an in-between frame predicted by RIFE v4.26 (pipeline/slowmo.py: the official IFNet arithmetic, MIT
    licence, run on the CPU) at the exact timestep between its two real neighbours: no blending, no ghosting
    from mixing two frames, and the speed changes are as smooth as the eased curve in the cue sheet.
Output: a 2160x3840 10-bit H.264 clip (crf 10) with exactly one frame per film frame of the shot, and a JSON map
(per output frame: film frame, prep position, real or predicted).

Usage: OMP_NUM_THREADS=2 python -I retime.py CUESHEET.json SOURCES.json PREP_DIR OUT_DIR SHOT_ID [--scale 1.0]
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from slowmo import Encoder, Interpolator, decode_frames, load_model, probe  # noqa: E402

WEIGHTS = "/home/user/coffee/slowmo/dl/rife426/RIFEv4.26_0921/flownet.pkl"
SNAP = 0.03


def main() -> None:
    args = sys.argv[1:]
    scale = 1.0
    if "--scale" in args:
        i = args.index("--scale"); scale = float(args[i + 1]); del args[i:i + 2]
    cs_p, src_p, prep_dir, out_dir, sid = args
    cs = json.load(open(cs_p, encoding="utf-8"))
    shot = next(s for s in cs["shots"] if s["id"] == sid)
    stretch = next(s for s in json.load(open(src_p, encoding="utf-8"))["stretches"] if s["id"] == shot["prep"])
    src = os.path.join(prep_dir, f"{shot['prep']}.mp4")
    w, h, fps = probe(src)
    n_src = int(subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries",
                                "stream=nb_read_packets", "-of", "csv=p=0", src], capture_output=True, text=True).stdout.strip())
    # positions outside the prepared stretch (the shot's handle frames) hold its first / last frame
    pos = [min(max(0.0, (x - stretch["from"]) * 30.0), n_src - 1.0) for x in shot["src_at_frame"]]
    lo, hi = int(np.floor(min(pos))), int(np.ceil(max(pos)))
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{sid}.mp4")
    net = load_model(WEIGHTS)
    ip = Interpolator(net, scale)
    enc = Encoder(out, w, h, fps, "x264", 10)
    frames = {}          # the three most recent real frames
    gen = decode_frames(src, lo, min(hi + 1, n_src - 1))
    manifest, times = [], []

    def real(k: int):
        while k not in frames:
            i, img = next(gen)
            frames[i] = img
            for old in [q for q in frames if q < i - 2]:
                del frames[old]
        return frames[k]

    snapped = [abs(p - round(p)) <= SNAP for p in pos]
    for j, p in enumerate(pos):
        k = int(round(p))
        if snapped[j]:
            slow = (j > 0 and not snapped[j - 1]) or (j + 1 < len(pos) and not snapped[j + 1])
            if slow and 0 < k < n_src - 1:
                # a real frame among predicted ones: it would look crisper (and noisier) than its neighbours and
                # tick three times a second; mixed half and half with the prediction from its own two neighbours,
                # it keeps its content and gets their smoothness
                fm, fp = real(k - 1), real(k + 1)
                y = next(ip.iter_between(fm, fp, [0.5], key_a=k - 1, key_b=k + 1))
                enc.write(0.5 * real(k) + 0.5 * y)
                manifest.append({"film_frame": shot["first_frame"] + j, "prep_pos": round(p, 4), "real": True, "smoothed": True})
                continue
            enc.write(real(k))
            manifest.append({"film_frame": shot["first_frame"] + j, "prep_pos": round(p, 4), "real": True})
            continue
        a = int(np.floor(p))
        fa, fb = real(a), real(a + 1)
        t0 = time.time()
        y = next(ip.iter_between(fa, fb, [p - a], key_a=a, key_b=a + 1))
        enc.write(y)
        times.append(time.time() - t0)
        manifest.append({"film_frame": shot["first_frame"] + j, "prep_pos": round(p, 4), "real": False})
        print(f"  {sid} frame {j}/{len(pos)} pos {p:.3f}: {times[-1]:.1f} s", file=sys.stderr, flush=True)
    enc.close()
    info = {"shot": sid, "src": src, "out": out, "method": f"RIFE IFNet v4.26 ({os.path.basename(WEIGHTS)}), scale {scale}",
            "first_film_frame": shot["first_frame"], "frames": len(manifest), "predicted": sum(1 for m in manifest if not m["real"]),
            "sec_per_predicted_frame": round(float(np.mean(times)), 2) if times else None, "map": manifest}
    json.dump(info, open(os.path.join(out_dir, f"{sid}.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in info.items() if k != "map"}))


if __name__ == "__main__":
    main()
