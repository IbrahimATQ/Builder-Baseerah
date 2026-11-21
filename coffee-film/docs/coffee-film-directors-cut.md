# THE CITY CAN WAIT — the coffee film, director's cut (2160×3840, 24 fps, 37.5 s)

## What was asked
The first cut ("A slow morning in Warsaw") was rejected as basic: "it could be the outcome of my little brother
doing editing ... you could use sound effects, pouring coffee ... VFX ... transitions ... You are in the position of
director ... it's not highly 4K Ultra HD ... the music ... looks like a massage spa music. We need ... something
closer to Interstellar ... Don't limit your capabilities." And then: one file only — "just give me 1 ultra 4K high
definition video".

## The idea
A film about time. Outside, the city races: the street and the square become long-exposure timelapses whose
walkers turn to streaks, a wall clock ticks and doubles and doubles again, a pipe-organ ostinato accelerates with
it, and the cutting accelerates with the music. On 13.500 time stops dead: the streaks snap into sharp, frozen
people, the colour drains, the lens goes soft into black. Inside, the coffee ritual happens slowly: the kettle's
stream on the coffee, a match cut on the stream to the coffee pouring into the WARSZAWA mug, the climax as the cup
fills, the full cup held on the resolution chord with steam rising. At the end the city waits outside the window:
*the city / can wait.* One last tick, black.

`data/cuesheet.json` is the contract shared by picture, score and sound: every hit (2.0 smash to black, 3.0 window,
7.0, 11.0 whip, 13.5 stop, 15.0 inside, 21.0 match cut, 27.0 climax, 29.0 resolution, 31.5, 36.5 last tick) lands on
a picture event, a musical event and a sound event within a few milliseconds.

## The film
| Film (s) | Picture | Sound |
|---|---|---|
| 0.0–2.0 | flash-forward: the amber coffee stream into the mug in real slow motion (0.4×, learned frame interpolation on the clean part of the pour only) | the pour, close, slowed; a low organ pedal D swelling from silence |
| 2.0 | smash cut to black | a deep hit with a body a phone can play; the first tick |
| 3.0–7.0 | the window opens (real speed), amber light from the window side; the camera's turn becomes a speed-ramped swing with real motion blur onto the street | latch, creak, the city floods in; the organ ostinato in 8ths; whooshes |
| 7.0–11.0 | the street as a trail-exposure timelapse (walkers streak, buildings stay sharp); WARSZAWA / *stare miasto* in the sky | ostinato in 16ths, ticks twice a second, a riser |
| 11.0 | whip pan: the street and the square side by side, as one swing | whoosh on the beat |
| 11.0–13.5 | the race: square and street cut against each other ever faster (1 s, 0.5, 0.25, 0.25, 0.125, 0.125) | 32nds, a rising organ cluster, ticks four times a second |
| 13.5–15.0 | TIME STOPS: frozen people, colour drains, push-in toward them, lens defocus into black | everything sucked into one hard stop; a deep hit; one low organ D breathing |
| 15.0–21.0 | inside: the kettle's stream on the coffee bed, racking into focus | the kettle, soft bubbles; quiet organ triads, a low piano motif; a pendulum clock every 2 s |
| 21.0 | match cut on the stream (the two streams land at the same place on screen) | the pour |
| 21.0–29.0 | the coffee into the mug; a slow push into the rising crema, peaking on 27.0 | the real pour; the organ and strings build through a valley into the climax (27.0, crash, full organ) |
| 29.0–32.0 | the full cup held on its last sharp frame; real steam rising; the frame draws back; amber light through the dissolve | the D-major resolution decaying |
| 31.5–36.5 | the view through the kitchen window; *the city / can wait.* written in the pane | the city faint through the glass, a distant church bell (in key), ticks at 34 and 36 |
| 36.5 | the last tick; black | nothing |

## How it is made
* `pipeline/prep.py` — the iPhone clips upright, every real 30 fps frame shown once at 24 fps (0.8×), stabilised
  (vid.stab), 10-bit 4K intermediates. The street plate uses only the steady wide part of its take, so it is real 4K
  (an earlier version included a swing-away that made the stabiliser zoom in 2.5×).
* `pipeline/slowmo.py` — RIFE v4.26 (MIT), weights from the author's own repository, run on CPU; only the stretch
  that interpolates cleanly is used.
* `pipeline/grade.py` — per-shot 3D LUTs: cool, grey city; warm kitchen; highlights that roll off; a toe that falls
  smoothly to black.
* `pipeline/render2.py` — the picture engine, in 16 bit: time remaps; a shutter that opens with the speed and
  per-pixel motion blur from optical flow; trail exposures aligned to the camera; freezes; the side-by-side whip;
  lens defocus with bokeh; light in linear light that moves with the framing; tracked plate layers (the steam);
  screen-blended filmed light leaks with radial masks; dissolves in linear light; titles laid out at 4× and placed
  with sub-pixel precision; bloom, clarity, sharpening, acutance on the soft interiors, highlight roll-off, live
  grain.
* `pipeline/compose.py` — the original score: sampled pipe organ (16'/8' pedal, open plenum, stopped flute), piano,
  strings, timpani, cymbals (VSCO-2 Community Edition), every note measured and tuned, a synthetic church reverb
  that is gated on the two hard stops. D minor, 60 bpm with the clock, ending in D major. No melody, chord
  sequence or motif of any existing score is quoted.
* `pipeline/sound2.py` + `data/sound2.py` — the sound: the clips' own sound (slowed with the picture), 25 recorded
  effects from Mixkit's free library, three clock voices, the score; ducks so the pour and the ticks carry; mastered
  to −14 LUFS, true peak ≤ −2 dBTP.
* `pipeline/qc2.py` — checks on the finished file (format, privacy tags, motion, blacks, levels, loudness, sync,
  titles' safe area, photosensitivity screen).

## Reviews
Three rounds of independent reviewers (direction, colour and resolution, effects artefacts, typography, sound, and
a lead reviewer who re-measured every claim) looked at the film frame by frame and measured its sound. Every change
they asked for was tested against an acceptance measurement before it was kept. Among them: the timelapse that did
not read as a timelapse (now trails), the street plate that was not real 4K (re-prepared), a whip that mirrored the
frame (now a real side-by-side pan), the payoff cup that went soft as the phone refocused (now held on its last
sharp frame), a climax that did not arrive (a valley before it, no sub-bass feeding the limiters, a crash), ticks
masked at their peak (the score dips under them), hits that vanished on a phone (mid-body impacts), the bloom
music that could read as spa (no harp, plain triads, a low piano line), and the fast swing, which failed the
photosensitivity screen until its shutter was lengthened.

## Licences
`data/licences2.json` (built by `data/licences2.py` from what the cut uses): the commissioner's own footage and
sound; the score made from VSCO-2 CE (CC0); 25 Mixkit sound effects and 3 Mixkit video elements (steam, light
leak), each with its own free-licence record; Cormorant Garamond (SIL OFL 1.1); RIFE (MIT).

## The delivered file
`output/The-City-Can-Wait_4K_2160x3840.mp4` (not in the repository): 2160×3840, 24 fps, 900 frames (37.5 s), H.264
High@5.1, two-pass 80 Mbps from a 10-bit near-lossless intermediate, AAC 320 kbps stereo, 359 MiB, no location or
device tags. QC (`data/qc_directors_cut_4K.json`): 11/11 — format, duration, privacy, motion (no repeated frames or
jumps), blacks, levels, loudness −14.0 LUFS / true peak −1.7 dBTP after AAC, sound in sync (0 ms, r = 0.9999),
titles in the safe area, photosensitivity screen (2.1 % flashing area against an 11 % limit). A release check of
the file itself (picture at full 4K, sound decoded from the AAC) found the encode within 42–46 dB PSNR of the
master with no grain pulsing, and a stutter at the start of the swing, fixed before delivery.

## Reproducing it
```
python data/plan2.py && python pipeline/grade.py data/plan2.json LUTS
python pipeline/compose.py data/cuesheet.json SCORE
python data/sound2.py && python pipeline/sound2.py data/sound2.json SOUND
python pipeline/render2.py data/plan2.json LUTS OUT.mp4 --codec h264_10 --crf 8   # then the delivery encode
python pipeline/qc2.py FILM.mp4 data/plan2.json SOUND/mix.wav QC.json
```
