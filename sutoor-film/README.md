---
title: Arabic Poetry Film Production MCP
emoji: 🎞️
colorFrom: yellow
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: other
---

# Sutoor film: «النِصالُ عَلى النِصالِ»

A free, open pipeline that turns an Arabic poetry recitation into a cinematic film, plus a remote
MCP connector (**ARABIC POETRY FILM PRODUCTION MCP**) that lets Claude run the whole pipeline from
an iPhone.

| Folder | What it is |
|---|---|
| `pipeline/` | separation QC, forced alignment, original score (CC0 samples), mix and master, shot builder |
| `remotion/` | the film composition (2.39:1 scope master, 9:16 vertical edition) |
| `mcp/` | the unified MCP server (14 tools, streamable HTTP), end-to-end and CI tests |
| `skills/` | the `arabic-poetry-cinematic-film-director` Claude skill (folder and upload zip) |
| `docs/` | director's treatment, infrastructure report |
| `data/` | the poem text truth table and aligned timings |

The server endpoint is `https://<space>.hf.space/mcp` (or the path set in the `MCP_PATH` Space
variable). Media you import stays on the server; nothing is sent to third-party AI services.

Licences: the code here was written for this project and has no licence chosen yet (add one
before inviting reuse); fonts are SIL OFL (`remotion/public/fonts/*OFL.txt`);
Remotion (Remotion License: free for individuals and teams of 3 or fewer); model weights (see
`docs/infrastructure-report.md`).
