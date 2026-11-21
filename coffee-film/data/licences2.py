#!/usr/bin/env python3
"""The licence record of the director's cut, built from what the cut actually uses.

Reads data/plan2.json (picture: footage, overlays, fonts), data/sound2.json (every sound file) and the sound
library's catalogue (each Mixkit item's own licence record, checked when it was downloaded), and writes
data/licences2.json. Run it after data/plan2.py and data/sound2.py.
Usage: python licences2.py [SFX_CATALOG.json] [VFX_CATALOG.json]
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CAT = sys.argv[1] if len(sys.argv) > 1 else "/home/user/coffee/sfx/catalog.json"
VFX_CAT = sys.argv[2] if len(sys.argv) > 2 else "/home/user/coffee/vfx/catalog.json"


def main() -> None:
    plan = json.load(open(os.path.join(HERE, "plan2.json"), encoding="utf-8"))
    snd = json.load(open(os.path.join(HERE, "sound2.json"), encoding="utf-8"))
    cat = json.load(open(CAT, encoding="utf-8"))
    by_file = {os.path.basename(i["file"]): i for i in cat["items"]}
    files = sorted({os.path.basename(x["file"]) for x in snd["beds"] + snd["cues"] + snd["ticks"]})
    used, own = [], []
    for f in files:
        if f.startswith("IMG_"):
            own.append(f)
            continue
        i = by_file.get(f)
        if i is None:
            raise SystemExit(f"no licence record for {f}")
        used.append({k: i.get(k) for k in ("id", "title", "page_url", "licence", "licence_code_on_page", "licence_url",
                                            "statement_on_page", "checked", "download_page", "asset_url", "asset_sha256")})
    # filmed elements (light leak, steam): each Mixkit item's own page record, from the VFX element catalogue
    vcat = json.load(open(VFX_CAT, encoding="utf-8"))
    vby = {str(i["id"]): i for i in vcat["items"]}
    ids = []
    for o in plan.get("overlays", []) + [pl for sh in plan["shots"] for pl in sh.get("plate_layers", [])]:
        ids += [i for i in o.get("credit_ids", []) if i not in ids]
    overlays = []
    for oid in ids:
        rec = vby.get(oid)
        if rec is None or "videoFree" not in (rec.get("licence_as_stated") or ""):
            raise SystemExit(f"element {oid}: no videoFree licence record")
        overlays.append({k: rec.get(k) for k in ("id", "title", "page", "licence_as_stated", "checked")})
    fonts = sorted({ln["font"] for t in plan["titles"] for ln in t["lines"]})
    out = {
        "what": "Licences of everything in THE CITY CAN WAIT (director's cut)",
        "footage": "All picture is the commissioner's own: iPhone clips " + ", ".join(sorted({os.path.basename(s['src']) for s in plan['shots'] if s.get('src')})) +
                   " are prepared stretches of the commissioner's clips; their own sound is used too (" + ", ".join(own) + "). Location and device tags are not carried into the finished file.",
        "filmed_elements": overlays,
        "score": {
            "title": "THE CITY CAN WAIT (original score, pipeline/compose.py)",
            "made_from": "VSCO-2 Community Edition sample library (Versilian Studios), CC0 1.0 (public domain dedication); the pipe organ and upright piano samples by Simon Dalzell (Ivy Audio), whose Info.txt grants the right to redistribute; credit to Versilian Studios and Simon Dalzell is encouraged",
            "composition": "original; written for this film; no melody, chord sequence or motif of any existing score is quoted",
        },
        "sound_effects": {"licence": cat.get("licence"), "how_checked": cat.get("how_checked"), "items": used},
        "fonts": {f: ("Montserrat, SIL Open Font License 1.1 (fonts/OFL-Montserrat.txt)" if f.startswith("montserrat")
                      else "Cormorant Garamond, SIL Open Font License 1.1 (fonts/OFL-Cormorant-Garamond.txt)") for f in fonts},
    }
    json.dump(out, open(os.path.join(HERE, "licences2.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"licences2.json: {len(used)} sound effects, {len(overlays)} overlays, {len(fonts)} fonts")


if __name__ == "__main__":
    main()
