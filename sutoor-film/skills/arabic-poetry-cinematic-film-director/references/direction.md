# Direction: from verse to image, grade, edit, QC

## Reading the poem

For each verse record: literal meaning, figurative move (irony, metaphor, apostrophe), emotional
intensity 1-10, and the turn it makes in the arc. Classical qasidas often run
mortality → vanity of effort → time → detachment → suffering → endurance; check the recited order.

## Choosing images (one metaphor per hemistich)

| Verse idea | Literal (avoid) | Metaphor (prefer) |
|---|---|---|
| Generations bury one another | corpses, funerals | weathered tombs in mist; feet on ancient paving |
| Preparing weapons, dying without battle | battle scenes, blood | steel being forged → a candle's flame breathing out |
| Swift horses cannot outrun the nights | a clock | tethered horse's eye/mane → night sky wheeling (time-lapse) |
| Indifference to calamity | sad face | a curtain breathing in an empty room; sand leaving open fingers |
| Struck by time's arrows | wounded man | arrows packed into an old target; a storm front |
| Blades breaking on blades | literal swords clashing | sea breaking on rock that stays; a lone figure unmoved at dusk |

Rules: 10-14 shots for ~30-40 s; no modern objects, logos, text or AI-plastic imagery; slow, motivated
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

## Aspect ratio decision

Compute the upscale factor: output height ÷ usable source crop height. Free stock (Mixkit) is ≤1080p,
often 720p; a 9:16 crop from 16:9 1080p needs 1.78×, from 720p 2.67×. Prefer a 16:9 master with a
2.39:1 matte (native resolution, verse line in the lower matte) and derive a vertical edition from the
same edit with per-shot `focusX`.

## QC checklist (report numbers, not adjectives)

Visual: every shot relevant to its verse; no anachronism; no repeated clip; transitions only at
verse/hemistich turns; frame stills per hemistich reviewed.
Audio: integrated LUFS, true peak, LRA; voice-minus-music per hemistich; music-only-region level of
the isolated voice; max short-term jump; sync (subtitle start − aligned word start ≤ 0.15 s).
Arabic: exact string equality with the truth table; harakat unclipped; RTL order; sadr right of ajuz.
Export: H.264 High, yuv420p, CRF ≤ 16, AAC 320 kb/s 48 kHz, `+faststart`, no watermark.
