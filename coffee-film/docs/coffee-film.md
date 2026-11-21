# "A slow morning in Warsaw": the coffee film (2160×3840, 24 fps, 40 s)

## What was asked
The commissioner filmed a V60 pour-over and the view over Warsaw's Old Town, on an
iPhone (six clips, 4K, 30 fps). Of three directions offered he chose the first: *a slow morning in
Warsaw*, 30–40 s, vertical, the city through the window to the cup, mostly the scene's own sound with a soft music
bed, minimal text. His instruction: "make sure it is VERY BEAUTIFUL!!"

## The film (31.5 s)
`data/plan.py` is the edit (it writes `data/plan.json`). Film time runs 0.8× the camera's time: every real frame
of the 30 fps footage is shown once at 24 fps. Nothing is blended or interpolated, and hand-held motion becomes slower
and calmer.

| Film (s) | Shot | Picture | Into it |
|---|---|---|---|
| 0.0 | square | the red houses and the castle square below, people crossing, a stone volute in front; "Warszawa · STARE MIASTO" in warm charcoal in the pale sky | from black, 0.2 s |
| 6.2 | street | the long street from above, people walking | dissolve 0.8 s |
| 12.6 | bloom | inside, on the music's swell: the kettle's stream meets the coffee, the window and red roofs behind | dissolve 0.5 s |
| 19.5 | pourcup | the stream of coffee into the WARSZAWA mug, softly lit, until the cup is full | cut, on a beat |
| 26.9 | roofs | the view through the kitchen window: red roofs, the brick church, the sky; "the city can wait." in the sky pane, held 2.5 s | dissolve 1.0 s |
| 30.6–31.1 | | fade to black, then 0.4 s of black | |

The story runs from the city to the cup and back to the window. The music fades with the last shot, and the city's own
murmur, heard through the window, carries the last line.

## Three cuts, two independent reviews
Two reviewers, each seeing the film fresh, looked at it frame by frame against the brief ("VERY beautiful"). Every
finding was measured before it was acted on.

| Finding | Change |
|---|---|
| The grade turned cold exactly where it should be warmest; the mug sat in blue shadow (b* −3.5, L 36) | Inside shots warmed and lifted, with shadows no longer cool; a soft light on the mug |
| The kitchen-counter shot was the weakest frame (cluttered, soft, auto-exposure jump) | Removed |
| The brew ran 11.5 s; the closer brew shot was the least beautiful frame, and its dissolve showed two dripper rims at once | Brew is one 6.9 s shot |
| The scale's green LED glowed through the dripper | Keyed out by hue in the lower part of the frame (`key_green` in render.py), so the green copper roof in the window is untouched |
| No hook in the first second: window bars over a plain wall | The film opens on its most beautiful frame, the square, with the title in its sky |
| A grey band behind the title; the small line thin and lost on ochre | Title set in warm charcoal on the pale sky, without a band |
| The mug shot ran 10.5 s, with a sliver of glass, fingertips and late blotchy bubbles | It starts as the stream enters the cup and leaves when the cup is full; cropped to keep the hand out |
| The end line crossed the pouring glass, then got no time to land | The ending is the view through the window; the line holds 2.5 s, then 0.4 s of black |
| The quiet first half was 8–10 LU under the pour | Piano half +4 dB, pour −3 dB, city +3 dB: loudness range 10.8 → 6.9 LU |
| A tick in the square shot (vid.stab tripod mode on a stretch where the camera had moved) and a 2 px tick in the street | Both re-stabilised with smoothing: 0.1–0.3 px residual |

## Music and sound (`pipeline/sound.py`)
- **Music**: Mixkit 599 "Possible Dreams" (Eugenio Mininni), Mixkit Stock Music Free License, entered at 9.83 s of the
  track. Its sparse piano phrases fall at 1.9 and 7.7 s (the city), and the strings swell at 12.6 s as we go inside and
  the water meets the coffee. The music fades out under the last shot. It was chosen from 18 candidates
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
- Titles in Cormorant Garamond (SIL OFL), in warm charcoal on pale sky: "Warszawa" in italic over small spaced
  capitals "STARE MIASTO" with a hairline between; at the end "the city can wait." in the sky pane of the window,
  like writing on the glass. Each fades in with a small rise and a focus pull.

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
All three delivered files pass all 11 checks (`data/qc_4K_9x16.json`, `data/qc_1080x1920_share.json`, `data/qc_natural.json`).

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
