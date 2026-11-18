#!/usr/bin/env python3
"""QC for the Blades edition: the words, their timing against the voice, the layout, the file, the sound, the licences.

Usage: python qc_blades.py FILM.mp4 PLAN.json WORK_DIR OUT.json [--licences LICENCES.json] [--original MIX.wav]
       WORK_DIR is the render_blades.py work folder (qc_edl.json, picture.mp4, text/, and the Remotion EDL
       it wrote to remotion/src/edl_blades.json is read from the repository).

What is checked
  text      every hemistich on screen is, character for character, the poem record (data/poem.json) and the
            aligned words (data/timing.json): nothing added, dropped, reordered or re-spelt
  sync      each word appears at its aligned onset (minus the fixed lead), inside the shot it is spoken over,
            and stays at least until it has been spoken
  layout    measured width of every row (HarfBuzz/Raqm shaping) <= 86 % of the frame, rows inside the safe area
  seen      in the FINISHED frames, each word really differs from the picture under it (it is not hidden by an
            occlusion, a dim "lit" shot or a bright plate)
  file      size, rate, duration, codec, colour tags, video levels; no stray black stretches
  sound     the film's sound is the original mix in sync (lag), loudness, true peak
  flashes   pipeline/flash_check.py on the whole film
  licences  every shot's source is recorded as verified free
"""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ORDER = ["v1a", "v1b", "v2a", "v2b", "v3a", "v3b", "v4a", "v4b", "v5a", "v5b", "v6a", "v6b"]
LEAD = 0.06


def run(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def frame(path: str, t: float, w: int, h: int, gray: bool = True) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(t, 0):.4f}", "-i", path, "-frames:v", "1", "-vf",
                          f"scale={w}:{h}:flags=area,format={'gray' if gray else 'rgb24'}", "-f", "rawvideo", "-"], capture_output=True).stdout
    c = 1 if gray else 3
    return np.frombuffer(raw, np.uint8).reshape(h, w, c).squeeze() if len(raw) == w * h * c else np.zeros((h, w), np.uint8)


def main() -> None:
    args = sys.argv[1:]
    opts = {"--licences": None, "--original": None}
    for k in list(opts):
        if k in args:
            i = args.index(k); opts[k] = args[i + 1]; del args[i:i + 2]
    film, plan_p, work, out_p = args
    plan = json.load(open(plan_p, encoding="utf-8"))
    qc_edl = json.load(open(os.path.join(work, "qc_edl.json"), encoding="utf-8"))
    edl = json.load(open(os.path.join(ROOT, "remotion", "src", "edl_blades.json"), encoding="utf-8"))
    poem = json.load(open(os.path.join(ROOT, "data", "poem.json"), encoding="utf-8"))
    timing = json.load(open(os.path.join(ROOT, plan.get("timing", "data/timing.json")), encoding="utf-8"))
    fps, dur = plan["fps"], plan["duration"]
    rep: dict = {"film": film, "checks": []}

    def check(name: str, ok: bool, detail) -> None:
        rep["checks"].append({"check": name, "pass": bool(ok), "detail": detail})

    # ------------------------------------------------------------ text
    truth = {}
    for v in poem["verses"]:
        truth[f"v{v['n']}a"], truth[f"v{v['n']}b"] = v["sadr"], v["ajuz"]
    aligned = {lid: [w for w in timing["words"] if w["line"] == lid] for lid in ORDER}
    blocks = {lid: sorted([l for l in edl["lines"] if l["id"] == lid or l["id"].startswith(lid + ".")],
                          key=lambda l: (int(l["id"].split(".")[1]) if "." in l["id"] else 0)) for lid in ORDER}
    bad = []
    for lid in ORDER:
        shown = " ".join(w["text"] for b in blocks[lid] for w in b["words"])
        spoken = " ".join(w["word"] for w in aligned[lid])
        if not (shown == truth[lid] == spoken):
            bad.append({"line": lid, "shown": shown, "poem": truth[lid], "aligned": spoken})
    check("all 12 hemistichs on screen equal the poem record and the aligned words, character for character", not bad,
          {"hemistichs": len(ORDER), "words": sum(len(aligned[l]) for l in ORDER), "mismatches": bad})
    verse_ids = {b["id"] for lid in ORDER for b in blocks[lid]}
    extra = [{"id": l["id"], "text": " ".join(w["text"] for w in l["words"])} for l in edl["lines"] if l["id"] not in verse_ids]
    allowed = {"title": "المُتَنَبّي", "credit1": "شِعر: أبو الطيّب المتنبّي", "credit2": "إلقاء: عبدالله العنزي"}
    check("no lettering other than the verses, the poet's name and the two credits",
          all(allowed.get(e["id"]) == e["text"] for e in extra), extra)

    # ------------------------------------------------------------ sync
    cuts = qc_edl["cuts"] + [dur]
    shot_ids = list(qc_edl["licences"].keys())
    rows, off, early, short = [], [], [], []
    for lid in ORDER:
        k = 0
        for b in blocks[lid]:
            fade = float(b.get("out", 0.0))
            for w in b["words"]:
                al = aligned[lid][k]; k += 1
                on = w["start"] - float(b.get("lead", LEAD))
                si = max(i for i, c in enumerate(cuts[:-1]) if c <= w["start"] + 1e-6)
                row = {"line": b["id"], "word": w["text"], "aligned_onset": al["start"], "appears": round(on, 3), "shot": shot_ids[si],
                       "full_until": round(b["clear"] - fade, 3), "spoken_end": al["end"]}
                rows.append(row)
                if abs(w["start"] - al["start"]) > 0.002:
                    off.append(row)
                if on < cuts[si] - 0.085 or b["clear"] > cuts[si + 1] + 0.26:   # a block may ride a transition's half
                    early.append({**row, "shot_span": [cuts[si], cuts[si + 1]], "clear": b["clear"]})
                if b["clear"] - fade < al["end"] - 0.12:   # it may leave with a cut that lands inside its last syllable
                    short.append(row)
    check("every word appears at its aligned onset (fixed 0.06 s lead)", not off, {"words": len(rows), "off": off})
    check("every word is shown inside the shot it is spoken over", not early, early)
    check("every word stays at full strength until it has been spoken (within 0.12 s of its last sound)", not short, short)
    rep["words"] = rows

    # ------------------------------------------------------------ layout
    try:
        from PIL import ImageFont
        fonts = {("AmiriB", 700): "amiri-Amiri-Bold.ttf", ("AmiriB", 400): "amiri-Amiri-Regular.ttf",
                 ("ArefRuqaaB", 700): "arefruqaa-ArefRuqaa-Bold.ttf", ("ArefRuqaaB", 400): "arefruqaa-ArefRuqaa-Regular.ttf"}
        wide, unsafe, lay = [], [], []
        for l in edl["lines"]:
            fam, wt, size = l.get("family", "AmiriB"), int(l.get("weight", 700)), float(l["size"])
            f = ImageFont.truetype(os.path.join(ROOT, "remotion", "public", "fonts", fonts[(fam, wt)]), 200, layout_engine=ImageFont.Layout.RAQM)
            rws = [l["words"][: l["breakAfter"]], l["words"][l["breakAfter"]:]] if l.get("breakAfter") else [l["words"]]
            for r in rws:
                wpx = sum(f.getlength(w["text"], direction="rtl", language="ar") / 200 * size + 0.28 * size for w in r)
                frac = wpx / 1080.0
                top, bot = l["y"] - 0.62 * size / 1920, l["y"] + 0.62 * size / 1920
                item = {"id": l["id"], "text": " ".join(w["text"] for w in r), "size": size, "width_frac": round(frac, 3), "y": l["y"],
                        "top": round(top, 3), "bottom": round(bot, 3)}
                lay.append(item)
                if frac > 0.86:
                    wide.append(item)
                if top < 0.08 or bot > 0.84:
                    unsafe.append(item)
        check("no row is wider than 86 % of the frame", not wide, wide)
        check("every row sits inside the safe area (8 %..84 % of the height)", not unsafe, unsafe)
        rep["layout"] = lay
    except Exception as e:  # noqa: BLE001
        check("layout measured", False, f"could not measure: {e}")

    # ------------------------------------------------------------ the file
    pr = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", film]))
    v = next(s for s in pr["streams"] if s["codec_type"] == "video")
    a = next((s for s in pr["streams"] if s["codec_type"] == "audio"), None)
    W, H = int(v["width"]), int(v["height"])
    n, d = v["r_frame_rate"].split("/")
    fdur = float(pr["format"]["duration"])
    scale = W / plan["w"]
    check("picture format", (W, H) == (int(plan["w"] * scale), int(plan["h"] * scale)) and W * 16 == H * 9 and abs(float(n) / float(d) - fps) < 1e-6
          and v["codec_name"] == "h264" and v.get("pix_fmt") == "yuv420p" and v.get("color_space") == "bt709" and v.get("color_range") == "tv",
          {"size": [W, H], "fps": f"{n}/{d}", "codec": v["codec_name"], "profile": v.get("profile"), "pix_fmt": v.get("pix_fmt"),
           "colour": [v.get("color_space"), v.get("color_primaries"), v.get("color_transfer"), v.get("color_range")], "bit_rate": pr["format"].get("bit_rate")})
    check("duration is the plan's", abs(fdur - dur) <= 1.5 / fps, {"file_s": fdur, "plan_s": dur})
    check("sound stream", a is not None and a["codec_name"] == "aac" and int(a["sample_rate"]) == 48000 and int(a["channels"]) == 2,
          None if a is None else {"codec": a["codec_name"], "rate": a["sample_rate"], "channels": a["channels"], "bit_rate": a.get("bit_rate")})
    st = run(["ffmpeg", "-v", "error", "-i", film, "-vf", "signalstats,metadata=print:file=-", "-an", "-f", "null", "-"])
    ymin = [float(x) for x in re.findall(r"signalstats\.YMIN=([\d.]+)", st)]
    ymax = [float(x) for x in re.findall(r"signalstats\.YMAX=([\d.]+)", st)]
    yavg = [float(x) for x in re.findall(r"signalstats\.YAVG=([\d.]+)", st)]
    # the picture is clamped to 18..232 before encoding; the encoder's own ringing may go a little beyond, which
    # EBU R103 allows for (preferred range 16..235, tolerated 5..246 in 8 bit)
    check("video levels inside the EBU R103 tolerance (luma 5..246 in every frame)", bool(ymin) and min(ymin) >= 5 and max(ymax) <= 246,
          {"frames": len(ymin), "min": min(ymin) if ymin else None, "max": max(ymax) if ymax else None,
           "frames_below_16": sum(y < 16 for y in ymin), "frames_above_235": sum(y > 235 for y in ymax)})
    dark = [i for i, y in enumerate(yavg) if y < 17.5]
    runs, s0 = [], None
    for i in dark + [None]:
        if s0 is None:
            s0 = p = i
        elif i is not None and i == p + 1:
            p = i
        else:
            runs.append([round(s0 / fps, 2), round((p + 1) / fps, 2)]); s0 = p = i
    allow = plan.get("qc_dark", [[0.0, 0.3], [3.2, 3.8], [9.9, 10.7], [20.5, 20.7], [30.4, 31.1]])
    stray = [r for r in runs if r[1] - r[0] > 0.09 and not any(a0 - 0.05 <= r[0] and r[1] <= a1 + 0.05 for a0, a1 in allow)]
    check("no stray black stretch", not stray, {"dark_runs": runs, "allowed": allow, "stray": stray})

    # ------------------------------------------------------------ are the words really seen?
    pic = os.path.join(work, "picture.mp4")
    tdir = os.path.join(work, "text")
    tfiles = {}
    for p in glob.glob(os.path.join(tdir, "element-*.png")):
        m = re.search(r"element-(\d+)\.png$", p)
        if m:
            tfiles[int(m.group(1))] = p
    if os.path.exists(pic) and tfiles:
        import cv2
        w2, h2 = 540, 960
        weak, seen = [], []
        for lid in ORDER:
            for b in blocks[lid]:
                for w in b["words"]:
                    t = min(w["start"] + 0.3, b["clear"] - float(b.get("out", 0.0)) - 0.03)
                    fi = int(round(t * fps))
                    tp = tfiles.get(fi)
                    if tp is None:
                        continue
                    al = cv2.resize(cv2.imread(tp, cv2.IMREAD_UNCHANGED)[..., 3], (w2, h2), interpolation=cv2.INTER_AREA)
                    al0 = None
                    tp0 = tfiles.get(int(round((w["start"] - 0.12) * fps)))   # the same block just before this word arrived
                    if tp0 is not None:
                        al0 = cv2.resize(cv2.imread(tp0, cv2.IMREAD_UNCHANGED)[..., 3], (w2, h2), interpolation=cv2.INTER_AREA)
                    m = (al > 128) & ((al0 < 40) if al0 is not None else True)   # this word's own pixels
                    if m.sum() < 30:
                        continue
                    fa = frame(film, fi / fps, w2, h2).astype(np.float32)
                    fb = frame(pic, fi / fps, w2, h2).astype(np.float32)
                    dlt = np.abs(fa - fb)[m]
                    item = {"line": b["id"], "word": w["text"], "t": round(fi / fps, 3), "mean_delta": round(float(dlt.mean()), 1),
                            "share_visible": round(float((dlt > 12).mean()), 2), "plate_luma": round(float(fb[m].mean()), 1)}
                    seen.append(item)
                    if item["mean_delta"] < 22 or item["share_visible"] < 0.55:
                        weak.append(item)
        check("every word stands out from the picture under it in the finished frames", not weak and len(seen) > 40, {"measured": len(seen), "weak": weak})
        rep["seen"] = seen
    else:
        check("every word stands out from the picture under it in the finished frames", False, "picture.mp4 or text/ missing in the work folder")

    # ------------------------------------------------------------ sound
    try:
        import pyloudnorm as pyln
        from scipy.signal import resample_poly
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", film, "-vn", "-ac", "2", "-ar", "48000", "-f", "f32le", "-"], capture_output=True).stdout
        x = np.frombuffer(raw, np.float32).reshape(-1, 2)
        lufs = float(pyln.Meter(48000).integrated_loudness(x))
        tp = float(20 * np.log10(np.abs(resample_poly(x, 4, 1, axis=0)).max() + 1e-12))
        check("loudness and true peak", -16.0 <= lufs <= -13.0 and tp <= -0.95, {"integrated_lufs": round(lufs, 2), "true_peak_dbtp": round(tp, 2)})
        orig_p = opts["--original"] or plan.get("audio")
        if orig_p and os.path.exists(orig_p):
            raw = subprocess.run(["ffmpeg", "-v", "error", "-i", orig_p, "-vn", "-ac", "2", "-ar", "48000", "-f", "f32le", "-"], capture_output=True).stdout
            o = np.frombuffer(raw, np.float32).reshape(-1, 2)
            nn = min(len(x), len(o))
            xm, om = x[:nn].mean(1), o[:nn].mean(1)
            seg = slice(48000 * 2, min(nn, 48000 * 28))
            best = max(range(-2400, 2401, 12), key=lambda L: float(np.dot(xm[seg], np.roll(om, L)[seg])))
            fine = max(range(best - 12, best + 13), key=lambda L: float(np.dot(xm[seg], np.roll(om, L)[seg])))
            c = float(np.dot(xm[seg], np.roll(om, fine)[seg]) / (np.linalg.norm(xm[seg]) * np.linalg.norm(om[seg]) + 1e-12))
            check("the sound is the original mix, in sync", abs(fine) <= 48 and c >= float(plan.get("qc_min_corr", 0.9)),
                  {"lag_samples": fine, "lag_ms": round(fine / 48, 2), "correlation": round(c, 4)})
    except Exception as e:  # noqa: BLE001
        check("sound measured", False, f"{e}")

    # ------------------------------------------------------------ flashes
    fc = run([sys.executable, os.path.join(HERE, "flash_check.py"), film])
    try:
        fj = json.loads(fc.strip().splitlines()[-1])
        check("photosensitivity screen", fj.get("verdict") == "PASS", fj)
    except Exception:  # noqa: BLE001
        check("photosensitivity screen", False, fc[-400:])

    # ------------------------------------------------------------ licences
    lic_p = opts["--licences"]
    if lic_p and os.path.exists(lic_p):
        lic = json.load(open(lic_p, encoding="utf-8"))
        rec, missing = [], []
        srcs = [(s["id"], s["src"]) for s in plan["shots"]] + [(f"overlay{i}", o["src"]) for i, o in enumerate(plan.get("overlays", []))] \
            + [(f"{s['id']}.matte", s["trans"]["src"]) for s in plan["shots"] if s.get("trans", {}).get("src")]
        for sid, src in srcs:
            m = re.search(r"(\d+)(?:-\d+)?\.mp4$", src)
            key = m.group(1) if m else None
            ok = bool(key) and lic.get(key, {}).get("licence") == "videoFree"
            rec.append({"use": sid, "item": key, "licence": lic.get(key, {}).get("licence"), "page": lic.get(key, {}).get("page")})
            if not ok:
                missing.append(sid)
        check("every source is recorded as verified free (Mixkit item page data-license=videoFree)", not missing, {"sources": rec, "not_verified": missing})
    else:
        check("licences checked", False, "no licence record given (--licences)")

    rep["passed"] = sum(c["pass"] for c in rep["checks"])
    rep["total"] = len(rep["checks"])
    json.dump(rep, open(out_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for c in rep["checks"]:
        print(("PASS " if c["pass"] else "FAIL ") + c["check"])
    print(f"{rep['passed']}/{rep['total']} passed -> {out_p}")


if __name__ == "__main__":
    main()
