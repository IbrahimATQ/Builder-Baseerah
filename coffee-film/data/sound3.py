#!/usr/bin/env python3
"""WARSZAWA (the window): the sound, written down once. Running it writes data/sound3.json for pipeline/sound3.py.

THE PRINCIPLE: the glass is a low-pass filter. Every sound has a source in the story: no whooshes, risers, impacts,
booms or clocks. Until the window opens, the city is heard through glass (low-passed from about 600 Hz, opening a
little with each look: 1 kHz at LOOK 1, 1.3 kHz at LOOK 2, 1.8 kHz at LOOK 3, 12-32 dB under its open level); the
latch cuts the music dead and the city floods in at full range over the 1.5 s the sash takes to clear.

Every film time below is a reference into data/cuesheet3.json ("@latch+0.15", "@cup", ...), resolved by the mixer at
mix time, so a re-run follows any nudge of the picture. Nothing here is a hard-coded film time.

Four stems:
  city     the street and the square: the clips' own sound (IMG_5417 behind glass, then in sync with the open window;
           IMG_5416 in sync with the square, its own +8 dB jump when he leans out kept), with Mixkit street/square
           atmospheres underneath; all of it cleaned of the street musician's notes (detone) so nothing in the
           city plays music against the score
  kitchen  the room: its own tone (IMG_5419/5420/5421, mains hum notched, appliance lines detoned), the clips' own
           sound in sync (walk, the pour), the kettle (switch-on, heating crescendo, click-off)
  foley    close, dry, sync: the stream, the bloom, drips, the set-downs, the glass on porcelain, the amber pour,
           the latch, the sash, the casement, the cup on the sill
  bell     one D bell (Mixkit 617), four strokes: far behind glass, behind glass, opening with the sash, open air
The clips' own sound is never slowed by resampling: every speed change goes through rubberband (pitch kept).
Sources: /home/user/coffee/raw (the commissioner's iPhone clips) and the licensed Mixkit library
/home/user/coffee/sfx (each item's licence and measurements in its catalog.json; only catalogued items are used).
"""
from __future__ import annotations

import json
import os

RAW = os.environ.get("COFFEE_RAW", "/home/user/coffee/raw")
SFX = os.environ.get("COFFEE_SFX", "/home/user/coffee/sfx")
SCORE = os.environ.get("COFFEE_SCORE3", "/home/user/coffee/score3/music.wav")
OWN = "the commissioner's own recording (iPhone clip)"
HUM = [50, 100, 150, 200, 250]
CATALOG = json.load(open(os.path.join(SFX, "catalog.json"), encoding="utf-8"))
ITEMS = {str(it["id"]): it for it in CATALOG["items"]}


def raw(i: str) -> str:
    return f"{RAW}/{i}.MOV"


def sfx(i: str) -> str:
    """A Mixkit item of the catalogue (refuses anything not catalogued)."""
    it = ITEMS[str(i)]
    return it["file"]


def lic(i: str) -> str:
    it = ITEMS[str(i)]
    return f"Mixkit {it['id']} '{it['title']}' ({it['licence']}, {it['licence_url']})"


E: list[dict] = []


def el(id_: str, bus: str, what: str, file_id: str, **kw) -> dict:
    """One element. file_id: a clip name (IMG_54xx) or a Mixkit id."""
    own = file_id.startswith("IMG_")
    d = {"id": id_, "bus": bus, "what": what, "file": raw(file_id) if own else sfx(file_id),
         "licence": OWN if own else lic(file_id)}
    d.update(kw)
    E.append(d)
    return d


# ---- THE GLASS: one curve for everything outside before the latch ----------------------------------------------------
GLASS_LP = [["@black_in", 600], ["@rise1", 600], ["@look1", 1000], ["@pullback", 1000], ["@look2", 1300],
            ["@server_out", 1300], ["@rise3", 1800], ["@open+0.35", 1800]]
# the window opens: whatever is still sounding outside opens with the sash (1.5 s, from just after bell 3 to clear)
OPENING_LP = [["@bell3+0.25", 1800], ["@sash_clear", 19000]]
OPENING_GAIN = [["@bell3+0.25", -9], ["@sash_clear", 0]]
# level of the city behind the glass, relative to the open street (dB): up on each look, gone on the cup
GLASS_GAIN = [["@black_in", -16], ["@rise1", -16], ["@look1", -13], ["@kettle_click-0.4", -13], ["@kettle_click", -15],
              ["@stream", -16], ["@pullback", -16], ["@look2", -13], ["@cup-0.25", -13], ["@cup", -32],
              ["@hand", -32], ["@server_out", -18], ["@bell2", -15], ["@rise3+0.5", -12], ["@open+0.35", -12]]
CITY_REF = -33.5      # RMS (dBFS, before the master) of the open street: the reference of everything outside


def city() -> None:
    # behind the glass: the street from a part of IMG_5417 the picture does not use (its notes removed), the 0.8x
    # world (rubberband), pieces joined so no loop is heard; Mixkit's downtown crowd underneath for continuity
    el("city_glass", "city", "the street behind the kitchen glass (unused part of the window clip)", "IMG_5417",
       splice=[[12.3, 19.6], [19.4, 27.0], [13.4, 18.8], [20.6, 26.6]], xfade=0.8, tempo=0.8,
       start="@black_in", end="@open+0.4", hp=60, detone={}, rms_db=CITY_REF,
       gain_keys=GLASS_GAIN, lp_keys=GLASS_LP, lp_order=2, fade_in=0.25, fade_out=0.4, fade_shape="power")
    el("city_glass_crowd", "city", "the wider city behind the glass (no speech in it)", "361",
       src=[2.0, 50.0], start="@black_in", end="@open+0.4", hp=80, detone={}, rms_db=CITY_REF - 6,
       gain_keys=GLASS_GAIN, lp_keys=GLASS_LP, lp_order=2, fade_in=0.25, fade_out=0.4, width=0.8, fade_shape="power")
    # the open window: IMG_5417's own sound in sync with its picture, running on through the dissolve to the turn
    # (the street is continuous); it rises ~5 dB by itself as the sash clears, the filter opens fully with it
    el("city_open", "city", "the street through the opening window, in sync (IMG_5417 0.0 on)", "IMG_5417",
       timemap={"shot": "open"}, start="@open", end="@square+0.3", hp=50, detone={}, rms_db=CITY_REF, crest_db=15.0,
       lp_keys=[["@open", 1800], ["@bell3+0.25", 1800], ["@sash_clear", 19000],
                ["@pilaster1-0.3", 19000], ["@pilaster1", 5500], ["@pilaster1+0.4", 19000]],
       # the music has stopped dead: the city fills the silence (+3 dB) and gives way a little as the organ returns
       gain_keys=[["@open", -6], ["@bell3+0.25", -6], ["@sash_clear", 3], ["@open+2.5", 3], ["@pilaster1-0.3", 1],
                  ["@pilaster1", -1.5], ["@pilaster1+0.4", 1], ["@street", 0]],
       fade_in=0.35, fade_out=0.6, fade_shape="power")
    el("city_walkers", "city", "passers-by on the stone below, low under the street", "375",
       src=[3.0, 30.0], start="@sash_clear", end="@square+0.6", hp=150, lp=7000, detone={}, rms_db=CITY_REF - 13,
       crest_db=14.0,
       width=1.3, fade_in=2.5, fade_out=1.0)
    # the square: IMG_5416's own sound in sync, matched to the street at the cut (inaudible hand-over); its own jump
    # when he leans out is kept (the city doubles: +8 dB at its peak, about +5 dB over 1.5 s); it outlasts everything
    el("city_square", "city", "the square, in sync (IMG_5416 4.1 on); its own jump when he leans out", "IMG_5416",
       timemap={"shot": "square"}, start="@square-0.3", end="@duration", hp=50, detone={}, crest_db=15.0,
       match={"to": "city_open", "at": "@square", "win": 1.0, "gap": 0.3}, fade_in=0.6, fade_out=1.75, fade_shape="power",
       step="@city_doubles")
    el("city_square_air", "city", "the width of the square as it opens, longer reflections", "346",
       src=[4.0, 30.0], start="@city_doubles-0.5", end="@duration", hp=120, polarity="flip_right", detone={},
       rms_db=CITY_REF - 4, reverb={"rt60": 1.8, "mix": 0.3, "predelay": 0.03},
       gain_keys=[["@city_doubles-0.5", -8], ["@square_in", 0], ["@end", 0]], fade_in=1.5, fade_out=1.75)


def kitchen() -> None:
    clean = {"notch": HUM, "hp": 60, "detone": {}}
    # the room's own tone, the whole kitchen long (IMG_5419: the static kitchen; pieces joined, no loop heard)
    el("room_tone", "kitchen", "the kitchen's own tone (IMG_5419), hum notched, appliance lines removed", "IMG_5419",
       splice=[[0.2, 2.7], [2.3, 4.7], [0.8, 3.6], [1.5, 4.7], [0.3, 2.2]], xfade=0.6, start="@black_in",
       end="@open+0.15", rms_db=-57.0, fade_in=0.3, fade_out=0.15, **clean)
    # the clips' own sound in sync with their pictures (0.8x and the slow motion, pitch kept)
    el("walk_own", "kitchen", "the walk's own sound (IMG_5420), in sync", "IMG_5420",
       timemap={"shot": "walk"}, start="@walk.film_in", end="@bloom", rms_db=-56.0, fade_in=0.6, fade_out=0.05, **clean)
    el("bloom_own", "kitchen", "the dripper's own sound (IMG_5421), in sync through the slow motion; handling knock "
       "at src 4.05-5.0 replaced", "IMG_5421", timemap={"shot": "bloom"}, start="@bloom", end="@bloom.film_out",
       repair=[[4.02, 5.02, 10.0]], rms_db=-56.0, fade_in=0.03, fade_out=1.0, **clean)
    el("brew_own", "kitchen", "the dripper later (IMG_5421), in sync; a handling tick at src 19.95-20.3 replaced",
       "IMG_5421", timemap={"shot": "brew"}, start="@brew", end="@cup", repair=[[19.93, 20.33, 21.3]],
       rms_db=-56.0, fade_in=1.0, fade_out=0.02, **clean)
    # the kettle (right of centre, where it stands): switched on as the picture rises, heating and building under the
    # walk (Mixkit 1817 from cold to the roar, squeezed into the walk, pitch kept), cut by its own click-off
    el("kettle_on", "kitchen", "kettle switched on", "1817", src=[1.06, 1.40], sync=[1.134, "@fade_up+0.75"],
       peak_db=-34.0, fade_in=0.004, fade_out=0.15, pan=0.45, width=0.5, onset="@fade_up+0.75")
    el("kettle_heat", "kitchen", "the kettle heating to the boil: a physical crescendo under the walk", "1817",
       fit=[["@fade_up+0.95", 1.95], ["@kettle_click+0.02", 30.0]], hp=70, detone={}, rms_db=-44.0,
       gain_keys=[["@fade_up+0.95", -14], ["@walk", -11], ["@church_in", -9], ["@rise1", -6], ["@look1", -3],
                  ["@kettle_click-0.5", 0]],
       fade_in=0.8, fade_out=0.018, pan=0.45, width=0.6)
    el("kettle_off", "kitchen", "the kettle clicks off; a tenth of a second of hush, then the cut", "1817",
       src=[52.70, 52.88], sync=[52.777, "@kettle_click"], hp=120, peak_db=-27.0, fade_in=0.004, fade_out=0.06,
       pan=0.4, width=0.5, onset="@kettle_click")


def foley() -> None:
    # the first water on the coffee, close and dry, slowed with the picture (rubberband, pitch kept): the stream runs
    # unbroken through the dissolve into the later pour (the sound carries the time jump) and stops with the spout
    el("stream", "foley", "the thin stream on the coffee, slowed with the picture", "1318",
       timemap={"shot": "bloom", "rate": 1.25, "anchor": ["@stream", 3.2]}, start="@stream", end="@bloom.film_out",
       hp=160, lp=12000, detone={}, rms_db=-37.0, crest_db=16.0, width=0.5, fade_in=0.006, fade_out=1.0,
       fade_shape="power", onset="@stream",
       onset_before=0.05, onset_after=0.15)
    el("stream_later", "foley", "the stream, later: the last pours, until the spout withdraws", "1318",
       src=[24.8, 33.0], start="@brew", end="@spout_out+0.05", hp=160, lp=12000, detone={}, rms_db=-38.0,
       crest_db=16.0, width=0.5, fade_in=1.0, fade_out=0.12, fade_shape="power")
    el("bloom_fizz", "foley", "the bloom: CO2 fizzing out of the wet coffee, faint", "3181",
       timemap={"shot": "bloom", "rate": 1.25, "anchor": ["@stream+0.25", 7.3]}, start="@stream+0.25",
       end="@brew.start", hp=1800, rms_db=-55.0, width=0.7, fade_in=1.2, fade_out=1.0)
    for k, (dt, p, pn) in enumerate([(1.35, 2.0, -0.12), (2.9, 3.0, 0.1), (4.4, 1.0, 0.0)]):
        el(f"bloom_bubble{k + 1}", "foley", "a bubble breaking in the bloom", "1317", src=[0.05, 0.40],
           start=f"@stream+{dt}", pitch=p, hp=400, peak_db=-49.0 - k, fade_in=0.01, fade_out=0.08, pan=pn)
    # the spout withdraws: the kettle is set down off-screen on its base (right); then single drips into the server
    el("kettle_down", "foley", "kettle set down off-screen on its base", "2934", src=[0.0, 0.30],
       sync=[0.004, "@spout_out+0.55"], pitch=-2.0, hp=90, lp=6000, peak_db=-33.0,
       reverb={"rt60": 0.45, "mix": 0.25, "predelay": 0.008}, pan=0.45, fade_out=0.08, onset="@spout_out+0.55")
    drips = [(0.40, 7.136, 4.0), (1.05, 1.090, 4.5), (1.75, 2.708, 3.5), (2.6, 3.394, 4.0), (3.6, 1.453, 5.0),
             (4.75, 6.616, 4.0), (6.0, 7.136, 3.0)]
    for k, (dt, ft, p) in enumerate(drips):
        el(f"drip{k + 1}", "foley", "a single drip into the glass server", "1879", src=[ft - 0.006, ft + 0.11],
           sync=[ft, f"@spout_out+{dt}"], pitch=p, hp=900, lp=14000, peak_db=-35.0 - 0.6 * k,
           reverb={"rt60": 0.3, "mix": 0.18, "predelay": 0.004}, fade_in=0.002, fade_out=0.05, width=0.3,
           skip_after="@cup-0.3")
    # the cup: the quietest moment; the glass lip touches the porcelain; the slow amber pour into the printed city
    el("server_lip", "foley", "the glass server's lip touches the porcelain, tiny", "154", src=[0.10, 0.42],
       sync=[0.113, "@server_in"], hp=300, peak_db=-40.0, fade_in=0.002, fade_out=0.22, onset="@server_in")
    el("pour_porcelain", "foley", "the coffee hits the empty porcelain, in slow motion (pitch kept)", "1310",
       timemap={"shot": "cup", "rate": 1.25, "anchor": ["@pour", 0.11]}, start="@pour", end="@slow2_end+1.1",
       hp=140, lp=13000, rms_db=-38.0, crest_db=15.0, fade_in=0.012, fade_out=0.9, onset="@pour", onset_before=0.05)
    el("pour_filling", "foley", "the cup filling, its pitch rising (slow, then the 0.8x real time)", "2826",
       timemap={"shot": "cup", "fit": [["@slow2_end-0.5", 0.55], ["@server_out-0.25", 3.4]]},
       start="@slow2_end-0.5", end="@server_out-0.05", hp=150, rms_db=-38.5, crest_db=15.0,
       gain_keys=[["@slow2_end", 0], ["@hand+0.8", 0], ["@server_out-2.0", 5], ["@server_out-0.3", 5]],
       fade_in=0.7, fade_out=0.15)
    el("crema", "foley", "the crema fizzing in the full cup", "2833", src=[2.6, 6.4], tempo=0.7,
       start="@hand", hp=2500, rms_db=-56.0, fade_in=1.5, fade_out=1.6, width=0.6)
    el("server_down", "foley", "the server set down off-screen", "3148", src=[0.0, 0.48],
       sync=[0.023, "@server_out+0.7"], hp=200, lp=8000, peak_db=-33.0,
       reverb={"rt60": 0.4, "mix": 0.22, "predelay": 0.006}, pan=-0.3, fade_out=0.1, onset="@server_out+0.7")
    # THE LATCH: close and dry, the loudest close transient so far; the handle turns, the latch gives
    el("latch", "foley", "the old window's handle and latch", "2856", src=[0.0, 0.62], sync=[0.238, "@latch"],
       hp=180, peak_db=-16.0, fade_in=0.002, fade_out=0.12, pan=0.1, width=0.4, onset="@latch",
       onset_before=0.04, onset_mode="attack")   # measured on the latch itself, not the handle's two small clicks before it
    el("latch_bolt", "foley", "the latch bolt snaps back", "1924", src=[0.10, 0.28], sync=[0.134, "@latch+0.012"],
       hp=150, peak_db=-23.0, fade_in=0.002, fade_out=0.05, pan=0.1)
    # the seal unsticks, the old wood creaks as the sash is pulled in (close, dry)
    el("sash_seal", "foley", "the sash's seal unsticks; the old hinge creaks", "195", src=[0.08, 1.62],
       sync=[0.118, "@latch+0.14"], hp=110, peak_db=-24.0, fade_in=0.004, fade_out=0.4, pan=0.15)
    el("sash_creak", "foley", "the old wood creaks as the sash swings in", "1163", src=[1.33, 2.0],
       start="@open+0.5", hp=260, peak_db=-27.0, fade_in=0.08, fade_out=0.3, pan=-0.1)
    # the turn away from the street: no catalogue item is a cloth rustle; nothing is added (the street runs on)
    # the square: the outer casement swings across, its hinge creaks in the open air
    el("casement", "foley", "the outer casement swings away, its hinge creaks", "1163", src=[1.95, 2.75],
       sync=[1.95, "@casement"], hp=240, peak_db=-24.0, fade_in=0.03, fade_out=0.35, pan=-0.25, onset="@casement",
       slap={"delays": [0.062, 0.118], "gains_db": [-14, -18], "lp": 4000})
    # at the climax, off screen: his cup set down on the stone sill: close and dry
    el("cup_on_sill", "foley", "his cup set down on the stone sill, off screen", "2933", src=[0.0, 0.45],
       sync=[0.069, "@cup_on_sill"], hp=200, peak_db=-18.0, fade_in=0.003, fade_out=0.12, pan=-0.15,
       onset="@cup_on_sill", onset_before=0.03, onset_mode="attack")   # the contact, not the light pre-touch 59 ms before it


def bells() -> None:
    bell = "617"   # a single strike, D (in key with the score), decays over 6 s

    el("bell1", "bell", "bell stroke 1: far off, muffled through the glass, over black", bell, src=[0.05, 6.3],
       sync=[0.100, "@bell1"], hp=90, lp=3500, rms_db=-56.0, pan=-0.25, width=0.6,
       reverb={"rt60": 3.4, "mix": 0.65, "predelay": 0.06}, lp_keys=GLASS_LP, onset="@bell1", onset_after=0.4)
    el("bell2", "bell", "bell stroke 2: through the kitchen glass", bell, src=[0.05, 6.3], sync=[0.100, "@bell2"],
       hp=90, lp=4500, rms_db=-42.0, pan=-0.25, width=0.6, reverb={"rt60": 3.4, "mix": 0.6, "predelay": 0.06},
       lp_keys=GLASS_LP[:-1] + OPENING_LP, gain_keys=[[k[0], 0.0] for k in GLASS_LP[-2:-1]] + OPENING_GAIN,
       onset="@bell2", onset_after=0.4)   # its tail is still ringing when the window opens: it opens too
    el("bell3", "bell", "bell stroke 3: behind the glass, then in the open air as the sash clears", bell,
       src=[0.05, 6.3], sync=[0.100, "@bell3"], hp=80, rms_db=-38.0, pan=-0.2,
       reverb={"rt60": 3.6, "mix": 0.5, "predelay": 0.05},
       slap={"delays": [0.068, 0.125], "gains_db": [-11, -15], "lp": 3500},
       lp_keys=[["@bell3", 1800], ["@bell3+0.25", 1800], ["@sash_clear", 19000]],
       gain_keys=[["@bell3", -9], ["@bell3+0.25", -9], ["@sash_clear", 0]], onset="@bell3", onset_after=0.4)
    el("bell4", "bell", "bell stroke 4: open air over the square, the facades answer, a long tail", bell,
       src=[0.05, 6.3], sync=[0.100, "@bell4"], hp=80, lp=9000, rms_db=-39.0, pan=-0.15,
       reverb={"rt60": 4.6, "mix": 0.45, "predelay": 0.05},
       slap={"delays": [0.085, 0.16, 0.31, 0.47], "gains_db": [-9, -12, -15, -19], "lp": 3200},
       gain_keys=[["@end", 0], ["@end+1.2", -40]], onset="@bell4", onset_after=0.4)


NOTES = [
    "IMG_5417 and IMG_5416 carry a street musician (sustained notes in A and D major, A = 437-439 Hz, +20-30 dB over "
    "the noise in 16k-point spectra). Under the organ score and through the kitchen glass that would be a second, "
    "unrelated music, so every city bed is detoned: sustained tonal lines are pulled down to the noise floor around "
    "them (tonal prominence 20.9 -> 11.9 dB, the noise baseline; footsteps, voices' breath and the air are kept).",
    "The kitchen clips' tracks have mains hum (50/100/150 Hz, +17-36 dB) and appliance lines (100, 161, 179, 223, "
    "299, 401 Hz): notched at 50-250 Hz and detoned. IMG_5421's handling knock (src 4.02-5.02) and a tick at src "
    "19.93-20.33 are replaced by clean material of the same clip. IMG_5422's own track is not used at all.",
    "Speed: the clips' own sound follows the cue sheet's speed curve (0.8x, 0.5x, eased ramps) through rubberband, "
    "pitch kept; library textures under the slow motion are laid on the same curve (rate 1.25: real speed where the "
    "picture is at 0.8x, 0.625x in the 0.5x stretch). Nothing is slowed by resampling; only the drips and two "
    "set-downs are pitched (by resampling, to make them smaller or heavier) and they are not time-locked to frames.",
    "Set-downs: the glass server is Mixkit 3148 (a glass jar touching down, 888 Hz glass ring); the metal kettle on "
    "its base is Mixkit 2934 pitched down 2 semitones (a dull contact) - the brief's 3148 for the kettle and 2933 for "
    "the server were swapped for material that matches what is set down. The cup on the stone sill is 2933.",
    "turn_away -> sill: the catalogue has no cloth rustle; nothing is added (the street runs on, continuous).",
    "The score is placed at 0 if its file exists at mix time; its gain is set so that the city stem sits 8 dB under "
    "it at the climax (window climax-0.5 .. climax+2.5); it is faded out from end+0.25 to end+1.35 so that the city "
    "is the last sound.",
]


def build() -> dict:
    E.clear()
    city()
    kitchen()
    foley()
    bells()
    return {
        "title": "WARSZAWA", "cuesheet": "cuesheet3.json", "duration": "@duration",
        "buses": ["city", "kitchen", "foley", "bell"],
        # the score (composed in parallel; used if the file exists at mix time). Its gain is set so that the city
        # sits 8 dB under it at the climax; it is out by the end of the black so that the city is the last sound
        "score": {"file": SCORE, "gain_db": 0.0,
                  "auto": {"t0": "@climax-0.5", "t1": "@climax+2.5", "city_under_db": 8.0, "bus": "city"},
                  "end_fade": ["@end+0.25", "@end+1.35"]},
        "music_ducks": [],
        "notes": NOTES,
        "glass_report": ["city_glass", "city_open", "bell3"],
        "ceiling_db": -2.0, "targets": {"mix": -14.0, "sfx_only": -16.0},
        "sections": [["black_in", "@black_in", "@fade_up"], ["walk", "@fade_up", "@bloom"],
                     ["bloom", "@bloom", "@brew.start"], ["brew", "@brew.start", "@cup"],
                     ["cup_quiet", "@cup", "@pour"], ["cup_pour", "@pour", "@server_out"],
                     ["look3", "@server_out", "@latch"], ["latch_to_sash", "@latch", "@sash_clear"],
                     ["no_music_gap", "@sash_clear", "@open+2.5"], ["street", "@open+2.5", "@turn.start"],
                     ["turn", "@turn.start", "@square"], ["square_build", "@square", "@climax"],
                     ["climax", "@climax-0.5", "@climax+2.5"], ["release", "@climax+2.5", "@end"],
                     ["black_out", "@end", "@duration"]],
        "elements": E,
    }


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    sp = build()
    json.dump(sp, open(os.path.join(here, "sound3.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote sound3.json:", len(sp["elements"]), "elements;", "score present" if os.path.exists(SCORE) else "no score yet")
