#!/usr/bin/env python3
"""Write the footage licence record of a cut: one entry per stock item the plan really uses.

The plan names its sources by file (…/<id>.mp4, or …/<id>-<n>.mp4 for a repaired stretch of item <id>);
the cache is the record kept while scouting (one entry per item whose own page was read: its title, page
address, the licence the page states, and when it was read). An item missing from the cache, or stated as
anything but free, stops the run: it must not be in the film.

Usage: python licence_record.py PLAN.json CACHE.json OUT.json
"""
from __future__ import annotations

import json
import re
import sys

FREE = "videoFree"


def item_id(path: str) -> str | None:
    m = re.search(r"(\d+)(?:-\d+)?\.mp4$", path or "")
    return m.group(1) if m else None


def main() -> None:
    plan_p, cache_p, out_p = sys.argv[1:4]
    plan, cache = json.load(open(plan_p, encoding="utf-8")), json.load(open(cache_p, encoding="utf-8"))
    uses: dict[str, list[str]] = {}
    for s in plan["shots"]:
        uses.setdefault(item_id(s["src"]) or s["src"], []).append(f"shot {s['id']} ({s['start']:g} s)")
    for o in plan.get("overlays", []):
        uses.setdefault(item_id(o["src"]) or o["src"], []).append(f"overlay ({o['start']:g}-{o['end']:g} s)")
    items, bad = [], []
    for i in sorted(uses, key=lambda k: (not k.isdigit(), int(k) if k.isdigit() else 0, k)):
        c = cache.get(i)
        if not c or c.get("licence") != FREE:
            bad.append((i, (c or {}).get("licence")))
            continue
        items.append({"id": int(i), "title": c.get("title", ""), "page": c.get("page", ""), "licence": c["licence"],
                      "verified": c.get("verified", ""), "checked": c.get("checked", ""), "used_for": uses[i]})
    if bad:
        sys.exit(f"not recorded as free, must not be used: {bad}")
    rec = {"licence": "Mixkit Stock Video Free License (https://mixkit.co/license/#videoFree)",
           "how_verified": "each item's own page carries data-license=\"videoFree\"; items marked videoRestricted are never used",
           "items": items}
    json.dump(rec, open(out_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"items": len(items), "shots": len(plan["shots"]), "overlays": len(plan.get("overlays", []))}))


if __name__ == "__main__":
    main()
