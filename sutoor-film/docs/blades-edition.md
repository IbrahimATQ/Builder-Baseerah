# «النِصالُ عَلى النِصالِ», the Blades edition (2160×3840, 24 fps, 31 s)

## What was asked
- "Still not the cinematic journey that I was hoping for, and the burning scenes is not good … They look purely AI generated, purely fake."
- "The voice also looks isolated. I'm thinking about getting the voice back without isolating the music, perhaps using the same music that has been already in the previous video."
- "I think the whole journey needs to be replanned and rebuilt for it to be a very cinematic way, like someone who has created it has a very good cinematic editing, montage, effects, great ones."
- Earlier, still standing: "It just like a video with a text in front of it … make it related, make it sensible", and "add modern footage as well with train clock or something".

## What this edition does differently
1. **The original soundtrack is back, untouched.** The film runs on the reel's own mix (the reciter's voice in the music it was mixed with), at its own pace. Film time is recording time: 31.0 s. No separation, no stretching, no re-scoring. Recorded effects sit under it (section 5).
2. **No simulated burning paper.** The reference reel is real phone footage of real calligraphy burning; three rounds of simulation never passed as real. This edition has no burning-paper scene. If real strips are filmed (`docs/paper-shoot-guide.md`, `pipeline/make_burn_strips.cjs`), they cut straight in (section 8).
3. **Real footage only, cut as a montage.** 24 shots in 31 s. Every cut falls on a spoken word's onset or on a music accent. Speed ramps, one whip, a zoom punch, flashes, dissolves that pass through a double exposure, an eyeline match, an impact jolt.
4. **The words are set into the shots.** One or two words per row, large, arriving as they are spoken, inside the shot they are spoken over and in that picture's own dark space. The first word lies in the earth and a hand smooths the earth over it; a foot steps in front of «وَتَمشي»; «الأَوالي» lies over a footprint the sea is coming for; flames, sparks and falling sand pass in front of others; branches cross them; a clock dial carries one like a numeral; the word that means "shattered" cracks apart.

## 1. The cut
`data/blades/plan.py` is the edit: every shot, cut, ramp, transition and word placement, with the reasons as comments. Running it writes `data/blades/plan.json`, which the pipeline builds from.

| Start (s) | Shot | Picture (Mixkit item) | Words on it | Into the shot |
|---|---|---|---|---|
| 0.00 | fire | a tall flame stands among ash-covered logs (3468): sharp wood, cold ash against the fire, lit from the first frame | «المُتَنَبّي», in the dark between two logs, up on the first frame | none: the film starts lit |
| 1.78 | earth | bare earth at dusk; then a hand comes, presses the earth down and smooths it over, busy to the cut (2851); the voice is alone here | «يُدَفِّنُ» lands on the earth before the hand arrives, and the hand presses down over it; «بَعضُنا بَعضاً» below | cut |
| 3.76 | walk | bare feet and a white robe on wet sand, in slow motion made of the clip's real frames (1013); the music enters; a foot comes down | «وَتَمشي» under the foot that lands, which steps in front of it; then «أَواخِرُنا» | cut from the dark earth to the white cloth |
| 5.34 | foam | the frame stays behind on the sand (1013): the foot lifts off its print and leaves, and the white edge of the sea comes for the footprint | «عَلى هامِ» on the sand, which the foam reaches; «الأَوالي» in gold over the footprint, as the foot lifts off it | cut on the step |
| 6.34 | pour | molten metal poured (2861): the stream starts on the cut, the sparks burst on «المَشرَفِيَّةَ», a push-in on the accent at 7.01 | «نُعِدُّ» / «المَشرَفِيَّةَ» | warm flash |
| 7.40 | forge | embers rising among trunks as tall as spears (51634) | «وَالعَوالي» | zoom punch |
| 8.13 | glass | an hourglass (28894), ramped so the sand runs out on «بِلا قِتالِ» and the picture dies | «وَتَقتُلُنا المَنونُ» / «بِلا قِتالِ», which outlast the light | hard cut on the accent |
| 10.63 | tether | a horse's head in halter and chain (100663) | «وَنَرتَبِطُ» | cut from black |
| 11.42 | eye | a horse's eye (100645), graded into the cold of its neighbours | «السَوابِقَ» | cut |
| 12.08 | grey | a grey horse behind stable bars (100646) | «مُقرَباتٍ» | cut |
| 12.82 | canter | a dark horse cantering in dusk haze (1154, ×2) | «وَما يُنجينَ» / «مِن خَبَبِ», on its dark flank; the hooves stay clear | the film's one whip |
| 14.38 | night | a night sky turning to dawn in half a second (4357) | «اللَيالي» | dissolve |
| 14.95 | man | a man's black profile against lit smoke (948), real time: he lifts his face | «وَهانَ» / «فَما أُبالي», inside his shoulders | dissolve (the ridge becomes his shoulders) |
| 16.70 | sky | what he looks up at: a storm sky shutting, ×12 (118) | «بِالرَزايا» | cut on his look |
| 17.42 | man_b | the same man: his face to that sky, then he lowers it and turns away (948) | «لِأَنّي ما اِنتَفَعتُ» / «بِأَن أُبالي» | dissolve |
| 19.50 | train | a subway train rushing in (1622), ×2.8 | «رَماني» | cut |
| 20.17 | clock | a clock face whose light goes out (28885) | «الدَهرُ», in ink on the dial like its numerals | flash |
| 20.60 | volley | a storm of embers streaking like arrows (4426, turned 90°) | «بِالأَرزاءِ», embers passing in front | dissolve |
| 21.56 | coal | one glowing coal (3462) | «حَتّى» / «فُؤادي» | dissolve |
| 22.46 | thorns | black branches across a low sun (3969), a little out of focus | «في غِشاءٍ» above the sun, «مِن نِبالِ» below it, both behind the branches | dissolve (the coal becomes the sun) |
| 23.70 | man2 | the same man, closer and from the other side (948, mirrored), his head in the frame; real sparks in flight cross him from the first frame (4426) | «فَصِرتُ إِذا» / «أَصابَتني سِهامٌ», inside his shoulders, clear of the buttons the platforms draw at the right edge | cut |
| 25.52 | shards | splinters of rock in exploding water, from above (1956, turned 90°), with a lens jolt | «تَكَسَّرَتِ», which cracks into shards | smash cut |
| 26.22 | blade | a long blade of rock, a wave sweeping over it (51455, turned 90°) | «النِصالُ» | cut |
| 26.84 | rock | a 0.9 s fall onto a lone rock in a dark sea (44398, turned 90°, ×12 then real time); it stays | «عَلى النِصالِ», then the two credits | cut |

**Why these images.** The verses are about burial and the living walking on; weapons made ready and a death that needs none; swift horses that cannot outrun the nights; a man who has stopped flinching; time as the archer; and a heart so full of arrows that new ones only break on the old. Earth carries verse 1: a hand covers it over, bare feet walk on it, and what is left of the one who walked is a footprint the sea is about to take ("the last of us walk on the heads of the first"). Sand as sand appears once more, as the hourglass. Fire runs through the first half (the name, the pour, the embers) and comes back as the arrows. The "I" of the poem is one man: a black profile who lifts his face to the storm, turns away from it, and stands while the embers cross him. The end is water on rock. The modern images the commissioner once asked for are the subway train and the clock.

**Top-down shots are turned 90°.** A drone shot looking straight down has no "up". Turned, a 3840×2160 source fills the 2160×3840 frame with no crop: full 4K, and a wide view a 9:16 window could never hold (the lone rock in its sea; the long rock that reads as a blade).

## 2. The lettering (`remotion/src/BladesText.tsx`, `pipeline/comp_text.py`)
- **Scale and rhythm.** Amiri Bold, 130–230 px in a 1080-wide frame; the poet's name in Aref Ruqaa. A row never exceeds 84 % of the width and nothing sits below 84 % of the height. Each hemistich is split into blocks, one per shot; fast runs of shots keep their words in one place so the eye does not hunt.
- **One gold word per line**, the image-word, and it lands: it arrives a little large and settles. Other words rise into place. Every block grows 3.5 % over its life, with its shot's push-in.
- **In the picture's own dark space**: a man's shoulders, a horse's flank, the black of a glass, dark water. Never across the thing the line is about.
- **A block leaves with its shot.** On a hard cut it is gone on the cut frame; into a transition it fades over the transition's first half (`plan.py`, `leaves()`).
- **A rhyme word is not left to flash by**: where it would have under half a second, it comes on with the word before it («هامِ الأَوالي», «فَما أُبالي», «مِن نِبالِ»; at most 0.34 s before it is spoken).
- **In the shot, not on it.** Bright things pass in front of the letters (flames, falling sand, sparks, embers, sea foam, a pale hand); so does warm skin on cool ground (the walker's foot, keyed on its warmth); dark branches cross «في غِشاءٍ مِن نِبالِ»; «الدَهرُ» is set in ink on the clock dial; letters lit by a shot's own light keep 62 % when that light dies, so «بِلا قِتالِ» outlasts the hourglass. In the footprint shot the picture is held on the ground, so the words lie on the sand and do not ride the camera. Where a plate is bright under a line, a soft shade is pooled there, measured, with no caption box.
- **Clear of the platforms' furniture.** Nothing above 8 % or below 84 % of the height, and nothing right of 86 % of the width in the lower half: Reels and TikTok draw their buttons there, and an Arabic row starts at the right.
- **One word breaks.** «تَكَسَّرَتِ» is cut into slanted shards that part and tilt for a quarter of a second before the cut takes it.
- No depth estimation is used in the final cut (the tools for it, `depth_cache.py` and the depth options of `comp_text.py`, remain).

## 3. The engine (`pipeline/montage.py`)
- **Time remapping** with keys, so a shot ramps (the hourglass, the fall onto the rock). Near real time the nearest source frame is shown whole: mixing two neighbours doubles every moving edge. Only a real rush (2.5× and up) is integrated into motion blur, in linear light.
- **Transitions centred on the cut:** whip (a push with directional blur), zoom (one continuous punch-through), flash (a soft bloom, one rise and one fall), dissolve, and matte (the luma of a real clip wipes one shot into the next; not used in the final cut).
- **Shake** (a small handheld drift; stronger on the impact shots), **shock** (colour fringes that close and a breath of overexposure on the smash cut), **soften** (a shot held slightly out of focus).
- **Overlays** of real elements shot on black (the sparks), screen-blended: only their bright cores are kept, they are blurred along their own flight so they read as shafts, a wide soft copy of themselves lets them light what they cross, and a 30 fps layer is played frame for frame like any other clip (sampled at 24 it skipped every fourth frame).
- **Rotation** of top-down sources.
- **Even motion.** Some stock files carry a stutter of their own: conformed to 24 fps by dropping frames, they advance in uneven steps (1, 2, 1, 1, 2 … units of true time), or they repeat every sixth frame. Three repairs, by case:
  - *A tracking shot over textured ground* (the walker): `pipeline/true_cadence.py` keeps every real frame and synthesizes only the missing in-between ones from optical flow in both directions (falling back to broad motion where the flow cannot be trusted, such as fluttering cloth). The stretch then plays 1.4× longer: slow motion made of real frames. Ground travel per frame in the finished shot: 32–35 px at half size, where the supplier's file alternated 26 and 51 px at 4K.
  - *A slow simple picture* (the silhouetted man): `pipeline/even_cadence.py` gives the frames back their true spacing and rebuilds even ones by motion-compensated interpolation at the same speed.
  - *A repeated frame* (the pour): dropped (`"decimate": 6`) and the speed corrected.
  Measuring this needs care: frame differences and coarse optical flow lock onto the ripples of wet sand and report "even" when it is not. The tools track large patches of bare ground to a fraction of a pixel.
- **A frame held on the ground.** `pipeline/ground_lock.py` measures how the ground slides through a tracking shot and writes the window positions that keep one point of it still (`data/blades/footprint_lock.json`): the camera travels on, the picture stays with the footprint.
- One grade for all shots (`build_picture.py`), with fire allowed to reach warm white (red feeds green in the hottest shots); one grain pass over picture and letters together; levels clamped to 18–232 before encoding.

## 4. The independent review, and what it changed
A reviewer who had no part in the film looked at every frame of the first full cut and judged it against the commissioner's own words. Verdict: strong from the hourglass on, with a real ending; the first six seconds still at risk. What changed because of it:

| Finding | Change |
|---|---|
| The opening flames on pure black read as a compositing element | The name stands in a real log fire: first 42768, and after the third review the sharper 3468, lit from its first frame |
| Doubled edges on five shots (frame-blended retiming) | The engine shows whole source frames near real time; the man's shots run at real speed |
| Red glass tea-lights for "we bury one another" can read as church candles | Replaced (first by falling sand; after the second review by a hand smoothing earth over) |
| A night city square was "the first image from another world" | Dropped; the walker carries «وَتَمشي أَواخِرُنا» |
| Lettering "behaves like a caption": always centred, always the same entrance, sometimes across the subject | Image-words land, blocks grow with the push-in, «تَكَسَّرَتِ» breaks; words moved into each picture's dark space (the horse's flank, the man's shoulders) |
| "Fire has no heat": nothing above 85 % of white | Fire shots regraded so cores reach warm white; the red sparks softened and turned to embers |
| The horses' eye shot in full colour between two monochrome ones | Graded into the cold of its neighbours |
| A man in a modern jacket in flat haze, "a different I" | Replaced by the silhouette man: he looks at the sky and turns away |
| Rhyme words on screen for 0.4 s | Brought on with the word before them |
| Low contrast under «النِصالُ» and the credits; marks colliding between rows | Foam darkened, the last rock held smaller so the credits sit on dark water, rows spread |
| Four identical whips; a rainbow leak; a saturated blue | One whip kept; the leak reduced to its warm light, and in the end removed; the blue pulled back |

Kept against the review's advice: the subway train and the clock for «رَماني الدَهرُ» (the commissioner asked for exactly these), with the dial now lit for the whole word.

**A second review** of the revised cut (a new reviewer, same brief) no longer expected the commissioner's earlier objections, and listed what still stood out:

| Finding | Change |
|---|---|
| Motion stutters on the man and the walker; a ghost on the pour | Traced to the stock files themselves; repaired as described in section 3 |
| Falling sand for the burial line is the hourglass twice, and reads as salt | A hand smoothing earth over, from a clip first passed by for its opening seconds (a tool breaking soil) |
| The man's back twice in a row | The third moment is closer and mirrored, and the embers are on him from the cut |
| The opening fire a little violet and soft | See the third review: replaced |
| «عَلى» on screen before its shot; «النِصالُ» weak on white foam; marks touching between two rows | No word may show before a hard cut into its shot (`arrives()`); the foam held grey under the gold word; rows spread |
| The pour lemon-green; the ember volley showing its pixels; the horse's eye the brightest frame of its run | Regraded to orange; held softer; darkened |

**A third review**, of the first six seconds and the embers shot only, by a reviewer who saw nothing else. Its judgement of that opening was "dim stock clips with captions laid over them", and it would not have stopped him scrolling. Every finding was checked by measurement before it was acted on; all held.

| Finding | Change |
|---|---|
| The walking shots still shudder (long, short, short, long, short steps) | True: the first repair had only halved the unevenness, and the measure used to verify it was fooled by the sand's ripples. Rebuilt at its true cadence (section 3) and verified by tracking bare sand |
| The second half of verse 1 ("on the heads of the first") had the weakest picture: the same feet again, in murky surf, on a jump cut | A different picture from the same take: the frame is held on the sand, the foot lifts off its print, and the sea comes for the footprint |
| The opening fire is the softest shot of the film, dark on its first frame, the name not up until 0.45 s | A sharper fire (ash-covered logs in focus), lit and titled from frame 0. Its framing was chosen by the flicker screen: 0.075 against a limit of 0.11, where a framing 4 % further in fails at 0.14 |
| For four seconds the lettering is the only bright and sharp thing on screen; skin, cloth, sand and foam are one brown | The beach is graded neutral and a stop brighter: white cloth, dark skin, grey sand, white foam |
| A twig runs through the film's first word; marks of two rows touch | The word sits clear of the twig, the rows are spread |
| Words lie across the walker's foot and ride the screen while the ground streams past | Words sit beside or under the foot, which steps in front of them; in the footprint shot the ground itself is held still |
| "We bury one another" reads as gardening until the word arrives; the hand is gone before the cut | The word now lands on bare earth first and the hand comes over it, still leaving at the cut |
| In the embers shot both rows start under the platforms' button column, the frame cuts his head, he is a flat black shape for a third of a second, and no light from the embers touches him | Reframed with his head whole; rows moved inside his shoulders and left of the column (now a check); embers from the first frame, with their own glow on him |

**A fourth review**, again of the opening and the sparks shot only, by a reviewer who saw none of the earlier ones. Its judgement: nothing looks generated, the lettering is mostly designed into the shots, and from the walking feet on it is "the image-for-sentence he asked for"; two places could still draw a "not it".

| Finding | Change |
|---|---|
| The burial picture is still the weakest: the hand is out of focus, and for half a second only a blurred forearm is left over an almost frozen frame | Reframed so the hand stays in the picture and is at work for the whole two seconds; lifted half a stop. It now presses down over the first word. The hand stays out of focus: that is how the clip was shot, and the two free clips of earth thrown into a grave are restricted-licence (section 7) |
| The spark layer reads as an overlay: it fades up over five frames and keeps brightening, slides as one sheet, skips every fourth frame, and looks like a man burning | Cut in at working level on a steady stretch of the clip; played frame for frame; only the bright cores kept, blurred along their flight; less of their glow on him |
| The opening flame is small and at the edge for the first 0.75 s; the logs are too violet | A stretch where the flame stands tall on the first frame (flicker 0.076 against 0.11); the ash pulled back toward grey |
| The walking shot is muddy next to the footprint shot (frame average 57 against 71) | Lifted about half a stop with a firmer white, and framed a little closer |
| Three rows reach below the 84 % line (the ink was measured at 85–86 %; the check had estimated it) | The check now measures the ink of the rendered lettering frame by frame; those rows were raised, and a fourth it found (in the silhouette shot) with them |
| Marks of stacked rows interlock in the earth and sparks shots | Upper rows raised |

## 5. Sound (`pipeline/mix_blades.py`, `data/blades/sfx_cues.json`)
- **The original mix is the soundtrack**: static gain 0.0 dB, no EQ, ducking, separation or re-timing. Outside 145 ms of limiter action at 11 voice peaks and the final fade, the master minus the effects is the original, sample for sample.
- **27 cues from 26 Mixkit recordings**, each anchored to a shot id, so their times are resolved from the plan on every run. Among them: a fire whoosh under the name, one small wave as the sea's edge comes in for the footprint, the roar of the pour, a low thump on the cut to the hourglass, muffled hooves, distant thunder under the sky, a gust as the man turns away, the rush of the train, two clock ticks, arrow fly-bys in the pauses, one heartbeat on «فُؤادي», a breaking wave on the smash cut, and open sea under the ending.
- **The voice wins.** Wherever a word is spoken, the effects sit at least 14 dB under the original mix (K-weighted, 400 ms windows). Worst case: 15.04 dB at «بِالأَرزاءِ». The automatic safety gain never had to act.
- **Nothing voice-like**: no human or animal voice, no metal ring, scrape or grind. A held-tone detector with planted controls finds none.
- **Master**: −14.17 LUFS integrated, true peak −1.08 dBTP, 31.000 s, the last 0.6 s faded to silence.
- Left out on purpose: anything under the spoken intro, anything under the hand on the earth (the voice is alone until the music enters), a footfall on the walk, a chain clink (metal), the sand hiss under the hourglass words.

## 6. Checks (`pipeline/qc_blades.py`)
What is checked on the finished file:
- **Text**: all 12 hemistichs on screen equal the poem record and the aligned words, character for character; no other lettering than the poet's name and the two credits.
- **Sync**: every word appears at its aligned onset (0.06 s lead), inside the shot it is spoken over, and stays until it has been spoken.
- **Layout**: every row measured with HarfBuzz shaping: none wider than 86 % of the frame, none outside 8–84 % of the height, none under the button column at the right edge of the lower half. Then the same limits are measured again on the ink of the rendered lettering, frame by frame, because an estimate of how far a tail or a kasra reaches was wrong by 2 % of the height.
- **Seen**: in the finished frames each word really differs from the picture under it.
- **File**: 2160×3840, 24 fps, H.264 High, BT.709, levels inside EBU R103; no stray black.
- **Sound**: loudness, true peak, and that the film's sound is the original mix in sync.
- **Flashes**: the photosensitivity screen (`pipeline/flash_check.py`).
- **Licences**: every source recorded as verified free.

## 7. What could not be had
- **Earth thrown into a grave.** Mixkit has the picture ("Man throws dirt into a grave", 32827; "Person filling a hole in the ground", 33727), but both pages state its restricted licence. The burial line therefore stays with the hand on the earth, which is shot with the hand out of focus.
- **Real burning calligraphy.** The only free burning-paper footage reachable is a printed Latin-script book in flames (Mixkit 52295, 52298–52300); it does not suit Arabic verse. Blank-paper burns exist on Mixkit only under its restricted licence.
- **Swords, spears, archery, a smith, Arabian horses.** Mixkit's free tier has none. Wikimedia Commons has candidates, but its media server refused every download from this machine (HTTP 429), so none could even be viewed.
- **A person in a real storm.** Free only as a figure in smoke (the man used here).
- **4K sources for two shots.** The cantering horse comes from a 1920×1080 clip of which a 608 px window survives; the embers of the volley are a 1080 px clip, softened on purpose. Everything else is from 4K files.

## 8. If the burning strips are filmed
`pipeline/make_burn_strips.cjs` prints the twelve hemistichs as strips with a shooting guide. A filmed strip replaces a shot by its file path in `plan.py`; setting `"hide": true` for that hemistich in the plan's `lines` removes the overlaid words there (the line is then in the picture itself), and QC lists it as "in picture".

## Licences
- Footage: 21 Mixkit items, each verified on its own page as `data-license="videoFree"` on 2026-11-18 (`data/blades/footage_licences.json`, written from the plan by `pipeline/licence_record.py`, which stops if a source in the cut is not recorded as free).
- Sound effects: 26 Mixkit recordings under the Mixkit Sound Effects Free License (`data/blades/sfx_licences.json`).
- Fonts: Amiri and Aref Ruqaa (SIL Open Font License).
- The voice and its music are the commissioner's own reel.

## Rebuild
```
V=/home/user/film/venv/bin/python; R=/home/user/Builder-Baseerah/sutoor-film
# stretches of two stock clips with their motion repaired (the plan plays these files); SRC holds the downloads
$V $R/pipeline/even_cadence.py SRC/948.mp4 10.2 2.5 SRC/948-11.mp4
$V $R/pipeline/even_cadence.py SRC/948.mp4 14.4 2.7 SRC/948-12.mp4
$V $R/pipeline/even_cadence.py SRC/948.mp4 16.8 2.3 SRC/948-13.mp4 --pattern 1,2
$V $R/pipeline/true_cadence.py SRC/1013.mp4 0.4 4.4 SRC/1013-22.mp4      # the walk, at its true cadence
$V $R/pipeline/true_cadence.py SRC/1013.mp4 9.3 3.4 SRC/1013-21.mp4      # the footprint stretch
$V $R/pipeline/ground_lock.py SRC/1013-21.mp4 $R/data/blades/footprint_lock.json --point 730,1700 --at 68 --frames 50,86 --band 200 --strip 180,830
$V $R/data/blades/plan.py                                   # the edit -> data/blades/plan.json
$V $R/pipeline/render_blades.py $R/data/blades/plan.json WORK WORK/picture_4k.mp4 --share WORK/picture_1080.mp4
$V $R/pipeline/mix_blades.py --out SOUND                    # effects under the original mix -> SOUND/mix.wav
ffmpeg -i WORK/picture_4k.mp4 -i SOUND/mix.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 320k -movflags +faststart OUT.mp4
$V $R/pipeline/qc_blades.py OUT.mp4 $R/data/blades/plan.json WORK qc.json --licences LICENCES.json
```
A section can be rendered alone (`--from T --to T --scale 0.5`), which is how every change was checked before the 4K render.
