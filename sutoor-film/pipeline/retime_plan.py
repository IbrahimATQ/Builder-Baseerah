#!/usr/bin/env python3
"""Re-time an existing shot plan onto a re-paced voice timeline (see repace.py).

Time map: piecewise linear through every hemistich start/end (old -> new), so a cut that sat in a
pause between two lines lands proportionally inside the new, longer pause, and the prologue and
coda keep their length. Each shot's source in-point is re-solved so that its anchor moment (by
default the first line it covers, or a named word such as the word a lightning strike or a wave
burst is timed to) still meets the same source frame.

Usage: python retime_plan.py plan.json old_timing.json new_timing.json OUT_plan.json [ID=word ...]
"""
from __future__ import annotations

import json
import sys

import numpy as np


def main() -> None:
    plan_p, old_p, new_p, out_p, *anchors = sys.argv[1:]
    named = dict(a.split("=", 1) for a in anchors)
    plan = json.load(open(plan_p, encoding="utf-8"))
    old = json.load(open(old_p, encoding="utf-8"))
    new = json.load(open(new_p, encoding="utf-8"))
    xs, ys = [0.0], [0.0]
    for k in old["hemistichs"]:
        for e in ("start", "end"):
            xs.append(old["hemistichs"][k][e]); ys.append(new["hemistichs"][k][e])
    xs.append(old["duration"]); ys.append(new["duration"])
    # before the first line: identity (the prologue keeps its timing)
    xs.insert(1, old["voice_film_start"] - 0.25); ys.insert(1, new["voice_film_start"] - 0.25)
    f = lambda t: float(np.interp(t, xs, ys))  # noqa: E731
    word_old = {w["word"]: w["film_start"] for w in old["words"]}
    word_new = {w["word"]: w["film_start"] for w in new["words"]}
    first_line = [(h["start"], k) for k, h in old["hemistichs"].items()]

    for s in plan["shots"]:
        fi = s.get("fadeIn", 0.4)
        a_old = s["start"] - fi
        s0, e0 = s["start"], s["end"]
        s["start"], s["end"] = round(f(s0), 3), round(f(e0), 3)
        if s["id"] in named:
            w = named[s["id"]]
            anc_old, anc_new = word_old[w], word_new[w]
        else:
            inside = [(t, k) for t, k in first_line if s0 - 0.3 <= t < e0]
            if inside:
                anc_old, anc_new = inside[0][0], new["hemistichs"][inside[0][1]]["start"]
            else:
                anc_old, anc_new = s0, s["start"]
        src_at_anchor = s["in"] + (anc_old - a_old) * s.get("speed", 1.0)
        s["in"] = round(max(0.0, src_at_anchor - (anc_new - (s["start"] - fi)) * s.get("speed", 1.0)), 3)
    shift = new["duration"] - old["duration"]
    for key in ("credits",):
        if key in plan:
            plan[key]["start"] = round(plan[key]["start"] + shift, 3)
            plan[key]["end"] = round(plan[key]["end"] + shift, 3)
    json.dump(plan, open(out_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for s in plan["shots"]:
        print(f"{s['id']:4s} {s['start']:6.2f}-{s['end']:6.2f}  in {s['in']:.2f}")


if __name__ == "__main__":
    main()
