#!/usr/bin/env python3
"""CI smoke test for the containerised MCP server, using ONLY synthetic media (no user content).

Generates: a 6 s stereo WAV (harmonic "voice-like" tone + noise bed) and a 3 s test-pattern clip,
then exercises every tool against the running server, including a 3 s Remotion render with an
Arabic verse to prove Chromium + HarfBuzz text rendering works inside the image.

Usage: python ci_smoke.py URL
"""
from __future__ import annotations

import asyncio
import base64
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from mcp import Client


def synth(tmp: Path) -> tuple[Path, Path]:
    wav, clip = tmp / "tone.wav", tmp / "pattern.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "aevalsrc='0.3*sin(2*PI*165*t)*(0.6+0.4*sin(2*PI*3*t))+0.15*sin(2*PI*330*t)':s=44100:d=6",
                    "-f", "lavfi", "-i", "anoisesrc=d=6:c=pink:a=0.05:r=44100",
                    "-filter_complex", "[0][1]amix=inputs=2,aformat=channel_layouts=stereo", str(wav)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:d=3",
                    "-pix_fmt", "yuv420p", "-c:v", "libx264", str(clip)], check=True)
    return wav, clip


async def main(url: str) -> None:
    tmp = Path(tempfile.mkdtemp())
    wav, clip = synth(tmp)
    results = []
    async with Client(url, read_timeout_seconds=3600) as c:
        async def call(name, args, expect_error=False):
            t0 = time.time()
            r = await c.call_tool(name, args)
            text = "".join(getattr(b, "text", "") for b in r.content)
            data = r.structured_content
            if data is None:
                try:
                    data = json.loads(text)
                except ValueError:
                    data = text
            if isinstance(data, dict) and set(data) == {"result"}:
                data = data["result"]
            ok = r.is_error == expect_error
            results.append({"tool": name, "ok": ok, "s": round(time.time() - t0, 1), "detail": str(data)[:300]})
            print(("PASS " if ok else "FAIL ") + f"{name:24s} {time.time() - t0:6.1f}s  {str(data)[:140]}", flush=True)
            return data

        names = sorted(t.name for t in (await c.list_tools()).tools)
        print("tools:", names)
        await call("import_media", {"filename": "tone.wav", "base64_data": base64.b64encode(wav.read_bytes()).decode()})
        await call("import_media", {"filename": "pattern.mp4", "base64_data": base64.b64encode(clip.read_bytes()).decode()})
        await call("import_media", {"filename": "../x", "base64_data": "AA"}, expect_error=True)
        await call("import_media", {"filename": "x.mp4", "url": "https://169.254.169.254/latest"}, expect_error=True)
        await call("list_assets", {})
        await call("inspect_media", {"asset": "tone.wav"})
        await call("extract_audio", {"asset": "pattern.mp4"}, expect_error=True)  # no audio stream -> clear error
        sep = await call("separate_voice", {"asset": "tone.wav", "music_only_start": 0, "music_only_end": 1})
        voice = sep["assets"]["voice"] if isinstance(sep, dict) else "tone.wav"
        await call("transcribe_arabic", {"asset": voice, "model": "small"})
        await call("sync_subtitles", {"asset": voice, "verses": [{"sadr": "تَكَسَّرَتِ النِصالُ", "ajuz": "عَلى النِصالِ"}]})
        await call("search_footage", {"query": "fog", "source": "mixkit", "limit": 3})
        await call("download_licensed_media", {"url": "https://example.com/a.mp4", "filename": "a.mp4"}, expect_error=True)
        await call("download_licensed_media", {"url": "https://assets.mixkit.co/videos/9592/9592-720.mp4", "filename": "r.mp4",
                   "source_page": "https://mixkit.co/free-stock-video/rainstorm-clouds-approaching-the-desert-9592/"}, expect_error=True)  # Restricted
        await call("edit_video", {"asset": "pattern.mp4", "output": "graded.mp4", "duration": 3, "grade": "endurance"})
        timing = {"duration": 3.0, "voice_film_start": 0.0, "words": [{"film_start": 0.5, "film_end": 1.5}]}
        await call("import_media", {"filename": "timing.json", "base64_data": base64.b64encode(json.dumps(timing).encode()).decode()})
        await call("mix_audio", {"voice": "tone.wav", "music": "tone.wav", "timing": "timing.json", "output_prefix": "ci"})
        edl = {
            "fps": 30, "duration": 3.0, "audio": "ci_master.wav",
            "title": {"text": "النِصالُ عَلى النِصالِ", "poet": "أبو الطيّب المتنبّي", "start": 0.0, "end": 1.4},
            "credits": {"lines": ["اختبار"], "start": 2.2, "end": 3.0},
            "shots": [{"id": "S1", "src": "graded.mp4", "start": 0.0, "end": 3.0, "fadeIn": 0, "fadeOut": 0,
                       "move": {"scaleFrom": 1.0, "scaleTo": 1.05, "xFrom": 0, "xTo": 0, "yFrom": 0, "yTo": 0},
                       "focusX": 0.5, "focusY": 0.5, "act": "VI"}],
            "verses": [{"n": 1, "showFrom": 1.0, "showUntil": 3.0,
                        "sadr": {"verse": 1, "part": "a", "text": "تَكَسَّرَتِ النِصالُ", "start": 1.2, "end": 2.0},
                        "ajuz": {"verse": 1, "part": "b", "text": "عَلى النِصالِ", "start": 2.0, "end": 2.8}}],
        }
        await call("create_composition", {"edl": edl})
        await call("render_film", {"composition": "NisalScope", "output": "ci_film.mp4", "crf": 20})
        await call("inspect_output", {"asset": "ci_film.mp4", "stills": 3})
    json.dump(results, open("ci_results.json", "w"), ensure_ascii=False, indent=1)
    failed = [r for r in results if not r["ok"]]
    print(f"{len(results) - len(failed)}/{len(results)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
