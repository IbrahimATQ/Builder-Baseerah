#!/usr/bin/env python3
"""WARSZAWA (the window): the sound, written down once. Running it writes data/sound3.json for pipeline/sound3.py.

THE PRINCIPLE: the glass is a low-pass filter. Every sound has a source in the story: no whooshes, risers, impacts,
booms or clocks. Until the window opens, the city is heard through glass (low-passed from about 600 Hz, opening a
little with each look: 1 kHz at LOOK 1, 1.3 kHz at LOOK 2, 1.8 kHz at LOOK 3 and 2.1 kHz as the camera pushes into
the pane; 10-24 dB under its open level: the long kitchen stays alive but distant, and under the score's forte
before the latch the city is texture, not a voice).
The latch cuts the music dead and the city FLOODS in with the bright first frames of the window (review 2): the
glass is gone at the cut (7 kHz on the cut frame, no filter 0.3 s later), at the open street's level on the cut
frame and +3 dB (filling the silence) 0.2 s later: no dip, no riser, the highs there at once. With a score, the
flood is made at least as loud as the score's last bar before the latch (flood_match). The organ comes back under
the city (the score ducked 6 dB for 1.5 s from its return), so the city's first moment at full range is heard.
THE ARRIVAL (review 1): the second half lifts once, at the volute and the climax - the mix ride dips 1 dB before
the Castle Square and lifts 1 dB through the climax, the square's air opens with the most open view, and nothing in
the chain flattens it (the score's bus limiter sits at the master ceiling and may add no more than 1 dB to hold the
climax balance; the master gives up loudness, down to -16 LUFS, before it gives up the lift): 2 s around the climax
at least 3 dB over the 4 s before square_in, measured on the mix.

Every film time below is a reference into data/cuesheet3.json ("@latch+0.15", "@cup", ...), resolved by the mixer at
mix time, so a re-run follows any nudge of the picture. Nothing here is a hard-coded film time.

Four stems:
  city     the street and the square: the clips' own sound (IMG_5417 behind glass, then in sync with the open window;
           IMG_5416 in sync with the square), with Mixkit street/square atmospheres underneath; all of it cleaned of
           the street musician's notes (detone) so nothing in the city plays music against the score. When he leans
           out the clip's own "jump" is only low thumps (a hand on the phone, wind: mostly < 150 Hz, mono); the band
           under 500 Hz is held to its level before the lean (dethump) and the city doubles where the ear and a phone
           speaker hear it, in 500 Hz-6 kHz
  kitchen  the room: its own tone (IMG_5419/5420/5421, mains hum notched, appliance lines detoned), the clips' own
           sound in sync (walk, the pour), the kettle (switch-on, heating crescendo, click-off)
  foley    close, dry, sync: the stream, the bloom, drips, the set-downs, the glass on porcelain, the amber pour,
           the latch, the sash, the casement, the cup on the sill
  bell     one D bell (Mixkit 617), four strokes: far behind glass, behind glass (in the breath the score leaves
           before its forte), struck as the window opens (it opens with it, never swells), open air
The clips' own sound is never slowed by resampling: every speed change goes through rubberband (pitch kept, the two
channels together so the image stays coherent; its short window, for less smear and pre-echo). The steady stream
is not stretched.
A fader ride (mix_keys) lifts the quiet kitchen 6 dB (back to 0 as the coffee pours), dips 1 dB before the Castle
Square and lifts 1 dB through the climax: the loudness range fits a phone speaker and the climax ARRIVES. The
score's own accents are held on its bus at the master's ceiling, so the master limiter never ducks the city with
them, and nothing takes the climax's lift away.
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
HUM = [49.3, 50, 100, 150, 200, 223, 250, 300]   # mains (it sits at 49.3 Hz in these clips), its harmonics, and
                                                 # the appliance lines at 223 and 300 Hz
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
            ["@server_out", 1300], ["@rise3", 1800], ["@latch", 2100]]   # LOOK 3 pushes into the pane: it comes closer
# the window opens on the latch, with the bright first frames: the handle's turn lets a breath in, and on the cut
# to the window the glass is already gone from the highs (7 kHz), fully open 0.3 s later - a flood, not a sweep
SEAL = "@latch+0.14"
OPENING_LP = [["@latch", 2100], ["@latch+0.06", 2800], ["@open", 7000], ["@open+0.12", 12000], ["@open+0.3", 19000]]
# level of the city behind the glass, relative to the open street (dB): up on each look; on the short empty mug it
# steps back (distant, never gone: the kitchen stays alive), and it comes closer with the push into the pane
GLASS_GAIN = [["@black_in", -16], ["@rise1", -16], ["@look1", -13], ["@kettle_click-0.4", -13], ["@kettle_click", -15],
              ["@stream", -16], ["@pullback", -16], ["@look2", -13], ["@cup-0.25", -13], ["@cup", -22],
              ["@pour", -22], ["@server_out", -18], ["@bell2", -15], ["@rise3+0.5", -12], ["@latch", -10.5]]
# ... and through the opening: a breath as the handle turns, the open street's level ON the cut to the window, and
# filling the silence (+3) 0.2 s later
OPENING_GAIN = [["@latch", -10.5], ["@latch+0.06", -8], ["@open", 0], ["@open+0.2", 3]]
CUP = "@cup_on_sill"   # the cup on the sill (see foley())
CITY_REF = -33.5      # RMS (dBFS, before the master) of the open street: the reference of everything outside


def city() -> None:
    # behind the glass: the street from a part of IMG_5417 the picture does not use (its notes removed), the 0.8x
    # world (rubberband), pieces joined so no loop is heard; Mixkit's downtown crowd underneath for continuity
    el("city_glass", "city", "the street behind the kitchen glass (unused part of the window clip)", "IMG_5417",
       splice=[[12.3, 19.6], [19.4, 27.0], [13.4, 18.8], [20.6, 26.6]], xfade=0.8, tempo=0.8,
       start="@black_in", end="@open+1.2", hp=60, detone={}, rms_db=CITY_REF,
       gain_keys=GLASS_GAIN + OPENING_GAIN, lp_keys=GLASS_LP + OPENING_LP, lp_order=2, fade_in=0.25, fade_out=0.9,
       fade_shape="power")
    el("city_glass_crowd", "city", "the wider city behind the glass (no speech in it)", "361",
       src=[2.0, 50.0], start="@black_in", end="@open+1.2", hp=80, detone={}, rms_db=CITY_REF - 6,
       gain_keys=GLASS_GAIN + OPENING_GAIN, lp_keys=GLASS_LP + OPENING_LP, lp_order=2, fade_in=0.25, fade_out=0.9,
       width=0.8, fade_shape="power")
    # the open window: IMG_5417's own sound in sync with its picture, running on through the dissolve to the turn
    # (the street is continuous). It takes over from the glass take on the same opening curve (equal-power, from the
    # cut to open+1.2: the glass take, the bright open street, carries the flood's first second).
    # The clip's own track is dull and 5 dB quiet until src 2.5 (its real rise comes at src 3.0-3.4, under the
    # returning organ), so its air above ~5 kHz is lifted 7 dB until then, tapering out by src 3.0, and its level
    # is made up (+5 dB on the opening curve until src 2.2, out by src 3.4 as the clip rises by itself): the flood is
    # full range and full level at once, and stays level while the organ comes back under it.
    el("city_open", "city", "the street through the opening window, in sync (IMG_5417 0.0 on)", "IMG_5417",
       timemap={"shot": "open"}, start="@open", end="@square+0.15", hp=50, detone={}, rms_db=CITY_REF, crest_db=12.0,
       # each pilaster passing the lens shades the street for a moment; the turn ends inside the second one (the cut
       # to the square is in it): the street is shaded into the cut, and the square opens at full range after it
       lp_keys=OPENING_LP + [["@pilaster1-0.3", 19000], ["@pilaster1", 5500], ["@pilaster1+0.4", 19000],
                             ["@pilaster2-0.3", 19000], ["@pilaster2", 5000], ["@square", 4500]],
       shelf_keys={"hz": 5000, "keys": [["@open", 7], ["@open~2.5", 7], ["@open~3.0", 0]]},
       # the music has stopped dead: the city fills the silence (+3 dB), holds while the organ comes back under it,
       # and gives way a little once the organ is up
       gain_keys=[[k[0], k[1] + 5] for k in OPENING_GAIN] + [["@open~2.2", 8], ["@open~3.0", 7], ["@open~3.4", 3],
                                                             ["@pilaster1-0.3", 1], ["@pilaster1", -1.5],
                                                             ["@pilaster1+0.4", 1], ["@street", 0],
                                                             ["@pilaster2-0.3", 0], ["@pilaster2", -2.0]],
       fade_in=1.2, fade_out=0.3, fade_shape="power")
    el("city_walkers", "city", "passers-by on the stone below, low under the street", "375",
       src=[3.0, 30.0], start="@sash_clear", end="@square+0.6", hp=150, lp=7000, detone={}, rms_db=CITY_REF - 13,
       crest_db=14.0,
       width=1.3, fade_in=2.5, fade_out=1.0)
    # the square: IMG_5416's own sound in sync, matched to the street at the cut (inaudible hand-over); it outlasts
    # everything. When he leans out the clip's own "jump" is low thumps (handling/wind, < 150 Hz, L/R corr 0.99) that
    # read as an edit bump and pump the limiter, and after them the band stays 6 dB up (wind on the exposed mic; the
    # bumps reach up to ~500 Hz): the band below 500 Hz is clamped to its level before the lean (src 4.2-5.0) + 2 dB
    # from src 5.1 on (dethump), and its peaks are held to 11 dB over its RMS. The
    # city doubles where it is heard instead: +2.5 dB in 500 Hz-6 kHz over 0.4 s at the lean, kept from then on (he
    # stays leaning out), on top of the square's air coming in (city_square_air)
    el("city_square", "city", "the square, in sync (IMG_5416 4.1 on); the city doubles when he leans out", "IMG_5416",
       timemap={"shot": "square"}, start="@square-0.15", end="@duration", hp=50, detone={}, crest_db=11.0,
       dethump={"fc": 500.0, "thr_db": 2.0, "ref": [4.2, 5.0], "after": 5.1, "smooth": 0.02},
       band_keys={"lo": 500, "hi": 6000, "keys": [["@city_doubles-0.2", 0], ["@city_doubles+0.2", 2.5]]},
       # matched on the street before the pilaster shades it (gap_to 0.6) and the square before the lean (gap 0.2)
       match={"to": "city_open", "at": "@square", "win": 1.0, "gap": 0.2, "gap_to": 0.6}, fade_in=0.3, fade_out=1.75,
       fade_shape="power", step="@city_doubles", step_band=[500, 6000],
       # the arrival: the square itself comes up 1.5 dB with the most open view, and settles as the stone closes in
       gain_keys=[["@square_in", 0], ["@volute", 0.5], ["@climax", 1.5], ["@climax+1.0", 1.5], ["@settle", 0.5]])
    el("city_square_air", "city", "the width of the square as it opens, longer reflections", "346",
       src=[4.0, 30.0], start="@city_doubles-0.5", end="@duration", hp=120, polarity="flip_right", detone={},
       rms_db=CITY_REF - 4, reverb={"rt60": 1.8, "mix": 0.3, "predelay": 0.03},
       # the square's width: it opens fully with the most open view at the climax and narrows a little as the stone
       # closes in like a curtain (settle)
       gain_keys=[["@city_doubles-0.5", -8], ["@square_in", -1.5], ["@volute", -0.5], ["@climax", 2.0],
                  ["@climax+1.0", 2.0], ["@settle", -0.5], ["@end", -0.5]], fade_in=1.5, fade_out=1.75)


def kitchen() -> None:
    clean = {"notch": HUM, "hp": 60, "detone": {"fmin": 40.0}}
    # the room's own tone, the whole kitchen long (IMG_5419: the static kitchen; pieces joined, no loop heard)
    el("room_tone", "kitchen", "the kitchen's own tone (IMG_5419), hum notched, appliance lines removed", "IMG_5419",
       splice=[[0.2, 2.7], [2.3, 4.7], [0.8, 3.6], [1.5, 4.7], [0.3, 2.2]], xfade=0.6, start="@black_in",
       end="@open+0.15", rms_db=-57.0, fade_in=0.3, fade_out=0.15, **clean)
    # the clips' own sound in sync with their pictures (0.8x and the slow motion, pitch kept)
    el("walk_own", "kitchen", "the walk's own sound (IMG_5420), in sync", "IMG_5420",
       timemap={"shot": "walk"}, start="@walk.film_in", end="@bloom", rms_db=-56.0, fade_in=0.6, fade_out=0.05, **clean)
    # the morph dissolve (brew.film_in .. spout_out): the pour's take melts into the finished, dripping bed - the
    # first take's sound (its real pour) fades across it and is gone by spout_out, the later take's comes in under it
    el("bloom_own", "kitchen", "the dripper's own sound (IMG_5421), in sync through the slow motion; handling knock "
       "at src 4.05-5.0 replaced; gone by the end of the morph dissolve", "IMG_5421", timemap={"shot": "bloom"},
       start="@bloom", end="@spout_out", rb_window="short", repair=[[4.02, 5.02, 10.0]], rms_db=-56.0, fade_in=0.03,
       fade_out=0.75, fade_shape="power", **clean)
    # (the brew now shows only the finished bed, src 18.4-23.0: its handling - a tick at src 19.93-20.33 and two low
    # bumps at 20.36-20.56 and 21.45-21.68, no highs: not drips - replaced by the quiet bed of src 18.6-19.7)
    el("brew_own", "kitchen", "the dripping bed later (IMG_5421), in sync; three handling bumps replaced",
       "IMG_5421", timemap={"shot": "brew"}, start="@brew", end="@cup",
       repair=[[19.93, 20.33, 18.6], [20.36, 20.56, 19.05], [21.45, 21.68, 19.3]], rb_window="short",
       rms_db=-56.0, fade_in=0.75, fade_out=0.02, fade_shape="power", **clean)
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
    # the first water on the coffee, close and dry: a steady stream, played at its own speed (not stretched with the
    # slow motion: a stretched stream smears and turns chirpy); it fades across the morph dissolve and is gone by
    # spout_out (the dissolve's end): the later take shows only the finished bed - no kettle, no pour
    el("stream", "foley", "the thin stream on the coffee (real speed under the slow motion)", "1318",
       src=[3.2, 12.0], sync=[3.2, "@stream"], end="@spout_out",
       hp=160, lp=12000, detone={}, rms_db=-37.0, crest_db=12.0, width=0.5, fade_in=0.006, fade_out=0.75,
       fade_shape="power", onset="@stream",
       onset_before=0.05, onset_after=0.15)
    el("bloom_fizz", "foley", "the bloom: CO2 fizzing out of the wet coffee, faint", "3181",
       timemap={"shot": "bloom", "rate": 1.25, "anchor": ["@stream+0.25", 7.3]}, start="@stream+0.25",
       end="@spout_out", rb_window="short", hp=1800, rms_db=-55.0, width=0.7, fade_in=1.2, fade_out=0.75)
    for k, (dt, p, pn) in enumerate([(1.35, 2.0, -0.12), (2.9, 3.0, 0.1), (4.4, 1.0, 0.0)]):
        el(f"bloom_bubble{k + 1}", "foley", "a bubble breaking in the bloom", "1317", src=[0.05, 0.40],
           start=f"@stream+{dt}", pitch=p, hp=400, peak_db=-49.0 - k, fade_in=0.01, fade_out=0.08, pan=pn)
    # the brew is the finished bed: nothing but single drips into the glass server, slowing as it drains (the kettle
    # was set down long ago, off the film: no set-down)
    drips = [(0.30, 7.136, 4.0), (0.95, 1.090, 4.5), (1.65, 2.708, 3.5), (2.45, 3.394, 4.0), (3.35, 1.453, 5.0),
             (4.30, 6.616, 4.0), (5.3, 7.136, 3.0)]
    for k, (dt, ft, p) in enumerate(drips):
        el(f"drip{k + 1}", "foley", "a single drip into the glass server", "1879", src=[ft - 0.006, ft + 0.11],
           sync=[ft, f"@spout_out+{dt}"], pitch=p, hp=900, lp=14000, peak_db=-30.0 - 0.6 * k,   # (+5 dB: the brew's story)
           reverb={"rt60": 0.3, "mix": 0.18, "predelay": 0.004}, fade_in=0.002, fade_out=0.05, width=0.3,
           skip_after="@cup-0.3")
    # the cup: the quietest moment; the glass lip touches the porcelain; the slow amber pour into the printed city
    el("server_lip", "foley", "the glass server's lip touches the porcelain, tiny", "154", src=[0.10, 0.42],
       sync=[0.113, "@server_in"], hp=300, peak_db=-40.0, fade_in=0.002, fade_out=0.22, onset="@server_in")
    # (anchored on the file's audible contact at 0.23 s: its first touch at 0.116 is 20 dB down once stretched, so
    # the pour was heard 0.2 s late; the first hit on the empty porcelain is the hardest, so it is lifted 6 dB
    # against the splashes that follow - it is heard on the frame)
    el("pour_porcelain", "foley", "the coffee hits the empty porcelain, in slow motion (pitch kept)", "1310",
       timemap={"shot": "cup", "rate": 1.25, "anchor": ["@pour", 0.23]}, start="@pour", end="@slow2_end+1.1",
       rb_window="short", hp=140, lp=13000, rms_db=-38.0, crest_db=15.0, fade_in=0.012, fade_out=0.9, onset="@pour",
       gain_keys=[["@pour", 6], ["@pour+0.15", 6], ["@pour+0.45", 0]], onset_before=0.05, onset_after=0.6)
    el("pour_filling", "foley", "the cup filling, its pitch rising (slow, then the 0.8x real time)", "2826",
       timemap={"shot": "cup", "fit": [["@slow2_end", 0.55], ["@server_out-0.25", 3.4]]},
       start="@slow2_end", end="@server_out-0.05", rb_window="short", hp=150, rms_db=-38.5, crest_db=15.0,
       gain_keys=[["@slow2_end", 0], ["@hand+0.8", 0], ["@server_out-2.0", 5], ["@server_out-0.3", 5]],
       fade_in=0.8, fade_out=0.15)   # (after the first hit, under its splashes: the slow motion is 0.25 s long now)
    el("crema", "foley", "the crema fizzing in the full cup", "2833", src=[2.6, 6.4], tempo=0.7, rb_window="short",
       start="@hand", hp=2500, rms_db=-56.0, fade_in=1.5, fade_out=1.6, width=0.6)
    # (no server set-down: off screen under the score's build it stayed masked even 8 dB up - best band +2.8 dB -
    # and it is not a story beat; the server simply leaves frame)
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
    # the square: his other window's outer casement swings in from the right (IMG_5416 src 4.5-6.1: its dark frame
    # enters at the right edge), its hinge creaks in the open air, on the right
    # (4th-order high-pass at 300 Hz: the wind left in Mixkit 1163 out, the creak's 400 Hz-4 kHz forward)
    el("casement", "foley", "the outer casement swings in from the right, its hinge creaks", "1163", src=[1.95, 2.75],
       sync=[1.95, "@casement"], hp=300, hp_order=4, peak_db=-19.0, fade_in=0.03, fade_out=0.35, pan=0.25, onset="@casement",
       slap={"delays": [0.062, 0.118], "gains_db": [-14, -18], "lp": 4000})
    # off screen: his cup set down on the stone sill, close and dry, at the cue sheet's cup_on_sill: the score's
    # brass is off just before it (it was inaudible under the old score's ff there; +2.5 dB). If the score fills that
    # moment again, CUP = "@title_in+1.0" (where the score has come down) is the fallback.
    # (its 23 dB crest held to 20 at the element and its peak 3 dB lower: the same body, but the master limiter no
    # longer catches its click and ducks the square under it for 0.3 s)
    el("cup_on_sill", "foley", "his cup set down on the stone sill, off screen", "2933", src=[0.0, 0.45],
       sync=[0.069, CUP], hp=200, crest_db=20.0, peak_db=-18.5, fade_in=0.003, fade_out=0.12, pan=-0.15,
       onset=CUP, onset_before=0.03, onset_mode="attack")   # the contact, not the light pre-touch 59 ms before it


BELL3_DB = -6.5   # bell 3 under the flooding city (it swelled 6-8 LU over it)


def bells() -> None:
    bell = "617"   # a single strike, D (in key with the score), decays over 6 s

    el("bell1", "bell", "bell stroke 1: far off, muffled through the glass, over black", bell, src=[0.05, 6.3],
       sync=[0.100, "@bell1"], hp=90, lp=3500, rms_db=-56.0, pan=-0.25, width=0.6,
       reverb={"rt60": 3.4, "mix": 0.65, "predelay": 0.06}, lp_keys=GLASS_LP, onset="@bell1", onset_after=0.4)
    # bell 2 must be heard in the score's forte: the score now breathes just before it; +3 dB and a drier strike (the
    # strike, not the tail, carries it); its tail stays inside the forte
    el("bell2", "bell", "bell stroke 2: through the kitchen glass", bell, src=[0.05, 6.3], sync=[0.100, "@bell2"],
       hp=90, lp=4500, rms_db=-39.0, pan=-0.25, width=0.6, reverb={"rt60": 3.4, "mix": 0.35, "predelay": 0.06},
       lp_keys=GLASS_LP + OPENING_LP,
       onset="@bell2", onset_after=0.4)   # its tail is still ringing when the window opens: only its filter opens
    # bell 3 is struck just after the seal gives: it opens with the window (filter only - a struck bell never swells)
    # and sits under the flooding city
    el("bell3", "bell", "bell stroke 3: struck as the window opens, heard opening into the open air", bell,
       src=[0.05, 6.3], sync=[0.100, "@bell3"], hp=80, rms_db=-38.0, gain_db=BELL3_DB, pan=-0.2,
       reverb={"rt60": 3.6, "mix": 0.5, "predelay": 0.05},
       slap={"delays": [0.068, 0.125], "gains_db": [-11, -15], "lp": 3500},
       lp_keys=OPENING_LP, onset="@bell3", onset_after=0.4)
    # bell 4 in the last chord: +5 dB and a drier strike so it clears the city, its tail level with the score; its
    # minor-third partial (F4, 350 Hz) cut 6 dB
    # against the score's D major (F#)
    el("bell4", "bell", "bell stroke 4: open air over the square, the facades answer, a long tail", bell,
       src=[0.05, 6.3], sync=[0.100, "@bell4"], hp=80, lp=9000, rms_db=-34.0, crest_db=14.0, pan=-0.15, peq=[[350.0, -6.0, 10.0]],
       reverb={"rt60": 4.6, "mix": 0.3, "predelay": 0.05},
       slap={"delays": [0.085, 0.16, 0.31, 0.47], "gains_db": [-9, -12, -15, -19], "lp": 3200},
       gain_keys=[["@end", 0], ["@end+1.2", -40]], onset="@bell4", onset_after=0.4)


NOTES = [
    "IMG_5417 and IMG_5416 carry a street musician (sustained notes in A and D major, A = 437-439 Hz, +20-30 dB over "
    "the noise in 16k-point spectra). Under the organ score and through the kitchen glass that would be a second, "
    "unrelated music, so every city bed is detoned: sustained tonal lines are pulled down to the noise floor around "
    "them (tonal prominence 20.9 -> 11.9 dB, the noise baseline; footsteps, voices' breath and the air are kept).",
    "The kitchen clips' tracks have mains hum (50/100/150 Hz, +17-36 dB) and appliance lines (100, 161, 179, 223, "
    "299, 401 Hz); the mains line sits at 49.3 Hz in these clips. Notched at 49.3, 50, 100-250, 223 and 300 Hz and "
    "detoned from 40 Hz: every line is now within 4 dB of its neighbours. IMG_5421's handling knock (src 4.02-5.02) "
    "and a tick at src 19.93-20.33 are replaced by clean material of the same clip. IMG_5422's own track is not used.",
    "Speed: the clips' own sound follows the cue sheet's speed curve (0.8x, 0.5x, eased ramps) through rubberband, "
    "pitch kept; library textures under the slow motion are laid on the same curve (rate 1.25: real speed where the "
    "picture is at 0.8x, 0.625x in the 0.5x stretch). Nothing is slowed by resampling; only the drips and the "
    "kettle's set-down are pitched (by resampling, to make them smaller or heavier) and they are not time-locked to frames. "
    "Rubberband processes the two channels together (apart, it decorrelated the water: L/R 0.95 -> 0.42) and uses its "
    "short window (less smear; pre-echo on a click 8-10 ms at 0.625-0.8x, about 14 ms at 0.5x). The steady first "
    "stream is not stretched at all.",
    "Set-downs: the locked edit has no kettle in the brew (the morph dissolve lands on the finished, dripping bed), so "
    "the kettle's set-down and the later pour are gone; the first stream and the dripper's own first take fade across "
    "the dissolve and are gone by spout_out. The glass server's set-down (3148) is left out: under the score's build "
    "it stayed masked even 8 dB up, and it is not a story beat. The cup on the stone sill is 2933, at the cue sheet's "
    "cup_on_sill.",
    "turn_away -> sill: the catalogue has no cloth rustle; nothing is added (the street runs on, continuous).",
    "The score is placed at 0 if its file exists at mix time AND is as long as the film (one frame of tolerance: a "
    "score composed to an earlier cut is not mixed); its gain is set so that the city stem sits 8 dB under it at the "
    "climax (window climax-0.5 .. climax+2.5; the square itself is 1.5 dB up there now); it is faded out from "
    "end+0.25 to end+1.35 so that the city is the last sound. It is ducked 6 dB for 1.5 s from its return after the "
    "latch (the city's first moment at full range is heard; the organ grows out of it). Its own accents are held on "
    "its bus at the master's ceiling (-2 dBFS after the master, release 0.3 s; it was -4 with up to 4.8 dB of make-up "
    "to hold the climax balance: on the 23:36 score that took the climax's 4.3 dB lift down to 0.3 dB - review 1), "
    "and the make-up is capped at 1 dB.",
    "Review 1 (the score must ARRIVE at the climax): measured on the mix, 2 s around the climax must be >= 3 dB over "
    "the 4 s before square_in. The ride gives 2 dB of it (-1 dB before the square, +1 dB through the climax); the "
    "square's own sound +1.5 dB and its air +3.5 dB at the most open view; and the master gives up loudness (from "
    "-14 down to at most -16 LUFS, in 0.5 dB steps) before its limiter takes the lift away.",
    "Review 2 (the flood): the glass is gone at the cut to the window (7 kHz on the cut frame, open 0.3 s later) and "
    "the city is at the open street's level on the cut frame, +3 dB 0.2 s later; with a score, the city's first 1.5 s "
    "after the cut is made at least as loud as the score's last bar before the latch (flood_match: the city bus "
    "lifted from the latch, held to the music's return, released over 2 s).",
    "The score is ridden 2 dB down in the kitchen (music_keys; the step is in its silence after the latch): with "
    "the 23:36 score the kitchen music sat 4-7 dB higher against the water and the kettle than before.",
    "Before the latch the city behind the glass is not heard under the score's forte (about 18 LU under it): it is "
    "texture in the kitchen's quiet moments, not a voice pressing on the pane.",
    "Fader ride (mix_keys): the quiet kitchen (walk, bloom, brew, the empty mug) +6 dB, back to 0 over the first 2 s "
    "of the pour (the score's build to the latch is left as composed); -1 dB from the red houses to the volute, +1 dB "
    "through the climax to the title, then 0: the loudness range fits a phone speaker and the climax is the arrival "
    "of the second half. Limiter release 200 ms (40 ms pumped under organ pedal).",
    "The kitchen is long and quiet: it stays alive but distant - the room's own tone, the clips' own sound, the "
    "kettle, the water, and the city behind the glass, which on the short empty mug only steps back to 22 dB under "
    "its open level (it was 32 dB under: a hole) and comes closer as LOOK 3 pushes into the pane (2.1 kHz, 10.5 dB "
    "under at the latch).",
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
                  "end_fade": ["@end+0.25", "@end+1.35"], "match_duration_tol_s": 1 / 24},
        # review 2: the city's first moment after the cut at least as loud as the score's last bar before the latch
        # (the bar from score_report.json's bar_by_bar if it was made for this cue sheet, else the last 2 s)
        "flood_match": {"bus": "city", "window": ["@open+0.1", "@open+1.6"], "margin_db": 0.5, "max_db": 6.0,
                        "attack": ["@latch", "@open+0.05"], "hold_to": "@music_return", "release_s": 2.0,
                        "fallback_bar_s": 2.0},
        # [t0, t1, dB, attack, release]: the city's first moment at full range is heard (the score breathes before
        # bell 2 itself now, so bell 2 needs no duck)
        "music_ducks": [["@music_return", "@music_return+1.5", -6.0, 0.05, 0.6]],
        # the score's balance in the kitchen: 2 dB under its level at the climax (the step is made in its silence
        # after the latch), so the water, the kettle and the set-downs keep their place against it
        "music_keys": [[0.0, -2.0], ["@latch+0.02", -2.0], ["@latch+0.5", 0.0]],
        # the fader ride: the quiet kitchen +6 dB (walk, bloom, brew, the hush), the climax -1.5 dB
        # (the lift ends as the coffee pours: the score's build from the pour to the latch is left as composed, and
        # the climax stays the loudest moment of the film)
        "mix_keys": [[0.0, 6.0], ["@pour-0.5", 6.0], ["@pour+1.5", 0.0], ["@red_houses", 0.0], ["@red_houses+1.5", -1.0],
                     ["@volute", -1.0], ["@climax-0.3", 1.0], ["@title_in+1.0", 1.0], ["@bell4", 0.0], ["@end", 0.0]],
        "limiter_release_s": 0.2,
        # the score's own accents held on its bus at the master's ceiling; the make-up that holds the climax balance
        # after it is capped (review 1: -4 dBFS + 4.8 dB of make-up flattened the climax)
        "music_peak_db": -2.0, "music_peak_release_s": 0.3, "music_makeup_max_db": 1.0,
        "notes": NOTES,
        "glass_report": ["city_glass", "city_open", "bell3"],
        "ceiling_db": -2.0, "targets": {"mix": -14.0, "sfx_only": -16.0},
        # the master gives up loudness (0.5 dB steps, down to mix_min) before its limiting takes the arrival away
        "arrival": {"pre": ["@square_in-4.0", "@square_in"], "climax": ["@climax-1.0", "@climax+1.0"], "min_db": 3.0,
                    "mix_min": -16.0},
        "sections": [["black_in", "@black_in", "@fade_up"], ["walk", "@fade_up", "@bloom"],
                     ["bloom", "@bloom", "@brew.start"], ["brew", "@brew.start", "@cup"],
                     ["cup_quiet", "@cup", "@pour"], ["cup_pour", "@pour", "@server_out"],
                     ["look3", "@server_out", "@latch"], ["latch_to_sash", "@latch", "@sash_clear"],
                     ["no_music_gap", "@sash_clear", "@music_return"], ["street", "@music_return", "@turn.start"],
                     ["turn", "@turn.start", "@square"], ["square_build", "@square", "@square_in"],
                     ["pre_square_4s", "@square_in-4.0", "@square_in"], ["volute", "@square_in", "@climax"],
                     ["climax", "@climax-0.5", "@climax+2.5"], ["release", "@climax+2.5", "@end"],
                     ["black_out", "@end", "@duration"]],
        # the story, measured (pipeline/sound3.py story_qc): each check has its pass rule in the mixer
        "story_qc": {
            "flood": {"latch": "@latch", "open": "@open", "sash_clear": "@sash_clear",
                      "street": ["@music_return+0.6", "@turn.start"]},
            # review 2: as loud as the score's last bar (with a score); review 1: the climax arrives
            "flood_vs_score": {"window": ["@open+0.1", "@open+1.6"], "min_lu": 0.0},
            "arrival": {"pre": ["@square_in-4.0", "@square_in"], "climax": ["@climax-1.0", "@climax+1.0"], "min_db": 3.0},
            "bells_vs_city": {"window": ["@open+0.5", "@open+2.5"], "min_lu": -3.0},
            "no_swell": ["bell2", "bell3"], "onsets": {"bell2": "@bell2", "bell3": "@bell3"},
            "lean": {"t": "@city_doubles"},
            # [element, event, window from, to (s)]: transients 0-80 ms, bell strikes 0-150 ms, the creak 0-400 ms
            "masking": [["drip1", "@spout_out+0.30", 0.0, 0.08],
                        ["pour_porcelain", "@pour", 0.0, 0.2], ["bell2", "@bell2", 0.0, 0.15],
                        ["latch", "@latch", -0.01, 0.07], ["casement", "@casement", 0.0, 0.4],
                        ["cup_on_sill", CUP, -0.005, 0.08], ["bell4", "@bell4", 0.0, 0.15],
                        ["kettle_off", "@kettle_click", 0.0, 0.08]],
            "hum": {"bus": "kitchen", "freqs": [50, 100, 150, 223, 300, 400],
                    "ranges": [["@fade_up+1.0", "@kettle_click"], ["@bloom", "@cup"], ["@cup", "@latch"]]},
            "loudness": {"lra_max": 15.0, "st_max": -8.0, "limiter_max_db": 2.0,
                         "st_min": [["@fade_up+1.5", "@cup", -28.0], ["@pour", "@latch", -28.0], ["@cup", "@pour", -30.0]]},
            "return": {"t": "@music_return", "first": 1.5, "first_max_lu": 2.0,
                       "street": ["@music_return", "@turn.start"], "street_max_lu": 8.0},
        },
        "elements": E,
    }


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    sp = build()
    json.dump(sp, open(os.path.join(here, "sound3.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    film = json.load(open(os.path.join(here, sp["cuesheet"]), encoding="utf-8"))["duration"]
    if os.path.exists(SCORE):
        import soundfile as sf
        i = sf.info(SCORE)
        ok = abs(i.frames / i.samplerate - film) <= 1 / 24
        state = f"score {i.frames / i.samplerate:.3f} s for a {film:.3f} s film: " + ("mixed" if ok else "NOT mixed (another cut)")
    else:
        state = "no score yet"
    print("wrote sound3.json:", len(sp["elements"]), "elements;", state)
