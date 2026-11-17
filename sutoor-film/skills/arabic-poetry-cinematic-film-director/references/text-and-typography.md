# Text truth and Arabic typography

## Text truth table (produce before any subtitle)

| Verse | Supplied by user | Recited (order) | Canonical source | Displayed text source |
|---|---|---|---|---|
| e.g. وَهانَ فَما أُبالي بِالرَزايا | no | yes (4th) | aldiwan poem9758, verse 7 | canonical, verbatim |
| e.g. نَصيبُكَ في حَياتِكَ مِن حَبيبٍ | yes | no | — | not shown; reported |

- Supplied text is copied character for character (diacritics included). Never "correct" it.
- Unsupplied but recited verses: copy from a canonical diwan text. Offline-friendly source:
  Hugging Face dataset `arbml/ashaar` (aldiwan.net, full tashkeel), search verses with diacritics stripped.
- Reciters reorder verses; the film follows the recording.
- Burned-in captions in the source video are a strong second witness for what is recited.

## Display rules

- Unit = hemistich. Reveal the sadr at its aligned start (−0.12 s), the ajuz at its own start; both hold
  until ~0.3 s before the next verse starts, then fade.
- Widescreen (2.39:1 scope matte in 16:9): classical diwan layout on ONE line in the lower matte —
  sadr on the right, ajuz on the left, ~110 px gutter; text never covers the picture.
- Vertical: picture window on top, sadr above ajuz below it.
- Size (1080 px tall frame): 48-54 px verse, 110-120 px title. Line-height ≥ 1.7 (harakat need room).
- Colour: warm ivory (#EFE6D2) for verses, muted champagne (#D8C49C) for title/credits.
- Contrast: soft shadow `0 2px 10px rgba(0,0,0,.55)`; no outline, no glow, no boxes.
- Motion: 0.45 s fade with 3 px blur-to-sharp and 6 px rise. No karaoke, no per-letter animation.
- Never `letter-spacing` Arabic; keep `direction: rtl`; enable `kern`, `liga`, `calt`.

## Font evaluation (Chromium/HarfBuzz render, harakat-heavy test line «تَكَسَّرَتِ النِصالُ عَلى النِصالِ»)

| Font (SIL OFL) | Verdict |
|---|---|
| Amiri | Verse font. Classical Naskh, correct shadda+fatha stacking, elegant at small sizes. |
| Aref Ruqaa | Title font. Calligraphic, restrained; too heavy for running verse. |
| Scheherazade New | Good fallback for verses; slightly wider. |
| Noto Naskh Arabic | Clean but generic; acceptable fallback. |
| Markazi Text | Reject for tashkeel: shadda+haraka visibly detached. |
| Reem Kufi / El Messiri | Reject for classical verse (modern geometric display). |

Get fonts from `https://raw.githubusercontent.com/google/fonts/main/ofl/<family>/` with their OFL.txt.

## Verification

1. Render a still at the midpoint of every hemistich; read each against the truth table.
2. Programmatic: compare the displayed strings with the source strings (exact Unicode equality).
3. Check no mark is clipped at line box edges, no fallback font appears (tofu, different shapes).
