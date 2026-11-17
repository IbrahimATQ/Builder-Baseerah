#!/usr/bin/env python3
"""Harvest Mixkit free stock-video listings (title, description, preview URLs) for a set of tags.

Mixkit items are covered by the Mixkit Stock Video Free License (free for commercial and
personal projects, no attribution required; items may not be redistributed standalone).
This script only reads public listing pages and records metadata. It does not download
full-resolution media; use `mixkit_download()` for selected items.

Usage:
    python mixkit_catalog.py OUT.json tag1 tag2 ... [--pages N]
"""
from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) film-pipeline/1.0"
CARD_RE = re.compile(
    r'data-algolia-analytics-object-id="video-(?P<id>\d+)".*?'
    r'<img src="(?P<thumb>[^"]+)".*?'
    r'<video src="(?P<preview>[^"]+)".*?'
    r'overlay-video-title">\s*(?P<title>.*?)\s*</span>.*?'
    r'(?:overlay-video-description">\s*(?P<desc>.*?)\s*</span>.*?)?'
    r'<a href="(?P<href>/free-stock-video/[^"]+)"',
    re.S,
)


def fetch(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def parse_cards(page: str) -> list[dict]:
    items = []
    for m in CARD_RE.finditer(page):
        vid = m.group("id")
        items.append(
            {
                "id": int(vid),
                "title": html.unescape(m.group("title")).strip(),
                "description": html.unescape(m.group("desc") or "").strip(),
                "page_url": "https://mixkit.co" + m.group("href"),
                "thumb": m.group("thumb"),
                "preview_360": m.group("preview"),
                "license": "Mixkit Stock Video Free License",
            }
        )
    return items


def hi_res_url(item: dict, height: int = 1080) -> str:
    """Best-guess full-resolution URL; both URL schemes Mixkit uses are handled."""
    p = item["preview_360"]
    if "/active_storage/" in p:
        return p.replace("-video-360.mp4", f"-video-{height}.mp4")
    return re.sub(r"-360\.mp4$", f"-{height}.mp4", p)


def harvest(tags: list[str], pages: int = 2, delay: float = 0.6) -> dict[int, dict]:
    catalog: dict[int, dict] = {}
    for tag in tags:
        for page in range(1, pages + 1):
            url = f"https://mixkit.co/free-stock-video/{tag}/" + (f"?page={page}" if page > 1 else "")
            try:
                items = parse_cards(fetch(url))
            except Exception as e:  # noqa: BLE001 - keep harvesting other tags
                print(f"  ! {tag} p{page}: {e}", file=sys.stderr)
                break
            for it in items:
                entry = catalog.setdefault(it["id"], {**it, "tags": []})
                if tag not in entry["tags"]:
                    entry["tags"].append(tag)
            print(f"{tag} p{page}: {len(items)} items", file=sys.stderr)
            if len(items) < 20:
                break
            time.sleep(delay)
    for it in catalog.values():
        it["download_1080"] = hi_res_url(it, 1080)
        it["download_720"] = hi_res_url(it, 720)
    return catalog


if __name__ == "__main__":
    args = sys.argv[1:]
    pages = 2
    if "--pages" in args:
        i = args.index("--pages")
        pages = int(args[i + 1])
        del args[i : i + 2]
    out, tags = args[0], args[1:]
    cat = harvest(tags, pages=pages)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(sorted(cat.values(), key=lambda x: x["id"]), f, ensure_ascii=False, indent=1)
    print(f"{len(cat)} unique items -> {out}", file=sys.stderr)
