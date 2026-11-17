#!/usr/bin/env python3
"""Shift every film time in a timing file by DELTA seconds (e.g. shorten the opening of a reel).

Usage: python shift_timing.py timing.json DELTA OUT.json
"""
import json
import sys

src, delta, out = sys.argv[1], float(sys.argv[2]), sys.argv[3]
t = json.load(open(src, encoding="utf-8"))
assert t["voice_film_start"] + delta >= 0.5, "the voice would start before 0.5 s"
for w in t["words"]:
    w["film_start"] = round(w["film_start"] + delta, 3)
    w["film_end"] = round(w["film_end"] + delta, 3)
for h in t["hemistichs"].values():
    h["start"] = round(h["start"] + delta, 3)
    h["end"] = round(h["end"] + delta, 3)
for k in ("voice_film_start", "voice_film_end", "duration"):
    t[k] = round(t[k] + delta, 3)
t.pop("warp", None)
t["shifted_by"] = delta
json.dump(t, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"voice {t['voice_film_start']}..{t['voice_film_end']} s, duration {t['duration']} s")
