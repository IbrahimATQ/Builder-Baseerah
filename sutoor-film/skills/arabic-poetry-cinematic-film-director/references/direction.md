# Direction: from verse to image, grade, edit, QC

## Reading the poem

For each verse record: literal meaning, figurative move (irony, metaphor, apostrophe), emotional
intensity 1-10, and the turn it makes in the arc. Classical qasidas often run
mortality → vanity of effort → time → detachment → suffering → endurance; check the recited order.

## Choosing images (one metaphor per hemistich)

| Verse idea | Literal (avoid) | Timeless metaphor | Contemporary metaphor |
|---|---|---|---|
| Generations bury one another | corpses, funerals | weathered tombs in mist | a real clock's hands moving in close-up; a station crowd flowing under a big clock |
| Preparing weapons, dying without battle | battle scenes, blood | steel being forged → a candle's flame breathing out | (forge footage is already documentary; keep it) |
| Swift horses cannot outrun the nights | a horse race | tethered horse's eye/mane → night sky wheeling | horse's eye → a passenger train rushing past |
| Indifference to calamity | sad face | a curtain breathing in an empty room; sand leaving open fingers | an hourglass; an empty platform after the train |
| Struck by time's arrows | wounded man | arrows packed into an old target; a storm front | lightning over a city skyline |
| Blades breaking on blades | literal swords clashing | sea breaking on rock that stays; a lone figure unmoved at dusk | an old stone fortress or wall still standing |

**Authenticity beats polish.** Viewers reject footage that "looks AI": glossy drone flyovers of ruins,
staged beauty shots (bare feet on a perfect beach), over-smooth slow motion, plastic colour. Prefer real
documentary footage with natural motion, real people and imperfection (handheld steadiness is fine).
Before locking, look at each pick at full speed and ask: would someone believe a person filmed this?

**Offer a contemporary layer.** Mixing modern imagery (clocks, stations, trains, city crowds) with
timeless imagery makes classical verse speak to the present. Ask the requester, or offer both; never
silently rule modern footage out.

Rules: 10-14 shots for ~30-40 s; no logos, readable brand text or AI-plastic imagery (modern objects are a
director's choice, see above); slow, motivated
camera moves (push-ins 3-8 %, lateral drifts); dissolves 0.4-0.8 s on verse turns, hard cuts never
inside a hemistich; end on a held wide composition with a slow fade, never an abrupt stop.

## Palette by act (grade per shot with ffmpeg, not one LUT)

| Act | Look | ffmpeg starting point |
|---|---|---|
| Mortality | charcoal, cold stone, low saturation | `eq=saturation=0.6:contrast=1.06,colorbalance=bs=0.04:bm=0.02` |
| Preparation | bronze/aged gold on steel | `colorbalance=rh=0.06:gh=0.02:bh=-0.05:rs=-0.02,eq=saturation=0.8` |
| Time | blue-grey night | `colorbalance=bs=0.07:bm=0.04:rh=-0.02,eq=saturation=0.7:brightness=-0.02` |
| Detachment | muted, soft amber window light | `eq=saturation=0.55,colorbalance=rh=0.04:bh=-0.03` |
| Suffering | rust/amber, higher contrast | `eq=contrast=1.12:saturation=0.75,colorbalance=rh=0.07:bs=-0.03` |
| Endurance | golden-hour bronze, deep shadows | `eq=contrast=1.08:saturation=0.85,colorbalance=rh=0.08:gh=0.03:bh=-0.06` |

Finish: gentle vignette, fine luma grain (`noise=c0s=7:c0f=t`), keep skin tones natural.

## Licence gate (before visual review)

Read each clip's licence from its own page, not the site's name or a listing:
- Mixkit: item page `data-license` must be `videoFree`. `videoRestricted` = personal use only,
  explicitly not "in a film", ads, or monetised social/YouTube. Listing-page JSON-LD is unreliable.
- Wikimedia Commons: `extmetadata.LicenseShortName` via the API; accept PD, CC0, CC BY (credit +
  "modified" note). Reject CC BY-SA (makes the whole film BY-SA), NC, ND.
- Record source URL + licence per shot in the shot plan; the build refuses a shot without one.

## Aspect ratio decision

Compute the upscale factor: output height ÷ usable source crop height. Free stock (Mixkit) is ≤1080p,
often 720p; a 9:16 crop from 16:9 1080p needs 1.78×, from 720p 2.67×. Prefer a 16:9 master with a
2.39:1 matte (native resolution, verse line in the lower matte) and derive a vertical edition from the
same edit with per-shot `focusX`.

## QC checklist (report numbers, not adjectives)

Visual: every shot relevant to its verse; no repeated clip; transitions only at verse/hemistich
turns; frame stills per hemistich reviewed, in BOTH editions (a 4:5 or 9:16 window can crop away the
subject: a clock's hub, a tower). Have someone other than the editor rate every shot "does a person
believe this was filmed?" before delivery.
Levels: picture black = matte black (Y 16), shadows rolled off, not clipped. Measure the share of
picture pixels at Y <= 18: above ~25 % the subject turns into a flat cut-out and reads as composited.
Motion: never slow 24/25/30p footage with setpts (it repeats frames, visible judder); use real speed
or a native high-frame-rate source. Prefer 30p sources in a 30p timeline.
Dissolves: if the outgoing shot has a bright element (flame, spray, lightning afterglow), it ghosts
over the next image; hard-cut instead. Keep the title off the screen before the next shot dissolves in.
Photosensitivity: lightning, strobes, muzzle flashes. Run `scripts/flash_check.py FILM.mp4` on every
edition (general-flash rule: no more than 3 flashes in any 1 s over > ~11 % of the screen; the
vertical edition fails first because its picture fills more of the screen). Fix with
`scripts/flash_limit.py IN OUT --max-per-second 2 --keep-first` on the shot, not by darkening it.
Audio: integrated LUFS, true peak, LRA; voice-minus-music per hemistich; music-only-region level of
the isolated voice; max short-term jump; sync (subtitle start − aligned word start ≤ 0.15 s).
Arabic: exact string equality with the truth table; harakat unclipped; RTL order; sadr right of ajuz.
Export: H.264 High, yuv420p, CRF ≤ 16, AAC 320 kb/s 48 kHz, `+faststart`, no watermark.

## Reel form (9:16, full screen)
For phone feeds, one intimate practical world beats a stock montage: few shots, long holds, real
textures. Reveal the verse word by word at each aligned onset (lead ~0.06 s), words holding their
place in the line from the start so nothing reflows. Keep the verse in the lower-middle, over a soft
dark band, clear of the bottom ~20 % that app controls cover. Start the voice within ~2.5 s. End on
one word alone on black (the poem's own last word, from the truth table) with a light that suits the
poem (e.g. iron glowing then cooling for a poem about blades).
