#!/usr/bin/env python3
"""One plan in, every build file out (the Blades edition).

The film runs on the ORIGINAL soundtrack (the reciter's voice in the music it was mixed with), so film
time is the recording's own time and the word timings are the forced alignment of that recording.

Reads  data/blades/plan.json:
  {"fps", "w", "h", "duration", "look": {...},
   "timing": "data/timing.json"   (words with "start"/"end" in recording time and "line": "v1a"...),
   "shots": [{montage.py shot keys..., "licence": "...",
              "text": {comp_text.py range keys: mode, occlude, track, glow, ...}}],   # how letters live in this shot
   "lines": {"v2a": {"y": 0.2, "x": 0.5, "size": 88, "em": 1, "breakAfter": 0, "clear": t, "out": 0.1, "color": ..}},
   "extra_lines": [{BladesText line objects for titles and credits}],
   "text_default": {...}, "overlays": [...]}

Writes OUT_DIR/montage.json, OUT_DIR/comp.json, OUT_DIR/depth_ranges.json, OUT_DIR/qc_edl.json and the
text EDL for Remotion (remotion/src/edl_blades.json).

Usage: python build_blades.py PLAN.json OUT_DIR [--edl remotion/src/edl_blades.json]
"""
from __future__ import annotations

import json
import os
import sys

ORDER = ["v1a", "v1b", "v2a", "v2b", "v3a", "v3b", "v4a", "v4b", "v5a", "v5b", "v6a", "v6b"]


def main() -> None:
    args = sys.argv[1:]
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    edl_p = os.path.join(here, "remotion", "src", "edl_blades.json")
    if "--edl" in args:
        i = args.index("--edl"); edl_p = args[i + 1]; del args[i:i + 2]
    plan_p, out_dir = args
    plan = json.load(open(plan_p, encoding="utf-8"))
    os.makedirs(out_dir, exist_ok=True)
    timing_p = plan.get("timing", "data/timing.json")
    if not os.path.isabs(timing_p):
        timing_p = os.path.join(here, timing_p)
    words = json.load(open(timing_p, encoding="utf-8"))["words"]
    fps, dur = plan["fps"], plan["duration"]

    # ---- picture
    shot_keys = ("id", "src", "start", "in", "speed", "time", "shutter", "blend", "window", "move", "shake", "flip", "grade", "grade_keys",
                 "sharpen", "trans")
    shots = plan["shots"]
    for a, b in zip(shots, shots[1:]):
        if not b["start"] > a["start"]:
            raise SystemExit(f"shots out of order: {a['id']} {a['start']} then {b['id']} {b['start']}")
    montage = {"fps": fps, "w": plan["w"], "h": plan["h"], "duration": dur, "look": plan.get("look", {}),
               "shots": [{k: s[k] for k in shot_keys if k in s} for s in shots], "overlays": plan.get("overlays", [])}
    json.dump(montage, open(os.path.join(out_dir, "montage.json"), "w"), ensure_ascii=False, indent=1)

    # ---- letters
    lines_cfg = plan.get("lines", {})
    dflt_line = {"y": 0.2, "x": 0.5, "size": 88, "out": 0.1, "color": "#F6EEDD", "emColor": "#FFD79A", **plan.get("line_default", {})}
    lines, qc_lines = [], []
    for i, lid in enumerate(ORDER):
        ws = [w for w in words if w["line"] == lid]
        cfg = {**dflt_line, **lines_cfg.get(lid, {})}
        if cfg.get("hide"):  # the line is written in the picture itself (a filmed burning strip)
            qc_lines.append({"id": lid, "in_picture": True, "words": [{"text": w["word"], "start": w["start"], "end": w["end"]} for w in ws]})
            continue
        nxt = next((w["start"] for w in words if w["line"] == ORDER[i + 1]), None) if i + 1 < len(ORDER) else None
        clear = cfg.pop("clear", None)
        if clear is None:
            clear = (nxt - 0.06) if nxt is not None else ws[-1]["end"] + 1.2
        em = cfg.pop("em", None)
        em = [em] if isinstance(em, int) else (em or [])
        parts = cfg.pop("parts", None)  # [{"words": [a, b], ...layout}]: the hemistich set as several blocks (a word alone on its own shot)
        base = {k: v for k, v in cfg.items() if k != "hide"}
        if parts:
            for pi, part in enumerate(parts):
                a, b = part["words"]
                pc = {**base, **{k: v for k, v in part.items() if k != "words"}}
                p_clear = pc.pop("clear", None)
                if p_clear is None:
                    p_clear = (ws[b]["start"] - 0.06) if b < len(ws) else clear
                lines.append({"id": f"{lid}.{pi}", "words": [{"text": w["word"], "start": round(w["start"], 3), **({"em": True} if k in em else {})}
                                                              for k, w in enumerate(ws) if a <= k < b],
                              "clear": round(p_clear, 3), **pc})
        else:
            lines.append({"id": lid, "words": [{"text": w["word"], "start": round(w["start"], 3), **({"em": True} if k in em else {})} for k, w in enumerate(ws)],
                          "clear": round(clear, 3), **base})
        qc_lines.append({"id": lid, "words": [{"text": w["word"], "start": w["start"], "end": w["end"]} for w in ws], "clear": round(clear, 3)})
    lines += plan.get("extra_lines", [])
    json.dump({"fps": fps, "duration": dur, "lines": lines}, open(edl_p, "w"), ensure_ascii=False, indent=1)

    # ---- how the letters live in each shot
    ranges, depth_ranges = [], []
    for i, s in enumerate(shots):
        t0 = s["start"]
        t1 = shots[i + 1]["start"] if i + 1 < len(shots) else dur
        tx = s.get("text")
        if tx:
            ranges.append({"from": t0, "to": t1, **tx})
            needs_depth = (tx.get("occlude") and tx["occlude"].get("type", "depth") == "depth") or tx.get("dof") or tx.get("atmo") \
                or tx.get("depth") is not None
            if needs_depth:
                depth_ranges.append([t0, t1])
    json.dump({"fps": fps, "default": plan.get("text_default", {}), "ranges": ranges}, open(os.path.join(out_dir, "comp.json"), "w"), ensure_ascii=False, indent=1)
    json.dump(depth_ranges, open(os.path.join(out_dir, "depth_ranges.json"), "w"))
    json.dump({"duration": dur, "fps": fps, "lines": qc_lines, "cuts": [s["start"] for s in shots],
               "licences": {s["id"]: s.get("licence", "") for s in shots}},
              open(os.path.join(out_dir, "qc_edl.json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps({"shots": len(shots), "lines": len(lines), "text_ranges": len(ranges), "depth_ranges": depth_ranges,
                      "missing_licence": [s["id"] for s in shots if not s.get("licence")]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
