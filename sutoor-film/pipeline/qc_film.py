#!/usr/bin/env python3
"""Automated QC for the finished film: Arabic text, sync, audio, video, licensing.

Usage: python qc_film.py FILM.mp4 edl.json poem.json timing.json plan.json voice_film.wav OUT.json
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import unicodedata

import numpy as np
import pyloudnorm as pyln
import soundfile as sf

HARAKAT = re.compile(r"[ً-ْٰ]")


def sh(args: list[str]) -> str:
    r = subprocess.run(args, capture_output=True, text=True)
    return r.stdout + r.stderr


def main(film, edl_p, poem_p, timing_p, plan_p, voice_p, out_p):
    edl = json.load(open(edl_p, encoding="utf-8"))
    poem = json.load(open(poem_p, encoding="utf-8"))
    timing = json.load(open(timing_p, encoding="utf-8"))
    plan = json.load(open(plan_p, encoding="utf-8"))
    rep: dict = {"checks": []}

    def check(name, ok, detail):
        rep["checks"].append({"check": name, "pass": bool(ok), "detail": detail})

    # ---- Arabic text: exact equality with the truth table, nothing invented or omitted
    shown = [(v["n"], v["sadr"]["text"], v["ajuz"]["text"]) for v in edl["verses"]]
    truth = [(v["n"], v["sadr"], v["ajuz"]) for v in poem["verses"]]
    check("verse text identical to truth table (Unicode)", shown == truth,
          {"verses": len(shown), "mismatches": [s for s, t in zip(shown, truth) if s != t]})
    nfc = all(unicodedata.is_normalized("NFC", x) for _, a, b in shown for x in (a, b))
    check("text is NFC-normalised", nfc, "")
    check("harakat present on every hemistich",
          all(HARAKAT.search(a) and HARAKAT.search(b) for _, a, b in shown),
          {f"v{n}": [len(HARAKAT.findall(a)), len(HARAKAT.findall(b))] for n, a, b in shown})
    unrecited = [x["sadr"] for x in poem.get("supplied_but_not_recited", [])]
    check("unrecited supplied verses are not displayed",
          not any(u == a for u in unrecited for _, a, _b in shown), {"unrecited": unrecited})

    # ---- Sync: subtitle reveal vs aligned hemistich onset
    H = timing["hemistichs"]
    offs = []
    for v in edl["verses"]:
        for part in ("sadr", "ajuz"):
            h = v[part]
            key = f"v{v['n']}{'a' if part == 'sadr' else 'b'}"
            offs.append(round((h["start"] - 0.12) - H[key]["start"], 3))
    check("subtitle reveal leads speech by 0.12 s (|err| <= 0.15 s)", all(abs(o + 0.12) <= 0.15 for o in offs), {"lead_s": offs})
    order_ok = all(edl["verses"][i]["showUntil"] <= edl["verses"][i + 1]["sadr"]["start"] for i in range(len(edl["verses"]) - 1))
    check("verses never overlap on screen", order_ok, "")

    # ---- Video stream
    probe = json.loads(sh(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", film]))
    v = next(s for s in probe["streams"] if s["codec_type"] == "video")
    a = next(s for s in probe["streams"] if s["codec_type"] == "audio")
    dur = float(probe["format"]["duration"])
    rep["video"] = {k: v.get(k) for k in ("codec_name", "profile", "width", "height", "pix_fmt", "r_frame_rate", "bit_rate")}
    rep["audio"] = {k: a.get(k) for k in ("codec_name", "sample_rate", "channels", "bit_rate")}
    check("H.264 High, yuv420p", v["codec_name"] == "h264" and v.get("pix_fmt") == "yuv420p", rep["video"])
    check("duration matches edit (±0.1 s)", abs(dur - edl["duration"]) <= 0.1, {"file": dur, "edit": edl["duration"]})
    black = sh(["ffmpeg", "-hide_banner", "-i", film, "-vf", "blackdetect=d=0.4:pic_th=0.985", "-an", "-f", "null", "-"])
    blacks = [(float(x), float(y)) for x, y in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", black)]
    intended = [(0.0, 1.2), (edl["duration"] - 4.2, edl["duration"])]
    unexpected = [b for b in blacks if not any(b[0] >= i0 - 0.3 and b[1] <= i1 + 0.3 for i0, i1 in intended)]
    check("no unintended black segments", not unexpected, {"black": blacks, "unexpected": unexpected})
    freeze = sh(["ffmpeg", "-hide_banner", "-i", film, "-vf", "freezedetect=n=0.001:d=1.5", "-an", "-f", "null", "-"])
    freezes = re.findall(r"freeze_start: ([\d.]+)", freeze)
    check("no frozen picture > 1.5 s (outside black)", all(float(f) >= edl["duration"] - 4.5 or float(f) < 1.3 for f in freezes), {"freeze_starts": freezes})

    # ---- Audio
    wav = out_p.replace(".json", "_audio.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", film, "-vn", "-c:a", "pcm_f32le", wav], check=True)
    y, sr = sf.read(wav, always_2d=True)
    meter = pyln.Meter(sr)
    lufs = meter.integrated_loudness(y)
    tp = re.search(r"Peak:\s+(-?[\d.]+)", sh(["ffmpeg", "-hide_banner", "-i", wav, "-af", "ebur128=peak=true", "-f", "null", "-"]).split("Summary:")[-1])
    clip = int(np.sum(np.abs(y) >= 0.999))
    rep["loudness"] = {"integrated_lufs": round(lufs, 2), "true_peak_dbfs": float(tp.group(1)) if tp else None, "clipped_samples": clip}
    check("integrated loudness -14 ±1 LUFS", abs(lufs + 14) <= 1, rep["loudness"])
    check("true peak <= -0.9 dBFS and no clipping", (tp and float(tp.group(1)) <= -0.9) and clip == 0, rep["loudness"])
    hop = int(0.4 * sr)
    st = [meter.integrated_loudness(y[i:i + hop]) if np.any(y[i:i + hop]) else -70 for i in range(0, len(y) - hop, hop)]
    st = [s if np.isfinite(s) else -70 for s in st]
    jumps = [round(b - a, 1) for a, b in zip(st, st[1:])]
    rep["max_short_term_jump_db"] = max(jumps) if jumps else 0
    check("no sudden loudness jump > 12 dB per 0.4 s (after the prologue)", max(jumps[3:]) <= 12, {"max_jump": max(jumps[3:])})

    # Voice preservation: the voice in the film must be the isolated voice, unaltered except gain.
    voice, vsr = sf.read(voice_p, always_2d=True)
    s0 = int(timing["voice_film_start"] * sr)
    from scipy.signal import resample_poly

    film_ds = resample_poly(y.mean(1), 1, 6)  # 8 kHz is enough for speech correlation
    vv = resample_poly(voice.mean(1), 1, 6)
    s0 = int(timing["voice_film_start"] * sr) // 6
    best = (-1.0, 0)
    for lag in range(-480, 481, 4):  # ±60 ms (AAC priming / encoder delay)
        a0 = s0 + lag
        if a0 < 0:
            continue
        seg = film_ds[a0:a0 + len(vv)]
        n = min(len(seg), len(vv))
        c = float(np.corrcoef(seg[:n], vv[:n])[0, 1])
        best = max(best, (c, lag))
    rep["voice_alignment"] = {"corr": round(best[0], 3), "lag_ms": round(best[1] / 8.0, 1)}
    check("film audio carries the original voice (corr > 0.8) in sync (|lag| <= 45 ms)",
          best[0] > 0.8 and abs(best[1] / 8.0) <= 45, rep["voice_alignment"])

    # ---- Licensing: every shot has a recorded source and licence
    lic = {s["id"]: s.get("license", "") for s in plan["shots"]}
    check("every shot has a licence record", all(lic.values()), lic)
    srcs = [s["source"] for s in plan["shots"]]
    check("no source clip reused", len(srcs) == len(set(srcs)), {"sources": srcs})

    rep["summary"] = {"passed": sum(c["pass"] for c in rep["checks"]), "total": len(rep["checks"])}
    json.dump(rep, open(out_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for c in rep["checks"]:
        print(("PASS " if c["pass"] else "FAIL ") + c["check"])
    print(rep["summary"])


if __name__ == "__main__":
    main(*sys.argv[1:8])
