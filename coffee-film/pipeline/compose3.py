#!/usr/bin/env python3
"""Original score for "WARSZAWA" (the window), rendered offline from real sampled instruments.

Usage:
    python pipeline/compose3.py [CUESHEET.json] [OUT_DIR]
        defaults: data/cuesheet3.json  /home/user/coffee/score3

Every film time comes from the cue sheet at run time (events by key, shot film_in times, duration), so when the
picture editor nudges a cut a re-run follows it. Writes, in OUT_DIR:
    organ.wav strings.wav brass.wav perc.wav   stems (24-bit; they sum exactly, sample for sample, to music.wav)
    music.wav                                  48 kHz / 24-bit / stereo, exactly the cue-sheet duration, -16 LUFS,
                                               true peak <= -2 dBTP
    score_report.json                          key, tempo map, bar-by-bar description with film times, locked
                                               arrivals with measured onset errors, tuning per instrument,
                                               per-section loudness, QC
    spectrogram.png  latch.png                 the whole piece with the events marked; zoom on the dead stop

THE MUSIC (nothing quoted or imitated from any existing score)
One theme, D minor, 3/4, rubato to the picture: four rising notes answered by a falling step,
    D - E - F - Bb | A      (dotted quarter, eighth, quarter | half ... quarter)
the leap to the minor sixth (Bb) falling a semitone to the fifth (A) is the sigh the whole film waits to resolve.
The kitchen (fade_up..latch) is placed at a distance: long church room, soft top end, narrow image.
  - fade_up: 16' pedal D, ppp.  walk: 8' stopped-flute ostinato rocking D-A, the pulse of the ritual; its lift to
    Bb at every bar end foreshadows the theme's sigh. The organ breathes before every arrival, and his first step
    and each look land on a soft low pizzicato of the new bass note (walk, rise1, look1, spout_out, pullback, look2).
  - church_in..look1: con-sordino violas and celli rise Dm -> Bb (rise1) -> F major (look1, first light);
    they drop away on the kettle click.
  - stream: the celli state the theme (D3) through the slow motion; Gm -> A (half close on spout_out);
    pullback: the violins take it an octave higher (D4 + D5), organ adds its principal; the peak Bb lands on look2.
  - cup: subito pp, the ostinato stops: a high solo-violin harmonic A6 and the pedal only.
  - pour: the solo horn sings the theme (D3) over the resumed ostinato; Bb -> Gm crescendo, the horn becomes a
    section, the violins join the rising line G-A-Bb, timpani roll on A from server_out; bell2: A sus4 forte with D
    on top (the theme's peak again) - held, pressing (semiquaver ostinato, tremolo) - and never resolved:
  - latch: DEAD STOP (hard gate on the indoor buses, reverb included). 2.6 s with no music: the city floods in,
    the bell's D answers the held A.
  - latch+2.6: the organ returns at full registration in D MAJOR (the first F sharp of the film), full strings,
    the theme at half tempo; descending bass D C# B | G (street, after a timpani roll under the pilaster) F# E |
    A -> rising string run under his turn -> D on the cut to the square.
  - square..climax: horns and trombones take the theme over full organ, f -> ff, cadence D Bm G A -> D; the four
    rising notes G-A-B -> E fall to the sus4 D over A and this time resolve through C# into D at the climax.
  - climax..end: brass out after 2 s, strings fade, the organ alone; the high flute sings the theme once more in
    major (D E F# B | A): B over G/D on title_in (a plagal amen), the falling step A over the last D-major chord;
    bell4 rings inside it (nothing between 300 and 900 Hz); the chord is released on 'end'.
Outdoors (after the latch) the music is close, full range and wide (short hall, more direct sound).

Instruments: VSCO-2 Community Edition (CC0): pipe organ (S. Dalzell / Ivy Audio: Man III open plenum, Man III
stopped flute at 16'/8'/4', pedal 16' + 8', a 32' resultant from 16' + 10 2/3'), violin/viola/cello sections
(sustain, tremolo, spiccato), solo contrabass, solo violin, F horn (one take per note, made into a section by
layering velocity layers with small detunes and offsets), tenor trombone, the 1950s Olds trombone (two takes),
timpani (hits and rolls). No piano, harp, pads, synths, chimes or ticking.
The sampling engine is pipeline/compose.py (imported, unchanged): sample calibration (measured pitch, level,
onset), A=440 equal-temperament pitch correction by polyphase resampling, loop extension, church reverb,
mastering and analysis helpers.  Deterministic.
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "2"

import json
import sys
import time

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy.ndimage import uniform_filter1d
from scipy.signal import butter, fftconvolve, sosfilt, sosfiltfilt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compose as C  # noqa: E402  (the previous film's engine, reused as a library)
from compose import N, NAME, SR, VSCO, Inst, _files, hz, dbv, log, raised_cos, render_note  # noqa: E402

DEFAULT_CUE = os.path.join(os.path.dirname(HERE), "data", "cuesheet3.json")
DEFAULT_OUT = "/home/user/coffee/score3"
STEMS = ("organ", "strings", "brass", "perc")
T_START = time.time()


# ============================================================================= the contract
class Cue:
    """Film times by key, read from the cue sheet (events, shot film_in times, duration) plus a few derived cues."""

    NEED = ("fade_up", "walk", "church_in", "rise1", "look1", "kettle_click", "stream", "spout_out", "pullback",
            "look2", "pour", "slow2_end", "server_out", "bell2", "latch", "pilaster1", "street", "turn_away",
            "climax", "title_in", "bell4", "end")

    def __init__(self, path):
        d = json.load(open(path, encoding="utf-8"))
        self.path = path
        self.duration = float(d["duration"])
        self.ev = {e["key"]: float(e["t"]) for e in d["events"]}
        self.what = {e["key"]: e.get("what", "") for e in d["events"]}
        shots = {s["id"]: s for s in d["shots"]}
        missing = [k for k in self.NEED if k not in self.ev] + [s for s in ("cup", "square") if s not in shots]
        if missing:
            raise KeyError(f"cue sheet {path} lacks {missing}")
        self.ev["cup_cut"] = float(shots["cup"]["film_in"])
        self.ev["square_cut"] = float(shots["square"]["film_in"])
        self.ev["return"] = self.ev["latch"] + 2.6           # the music comes back 2.6 s after the latch
        self.ev["last_chord"] = self.ev["bell4"] - 0.7       # the last chord is in place before bell 4 rings
        self.what.update(cup_cut="cut to the empty WARSZAWA mug (shot 'cup' film_in)",
                         square_cut="cut to his other window (shot 'square' film_in)",
                         **{"return": "latch + 2.6 s: the music returns", "last_chord": "bell4 - 0.7 s"})
        self.shots = shots
        self.events = d["events"]

    def __getitem__(self, k):
        return self.ev[k]


class TempoMap:
    """Beat -> film time. Hard anchors (beat, cue key) put beats exactly on events; between two anchors the beats
    are spaced by a tempo that ramps from the mean of the previous segment to the mean of the next one, scaled to
    fit (rubato); `stretch` lengthens single beats (agogic accents, the allargando into an arrival)."""

    def __init__(self, name, anchors, cue, stretch=None):
        self.name = name
        self.anchors = [(int(b), key, float(cue[key])) for b, key in anchors]
        bs = np.array([a[0] for a in self.anchors])
        ts = np.array([a[2] for a in self.anchors])
        if np.any(np.diff(bs) <= 0) or np.any(np.diff(ts) <= 0):
            raise ValueError(f"tempo map {name}: anchors out of order {self.anchors}")
        L = np.diff(ts) / np.diff(bs)
        edge = np.concatenate([[L[0]], 0.5 * (L[:-1] + L[1:]), [L[-1]]])
        stretch = stretch or {}
        durs = []
        for k in range(len(L)):
            n = int(bs[k + 1] - bs[k])
            raw = np.array([edge[k] + (edge[k + 1] - edge[k]) * (i + 0.5) / n for i in range(n)])
            raw *= np.array([stretch.get(int(bs[k]) + i, 1.0) for i in range(n)])
            raw *= (ts[k + 1] - ts[k]) / raw.sum()
            durs.extend(raw.tolist())
        self.b0, self.b1 = int(bs[0]), int(bs[-1])
        self.durs = np.array(durs)
        self.beat_t = ts[0] + np.concatenate([[0.0], np.cumsum(self.durs)])
        self.seg_bpm = [dict(from_key=self.anchors[k][1], to_key=self.anchors[k + 1][1],
                             beats=int(bs[k + 1] - bs[k]), seconds=round(float(ts[k + 1] - ts[k]), 3),
                             mean_bpm=round(60.0 / float(L[k]), 1)) for k in range(len(L))]

    def t(self, b):
        b = float(b)
        if b <= self.b0:
            return float(self.beat_t[0] + (b - self.b0) * self.durs[0])
        if b >= self.b1:
            return float(self.beat_t[-1] + (b - self.b1) * self.durs[-1])
        i = int(np.floor(b - self.b0))
        return float(self.beat_t[i] + (b - self.b0 - i) * self.durs[i])

    def bpm(self, b):
        i = int(np.clip(np.floor(b - self.b0), 0, len(self.durs) - 1))
        return 60.0 / float(self.durs[i])

    def describe(self):
        return dict(name=self.name, anchors=[dict(beat=b, key=k, t=round(t, 3)) for b, k, t in self.anchors],
                    segments=self.seg_bpm,
                    beat_bpm_range=[round(float(60 / self.durs.max()), 1), round(float(60 / self.durs.min()), 1)],
                    beats_s=[round(float(x), 3) for x in self.beat_t])


# ============================================================================= instruments
def build_library3():
    """compose.py's organ / strings / timpani, plus brass, solo violin and string spiccato (same calibration)."""
    lib = C.build_library()
    nre = r"([A-G]#?-?\d)"
    up = lambda m: N(m.group(1)) + 12   # noqa: E731  VSCO names brass/woodwinds/sections one octave low (measured)
    lay = lambda m: int(m.group(2))     # noqa: E731
    lib["horn"] = Inst("horn", _files("Brass/F Horn/sus/*.wav", rf"MOHorn_sus_{nre}_v(\d)_1\.wav$", up, lay))
    lib["otbn"] = Inst("otbn", _files("Brass/OldTrombone/Sustain/*_1.wav", rf"Trombone_Sustain_{nre}_v(\d)_1\.wav$", up, lay))
    lib["otbn2"] = Inst("otbn2", _files("Brass/OldTrombone/Sustain/*_2.wav", rf"Trombone_Sustain_{nre}_v(\d)_2\.wav$", up, lay))
    lib["tbn"] = Inst("tbn", _files("Brass/Tenor Trombone/sus/*.wav", rf"tenortbn_sus_{nre}_v(\d)_1\.wav$", up, lay))
    lib["svln"] = Inst("svln", _files("Strings/Solo Violin/Arco Vib/*.wav", rf"LLVln_ArcoVib_{nre}_(p|f)\.wav$",
                                      lambda m: N(m.group(1)), lambda m: 1 if m.group(2) == "p" else 2))
    rr = lambda m: int(m.group(3))      # noqa: E731
    lib["vln_spic"] = Inst("vln_spic", _files("Strings/Violin Section/Spic/*.wav", rf"VlnEns_Spic_{nre}_v(\d)_rr(\d)\.wav$",
                                              up, lay, rr), kind="pluck", kmax=6)
    lib["va_spic"] = Inst("va_spic", _files("Strings/Viola Section/spic/*.wav", rf"Violas_spic_{nre}_v(\d)_rr(\d)\.wav$",
                                            up, lay, rr), kind="pluck", kmax=6)
    lib["vc_spic"] = Inst("vc_spic", _files("Strings/Cello Section/spic/*.wav", rf"^spic_{nre}_v(\d)_RR(\d)\.wav$",
                                            up, lay, rr), kind="pluck", kmax=6)
    lib["cb_pizz"] = Inst("cb_pizz", _files("Strings/Solo Contrabass/Pizz/*.wav", rf"BKCtbss_Pizz_{nre}_v(\d)_rr(\d)\.wav$",
                                            up, lay, rr), kind="pluck", kmax=6)
    lib["vc_pizz"] = Inst("vc_pizz", _files("Strings/Cello Section/pizzT/*.wav", rf"^pizzT_{nre}_v(\d)_RR(\d)\.wav$",
                                            up, lay, rr), kind="pluck", kmax=6)
    return lib


TIMP_REF = {}   # loudness offset that brings a layer-4 timpani hit (raw level, not normalised) to -20 LUFS
SPIC_WIN = (0.01, 0.22)      # pitch window of a spiccato note (s after its attack point)
PLUCK_WIN = {"cb_pizz": (0.03, 0.6), "vc_pizz": (0.03, 0.6)}   # pizzicato rings longer
ROLL_WIN = (0.5, 6.0)        # pitch window of a timpani roll (s after its onset)


def refine_calibration(lib, names):
    """compose.Inst measures a 'pluck' over att+0.05..1.2 s and a timpani over 0.12..1.8 s; a spiccato note lasts
    ~0.3 s and a roll swells for seconds, so their pitch is re-measured here on windows that fit them (the same
    windows the tuning test uses). compose.py itself is not changed."""
    out = {}
    for name in names:
        inst = lib[name]
        if not inst.ready:
            continue
        rows = []
        for smp in inst.samples:
            x, sr = C.load(smp.path)
            xm = (x[:, smp.mono] if smp.mono >= 0 else x.mean(1)).astype(np.float64)
            old = smp.meas
            if inst.kind == "pluck":
                w0, w1 = PLUCK_WIN.get(name, SPIC_WIN)
                seg = xm[smp.att + int(w0 * sr): smp.att + int(w1 * sr)]
                smp.meas = float(C.midi_of(C.harmonic_f0(seg, sr, hz(smp.nominal), 6)))
            else:
                smp.meas = float(C.midi_of(C.timp_principal(xm, sr, *ROLL_WIN)))
            rows.append((os.path.basename(smp.path), round(old, 3), round(smp.meas, 3)))
        out[name] = rows
    return out


# ============================================================================= score
class Score:
    def __init__(self, cue):
        self.cue = cue
        self.E: list[dict] = []
        self.locks: list[dict] = []
        self.bars: list[dict] = []

    def note(self, stem, inst, pitch, t, dur, g=0.0, pan=0.0, space="in", **kw):
        m = float(N(pitch)) if isinstance(pitch, str) else float(pitch)
        e = dict(stem=stem, inst=inst, midi=m, t=float(t), dur=max(float(dur), 0.02), g=float(g), pan=float(pan),
                 space=space, **kw)
        self.E.append(e)
        return e

    def lock(self, key, kind, stem, what, t=None, off=0.0):
        self.locks.append(dict(key=key, t=float(self.cue[key] if t is None else t) + off, kind=kind, stem=stem,
                               what=what, offset_s=off))

    def bar(self, n, tm, beat, meter, harmony, melody, what):
        self.bars.append(dict(bar=n, map=tm.name if tm else None, beat=beat, t=round(tm.t(beat), 3) if tm else beat,
                              meter=meter, harmony=harmony, melody=melody, what=what))

    def chords(self, stem, inst, seq, t_end, g=0.0, space="in", pan=(-0.45, 0.45), attack=0.05, release=0.25,
               overlap=0.03, layer=None, env=None, role="chord", **kw):
        """seq = [(t, [pitches]), ...]; each chord lasts until the next; common tones are held (tied)."""
        times = [s[0] for s in seq] + [t_end]
        sets = [[N(p) if isinstance(p, str) else p for p in s[1]] for s in seq]
        allp = sorted({p for s in sets for p in s})
        lo, hi = min(allp), max(allp)
        for p in allp:
            i = 0
            while i < len(sets):
                if p in sets[i]:
                    j = i
                    while j + 1 < len(sets) and p in sets[j + 1]:
                        j += 1
                    pn = pan[0] + (pan[1] - pan[0]) * ((p - lo) / max(hi - lo, 1))
                    self.note(stem, inst, p, times[i], times[j + 1] - times[i] + overlap, g, pn, space, attack=attack,
                              release=release, layer=layer, env=env, role=role, **kw)
                    i = j + 1
                else:
                    i += 1

    def line(self, stem, inst, notes, tm, b0, g=0.0, pan=0.0, space="in", layer=None, attack=0.06, release=0.22,
             overlap=0.07, gains=None, env=None, role="melody", first=None, last_end=None, **kw):
        """A legato line: notes = [(pitch or None, beats), ...] from beat b0 of tempo map tm."""
        b = b0
        out = []
        for i, (p, d) in enumerate(notes):
            t0, t1 = tm.t(b), tm.t(b + d)
            if p is not None:
                last = i == len(notes) - 1
                end = last_end if (last and last_end is not None) else t1 + overlap
                kw2 = dict(kw)
                if i == 0 and first:
                    kw2.update(first)
                a = kw2.pop("attack", attack)
                e = self.note(stem, inst, p, t0, end - t0, g + (gains[i] if gains else 0.0), pan, space, layer=layer,
                              attack=a, release=release, env=env, role=role, **kw2)
                out.append(e)
            b += d
        return out


def rock(S, tm, b0, b1, lo, hi, nb, g0, g1, sub=2, inst="ged", space="in", oct_=0, stop_t=None, g_add=0.0,
         pan=0.2, role="ostinato", bars=(), arrivals=(), legato=0.82):
    """The ritual's pulse: lo/hi alternating in quavers (sub=2) or semiquavers (sub=4) from beat b0 to b1;
    `nb` replaces the last note of a group (the lift); beat 1 of a bar is accented, the upper note softer."""
    n = int(round((b1 - b0) * sub))
    for k in range(n):
        b = b0 + k / sub
        t = tm.t(b)
        if stop_t is not None and t >= stop_t:
            break
        step = tm.t(b + 1.0 / sub) - t
        p = lo if k % 2 == 0 else hi
        if nb and k == n - 1:
            p = nb
        g = g0 + (g1 - g0) * k / max(n - 1, 1) + g_add
        if k % 2:
            g -= 1.8
        if abs(b - round(b)) < 1e-6 and int(round(b)) in bars:
            g += 1.2
        frac = legato
        if any(0.0 < a - (t + step) < 0.004 or abs(a - (t + step)) < 0.004 for a in arrivals):
            frac = 0.6      # an organist's breath before the arrival
        S.note("organ", inst, N(p) + oct_, t, step * frac, g, pan if k % 2 else -pan, space, attack=0.004,
               release=0.04, role=role)


HORN_COPIES = [dict(dl=0, det=0.0, dt=0.000, dp=0.00, g=0.0),      # the solo horn
               dict(dl=-1, det=-5.0, dt=0.016, dp=0.14, g=-1.0),   # 2nd
               dict(dl=+1, det=+4.0, dt=0.008, dp=-0.12, g=-1.5),  # 3rd
               dict(dl=0, det=-2.5, dt=0.023, dp=0.24, g=-2.0)]    # 4th


def horns(S, notes, tm, b0, g, layer, pan=-0.22, space="in", n_from=1, n_to=4, grow=None, env=None, role="horns",
          **kw):
    """A horn line played by `n_to` players: copies of the line from different velocity layers, slightly detuned
    (<= 5 cents) and late (<= 23 ms), spread in pan; players n_from+1..n_to fade in with `grow` (dB env)."""
    for i, c in enumerate(HORN_COPIES[:n_to]):
        if i < n_from or grow is None:
            e_env = env
        elif env is None:
            e_env = grow
        else:
            e_env = (lambda tt, a=env, b=grow: a(tt) * b(tt))
        for e in S.line("brass", "horn", notes, tm, b0, g + c["g"], pan + c["dp"], space, layer=max(1, layer + c["dl"]),
                        env=e_env, role=role if i else role + " (lead)", **kw):
            e["t"] += c["dt"] if i else 0.0
            e["detune"] = c["det"]


def kitchen(S: Score, cue: Cue):
    """Bars 1-14: fade_up .. latch, indoors."""
    K = TempoMap("kitchen", [(0, "walk"), (6, "rise1"), (7, "look1"), (12, "stream"), (20, "spout_out"),
                             (21, "pullback"), (24, "look2"), (26, "cup_cut"), (30, "pour"), (39, "bell2")], cue,
                 stretch={38: 1.12, 19: 1.06})
    t = K.t
    sp = "in"
    latch = cue["latch"]
    ramp = C.ramp
    KB = {0, 3, 6, 9, 12, 15, 18, 21, 24, 26, 30, 33, 36, 39}

    # ---------------------------------------------------------------- pedal (16' + 8'), with the bass line
    ped = [(cue["fade_up"], "D", -24), (t(6), "Bb", -21), (t(7), "F", -20), (t(11), "A", -20), (t(12), "D", -18),
           (t(15), "Bb", -18), (t(18), "G", -17), (t(20), "A", -16), (t(21), "D", -15), (t(24), "Bb", -14),
           (cue["cup_cut"], "D", -23), (t(33), "Bb", -17), (t(36), "G", -14), (t(39), "A", -9)]
    for i, (t0, pc, g) in enumerate(ped):
        t1 = ped[i + 1][0] if i + 1 < len(ped) else latch + 0.05
        first = i == 0
        kw = dict(skip=1.0, attack=0.002, env=ramp([(cue["fade_up"], -45), (cue["walk"], 0)])) if first else \
            dict(attack=0.06 if t0 != cue["cup_cut"] else 0.25)
        if t0 == t(39):
            kw["env"] = ramp([(t(39), 0), (latch, 3)])
        if t0 == cue["cup_cut"]:   # ppp over the empty mug, back to p under the horn
            kw["env"] = ramp([(t0, 0), (cue["pour"] - 0.2, 0), (cue["pour"] + 1.0, 6)])
        legato = 0.0 if t1 == cue["cup_cut"] else 0.05
        S.note("organ", "ped16", pc + "1", t0, t1 - t0 + legato, g, 0.0, sp, release=0.12 if legato else 0.05,
               role="pedal 16'", **kw)
        S.note("organ", "ped8", pc + "2", t0, t1 - t0 + legato, g - 5, 0.0, sp, release=0.12 if legato else 0.05,
               role="pedal 8'", **kw)
    # a 16' Bourdon (stopped flute an octave down) under the theme's bars
    S.lock("fade_up", "start", "organ", "16' pedal D enters ppp (felt more than heard)")

    # ---------------------------------------------------------------- the ostinato (8' stopped flute)
    O = [  # b0, b1, lo, hi, lift, g0, g1, sub
        (0, 3, "D4", "A4", "Bb4", -16, -15, 2), (3, 6, "D4", "A4", "Bb4", -15, -14, 2),
        (6, 7, "D4", "Bb4", None, -13.5, -13.5, 2), (7, 9, "C4", "A4", "Bb4", -12.5, -12.5, 2),
        (9, 11, "C4", "A4", None, -13, -13.5, 2), (11, 12, "E4", "A4", None, -13.5, -13.5, 2),
        (12, 15, "D4", "A4", "Bb4", -13.5, -13, 2), (15, 17, "D4", "Bb4", None, -13, -13, 2),
        (17, 18, "D4", "A4", None, -13, -13, 2), (18, 20, "D4", "Bb4", None, -13, -12.5, 2),
        (20, 21, "E4", "A4", None, -12.5, -12, 2), (21, 24, "D4", "A4", "Bb4", -12, -10.5, 2),
        (24, 25, "D4", "Bb4", None, -10, -10, 2), (25, 26, "D4", "A4", None, -10, -10, 2),
        (30, 33, "D4", "A4", "Bb4", -14, -13, 2), (33, 35, "D4", "Bb4", None, -13, -12, 2),
        (35, 36, "D4", "A4", None, -12, -11.5, 2), (36, 39, "D4", "Bb4", None, -11, -8.5, 2),
        (39, 44, "D4", "A4", None, -7.5, -4.5, 4)]
    arr = [cue[k] for k in ("walk", "rise1", "look1", "stream", "spout_out", "pullback", "look2", "pour")]
    for b0, b1, lo, hi, nb, g0, g1, sub in O:
        rock(S, K, b0, b1, lo, hi, nb, g0, g1, sub, space=sp, stop_t=latch, bars=KB, arrivals=arr)
        if b0 >= 12 and b1 <= 26:   # the 16' Bourdon joins under the theme
            rock(S, K, b0, b1, lo, hi, nb, g0 - 9, g1 - 9, sub, space=sp, oct_=-12, pan=0.1, role="ostinato 16'",
                 bars=KB, arrivals=arr)
        if b0 >= 36:                # 4' flute brightens the crescendo
            rock(S, K, b0, b1, lo, hi, None, g0 - 9, g1 - 6, sub, space=sp, oct_=12, pan=0.3, stop_t=latch,
                 role="ostinato 4'", bars=KB, arrivals=arr)
    for key, pc in (("walk", "D"), ("rise1", "Bb"), ("look1", "F"), ("spout_out", "A"), ("pullback", "D"),
                    ("look2", "Bb")):
        S.note("strings", "cb_pizz", pc + "1" if pc in ("Bb", "A", "F") else pc + "2", cue[key], 1.2, -11, 0.45, sp,
               layer=1, attack=0.002, release=0.3, role="pizzicato (the look lands)")
        S.note("strings", "vc_pizz", pc + "2" if pc in ("Bb", "A", "F") else pc + "3", cue[key], 1.0, -15, 0.35, sp,
               layer=1, attack=0.002, release=0.3, role="pizzicato (the look lands)")
    S.lock("walk", "onset", "strings", "his first step: the ostinato begins, a soft low pizzicato D")
    S.lock("rise1", "onset", "strings", "Bb: the violas rise A3->Bb3, ostinato D-Bb, pedal Bb")
    S.lock("look1", "onset", "strings", "F major, first light: violas C4, celli C3 A3, violins A4 C5")

    # ---------------------------------------------------------------- con-sordino strings: Dm -> Bb -> F
    kc = cue["kettle_click"]
    ci, r1, l1 = cue["church_in"], t(6), t(7)
    swell = ramp([(ci, -6), (r1, -1), (l1, 1.5), (kc - 0.6, 0.5), (kc, -1)])
    st = dict(space=sp, layer=1, fx="sord", env=swell, role="strings (sord.)")
    S.note("strings", "vc_sus", "D3", ci, l1 - ci + 0.12, -14, 0.35, attack=1.7, release=0.3, **st)
    S.note("strings", "vc_sus", "F3", ci, l1 - ci + 0.12, -15, 0.3, attack=1.7, release=0.3, **st)
    S.note("strings", "va_sus", "A3", ci, r1 - ci + 0.1, -15, 0.15, attack=1.7, release=0.25, **st)
    S.note("strings", "va_sus", "Bb3", r1, l1 - r1 + 0.1, -14.5, 0.15, attack=0.18, release=0.25, **st)
    for inst, p, g, pan in (("va_sus", "C4", -14, 0.15), ("vc_sus", "C3", -14.5, 0.35), ("vc_sus", "A3", -15, 0.3),
                            ("vln_sus", "A4", -20, -0.3), ("vln_sus", "C5", -21, -0.4)):
        S.note("strings", inst, p, l1, kc - l1, g, pan, attack=0.16 if inst != "vln_sus" else 0.7, release=0.07,
               **st)
    S.lock("kettle_click", "release", "strings", "the strings drop away (bows off 0.07 s after the click, room tail "
                                                  "cut down with them; the ostinato goes on)")

    # ---------------------------------------------------------------- stream: the theme in the celli
    S.line("strings", "vc_sus", [("D3", 1.5), ("E3", 0.5), ("F3", 1), ("Bb3", 2), ("A3", 1), ("G3", 1.5), ("F3", 0.5),
                                 ("E3", 1)], K, 12, -8.0, 0.3, sp, layer=3, attack=0.08, release=0.25,
           gains=[0, -0.8, 0, 1.2, -0.3, 0.4, -0.8, -0.2], first=dict(attack=0.02), role="theme (celli)")
    S.lock("stream", "onset", "strings", "the celli begin the theme as the water touches the coffee")
    vla = dict(space=sp, layer=1, fx="sord", role="violas (inner)")
    S.line("strings", "va_sus", [("A3", 3), ("D4", 3), ("Bb3", 2), ("A3", 1)], K, 12, -17, 0.15, attack=0.3,
           release=0.3, overlap=0.1, **vla)
    S.lock("spout_out", "onset", "strings", "half close on A (pizzicato A, cello E3, ostinato E-A, pedal A)")
    # pullback: the violins take the theme an octave higher (vln2 D4, vln1 D5); celli and violas carry the harmony
    vth = [("D", 1.5), ("E", 0.5), ("F", 1), ("Bb", 1), ("A", 1)]
    cup = cue["cup_cut"]
    S.line("strings", "vln_sus", [(p + "5", d) for p, d in vth], K, 21, -8.5, -0.42, sp, layer=1, attack=0.07,
           release=0.05, gains=[0, -0.5, 0.5, 2.0, 1.0], first=dict(attack=0.02), last_end=cup,
           env=ramp([(t(21), -2), (t(24), 1.5)]), role="theme (violins I)")
    S.line("strings", "vln_sus", [(p + "4", d) for p, d in vth], K, 21, -12, -0.2, sp, layer=1, attack=0.07,
           release=0.05, gains=[0, -0.5, 0.5, 2.0, 1.0], first=dict(attack=0.02), last_end=cup,
           env=ramp([(t(21), -2), (t(24), 1.5)]), role="theme (violins II)")
    for inst, seq, g, pan in (("vc_sus", [("D3", 3), ("Bb2", 2)], -12, 0.35), ("vc_sus", [("A3", 3), ("F3", 2)], -13, 0.3),
                              ("va_sus", [("F3", 3), ("D4", 2)], -15, 0.15)):
        S.line("strings", inst, seq, K, 21, g, pan, sp, layer=1, attack=0.12, release=0.05, last_end=cup,
               role="harmony")
    # the organ adds its principal (the open rank, swell box nearly closed) from the spout's withdrawal
    S.chords("organ", "open", [(t(20), ["E3", "A3", "E4"]), (t(21), ["A3", "D4", "F4"]), (t(24), ["Bb3", "D4", "F4"])],
             cup, -16, sp, attack=0.12, release=0.05, env=ramp([(t(20), -9), (t(24), 0)]), role="principal 8'")
    S.lock("pullback", "onset", "strings", "Dm: violins begin the theme an octave higher as he straightens")
    S.lock("look2", "onset", "strings", "Bb: the theme's peak (violins Bb5/Bb4), mp")

    # ---------------------------------------------------------------- cup: subito pp, harmonic + pedal only
    pour = cue["pour"]
    S.note("strings", "svln", "A6", cup, pour - cup + 1.4, -12, -0.3, sp, layer=1, attack=0.03, release=0.9,
           fx="harm", env=ramp([(cup, 0), (pour, 0), (pour + 1.4, -14)]), role="solo violin harmonic")
    S.lock("cup_cut", "release", "organ", "subito pp: the ostinato and the violins stop on the cut")

    # ---------------------------------------------------------------- pour: the solo horn sings the theme
    S.lock("pour", "onset", "brass", "the solo horn begins the theme, the ostinato resumes")
    bell2 = cue["bell2"]
    grow = ramp([(t(36), -18), (t(38), -6), (t(39), 0)])
    horns(S, [("D3", 1.5), ("E3", 0.5), ("F3", 1), ("Bb3", 2), ("A3", 1), ("G3", 1.5), ("A3", 0.5), ("Bb3", 1)],
          K, 30, -6.5, 2, space=sp, n_from=1, n_to=4, grow=grow, attack=0.06, release=0.18, overlap=0.06,
          gains=[0, -0.8, 0, 1.0, -0.5, 1.0, 1.5, 2.5], first=dict(attack=0.03), role="theme (horn)")
    pressing = ramp([(bell2, 0), (latch, 3.0)])
    horns(S, [("D4", 3)], K, 39, -3.0, 3, space=sp, n_to=4, attack=0.03, release=0.05, last_end=latch + 0.05,
          env=pressing, role="peak D (horns)")
    for inst, p, g, pan in (("otbn", "A2", -6, 0.3), ("otbn2", "E3", -7, 0.38), ("tbn", "A3", -7.5, 0.22),
                            ("otbn", "D4", -9, 0.3)):
        S.note("brass", inst, p, bell2, latch - bell2 + 0.05, g, pan, sp, layer=4, attack=0.03, release=0.05,
               env=pressing, role="trombones (A sus4)")
    # strings under the horn: soft at the pour, crescendo through Bb and Gm, A sus4 forte (tremolo) on bell2
    t30, t33, t36 = t(30), t(33), t(36)
    cres = ramp([(t30, -4), (t33, -2), (t36, 0), (bell2, 3)])
    for inst, seq, g, pan in (("vc_sus", [("D2", 3), ("Bb2", 3), ("G2", 3)], -14, 0.35),
                              ("vc_sus", [("A2", 3), ("F3", 3), ("D3", 3)], -15, 0.3),
                              ("va_sus", [("A3", 3), ("D4", 3), ("Bb3", 3)], -16, 0.15),
                              ("va_sus", [(None, 3), ("F3", 3), ("G3", 3)], -16.5, 0.15),
                              ("cb_sus", [(None, 3), ("Bb1", 3), ("G1", 3)], -15, 0.5)):
        S.line("strings", inst, seq, K, 30, g, pan, sp, layer=1, attack=0.25, release=0.2, overlap=0.08, env=cres,
               role="strings (pour)")
    for inst, oct_, g, pan in (("vln_sus", 5, -9, -0.42), ("vln_sus", 4, -11.5, -0.2)):
        S.line("strings", inst, [(f"G{oct_}", 1.5), (f"A{oct_}", 0.5), (f"Bb{oct_}", 1)], K, 36, g, pan, sp, layer=2,
               attack=0.12, release=0.12, gains=[0, 1, 2.5], env=ramp([(t36, -5), (bell2, 0)]),
               role="rising line (violins)")
    trem = dict(space=sp, attack=0.04, release=0.05, env=pressing, role="A sus4 tremolo")
    for inst, p, g, pan in (("vln_trem", "D6", -8, -0.42), ("vln_trem", "D5", -8, -0.2), ("vln_trem", "A4", -10, -0.25),
                            ("va_trem", "E4", -9, 0.15), ("va_trem", "A3", -9.5, 0.15), ("vc_trem", "E3", -8.5, 0.32),
                            ("vc_trem", "A2", -8, 0.36), ("cb_trem", "A1", -9, 0.5)):
        S.note("strings", inst, p, bell2, latch - bell2 + 0.05, g, pan, layer=2, **trem)
    for inst, p, g, pan in (("vln_sus", "D6", -9, -0.42), ("vln_sus", "D5", -9.5, -0.2), ("va_sus", "A3", -11, 0.15),
                            ("vc_sus", "A2", -10, 0.35), ("cb_sus", "A1", -10, 0.5)):
        S.note("strings", inst, p, bell2, latch - bell2 + 0.05, g, pan, layer=2, **trem)
    # organ crescendo: open rank chords from the Bb bar, swell box opening
    S.chords("organ", "open", [(t33, ["F3", "Bb3", "D4"]), (t36, ["G3", "Bb3", "D4", "G4"]),
                               (bell2, ["A2", "E3", "A3", "D4", "E4", "A4"])], latch + 0.05, -9, sp, attack=0.1,
             release=0.05, env=ramp([(t33, -16), (t36, -10), (bell2, -2), (latch, 0.5)]), role="organ crescendo")
    # timpani: a roll on A from server_out, an accent on bell2, cut by the latch
    so = cue["server_out"]
    S.note("perc", "timproll", "A2", so, latch - so + 0.05, -15, 0.08, sp, layer=5, attack=0.004, release=0.05,
           env=ramp([(so, 0), (bell2, 9), (latch, 12)]), role="timpani roll")
    S.note("perc", "timp", "A2", bell2, latch - bell2 + 0.05, -6, 0.08, sp, layer=4, release=0.05, role="timpani accent")
    S.lock("server_out", "onset", "perc", "timpani roll on A begins as the server lifts away")
    S.lock("bell2", "onset", "perc", "A sus4 forte (D on top) arrives with the bell")
    S.lock("latch", "stop", "all", "DEAD STOP: hard gate, reverb included")

    # ---------------------------------------------------------------- bar descriptions
    bd = [
        (1, 0, "3/4", "Dm (pedal D)", "-", "ostinato D4-A4 in quavers on the 8' stopped flute, lifting to Bb4 at the "
                                           "bar end; 16'+8' pedal D ppp"),
        (2, 3, "3/4", "Dm", "-", "con-sordino celli D3 F3 and violas A3 swell in from church_in"),
        (3, 6, "3/4", "Bb (rise1) -> F (look1, on beat 2)", "violas A3-Bb3-C4",
         "rise1: pedal Bb, ostinato D-Bb; look1 (beat 2, an agogic stretch as the eye settles): F major, ostinato "
         "C-A, celli C3 A3, violas C4, violins A4 C5 pp (first light)"),
        (4, 9, "3/4", "F -> A (beat 3, on the cut to the bloom)", "-",
         "strings drop away on the kettle click (silent before the cut); pedal A, ostinato E-A"),
        (5, 12, "3/4", "Dm", "celli D3 (q.) E3 (e) F3 (q)", "stream: the theme in the celli; 16' Bourdon joins the "
                                                            "ostinato; violas pp inner line"),
        (6, 15, "3/4", "Bb (maj7 colour)", "celli Bb3 (h) A3 (q)", "the sigh Bb->A"),
        (7, 18, "3/4", "Gm -> A (spout_out, beat 3)", "celli G3 (q.) F3 (e) E3 (q)",
         "slow motion ends inside bar 6, the brew dissolve ends on this downbeat; half close on spout_out; the organ's "
         "principal enters"),
        (8, 21, "3/4", "Dm", "violins D5/D4 (q.) E (e) F (q)", "pullback: the violins take the theme an octave "
                                                               "higher; celli D3 A3, violas F3"),
        (9, 24, "2/4", "Bb", "violins Bb5/Bb4 (q) A (q)", "look2: the peak Bb, mp (allargando into the cut)"),
        (10, 26, "4/4 (free)", "D (pedal)", "solo violin harmonic A6",
         "cup: subito pp; the ostinato stops; harmonic A6 (the violins' A taken up an octave) over the pedal only"),
        (11, 30, "3/4", "Dm", "horn D3 (q.) E3 (e) F3 (q)", "pour: the solo horn sings the theme; ostinato resumes"),
        (12, 33, "3/4", "Bb", "horn Bb3 (h) A3 (q)", "crescendo begins; contrabass enters; organ open rank, box "
                                                     "opening"),
        (13, 36, "3/4", "Gm", "horns + violins G (q.) A (e) Bb (q)", "the horn becomes a section; violins join the "
                                                                     "rising line; 4' flute; timpani roll on A from "
                                                                     "server_out"),
        (14, 39, "3/4 (held)", "A sus4 (A D E)", "horns D4, violins D6/D5",
         "bell2: forte, trombones, string tremolo, semiquaver ostinato, pressing; never resolved: cut dead at the "
         "latch"),
    ]
    for n, b, meter, harm, mel, what in bd:
        S.bar(n, K, b, meter, harm, mel, what)
    return K


def window(S: Score, cue: Cue):
    """Bars 15-27: latch+2.6 .. end, outdoors."""
    W = TempoMap("window", [(0, "return"), (6, "street"), (19, "square_cut"), (31, "climax")], cue,
                 stretch={30: 1.22, 5: 1.08})
    t = W.t
    sp = "out"
    ramp = C.ramp
    R, street, sq, clx = cue["return"], cue["street"], cue["square_cut"], cue["climax"]
    end, title, lastc = cue["end"], cue["title_in"], cue["last_chord"]
    WB = {0, 3, 6, 9, 12, 15, 19, 22, 25, 28, 31}
    mp0 = dict(max_pre=0.0)   # nothing may sound before the return: the attack starts on the event

    # dynamics: f at the return, mf on the street, f by the turn, ff at the climax, release
    dyn = ramp([(R, 0), (street - 0.3, 0.5), (street + 0.4, -3.0), (cue["turn_away"], 0.0), (sq, 0.0), (t(25), 1.0),
                (clx - 0.2, 3.0), (clx, 5.0), (clx + 2.0, 5.0), (clx + 2.8, 2.5), (title, -1.5), (lastc, -7.0),
                (end, -8.0)])

    # ---------------------------------------------------------------- pedal: 16' + 32' resultant (10 2/3') + 8'
    bass = [(R, "D"), (t(3), "C#"), (t(4), "B"), (street, "G"), (t(9), "F#"), (t(12), "E"), (t(15), "A"), (sq, "D"),
            (t(22), "B"), (t(25), "G"), (t(28), "A"), (clx, "D")]
    fifth = {"D": "A", "G": "D", "A": "E"}
    for i, (t0, pc) in enumerate(bass):
        t1 = bass[i + 1][0] if i + 1 < len(bass) else end
        kw = dict(mp0) if t0 == R else {}
        S.note("organ", "ped16", pc + "1", t0, t1 - t0 + (0.0 if t1 == end else 0.04), -9, 0.0, sp,
               attack=0.006 if t0 == R else 0.05, release=0.2 if t1 == end else 0.1, env=dyn, role="pedal 16'", **kw)
        S.note("organ", "ped8", pc + "2", t0, t1 - t0 + (0.0 if t1 == end else 0.04), -13, 0.0, sp,
               attack=0.006 if t0 == R else 0.05, release=0.2 if t1 == end else 0.1, env=dyn, role="pedal 8'", **kw)
        if pc in fifth and t0 <= clx and (t0 < street or t0 >= sq):   # the 32' resultant in the full passages
            q = N(fifth[pc] + "1") if fifth[pc] != "E" else N("E2") - 12
            tq1 = min(t1, clx + 2.0) if t0 == clx else t1
            S.note("organ", "ped16", q if q >= N("C1") else q + 12, t0, tq1 - t0 + 0.04, -17, 0.0, sp,
                   attack=0.006 if t0 == R else 0.05, release=0.3, env=dyn, role="32' resultant (quint)", **kw)
    S.lock("return", "onset", "organ", "full organ returns in D major (first F sharp), latch + 2.6 s")

    # ---------------------------------------------------------------- full organ (open plenum) chords
    plen = [(R, ["D3", "A3", "D4", "F#4", "A4", "D5"]), (t(3), ["C#3", "E3", "A3", "E4", "A4"]),
            (t(4), ["B2", "D3", "F#3", "B3", "D4", "F#4"]), (street, ["G2", "D3", "G3", "B3", "D4", "G4"]),
            (t(9), ["F#2", "A2", "D3", "A3", "D4", "F#4"]), (t(12), ["E2", "B2", "D3", "G3", "B3", "E4"]),
            (t(15), ["A2", "D3", "F#3", "A3", "D4", "F#4"]), (t(16), ["A2", "E3", "G3", "C#4", "E4", "A4"]),
            (sq, ["D3", "A3", "D4", "F#4", "A4", "D5"]), (t(22), ["B2", "F#3", "B3", "D4", "F#4", "B4"]),
            (t(25), ["G2", "D3", "G3", "B3", "D4", "G4"]), (t(28), ["A2", "E3", "A3", "C#4", "E4", "A4"]),
            (t(29), ["A2", "E3", "A3", "D4", "E4", "A4"]), (t(30.5), ["A2", "E3", "A3", "C#4", "E4", "A4"]),
            (clx, ["D3", "A3", "D4", "F#4", "A4", "D5", "F#5"])]
    pl_env = lambda tt: dyn(tt) * ramp([(clx + 2.0, 0), (title + 0.6, -30)])(tt)  # noqa: E731  open rank retires
    S.chords("organ", "open", plen, title + 0.6, -11.5, sp, pan=(-0.5, 0.5), attack=0.035, release=0.15, env=pl_env,
             role="full organ (open plenum)")
    # 8' + 4' flutes: the ostinato goes on, now in D major
    O = [(0, 3, "D4", "A4", None), (3, 4, "E4", "A4", None), (4, 6, "D4", "F#4", None), (6, 9, "D4", "G4", None),
         (9, 12, "D4", "A4", None), (12, 15, "D4", "G4", None), (15, 16, "D4", "A4", None), (16, 19, "E4", "A4", None),
         (19, 22, "D4", "A4", None), (22, 25, "D4", "F#4", None), (25, 28, "D4", "G4", None), (28, 29, "E4", "A4", None),
         (29, 30.5, "D4", "A4", None), (30.5, 31, "E4", "A4", None)]
    for b0, b1, lo, hi, nb in O:
        rock(S, W, b0, b1, lo, hi, nb, -12, -12, 2, space=sp, pan=0.3, role="ostinato 8'", bars=WB)
        rock(S, W, b0, b1, lo, hi, nb, -17, -17, 2, space=sp, oct_=12, pan=0.35, role="ostinato 4'", bars=WB)
    for e in S.E:
        if e["space"] == sp and abs(e["t"] - R) < 1e-6:
            e["max_pre"], e["attack"] = 0.0, 0.006

    # ---------------------------------------------------------------- strings: the theme at half tempo
    vth2 = [("D5", 3), ("E5", 1), ("F#5", 2), ("B5", 4), ("A5", 2), ("G5", 3), ("F#5", 1), ("E5", 1.6)]
    for inst, oct_, g, pan, lay in (("vln_sus", 0, -4.5, -0.5, 2), ("vln_sus", -12, -7.5, -0.25, 2)):
        notes = [(N(p) + oct_, d) for p, d in vth2]
        S.line("strings", inst, notes, W, 0, g, pan, sp, layer=lay, attack=0.08, release=0.2, overlap=0.08,
               gains=[0, -0.5, 0, 1.5, 0.5, 0.5, 0, -0.5], env=dyn, first=dict(attack=0.006, max_pre=0.0),
               role="theme half tempo (violins)")
    cel = [(["D3", "A3"], 3), (["C#3", "E3"], 1), (["B2", "F#3"], 2), (["G2", "D3"], 3), (["F#2", "A2"], 3),
           (["E2", "B2"], 3), (["A2", "D3"], 1), (["A2", "E3"], 2.6)]
    b = 0
    for ps, d in cel:
        for j, p in enumerate(ps):
            kw = dict(max_pre=0.0) if b == 0 else {}
            S.note("strings", "vc_sus", p, t(b), t(b + d) - t(b) + 0.08, -9.5 - j, 0.35, sp, layer=3,
                   attack=0.006 if b == 0 else 0.1, release=0.2, env=dyn, role="celli", **kw)
        b += d
    cbl = [("D2", 3), ("C#2", 1), ("B1", 2), ("G1", 3), ("F#1", 3), ("E1", 3), ("A1", 3.6)]
    S.line("strings", "cb_sus", cbl, W, 0, -10, 0.55, sp, layer=3, attack=0.1, release=0.2, overlap=0.08, env=dyn,
           first=dict(attack=0.006, max_pre=0.0), role="contrabass")
    # violas: the pulse in spiccato quavers (the ritual's rocking, now in the strings)
    VA = [(0, 3, "D4", "A4"), (3, 4, "E4", "A4"), (4, 6, "D4", "F#4"), (6, 9, "D4", "G4"), (9, 12, "D4", "A4"),
          (12, 15, "D4", "G4"), (15, 16, "D4", "A4"), (16, 18.5, "E4", "A4"),
          (19, 22, "D4", "A4"), (22, 25, "D4", "F#4"), (25, 28, "D4", "G4"), (28, 29, "E4", "A4"), (29, 30.5, "D4", "A4"),
          (30.5, 31, "E4", "A4")]
    for b0, b1, lo, hi in VA:
        n = int(round((b1 - b0) * 2))
        for k in range(n):
            bb = b0 + k / 2
            g = -10.5 - (1.5 if k % 2 else 0) + (1.0 if abs(bb - round(bb)) < 1e-6 and int(round(bb)) in WB else 0)
            S.note("strings", "va_spic", lo if k % 2 == 0 else hi, t(bb), 0.25, g, 0.18, sp, layer=2, attack=0.003,
                   release=0.08, env=dyn, role="violas spiccato pulse", **(mp0 if bb == 0 else {}))
    # timpani: roll under the pilaster wipe, resolving on the street downbeat
    pil = cue["pilaster1"]
    S.note("perc", "timproll", "D3", pil, street - pil - 0.03, -15, 0.08, sp, layer=5, attack=0.004, release=0.02,
           env=ramp([(pil, 0), (street - 0.05, 9)]), role="timpani roll (pilaster)")
    S.note("perc", "timp", "G2", street, 3.0, -3, 0.08, sp, layer=4, release=0.5, role="timpani (street)")
    S.lock("pilaster1", "onset", "perc", "timpani roll on D3 under the pilaster wipe")
    S.lock("street", "onset", "perc", "downbeat: timpani G, G major, the theme's peak B5 as the street opens")

    # ---------------------------------------------------------------- the run under his turn
    ta = cue["turn_away"]
    # an A-major scale A3..C#5 in violins + violas, an octave up in the first violins and down in the celli,
    # accelerating (each step 0.9 x the previous) from turn_away; it resolves into the D of the square's downbeat
    run = ["A3", "B3", "C#4", "D4", "E4", "F#4", "G4", "A4", "B4", "C#5"]
    nrun = len(run)
    w_ = 0.9 ** np.arange(nrun + 1)
    tt_run = ta + np.concatenate([[0], np.cumsum(w_)])[:nrun] * (sq - ta) / w_.sum()
    for k, (p, t0) in enumerate(zip(run, tt_run)):
        g = -9 + 4 * k / (nrun - 1) + (2.0 if k == 0 else 0.0)
        for inst, d_oct, dg, pan in (("vln_spic", 0, 0, -0.3), ("vln_spic", 12, -3, -0.5), ("va_spic", 0, -2, 0.15),
                                     ("vc_spic", -12, -2, 0.35)):
            S.note("strings", inst, N(p) + d_oct, t0, 0.22, g + dg, pan, sp, layer=2, attack=0.002, release=0.06,
                   env=dyn, role="rising run")
    S.lock("turn_away", "onset", "strings", "a rising string run starts under his turn")
    S.lock("square_cut", "onset", "perc", "downbeat on the cut to the square: D, timpani, brass theme")

    # ---------------------------------------------------------------- the final build: brass take the theme
    bth = [("D3", 1.5), ("E3", 0.5), ("F#3", 1), ("B3", 2), ("A3", 1), ("G3", 1.5), ("A3", 0.5), ("B3", 1),
           ("E4", 1), ("D4", 1.5), ("C#4", 0.5)]
    build = ramp([(sq, -4.5), (t(25), -2.5), (t(28), -0.5), (clx, 1.5)])
    horns(S, bth, W, 19, -4.5, 3, pan=-0.22, space=sp, n_to=4, attack=0.03, release=0.12, overlap=0.05,
          env=build, gains=[0, -0.5, 0, 1, 0, 0.5, 0, 1, 2, 1, 0.5], first=dict(attack=0.01), role="theme (horns)")
    for inst, g, pan, det in (("otbn", -5.5, 0.28, 0.0), ("otbn2", -7, 0.36, 3.0)):
        for e in S.line("brass", inst, bth, W, 19, g, pan, sp, layer=4, attack=0.03, release=0.12, overlap=0.05,
                        env=build, first=dict(attack=0.01), role="theme (trombones)"):
            e["detune"] = det
    tb_low = [("D3", 3), ("B2", 3), ("G2", 3), ("A2", 3)]
    S.line("brass", "tbn", tb_low, W, 19, -8, 0.4, sp, layer=3, attack=0.04, release=0.12, overlap=0.06, env=build,
           role="trombone (roots)")
    # violins double the theme two and three octaves above, climbing an octave at the four rising notes
    vb = [("D5", 1.5), ("E5", 0.5), ("F#5", 1), ("B5", 2), ("A5", 1), ("G5", 1.5), ("A5", 0.5), ("B5", 1), ("E6", 1),
          ("D6", 1.5), ("C#6", 0.5)]
    for oct_, g, pan in ((0, -5, -0.5), (-12, -7, -0.25)):
        S.line("strings", "vln_sus", [(N(p) + oct_, d) for p, d in vb], W, 19, g, pan, sp, layer=2, attack=0.05,
               release=0.12, overlap=0.06, env=build, role="theme (violins)")
    for inst, seq, g, pan in (("vc_sus", [("D3", 3), ("B2", 3), ("G2", 3), ("A2", 3)], -8.5, 0.35),
                              ("vc_sus", [("A3", 3), ("F#3", 3), ("D3", 3), ("E3", 3)], -9.5, 0.3),
                              ("cb_sus", [("D2", 3), ("B1", 3), ("G1", 3), ("A1", 3)], -9.5, 0.55)):
        S.line("strings", inst, seq, W, 19, g, pan, sp, layer=3, attack=0.06, release=0.15, overlap=0.06, env=build,
               role="bass line")
    for b_, p, g in ((19, "D2", -4), (25, "G2", -5)):
        S.note("perc", "timp", p, t(b_), 2.8, g, 0.08, sp, layer=4, release=0.4, role="timpani")
    S.note("perc", "timproll", "A2", t(28), clx - t(28) - 0.03, -13, 0.08, sp, layer=5, attack=0.004, release=0.02,
           env=ramp([(t(28), 0), (clx - 0.05, 9)]), role="timpani roll (into the climax)")

    # ---------------------------------------------------------------- climax and the long release
    S.note("perc", "timp", "D2", clx, 5.0, 0.0, 0.05, sp, layer=4, release=0.8, role="timpani (climax)")
    S.note("perc", "timp", "A2", clx, 4.0, -4.0, 0.15, sp, layer=4, release=0.8, role="timpani (climax)")
    S.lock("climax", "onset", "perc", "D major, the whole ensemble, ff, timpani stroke")
    brass_out = ramp([(clx, 0), (clx + 2.0, 0)])
    for i, c in enumerate(HORN_COPIES):
        for p, g in (("D4", -3.5), ("A3", -6.5), ("F#3", -7.5)):
            e = S.note("brass", "horn", p, clx + (c["dt"] if i else 0), 2.0, g + c["g"], -0.22 + c["dp"], sp,
                       layer=max(1, 3 + c["dl"]), attack=0.02, release=0.8, env=brass_out, role="climax (horns)")
            e["detune"] = c["det"]
    for inst, p, g, pan in (("otbn", "D3", -5, 0.28), ("otbn2", "A3", -7, 0.36), ("otbn", "F#3", -8, 0.32),
                            ("tbn", "D3", -7.5, 0.4), ("tbn", "A2", -8, 0.42)):
        S.note("brass", inst, p, clx, 2.0, g, pan, sp, layer=4, attack=0.02, release=0.8, env=brass_out,
               role="climax (trombones)")
    fade_s = ramp([(clx, 0), (clx + 1.5, 0), (title, -8), (lastc - 0.2, -40)])
    for inst, p, g, pan, lay in (("vln_sus", "D6", -6, -0.5, 2), ("vln_sus", "D5", -7, -0.25, 2),
                                 ("va_sus", "A4", -9, 0.15, 2), ("va_sus", "F#4", -9.5, 0.15, 2),
                                 ("vc_sus", "D3", -8.5, 0.35, 3), ("vc_sus", "A3", -9.5, 0.3, 3),
                                 ("cb_sus", "D2", -9.5, 0.55, 3)):
        S.note("strings", inst, p, clx, lastc - clx, g, pan, sp, layer=lay, attack=0.02, release=0.4,
               env=fade_s, role="climax / release (strings)")
    # the organ alone: 8' flutes D -> G/D (title_in, plagal) -> D (the last chord), the high flute sings the theme
    S.chords("organ", "ged", [(clx, ["D3", "A3", "D4", "F#4", "A4"]), (title, ["D3", "G3", "B3", "D4"]),
                              (lastc, ["D3", "A3"])], end, -9.5, sp, pan=(-0.35, 0.35), attack=0.03, release=0.2,
             overlap=-0.07,
             env=ramp([(clx, 0), (title, -1.5), (lastc, -3.5), (end, -4.5)]), role="release (8' flutes)")
    fl = [(clx, "D6", 0), (clx + 0.6 * (title - clx), "E6", -0.5), (clx + 0.75 * (title - clx), "F#6", 0),
          (title, "B6", 0.5), (lastc, "A6", 0)]
    for i, (t0, p, g) in enumerate(fl):
        t1 = fl[i + 1][0] - 0.06 if i + 1 < len(fl) else end
        S.note("organ", "ged", p, t0, t1 - t0, -11 + g, -0.1, sp, attack=0.02, release=0.2 if i == len(fl) - 1 else 0.05,
               env=ramp([(clx, -4), (clx + 1.5, 0), (end, -2)]), role="high flute (theme)")
    for p, g in (("D6", -16), ("F#6", -17)):
        S.note("organ", "ged", p, lastc, end - lastc, g, 0.15, sp, attack=0.03, release=0.2, role="last chord (high flute)")
    S.lock("title_in", "onset", "organ", "G/D, the plagal amen, high flute B6 as the word appears")
    S.lock("last_chord", "onset", "organ", "the last D major chord, high flute A6: the falling step at last")
    S.lock("end", "release", "all", "the last chord released on the cut to black")

    bd = [
        (15, 0, "3/4", "D major", "violins D5/D4 (dotted half)",
         "return: full organ (open plenum, flutes 8'+4', pedal 16'+8' and the 32' resultant), full strings, violas "
         "take the pulse in spiccato quavers; f"),
        (16, 3, "3/4", "A/C# -> Bm", "E5 (q) F#5 (h)", "descending bass D-C#-B; timpani roll on D from pilaster1"),
        (17, 6, "3/4", "G", "B5 (tied)", "street: timpani G on the downbeat, the theme's peak as the street opens; "
                                         "mf (room for the street)"),
        (18, 9, "3/4", "D/F#", "B5 -> A5", "the sigh in major (6 -> 5)"),
        (19, 12, "3/4", "Em7", "G5 (dotted half)", "crescendo; the dissolve to the turn passes through"),
        (20, 15, "4/4", "D/A -> A7", "F#5 E5 + run", "cadential six-four; turn_away: a rising string run (spiccato, "
                                                     "violins/violas/celli in octaves, accelerating) to the cut"),
        (21, 19, "3/4", "D", "horns+trombones D3 (q.) E3 (e) F#3 (q)", "square: the final build begins; violins "
                                                                       "double two/three octaves up; timpani D"),
        (22, 22, "3/4", "Bm", "B3 (h) A3 (q)", "f"),
        (23, 25, "3/4", "G", "G3 (q.) A3 (e) B3 (q)", "the four rising notes from G; timpani G"),
        (24, 28, "3/4", "A -> A sus4 -> A", "E4 (q) D4 (q.) C#4 (e)", "the sus4 of bell2 returns and resolves; "
                                                                      "timpani roll on A; allargando"),
        (25, 31, "free", "D major", "D4 / D6", "CLIMAX: whole ensemble ff with timpani D+A; brass out after 2 s; "
                                               "strings fade"),
        (26, "title_in", "free", "G/D (plagal)", "high flute D6 E6 F#6 -> B6", "the organ alone (8' flutes); the "
                                                                                "high flute sings the theme in major"),
        (27, "last_chord", "free", "D major", "high flute A6", "the falling step on the last chord; bell4 rings "
                                                               "inside it; released on 'end'"),
    ]
    for n, b, meter, harm, mel, what in bd:
        if isinstance(b, str):
            S.bars.append(dict(bar=n, map=None, beat=None, t=round(cue[b], 3), meter=meter, harmony=harm, melody=mel,
                               what=what, locked_to=b))
        else:
            S.bar(n, W, b, meter, harm, mel, what)
    return W


ARRIVAL_PRE_S = 0.06   # notes that make a locked arrival speak at most 60 ms before it (a clean bow change / pipe speech)


def build_score(cue):
    S = Score(cue)
    K = kitchen(S, cue)
    W = window(S, cue)
    for L_ in S.locks:
        if L_["kind"] != "onset":
            continue
        for e in S.E:
            if (L_["stem"] in ("all", e["stem"]) and abs(e["t"] - L_["t"]) < 1e-3 and e.get("attack", 0.004) <= 0.1
                    and not e.get("skip")):
                e["max_pre"] = min(e.get("max_pre", ARRIVAL_PRE_S) if e.get("max_pre") is not None else ARRIVAL_PRE_S,
                                   ARRIVAL_PRE_S)
                e["attack"] = min(max(e.get("attack", 0.004), 0.004), 0.03)
                e["arrival"] = L_["key"]
    # contract checks: nothing sounds in the silence, no F sharp before the latch
    for e in S.E:
        if e["space"] == "in" and e["t"] > cue["latch"]:
            raise AssertionError(f"indoor event after the latch: {e}")
        if e["space"] == "out" and e["t"] < cue["return"] - 1e-6:
            raise AssertionError(f"outdoor event before the return: {e}")
    fsharp = [e for e in S.E if e["space"] == "in" and "midi" in e and int(round(e["midi"])) % 12 == 6]
    if fsharp:
        raise AssertionError(f"F sharp before the latch: {fsharp[:3]}")
    return S, K, W


# ============================================================================= rendering
def swell_box(cue):
    pts = [(0.0, 0.2), (cue["walk"], 0.3), (cue["look1"], 0.5), (cue["kettle_click"], 0.4), (cue["stream"], 0.35),
           (cue["spout_out"], 0.45), (cue["look2"], 0.65), (cue["cup_cut"], 0.2), (cue["pour"], 0.3),
           (cue["slow2_end"], 0.45), (cue["bell2"], 0.95), (cue["latch"], 1.0), (cue["return"], 1.0),
           (cue["climax"], 1.0), (cue["last_chord"], 0.9), (cue.duration, 0.9)]
    return [p[0] for p in pts], [p[1] for p in pts]


def render3(lib, events, n, cue):
    pad = int(6.0 * SR)
    buses = {}
    used = {}
    R = cue["return"]

    def bus(k):
        if k not in buses:
            buses[k] = np.zeros((n + pad, 2), np.float32)
        return buses[k]

    for i, e in enumerate(events):
        inst = lib[e["inst"]]
        g = e.get("g", 0.0)
        if inst.kind == "timp":
            g += TIMP_REF.get(e["inst"], 0.0)
        max_pre = e.get("max_pre")
        if e["space"] == "out":   # nothing before the return
            room = e["t"] - R
            max_pre = room if max_pre is None else min(max_pre, room)
            max_pre = max(0.0, max_pre) if room < 0.6 else max_pre
        rkey = (round(e["midi"] + e.get("detune", 0.0) / 100.0, 2), e.get("layer"))
        if "_rr" in e:
            inst.rr_count[rkey] = e["_rr"]
        else:
            e["_rr"] = inst.rr_count.get(rkey, 0)
        sig, pre = render_note(inst, e["midi"] + e.get("detune", 0.0) / 100.0, e["dur"], layer=e.get("layer"),
                               attack=e.get("attack", 0.004), release=e.get("release", 0.08), skip=e.get("skip", 0.0),
                               max_pre=max_pre)
        i0 = int(round(e["t"] * SR)) - pre
        b = bus((e["stem"], e["space"], e.get("fx")))
        if i0 < 0:
            sig, i0 = sig[-i0:], 0
        sig = sig[: len(b) - i0]
        if e.get("env") is not None:
            tt = (i0 + np.arange(len(sig))) / SR
            sig = sig * e["env"](tt)[:, None].astype(np.float32)
        pan = e.get("pan", 0.0)
        gl = np.cos((pan + 1) * np.pi / 4) * np.sqrt(2) * 10 ** (g / 20)
        gr = np.sin((pan + 1) * np.pi / 4) * np.sqrt(2) * 10 ** (g / 20)
        b[i0: i0 + len(sig), 0] += sig[:, 0] * np.float32(gl)
        b[i0: i0 + len(sig), 1] += sig[:, 1] * np.float32(gr)
        used.setdefault(e["inst"], set()).add((round(e["midi"], 3), e.get("layer")))
        if i % 200 == 0:
            log(f"  rendered {i}/{len(events)} notes")
    return buses, used


def hall_ir(seed=2026, length=4.5, predelay=0.012):
    """Short bright hall for the open window (same construction as compose.church_ir, shorter decay):
    RT60 2.3-2.6 s in the low mids, 0.5 s above 11 kHz."""
    rng = np.random.default_rng(seed)
    nn = int(length * SR)
    tt = np.arange(nn) / SR
    edges = [None, 90, 180, 355, 710, 1400, 2800, 5600, 11200, None]
    rts = [2.2, 2.5, 2.6, 2.4, 2.2, 1.9, 1.4, 0.9, 0.5]
    late = np.zeros((nn, 2))
    for i, rt in enumerate(rts):
        band = sosfilt(C.bandpass_sos(edges[i], edges[i + 1]), rng.standard_normal((nn, 2)), axis=0)
        late += band * np.exp(-6.9078 * tt / rt)[:, None]
    on = np.clip((tt - predelay) / 0.04, 0, 1)
    late *= (on * on * (3 - 2 * on))[:, None]
    early = np.zeros((nn, 2))
    for c in range(2):
        for x in np.sort(rng.uniform(0.004, 0.06, 16)):
            early[int(x * SR), c] += rng.choice([-1, 1]) * np.exp(-x / 0.03) * rng.uniform(0.5, 1.0)
    early = sosfilt(butter(2, 8000, btype="low", fs=SR, output="sos"), early, axis=0)
    late /= np.sqrt(np.mean(late[: int(0.2 * SR)] ** 2) + 1e-12)
    early /= np.sqrt(np.mean(early[: int(0.06 * SR)] ** 2) + 1e-12)
    ir = 0.5 * early + 0.6 * late
    ir /= np.sqrt(np.sum(ir ** 2) / 2)
    ir *= raised_cos(nn, rising=False)[:, None] ** 0.3
    return ir.astype(np.float32), dict(rt60_bands_s=dict(zip(["<90", "90-180", "180-355", "355-710", "710-1.4k",
                                                              "1.4-2.8k", "2.8-5.6k", "5.6-11k", ">11k"], rts)),
                                       predelay_s=predelay, length_s=length)


def width(x, w):
    m = 0.5 * (x[:, 0] + x[:, 1])
    s = 0.5 * (x[:, 0] - x[:, 1]) * w
    return np.stack([m + s, m - s], axis=1).astype(np.float32)


SPACE = dict(
    inside=dict(send=0.62, dry=0.72, pre_lowpass_hz=7000, shelf_hz=3000, shelf_cut=0.55, width=0.55),
    outside=dict(send=0.24, dry=1.0, width=1.25),
)
GATE_FADE_S = 0.012
# balance per stem and space (dB): the organ leads; brass and timpani sit inside the full organ outdoors
STEM_TRIM = {("organ", "in"): 5.0, ("strings", "in"): 0.0, ("brass", "in"): -2.0, ("perc", "in"): -2.0,
             ("organ", "out"): 6.0, ("strings", "out"): -1.0, ("brass", "out"): -3.5, ("perc", "out"): -5.0}


def inside_fader(cue):
    """The kitchen is heard from a distance: a fader on everything indoors (dB) that keeps it pp-mp, with the
    crescendo to bell2 reaching forte but well under the climax."""
    return C.ramp([(0.0, -4.5), (cue["stream"] - 1.0, -4.5), (cue["stream"], -6.0), (cue["cup_cut"], -6.0),
                   (cue["cup_cut"] + 0.3, -3.0), (cue["pour"], -4.5), (cue["slow2_end"], -6.0),
                   (cue["server_out"], -7.0), (cue["bell2"], -7.0), (cue["latch"], -7.0)])


def mixdown(buses, n, cue, church, hall):
    hp = butter(4, 28.0, btype="high", fs=SR, output="sos")
    lp_in = butter(2, SPACE["inside"]["pre_lowpass_hz"], btype="low", fs=SR, output="sos")
    sh_in = butter(2, SPACE["inside"]["shelf_hz"], btype="high", fs=SR, output="sos")
    fx_sos = {"sord": butter(2, 2200, btype="low", fs=SR, output="sos"),
              "harm": butter(2, 2900, btype="low", fs=SR, output="sos")}
    bx_t, bx_v = swell_box(cue)
    dark = butter(2, 1400, btype="low", fs=SR, output="sos")
    latch, R, end, dur = cue["latch"], cue["return"], cue["end"], cue.duration
    il, iR = int(round(latch * SR)), int(round(R * SR))
    ig = int(round((latch + GATE_FADE_S) * SR))
    stems = {s: np.zeros((n, 2), np.float32) for s in STEMS}
    for (stem, space, fx), x in sorted(buses.items(), key=lambda kv: str(kv[0])):
        if not np.any(x):
            continue
        if stem == "organ":
            tt = np.arange(len(x)) / SR
            bb = np.interp(tt, bx_t, bx_v).astype(np.float32)[:, None]
            x = x * bb + sosfilt(dark, x, axis=0).astype(np.float32) * (1 - bb)
        if fx in fx_sos:
            x = sosfilt(fx_sos[fx], x, axis=0).astype(np.float32)
        x = x * np.float32(10 ** (STEM_TRIM[(stem, space)] / 20))
        x = sosfilt(hp, x, axis=0).astype(np.float32)
        nz = np.nonzero(np.abs(x).max(1) > 0)[0]
        first = int(nz[0]) if len(nz) else 0
        y = np.zeros((n, 2), np.float32)
        if space == "in":
            a, b = 0, ig + 1
            xs = sosfilt(lp_in, x[a:b], axis=0).astype(np.float32)
            wet = C.convolve(xs, church)[: b - a]
            # subito pp on the cut to the mug: the room's tail of the phrase is cut down with the picture
            ic = int(round(cue["cup_cut"] * SR))
            duck = np.interp(np.arange(a, b), [ic, ic + int(0.06 * SR), ic + int(1.2 * SR), ic + int(2.5 * SR)],
                             [1.0, 10 ** (-14 / 20), 10 ** (-14 / 20), 1.0]).astype(np.float32)[:, None]
            if stem == "strings":   # the strings leave with the kettle click: their room tail goes with them
                ik = int(round(cue["kettle_click"] * SR))
                duck = duck * np.interp(np.arange(a, b), [ik, ik + int(0.06 * SR), ik + int(0.9 * SR),
                                                          ik + int(2.0 * SR)],
                                        [1.0, 10 ** (-12 / 20), 10 ** (-12 / 20), 1.0]).astype(np.float32)[:, None]
            seg = SPACE["inside"]["dry"] * xs + SPACE["inside"]["send"] * wet * duck
            seg = seg - SPACE["inside"]["shelf_cut"] * sosfiltfilt(sh_in, seg, axis=0).astype(np.float32)
            seg = width(seg, SPACE["inside"]["width"])
            gate = inside_fader(cue)(np.arange(a, b) / SR).astype(np.float32)
            gate[il - a: ig - a] *= raised_cos(ig - il, rising=False)
            gate[ig - a:] = 0.0
            y[a:b] = seg * gate[:, None]
        else:
            a = iR
            xs = x[a:n]
            wet = C.convolve(xs, hall)[: n - a]
            tt = a + np.arange(n - a)
            ie, i_off = int((end + 0.25) * SR), int((dur - 0.32) * SR)
            wt = np.ones(n - a, np.float32)
            wt[max(0, ie - a): i_off - a] = raised_cos(i_off - ie, rising=False) ** 1.5
            wt[i_off - a:] = 0.0
            seg = SPACE["outside"]["dry"] * xs + SPACE["outside"]["send"] * wet * wt[:, None]
            y[a:n] = width(seg, SPACE["outside"]["width"])
        y[: first] = 0.0
        stems[stem] += y
    # room for bell 4 (a D bell): a 300-900 Hz dip on all music from just before the bell to the end
    bp = butter(2, [300, 900], btype="band", fs=SR, output="sos")
    tt = np.arange(n) / SR
    depth = 1 - 10 ** (-8 / 20)
    w = np.interp(tt, [cue["bell4"] - 0.8, cue["bell4"] - 0.2, dur], [0, depth, depth]).astype(np.float32)[:, None]
    for s in stems:
        band = sosfiltfilt(bp, stems[s], axis=0).astype(np.float32)
        stems[s] = stems[s] - band * w
    # the indoor silence and the final silence are exact zeros
    i_silent = int(round((dur - 0.3) * SR))
    for s in stems:
        stems[s][ig:iR] = 0.0
        stems[s][i_silent - int(0.02 * SR): i_silent] *= raised_cos(int(0.02 * SR), rising=False)[:, None]
        stems[s][i_silent:] = 0.0
    return stems


def quantise24(x):
    return (np.round(np.clip(x, -1.0, 1.0 - 2 ** -23) * 2 ** 23) / 2 ** 23).astype(np.float64)


# ============================================================================= analysis
def k_weight(x):
    m = pyln.Meter(SR)
    y = x.astype(np.float64)
    for f in m._filters.values():
        y = f.apply_filter(y)
    return y


def short_term(x, win=3.0, hop=0.25):
    """EBU short-term loudness (3 s, ungated) every `hop` s; window centred on the returned time."""
    y = k_weight(x)
    p = (y ** 2).sum(1)
    cs = np.concatenate([[0.0], np.cumsum(p)])
    W = int(win * SR)
    centres = np.arange(win / 2, len(x) / SR - win / 2 + 1e-9, hop)
    out = []
    for c in centres:
        a = int((c - win / 2) * SR)
        e = (cs[a + W] - cs[a]) / W
        out.append(-0.691 + 10 * np.log10(e + 1e-20))
    return centres, np.array(out)


_HP150 = butter(4, 150.0, btype="high", fs=SR, output="sos")


def onset_measure(x, t, tol=0.06):
    """The arrival's onset: the strongest spectral-flux peak (log-mel, 150 Hz-12 kHz, hop 2.7 ms) within +-tol of
    the event, accepted if it stands at least 2x above the median flux of the surrounding second (salience).
    High-passing keeps the pedal's beating out of the flux."""
    import librosa
    a = max(0, int((t - 0.5) * SR))
    y = sosfilt(_HP150, x[a: int((t + 0.5) * SR)].mean(1)).astype(np.float32)
    oenv = librosa.onset.onset_strength(y=y, sr=SR, hop_length=128, n_mels=96, fmin=150, fmax=12000)
    tt = a / SR + np.arange(len(oenv)) * 128 / SR
    w = np.abs(tt - t) <= tol
    if not np.any(w) or oenv.max() <= 0:
        return None, 0.0
    k = int(np.nonzero(w)[0][np.argmax(oenv[w])])
    sal = float(oenv[k] / (np.median(oenv) + 1e-9))
    return (float(tt[k]) if sal >= 2.0 else None), round(sal, 1)


def arrival_pitches(events, stem, t0, memory):
    """Pitches that start at t0 in `stem` and were not played there in the preceding `memory` seconds, and the
    other pitches sounding around t0 (whose partials must be kept out of the measurement)."""
    sel = [e for e in events if stem == "all" or e["stem"] == stem]
    starting = {e["midi"] for e in sel if abs(e["t"] - t0) < 0.03 and hz(e["midi"]) >= 100}
    recent = [e["midi"] for e in sel if e["t"] < t0 - 0.03 and e["t"] + e["dur"] + e.get("release", 0.08) > t0 - memory]
    new = sorted(m for m in starting if all(abs(m - r) > 0.5 for r in recent))
    others = sorted({e["midi"] for e in sel if e["t"] < t0 + 0.3 and e["t"] + e["dur"] + 0.5 > t0 - 0.4} - set(new))
    return new, others


def pitch_onset(x, t, midis, others=(), n_fft=1024, hop=48):
    """Onset of the notes that arrive at t, measured inside the real stem: energy of their first four harmonics
    in the STFT bins that no other sounding note's partials (j <= 10, < 1.2 kHz) come within 1.6 bins of; the onset
    is where it first reaches -12 dB of its peak in the 0.4 s after t (the convention used to place the notes:
    -12 dB of the sample's early peak).
    Returns (onset or None, rise in dB from before to after, number of bins used)."""
    a = max(0, int((t - 0.45) * SR))
    y = x[a: int((t + 0.45) * SR)].mean(1)
    win = np.hanning(n_fft)
    frames = range(0, len(y) - n_fft, hop)
    F = np.array([np.abs(np.fft.rfft(y[i: i + n_fft] * win)) ** 2 for i in frames])
    tt = a / SR + (np.array(list(frames)) + n_fft / 2) / SR
    df = SR / n_fft
    op = [j * hz(o) for o in others for j in range(1, 11) if j * hz(o) < 1200 or j <= 2]
    bins = sorted({int(round(k * hz(m) / df)) for m in midis for k in range(1, 5) if k * hz(m) < 6000
                   and all(abs(k * hz(m) - f) > 1.6 * df for f in op)})
    if not bins:
        return None, 0.0, 0
    e = 10 * np.log10(F[:, bins].sum(1) + 1e-20)
    post = float(np.max(e[(tt >= t + 0.02) & (tt <= t + 0.40)]))
    pre = float(np.median(e[(tt >= t - 0.35) & (tt <= t - 0.12)]))
    w = (tt >= t - 0.12) & (tt <= t + 0.12)
    k = np.nonzero(w & (e >= post - 12.0))[0]
    if len(k) == 0 or post - pre < 6.0:
        return None, round(post - pre, 1), len(bins)
    j = int(k[0])
    if j > 0 and e[j] != e[j - 1]:   # interpolate the crossing between frames
        f = (post - 12.0 - e[j - 1]) / (e[j] - e[j - 1])
        return float(tt[j - 1] + np.clip(f, 0, 1) * (tt[j] - tt[j - 1])), round(post - pre, 1), len(bins)
    return float(tt[j]), round(post - pre, 1), len(bins)


def probe_onset(lib, events, key, stem, t0, n, cue, church, hall):
    """The notes that make the arrival, rendered on their own through the same chain (same samples, spaces,
    gate, fader): onset = first time the 5 ms RMS reaches -12 dB of its peak (the placement convention)."""
    sub = [e for e in events if e.get("arrival") == key and stem in ("all", e["stem"])]
    if not sub:
        return None
    buses, _ = render3(lib, sub, n, cue)
    x = sum(mixdown(buses, n, cue, church, hall).values())
    a, b = int((t0 - 0.3) * SR), int((t0 + 0.5) * SR)
    env = C.env_db(x[a:b], 0.005)
    k = np.nonzero(env >= env.max() - 12.0)[0]
    return float(t0 - 0.3 + k[0] / SR) if len(k) else None


def release_time(x, t):
    """Times at which the 10 ms RMS falls 3, 6 and 20 dB under its median over the 0.4 s before the event."""
    e = C.env_db(x, 0.01)
    ref = float(np.median(e[int((t - 0.4) * SR): int((t - 0.05) * SR)]))
    seg = e[int((t - 0.1) * SR): int((t + 1.0) * SR)]
    out = {}
    for d in (3, 6, 20):
        k = np.nonzero(seg < ref - d)[0]
        out[d] = round(t - 0.1 + k[0] / SR, 4) if len(k) else None
    return out, ref


def tuning_test3(lib, used):
    """Isolated rendered notes measured with pYIN (independent of the calibration) and by the partials' FFT."""
    import librosa
    rep = {}
    for name in sorted(used):
        inst = lib[name]
        rows = []
        for m, layer in sorted(used[name], key=lambda v: (v[0], v[1] or 0)):
            if inst.kind == "timp":
                roll = name == "timproll"
                sig, pre = render_note(inst, m, 6.5 if roll else 2.0, layer=layer, release=0.1)
                f = C.timp_principal(sig.mean(1).astype(np.float64), SR, *(ROLL_WIN if roll else (0.12, 1.8)))
                rows.append(dict(note=NAME(m), layer=layer, cents=round(float(1200 * np.log2(f / hz(m))), 1),
                                 method="principal (1,1) mode"))
                continue
            sig, pre = render_note(inst, m, 3.0, layer=layer, attack=0.004, release=0.05)
            f = hz(m)
            if inst.kind == "pluck":
                w0, w1 = PLUCK_WIN.get(name, SPIC_WIN)
                a, b = pre + int(w0 * SR), pre + int(w1 * SR)
            else:
                a, b = pre + int(0.45 * SR), pre + int(2.9 * SR)
            seg = sig[a:b].mean(1).astype(np.float64)
            ff = C.harmonic_f0(seg, SR, f, kmax=6)
            cf = round(float(1200 * np.log2(ff / f)), 1)
            fl = int(min(max(2 ** int(np.ceil(np.log2(4 * SR / (f * 0.94)))), 2048), 2048 if inst.kind == "pluck" else 16384))
            c = None
            if len(seg) > fl * 1.5:
                f0, _, _ = librosa.pyin(seg.astype(np.float32), fmin=f * 2 ** (-1.5 / 12), fmax=f * 2 ** (1.5 / 12),
                                        sr=SR, frame_length=fl, hop_length=fl // 4, resolution=0.01,
                                        max_transition_rate=1.0)
                v = f0[~np.isnan(f0)]
                if len(v) >= 3:
                    c = round(float(1200 * np.log2(np.median(v) / f)), 1)
            rows.append(dict(note=NAME(m), layer=layer, cents=c, cents_fft=cf))
        if inst.kind == "timp":
            cs = [abs(r["cents"]) for r in rows]
            rep[name] = dict(notes=rows, max_abs_cents=round(max(cs), 1), mean_abs_cents=round(float(np.mean(cs)), 2),
                             within_6_cents=bool(max(cs) <= 6.0))
        else:
            cs = [abs(r["cents"]) for r in rows if r["cents"] is not None]
            cf = [abs(r["cents_fft"]) for r in rows]
            best = [min(abs(r["cents"]) if r["cents"] is not None else 99, abs(r["cents_fft"])) for r in rows]
            rep[name] = dict(notes=rows, n=len(rows), pyin_measured=len(cs),
                             pyin_mean_abs_cents=round(float(np.mean(cs)), 2) if cs else None,
                             pyin_max_abs_cents=round(float(np.max(cs)), 2) if cs else None,
                             fft_mean_abs_cents=round(float(np.mean(cf)), 2), fft_max_abs_cents=round(float(np.max(cf)), 2),
                             worst_best_of_two_cents=round(float(np.max(best)), 1),
                             within_6_cents=bool(np.max(best) <= 6.0))
        log(f"tuning {name}: {rep[name].get('pyin_max_abs_cents', rep[name].get('max_abs_cents'))} max |c|")
    return rep


def plots(mix, cue, out_dir, st_t, st_v):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from scipy.signal import stft

    mono = mix.mean(1).astype(np.float64)
    f, t, Z = stft(mono, fs=SR, nperseg=4096, noverlap=4096 - 960)
    S_ = 20 * np.log10(np.abs(Z) + 1e-9)
    S_ -= S_.max()
    keep = (f >= 25) & (f <= 16000)
    fig, ax = plt.subplots(2, 1, figsize=(30, 11), dpi=90, gridspec_kw=dict(height_ratios=[4, 1.3]), sharex=True)
    ax[0].pcolormesh(t, f[keep], S_[keep], shading="auto", cmap="magma", vmin=-95, vmax=0, rasterized=True)
    ax[0].set_yscale("log")
    ax[0].set_ylim(25, 16000)
    ax[0].set_ylabel("Hz")
    keys = ["fade_up", "walk", "rise1", "look1", "kettle_click", "stream", "spout_out", "pullback", "look2", "cup_cut",
            "pour", "server_out", "bell2", "latch", "return", "pilaster1", "street", "turn_away", "square_cut",
            "climax", "title_in", "last_chord", "bell4", "end"]
    for i, k in enumerate(keys):
        x = cue[k]
        col = "red" if k in ("latch", "climax") else "cyan"
        for a_ in ax:
            a_.axvline(x, color=col, lw=0.9, alpha=0.8)
        ax[0].text(x + 0.08, 12500 if i % 2 == 0 else 7000, k, color=col, fontsize=9, rotation=90, va="top",
                   fontweight="bold")
    ax[1].plot(st_t, st_v, color="black", lw=1.0, label="short-term loudness (3 s)")
    e = C.env_db(mix, 0.05)
    tt = np.arange(len(e)) / SR
    ax[1].plot(tt[::480], e[::480], color="0.6", lw=0.6, label="50 ms RMS (dBFS)")
    ax[1].set_ylim(-75, 0)
    ax[1].set_ylabel("LUFS / dBFS")
    ax[1].set_xlabel("film time (s)")
    ax[1].legend(loc="upper left", fontsize=8)
    ax[1].set_xlim(0, len(mono) / SR)
    ax[0].set_title("WARSZAWA - original score (music.wav). Lines: cue-sheet events (red: latch, climax)", pad=10)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "spectrogram.png"))
    plt.close(fig)
    # the dead stop
    L, R = cue["latch"], cue["return"]
    fig, ax = plt.subplots(3, 1, figsize=(16, 11), dpi=90)
    a, b = int((L - 0.25) * SR), int((L + 0.25) * SR)
    tt = L - 0.25 + np.arange(b - a) / SR
    e1 = C.env_db(mix[a:b], 0.001)
    ax[0].plot(tt, np.maximum(e1, -160), lw=0.8)
    ax[0].axvline(L, color="r", lw=0.8)
    ax[0].axvline(L + 0.03, color="orange", lw=0.8, ls="--")
    ax[0].set_ylim(-165, 0)
    ax[0].set_title(f"latch at {L:.3f} s: 1 ms RMS envelope (dBFS; -160 = digital zero). Orange: latch + 30 ms")
    a2, b2 = int((L - 1.0) * SR), int((R + 1.0) * SR)
    tt2 = L - 1.0 + np.arange(b2 - a2) / SR
    e2 = C.env_db(mix[a2:b2], 0.005)
    ax[1].plot(tt2, np.maximum(e2, -160), lw=0.7)
    for x, c in ((L, "r"), (L + 0.03, "orange"), (R, "g")):
        ax[1].axvline(x, color=c, lw=0.8)
    ax[1].axhline(-70, color="k", lw=0.6, ls=":")
    ax[1].set_ylim(-165, 0)
    ax[1].set_title(f"latch -> return ({R:.3f} s = latch + 2.6): 5 ms RMS (dBFS); dotted: -70 dBFS")
    f2, t2, Z2 = stft(mono[a2:b2], fs=SR, nperseg=2048, noverlap=2048 - 240)
    S2 = 20 * np.log10(np.abs(Z2) + 1e-9)
    ax[2].pcolormesh(t2 + L - 1.0, f2[1:], S2[1:], shading="auto", cmap="magma", vmin=S2.max() - 110, vmax=S2.max())
    ax[2].set_yscale("log")
    ax[2].set_ylim(30, 20000)
    for x in (L, R):
        ax[2].axvline(x, color="cyan", lw=0.8)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "latch.png"))
    plt.close(fig)


# ============================================================================= main
def main(argv):
    cue_path = argv[1] if len(argv) > 1 else DEFAULT_CUE
    out_dir = argv[2] if len(argv) > 2 else DEFAULT_OUT
    os.makedirs(out_dir, exist_ok=True)
    cue = Cue(cue_path)
    dur = cue.duration
    n = int(round(dur * SR))
    lib = build_library3()
    S, K, W = build_score(cue)
    events = S.E
    log(f"score: {len(events)} notes, {len(S.locks)} locked arrivals")
    for name in sorted({e["inst"] for e in events}):
        lib[name].calibrate()
    refined = refine_calibration(lib, [k for k in ("vln_spic", "va_spic", "vc_spic", "cb_pizz", "vc_pizz", "timproll")
                                       if lib[k].ready])
    for name in ("timp", "timproll"):
        if lib[name].ready:
            L4 = [s.lufs for s in lib[name].samples if s.layer >= 4 and s.lufs > -69]
            TIMP_REF[name] = float(-20.0 - np.mean(L4)) if L4 else 0.0
    log("calibration done")
    church, church_info = C.church_ir()
    hall, hall_info = hall_ir()
    C.LOOPS.clear()
    buses, used = render3(lib, events, n, cue)
    loops = list(C.LOOPS)
    log(f"rendered into {len(buses)} buses")
    stems = mixdown(buses, n, cue, church, hall)
    del buses
    log("mixdown done")
    stems, mhist, minfo = C.master(stems, target_lufs=-16.0, tp_ceiling=-2.0)
    q = {s: quantise24(stems[s]) for s in STEMS}
    mix = sum(q[s] for s in STEMS)
    assert np.abs(mix).max() < 1.0
    for s in STEMS:
        sf.write(os.path.join(out_dir, f"{s}.wav"), q[s], SR, subtype="PCM_24")
    sf.write(os.path.join(out_dir, "music.wav"), mix, SR, subtype="PCM_24")
    log("wrote wavs")

    # ------------------------------------------------------------------ QC
    rd, _ = sf.read(os.path.join(out_dir, "music.wav"), dtype="float64", always_2d=True)
    st = {s: sf.read(os.path.join(out_dir, f"{s}.wav"), dtype="float64", always_2d=True)[0] for s in STEMS}
    sum_err = float(np.abs(sum(st[s] for s in STEMS) - rd).max())
    info = sf.info(os.path.join(out_dir, "music.wav"))
    m = pyln.Meter(SR)
    lufs = m.integrated_loudness(rd)
    tp = C.true_peak_db(rd)
    peak = dbv(np.abs(rd).max())

    # locked arrivals
    arrivals = []
    for L_ in S.locks:
        k, t0, kind, stem = L_["key"], L_["t"], L_["kind"], L_["stem"]
        row = dict(key=k, film_time=round(t0, 3), kind=kind, stem=stem, what=L_["what"])
        x = rd if stem == "all" else st[stem]
        if kind == "onset":
            o, sal = onset_measure(x, t0)
            om, salm = onset_measure(rd, t0)
            arriving, others = arrival_pitches(events, stem, t0, 1.5 if t0 < cue["latch"] else 0.6)
            po, rise, nb = pitch_onset(x, t0, arriving, others) if arriving else (None, 0.0, 0)
            row.update(new_pitches=[NAME(mm) for mm in arriving], exclusive_bins=nb,
                       pitch_onset=round(po, 4) if po is not None else None, pitch_rise_db=rise,
                       pitch_error_ms=round((po - t0) * 1000, 1) if po is not None else None,
                       flux_onset_stem=o, flux_salience=sal,
                       flux_error_ms=round((o - t0) * 1000, 1) if o is not None else None,
                       flux_onset_mix=om, flux_salience_mix=salm,
                       flux_error_mix_ms=round((om - t0) * 1000, 1) if om is not None else None)
            # a clear onset in the stem (flux salience >= 3) is measured there; a soft legato arrival that the
            # stem cannot separate is measured on its own notes through the same chain (probe)
            if o is not None and sal >= 3.0:
                row["measure"], row["error_ms"] = "flux in stem", row["flux_error_ms"]
            else:
                pr = probe_onset(lib, events, k, stem, t0, n, cue, church, hall)
                row["probe_onset"] = round(pr, 4) if pr is not None else None
                row["measure"] = "probe (arrival notes alone, same chain)"
                row["error_ms"] = round((pr - t0) * 1000, 1) if pr is not None else None
            row["pass"] = row["error_ms"] is not None and abs(row["error_ms"]) <= 25.0
        elif kind == "start":
            nz = np.nonzero(np.abs(x[int((t0 - 0.5) * SR): int((t0 + 0.5) * SR)]).max(1) > 0)[0]
            s0 = t0 - 0.5 + nz[0] / SR if len(nz) else None
            row.update(first_sample=round(s0, 4) if s0 is not None else None,
                       error_ms=round((s0 - t0) * 1000, 1) if s0 is not None else None)
            row["pass"] = s0 is not None and abs(s0 - t0) <= 0.025
        elif kind == "release":
            r, ref = release_time(x, t0)
            row.update(level_before_dbfs=round(ref, 1), drop_3db_at=r[3], drop_6db_at=r[6], drop_20db_at=r[20],
                       error_ms=round((r[3] - t0) * 1000, 1) if r[3] is not None else None)
            row["pass"] = r[3] is not None and -0.025 <= r[3] - t0 <= 0.15
        elif kind == "stop":
            sm = C.stop_metrics(rd, t0)
            row.update(**{k_: v for k_, v in sm.items() if k_ != "stop_time"})
            last_nz = C._last_nonzero(rd, t0 - 0.1, t0 + 1.0)
            row["last_nonzero_sample_s"] = round(last_nz, 5)
            row["error_ms"] = round((last_nz - t0) * 1000, 1)
            row["pass"] = bool(last_nz <= t0 + 0.030)
        arrivals.append(row)
    n_onsets = [a for a in arrivals if a["kind"] in ("onset", "start")]
    errs_ = [abs(a["error_ms"]) for a in n_onsets if a.get("error_ms") is not None]
    worst = max(errs_) if errs_ else None

    # silence after the latch
    a_, b_ = int((cue["latch"] + 0.03) * SR), int(cue["return"] * SR)
    sil = rd[a_:b_]
    silence = dict(window_s=[round(cue["latch"] + 0.03, 3), round(cue["return"], 3)],
                   max_abs_dbfs=round(dbv(np.abs(sil).max()), 1) if np.any(sil) else -999.0,
                   rms_dbfs=round(10 * np.log10(np.mean(sil ** 2) + 1e-30), 1),
                   digital_zero=bool(not np.any(sil)), last_nonzero_after_latch_s=round(C._last_nonzero(rd, cue["latch"] - 0.1, cue["return"] - 0.01), 5),
                   first_nonzero_before_return_s=round(C._first_nonzero(rd, cue["latch"] + 0.1, cue["return"] + 0.2), 5))
    silence["pass"] = silence["max_abs_dbfs"] < -70.0
    final = dict(last_nonzero_s=round(C._last_nonzero(rd, dur - 3.0, dur), 4), required_silent_from_s=round(dur - 0.3, 4))
    final["pass"] = bool(final["last_nonzero_s"] <= dur - 0.3 + 1e-6)

    # loudness
    st_t, st_v = short_term(rd)
    sections = [("pre-roll (fade_up..walk)", "fade_up", "walk"), ("walk..stream", "walk", "stream"),
                ("stream..cup", "stream", "cup_cut"), ("cup..pour", "cup_cut", "pour"), ("pour..bell2", "pour", "bell2"),
                ("bell2..latch", "bell2", "latch"), ("latch..return (silence)", "latch", "return"),
                ("return..street", "return", "street"), ("street..square", "street", "square_cut"),
                ("square..climax", "square_cut", "climax"), ("climax..title_in", "climax", "title_in"),
                ("title_in..end", "title_in", "end")]
    sec = []
    for name, k0, k1 in sections:
        a, b = int(cue[k0] * SR), int(cue[k1] * SR)
        seg = rd[a:b]
        v = m.integrated_loudness(seg) if b - a > int(0.45 * SR) and np.any(seg) else float("-inf")
        msk = (st_t >= cue[k0]) & (st_t < cue[k1])
        sec.append(dict(section=name, start=round(cue[k0], 3), end=round(cue[k1], 3),
                        integrated_lufs=round(v, 2) if np.isfinite(v) else None,
                        short_term_max_lufs=round(float(st_v[msk].max()), 1) if msk.any() and np.isfinite(st_v[msk].max()) else None,
                        peak_dbfs=round(dbv(np.abs(seg).max()), 1) if np.any(seg) else None))
    i_max = int(np.argmax(st_v))
    kitchen_mask = (st_t >= cue["walk"]) & (st_t < cue["latch"] - 1.5)
    kv = st_v[kitchen_mask]

    def dyn_label(v):
        return "pp" if v < -34 else "p" if v < -29 else "mp" if v < -24 else "mf" if v < -20 else "f" if v < -15 else "ff"
    labels = [dyn_label(v) for v in kv]
    kshare = {k_: round(labels.count(k_) / max(len(labels), 1), 3) for k_ in ("pp", "p", "mp", "mf", "f", "ff")}
    k_peak_t = float(st_t[kitchen_mask | ((st_t >= cue["walk"]) & (st_t < cue["latch"]))][np.argmax(
        st_v[kitchen_mask | ((st_t >= cue["walk"]) & (st_t < cue["latch"]))])])
    out_mask = (st_t >= cue["return"] + 1.5) & (st_t < cue["end"])
    contour = dict(
        short_term_max_lufs=round(float(st_v[i_max]), 2), short_term_max_at_s=round(float(st_t[i_max]), 2),
        climax_s=round(cue["climax"], 3),
        peak_at_climax=bool(abs(st_t[i_max] - (cue["climax"] + 0.5)) <= 2.0),
        kitchen_dynamic_share=kshare, kitchen_pp_to_mp_share=round(kshare["pp"] + kshare["p"] + kshare["mp"], 3),
        kitchen_loudest_short_term_at_s=round(k_peak_t, 2),
        kitchen_loudest_near_bell2=bool(cue["bell2"] - 2.0 <= k_peak_t <= cue["latch"] + 0.5),
        kitchen_median_lufs=round(float(np.median(kv)), 1), window_median_lufs=round(float(np.median(st_v[out_mask])), 1),
        louder_after_latch_lu=round(float(np.median(st_v[out_mask]) - np.median(kv)), 1),
        dynamic_labels="short-term LUFS: pp < -34, p < -29, mp < -24, mf < -20, f < -15, ff >= -15",
    )
    contour["pass"] = bool(contour["peak_at_climax"] and contour["kitchen_pp_to_mp_share"] >= 0.6 and
                           contour["kitchen_loudest_near_bell2"] and contour["louder_after_latch_lu"] > 3)

    # motion: longest stretch without a new note (score) and without a detected onset (audio)
    spans = [("fade_up", "latch"), ("return", "last_chord")]
    mot = []
    for k0, k1 in spans:
        ts_ = sorted({round(e["t"], 3) for e in events if cue[k0] - 1e-6 <= e["t"] <= cue[k1] + 1e-6})
        ts_ = [cue[k0]] + ts_ + [cue[k1]]
        gaps = np.diff(ts_)
        gi = int(np.argmax(gaps))
        ons = C.detect_onsets(rd, cue[k0], cue[k1])
        oa = [cue[k0]] + ons + [cue[k1]]
        ga = np.diff(oa)
        gj = int(np.argmax(ga))
        mot.append(dict(span=f"{k0}..{k1}", score_longest_gap_s=round(float(gaps[gi]), 2),
                        score_gap_from_s=round(ts_[gi], 2), audio_longest_onset_gap_s=round(float(ga[gj]), 2),
                        audio_gap_from_s=round(oa[gj], 2)))
    motion = dict(spans=mot, limit_s=6.0, pass_=bool(all(x["score_longest_gap_s"] <= 6.0 for x in mot)),
                  note="the final release (last_chord..end) is exempt by design")

    tun = tuning_test3(lib, used)
    tuning_pass = all(v["within_6_cents"] for v in tun.values())
    clicks = C.click_scan(rd)
    expected = sorted({round(e["t"], 3) for e in events} | {round(cue["latch"], 3), round(cue["return"], 3)})
    clicks_unexpl = [c for c in clicks if min(abs(c - x) for x in expected) > 0.03]
    plots(rd, cue, out_dir, st_t, st_v)
    log("plots done")

    qc = dict(
        locked_arrivals_within_25ms=dict(pass_=bool(all(a["pass"] for a in arrivals if a["kind"] in ("onset", "start"))),
                                         worst_abs_error_ms=worst, n=len(n_onsets)),
        silence_after_latch=silence,
        dead_stop=[a for a in arrivals if a["kind"] == "stop"][0],
        final_silence=final,
        clipping=dict(sample_peak_dbfs=round(peak, 2), true_peak_dbtp=round(tp, 2),
                      pass_=bool(peak < 0 and tp <= -2.0 + 0.05)),
        loudness=dict(integrated_lufs=round(lufs, 2), target=-16.0, pass_=bool(abs(lufs + 16) <= 0.2)),
        tuning=dict(pass_=bool(tuning_pass), limit_cents=6.0),
        loudness_contour=contour,
        motion=motion,
        stems_sum_to_mix=dict(max_abs_difference=sum_err, pass_=bool(sum_err == 0.0)),
        format=dict(sample_rate=info.samplerate, channels=info.channels, subtype=info.subtype,
                    frames=info.frames, duration_s=round(info.frames / SR, 6), cue_duration_s=dur,
                    pass_=bool(info.samplerate == SR and info.channels == 2 and info.subtype == "PCM_24" and
                               info.frames == n)),
        clicks=dict(count=len(clicks), unexplained=clicks_unexpl[:40], pass_=not clicks_unexpl),
        tempo_sanity=dict(kitchen_bpm_range=K.describe()["beat_bpm_range"], window_bpm_range=W.describe()["beat_bpm_range"],
                          limits=[40, 90], pass_=bool(all(40 <= v <= 90 for tm in (K, W)
                                                         for v in tm.describe()["beat_bpm_range"]))),
    )
    qc["all_pass"] = bool(all(v.get("pass_", v.get("pass", True)) for k_, v in qc.items() if isinstance(v, dict)))

    instruments_used = sorted({e["inst"] for e in events})
    report = dict(
        title="WARSZAWA - original score", cue_sheet=os.path.relpath(cue_path, os.path.dirname(HERE)),
        file="music.wav", duration_s=round(len(rd) / SR, 6), samples=len(rd), sample_rate=SR, bit_depth=24, channels=2,
        key="D minor (kitchen: no F sharp before the latch) -> D major from latch + 2.6 s",
        theme="four rising notes answered by a falling step: D-E-F-Bb | A (3/4: q. e q | h q); major form D-E-F#-B | A",
        meter="3/4 (one 2/4 bar at look2, a free 4/4 bar over the empty mug, a 4/4 bar for the run)",
        tempo=dict(nominal="quarter = 60-66, rubato to the picture", kitchen=K.describe(), window=W.describe()),
        bar_by_bar=S.bars,
        locked_arrivals=dict(method="onset, two independent measures on the stem that carries the arrival: (a) "
                                    "broadband spectral flux (log-mel 150 Hz-12 kHz, hop 2.7 ms), strongest peak within "
                                    "+-60 ms, accepted if >= 2x the median flux of the surrounding second; (b) narrowband: "
                                    "energy of the first four harmonics of the pitches that start at the event (STFT "
                                    "21 ms, hop 1 ms), onset where it first reaches -12 dB of its peak in the 0.4 s "
                                    "after the event (needs a >= 6 dB rise; only "
                                    "pitches not played in that stem in the previous 1.5 s indoors / 0.6 s outdoors, "
                                    "only bins clear of other sounding notes' partials) - listed for information; "
                                    "(c) probe: the notes that make the arrival rendered alone through the same chain "
                                    "(same samples, spaces, gate), onset where the 5 ms RMS first reaches -12 dB of its "
                                    "peak (the placement convention). error_ms: (a) when its salience >= 3 (a clear "
                                    "onset in the delivered stem), else (c); flux on music.wav is also listed. start: first non-zero sample; release: first 10 ms RMS 3 dB under the "
                                    "preceding level (6 and 20 dB listed); stop: last non-zero sample after the gate",
                             arrivals=arrivals),
        qc=qc,
        per_section_loudness=sec,
        loudness=dict(integrated_lufs=round(lufs, 2), true_peak_dbtp_4x=round(tp, 2), sample_peak_dbfs=round(peak, 2),
                      master_iterations=mhist, limiter=minfo,
                      note="one static gain + one limiter gain curve applied identically to every stem; stems "
                           "quantised to 24 bit first and music.wav written as their exact sum"),
        short_term_loudness=dict(hop_s=0.25, window_s=3.0, t=[round(float(x), 2) for x in st_t[::4]],
                                 lufs=[round(float(x), 1) if np.isfinite(x) else None for x in st_v[::4]]),
        tuning_cents=tun,
        recalibrated=dict(note="spiccato pitch re-measured on att+0.01..0.22 s, pizzicato on att+0.03..0.6 s, "
                               "timpani rolls on 0.5..6 s "
                               "(file, compose.py measurement, refined measurement in MIDI)", samples=refined),
        loops=dict(count=len(loops), min_rho=round(min([L_["rho"] for L_ in loops]), 3) if loops else None,
                   in_score=loops[:60]),
        spaces=dict(inside=dict(**SPACE["inside"], reverb="compose.church_ir (RT60 ~4.8 s)", ir=church_info,
                                gate=f"all indoor buses x raised-cosine {GATE_FADE_S * 1000:.0f} ms from the latch, "
                                     "then exact zero (dry and reverb)"),
                    outside=dict(**SPACE["outside"], reverb="short hall", ir=hall_info,
                                 tail="reverb return faded from end+0.25 s to duration-0.32 s; exact zero from "
                                      "duration-0.3 s"),
                    bell4_room="300-900 Hz band 8 dB down on all music from bell4-0.2 s (ramped from bell4-0.8 s)",
                    swell_box=dict(zip(["t", "brightness"], [list(map(lambda v: round(v, 3), x)) for x in swell_box(cue)]))),
        instruments=dict(
            used=instruments_used,
            organ="VSCO-2 CE pipe organ (S. Dalzell / Ivy Audio): Man III open plenum ('open'), Man III stopped flute "
                  "('ged', played at 16', 8', 4' and in the high treble as the 'high flute'), Pedal 16' Loud "
                  "('ped16', also a fifth above for the 32' resultant), Pedal 8' Quiet ('ped8'); swell-box simulation",
            strings="VSCO-2 CE violin, viola, cello sections (sustain vibrato, tremolo, spiccato), solo contrabass, "
                    "solo violin (the harmonic: A6 sample, low-passed)",
            brass="VSCO-2 CE F horn (sustain; 4-player section = velocity layers, detune <= 5 cents, offsets <= 23 ms), "
                  "1950s Olds trombone (two takes), tenor trombone",
            perc="VSCO-2 CE timpani (hits and rolls)",
            not_used="no piano, harp, pads, synths, chimes/bells or ticking",
            octave_mapping="brass and woodwind sample names are one octave below sounding pitch (verified with "
                           "pYIN and a sub-octave partial test on every horn/trombone file family); string mappings "
                           "as in compose.py",
            licence="VSCO-2 Community Edition, CC0 1.0"),
        not_verified_by_ear=[
            "I cannot listen. Balance, phrasing, the realism of the layered horn section and of the pitch-shifted "
            "notes, and the emotional effect were judged from the score, loudness curves, spectrograms, onset and "
            "pitch measurements only.",
            "The solo violin 'harmonic' is an A6 vibrato sample low-passed to approach a harmonic's purity.",
            "The '8' principal' in the kitchen is the open plenum rank at low level behind a nearly closed swell box.",
            "Six soft arrivals (rise1, look1, spout_out, pullback, look2 inside legato strings/organ, title_in in the "
            "organ release) cannot be separated by onset detection inside the delivered stem (flux salience < 3); "
            "their timing is measured on the arrival notes rendered alone through the same chain (probe).",
            "The master limiter takes up to ~6 dB around the climax (needed for -16 LUFS integrated with a pp-mp "
            "kitchen at -2 dBTP); it is one gain curve on all stems.",
        ],
        rendered_by="pipeline/compose3.py (imports pipeline/compose.py unchanged)",
        render_seconds=round(time.time() - T_START, 1),
    )
    with open(os.path.join(out_dir, "score_report.json"), "w") as fh:
        json.dump(report, fh, indent=1, default=C._json_default)
    log(f"done: {lufs:.2f} LUFS, TP {tp:.2f} dBTP, worst locked onset {worst} ms, QC all_pass={qc['all_pass']}")


if __name__ == "__main__":
    main(sys.argv)
