#!/usr/bin/env python3
"""Build graded shot intermediates + the Remotion EDL from a shot plan and the aligned timing.

Each shot is cut to its hemistich window (plus dissolve handles), retimed if asked, scaled to
1920x1080 with Lanczos, colour-graded with its act's palette (ffmpeg, per shot — no global LUT)
and written as a high-quality H.264 intermediate into remotion/public/shots/.

Usage: python build_film.py shot_plan.json timing.json poem.json REMOTION_DIR AUDIO_FILE
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

GRADES = {
    "prologue": "eq=saturation=0.55:contrast=1.08:brightness=-0.03,colorbalance=bs=0.05:bm=0.03:rh=0.02,curves=master='0/0.02 0.5/0.46 1/0.95'",
    "mortality": "eq=saturation=0.6:contrast=1.06,colorbalance=bs=0.04:bm=0.02:rh=0.02,curves=master='0/0.02 0.5/0.47 1/0.95'",
    "preparation": "colorbalance=rh=0.06:gh=0.02:bh=-0.05:rs=-0.02,eq=saturation=0.8:contrast=1.08,curves=master='0/0.01 0.5/0.47 1/0.96'",
    "time": "colorbalance=bs=0.07:bm=0.04:rh=-0.02,eq=saturation=0.7:brightness=-0.01:contrast=1.05",
    "detachment": "eq=saturation=0.55:contrast=1.02,colorbalance=rh=0.04:bh=-0.03,curves=master='0/0.03 0.5/0.49 1/0.94'",
    "suffering": "eq=contrast=1.12:saturation=0.75,colorbalance=rh=0.07:gm=-0.01:bs=-0.03,curves=master='0/0 0.5/0.46 1/0.97'",
    "endurance": "eq=contrast=1.08:saturation=0.85,colorbalance=rh=0.08:gh=0.03:bh=-0.06:bs=0.02,curves=master='0/0.01 0.5/0.47 1/0.96'",
}


def run(args: list[str]) -> None:
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-2000:])


def probe_duration(p: str) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                         capture_output=True, text=True).stdout
    return float(out.strip())


def main(plan_p: str, timing_p: str, poem_p: str, remotion: str, audio: str) -> None:
    plan = json.load(open(plan_p, encoding="utf-8"))
    timing = json.load(open(timing_p, encoding="utf-8"))
    poem = json.load(open(poem_p, encoding="utf-8"))
    H = timing["hemistichs"]
    shots_dir = os.path.join(remotion, "public", "shots")
    os.makedirs(shots_dir, exist_ok=True)
    fps = 30
    edl_shots = []
    for s in plan["shots"]:
        start, end = s["start"], s["end"]
        fade_in, fade_out = s.get("fadeIn", 0.4), s.get("fadeOut", 0.0)
        speed = s.get("speed", 1.0)
        need = (end - start) + fade_in + fade_out + 0.1  # film seconds incl. handles
        src_need = need * speed
        src_dur = probe_duration(s["source"])
        src_in = max(0.0, min(s["in"], src_dur - src_need))
        if src_dur < src_need:
            raise ValueError(f"{s['id']}: source {src_dur:.2f}s shorter than needed {src_need:.2f}s")
        out = os.path.join(shots_dir, f"{s['id']}.mp4")
        vf = [f"setpts=(PTS-STARTPTS)/{speed}"] if speed != 1.0 else []
        if s.get("reverse"):
            vf.append("reverse")
        vf += [
            f"fps={fps}",
            "scale=1920:1080:force_original_aspect_ratio=increase:flags=lanczos",
            "crop=1920:1080",
            GRADES[s["grade"]],
        ]
        if s.get("extra"):
            vf.append(s["extra"])
        vf.append("format=yuv420p")
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{src_in:.3f}", "-t", f"{src_need:.3f}", "-i", s["source"], "-an",
             "-vf", ",".join(vf), "-c:v", "libx264", "-preset", "slow", "-crf", "12", "-g", "15", out])
        edl_shots.append({
            "id": s["id"], "src": f"shots/{s['id']}.mp4", "start": start, "end": end, "fadeIn": fade_in,
            "fadeOut": fade_out, "toBlack": s.get("toBlack", False), "fromBlack": s.get("fromBlack", False),
            "move": s["move"], "focusX": s.get("focusX", 0.5), "focusY": s.get("focusY", 0.5), "act": s["act"],
        })
        print(f"{s['id']:4s} {start:6.2f}-{end:6.2f}  src {os.path.basename(s['source'])} @{src_in:.2f}s x{speed}  {s['grade']}")

    verses = []
    keys = [f"v{v['n']}" for v in poem["verses"]]
    for i, v in enumerate(poem["verses"]):
        a, b = H[f"v{v['n']}a"], H[f"v{v['n']}b"]
        nxt = H[f"{keys[i + 1]}a"]["start"] if i + 1 < len(keys) else None
        show_until = (nxt - 0.08) if nxt else b["end"] + plan.get("last_verse_hold", 1.6)
        verses.append({
            "n": v["n"], "showFrom": a["start"] - 0.12, "showUntil": round(show_until, 3),
            "sadr": {"verse": v["n"], "part": "a", "text": v["sadr"], "start": a["start"], "end": a["end"]},
            "ajuz": {"verse": v["n"], "part": "b", "text": v["ajuz"], "start": b["start"], "end": b["end"]},
        })
    os.makedirs(os.path.join(remotion, "public", "audio"), exist_ok=True)
    shutil.copy(audio, os.path.join(remotion, "public", "audio", "film_mix.wav"))
    edl = {
        "fps": fps, "duration": timing["duration"], "audio": "audio/film_mix.wav",
        "title": plan["title"], "credits": plan["credits"], "shots": edl_shots, "verses": verses,
    }
    json.dump(edl, open(os.path.join(remotion, "src", "edl.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("edl written:", len(edl_shots), "shots,", len(verses), "verses,", timing["duration"], "s")


if __name__ == "__main__":
    main(*sys.argv[1:6])
