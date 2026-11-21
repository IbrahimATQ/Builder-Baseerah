#!/usr/bin/env python3
"""Original score for "WARSZAWA" (the window), rendered offline from real sampled instruments.

Usage:
    python pipeline/compose3.py [CUESHEET.json] [OUT_DIR]
        defaults: data/cuesheet3.json  /home/user/coffee/score3

Every film time comes from the cue sheet at run time (events by key, shot film_in times, duration), so when the
picture editor nudges a cut a re-run follows it. The music returns after the latch on the cue-sheet event
"music_return" if the sheet has one, else on "turn_right" (his gaze turns right along the facade). Writes, in OUT_DIR:
    organ.wav strings.wav brass.wav perc.wav   stems (24-bit; they sum exactly, sample for sample, to music.wav)
    music.wav                                  48 kHz / 24-bit / stereo, exactly the cue-sheet duration, delivered
                                               open (no loudness target): one static gain to a -2.3 dBTP peak, the
                                               safety limiter takes at most 0.9 dB
    score_report.json                          key, tempo map, bar-by-bar description with film times, locked
                                               arrivals with measured onset errors, tuning per instrument,
                                               per-section loudness, QC, and the "story" acceptance tests (the
                                               music editor's review): climax step, masking of the story sounds
                                               against the sound team's stems, unique brass samples, stereo, ...
    spectrogram.png  latch.png                 the whole piece with the events marked; zoom on the dead stop

THE MUSIC (nothing quoted or imitated from any existing score)
One theme, D minor, 3/4, rubato to the picture: four rising notes answered by a falling step,
    D - E - F - Bb | A      (dotted quarter, eighth, quarter | half ... quarter)
The kitchen (fade_up..latch) is placed at a distance: long church room, soft top end, narrow image.
  - fade_up: 16' pedal D.  walk: the ritual's pendulum, D3-A3 crotchets on the 8' stopped flute (tenor octave).
  - church_in: as the church slides into the window the violas (con sordino) begin the theme: D - E - F, the leap to
    Bb on rise1 (the pendulum lifts to Bb and HOLDS: a fermata while the eye rises), the falling step to A on LOOK 1:
    F major, first light (a low pizzicato chord: the look lands). All but the pedal stop on the kettle click.
  - stream (slow motion: time suspended, no pulse): the celli state the theme; Dm Bb Gm -> A on spout_out.
  - spout_out ("the dripper drips alone"): the pendulum returns in quavers; pullback: the violins take the theme;
    LOOK 2 on its peak Bb (pizzicato chord). cup: subito, the pedal alone (ppp) over the empty mug.
  - pour: the solo horn sings the theme; slow2_end (real time again): the pendulum resumes; Bb -> Gm crescendo,
    the horn becomes a section. bell2: the music BREATHES (everything lets go 60 ms before the bell, the room tail is
    drawn down) so the bell is heard alone; LOOK 3 (rise3): A sus4, forte but dark (horns, trombones, low string
    tremolo, timpani, the pizzicato chord of the looks), never resolved:
  - latch: DEAD STOP (hard gate on the indoor buses, reverb included). The city floods in alone.
  - music_return (turn_right): an open fifth D-A swells in under his turning gaze (mp, strings and 8' flutes, natural
    attacks); a new pulse - three-note cells root-2nd-5th in viola spiccato - and NO third: no F sharp anywhere
    before the climax. A timpani roll under the pilaster lands on the street: G major, the theme on B
    (B - C# - D - G, the minor theme's own intervals inside D major) over G - A/G - Bb - C - A7; its sigh (G -> F#) is
    withheld. A rising A7 arpeggio under his turn throws to the square cut: a DECEPTIVE cadence on Bb (the kitchen's
    chord), dark (low brass and strings) so the casement creaks through it.
  - square..climax: horns take the kitchen theme (D - E - F - Bb | A) over Bb - Gm - A, then the window form
    (B - C# - D) over G - A/G - Gm as the red houses swing in; at square_in the violins hold a shimmering A5 over
    A7sus4 (the sus4 of bell2 returns) with a timpani roll: f, crescendo.
  - climax: D MAJOR - the first F sharp of the film - and the first full organ (open plenum) of the window: the
    withheld sigh resolves (G -> F#) inside, the violins leap A5 -> D6 (the film's highest forte note), horns,
    trombones, timpani D+A, 32' pedal. The brass leaves before the cup touches the sill.
  - release: the plenum thins to a soft principal: the theme once more in major on the principal (E - F# | B over
    G/D on title_in, a plagal amen | A over the last D major chord, in the A5 octave of bell 4's 877 Hz partial);
    bell4 rings inside it (300-900 Hz kept clear); the chord is released on 'end'.
Outdoors the music is close and full range, with the bass mono below 120 Hz and a moderate width.

Instruments: VSCO-2 Community Edition (CC0): pipe organ (S. Dalzell / Ivy Audio: Man III open plenum, Man III
stopped flute 8'/4', pedal 16' + 8', a 32' resultant from 16' + its fifth above), violin/viola/cello sections
(sustain, tremolo, spiccato, pizzicato), solo contrabass, F horn, 1950s Olds trombone (all takes), tenor trombone,
timpani. A brass "section" is made of DIFFERENT sample files (each player a distinct file, resampled <= 2
semitones), never copies of one take. No piano, harp, pads, synths, chimes or ticking.
The sampling engine is pipeline/compose.py (imported, unchanged): sample calibration (measured pitch, level,
onset), A=440 equal-temperament pitch correction by polyphase resampling, loop extension, church reverb and
analysis helpers.  Deterministic.
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "2"

import json
import re
import sys
import time

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy.ndimage import uniform_filter1d
from scipy.signal import butter, sosfilt, sosfiltfilt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compose as C  # noqa: E402  (the previous film's engine, reused as a library)
from compose import N, NAME, SR, Inst, _files, hz, dbv, log, raised_cos  # noqa: E402

REPO = os.path.dirname(HERE)
DEFAULT_CUE = os.path.join(REPO, "data", "cuesheet3.json")
DEFAULT_OUT = "/home/user/coffee/score3"
SOUND_DIR = "/home/user/coffee/sound3"                 # the sound team's stems: read by the QC only (masking tests)
SOUND_SPEC = os.path.join(REPO, "data", "sound3.json")  # for the score gain the sound mix applies ("auto")
STEMS = ("organ", "strings", "brass", "perc")
T_START = time.time()
FS = 6   # pitch class of F sharp


# ============================================================================= the contract
class Cue:
    """Film times by key, read from the cue sheet (events, shot film_in times, duration) plus derived cues."""

    NEED = ("fade_up", "walk", "church_in", "rise1", "look1", "kettle_click", "stream", "spout_out", "pullback",
            "look2", "pour", "slow2_end", "server_out", "bell2", "rise3", "latch", "pilaster1", "street",
            "turn_away", "casement", "red_houses", "square_in", "climax", "cup_on_sill", "title_in", "bell4", "end")
    RETURN_KEYS = ("music_return", "turn_right")   # the first one present anchors the music's return

    def __init__(self, path):
        d = json.load(open(path, encoding="utf-8"))
        self.path = path
        self.duration = float(d["duration"])
        self.ev = {e["key"]: float(e["t"]) for e in d["events"]}
        self.what = {e["key"]: e.get("what", "") for e in d["events"]}
        shots = {s["id"]: s for s in d["shots"]}
        rk = next((k for k in self.RETURN_KEYS if k in self.ev), None)
        missing = [k for k in self.NEED if k not in self.ev] + [s for s in ("cup", "square") if s not in shots]
        if rk is None:
            missing.append(" or ".join(self.RETURN_KEYS))
        if missing:
            raise KeyError(f"cue sheet {path} lacks {missing}")
        self.return_key = rk
        self.ev["cup_cut"] = float(shots["cup"]["film_in"])
        self.ev["square_cut"] = float(shots["square"]["film_in"])
        self.ev["return"] = self.ev[rk]
        self.ev["last_chord"] = self.ev["bell4"] - 0.7       # the last chord is in place before bell 4 rings
        self.what.update(cup_cut="cut to the empty WARSZAWA mug (shot 'cup' film_in)",
                         square_cut="cut to his other window (shot 'square' film_in)",
                         **{"return": f"the music returns (cue-sheet event '{rk}')", "last_chord": "bell4 - 0.7 s"})
        if not (self.ev["latch"] + 1.0 < self.ev["return"] < self.ev["street"]):
            raise ValueError(f"return {self.ev['return']} must fall between latch + 1 s and street")
        self.shots = shots
        self.events = d["events"]

    def __getitem__(self, k):
        return self.ev[k]


class TempoMap:
    """Beat -> film time. Anchors (beat, cue key) put beats exactly on events (beats on a half-beat grid). The beat
    lengths between anchors are solved as the SMOOTHEST tempo curve that meets every anchor (least squares on the
    change of tempo from half-beat to half-beat), so the pulse never lurches at an anchor; `stretch` marks a
    fermata (that beat is longer by the factor, the tempo around it unaffected); `cuts` are beats where the music
    has no pulse (a free bar, a break) and the tempo may change."""

    def __init__(self, name, anchors, cue, stretch=None, cuts=(), grid=0.5):
        self.name, self.grid = name, grid
        self.anchors = [(float(b), key, float(cue[key])) for b, key in anchors]
        bs = np.array([a[0] for a in self.anchors])
        ts = np.array([a[2] for a in self.anchors])
        if np.any(np.diff(bs) <= 0) or np.any(np.diff(ts) <= 0):
            raise ValueError(f"tempo map {name}: anchors out of order {self.anchors}")
        self.b0, self.b1 = float(bs[0]), float(bs[-1])
        n = int(round((self.b1 - self.b0) / grid))
        cb = self.b0 + grid * np.arange(n)
        s = np.ones(n)
        for b, f in (stretch or {}).items():
            s[(cb >= b - 1e-9) & (cb < b + 1 - 1e-9)] = f
        seg = np.searchsorted(bs, cb + 1e-9, side="right") - 1
        K = len(bs) - 1
        A = np.zeros((K, n))
        A[seg, np.arange(n)] = s
        T = np.diff(ts)
        w = np.ones(n - 1)
        for c in cuts:
            j = int(round((c - self.b0) / grid))
            if 1 <= j <= n - 1:
                w[j - 1] = 1e-3
        D = np.zeros((n - 1, n))
        D[np.arange(n - 1), np.arange(n - 1)] = -1.0
        D[np.arange(n - 1), np.arange(1, n)] = 1.0
        mseg = T / np.array([s[seg == k].sum() for k in range(K)])
        eps = 1e-3
        H = 2 * (D.T @ (w[:, None] * D)) + 2 * eps * np.eye(n)
        KKT = np.block([[H, A.T], [A, np.zeros((K, K))]])
        sol = np.linalg.solve(KKT, np.concatenate([2 * eps * mseg[seg], T]))
        d = s * sol[:n]
        if np.any(d <= 0.05):
            raise ValueError(f"tempo map {name}: impossible anchors {self.anchors}")
        self.cell, self.stretch = d, s
        cs = {float(c) for c in cuts}
        self.free = np.array([bs[seg[j]] in cs and bs[seg[j] + 1] in cs for j in range(n)])  # pulse-less free bars
        self.cell_t = ts[0] + np.concatenate([[0.0], np.cumsum(d)])
        self.seg_bpm = [dict(from_key=self.anchors[k][1], to_key=self.anchors[k + 1][1],
                             beats=float(bs[k + 1] - bs[k]), seconds=round(float(T[k]), 3),
                             mean_bpm=round(60.0 * float(bs[k + 1] - bs[k]) / float(T[k]), 1)) for k in range(K)]

    def t(self, b):
        x = (float(b) - self.b0) / self.grid
        n = len(self.cell)
        if x <= 0:
            return float(self.cell_t[0] + x * self.cell[0])
        if x >= n:
            return float(self.cell_t[-1] + (x - n) * self.cell[-1])
        i = int(np.floor(x))
        return float(self.cell_t[i] + (x - i) * self.cell[i])

    def describe(self):
        bpm = 60.0 * self.grid / self.cell
        base = (bpm * self.stretch)[~self.free]
        return dict(name=self.name, anchors=[dict(beat=b, key=k, t=round(t, 3)) for b, k, t in self.anchors],
                    segments=self.seg_bpm, grid_beats=self.grid,
                    beat_bpm_range=[round(float(bpm.min()), 1), round(float(bpm.max()), 1)],
                    base_bpm_range_without_fermatas=[round(float(base.min()), 1), round(float(base.max()), 1)],
                    free_bars_excluded=[[float(self.b0 + self.grid * j), round(float(bpm[j]), 1)]
                                        for j in range(len(bpm)) if self.free[j]][::2],
                    fermatas=[dict(beat=float(self.b0 + self.grid * j), factor=round(float(self.stretch[j]), 2))
                              for j in range(len(self.stretch)) if self.stretch[j] != 1.0][::2],
                    beats_s=[round(float(x), 3) for x in self.cell_t[::2]])


# ============================================================================= instruments
def build_library3():
    """compose.py's organ / strings / timpani, plus brass, string spiccato and pizzicato (same calibration)."""
    lib = C.build_library()
    nre = r"([A-G]#?-?\d)"
    up = lambda m: N(m.group(1)) + 12   # noqa: E731  VSCO names brass/woodwinds/sections one octave low (measured)
    lay = lambda m: int(m.group(2))     # noqa: E731
    rr = lambda m: int(m.group(3))      # noqa: E731
    lib["horn"] = Inst("horn", _files("Brass/F Horn/sus/*.wav", rf"MOHorn_sus_{nre}_v(\d)_1\.wav$", up, lay))
    # the 1950s Olds trombone: every take of layers 2-5 (one Inst; takes are separate files a section can use)
    lib["otbn"] = Inst("otbn", _files("Brass/OldTrombone/Sustain/*.wav", rf"Trombone_Sustain_{nre}_v([2-5])_(\d)\.wav$",
                                      up, lay, rr))
    lib["tbn"] = Inst("tbn", _files("Brass/Tenor Trombone/sus/*.wav", rf"tenortbn_sus_{nre}_v(\d)_1\.wav$", up, lay))
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
BRASS_FAMILIES = ("horn", "otbn", "tbn")
MAX_BRASS_SHIFT = 2.0        # semitones a brass sample may be resampled


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


def assign_brass(lib, events):
    """Every brass note gets its own sample FILE: notes of the same pitch that start together (a section, or two
    sections in unison) are given distinct files from their pool (the horn alone, or old + tenor trombone takes),
    resampled at most MAX_BRASS_SHIFT semitones, nearest pitch and nearest requested layer first. A player with no
    file left within reach is dropped (logged), never doubled."""
    br = sorted([e for e in events if e.get("pool")], key=lambda e: (int(round(e["midi"])), e["t"], e.get("player", 0)))
    groups = []
    for e in br:
        if groups and int(round(groups[-1][0]["midi"])) == int(round(e["midi"])) and e["t"] - groups[-1][0]["t"] < 0.03:
            groups[-1].append(e)
        else:
            groups.append([e])
    dropped = []
    for g in groups:
        used = set()
        for e in sorted(g, key=lambda e: (e.get("player", 0), e["t"])):
            m = e["midi"] + e.get("detune", 0.0) / 100.0
            L = e.get("layer") or 3
            cands = []
            for rank, fam in enumerate(e["pool"]):
                for s in lib[fam].samples:
                    sh = abs(s.meas - m)
                    if sh <= MAX_BRASS_SHIFT and s.path not in used:
                        cands.append((sh + 0.45 * abs(s.layer - L) + 0.6 * rank, fam, s))
            if not cands:
                e["drop"] = True
                dropped.append(dict(t=round(e["t"], 3), note=NAME(e["midi"]), role=e.get("role"), pool=e["pool"]))
                continue
            cands.sort(key=lambda c: (c[0], c[2].path))
            _, fam, s = cands[0]
            used.add(s.path)
            e["inst"], e["smp"], e["shift_st"] = fam, s.path, round(m - s.meas, 3)
    # the assertion the music editor asked for: no two players of one note on the same file
    for g in groups:
        files = [e["smp"] for e in g if not e.get("drop")]
        assert len(files) == len(set(files)), f"brass note {NAME(g[0]['midi'])} at {g[0]['t']:.3f}: duplicated file"
    return dict(groups=len(groups), multi_player_groups=sum(1 for g in groups if len(g) > 1),
                max_players=max((len(g) for g in groups), default=0), dropped=dropped)


# ============================================================================= score
class Score:
    def __init__(self, cue):
        self.cue = cue
        self.E: list[dict] = []
        self.locks: list[dict] = []
        self.bars: list[dict] = []
        self.harm: list[tuple] = []       # window harmony (t, chord, bass pitch class)
        self.themes: list[dict] = []      # theme statements (t, first note, voice)
        self.derived: dict = {}

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
        out = []
        for p in allp:
            i = 0
            while i < len(sets):
                if p in sets[i]:
                    j = i
                    while j + 1 < len(sets) and p in sets[j + 1]:
                        j += 1
                    pn = pan[0] + (pan[1] - pan[0]) * ((p - lo) / max(hi - lo, 1))
                    out.append(self.note(stem, inst, p, times[i], times[j + 1] - times[i] + overlap, g, pn, space,
                                         attack=attack, release=release, layer=layer, env=env, role=role, **kw))
                    i = j + 1
                else:
                    i += 1
        return out

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


def rock(S, tm, b0, b1, lo, hi, g0, g1, sub=2, inst="ged", space="in", oct_=0, start_t=None, stop_t=None, pan=0.2,
         role="ostinato 8'", bars=(), arrivals=(), legato=0.82, line="k"):
    """The ritual's pendulum: lo/hi alternating (sub=1 crotchets, 2 quavers, 4 semiquavers) from beat b0 to b1;
    beat 1 of a bar is accented, the upper note softer; the organist breathes before an arrival."""
    n = int(round((b1 - b0) * sub))
    out = []
    for k in range(n):
        b = b0 + k / sub
        t = tm.t(b)
        if start_t is not None and t < start_t - 1e-6:
            continue
        if stop_t is not None and t >= stop_t - 0.02:
            break
        step = tm.t(b + 1.0 / sub) - t
        p = lo if k % 2 == 0 else hi
        g = g0 + (g1 - g0) * k / max(n - 1, 1)
        if k % 2:
            g -= 1.8
        if abs(b - round(b)) < 1e-6 and int(round(b)) in bars:
            g += 1.2
        frac = legato
        if any(-0.004 < a - (t + step) < 0.004 for a in arrivals):
            frac = 0.6      # an organist's breath before the arrival
        dur = step * frac
        if stop_t is not None:
            dur = min(dur, stop_t - t - 0.01)
        out.append(S.note("organ", inst, N(p) + oct_, t, dur, g, pan if k % 2 else -pan, space, attack=0.004,
                          release=0.04, role=role, line=line, step_beats=1.0 / sub, beat=b))
    return out


CELLS = {  # the window's pulse: three-note cells root - 2nd - 5th (no third: the major third waits for the climax)
    "D": ("D4", "E4", "A4"), "G": ("G3", "A3", "D4"), "A": ("A3", "B3", "E4"), "Bb": ("Bb3", "C4", "F4"),
    "C": ("C4", "D4", "G4")}


def cells(S, tm, b0, b1, chord_at, g0, g1, space="out", stop_t=None, env=None, role="pulse (three-note cells)"):
    """Viola spiccato quavers cycling root-2nd-5th of the chord sounding at each quaver (chord_at(t) -> CELLS key);
    the cell's first note is accented."""
    n = int(round((b1 - b0) * 2))
    out = []
    for k in range(n):
        b = b0 + k / 2
        t = tm.t(b)
        if stop_t is not None and t >= stop_t - 0.02:
            break
        p = CELLS[chord_at(t)][k % 3]
        g = g0 + (g1 - g0) * k / max(n - 1, 1) + (1.0 if k % 3 == 0 else -0.8)
        out.append(S.note("strings", "va_spic", p, t, 0.24, g, 0.12 if k % 3 == 0 else 0.2, space,
                          layer=1 if g < -14 else 2, attack=0.003, release=0.08, env=env, role=role, line="w",
                          step_beats=0.5, beat=b))
    return out


SPREAD = [dict(dt=0.000, det=0.0, dp=0.00, g=0.0, dl=0),      # the lead
          dict(dt=0.010, det=-4.0, dp=0.12, g=-1.0, dl=-1),   # 2nd
          dict(dt=0.005, det=+3.5, dp=-0.10, g=-1.5, dl=+1),  # 3rd
          dict(dt=0.014, det=-2.0, dp=0.20, g=-2.0, dl=0)]    # 4th


def horns(S, notes, tm, b0, g, layer, pan=-0.2, space="in", n_from=1, n_to=4, grow=None, env=None, role="horns",
          **kw):
    """A horn line played by `n_to` players, each on its own sample file (assign_brass), slightly detuned (<= 4 cents)
    and late (<= 14 ms), spread in pan; players n_from+1..n_to fade in with `grow` (dB env)."""
    for i, c in enumerate(SPREAD[:n_to]):
        if i < n_from or grow is None:
            e_env = env
        elif env is None:
            e_env = grow
        else:
            e_env = (lambda tt, a=env, b=grow: a(tt) * b(tt))
        for e in S.line("brass", "horn", notes, tm, b0, g + c["g"], pan + c["dp"], space, layer=max(1, layer + c["dl"]),
                        env=e_env, role=role if i else role + " (lead)", **kw):
            e["t"] += c["dt"]
            e["dur"] = max(0.02, e["dur"] - c["dt"])
            e.update(detune=c["det"], pool=["horn"] if i < 2 else ["horn", "otbn"], player=i)


def section(S, pitch, t0, dur, g, players, pool, layer, pan=0.0, space="out", role="brass", env=None, **kw):
    """One sustained brass note for `players` players (distinct files, small spread)."""
    for i, c in enumerate(SPREAD[:players]):
        pl = list(pool) if (i < 2 or "otbn" in pool) else list(pool) + ["otbn"]
        S.note("brass", pool[0], pitch, t0 + c["dt"], dur - c["dt"], g + c["g"], pan + c["dp"], space,
               layer=max(1, layer + c["dl"]), env=env, role=role, detune=c["det"], pool=pl, player=i, **kw)


def kitchen(S: Score, cue: Cue):
    """fade_up .. latch, indoors."""
    ci, r1, l1, kc = cue["church_in"], cue["rise1"], cue["look1"], cue["kettle_click"]
    st6 = (l1 - r1) / max((r1 - ci) / 4.0, 1e-3)   # beat 6 (rise1 -> look1) is a fermata: the pulse holds
    K = TempoMap("kitchen", [(0, "walk"), (2, "church_in"), (6, "rise1"), (7, "look1"), (11, "kettle_click"),
                             (12, "stream"), (20, "spout_out"), (21, "pullback"), (24, "look2"), (26.5, "cup_cut"),
                             (30, "pour"), (32.5, "slow2_end"), (39, "rise3")], cue,
                 stretch={6: st6}, cuts=(11, 12, 26.5, 30))
    t = K.t
    sp = "in"
    ramp = C.ramp
    latch, bell2, r3 = cue["latch"], cue["bell2"], cue["rise3"]
    cup, pour, s2 = cue["cup_cut"], cue["pour"], cue["slow2_end"]
    br0 = bell2 - 0.06                  # the breath: everything indoors lets go just before the bell ...
    br1 = max(r3, bell2 + 0.15)         # ... and the A sus4 arrives on LOOK 3
    S.derived.update(breath_start=round(br0, 3), sus4_on=round(br1, 3))
    KB = {0, 3, 6, 7, 10, 12, 15, 18, 21, 24, 27, 30, 33, 36, 39}

    # ---------------------------------------------------------------- pedal (16' + 8'): the bass line
    fu = cue["fade_up"]
    ped = [  # t0, t1, pitch class, gain, extra
        (fu, r1, "D", -24, dict(skip=1.0, attack=0.002, env=ramp([(fu, -45), (cue["walk"], 0)]))),
        (r1, l1, "Bb", -21, {}), (l1, cue["stream"], "F", -21, dict(env=ramp([(l1, 0), (kc, 0), (kc + 0.3, -4)]))),
        (cue["stream"], t(15), "D", -18, {}), (t(15), t(18), "Bb", -18, {}), (t(18), cue["spout_out"], "G", -17, {}),
        (cue["spout_out"], cue["pullback"], "A", -16, {}), (cue["pullback"], cue["look2"], "D", -15, {}),
        (cue["look2"], t(25), "Bb", -14.5, {}),
        (t(25), t(33), "D", -15, dict(env=ramp([(t(25), 0), (cup, 0), (cup + 0.25, -8), (pour - 0.2, -8),
                                                (pour + 1.0, -2)]))),
        (t(33), t(36), "Bb", -15, {}), (t(36), br0, "G", -13, dict(release=0.05)),
        (br1, latch + 0.05, "A", -10, dict(env=ramp([(br1, 0), (latch, 3)]), release=0.05))]
    for t0, t1, pc, g, kw in ped:
        kw = dict(kw)
        kw.setdefault("attack", 0.12)
        rel = kw.pop("release", 0.12)
        S.note("organ", "ped16", pc + "1", t0, t1 - t0 + 0.04, g, 0.0, sp, release=rel, role="pedal 16'", **kw)
        S.note("organ", "ped8", pc + "2", t0, t1 - t0 + 0.04, g - 5, 0.0, sp, release=rel, role="pedal 8'", **kw)
    S.lock("fade_up", "start", "organ", "16' pedal D enters ppp (felt more than heard)")

    # ---------------------------------------------------------------- the pendulum (8' stopped flute)
    arr = [cue[k] for k in ("rise1", "look1", "spout_out", "pullback", "look2")] + [br1]
    rock(S, K, 0, 6, "D3", "A3", -17, -15.5, sub=1, space=sp, bars=KB, arrivals=arr, line="kA")
    S.note("organ", "ged", "Bb3", r1, (l1 - r1) * 0.9, -14.5, -0.2, sp, attack=0.004, release=0.05,
           role="ostinato 8'", line="kA", step_beats=1.0, beat=6.0, fermata=True)
    rock(S, K, 7, 11, "F3", "C4", -15, -16, sub=1, space=sp, stop_t=kc, bars=KB, arrivals=arr, line="kA")
    for b0, b1, lo, hi, g0, g1, stop in ((20, 21, "E3", "A3", -15, -15, None), (21, 24, "D3", "A3", -15, -14, None),
                                         (24, 25, "D3", "Bb3", -13.5, -13.5, None),
                                         (25, 26.5, "D3", "A3", -13.5, -14, cup)):
        rock(S, K, b0, b1, lo, hi, g0, g1, sub=2, space=sp, stop_t=stop, bars=KB, arrivals=arr, line="kB")
    for b0, b1, lo, hi, g0, g1 in ((32.5, 33, "D3", "A3", -14, -14), (33, 36, "D3", "Bb3", -13.5, -12),
                                   (36, 39, "D4", "Bb4", -12, -10)):
        rock(S, K, b0, b1, lo, hi, g0, g1, sub=2, space=sp, stop_t=br0, bars=KB, arrivals=arr, line="kC")
    rock(S, K, 39, 42, "D4", "A4", -10, -8, sub=4, space=sp, start_t=br1, stop_t=latch, bars=KB, line="kC")
    S.lock("walk", "onset", "organ", "his first step: the pendulum begins (D3-A3 crotchets, 8' stopped flute)")

    # ---------------------------------------------------------------- the theme's first figure (violas, con sord.)
    swell = ramp([(ci, -6), (r1, -1), (l1, 1.0), (kc - 0.6, 0.5), (kc, -1)])
    S.line("strings", "va_sus", [("D4", 2.5), ("E4", 0.5), ("F4", 1), ("Bb4", 1), ("A4", 4)], K, 2, -14.5, 0.15, sp,
           layer=1, attack=0.15, release=0.07, overlap=0.06, gains=[0, -0.8, -0.2, 1.2, 0.6], first=dict(attack=1.0),
           last_end=kc, env=swell, fx="sord", role="theme (violas, con sord.)")
    S.themes.append(dict(t=round(ci, 3), first="D", voice="violas (con sord.)", form="minor, first figure"))
    st = dict(space=sp, layer=1, fx="sord", env=swell, role="strings (sord.)")
    S.note("strings", "vc_sus", "D3", ci, l1 - ci + 0.1, -16, 0.35, attack=1.7, release=0.3, **st)
    S.note("strings", "vc_sus", "F3", ci, kc - ci, -16.5, 0.3, attack=1.7, release=0.07, **st)
    S.note("strings", "vc_sus", "C3", l1, kc - l1, -16, 0.35, attack=0.2, release=0.07, **st)
    for p, g, pan in (("C5", -22, -0.3), ("F5", -23, -0.4)):
        S.note("strings", "vln_sus", p, l1, kc - l1, g, pan, attack=0.25, release=0.07, **st)
    for key, chord in (("look1", ("F1", "F2", "C3", "A3")), ("look2", ("Bb1", "Bb2", "F3", "D4"))):
        for j, p in enumerate(chord):
            S.note("strings", "cb_pizz" if j == 0 else "vc_pizz", p, cue[key], 1.2, -6 if j == 0 else -8 - 1.5 * j,
                   0.45 if j == 0 else 0.3 - 0.05 * j, sp, layer=2, attack=0.002, release=0.3,
                   role="pizzicato (the look lands)")
    S.lock("rise1", "onset", "organ", "the pendulum lifts to Bb and holds (fermata); the violas leap to Bb; pedal Bb")
    S.lock("look1", "onset", "strings", "LOOK 1: the falling step to A, F major, low pizzicato F; violins enter pp")
    S.lock("kettle_click", "release", "strings", "the strings and the pendulum stop on the click (the pedal holds)")

    # ---------------------------------------------------------------- stream: the theme in the celli (no pulse)
    S.line("strings", "vc_sus", [("D3", 1.5), ("E3", 0.5), ("F3", 1), ("Bb3", 2), ("A3", 1), ("G3", 1.5), ("F3", 0.5),
                                 ("E3", 1)], K, 12, -8.0, 0.3, sp, layer=3, attack=0.08, release=0.25,
           gains=[0, -0.8, 0, 1.2, -0.3, 0.4, -0.8, -0.2], first=dict(attack=0.02), role="theme (celli)")
    S.themes.append(dict(t=round(cue["stream"], 3), first="D", voice="celli", form="minor"))
    S.lock("stream", "onset", "strings", "the celli begin the theme as the water touches the coffee (time stops)")
    S.line("strings", "va_sus", [("A3", 3), ("D4", 3), ("Bb3", 2), ("C#4", 1)], K, 12, -17, 0.15, sp, layer=1,
           attack=0.3, release=0.2, overlap=0.1, fx="sord", role="violas (inner)")
    S.chords("organ", "ged", [(cue["stream"], ["F3", "A3", "D4"]), (t(15), ["F3", "Bb3", "D4"]),
                              (t(18), ["G3", "Bb3", "D4"])], cue["spout_out"] - 0.05, -22, sp, attack=0.4,
             release=0.3, role="8' flute chords")
    S.lock("spout_out", "onset", "organ", "half close on A: the pendulum returns in quavers (the dripper drips), "
                                          "the principal enters, pedal A")
    # pullback: the violins take the theme (vln I D5, vln II D4); celli and violas carry the harmony
    vth = [("D", 1.5), ("E", 0.5), ("F", 1), ("Bb", 1), ("A", 1.5)]
    for oct_, g, pan in ((5, -8.5, -0.42), (4, -12, -0.2)):
        S.line("strings", "vln_sus", [(p + str(oct_), d) for p, d in vth], K, 21, g, pan, sp, layer=1, attack=0.07,
               release=0.05, gains=[0, -0.5, 0.5, 2.0, 1.0], first=dict(attack=0.02), last_end=cup,
               env=ramp([(t(21), -2), (t(24), 1.5)]), role=f"theme (violins {'I' if oct_ == 5 else 'II'})")
    S.themes.append(dict(t=round(cue["pullback"], 3), first="D", voice="violins", form="minor"))
    for inst, seq, g, pan in (("vc_sus", [("D3", 3), ("Bb2", 1), ("D3", 1.5)], -12, 0.35),
                              ("vc_sus", [("A3", 3), ("F3", 2.5)], -13, 0.3),
                              ("va_sus", [("F3", 3), ("D4", 2.5)], -15, 0.15)):
        S.line("strings", inst, seq, K, 21, g, pan, sp, layer=1, attack=0.12, release=0.05, last_end=cup,
               role="harmony")
    S.chords("organ", "open", [(cue["spout_out"], ["E3", "A3", "E4"]), (t(21), ["A3", "D4", "F4"]),
                               (t(24), ["Bb3", "D4", "F4"]), (t(25), ["A3", "D4", "F4"])], cup, -16, sp, attack=0.12,
             release=0.05, env=ramp([(t(20), -9), (t(24), 0)]), role="principal 8'")
    S.lock("pullback", "onset", "strings", "Dm: the violins begin the theme as he straightens")
    S.lock("look2", "onset", "strings", "LOOK 2: the theme's peak Bb (violins), low pizzicato Bb, mp")

    # ---------------------------------------------------------------- cup: subito pp, one steady pipe + pedal
    S.lock("cup_cut", "release", "strings", "subito: the violins and the pendulum stop on the cut; the pedal alone, "
                                           "ppp, over the empty mug")

    # ---------------------------------------------------------------- pour: the solo horn sings the theme
    S.lock("pour", "onset", "brass", "the solo horn begins the theme over the pedal (slow motion: no pulse)")
    grow = ramp([(t(36), -18), (t(37.5), -6), (t(38.5), 0)])
    horns(S, [("D3", 1.5), ("E3", 0.5), ("F3", 1), ("Bb3", 2), ("A3", 1), ("G3", 1.5), ("A3", 0.5), ("Bb3", 1)],
          K, 30, -6.5, 2, space=sp, n_from=1, n_to=4, grow=grow, attack=0.06, release=0.05, overlap=0.06,
          gains=[0, -0.8, 0, 1.0, -0.5, 1.0, 1.5, 2.5], first=dict(attack=0.03), last_end=br0, role="theme (horn)")
    S.themes.append(dict(t=round(pour, 3), first="D", voice="horn", form="minor"))
    t30, t33, t36 = t(30), t(33), t(36)
    cres = ramp([(t30, -4), (t33, -2), (t36, 0), (br0, 2)])
    for inst, seq, g, pan in (("vc_sus", [("D2", 3), ("Bb2", 3), ("G2", 3)], -14, 0.35),
                              ("vc_sus", [("A2", 3), ("F3", 3), ("D3", 3)], -15, 0.3),
                              ("va_sus", [("A3", 3), ("D4", 3), ("Bb3", 3)], -16, 0.15),
                              ("va_sus", [(None, 3), ("F3", 3), ("G3", 3)], -16.5, 0.15),
                              ("cb_sus", [(None, 3), ("Bb1", 3), ("G1", 3)], -15, 0.5)):
        S.line("strings", inst, seq, K, 30, g, pan, sp, layer=1, attack=0.25, release=0.05, overlap=0.08, env=cres,
               last_end=br0, role="strings (pour)")
    S.line("strings", "vln_sus", [("G4", 1.5), ("A4", 0.5), ("Bb4", 1)], K, 36, -11, -0.35, sp, layer=2, attack=0.12,
           release=0.05, gains=[0, 1, 2.5], env=ramp([(t36, -5), (br0, 0)]), last_end=br0,
           role="rising line (violins)")
    S.chords("organ", "open", [(t33, ["F3", "Bb3", "D4"]), (t36, ["G3", "Bb3", "D4", "G4"])], br0, -10, sp, attack=0.1,
             release=0.05, env=ramp([(t33, -16), (t36, -10), (br0, -4)]), role="organ crescendo")
    so = cue["server_out"]
    S.note("perc", "timproll", "A2", so, br0 - so, -17, 0.08, sp, layer=5, attack=0.004, release=0.04,
           env=ramp([(so, 0), (br0, 6)]), role="timpani roll")
    S.lock("server_out", "onset", "perc", "timpani roll on A begins as the server lifts away")
    S.lock("bell2", "breath", "all", "the music breathes: everything lets go 60 ms before the bell (room tail drawn "
                                      "down) so the bell is heard alone", t=br0)

    # ---------------------------------------------------------------- LOOK 3: A sus4, forte but dark
    sus_end = latch + 0.05
    pressing = ramp([(br1, 0), (latch, 3.0)])
    for p, n_, g in (("A3", 2, -6.5), ("D4", 2, -5.5)):
        section(S, p, br1, sus_end - br1, g, n_, ["horn"], 3, pan=-0.2, space=sp, attack=0.03, release=0.05,
                env=pressing, role="A sus4 (horns)")
    for p, g in (("A2", -7), ("E3", -8.5)):
        section(S, p, br1, sus_end - br1, g, 1, ["otbn", "tbn"], 4, pan=0.3, space=sp, attack=0.03, release=0.05,
                env=pressing, role="A sus4 (trombones)")
    trem = dict(space=sp, attack=0.04, release=0.05, env=pressing, role="A sus4 tremolo")
    for inst, p, g, pan in (("va_trem", "D4", -10, 0.15), ("va_trem", "A3", -10.5, 0.15), ("vc_trem", "E3", -9, 0.32),
                            ("vc_trem", "A2", -8.5, 0.36), ("cb_trem", "A1", -9.5, 0.5)):
        S.note("strings", inst, p, br1, sus_end - br1, g, pan, layer=2, **trem)
    for inst, p, g, pan in (("vc_sus", "A2", -11, 0.35), ("cb_sus", "A1", -11, 0.5)):
        S.note("strings", inst, p, br1, sus_end - br1, g, pan, layer=2, **trem)
    for j, p in enumerate(("A1", "A2", "E3", "A3")):
        S.note("strings", "cb_pizz" if j == 0 else "vc_pizz", p, br1, 1.0, -6 if j == 0 else -8 - 1.5 * j, 0.4, sp,
               layer=2, attack=0.002, release=0.3, role="pizzicato (the look lands)")
    S.chords("organ", "open", [(br1, ["A2", "E3", "A3", "D4"])], sus_end, -9, sp, attack=0.05, release=0.05,
             env=pressing, role="organ (A sus4)")
    S.note("perc", "timp", "A2", br1, sus_end - br1, -7, 0.08, sp, layer=4, release=0.05, role="timpani accent")
    S.note("perc", "timproll", "A2", br1, sus_end - br1, -15, 0.08, sp, layer=5, attack=0.004, release=0.05,
           env=ramp([(br1, 0), (latch, 8)]), role="timpani roll")
    S.lock("rise3", "onset", "brass", "LOOK 3: A sus4 (D on top, D4), forte, dark; pizzicato A", t=br1)
    S.lock("latch", "stop", "all", "DEAD STOP: hard gate, reverb included")

    bd = [
        (1, 0, "3/4", "Dm (pedal D)", "-", "the pendulum: D3-A3 crotchets on the 8' stopped flute; 16'+8' pedal D"),
        (2, 2, "3/4", "Dm", "violas D4 (dotted half...)", "church_in: the violas (con sord.) begin the theme; "
                                                         "celli D3 F3 swell in"),
        (3, 4.5, "3/4", "Dm -> Bb (rise1)", "E4 F4 | Bb4", "rise1: the leap to Bb, pedal Bb; the pendulum lifts to "
                                                          "Bb and holds through a fermata while the eye rises"),
        (4, 7, "3/4", "F major (look1)", "A4", "LOOK 1: the falling step to A; F major (first light), pendulum F3-C4, "
                                               "violins pp, low pizzicato F; all stop on the kettle click"),
        (5, 12, "3/4", "Dm", "celli D3 (q.) E3 (e) F3 (q)", "stream: no pulse (slow motion); the celli sing the "
                                                            "theme over 8' flute chords"),
        (6, 15, "3/4", "Bb", "celli Bb3 (h) A3 (q)", "the sigh Bb->A"),
        (7, 18, "3/4", "Gm -> A (spout_out)", "celli G3 (q.) F3 (e) E3 (q)", "half close: the pendulum returns "
                                                                             "(quavers), the principal enters"),
        (8, 21, "3/4", "Dm", "violins D5/D4 (q.) E (e) F (q)", "pullback: the violins take the theme"),
        (9, 24, "2/4 + 1/2", "Bb -> Dm", "violins Bb5/Bb4 (q) A (q.)", "LOOK 2: the peak Bb, mp, pizzicato Bb"),
        (10, 26.5, "free", "D (pedal)", "-", "cup: subito, the pedal alone (ppp) over the empty mug"),
        (11, 30, "3/4", "Dm", "horn D3 (q.) E3 (e) F3 (q)", "pour (slow motion): the solo horn"),
        (12, 33, "3/4", "Bb", "horn Bb3 (h) A3 (q)", "slow2_end: the pendulum resumes; crescendo; contrabass"),
        (13, 36, "3/4", "Gm", "horns + violins G (q.) A (e) Bb", "the horn becomes a section (distinct takes); "
                                                                 "timpani roll from server_out; BREATH before bell2"),
        (14, 39, "3/4 (held)", "A sus4 (A D E)", "horns D4", "LOOK 3: forte but dark; semiquaver pendulum, low "
                                                              "tremolo, timpani; never resolved: cut dead at the latch"),
    ]
    for n, b, meter, harm, mel, what in bd:
        S.bar(n, K, b, meter, harm, mel, what)
    return K


def window(S: Score, cue: Cue):
    """music_return .. end, outdoors."""
    W = TempoMap("window", [(0, "return"), (4, "street"), (14, "turn_away"), (16, "square_cut"), (22, "red_houses"),
                            (25, "square_in"), (27, "climax")], cue, cuts=(14, 16))
    t = W.t
    sp = "out"
    ramp = C.ramp
    R, street, ta, sq = cue["return"], cue["street"], cue["turn_away"], cue["square_cut"]
    rh, sqi, clx, cos = cue["red_houses"], cue["square_in"], cue["climax"], cue["cup_on_sill"]
    title, lastc, end = cue["title_in"], cue["last_chord"], cue["end"]
    brass_off = cos - 0.12                       # the brass is silent before the cup touches the sill
    t7, t8, t10, t12, t19, t21, t235, t24 = t(7), t(8), t(10), t(12), t(19), t(21), t(23.5), t(24)
    WB = {0, 1, 4, 7, 10, 13, 16, 19, 22, 25, 27}

    H = [(R, "D5 (open fifth)", "D"), (street, "G", "G"), (t7, "A/G", "G"), (t8, "Bb", "Bb"), (t10, "C", "C"),
         (t12, "A7", "A"), (sq, "Bb", "Bb"), (t19, "Gm", "G"), (t21, "A", "A"), (rh, "G", "G"), (t235, "A/G", "G"),
         (t24, "Gm", "G"), (sqi, "A7sus4", "A"), (clx, "D", "D"), (title, "G/D", "D"), (lastc, "D", "D")]
    S.harm = H
    cell_key = {"D5 (open fifth)": "D", "G": "G", "A/G": "A", "Bb": "Bb", "C": "C", "A7": "A", "Gm": "G", "A": "A",
                "A7sus4": "A"}

    def chord_at(tt):
        k = max(i for i, h in enumerate(H) if h[0] <= tt + 1e-6)
        return cell_key[H[k][1]]

    # dynamics (dB): mp return under the city, mf street, the build from the square cut, ff climax, release
    dyn = ramp([(R, 2.0), (street - 0.3, 2.0), (street, 1.0), (ta, 1.0), (sq, -1.5), (sqi, 2.0),
                (clx - 0.1, 3.0), (clx, 4.0), (cos - 0.4, 4.0), (cos + 0.3, 1.0), (title, -4.0), (lastc, -7.0),
                (end, -8.0)])

    # ---------------------------------------------------------------- pedal 16' + 8' (32' resultant at the cadence)
    bass = [(R, "D"), (street, "G"), (t8, "Bb"), (t10, "C"), (t12, "A"), (sq, "Bb"), (t19, "G"), (t21, "A"), (rh, "G"),
            (sqi, "A"), (clx, "D")]
    for i, (t0, pc) in enumerate(bass):
        t1 = bass[i + 1][0] if i + 1 < len(bass) else end
        ret = t0 == R
        kw = dict(align=False, attack=0.7) if ret else dict(attack=0.05)
        g16 = -12 if t0 < sq else (-13 if t0 < clx else -7)
        oc = "2" if pc == "C" else "1"
        e16 = S.note("organ", "ped16", pc + oc, t0, (min(t1, title) if t0 == clx else t1) - t0 + 0.04, g16, 0.0, sp,
                     release=0.3 if t0 == clx else 0.1, env=dyn, role="pedal 16'", **kw)
        S.note("organ", "ped8", pc + str(int(oc) + 1), t0, t1 - t0 + (0.0 if t1 == end else 0.04), g16 - 4, 0.0, sp,
               release=0.2 if t1 == end else 0.1, env=dyn, role="pedal 8'", **kw)
        if t0 in (sqi, clx):   # the 32' resultant: the fifth ABOVE the 16' note (10 2/3')
            S.note("organ", "ped16", e16["midi"] + 7, t0, e16["dur"], g16 - 8, 0.0, sp, attack=0.05, release=0.3,
                   env=dyn, role="32' resultant (fifth above)")
    S.lock("return", "start", "organ", f"the music returns on '{cue.return_key}': an open fifth D-A swells in "
                                       "(natural attacks), mp, under the city")

    # ---------------------------------------------------------------- the return: open fifth, strings + flutes
    sw = dict(space=sp, align=False, release=0.1, env=dyn)
    for inst, p, g, pan, a in (("vc_sus", "D3", -13, 0.3, 0.9), ("vc_sus", "A3", -14, 0.2, 1.0),
                               ("cb_sus", "D2", -14, 0.45, 1.1)):
        S.note("strings", inst, p, R, street - R + 0.08, g, pan, layer=1, attack=a, role="open fifth (strings)", **sw)
    S.chords("organ", "ged", [(R, ["D3", "A3", "D4", "A4"])], street + 0.03, -15, sp, pan=(-0.3, 0.3), attack=0.8,
             release=0.2, env=dyn, align=False, role="8' flutes (open fifth)")
    # the pulse: three-note cells in the violas (spiccato), from one beat after the return
    cells(S, W, 1, 14, chord_at, -18, -12, env=dyn)
    # timpani: a roll under the pilaster wipe, landing on the street downbeat
    pil = cue["pilaster1"]
    S.note("perc", "timproll", "D3", pil, street - pil - 0.03, -18, 0.08, sp, layer=5, attack=0.004, release=0.02,
           env=ramp([(pil, 0), (street - 0.05, 8)]), role="timpani roll (pilaster)")
    S.note("perc", "timp", "G2", street, 3.0, -8, 0.08, sp, layer=3, release=0.5, role="timpani (street)")
    S.lock("pilaster1", "onset", "perc", "timpani roll under the pilaster wipe")
    S.lock("street", "onset", "perc", "downbeat: G major (timpani G), the theme on B begins as the street opens")

    # ---------------------------------------------------------------- the street: the theme on B (violins I)
    S.line("strings", "vln_sus", [("B4", 3), ("C#5", 1), ("D5", 2), ("G5", 4)], W, 4, -10, -0.3, sp, layer=2,
           attack=0.08, release=0.25, overlap=0.08, gains=[0, -0.5, 0.5, 1.5], first=dict(attack=0.03), last_end=ta + 0.3,
           env=dyn, role="theme on B (violins I)")
    S.themes.append(dict(t=round(street, 3), first="B", voice="violins I", form="window form B-C#-D-G (sigh withheld)"))
    S.line("strings", "vln_sus", [("G4", 3), ("A4", 1), ("F4", 2), ("E4", 4)], W, 4, -14, -0.15, sp, layer=1,
           attack=0.15, release=0.25, overlap=0.08, last_end=ta + 0.3, env=dyn, role="violins II")
    S.chords("strings", "vc_sus", [(street, ["G2", "D3"]), (t7, ["G2", "E3"]), (t8, ["Bb2", "F3"]), (t10, ["C3", "G3"]),
                                   (t12, ["A2", "E3"])], sq + 0.04, -12, sp, pan=(0.25, 0.35), attack=0.12, release=0.15,
             layer=2, env=dyn, role="celli")
    S.chords("strings", "cb_sus", [(street, ["G1"]), (t8, ["Bb1"]), (t10, ["C2"]), (t12, ["A1"])], sq + 0.04, -13, sp,
             pan=(0.4, 0.4), attack=0.12, release=0.15, layer=2, env=dyn, role="contrabass")
    S.chords("organ", "ged", [(street, ["G3", "B3", "D4"]), (t7, ["A3", "C#4", "E4"]), (t8, ["Bb3", "D4", "F4"]),
                              (t10, ["C4", "E4", "G4"]), (t12, ["A3", "C#4", "E4", "G4"])], sq + 0.03, -16, sp,
             pan=(-0.3, 0.3), attack=0.1, release=0.15, env=dyn, role="8' flutes")

    # ---------------------------------------------------------------- the run under his turn: A7 arpeggio
    run = ["A3", "C#4", "E4", "G4", "A4", "C#5", "E5", "G5"]
    nrun = len(run)
    w_ = 0.9 ** np.arange(nrun + 1)
    tt_run = ta + np.concatenate([[0], np.cumsum(w_)])[:nrun] * (sq - ta) / w_.sum()
    for k, (p, t0) in enumerate(zip(run, tt_run)):
        g = -15 + 3.0 * k / (nrun - 1) + (1.5 if k == 0 else 0.0)
        for inst, d_oct, dg, pan in (("vln_spic", 0, 0, -0.25), ("va_spic", -12, -2, 0.15), ("vc_spic", -12, -3, 0.3)):
            if inst == "va_spic" and N(p) - 12 < N("C3"):
                continue
            S.note("strings", inst, N(p) + d_oct, t0, 0.22, g + dg, pan, sp, layer=2, attack=0.002, release=0.06,
                   role="rising run (A7)")
    S.lock("turn_away", "onset", "strings", "a rising A7 arpeggio (spiccato) starts under his turn")

    # ---------------------------------------------------------------- the build: deceptive Bb at the square cut
    build = ramp([(sq, -3.5), (t19, -3.0), (rh, -2.0), (sqi - 0.05, -0.5), (sqi + 0.3, 1.0), (clx - 0.05, 1.5)])
    S.note("perc", "timp", "Bb2", sq, 2.6, -10.5, 0.08, sp, layer=4, release=0.4, role="timpani (square downbeat)")
    for inst, p, g, pan in (("vc_spic", "Bb2", -12, 0.3), ("vc_spic", "F3", -14, 0.25), ("cb_pizz", "Bb1", -11, 0.45)):
        S.note("strings", inst, p, sq, 0.3, g, pan, sp, layer=2, attack=0.002, release=0.15,
               role="square downbeat (low strings, short)")
    S.lock("square_cut", "onset", "perc", "deceptive cadence on Bb, dark (timpani, low brass, low strings): the "
                                          "casement creaks through it")
    horns(S, [("D3", 1.5), ("E3", 0.5), ("F3", 1), ("Bb3", 2), ("A3", 1), ("B3", 1.5), ("C#4", 0.5), ("D4", 3)],
          W, 16, -6.5, 3, pan=-0.2, space=sp, n_from=1, n_to=4, grow=ramp([(sq, -12), (t19, -4), (rh, 0)]),
          attack=0.04, release=0.12, overlap=0.05, env=build, gains=[0, -0.5, 0, 1, 0, 0.5, 0.5, 1.5],
          first=dict(attack=0.015), last_end=clx + 0.03, role="theme (horns)")
    S.themes.append(dict(t=round(sq, 3), first="D", voice="horns", form="minor (the kitchen theme) over Bb Gm A"))
    S.themes.append(dict(t=round(rh, 3), first="B", voice="horns + violins II", form="window form, sigh resolves at "
                                                                                     "the climax"))
    tb = S.chords("brass", "otbn", [(sq, ["Bb2", "F3"]), (t19, ["G2", "D3"]), (t21, ["A2", "E3"]), (rh, ["G2", "D3"]),
                                    (t24, ["G2", "D3", "Bb3"]), (sqi, ["A2", "E3", "G4"])], clx + 0.03, -8, sp,
                  pan=(0.25, 0.4), attack=0.05, release=0.12, layer=4, env=build, role="trombones")
    for e in tb:
        e.update(pool=["otbn", "tbn"], player=0)
    S.line("strings", "vln_sus", [("Bb5", 2), ("A5", 1)], W, 19, -10, -0.42, sp, layer=2, attack=0.1, release=0.1,
           overlap=0.15, env=build, role="violins I")
    S.note("strings", "vln_trem", "A5", rh, clx - rh + 0.03, -11, -0.42, sp, layer=2, attack=0.3, release=0.05,
           env=lambda tt: build(tt) * ramp([(rh, -3), (sqi, 0), (clx, 2)])(tt), role="violins I (A5 tremolo, the "
                                                                                    "dominant held)")
    S.line("strings", "vln_sus", [("Bb4", 2), ("A4", 1), ("B4", 1.5), ("C#5", 0.5), ("D5", 1), ("G5", 2)], W, 19, -11,
           -0.22, sp, layer=2, attack=0.08, release=0.1, overlap=0.06, last_end=clx + 0.03, env=build,
           role="violins II")
    S.chords("strings", "vc_sus", [(sq, ["Bb2", "F3"]), (t19, ["G2", "D3"]), (t21, ["A2", "E3"]), (rh, ["G2", "D3"]),
                                   (t235, ["G2", "E3"]), (t24, ["G2", "D3"]), (sqi, ["A2", "E3"])], clx + 0.03, -10,
             sp, pan=(0.25, 0.35), attack=0.06, release=0.1, layer=3, env=build, role="celli")
    S.chords("strings", "cb_sus", [(sq, ["Bb1"]), (t19, ["G1"]), (t21, ["A1"]), (rh, ["G1"]), (sqi, ["A1"])],
             clx + 0.03, -11, sp, pan=(0.4, 0.4), attack=0.06, release=0.1, layer=3, env=build, role="contrabass")
    S.chords("organ", "ged", [(sq, ["Bb3", "D4", "F4"]), (t19, ["G3", "Bb3", "D4"]), (t21, ["A3", "C#4", "E4"]),
                              (rh, ["G3", "B3", "D4"]), (t235, ["A3", "C#4", "E4"]), (t24, ["G3", "Bb3", "D4"]),
                              (sqi, ["A3", "D4", "E4", "G4"])], clx + 0.03, -21, sp, pan=(-0.3, 0.3), attack=0.06,
             release=0.1, env=build, role="8' flutes")
    cells(S, W, 18, 26.5, chord_at, -14, -10, env=build)
    S.note("perc", "timp", "G2", rh, 2.6, -8, 0.08, sp, layer=4, release=0.4, role="timpani (red houses)")
    S.note("perc", "timproll", "A2", sqi, clx - sqi - 0.03, -13, 0.08, sp, layer=5, attack=0.004, release=0.02,
           env=ramp([(sqi, 0), (clx - 0.05, 8)]), role="timpani roll (into the climax)")
    S.lock("red_houses", "onset", "brass", "the window form of the theme (B - C# - D) as the red houses swing in")
    S.lock("square_in", "onset", "strings", "A7sus4 (the sus4 of bell2 returns), G held, timpani roll: the Castle "
                                            "Square appears")

    # ---------------------------------------------------------------- CLIMAX: D major, the first F sharp
    rel_s = ramp([(clx, 0), (cos - 0.6, 0), (cos - 0.1, -6), (title, -14), (title + 1.0, -40)])
    S.chords("organ", "open", [(clx, ["D3", "A3", "D4", "F#4", "A4", "D5", "F#5"]), (cos, ["D3", "A3", "D4", "F#4",
                                                                                          "A4", "D5"]),
                               (title, ["D3", "G3", "B3", "D4"]), (lastc, ["D3", "D4", "F#4", "A4"])], end, -6.5, sp,
             pan=(-0.4, 0.4), attack=0.03, release=0.2,
             env=ramp([(clx, 0), (cos - 0.6, 0), (cos - 0.1, -6), (title - 0.1, -14), (title + 0.4, -15),
                       (lastc, -16), (end, -17)]), role="full organ (open plenum) -> principal")
    dur_b = brass_off - 0.4 - clx
    for p, n_, g in (("D4", 2, -4.5), ("A3", 1, -6.5), ("F#3", 1, -7.5)):
        section(S, p, clx, dur_b, g, n_, ["horn"], 3, pan=-0.2, space=sp, attack=0.02, release=0.4, role="climax (horns)")
    for p, g in (("D3", -6), ("A3", -7.5), ("D4", -8), ("F#4", -7)):
        section(S, p, clx, dur_b, g, 1, ["otbn", "tbn"], 4, pan=0.3, space=sp, attack=0.02, release=0.4,
                role="climax (trombones)")
    S.note("strings", "vln_sus", "D6", clx, cos - 0.3 - clx, -6, -0.45, sp, layer=2, attack=0.02, release=0.2,
           role="climax: violins I D6 (the highest forte note)")
    for inst, p, g, pan, lay in (("vln_sus", "F#5", -8, -0.35, 2), ("vln_sus", "A5", -9.5, -0.3, 2),
                                 ("va_sus", "A4", -9, 0.12, 2), ("va_sus", "D4", -9.5, 0.12, 2),
                                 ("vc_sus", "D3", -8.5, 0.3, 3), ("vc_sus", "A3", -9.5, 0.25, 3),
                                 ("cb_sus", "D2", -9.5, 0.45, 3)):
        S.note("strings", inst, p, clx, title + 1.0 - clx, g, pan, sp, layer=lay, attack=0.02, release=0.4,
               env=rel_s, role="climax / release (strings)")
    S.note("perc", "timp", "D3", clx, 5.0, -2.0, 0.05, sp, layer=4, release=0.8, role="timpani (climax)")
    S.note("perc", "timp", "A2", clx, 4.0, -6.0, 0.15, sp, layer=4, release=0.8, role="timpani (climax)")
    S.lock("climax", "onset", "perc", "D MAJOR (the first F sharp), the first full organ, violins A5 -> D6, ff")
    S.lock("cup_on_sill", "gone", "brass", "the brass has left before the cup touches the sill (50 dB under its "
                                           "climax level)")

    # ---------------------------------------------------------------- release: the theme in major on the principal
    e5 = cos + 0.3
    f5 = max(e5 + 0.25, title - 0.3)
    mel = [(e5, "E5", -1.0), (f5, "F#5", -0.5), (title, "B5", 0.5), (lastc, "A5", 0.0)]
    for i, (t0, p, g) in enumerate(mel):
        t1 = mel[i + 1][0] - 0.04 if i + 1 < len(mel) else end
        S.note("organ", "open", p, t0, t1 - t0, -14 + g, -0.15, sp, attack=0.03,
               release=0.2 if i == len(mel) - 1 else 0.05, env=ramp([(e5, -1), (title, 0), (end, -2)]),
               role="principal (the theme in major)")
    S.themes.append(dict(t=round(e5, 3), first="E (D in the climax chord)", voice="principal",
                         form="major: D-E-F#-B | A"))
    S.lock("title_in", "onset", "organ", "G/D, the plagal amen, principal B5 as the word appears")
    S.lock("last_chord", "onset", "organ", "the last D major chord, principal A5: the falling step at last")
    S.lock("end", "release", "all", "the last chord released on the cut to black")
    S.derived.update(brass_off=round(brass_off, 3))

    bd = [
        (15, 0, "3/4", "D5 (open fifth)", "-", f"music_return ({cue.return_key}): celli, contrabass and 8' flutes "
                                               "swell in, mp; viola spiccato cells (root-2nd-5th) from beat 2"),
        (16, 3, "3/4", "D5", "-", "timpani roll under the pilaster"),
        (17, 4, "3/4", "G", "violins I B4 (dotted half)", "street: timpani G, the theme on B; mf under the city"),
        (18, 7, "3/4", "A/G -> Bb", "C#5 (q) D5 (h)", "Bb: the kitchen's chord, borrowed from D minor"),
        (19, 10, "3/4", "C -> A7", "G5 (tied)", "C (bVII) -> A7: the G is the seventh and waits to fall to F#"),
        (20, 14, "free", "A7", "A7 arpeggio", "turn_away: a rising spiccato arpeggio, accelerating, to the cut"),
        (21, 16, "3/4", "Bb (deceptive)", "horns D3 (q.) E3 (e) F3 (q)", "square: deceptive cadence on Bb, dark: the "
                                                                         "kitchen theme in the horns"),
        (22, 19, "3/4", "Gm -> A", "Bb3 (h) A3 (q); violins Bb5 A5", "the sigh in the horns and violins; the horn "
                                                                    "section fills in; viola cells resume"),
        (23, 22, "3/4", "G -> A/G -> Gm", "B3 (q.) C#4 (e) D4 (q)", "red houses: the window form; violins I hold A5 "
                                                                   "(tremolo); IV -> iv over G"),
        (24, 25, "2/4", "A7sus4 (G/A)", "D4 held; G4/G5 inside", "square_in: the sus4 of bell2 returns; timpani roll "
                                                                "on A; 32' pedal"),
        (25, 27, "free", "D major", "violins D6, F#5", "CLIMAX: the first F sharp; full organ; horns, trombones, "
                                                       "timpani D+A; brass gone before cup_on_sill"),
        (26, "title_in", "free", "G/D (plagal)", "principal E5 F#5 -> B5", "the organ alone (principal, box closing)"),
        (27, "last_chord", "free", "D major", "principal A5", "the falling step on the last chord; bell4 rings inside "
                                                              "it; released on 'end'"),
    ]
    for n, b, meter, harm, mel_, what in bd:
        if isinstance(b, str):
            S.bars.append(dict(bar=n, map=None, beat=None, t=round(cue[b], 3), meter=meter, harmony=harm, melody=mel_,
                               what=what, locked_to=b))
        else:
            S.bar(n, W, b, meter, harm, mel_, what)
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
                    and not e.get("skip") and e.get("align", True)):
                e["max_pre"] = min(e.get("max_pre", ARRIVAL_PRE_S) if e.get("max_pre") is not None else ARRIVAL_PRE_S,
                                   ARRIVAL_PRE_S)
                e["attack"] = min(max(e.get("attack", 0.004), 0.004), 0.03)
                e["arrival"] = L_["key"]
    # contract checks: nothing sounds in the silence; no F sharp before the climax (D minor indoors, no third
    # outdoors until the climax)
    for e in S.E:
        if e["space"] == "in" and e["t"] > cue["latch"]:
            raise AssertionError(f"indoor event after the latch: {e}")
        if e["space"] == "out" and e["t"] < cue["return"] - 1e-6:
            raise AssertionError(f"outdoor event before the return: {e}")
    fsharp = [e for e in S.E if e["t"] < cue["climax"] - 0.03 and int(round(e["midi"])) % 12 == FS]
    if fsharp:
        raise AssertionError(f"F sharp before the climax: {fsharp[:3]}")
    return S, K, W


# ============================================================================= rendering
def render_note3(inst, midi, dur, layer=None, attack=0.004, release=0.08, skip=0.0, align=True, max_pre=None,
                 smp=None):
    """compose.render_note with two additions: `smp` forces a given sample file (brass sections) and align=False
    places the sample's physical start (not its attack point) on the event, so the natural attack rises after it."""
    s = smp if smp is not None else inst.pick(midi, layer)
    ratio = 2 ** ((midi - s.meas) / 12)
    y, info = C.resampled(s, ratio)
    if skip > 0:
        begin, pre = int(skip * SR), 0
    else:
        begin, pre = 0, (info["att"] if align else 0)
        if max_pre is not None and pre > int(max_pre * SR):
            begin, pre = pre - int(max_pre * SR), int(max_pre * SR)
    need = pre + int(round((dur + release) * SR))
    seg = y[begin:]
    if len(seg) < need:
        if inst.loopable:
            seg = C.loop_extend(seg, info["s0"] - begin, info["s1"] - begin, need, tag=f"{inst.name} {NAME(midi)}")
        else:
            seg = np.concatenate([seg, np.zeros((need - len(seg), 2), np.float32)])
    seg = seg[:need].copy()
    env = np.ones(need, np.float32)
    na = max(int(attack * SR), int(0.002 * SR))
    env[: min(na, need)] *= raised_cos(na)[: min(na, need)]
    r0 = pre + int(round(dur * SR))
    nr = need - r0
    if nr > 0:
        env[r0:] *= raised_cos(nr, rising=False)
    return seg * env[:, None], pre


def swell_box(cue):
    pts = [(0.0, 0.2), (cue["walk"], 0.3), (cue["look1"], 0.5), (cue["kettle_click"], 0.4), (cue["stream"], 0.35),
           (cue["spout_out"], 0.45), (cue["look2"], 0.6), (cue["cup_cut"], 0.25), (cue["pour"], 0.3),
           (cue["slow2_end"], 0.4), (cue["bell2"], 0.5), (cue["latch"], 0.5), (cue["return"], 0.55),
           (cue["street"], 0.65), (cue["square_cut"], 0.7), (cue["square_in"], 0.85), (cue["climax"], 1.0),
           (cue["cup_on_sill"], 0.9), (cue["title_in"], 0.5), (cue.duration, 0.5)]
    return [p[0] for p in pts], [p[1] for p in pts]


def render3(lib, events, n, cue):
    pad = int(6.0 * SR)
    buses = {}
    used = {}
    R = cue["return"]
    bypath = {}

    def bus(k):
        if k not in buses:
            buses[k] = np.zeros((n + pad, 2), np.float32)
        return buses[k]

    for i, e in enumerate(events):
        if e.get("drop"):
            continue
        inst = lib[e["inst"]]
        g = e.get("g", 0.0)
        if inst.kind == "timp":
            g += TIMP_REF.get(e["inst"], 0.0)
        max_pre = e.get("max_pre")
        if e["space"] == "out":   # nothing before the return
            room = e["t"] - R
            max_pre = room if max_pre is None else min(max_pre, room)
            max_pre = max(0.0, max_pre) if room < 0.6 else max_pre
        smp = None
        if e.get("smp"):
            if e["inst"] not in bypath:
                bypath[e["inst"]] = {s.path: s for s in inst.samples}
            smp = bypath[e["inst"]][e["smp"]]
        else:
            rkey = (round(e["midi"] + e.get("detune", 0.0) / 100.0, 2), e.get("layer"))
            if "_rr" in e:
                inst.rr_count[rkey] = e["_rr"]
            else:
                e["_rr"] = inst.rr_count.get(rkey, 0)
        sig, pre = render_note3(inst, e["midi"] + e.get("detune", 0.0) / 100.0, e["dur"], layer=e.get("layer"),
                                attack=e.get("attack", 0.004), release=e.get("release", 0.08),
                                skip=e.get("skip", 0.0), align=e.get("align", True), max_pre=max_pre, smp=smp)
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
        used.setdefault(e["inst"], set()).add((round(e["midi"], 3), e.get("layer"), e.get("smp")))
        if i % 250 == 0:
            log(f"  rendered {i}/{len(events)} notes")
    return buses, used


def hall_ir(seed=2026, length=4.5, predelay=0.012, lr_mix=0.25):
    """Short bright hall for the open window (same construction as compose.church_ir, shorter decay):
    RT60 2.2-2.6 s in the low mids, 0.5 s above 11 kHz; the two channels share part of their tail (lr_mix) so the
    hall does not decorrelate the image."""
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
    ir = np.stack([ir[:, 0] + lr_mix * ir[:, 1], ir[:, 1] + lr_mix * ir[:, 0]], axis=1)
    ir /= np.sqrt(np.sum(ir ** 2) / 2)
    ir *= raised_cos(nn, rising=False)[:, None] ** 0.3
    return ir.astype(np.float32), dict(rt60_bands_s=dict(zip(["<90", "90-180", "180-355", "355-710", "710-1.4k",
                                                              "1.4-2.8k", "2.8-5.6k", "5.6-11k", ">11k"], rts)),
                                       predelay_s=predelay, length_s=length, lr_mix=lr_mix,
                                       lr_corr=round(float(np.corrcoef(ir[:, 0], ir[:, 1])[0, 1]), 3))


def width(x, w):
    m = 0.5 * (x[:, 0] + x[:, 1])
    s = 0.5 * (x[:, 0] - x[:, 1]) * w
    return np.stack([m + s, m - s], axis=1).astype(np.float32)


def bass_mono(x, fc=120.0):
    """The side signal high-passed at fc (zero phase): everything below fc is mono."""
    m = 0.5 * (x[:, 0] + x[:, 1])
    s = 0.5 * (x[:, 0] - x[:, 1])
    s = s - sosfiltfilt(butter(4, fc, btype="low", fs=SR, output="sos"), s).astype(np.float32)
    return np.stack([m + s, m - s], axis=1).astype(np.float32)


SPACE = dict(
    inside=dict(send=0.62, dry=0.72, pre_lowpass_hz=7000, shelf_hz=3000, shelf_cut=0.55, width=0.42),
    outside=dict(send=0.20, dry=1.0, width=0.62, bass_mono_hz=120.0),
)
GATE_FADE_S = 0.012
# balance per stem and space (dB): the organ leads indoors; outdoors the brass carries the build
STEM_TRIM = {("organ", "in"): 5.0, ("strings", "in"): 0.0, ("brass", "in"): -2.0, ("perc", "in"): -2.0,
             ("organ", "out"): 4.0, ("strings", "out"): 0.0, ("brass", "out"): 0.0, ("perc", "out"): -4.0}
HOLE = dict(lo=1000.0, hi=9000.0, db=-9.0)   # a gentle dip in the music around the cup on the sill


def inside_fader(cue):
    """The kitchen is heard from a distance: a fader on everything indoors (dB) that keeps it pp-mp; the A sus4 on
    LOOK 3 is forte for the kitchen but stays well under the window's build."""
    return C.ramp([(0.0, -5.0), (cue["stream"] - 1.0, -5.0), (cue["stream"], -6.5), (cue["cup_cut"], -6.5),
                   (cue["cup_cut"] + 0.3, -5.0), (cue["pour"], -5.5), (cue["slow2_end"], -7.0),
                   (cue["server_out"], -10.5), (cue["bell2"], -11.0), (cue["latch"], -11.5)])


def duck_curve(n_ab, a, points):
    """Gain curve on samples a..a+n_ab from (time, dB) points (1.0 outside)."""
    ts = [p[0] for p in points]
    ds = [10 ** (p[1] / 20) for p in points]
    return np.interp((a + np.arange(n_ab)) / SR, ts, ds).astype(np.float32)[:, None]


def mixdown(buses, n, cue, church, hall, breath):
    hp = butter(4, 28.0, btype="high", fs=SR, output="sos")
    lp_in = butter(2, SPACE["inside"]["pre_lowpass_hz"], btype="low", fs=SR, output="sos")
    sh_in = butter(2, SPACE["inside"]["shelf_hz"], btype="high", fs=SR, output="sos")
    fx_sos = {"sord": butter(2, 2200, btype="low", fs=SR, output="sos")}
    bx_t, bx_v = swell_box(cue)
    dark = butter(2, 1400, btype="low", fs=SR, output="sos")
    latch, R, end, dur = cue["latch"], cue["return"], cue["end"], cue.duration
    il, iR = int(round(latch * SR)), int(round(R * SR))
    ig = int(round((latch + GATE_FADE_S) * SR))
    br0, br1 = breath
    kc, cup, pour = cue["kettle_click"], cue["cup_cut"], cue["pour"]
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
            # the room's tail is drawn down where the picture asks for a hush: subito pp on the mug (until the pour),
            # the kettle click (strings and pendulum stop), the breath before bell 2
            pts = [(0.0, 0), (kc, 0), (kc + 0.06, -10 if stem != "strings" else -12), (kc + 0.9, -10),
                   (kc + 2.0, 0), (cup, 0), (cup + 0.06, -14), (pour - 0.3, -14), (pour + 1.0, 0), (br0 - 0.01, 0),
                   (br0 + 0.06, -20), (br1 - 0.02, -20), (br1 + 0.3, 0), (dur, 0)]
            duck = duck_curve(b - a, a, sorted(pts))
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
            ie, i_off = int((end + 0.25) * SR), int((dur - 0.32) * SR)
            wt = np.ones(n - a, np.float32)
            wt[max(0, ie - a): i_off - a] = raised_cos(i_off - ie, rising=False) ** 1.5
            wt[i_off - a:] = 0.0
            seg = SPACE["outside"]["dry"] * xs + SPACE["outside"]["send"] * wet * wt[:, None]
            y[a:n] = width(seg, SPACE["outside"]["width"])
        y[: first] = 0.0
        stems[stem] += y
    tt = np.arange(n) / SR
    # room for bell 4 (a D bell): a 300-900 Hz dip on all music from just before the bell to the end
    bp = butter(2, [300, 900], btype="band", fs=SR, output="sos")
    depth = 1 - 10 ** (-8 / 20)
    w = np.interp(tt, [cue["bell4"] - 0.8, cue["bell4"] - 0.2, dur], [0, depth, depth]).astype(np.float32)[:, None]
    # a hole for the cup on the sill (the brass has already gone): HOLE dB in HOLE lo..hi around the event
    cs_ = cue["cup_on_sill"]
    hb = butter(2, [HOLE["lo"], HOLE["hi"]], btype="band", fs=SR, output="sos")
    hd = 1 - 10 ** (HOLE["db"] / 20)
    wh = np.interp(tt, [cs_ - 0.25, cs_ - 0.08, cs_ + 0.35, cs_ + 0.7], [0, hd, hd, 0]).astype(np.float32)[:, None]
    for s in stems:
        stems[s] = stems[s] - sosfiltfilt(bp, stems[s], axis=0).astype(np.float32) * w
        stems[s] = stems[s] - sosfiltfilt(hb, stems[s], axis=0).astype(np.float32) * wh
        stems[s] = bass_mono(stems[s], SPACE["outside"]["bass_mono_hz"])
    # the indoor silence and the final silence are exact zeros
    i_silent = int(round((dur - 0.3) * SR))
    for s in stems:
        stems[s][ig:iR] = 0.0
        stems[s][i_silent - int(0.02 * SR): i_silent] *= raised_cos(int(0.02 * SR), rising=False)[:, None]
        stems[s][i_silent:] = 0.0
    return stems


def master_open(stems, tp_target=-2.3, max_gr_db=0.9):
    """No loudness target: one static gain so that the true peak lands on tp_target with a safety limiter that may
    take at most max_gr_db (the climax keeps its transient); the SAME gain curve on every stem."""
    names = list(stems)
    mix = sum(stems[s] for s in names).astype(np.float64)
    tp0 = C.true_peak_db(mix)
    G = 10 ** ((tp_target - tp0 + max_gr_db) / 20)
    hist = []
    for it in range(6):
        lim = C.limiter_env(mix * G, tp_target)
        y = mix * (G * lim)[:, None]
        tp = C.true_peak_db(y)
        gr = float(-dbv(lim.min()))
        hist.append(dict(iter=it, static_gain_db=round(dbv(G), 3), true_peak_dbtp=round(tp, 3), max_gr_db=round(gr, 2)))
        if tp <= -2.05 and gr <= max_gr_db + 0.05:
            break
        G *= 10 ** (min(-2.05 - tp, max_gr_db - gr, 0.0) / 20 - 0.002)
    total = (G * lim).astype(np.float32)[:, None]
    grc = -20 * np.log10(np.maximum(lim, 1e-9))
    info = dict(static_gain_db=round(dbv(G), 2), max_gain_reduction_db=round(float(grc.max()), 2),
                seconds_with_gr_over_0_1db=round(float((grc > 0.1).sum()) / SR, 3), gr_regions_s=C._regions(grc > 0.1))
    return {s: stems[s] * total for s in names}, hist, info


def quantise24(x):
    return (np.round(np.clip(x, -1.0, 1.0 - 2 ** -23) * 2 ** 23) / 2 ** 23).astype(np.float64)


# ============================================================================= analysis
def k_weight(x):
    m = pyln.Meter(SR)
    y = x.astype(np.float64)
    for f in m._filters.values():
        y = f.apply_filter(y)
    return y


class Loud:
    """K-weighted energy integrals: L(t0, t1) ungated LUFS of a span, M(t) momentary (400 ms, centred)."""

    def __init__(self, x):
        y = k_weight(x)
        self.cs = np.concatenate([[0.0], np.cumsum((y ** 2).sum(1))])
        self.n = len(x)

    def L(self, t0, t1):
        a, b = int(max(t0, 0) * SR), int(min(t1, self.n / SR) * SR)
        return float(-0.691 + 10 * np.log10((self.cs[b] - self.cs[a]) / max(b - a, 1) + 1e-20))

    def M(self, t):
        return self.L(t - 0.2, t + 0.2)

    def grid(self, step=0.01):
        tt = np.arange(0.2, self.n / SR - 0.2, step)
        a = ((tt - 0.2) * SR).astype(int)
        b = a + int(0.4 * SR)
        return tt, -0.691 + 10 * np.log10((self.cs[b] - self.cs[a]) / (b - a) + 1e-20)


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
        out.append(-0.691 + 10 * np.log10((cs[a + W] - cs[a]) / W + 1e-20))
    return centres, np.array(out)


_HP150 = butter(4, 150.0, btype="high", fs=SR, output="sos")


def env_db3(x, win=0.005):
    """RMS envelope in dB (float64, clamped: no NaN from rounding in the moving average)."""
    e = uniform_filter1d((np.asarray(x, np.float64) ** 2).mean(1), max(1, int(win * SR)))
    return 10 * np.log10(np.maximum(e, 0.0) + 1e-20)


def onset_measure(x, t, tol=0.06):
    """The arrival's onset: the strongest spectral-flux peak (log-mel, 150 Hz-12 kHz, hop 2.7 ms) within +-tol of
    the event, accepted if it stands at least 2x above the median flux of the surrounding second (salience)."""
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


def probe_onset(lib, events, key, stem, t0, n, cue):
    """The notes that make the arrival, rendered on their own (same samples, gains, envelopes) and summed DRY:
    onset = first time the 5 ms RMS reaches -12 dB of its peak (the placement convention). Dry, because a soft
    bowed entry heard through the 4.8 s church room reaches -12 dB of its (reverb-dominated) peak late: that is the
    room building up, not the note being late."""
    sub = [e for e in events if e.get("arrival") == key and stem in ("all", e["stem"]) and not e.get("drop")]
    if not sub:
        return None
    buses, _ = render3(lib, sub, n, cue)
    x = sum(b[:n] for b in buses.values())
    a, b = int((t0 - 0.3) * SR), int((t0 + 0.5) * SR)
    env = env_db3(x[a:b], 0.005)
    k = np.nonzero(env >= env.max() - 12.0)[0]
    return float(t0 - 0.3 + k[0] / SR) if len(k) else None


def release_time(x, t):
    """Where the level falls: the steepest 30 ms fall of the 10 ms RMS within -0.15..+0.3 s of the event, and the
    drop from the 0.1 s before to 0.1-0.2 s after it. (A first-3-dB-dip measure is fooled by the church room's
    natural decay of a diminuendo before the event.)"""
    e = env_db3(x, 0.01)
    a = int((t - 0.15) * SR)
    seg = e[a: int((t + 0.33) * SR)]
    k = int(0.03 * SR)
    fall = seg[:-k] - seg[k:]
    j = int(np.argmax(fall[: int(0.45 * SR)]))
    t_fall = (a + j + k // 2) / SR
    before = float(np.median(e[int((t - 0.1) * SR): int((t - 0.02) * SR)]))
    after = float(np.median(e[int((t + 0.1) * SR): int((t + 0.2) * SR)]))
    return dict(steepest_fall_at=round(t_fall, 4), fall_30ms_db=round(float(fall[j]), 1),
                drop_db=round(before - after, 1)), before


def tuning_test3(lib, used):
    """Isolated rendered notes (the very sample each brass player uses) measured with pYIN and by the partials' FFT."""
    import librosa
    rep = {}
    for name in sorted(used):
        inst = lib[name]
        byp = {s.path: s for s in inst.samples}
        rows = []
        seen = set()
        for m, layer, sp in sorted(used[name], key=lambda v: (v[0], v[1] or 0, v[2] or "")):
            if (m, layer, sp) in seen:
                continue
            seen.add((m, layer, sp))
            smp = byp.get(sp) if sp else None
            if inst.kind == "timp":
                roll = name == "timproll"
                sig, pre = render_note3(inst, m, 6.5 if roll else 2.0, layer=layer, release=0.1)
                f = C.timp_principal(sig.mean(1).astype(np.float64), SR, *(ROLL_WIN if roll else (0.12, 1.8)))
                rows.append(dict(note=NAME(m), layer=layer, cents=round(float(1200 * np.log2(f / hz(m))), 1),
                                 method="principal (1,1) mode"))
                continue
            sig, pre = render_note3(inst, m, 3.0, layer=layer, attack=0.004, release=0.05, smp=smp)
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
            rows.append(dict(note=NAME(m), layer=layer, file=os.path.basename(sp) if sp else None, cents=c,
                             cents_fft=cf))
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
        log(f"tuning {name}: {rep[name].get('worst_best_of_two_cents', rep[name].get('max_abs_cents'))} worst |c|")
    return rep


# ----------------------------------------------------------------------------- the story acceptance tests
EDGES3 = 1000 * 2 ** (np.arange(-10, 11) / 3)          # 20 third-octave bands, 99 Hz .. 10.1 kHz
CENT3 = np.sqrt(EDGES3[:-1] * EDGES3[1:])


def bands3(sig, t0, t1):
    a, b = int(t0 * SR), int(t1 * SR)
    s = sig[a:b] * np.hanning(b - a)
    P = np.abs(np.fft.rfft(s)) ** 2
    f = np.fft.rfftfreq(b - a, 1 / SR)
    return np.array([P[(f >= lo) & (f < hi)].sum() + 1e-20 for lo, hi in zip(EDGES3[:-1], EDGES3[1:])])


def resolve_t(v, cue):
    """'@key+0.5' / '@key-1' / number -> film time (the sound spec's notation)."""
    if isinstance(v, (int, float)):
        return float(v)
    m = re.match(r"@([A-Za-z0-9_]+)([+-][0-9.]+)?$", str(v))
    if not m or m.group(1) not in cue.ev:
        return None
    return cue.ev[m.group(1)] + (float(m.group(2)) if m.group(2) else 0.0)


def sound_inputs(cue):
    """The sound team's stems (mono) and the score gain its mix applies ("auto": the city sits N dB under the score
    around the climax). Returns None when the stems are not there."""
    try:
        st = {k: sf.read(os.path.join(SOUND_DIR, f"{k}.wav"), always_2d=True)[0].mean(1) for k in ("city", "bell", "foley")}
    except Exception as ex:   # noqa: BLE001
        return dict(error=f"sound stems not readable: {ex}")
    auto = dict(t0="@climax-0.5", t1="@climax+2.5", city_under_db=8.0, bus="city")
    try:
        sp = json.load(open(SOUND_SPEC))
        auto.update((sp.get("score") or {}).get("auto") or {})
    except Exception:   # noqa: BLE001
        pass
    rep = {}
    try:
        rep = json.load(open(os.path.join(SOUND_DIR, "sound_report.json")))
    except Exception:   # noqa: BLE001
        pass
    return dict(stems=st, auto=auto, report=rep)


def onset_rank(x, t, half=1.0):
    """The music editor's onset ranking: onset strength (log-mel 150 Hz-12 kHz of the 150 Hz-high-passed mono, 5 ms
    hop), the strongest value within +-80 ms of the event, ranked among the picked onset peaks within +-half s
    (0 = the strongest)."""
    import librosa
    a = max(0, int((t - half - 0.6) * SR))
    y = sosfilt(_HP150, x[a: int((t + half + 0.6) * SR)].mean(1)).astype(np.float32)
    hop = 240
    o = librosa.onset.onset_strength(y=y, sr=SR, hop_length=hop, n_mels=96, fmin=150, fmax=12000)
    to = a / SR + np.arange(len(o)) * hop / SR
    pk = librosa.util.peak_pick(o, pre_max=6, post_max=6, pre_avg=40, post_avg=40, delta=0.0, wait=20)
    w = np.abs(to - t) <= 0.08
    j = int(np.nonzero(w)[0][np.argmax(o[w])])
    near = pk[np.abs(to[pk] - t) <= half]
    rank = int(np.sum(o[near] > o[j] + 1e-9))
    return rank, round(float(to[j]), 3), round(float(o[j]), 2)


def story_qc(rd, st, S, cue, minfo, out_dir):
    """Every acceptance test of the music editor's review, measured on the delivered files."""
    ev = [e for e in S.E if not e.get("drop")]
    L = Loud(rd)
    tt, Mv = L.grid(0.01)
    clx, R, street, sq = cue["climax"], cue["return"], cue["street"], cue["square_cut"]
    out = {}

    def Mmax(t0, t1):
        w = (tt >= t0) & (tt <= t1)
        return float(Mv[w].max())

    # 1. the climax lands; the second half has a shape
    pre = (tt >= clx - 1.0) & (tt <= clx - 0.1)
    step = Mmax(clx, clx + 0.5) - float(np.mean(Mv[pre]))
    ig = int(np.argmax(Mv))
    cmax = Mmax(clx, clx + 2.0)
    wr = (tt >= R) & (tt < street)
    ks = []
    k = 0
    while sq + k <= clx - 0.2 + 1e-9:
        ks.append(round(L.M(sq + k), 2))
        k += 1
    dif = np.diff(ks)
    hi_pre = max(e["midi"] for e in ev if e["t"] < clx - 0.05)
    hi_clx = max(e["midi"] for e in ev if abs(e["t"] - clx) < 0.05)
    out["1_climax"] = dict(
        step_lu=round(step, 2), step_pass=bool(step >= 3.0),
        global_M_max=dict(lufs=round(float(Mv[ig]), 2), at_s=round(float(tt[ig]), 2),
                          pass_=bool(clx <= tt[ig] <= clx + 2.0)),
        limiter_max_gr_db=minfo["max_gain_reduction_db"], limiter_pass=bool(minfo["max_gain_reduction_db"] <= 1.0),
        return_street_median_M=round(float(np.median(Mv[wr])), 2), climax_max_M=round(cmax, 2),
        return_below_climax_lu=round(cmax - float(np.median(Mv[wr])), 2),
        return_pass=bool(float(np.median(Mv[wr])) <= cmax - 8.0),
        build_M_1s=ks, build_rise_lu=round(ks[-1] - ks[0], 2), build_max_step_down_lu=round(float(-dif.min()), 2) if len(dif) else 0,
        build_pass=bool(ks[-1] - ks[0] >= 5.0 and (len(dif) == 0 or dif.min() >= -1.5)),
        highest_pitch_before_climax=NAME(hi_pre), highest_pitch_at_climax=NAME(hi_clx),
        highest_pitch_pass=bool(hi_clx > hi_pre))
    o1 = out["1_climax"]
    o1["pass"] = bool(o1["step_pass"] and o1["global_M_max"]["pass_"] and o1["limiter_pass"] and o1["return_pass"]
                      and o1["build_pass"] and o1["highest_pitch_pass"])

    # 2. bell2 breath, the kitchen distant and dark
    kit = (tt >= cue["fade_up"]) & (tt < cue["latch"])
    kmax = float(Mv[kit].max())
    import librosa
    i0, i1 = int(cue["bell2"] * SR), int(cue["latch"] * SR)
    Sx = np.abs(librosa.stft(rd[i0:i1].mean(1).astype(np.float32), n_fft=4096, hop_length=2048)) ** 2
    fr = librosa.fft_frequencies(sr=SR, n_fft=4096)
    Ps = Sx.sum(1)
    cent = float((fr * Ps).sum() / Ps.sum())
    top_forte = max(e["midi"] for e in ev if e["space"] == "in" and e["t"] >= cue["slow2_end"])
    out["2_kitchen"] = dict(kitchen_M_max=round(kmax, 2), kitchen_pass=bool(kmax <= -17.0),
                            kitchen_below_climax_lu=round(cmax - kmax, 2),
                            centroid_bell2_latch_hz=round(cent, 1), centroid_pass=bool(cent <= 450.0),
                            top_note_forte_indoors=NAME(top_forte), top_note_pass=bool(top_forte <= N("A5")))
    out["2_kitchen"]["pass"] = bool(kmax <= -17.0 and cent <= 450.0 and top_forte <= N("A5"))

    # 3 + 1e + 2a. masking of the story sounds (the sound team's stems, the score at the gain their mix applies)
    snd = sound_inputs(cue)
    if "error" in snd:
        out["masking"] = dict(measured=False, reason=snd["error"])
    else:
        a = snd["auto"]
        t0a, t1a = resolve_t(a["t0"], cue), resolve_t(a["t1"], cue)
        m_ = pyln.Meter(SR)
        city2 = sf.read(os.path.join(SOUND_DIR, "city.wav"), always_2d=True)[0]
        Lm = m_.integrated_loudness(rd[int(t0a * SR): int(t1a * SR)])
        Lc = m_.integrated_loudness(city2[int(t0a * SR): int(t1a * SR)])
        gain = float(np.clip(Lc + float(a["city_under_db"]) - Lm, -24, 24))
        mus = rd.mean(1) * 10 ** (gain / 20)
        sx = snd["stems"]

        def ratio(stem, t0, t1, lo=None, hi=None):
            T, Mu = bands3(sx[stem], t0, t1), bands3(mus, t0, t1)
            r = 10 * np.log10(T / Mu)
            sel = np.ones(len(r), bool)
            if lo is not None:
                sel &= CENT3 >= lo
            if hi is not None:
                sel &= CENT3 <= hi
            return dict(broadband_db=round(float(10 * np.log10(T.sum() / Mu.sum())), 1),
                        bands_above=int(np.sum(r[sel] > 0)), bands_considered=int(sel.sum()),
                        best_band_hz=round(float(CENT3[sel][np.argmax(r[sel])]), 0),
                        best_band_db=round(float(r[sel].max()), 1))
        b2 = ratio("bell", cue["bell2"], cue["bell2"] + 0.4, 250, 2000)
        cs_ = cue["cup_on_sill"]
        cas = cue["casement"]
        rc = ratio("foley", cas, cas + 1.5, 1000, None)
        # the cup: where the cue sheet puts it, and where the sound team's last render actually put it
        cup_rows = {}
        el = {e.get("id"): e for e in snd["report"].get("elements", [])}
        sy = {s.get("id"): s for s in snd["report"].get("sync", [])}
        t_act = sy.get("cup_on_sill", {}).get("target")
        if t_act is None and "cup_on_sill" in el:
            t_act = el["cup_on_sill"].get("film_in")
        has_at_cue = float(np.abs(sx["foley"][int((cs_ - 0.03) * SR): int((cs_ + 0.25) * SR)]).max()) > 1e-6
        if has_at_cue:
            cup_rows["at_cue_sheet_time"] = dict(t=round(cs_, 3), **ratio("foley", cs_ - 0.03, cs_ + 0.25, 1000, None))
        elif t_act is not None:
            # the sound team's cup sound, moved to the cue-sheet time, against the music there
            a0, b0 = int((t_act - 0.03) * SR), int((t_act + 0.25) * SR)
            tmp = np.zeros_like(sx["foley"])
            c0 = int((cs_ - 0.03) * SR)
            tmp[c0: c0 + (b0 - a0)] = sx["foley"][a0:b0]
            T, Mu = bands3(tmp, cs_ - 0.03, cs_ + 0.25), bands3(mus, cs_ - 0.03, cs_ + 0.25)
            r = 10 * np.log10(T / Mu)
            sel = CENT3 >= 1000
            cup_rows["at_cue_sheet_time"] = dict(t=round(cs_, 3), note=f"the sound team placed the cup at "
                                                 f"{t_act:.3f}; its sound moved to the cue-sheet time",
                                                 bands_above=int(np.sum(r[sel] > 0)), bands_considered=int(sel.sum()),
                                                 broadband_db=round(float(10 * np.log10(T.sum() / Mu.sum())), 1))
        if t_act is not None and abs(t_act - cs_) > 0.05:
            cup_rows["at_sound_team_time"] = dict(t=round(t_act, 3),
                                                  **ratio("foley", t_act - 0.03, t_act + 0.25, 1000, None))
        city_a = ratio("city", R, R + 2.0)
        city_b = ratio("city", R, street)
        out["masking"] = dict(
            measured=True, score_gain_db=round(gain, 2), auto=dict(window=[round(t0a, 3), round(t1a, 3)],
                                                                   score_lufs=round(Lm, 2), city_lufs=round(Lc, 2),
                                                                   city_under_db=a["city_under_db"]),
            note="the score at the gain the sound mix's 'auto' rule gives it, WITHOUT the sound team's music ducks "
                 "(stricter); third-octave bands 99 Hz-10 kHz, Hann-windowed spans",
            bell2=dict(**b2, pass_=bool(b2["bands_above"] >= 3)),
            casement=dict(**rc, pass_=bool(rc["bands_above"] >= 3)),
            cup_on_sill={k_: dict(**v, pass_=bool(v["bands_above"] >= 3)) for k_, v in cup_rows.items()},
            city_return_2s=dict(**city_a, pass_=bool(city_a["broadband_db"] >= -1.0)),
            city_return_street=dict(**city_b, pass_=bool(city_b["broadband_db"] >= -3.0)))
        mk = out["masking"]
        mk["pass"] = bool(mk["bell2"]["pass_"] and mk["casement"]["pass_"] and mk["city_return_2s"]["pass_"] and
                          mk["city_return_street"]["pass_"] and all(v["pass_"] for v in mk["cup_on_sill"].values()))

    # 4. the brass: one file per player, short resampling, brass over the organ in the build
    shifts = {}
    for e in ev:
        if e.get("smp"):
            shifts.setdefault(e["inst"], []).append(abs(e["shift_st"]))
    groups = {}
    for e in ev:
        if e.get("pool"):
            groups.setdefault((int(round(e["midi"])), round(e["t"], 1)), []).append(e["smp"])
    dup = sum(1 for v in groups.values() if len(v) != len(set(v)))

    def bandlev(x, t0, t1, lo, hi):
        y = x[int(t0 * SR): int(t1 * SR)].mean(1).astype(np.float32)
        Z = np.abs(librosa.stft(y, n_fft=4096, hop_length=2048)) ** 2
        w = (fr >= lo) & (fr < hi)
        return float(10 * np.log10(Z[w].sum() / Z.shape[1] + 1e-20))
    bo = bandlev(st["brass"], sq, clx, 120, 500) - bandlev(st["organ"], sq, clx, 120, 500)
    out["4_brass"] = dict(groups_with_duplicate_file=dup, unique_files_pass=bool(dup == 0),
                          max_shift_semitones={k_: round(max(v), 2) for k_, v in shifts.items()},
                          horn_shift_pass=bool(max(shifts.get("horn", [0])) <= MAX_BRASS_SHIFT + 1e-6),
                          brass_minus_organ_120_500_square_climax_db=round(bo, 1), balance_pass=bool(bo >= 3.0))
    ob = out["4_brass"]
    ob["pass"] = bool(ob["unique_files_pass"] and ob["horn_shift_pass"] and ob["balance_pass"])

    # 5. no pure-tone moments; a melody early
    cup, pour = cue["cup_cut"], cue["pour"]
    top = [e for e in ev if e["inst"] not in ("ped16", "ped8") and e["t"] < pour - 0.3 and
           e["t"] + e["dur"] > cup + 0.3]
    org = st["organ"].mean(1)
    seg = org[int((cup + 0.3) * SR): int((pour - 0.3) * SR)]
    fa = hz(N("A4"))
    cents = []
    for k in range(0, len(seg) - int(0.5 * SR), int(0.25 * SR)):
        f = C.harmonic_f0(seg[k: k + int(0.5 * SR)].astype(np.float64), SR, fa, kmax=4)
        cents.append(1200 * np.log2(f / fa))
    bp = butter(4, [fa * 0.97, fa * 1.03], btype="band", fs=SR, output="sos")
    e20 = 10 * np.log10(uniform_filter1d(sosfiltfilt(bp, seg) ** 2, int(0.02 * SR)) + 1e-20)
    swing = float(np.percentile(e20, 99.5) - np.percentile(e20, 0.5))
    lc0, lc1 = cue["last_chord"] + 0.2, cue["end"] - 0.1
    mono = rd.mean(1)[int(lc0 * SR): int(lc1 * SR)]
    P = np.abs(np.fft.rfft(mono * np.hanning(len(mono)))) ** 2
    f = np.fft.rfftfreq(len(mono), 1 / SR)
    tot = P[f > 150].sum()
    notes = sorted({e["midi"] for e in ev if e["t"] < lc1 and e["t"] + e["dur"] > lc0 + 0.3 and hz(e["midi"]) >= 150})
    rows, ns = [], 0.0
    for mm in notes:
        fc = hz(mm)
        h1 = P[(f > fc * 0.985) & (f < fc * 1.015)].sum()
        h2 = P[(f > 2 * fc * 0.985) & (f < 2 * fc * 1.015)].sum()
        r = float(10 * np.log10((h2 + 1e-20) / (h1 + 1e-20)))
        if r < -20:
            ns += h1
        rows.append(dict(note=NAME(mm), h1_share=round(float(h1 / tot), 3), h2_minus_h1_db=round(r, 1)))
    last_mel = [e for e in ev if e.get("role", "").startswith("principal (the theme") and abs(e["t"] - cue["last_chord"]) < 0.01]
    first_mel = min(e["t"] for e in ev if "theme" in e.get("role", "") or "melody" in e.get("role", ""))
    cup_tv = (dict(removed=True, note="no voice above the pedal over the empty mug (cup_cut+0.3 .. pour-0.3)",
                   pass_=True) if not top else
              dict(removed=False, notes=sorted({NAME(e["midi"]) for e in top}),
                   pitch_cents_max_abs=round(float(np.max(np.abs(cents))), 2), level_swing_db=round(swing, 2),
                   pass_=bool(np.max(np.abs(cents)) <= 3.0 and swing <= 3.0)))
    out["5_timbre"] = dict(
        cup_top_voice=cup_tv,
        last_chord=dict(near_sine_share=round(float(ns / tot), 3), notes=rows, pass_=bool(ns / tot <= 0.40)),
        final_A=dict(note=NAME(last_mel[0]["midi"]) if last_mel else None,
                     pass_=bool(last_mel and int(round(last_mel[0]["midi"])) == N("A5"))),
        first_melodic_note_s=round(first_mel, 3), first_melody_pass=bool(first_mel <= 7.0))
    o5 = out["5_timbre"]
    o5["pass"] = bool(o5["cup_top_voice"]["pass_"] and o5["last_chord"]["pass_"] and o5["final_A"]["pass_"] and
                      o5["first_melody_pass"])

    # 6. the 32' resultant: no pedal note under the 16' root
    bad = []
    roots = [e for e in ev if e["space"] == "out" and e["role"] == "pedal 16'"]
    for e in ev:
        if e["space"] == "out" and e["inst"] in ("ped16", "ped8"):
            r_ = [x for x in roots if x["t"] <= e["t"] + 1e-6 < x["t"] + x["dur"]]
            if r_:
                root = max(r_, key=lambda x: x["t"])     # the root that has started latest (legato overlaps)
                if e["midi"] < root["midi"] - 1e-6:
                    bad.append(dict(t=round(e["t"], 3), note=NAME(e["midi"]), root=NAME(root["midi"])))
    out["6_pedal"] = dict(notes_below_root=bad, pass_=not bad)

    # 7. the return: natural attack, read from the cue sheet, no F# in 300-400 Hz early
    s_ = st["strings"]
    env = np.sqrt(uniform_filter1d((s_ ** 2).mean(1), int(0.01 * SR)))
    a_, b_ = int(R * SR), int((R + 0.9) * SR)
    ee = env[a_:b_]
    ref = ee.max()
    t10 = int(np.argmax(ee >= 0.1 * ref))
    t90 = int(np.argmax(ee >= 0.9 * ref))
    fs_early = [e for e in ev if int(round(e["midi"])) % 12 == FS and 300 <= hz(e["midi"]) <= 400 and
                e["t"] < R + 1.5 and e["t"] + e["dur"] > R]
    out["7_return"] = dict(event=cue.return_key, t=round(R, 3), strings_rise_10_90_ms=round((t90 - t10) / SR * 1000, 1),
                           rise_pass=bool((t90 - t10) / SR >= 0.040), fsharp_300_400_first_1_5s=len(fs_early),
                           first_fsharp_s=round(min(e["t"] for e in ev if int(round(e["midi"])) % 12 == FS), 3),
                           pass_=bool((t90 - t10) / SR >= 0.040 and not fs_early))

    # 8 + 9. the pendulum: smooth tempo, limited use; a different figure outdoors
    rk = [e for e in ev if e.get("role") == "ostinato 8'"]
    by = {}
    for e in rk:
        by.setdefault(e["line"], []).append(e)
    worst, pairs, fer = 0.0, [], []
    runs = []
    for ln, notes_ in by.items():
        notes_.sort(key=lambda e: e["t"])
        ioi = [(notes_[i + 1]["t"] - notes_[i]["t"]) / notes_[i]["step_beats"] for i in range(len(notes_) - 1)]
        fl = [bool(notes_[i].get("fermata")) for i in range(len(notes_) - 1)]
        brk = [notes_[i + 1]["t"] - notes_[i]["t"] > 1.6 * notes_[i]["step_beats"] * max(ioi[max(i - 1, 0)], 0.3)
               for i in range(len(notes_) - 1)]
        start = notes_[0]["t"]
        for i in range(len(ioi)):
            if brk[i] and not fl[i]:
                runs.append((start, notes_[i]["t"] + notes_[i]["dur"]))
                start = notes_[i + 1]["t"]
        runs.append((start, notes_[-1]["t"] + notes_[-1]["dur"]))
        for i in range(len(ioi) - 1):
            if fl[i] or fl[i + 1] or brk[i] or brk[i + 1]:
                if fl[i] or fl[i + 1]:
                    fer.append(dict(t=round(notes_[i + 1]["t"], 3), ioi_ratio=round(ioi[i + 1] / ioi[i], 3)))
                continue
            r = ioi[i + 1] / ioi[i] - 1
            pairs.append(r)
            if abs(r) > abs(worst):
                worst = r
                wt = notes_[i + 1]["t"]
    cover = sum(b - a for a, b in runs)
    longest = max(b - a for a, b in runs)
    out["8_9_pendulum"] = dict(
        max_beat_to_beat_change=round(float(worst), 4), at_s=round(wt, 3) if pairs else None,
        fermatas_excluded=fer, tempo_pass=bool(abs(worst) <= 0.12),
        rocking_runs_s=[[round(a, 2), round(b, 2)] for a, b in runs], rocking_seconds=round(cover, 2),
        rocking_share_of_film=round(cover / cue.duration, 3), longest_run_s=round(longest, 2),
        outdoor_pulse="three-note cells (root-2nd-5th, viola spiccato), not a two-note rocking",
        use_pass=bool(cover / cue.duration <= 0.40 and longest <= 15.0))
    o8 = out["8_9_pendulum"]
    o8["pass"] = bool(o8["tempo_pass"] and o8["use_pass"])

    # 10. stereo
    secs = [("return..street", R, street), ("street..turn_away", street, cue["turn_away"]),
            ("turn_away..square", cue["turn_away"], sq), ("square..climax", sq, clx),
            ("climax..title_in", clx, cue["title_in"]), ("title_in..end", cue["title_in"], cue["end"]),
            ("kitchen walk..latch", cue["walk"], cue["latch"])]
    bmid = butter(4, [150, 2500], btype="band", fs=SR, output="sos")
    blo = butter(4, 150, btype="low", fs=SR, output="sos")
    m_ = pyln.Meter(SR)
    srows = []
    ok = True
    for name, t0, t1 in secs:
        x = rd[int(t0 * SR): int(t1 * SR)]

        def corr(y):
            return float(np.sum(y[:, 0] * y[:, 1]) / np.sqrt(np.sum(y[:, 0] ** 2) * np.sum(y[:, 1] ** 2) + 1e-30))
        cm, cl = corr(sosfilt(bmid, x, axis=0)), corr(sosfilt(blo, x, axis=0))
        mono_ = np.repeat(x.mean(1, keepdims=True), 2, axis=1)
        loss = m_.integrated_loudness(x) - m_.integrated_loudness(mono_)
        row = dict(section=name, corr_150_2500=round(cm, 3), corr_below_150=round(cl, 3), mono_loss_db=round(loss, 2))
        if not name.startswith("kitchen"):
            row["pass_"] = bool(cm >= 0.3 and cl >= 0.8 and loss <= 1.5)
            ok &= row["pass_"]
        srows.append(row)
    out["10_stereo"] = dict(outdoor_width=SPACE["outside"]["width"], indoor_width=SPACE["inside"]["width"],
                            bass_mono_below_hz=SPACE["outside"]["bass_mono_hz"], sections=srows,
                            pass_=bool(ok and SPACE["outside"]["width"] <= 1.0))

    # 11. the window harmony
    pre_h = [h for h in S.harm if h[0] < clx - 1e-6]
    borrowed = [dict(t=round(h[0], 3), chord=h[1]) for h in pre_h if h[1] in ("Bb", "Gm")]
    pcs = {"C": 0, "C#": 1, "D": 2, "Eb": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "Ab": 8, "A": 9, "Bb": 10, "B": 11}
    bl = [pcs[h[2]] for h in S.harm if h[0] <= clx + 1e-6]
    bl = [b for i, b in enumerate(bl) if i == 0 or b != bl[i - 1]]
    desc = 0
    for i in range(len(bl)):
        if bl[i] != pcs["D"]:
            continue
        k = i
        while k + 1 < len(bl) and 1 <= (bl[k] - bl[k + 1]) % 12 <= 2:
            k += 1
        desc = max(desc, k - i)
    non_d = [th for th in S.themes if not str(th["first"]).startswith("D")]
    out["11_harmony"] = dict(window_chords=[dict(t=round(h[0], 3), chord=h[1], bass=h[2]) for h in S.harm],
                             borrowed_before_climax=borrowed, longest_stepwise_descent_from_tonic=desc,
                             theme_statements=S.themes, non_D_statements=len(non_d),
                             pass_=bool(borrowed and desc < 3 and non_d))

    # 12. the three looks are the strongest onsets around them (in the mix)
    lk = []
    for key in ("look1", "look2", "rise3"):
        tl = S.derived["sus4_on"] if key == "rise3" else cue[key]
        rank, at, strength = onset_rank(rd, tl, 1.0)
        lk.append(dict(key=key, t=round(tl, 3), onset_at=at, strength=strength, rank_within_1s=rank,
                       pass_=bool(rank <= 1)))
    marks = sorted({e.get("role") for e in ev if "pizzicato" in e.get("role", "")})
    piz = sorted({round(e["t"], 3) for e in ev if "pizzicato" in e.get("role", "")})
    sqr = onset_rank(rd, sq, 1.0)
    out["12_looks"] = dict(looks=lk, pizzicato_marks_at=piz, roles=marks,
                           square_cut_downbeat_rank_within_1s=sqr[0], pass_=bool(all(x["pass_"] for x in lk)))
    out["all_pass"] = bool(all(v.get("pass", v.get("pass_", True)) for k_, v in out.items()
                               if isinstance(v, dict) and k_ != "masking") and
                           out.get("masking", {}).get("pass", True))
    return out, (tt, Mv)


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
    keys = ["fade_up", "walk", "church_in", "rise1", "look1", "kettle_click", "stream", "spout_out", "pullback",
            "look2", "cup_cut", "pour", "slow2_end", "server_out", "bell2", "rise3", "latch", "return", "pilaster1",
            "street", "turn_away", "square_cut", "casement", "red_houses", "square_in", "climax", "cup_on_sill",
            "title_in", "last_chord", "bell4", "end"]
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
    ax[1].set_title(f"latch -> return ({R:.3f} s, cue '{cue.return_key}'): 5 ms RMS (dBFS); dotted: -70 dBFS")
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
    breath = (S.derived["breath_start"], S.derived["sus4_on"])
    log(f"score: {len(events)} notes, {len(S.locks)} locked arrivals")
    for name in sorted({e["inst"] for e in events} | set(BRASS_FAMILIES)):
        lib[name].calibrate()
    refined = refine_calibration(lib, [k for k in ("vln_spic", "va_spic", "vc_spic", "cb_pizz", "vc_pizz", "timproll")
                                       if lib[k].ready])
    brass_alloc = assign_brass(lib, events)
    for name in ("timp", "timproll"):
        if lib[name].ready:
            L4 = [s.lufs for s in lib[name].samples if s.layer >= 4 and s.lufs > -69]
            TIMP_REF[name] = float(-20.0 - np.mean(L4)) if L4 else 0.0
    log(f"calibration done; brass: {brass_alloc['groups']} notes, {len(brass_alloc['dropped'])} players dropped")
    church, church_info = C.church_ir()
    hall, hall_info = hall_ir()
    C.LOOPS.clear()
    buses, used = render3(lib, events, n, cue)
    loops = list(C.LOOPS)
    log(f"rendered into {len(buses)} buses")
    stems = mixdown(buses, n, cue, church, hall, breath)
    del buses
    log("mixdown done")
    stems, mhist, minfo = master_open(stems)
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

    arrivals = []
    for L_ in S.locks:
        k, t0, kind, stem = L_["key"], L_["t"], L_["kind"], L_["stem"]
        row = dict(key=k, film_time=round(t0, 3), kind=kind, stem=stem, what=L_["what"])
        x = rd if stem == "all" else st[stem]
        if kind == "onset":
            o, sal = onset_measure(x, t0)
            om, salm = onset_measure(rd, t0)
            row.update(flux_onset_stem=o, flux_salience=sal,
                       flux_error_ms=round((o - t0) * 1000, 1) if o is not None else None,
                       flux_onset_mix=om, flux_salience_mix=salm,
                       flux_error_mix_ms=round((om - t0) * 1000, 1) if om is not None else None)
            if o is not None and sal >= 3.0:
                row["measure"], row["error_ms"] = "flux in stem", row["flux_error_ms"]
            else:
                pr = probe_onset(lib, events, k, stem, t0, n, cue)
                row["probe_onset"] = round(pr, 4) if pr is not None else None
                row["measure"] = "probe (arrival notes alone, dry)"
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
            row.update(level_before_dbfs=round(ref, 1), **r, error_ms=round((r["steepest_fall_at"] - t0) * 1000, 1))
            row["pass"] = bool(-0.025 <= r["steepest_fall_at"] - t0 <= 0.15 and r["drop_db"] >= 6.0)
        elif kind == "gone":
            # every brass note (and its release) has ended before the event; what is left is the hall's tail
            ends = [e["t"] + e["dur"] + e.get("release", 0.08) for e in events
                    if e["stem"] == stem and not e.get("drop") and e["t"] < t0]
            t_gone = max(ends) if ends else cue["climax"]
            e_ = env_db3(x, 0.01)
            pk = float(e_[int(cue["climax"] * SR): int(t0 * SR)].max())
            row.update(last_note_ends_at=round(t_gone, 4), gone_at=round(t_gone, 4),
                       error_ms=round((t_gone - t0) * 1000, 1),
                       hall_tail_at_event_db_re_climax=round(float(e_[int(t0 * SR)]) - pk, 1))
            row["pass"] = bool(t_gone <= t0 - 0.03)
        elif kind == "breath":
            e_ = env_db3(rd, 0.01)
            before = float(np.median(e_[int((t0 - 0.5) * SR): int((t0 - 0.1) * SR)]))
            # up to the sus4's pre-roll (its samples may speak up to ARRIVAL_PRE_S before the look)
            during = float(np.max(e_[int((cue["bell2"]) * SR): int((breath[1] - ARRIVAL_PRE_S - 0.01) * SR)]))
            row.update(level_before_dbfs=round(before, 1), max_level_in_breath_dbfs=round(during, 1),
                       drop_db=round(before - during, 1), breath_s=[round(breath[0], 3), round(breath[1], 3)])
            row["pass"] = bool(before - during >= 12.0)
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

    a_, b_ = int((cue["latch"] + 0.03) * SR), int(cue["return"] * SR)
    sil = rd[a_:b_]
    silence = dict(window_s=[round(cue["latch"] + 0.03, 3), round(cue["return"], 3)],
                   max_abs_dbfs=round(dbv(np.abs(sil).max()), 1) if np.any(sil) else -999.0,
                   digital_zero=bool(not np.any(sil)),
                   last_nonzero_after_latch_s=round(C._last_nonzero(rd, cue["latch"] - 0.1, cue["return"] - 0.01), 5),
                   first_nonzero_before_return_s=round(C._first_nonzero(rd, cue["latch"] + 0.1, cue["return"] + 0.2), 5))
    silence["pass"] = silence["max_abs_dbfs"] < -70.0
    final = dict(last_nonzero_s=round(C._last_nonzero(rd, dur - 3.0, dur), 4), required_silent_from_s=round(dur - 0.3, 4))
    final["pass"] = bool(final["last_nonzero_s"] <= dur - 0.3 + 1e-6)

    st_t, st_v = short_term(rd)
    Lr = Loud(rd)
    sections = [("pre-roll (fade_up..walk)", "fade_up", "walk"), ("walk..stream", "walk", "stream"),
                ("stream..cup", "stream", "cup_cut"), ("cup..pour", "cup_cut", "pour"), ("pour..bell2", "pour", "bell2"),
                ("bell2..latch", "bell2", "latch"), ("latch..return (silence)", "latch", "return"),
                ("return..street", "return", "street"), ("street..square", "street", "square_cut"),
                ("square..climax", "square_cut", "climax"), ("climax..title_in", "climax", "title_in"),
                ("title_in..end", "title_in", "end")]
    tg, Mg = Lr.grid(0.01)
    sec = []
    for name, k0, k1 in sections:
        a, b = int(cue[k0] * SR), int(cue[k1] * SR)
        seg = rd[a:b]
        v = m.integrated_loudness(seg) if b - a > int(0.45 * SR) and np.any(seg) else float("-inf")
        w = (tg >= cue[k0]) & (tg < cue[k1])
        sec.append(dict(section=name, start=round(cue[k0], 3), end=round(cue[k1], 3),
                        integrated_lufs=round(v, 2) if np.isfinite(v) else None,
                        momentary_median_lufs=round(float(np.median(Mg[w])), 1) if w.any() and np.any(seg) else None,
                        momentary_max_lufs=round(float(Mg[w].max()), 1) if w.any() and np.any(seg) else None,
                        peak_dbfs=round(dbv(np.abs(seg).max()), 1) if np.any(seg) else None))

    spans = [("fade_up", "latch"), ("return", "last_chord")]
    mot = []
    for k0, k1 in spans:
        ts_ = sorted({round(e["t"], 3) for e in events if cue[k0] - 1e-6 <= e["t"] <= cue[k1] + 1e-6})
        ts_ = [cue[k0]] + ts_ + [cue[k1]]
        gaps = np.diff(ts_)
        gi = int(np.argmax(gaps))
        mot.append(dict(span=f"{k0}..{k1}", score_longest_gap_s=round(float(gaps[gi]), 2),
                        score_gap_from_s=round(ts_[gi], 2)))
    motion = dict(spans=mot, limit_s=6.0, pass_=bool(all(x["score_longest_gap_s"] <= 6.0 for x in mot)),
                  note="the final release (last_chord..end) is exempt by design")

    tun = tuning_test3(lib, used)
    tuning_pass = all(v["within_6_cents"] for v in tun.values())
    clicks = C.click_scan(rd)
    expected = sorted({round(e["t"], 3) for e in events} | {round(cue["latch"], 3), round(cue["return"], 3)})
    clicks_unexpl = [c for c in clicks if min(abs(c - x) for x in expected) > 0.03]
    plots(rd, cue, out_dir, st_t, st_v)
    log("plots done")
    story, _ = story_qc(rd, st, S, cue, minfo, out_dir)
    log(f"story QC all_pass={story['all_pass']}")

    qc = dict(
        locked_arrivals_within_25ms=dict(pass_=bool(all(a["pass"] for a in arrivals if a["kind"] in ("onset", "start"))),
                                         worst_abs_error_ms=worst, n=len(n_onsets)),
        releases=dict(pass_=bool(all(a["pass"] for a in arrivals if a["kind"] in ("release", "gone"))),
                      rows=[{k_: a.get(k_) for k_ in ("key", "kind", "error_ms", "drop_db", "gone_at")}
                            for a in arrivals if a["kind"] in ("release", "gone")]),
        bell2_breath=[a for a in arrivals if a["kind"] == "breath"][0],
        silence_after_latch=silence,
        dead_stop=[a for a in arrivals if a["kind"] == "stop"][0],
        final_silence=final,
        clipping=dict(sample_peak_dbfs=round(peak, 2), true_peak_dbtp=round(tp, 2),
                      pass_=bool(peak < 0 and tp <= -2.0 + 0.05)),
        loudness=dict(integrated_lufs=round(lufs, 2), target=None,
                      note="delivered open (no loudness target): static gain to a -2.3 dBTP peak, limiter <= 0.9 dB; "
                           "the sound mix sets the score's gain itself (its 'auto' rule at the climax)",
                      limiter_max_gr_db=minfo["max_gain_reduction_db"], pass_=bool(minfo["max_gain_reduction_db"] <= 1.0)),
        tuning=dict(pass_=bool(tuning_pass), limit_cents=6.0),
        motion=motion,
        stems_sum_to_mix=dict(max_abs_difference=sum_err, pass_=bool(sum_err == 0.0)),
        format=dict(sample_rate=info.samplerate, channels=info.channels, subtype=info.subtype,
                    frames=info.frames, duration_s=round(info.frames / SR, 6), cue_duration_s=dur,
                    pass_=bool(info.samplerate == SR and info.channels == 2 and info.subtype == "PCM_24" and
                               info.frames == n)),
        clicks=dict(count=len(clicks), unexplained=clicks_unexpl[:40], pass_=not clicks_unexpl),
        tempo_sanity=dict(kitchen=K.describe()["base_bpm_range_without_fermatas"],
                          window=W.describe()["base_bpm_range_without_fermatas"], limits=[40, 90],
                          pass_=bool(all(40 <= v <= 90 for tm in (K, W)
                                         for v in tm.describe()["base_bpm_range_without_fermatas"]))),
        brass_unique_files=dict(**brass_alloc, pass_=bool(not brass_alloc["dropped"])),
        story_acceptance=dict(pass_=story["all_pass"]),
    )
    qc["all_pass"] = bool(all(v.get("pass_", v.get("pass", True)) for k_, v in qc.items() if isinstance(v, dict)))

    probed = [a["key"] for a in arrivals if str(a.get("measure", "")).startswith("probe")]
    report = dict(
        title="WARSZAWA - original score", cue_sheet=os.path.relpath(cue_path, REPO),
        file="music.wav", duration_s=round(len(rd) / SR, 6), samples=len(rd), sample_rate=SR, bit_depth=24, channels=2,
        key="D minor (kitchen) -> open fifths, IV, bVI, bVII, iv, V (no F sharp) -> D major at the climax",
        theme="four rising notes answered by a falling step: D-E-F-Bb | A (3/4: q. e q | h q); window form "
              "B-C#-D-G | (F# at the climax); major form D-E-F#-B | A",
        meter="3/4 rubato (a fermata at rise1, free bars over the mug, the kettle click and the run)",
        music_return=dict(event=cue.return_key, t=round(cue["return"], 3)),
        derived_times=dict(**S.derived, last_chord=round(cue["last_chord"], 3)),
        tempo=dict(nominal="quarter = 55-75, rubato to the picture", kitchen=K.describe(), window=W.describe()),
        bar_by_bar=S.bars,
        locked_arrivals=dict(method="onset: (a) broadband spectral flux in the stem that carries the arrival "
                                    "(log-mel 150 Hz-12 kHz, hop 2.7 ms), strongest peak within +-60 ms, used when its "
                                    "salience >= 3; else (c) probe: the notes that make the arrival rendered alone "
                                    "through the same chain, onset where the 5 ms RMS first reaches -12 dB of its peak; "
                                    "flux on music.wav is also listed. start: first non-zero sample; release: first "
                                    "10 ms RMS 3 dB under the preceding level; breath: level drop (10 ms RMS) from the "
                                    "0.4 s before the breath to the loudest moment between the bell and the sus4; "
                                    "stop: last non-zero sample after the gate",
                             arrivals=arrivals),
        story_acceptance=story,
        qc=qc,
        per_section_loudness=sec,
        loudness=dict(integrated_lufs=round(lufs, 2), true_peak_dbtp_4x=round(tp, 2), sample_peak_dbfs=round(peak, 2),
                      master_iterations=mhist, limiter=minfo,
                      note="one static gain + one limiter gain curve (<= 0.9 dB) applied identically to every stem; "
                           "stems quantised to 24 bit first and music.wav written as their exact sum"),
        short_term_loudness=dict(hop_s=0.25, window_s=3.0, t=[round(float(x), 2) for x in st_t[::4]],
                                 lufs=[round(float(x), 1) if np.isfinite(x) else None for x in st_v[::4]]),
        tuning_cents=tun,
        brass_allocation=dict(**brass_alloc, players=[dict(t=round(e["t"], 3), note=NAME(e["midi"]), role=e["role"],
                                                           player=e.get("player"), inst=e["inst"],
                                                           file=os.path.basename(e["smp"]), shift_st=e["shift_st"])
                                                      for e in events if e.get("smp")]),
        recalibrated=dict(note="spiccato pitch re-measured on att+0.01..0.22 s, pizzicato on att+0.03..0.6 s, "
                               "timpani rolls on 0.5..6 s (file, compose.py measurement, refined measurement in MIDI)",
                          samples=refined),
        loops=dict(count=len(loops), min_rho=round(min([L_["rho"] for L_ in loops]), 3) if loops else None,
                   in_score=loops[:60]),
        spaces=dict(inside=dict(**SPACE["inside"], reverb="compose.church_ir (RT60 ~4.8 s)", ir=church_info,
                                gate=f"all indoor buses x raised-cosine {GATE_FADE_S * 1000:.0f} ms from the latch, "
                                     "then exact zero (dry and reverb)",
                                room_ducks="reverb send drawn down at the kettle click, over the mug (until the pour) "
                                           "and in the breath before bell2"),
                    outside=dict(**SPACE["outside"], reverb="short hall", ir=hall_info,
                                 tail="reverb return faded from end+0.25 s to duration-0.32 s; exact zero from "
                                      "duration-0.3 s"),
                    bell4_room="300-900 Hz band 8 dB down on all music from bell4-0.2 s (ramped from bell4-0.8 s)",
                    cup_hole=f"{HOLE['lo']:.0f}-{HOLE['hi']:.0f} Hz {HOLE['db']} dB from cup_on_sill-0.08 to +0.35 s",
                    stem_trim_db={f"{k[0]}/{k[1]}": v for k, v in STEM_TRIM.items()},
                    swell_box=dict(zip(["t", "brightness"], [list(map(lambda v: round(v, 3), x)) for x in swell_box(cue)]))),
        instruments=dict(
            used=sorted({e["inst"] for e in events if not e.get("drop")}),
            organ="VSCO-2 CE pipe organ (S. Dalzell / Ivy Audio): Man III open plenum ('open': the full organ at the "
                  "climax, a soft principal behind a closing swell box elsewhere), Man III stopped flute ('ged', 8' "
                  "and 4'), Pedal 16' Loud ('ped16', and its fifth above for the 32' resultant), Pedal 8' Quiet",
            strings="VSCO-2 CE violin, viola, cello sections (sustain vibrato, tremolo, spiccato, cello pizzicato), "
                    "solo contrabass (sustain, tremolo, pizzicato)",
            brass="VSCO-2 CE F horn, 1950s Olds trombone (every take of layers 2-5), tenor trombone: every player of "
                  "a note on a different file, resampled <= 2 semitones (assign_brass)",
            perc="VSCO-2 CE timpani (hits and rolls)",
            not_used="no piano, harp, pads, synths, chimes/bells, flute solos or ticking",
            licence="VSCO-2 Community Edition, CC0 1.0"),
        not_verified_by_ear=[
            "I cannot listen. Balance, phrasing, realism and the emotional effect were judged from the score, "
            "loudness curves, spectrograms, onset, pitch and masking measurements only.",
            f"{len(probed)} soft arrivals ({', '.join(probed)}) cannot be separated by onset detection inside the "
            "delivered stem (legato organ/strings); their timing is measured on the arrival notes rendered alone "
            "through the same chain (probe). The three looks are also ranked by onset strength in the mix.",
            "The masking tests use the sound team's stems as they are on disk now, at the score gain their 'auto' "
            "rule would give this score, without their music ducks; a re-render of the sound changes them.",
        ],
        rendered_by="pipeline/compose3.py (imports pipeline/compose.py unchanged)",
        render_seconds=round(time.time() - T_START, 1),
    )
    with open(os.path.join(out_dir, "score_report.json"), "w") as fh:
        json.dump(report, fh, indent=1, default=C._json_default)
    log(f"done: {lufs:.2f} LUFS, TP {tp:.2f} dBTP, worst locked onset {worst} ms, QC all_pass={qc['all_pass']}")


if __name__ == "__main__":
    main(sys.argv)
