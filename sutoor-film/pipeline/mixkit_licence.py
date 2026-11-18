#!/usr/bin/env python3
"""Read the licence of Mixkit items from their own pages, slowly, into a cache.

Mixkit serves two licences item by item: only pages carrying data-license="videoFree" (the Mixkit
Stock Video Free License) may be used; "videoRestricted" may not. Item pages are rate-limited, so this
checks one page at a time with a long pause, keeps everything it has learnt in CACHE.json, and stops
politely on HTTP 429 (run it again later; items already in the cache are skipped).

Usage: python mixkit_licence.py CACHE.json CATALOGUE.json[,CATALOGUE2.json...] ID [ID ...] [--delay 25]
       (catalogues are lists of {"id", "page_url", "title"}; also accepts "ID=URL" arguments)
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) film-pipeline/1.0 (licence check)"


def main() -> None:
    args = sys.argv[1:]
    delay = 25.0
    if "--delay" in args:
        i = args.index("--delay"); delay = float(args[i + 1]); del args[i:i + 2]
    cache_p, cats, ids = args[0], args[1].split(","), args[2:]
    cache = json.load(open(cache_p)) if os.path.exists(cache_p) else {}
    pages: dict[str, dict] = {}

    def walk(o) -> None:
        if isinstance(o, dict):
            if "id" in o and "page_url" in o:
                pages.setdefault(str(o["id"]), {"page": o["page_url"], "title": o.get("title", "")})
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    for c in cats:
        if os.path.exists(c):
            walk(json.load(open(c, encoding="utf-8")))
    todo = []
    for a in ids:
        if "=" in a:
            k, u = a.split("=", 1)
            pages[k] = {"page": u, "title": ""}
            a = k
        if a in cache and cache[a].get("licence") in ("videoFree", "videoRestricted"):
            continue
        if a not in pages:
            print(f"{a}: no page url known", flush=True)
            continue
        todo.append(a)
    for n, a in enumerate(todo):
        if n:
            time.sleep(delay)
        req = urllib.request.Request(pages[a]["page"], headers={"User-Agent": UA})
        try:
            html = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            print(f"{a}: HTTP {e.code}; stopping" if e.code == 429 else f"{a}: HTTP {e.code}", flush=True)
            if e.code == 429:
                break
            continue
        except Exception as e:  # noqa: BLE001
            print(f"{a}: {e}", flush=True)
            continue
        m = re.search(r'data-license="([a-zA-Z]+)"', html)
        lic = m.group(1) if m else "unknown"
        cache[a] = {"licence": lic, "page": pages[a]["page"], "title": pages[a]["title"], "checked": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "verified": f"item page data-license={lic}"}
        json.dump(cache, open(cache_p, "w"), ensure_ascii=False, indent=1)
        print(f"{a}: {lic} | {pages[a]['title']}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
