#!/usr/bin/env python3
"""Turn a journey plan into the three files the Journey edition is rendered from.

  OUT/picture_plan.json  -> build_picture.py (footage, camera moves, grade, transitions)
  OUT/sfx_spec.json      -> build_sfx.py     (diegetic sound: strikes, hooves, wind, fire)
  OUT/amb_spec.json      -> build_sfx.py     (ambience beds per scene)
  remotion/src/edl_journey.json              (words, their styles, overlays, end word, credits)

The words are never typed into the plan: they come from the aligned timing file, so the text on
screen is exactly the supplied text and each word appears when it is spoken.

Plan keys: timing, fps, end, look, picture (public path of the built picture), audio (public path
of the master), shots[], verses{n: style}, overlays[], endWord{y}, credits{}, sfx[], ambience[].
A verse leaves at `style.clear` if given, else 0.35 s after its last word or 1.0 s before the next
verse's first word, whichever is earlier.

Usage: python build_journey.py plan.json OUT_DIR [--light picture.light.json]
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    args = sys.argv[1:]
    light_p = None
    if "--light" in args:
        i = args.index("--light"); light_p = args[i + 1]; del args[i:i + 2]
    plan_p, out_dir = args
    plan = json.load(open(plan_p, encoding="utf-8"))
    os.makedirs(out_dir, exist_ok=True)
    timing = json.load(open(os.path.join(ROOT, plan["timing"]), encoding="utf-8"))
    fps, end = plan["fps"], plan["end"]

    # ---- picture
    pic = {"fps": fps, "w": 2160, "h": 3840, "duration": end, "end": end, "look": plan.get("look", {}),
           "shots": [{k: v for k, v in s.items() if k not in ("why", "licence", "line")} for s in plan["shots"]]}
    starts = [s["start"] for s in plan["shots"]]
    assert starts == sorted(starts), "shots must be in time order"
    json.dump(pic, open(os.path.join(out_dir, "picture_plan.json"), "w"), indent=1, ensure_ascii=False)

    # ---- words
    words = timing["words"]
    last_word = words[-1]
    verses = []
    for n in range(1, 7):
        ws = [{"text": w["word"], "start": w["film_start"], "end": w["film_end"], "part": w["line"][-1]}
              for w in words if w["line"][:-1] == f"v{n}"]
        style = dict(plan["verses"][str(n)])
        nxt = [w["film_start"] for w in words if w["line"][:-1] == f"v{n + 1}"]
        auto = ws[-1]["end"] + 0.45  # every line stays clean >= 0.4 s after its hemistich ends
        if nxt:
            auto = min(auto, nxt[0] - 0.95)
        clear = style.pop("clear", None)
        if n == 6:
            clear = clear if clear is not None else plan["endWord"].get("clear_line", last_word["film_start"] + 1.6)
        verses.append({"n": n, "words": ws, "clear": round(clear if clear is not None else auto, 3), "style": style})

    light = {"lum": [], "warm": []}
    if light_p and os.path.exists(light_p):
        lj = json.load(open(light_p))
        light = {"lum": lj["lum"], "warm": lj["warm"]}
    ew = plan["endWord"]
    edl = {
        "fps": fps,
        "duration": max(end, timing["duration"]),
        "picture": plan["picture"],
        "audio": plan["audio"],
        "light": light,
        "overlays": plan.get("overlays", []),
        "verses": verses,
        "endWord": {"text": last_word["word"], "start": round(last_word["film_start"], 3),
                    "end": round(ew.get("end", last_word["film_start"] + 3.3), 3), "y": ew.get("y", 0.45),
                    "overlay": ew.get("overlay", True)},
        "credits": plan["credits"],
        "tints": plan.get("tints", []),
    }
    if plan.get("title"):
        edl["title"] = plan["title"]
    json.dump(edl, open(os.path.join(ROOT, "remotion", "src", "edl_journey.json"), "w"), ensure_ascii=False)

    # ---- QC views (qc_film.py's formats): hemistich text as shown, how long each verse stays, shot sources
    H = timing["hemistichs"]
    qc_edl = {"duration": edl["duration"], "endWord": edl["endWord"], "verses": []}
    for v in verses:
        n = v["n"]
        hs = {p: {"text": " ".join(w["text"] for w in v["words"] if w["part"] == ab), "start": H[f"v{n}{ab}"]["start"], "end": H[f"v{n}{ab}"]["end"]}
              for p, ab in (("sadr", "a"), ("ajuz", "b"))}
        until = (edl["endWord"]["end"] if n == 6 else v["clear"] + 0.70)  # the exit takes 0.25 s stagger + 0.45 s
        qc_edl["verses"].append({"n": n, **hs, "words": v["words"], "showUntil": round(until, 3)})
    json.dump(qc_edl, open(os.path.join(out_dir, "qc_edl.json"), "w"), ensure_ascii=False, indent=1)
    shots = plan["shots"]
    qc_plan = {"intended_black": plan.get("intended_black", []), "shots": []}
    for i, s in enumerate(shots):
        dur_in = float(s.get("trans", {}).get("dur", 0)) if i else 0.0
        e = shots[i + 1]["start"] if i + 1 < len(shots) else end
        qc_plan["shots"].append({"id": s["id"], "source": s["src"], "in": s["in"], "start": s["start"], "end": e,
                                 "fadeIn": dur_in, "fadeOut": 0.0, "speed": s.get("speed", 1.0), "license": s.get("licence", "")})
    json.dump(qc_plan, open(os.path.join(out_dir, "qc_plan.json"), "w"), ensure_ascii=False, indent=1)

    # ---- sound
    json.dump({"duration": end, "cues": plan.get("sfx", [])}, open(os.path.join(out_dir, "sfx_spec.json"), "w"), indent=1)
    json.dump({"duration": end, "cues": plan.get("ambience", [])}, open(os.path.join(out_dir, "amb_spec.json"), "w"), indent=1)

    print(json.dumps({"shots": len(plan["shots"]), "verses": [(v["n"], v["words"][0]["start"], v["clear"]) for v in verses],
                      "endWord": edl["endWord"], "light_frames": len(light["lum"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
