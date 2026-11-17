#!/usr/bin/env python3
"""Re-pace a recitation: gentle pitch-preserving slowdown plus breathing room between lines.

The reciter's delivery inside each hemistich is kept (same words, same intonation, same pitch);
only the tempo is eased (rubberband, default 0.92x) and the pauses between hemistichs and between
verses are opened to a minimum length by inserting silence at the quietest point of each gap.

Writes:
  OUT_DIR/voice_film_slow.wav  the re-paced voice, starting at timing["voice_film_start"]
  OUT_DIR/timing_slow.json     every film time remapped (words, hemistichs, end, duration),
                               plus "warp": [[old_t, new_t], ...] for re-timing an existing edit

Usage: python repace.py timing.json voice_film.wav OUT_DIR [--tempo 0.92] [--gap-in 0.6] [--gap-between 1.15]
"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys

import numpy as np
import soundfile as sf

SR = 48000


def stretch(src: str, dst: str, tempo: float) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-af",
                    f"aresample={SR},rubberband=tempo={tempo}:transients=mixed:detector=compound:phase=laminar"
                    ":window=standard:pitchq=quality:channels=together",
                    "-c:a", "pcm_f32le", dst], check=True)


def quietest(x: np.ndarray, a: float, b: float, frame: float = 0.01) -> float:
    """Time (s) of the quietest 10 ms frame between a and b."""
    mono = x.mean(axis=1) if x.ndim > 1 else x
    i0, i1 = max(0, int(a * SR)), min(len(mono), int(b * SR))
    if i1 - i0 < int(frame * SR) * 2:
        return (a + b) / 2
    hop = int(frame * SR)
    e = [np.sqrt(np.mean(mono[i:i + hop] ** 2)) for i in range(i0, i1 - hop, hop // 2)]
    k = int(np.argmin(e))
    return (i0 + k * (hop // 2) + hop // 2) / SR


def main() -> None:
    args = sys.argv[1:]
    opts = {"--tempo": 0.92, "--gap-in": 0.6, "--gap-between": 1.15}
    for k in list(opts):
        if k in args:
            i = args.index(k); opts[k] = float(args[i + 1]); del args[i:i + 2]
    timing_p, voice_p, out_dir = args
    tempo, gap_in, gap_between = opts["--tempo"], opts["--gap-in"], opts["--gap-between"]
    os.makedirs(out_dir, exist_ok=True)
    timing = json.load(open(timing_p, encoding="utf-8"))
    vfs = timing["voice_film_start"]

    st_p = os.path.join(out_dir, "_stretched.wav")
    stretch(voice_p, st_p, tempo)
    y, sr = sf.read(st_p, dtype="float32", always_2d=True)
    assert sr == SR

    def s_of(t_film: float) -> float:  # old film time -> time in the stretched voice file
        return (t_film - vfs) / tempo

    H = timing["hemistichs"]
    keys = list(H)
    cuts = []  # (cut time in stretched file, inserted seconds, label)
    for a, b in zip(keys, keys[1:]):
        same_verse = a[:-1] == b[:-1]
        target = gap_in if same_verse else gap_between
        g0, g1 = s_of(H[a]["end"]), s_of(H[b]["start"])
        cur = g1 - g0
        c = quietest(y, g0 - 0.03, g1 + 0.03)
        cuts.append((c, max(0.0, target - cur), f"{a}->{b}", round(cur, 3), target))

    # Assemble: pieces of the stretched voice with silence inserted at each cut (8 ms fades).
    fade = int(0.008 * SR)
    pieces, prev = [], 0
    for c, ins, *_ in cuts:
        i = int(c * SR)
        seg = y[prev:i].copy()
        if prev > 0:
            seg[:fade] *= np.linspace(0, 1, fade)[:, None]
        seg[-fade:] *= np.linspace(1, 0, fade)[:, None]
        pieces += [seg, np.zeros((int(round(ins * SR)), y.shape[1]), np.float32)]
        prev = i
    last = y[prev:].copy()
    last[:fade] *= np.linspace(0, 1, fade)[:, None]
    pieces.append(last)
    out = np.concatenate(pieces)
    sf.write(os.path.join(out_dir, "voice_film_slow.wav"), out, SR, subtype="FLOAT")
    os.remove(st_p)

    cut_s = [c for c, *_ in cuts]
    ins_s = [x for _, x, *_ in cuts]

    def warp(t: float) -> float:
        if t <= vfs:
            return t
        s = s_of(t)
        return vfs + s + sum(x for c, x in zip(cut_s, ins_s) if c <= s)

    def warp_line(t: float, line_idx: int) -> float:
        """Map a time that belongs to hemistich `line_idx`: it receives exactly the inserts of the
        cuts before its line, and is clamped to its side of the neighbouring cuts (aligner word
        boundaries can sit a few ms past the quietest point where the silence went in)."""
        s = s_of(t)
        if line_idx > 0:
            s = max(s, cut_s[line_idx - 1])
        if line_idx < len(cut_s):
            s = min(s, cut_s[line_idx])
        return vfs + s + sum(ins_s[:line_idx])

    old_end = timing["voice_film_end"]
    shift_end = warp(old_end) - old_end
    new = copy.deepcopy(timing)
    for w in new["words"]:
        li = keys.index(w["line"])
        w["film_start"], w["film_end"] = round(warp_line(w["film_start"], li), 3), round(warp_line(w["film_end"], li), 3)
    for li, (k, h) in enumerate(new["hemistichs"].items()):
        h["start"], h["end"] = round(warp_line(h["start"], li), 3), round(warp_line(h["end"], li), 3)
    new["voice_film_end"] = round(warp(old_end), 3)
    new["duration"] = round(timing["duration"] + shift_end, 3)
    new["repace"] = {"tempo": tempo, "gap_in": gap_in, "gap_between": gap_between,
                     "inserted": [{"between": lab, "gap_before_s": cur, "target_s": tgt, "inserted_s": round(x, 3)}
                                  for _, x, lab, cur, tgt in cuts],
                     "note": "word 'start'/'end' remain source times of the ORIGINAL isolated voice; film times are re-paced"}
    knots = [(0.0, 0.0), (vfs, vfs)]
    for c, x in zip(cut_s, ins_s):
        t_old = vfs + c * tempo
        knots += [(t_old, warp(t_old - 1e-6)), (t_old + 1e-6, warp(t_old + 1e-6))]
    knots += [(old_end, warp(old_end)), (timing["duration"], timing["duration"] + shift_end)]
    new["warp"] = [[round(a, 4), round(b, 4)] for a, b in knots]
    json.dump(new, open(os.path.join(out_dir, "timing_slow.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"old_voice_span": round(old_end - vfs, 2), "new_voice_span": round(new["voice_film_end"] - vfs, 2),
                      "old_duration": timing["duration"], "new_duration": new["duration"],
                      "inserted_total": round(sum(ins_s), 2)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
