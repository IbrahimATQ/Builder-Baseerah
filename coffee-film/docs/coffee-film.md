# "A slow morning in Warsaw": the coffee film (2160×3840, 24 fps, 40 s)

## What was asked
The commissioner filmed a V60 pour-over and the view over Warsaw's Old Town, on an
iPhone (six clips, 4K, 30 fps). Of three directions offered he chose the first: *a slow morning in
Warsaw*, 30–40 s, vertical, the city through the window to the cup, mostly the scene's own sound with a soft music
bed, minimal text. His instruction: "make sure it is VERY BEAUTIFUL!!"

## The film
`data/plan.py` is the edit (it writes `data/plan.json`). Film time runs 0.8× the camera's time: every real frame
of the 30 fps footage is shown once at 24 fps. Nothing is blended or interpolated, and hand-held motion becomes slower
and calmer.

| Film (s) | Shot | Picture | Into it |
|---|---|---|---|
| 0.0 | window | the window opens on the painted (sgraffito) facade across the street; "Warszawa · STARE MIASTO", up within the first second | from black, 0.2 s |
| 3.8 | square | red houses and the square below, people crossing, a stone volute in front | dissolve 0.8 s |
| 7.7 | street | the long street from above, people walking | dissolve 0.8 s, on a piano phrase |
| 12.6 | bloom | inside: the gooseneck's stream meets the coffee bed, the window and red roofs behind | dissolve 0.5 s, on the music's swell |
| 18.35 | spiral | closer: the slow spiral pour (time passing) | dissolve 0.6 s, on a beat |
| 21.25 | pourcup | one take: coffee from the glass server into the WARSZAWA mug, which is softly lit, then the camera draws back toward the window | cut, on a beat |
| 31.75 | roofs | the view through the kitchen window: red roofs, the brick church, the sky; "the city can wait." set in the sky pane | dissolve 1.0 s |
| 34.9–36.0 | | fade to black | |

The story runs from outside to inside to the cup and back to the window. The music ends at about 34 s, and the city's
own murmur carries the last line.

## Two reviews
An independent reviewer looked at the first cut frame by frame and called it nice but not yet very beautiful, because
it grew colder, darker and more cluttered as it went. Changes:

| Finding | Change |
|---|---|
| The grade turned cold exactly where it should be warmest; the mug sat in blue shadow (b* −3.5, L 36) | Inside shots warmed and lifted, with shadows no longer cool; a soft tracked light on the mug |
| The kitchen-counter shot was the weakest frame: cluttered, soft, auto-exposure jump, neon scale display | Removed; the street dissolves straight into the brew, which already shows the window |
| The brew ran 11.5 s, and the second shot read as a jump cut | Brew 8.7 s; the closer shot now dissolves in (time passing) |
| The green LED glowed through the dripper | Its hue loses its colour and half its light (`led` in grade.py) |
| No hook in the first second | The film starts later in the window shot; the title is up within a second |
| A grey band behind the title; the small line too thin | The band is almost gone, with a stronger glyph shadow; "STARE MIASTO" is larger |
| The end line crossed the pouring glass; the rack and the camera's drift showed at the end | The ending moved to the view through the window; the cup shot is cropped in a little |
| The first half was 8–10 LU quieter than the pour | Piano half +4 dB, kettle −3 dB, city +3 dB: loudness range 10.8 → 6.9 LU |

## Music and sound (`pipeline/sound.py`)
- **Music**: Mixkit 599 "Possible Dreams" (Eugenio Mininni), Mixkit Stock Music Free License, entered at 9.83 s of the
  track. Its sparse piano phrases fall at 1.9 and 7.7 s (the city), the strings swell at 12.6 s as we go inside and
  the water meets the coffee, and the section dies away from about 32 s, under the last shot. It was chosen from 18 candidates
  by measured tempo, percussion share, brightness and structure, and its spectrogram was read: piano phrases with
  space between them, then a swell.
- **Scene sound**: each shot carries its own recorded sound (city murmur from the window, the quiet room, the kettle's
  stream, the coffee falling into the mug), slowed to 0.8× with the pitch kept, cleaned of rumble, crossfaded with
  the picture. The music steps back 3 dB while the coffee is poured into the mug, and its quiet piano half is lifted 4 dB.
- **Masters**: `mix.wav`, −14 LUFS, true peak −1.5 dBTP; and `natural.wav`, the scene sound alone at −16 LUFS, for
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
