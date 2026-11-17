#!/usr/bin/env python3
"""End-to-end test of the ARABIC POETRY FILM PRODUCTION MCP over streamable HTTP.

Usage: python e2e_test.py URL SOURCE_VIDEO POEM_JSON [--render]
Writes a JSON log of every call (tool, arguments summary, ok/error, seconds, result excerpt).
"""
from __future__ import annotations

import asyncio
import base64
import json
import sys
import time

from mcp import Client


async def main(url: str, video: str, poem_path: str, render: bool) -> None:
    poem = json.load(open(poem_path, encoding="utf-8"))
    log = []

    async with Client(url, read_timeout_seconds=7200) as c:
        tools = await c.list_tools()
        names = sorted(t.name for t in tools.tools)
        log.append({"step": "list_tools", "ok": True, "tools": names})

        async def call(name: str, args: dict, expect_error: bool = False):
            t0 = time.time()
            r = await c.call_tool(name, args)
            text = "".join(getattr(b, "text", "") for b in r.content)
            data = r.structured_content
            if data is None:
                try:
                    data = json.loads(text)
                except ValueError:
                    data = text
            ok = (not r.is_error) != expect_error
            log.append({"step": name, "ok": ok, "is_error": r.is_error, "seconds": round(time.time() - t0, 1),
                        "result": (json.dumps(data, ensure_ascii=False)[:900] if not isinstance(data, str) else data[:900])})
            print(f"{'PASS' if ok else 'FAIL'} {name:24s} {time.time() - t0:7.1f}s", flush=True)
            if r.is_error and not expect_error:
                raise SystemExit(f"{name} failed: {text[:800]}")
            return data.get("result", data) if isinstance(data, dict) and set(data) == {"result"} else data

        b64 = base64.b64encode(open(video, "rb").read()).decode()
        await call("import_media", {"filename": "recitation.mp4", "base64_data": b64})
        await call("import_media", {"filename": "../escape.mp4", "base64_data": "AAAA"}, expect_error=True)  # traversal
        await call("import_media", {"filename": "x.mp4", "url": "https://127.0.0.1/secret"}, expect_error=True)  # SSRF
        await call("list_assets", {})
        await call("inspect_media", {"asset": "recitation.mp4"})
        audio = await call("extract_audio", {"asset": "recitation.mp4"})
        sep = await call("separate_voice", {"asset": audio["asset"], "music_only_start": 28.6, "music_only_end": 30.9})
        voice = sep["assets"]["voice"]
        await call("transcribe_arabic", {"asset": voice})
        verses = [{"sadr": v["sadr"], "ajuz": v["ajuz"]} for v in poem["verses"]]
        await call("sync_subtitles", {"asset": voice, "verses": verses, "intro": poem["intro_spoken"]})
        found = await call("search_footage", {"query": "fog", "source": "mixkit", "limit": 5})
        await call("search_footage", {"query": "desert dunes", "source": "wikimedia", "limit": 5})
        first = found[0]
        dl = None
        for u in (first["download"], first["fallback_download"]):
            try:
                dl = await call("download_licensed_media", {"url": u, "filename": "fog_test.mp4", "source_page": first["page_url"]})
                break
            except SystemExit:
                continue
        await call("download_licensed_media", {"url": "https://example.com/a.mp4", "filename": "bad.mp4"}, expect_error=True)
        await call("edit_video", {"asset": "fog_test.mp4", "output": "fog_graded.mp4", "start": 1, "duration": 3, "grade": "mortality"})
        await call("inspect_output", {"asset": "fog_graded.mp4", "stills": 6})
        if render:
            await call("render_film", {"composition": "NisalScope", "output": "film_via_mcp.mp4"})
            await call("inspect_output", {"asset": "film_via_mcp.mp4", "stills": 12})

    json.dump(log, open("e2e_log.json", "w"), ensure_ascii=False, indent=1)
    print("ALL PASS" if all(s["ok"] for s in log) else "SOME FAILED")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3], "--render" in sys.argv))
