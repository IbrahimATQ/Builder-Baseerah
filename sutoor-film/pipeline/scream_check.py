#!/usr/bin/env python3
"""Check that nothing but the reciter's own voice carries a human voice in the final mix.

The mix is premaster = voice_bus + everything else (music, ambience, sound effects). The "everything
else" part is recovered exactly as premaster - voice_bus, then:
  1. a vocal-separation model (Mel-RoFormer) pulls any voice-like sound out of it;
  2. that stem's loudness is measured per 0.4 s window (a scream or cry would stand out);
  3. a pitch tracker (pYIN) counts voiced frames in it (a cry is strongly pitched).
Also run on the voice bus alone with the karaoke model, which splits a lead voice from any
backing voice: the backing part must be near silence.

Usage: python scream_check.py MIX_DIR OUT.json   (MIX_DIR holds mix_premaster.wav and voice_bus.wav)
PASS when: residual vocal stem max short-term < -42 LUFS and voiced frames < 2 %, and the voice bus's
backing stem integrated < -50 LUFS.
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
import pyloudnorm as pyln
import soundfile as sf

MODELS = "/home/user/film/sep/models"
SEP = "/home/user/film/venv/bin/audio-separator"


def separate(wav: str, model: str, out_dir: str) -> dict[str, str]:
    env = dict(os.environ, HF_HUB_DISABLE_XET="1")
    subprocess.run([SEP, wav, "-m", model, "--model_file_dir", MODELS, "--output_dir", out_dir, "--output_format", "WAV"],
                   check=True, capture_output=True, env=env)
    stem = os.path.splitext(os.path.basename(wav))[0]
    out = {}
    for f in glob.glob(os.path.join(out_dir, stem + "*")):
        tag = f.rsplit("(", 1)[-1].split(")")[0].lower() if "(" in f else "?"
        out[tag] = f
    return out


def short_term(y: np.ndarray, sr: int, win: float = 0.4) -> list[float]:
    meter = pyln.Meter(sr, block_size=win)
    hop = int(win * sr)
    vals = []
    for i in range(0, len(y) - hop, hop):
        seg = y[i:i + hop]
        v = meter.integrated_loudness(seg) if np.any(np.abs(seg) > 1e-6) else -90.0
        vals.append(v if np.isfinite(v) else -90.0)
    return vals


def main(mix_dir: str, out_p: str) -> None:
    pre, sr = sf.read(os.path.join(mix_dir, "mix_premaster.wav"), always_2d=True)
    vb, sr2 = sf.read(os.path.join(mix_dir, "voice_bus.wav"), always_2d=True)
    assert sr == sr2
    n = min(len(pre), len(vb))
    residual = pre[:n] - vb[:n]
    tmp = tempfile.mkdtemp(prefix="scream_", dir=os.path.dirname(os.path.abspath(out_p)))
    res_p = os.path.join(tmp, "residual.wav")
    sf.write(res_p, residual, sr, subtype="FLOAT")
    rep: dict = {}

    stems = separate(res_p, "vocals_mel_band_roformer.ckpt", tmp)
    voc_p = stems.get("vocals") or next(v for k, v in stems.items() if "vocal" in k)
    voc, vsr = sf.read(voc_p, always_2d=True)
    st = short_term(voc.mean(axis=1), vsr)
    worst = int(np.argmax(st))
    import librosa
    mono = librosa.resample(voc.mean(axis=1).astype(np.float32), orig_sr=vsr, target_sr=16000)
    f0, vflag, vprob = librosa.pyin(mono, fmin=80, fmax=1000, sr=16000, frame_length=1024)
    loud = librosa.feature.rms(y=mono, frame_length=1024, hop_length=256)[0][: len(vflag)]
    audible = loud > 10 ** (-50 / 20)
    voiced_frac = float(np.mean(vflag[: len(audible)] & audible)) if len(vflag) else 0.0
    rep["residual_vocal_stem"] = {"max_short_term_lufs": round(max(st), 1), "at_s": round(worst * 0.4, 1),
                                  "voiced_audible_fraction": round(voiced_frac, 4)}

    vb_p = os.path.join(tmp, "voice_bus.wav")
    sf.write(vb_p, vb, sr, subtype="FLOAT")
    k = separate(vb_p, "mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt", tmp)
    back_p = k.get("instrumental") or next(v for kk, v in k.items() if "instr" in kk or "back" in kk)
    back, bsr = sf.read(back_p, always_2d=True)
    meter = pyln.Meter(bsr)
    bl = meter.integrated_loudness(back)
    rep["voice_bus_backing_stem"] = {"integrated_lufs": round(float(bl), 1) if np.isfinite(bl) else -90.0,
                                     "max_short_term_lufs": round(max(short_term(back.mean(axis=1), bsr)), 1)}
    ok = (rep["residual_vocal_stem"]["max_short_term_lufs"] < -42 and voiced_frac < 0.02
          and rep["voice_bus_backing_stem"]["integrated_lufs"] < -50)
    rep["verdict"] = "PASS" if ok else "FAIL"
    json.dump(rep, open(out_p, "w"), indent=1)
    print(json.dumps(rep, indent=1))
    for f in glob.glob(os.path.join(tmp, "*")):
        os.remove(f)
    os.rmdir(tmp)


if __name__ == "__main__":
    main(*sys.argv[1:3])
