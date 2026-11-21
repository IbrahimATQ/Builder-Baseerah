# "A slow morning in Warsaw": the coffee film (2160×3840, 24 fps, 40 s)

## What was asked
The commissioner filmed a V60 pour-over in his kitchen in Warsaw's Old Town, and the view from his window, on an
iPhone (six clips, 4K, 30 fps). Of three directions offered he chose the first: *a slow morning in
Warsaw*, 30–40 s, vertical, the city through the window to the cup, mostly the scene's own sound with a soft music
bed, minimal text. His instruction: "make sure it is VERY BEAUTIFUL!!"

## The film
`data/plan.py` is the edit (it writes `data/plan.json`). Film time runs 0.8× the camera's time: every real frame
of the 30 fps footage is shown once at 24 fps. Nothing is blended or interpolated, and hand-held motion becomes slower
and calmer.

| Film (s) | Shot | Picture | Into it |
|---|---|---|---|
| 0.0 | window | the window opens on the painted (sgraffito) facade across the street; "Warszawa · STARE MIASTO" | from black, 0.35 s |
| 6.2 | square | red houses and the square below, people crossing, a stone volute in front | dissolve 0.8 s |
| 12.0 | street | the long street from above, people walking | dissolve 0.8 s |
| 14.4 | kitchen | inside: the counter under the window, grinder, kettle, scale | dissolve 0.5 s |
| 16.93 | bloom | the gooseneck's stream meets the coffee bed | cut, on the music's swell |
| 23.83 | spiral | closer: the slow spiral pour, the bed bubbling | cut, on a beat |
| 28.44 | pourcup | one take: coffee from the glass server into the WARSZAWA mug (it lands on a beat at 29.36), then the camera draws back to the window and the church; "the city can wait." | cut, on a beat |
| 39.0–40.0 | | fade to black | |

The story is outside to inside to the cup, and the last frame returns to the window it started from.

## Music and sound (`pipeline/sound.py`)
- **Music**: Mixkit 599 "Possible Dreams" (Eugenio Mininni), Mixkit Stock Music Free License, entered at 5.5 s of the
  track. Its sparse piano phrases fall at 1.0, 6.2 and 12.0 s (the city), the strings swell at 16.93 s as the water
  meets the coffee, and the section dies away from 36.3 s as the camera draws back. It was chosen from 18 candidates
  by measured tempo, percussion share, brightness and structure, and its spectrogram was read: piano phrases with
  space between them, then a swell.
- **Scene sound**: each shot carries its own recorded sound (city murmur from the window, the quiet room, the kettle's
  stream, the coffee falling into the mug), slowed to 0.8× with the pitch kept, cleaned of rumble, crossfaded with
  the picture. The music steps back 3.5 dB while the coffee is poured into the mug.
- **Masters**: `mix.wav`, −14 LUFS, true peak −1 dBTP; and `natural.wav`, the scene sound alone at −16 LUFS, for
  posting with a platform's own music.

## Look (`pipeline/grade.py`, `pipeline/render.py`)
- One grade function, baked into a 65-point 3D LUT per shot and applied by ffmpeg in 16-bit. It adds per-shot exposure
  and warmth (the kitchen and coffee shots get more of both), a gentle S curve with highlights that roll off (the
  windows), slightly lifted cool blacks (a soft matte), warm highlights against cool shadows, rich reds and oranges
  (brick, roofs, coffee), and held-back greens and blues (the scale's green LED, the grey sky).
- In the render: a slow push-in on most shots, a warm bloom around highlights, a vignette, and fine film grain, which
  also dithers the 16-bit picture to 8 bits.
- Titles in Cormorant Garamond (SIL OFL): "Warszawa" in italic over small spaced capitals "STARE MIASTO" with a hairline
  between; at the end "the city can wait.", set over the dark counter above the mug. Each fades in with a small rise
  and a focus pull, over a soft pool of shade, with no box.

## Preparing the footage (`pipeline/prep.py`, `data/sources.json`)
- The iPhone timestamps were checked first: no dropped frames in any clip, so frame-for-frame slow motion is even.
- Each stretch is decoded upright, retimed to 24 fps frame for frame, stabilised in two passes (vid.stab) and stored as
  10-bit 4K. Residual shake was then measured by phase correlation between frames: under 3 px at 4K (95th percentile)
  in every shot used.
- **Two lessons from this film:**
  - vid.stab's *tripod* mode is only safe when the camera really was still. On a stretch where it had moved, the
    square shot jittered by up to 70 px per frame. It was re-stabilised with smoothing instead (0.1 px residual).
  - A slow pan across a facade of white-framed windows failed the photosensitivity screen (0.23 against a limit of
    0.11): rows of high-contrast window frames slid through the picture. The pan was replaced by a held shot, and the
    whole film now measures 0.02.

## Checks (`pipeline/qc.py`)
File format (9:16, 24 fps, H.264 High, BT.709); duration; no location or device tags (the originals carried GPS
coordinates); no repeated frames and no jumps inside shots; no black frames outside the fades; levels inside EBU R103,
measured after a light low-pass; sound format, loudness and true peak; the sound in the file is the intended master,
in sync; titles inside the platforms' safe area; the photosensitivity screen.

## Rebuild
```
V=/home/user/film/venv/bin/python; R=coffee-film
$V $R/pipeline/prep.py $R/data/sources.json RAW PREP            # stabilised 10-bit stretches
$V $R/data/plan.py                                              # the edit -> plan.json
$V $R/pipeline/grade.py $R/data/plan.json LUTS                  # one LUT per shot
$V $R/pipeline/render.py $R/data/plan.json LUTS picture.mp4 --jobs 3          # add --scale 0.5 for a quick look
$V $R/pipeline/sound.py $R/data/plan.json $R/data/sources.json RAW SOUND     # mix.wav and natural.wav
ffmpeg -i picture.mp4 -i SOUND/mix.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 320k -map_metadata -1 -movflags +faststart film.mp4
$V $R/pipeline/qc.py film.mp4 $R/data/plan.json SOUND/mix.wav qc.json
```
`COFFEE_PREP` sets where plan.py looks for the prepared stretches.
