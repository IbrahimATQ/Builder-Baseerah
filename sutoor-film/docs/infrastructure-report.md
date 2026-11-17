# Infrastructure Report: free, iPhone-only production of a cinematic Arabic poetry film

*Status as of 2026-11-17. Every claim marked ✅ was verified by running it in this project; ⚠️ means
documented but not runnable here; ❌ means evaluated and rejected.*

---

## 1. Skills selected

| Skill | Source | Role | Status |
|---|---|---|---|
| `remotion-best-practices` (router) with `remotion-create`, `remotion-markup`, `remotion-render`, `remotion-multimedia`, `remotion-captions` | Official Remotion plugin, already installed on your claude.ai account (Anthropic plugin directory) | Composition, layout, fonts, rendering | ✅ Loaded and followed in this session |
| **`arabic-poetry-cinematic-film-director`** (custom) | Written for this project | Text truth, verse timing, breath-safe voice isolation, Arabic typography, maqam scoring, licence gate, QC | ✅ Built and tested (RED → GREEN → REFACTOR, see §10) |
| `superpowers:writing-skills`, `workflow-authoring` | Already available | Test-driven skill authoring; parallel research and scouting | ✅ Used |
| `ffmpeg-llm` plugin skills | Already available | FFmpeg command help | Not needed (duplicative) |

Evaluated and not added:
- **Re-uploading the Remotion skills as zips.** They are already installed, and duplicates would collide.
- **`remotion-captions` for transcription.** It points to whisper.cpp `medium.en`, which is English-only and so a trap for Arabic. Use the custom skill's alignment instead.
- **`remotion-upgrade` on captions.** Upstream moved to WebGPU Whisper, which needs a GPU.

## 2. Skills installed or prepared for upload

| Item | Where | Verified |
|---|---|---|
| Custom skill, Claude Code | `.claude/skills/arabic-poetry-cinematic-film-director` → `sutoor-film/skills/…` | ✅ Claude Code lists it in this session's skill registry |
| Custom skill, claude.ai upload | `sutoor-film/skills/arabic-poetry-cinematic-film-director.zip` | ⚠️ Needs your upload (Settings → Capabilities → Skills). Frontmatter is valid (`name`, 367-character description) |
| Remotion skills | Already on your account | ✅ No action needed |

## 3. Connectors selected

**ARABIC POETRY FILM PRODUCTION MCP**, a single unified server built for this project
(`sutoor-film/mcp/`). It has 16 tools:
`import_media`, `list_assets`, `inspect_media`, `extract_audio`, `separate_voice`, `transcribe_arabic`,
`sync_subtitles`, `search_footage`, `download_licensed_media`, `edit_video`, `create_composition`,
`mix_audio`, `render_film`, `inspect_output`, `start_job`, `job_status`.

It is served three ways from one code base (`mcp/tools.py`):

| Transport | Use | Verified |
|---|---|---|
| stdio via `.mcp.json` | Claude Code cloud sessions (iPhone app → Code) | ✅ 16 tools listed; async job completed |
| Streamable HTTP (`mcp/server.py`) in Docker | Any Docker host; HF Docker Space (paid) | ✅ GitHub Actions built the image and passed 18/18 smoke checks, including an Arabic Remotion render |
| Gradio MCP (`space/app.py`) | **Free** HF Gradio Space on ZeroGPU → claude.ai custom connector | ✅ Locally: 16 tools, error messages, async job. ⚠️ Not yet deployed to HF |

Security model, verified by tests:
- No shell or raw-filter tools.
- Workspace path confinement, with symlinks refused.
- SSRF guard on imports (private and loopback IPs refused).
- ffmpeg reads inputs with `-protocol_whitelist file,pipe`, so crafted media cannot trigger network fetches.
- Footage downloads only from an allowlist of hosts.
- **The licence is read at the source before any download.** A Mixkit `videoRestricted` clip is refused, Commons SA, NC and ND licences are refused, and the check fails closed.
- Media is never sent to third-party AI services.

Existing third-party MCP servers were audited by reading their published source. None are adopted:
- `whisper-mcp` 0.1.1 has shell injection.
- `whisper-transcribe-mcp` silently uploads audio to OpenAI when a key is present.
- `remotion-mcp` exposes open-CORS HTTP with no auth.
- The official `@remotion/mcp` was shut down on 2026-10-26.
- The hosted ffmpeg, caption and stem services upload media and are mostly paid.
- Several repositories have no licence at all.

Only `@modelcontextprotocol/server-filesystem` passed, and it is redundant inside Claude Code.

## 4. Connectors that still require your authorization

1. **Remote connector for ordinary Claude chats (optional).**
   1. Create a free Hugging Face account. To use ZeroGPU it must be in good standing.
   2. Create a Gradio Space and choose ZeroGPU hardware.
   3. Create a *write* token.
   4. In GitHub, add secret `HF_TOKEN` and variable `HF_SPACE` (`user/space`).
   5. Run the **Deploy poetry film MCP to Hugging Face Space** workflow with flavour `gradio`.
   6. In claude.ai → Settings → Connectors → *Add custom connector*, paste `https://<user>-<space>.hf.space/gradio_api/mcp/`.

   The Free plan allows one custom connector.
2. **Pixabay (optional).** Pixabay's key is a URL query parameter, so the secure credential form here cannot hold it. If you want Pixabay, add it as a Space secret `PIXABAY_API_KEY`.
3. **Claude Code project MCP.** The first session that uses `.mcp.json` asks you to approve the server.
4. **Environment setup script (optional).** Lets a fresh cloud session reinstall the toolchain automatically (see §7).

## 5. Software and models selected

| Component | Version | Licence | Use |
|---|---|---|---|
| FFmpeg / FFprobe | 6.1.1 (Ubuntu, GPL build) | GPL/LGPL; output files are unaffected | Extraction, grading, loudness, final encode |
| Remotion | 4.0.544 | Remotion License: free for individuals and teams of 3 or fewer | Composition, Arabic typography, render |
| python-audio-separator | 0.48.0 | MIT; weights are SHA-checked | Voice/music separation runner |
| **Kim Mel-Band RoFormer** (`vocals_mel_band_roformer.ckpt`) | n/a | **MIT weights** | **The isolated voice used in the film** |
| BS-RoFormer viperx 1296, htdemucs_ft | n/a | Weight licences unclear | Comparison only; not in the film |
| faster-whisper + Whisper large-v3 | 1.2.1 | MIT code; MIT/Apache weights | Independent check of what was recited |
| torchaudio MMS_FA + uroman | 2.11.1 | Code BSD; **weights CC-BY-NC 4.0** | Word-level forced alignment (see §9) |
| librosa, soundfile, scipy, numpy, pyloudnorm | current | ISC/BSD/MIT | Analysis, sampler, loudness |
| VSCO-2 Community Edition | git HEAD | **CC0** | Samples for the original score |
| Amiri, Aref Ruqaa | google/fonts | SIL OFL 1.1 | Verse and title typography |
| MCP Python SDK; Gradio | 2.3.0; 6.32.0 | MIT; Apache-2.0 | Connector |

Rejected:
- **Desktop-only:** DaVinci Resolve, Audacity, Subtitle Edit, Aegisub, Kdenlive.
- **Impractical on CPU:** Blender.
- **Non-commercial or unsuitable weights:** MusicGen, YuE, Stable Audio (registration needed).
- **Obsolete or unmaintained:** Spleeter, Open-Unmix.
- **Breaks the Python stack:** WhisperX (torch downgrade).
- **Unverified binary download:** auto-editor.

## 6. Hosting environment

| Need | Free option | Limits (verified or documented) |
|---|---|---|
| **Primary compute** | **Claude Code on the web** (this session), driven from the iPhone app | 4 vCPU, 15 GB RAM, no GPU, ~30 GB disk; ephemeral container; commands capped at 10 min foreground; network allowlist (this environment: *Builder-Baseerah film production*) |
| Remote connector compute | HF **Gradio Space on ZeroGPU** | Free accounts: up to 2 such Spaces; GPU quota of a few minutes per day; disk is not persistent |
| Batch fallback | GitHub Actions | Public repos: free, but logs and artifacts are public, so **never with your media**. Private: about 2,000 min/month included; 6 h per job |
| Persistent storage | GitHub (code); your own Drive or iCloud (media) | Public repo is unsuitable for media |
| GPU | ZeroGPU (minutes per day); Kaggle (hours per week, notebook only) | **No free unlimited GPU exists.** This pipeline does not need one |

Not free or not suitable:
- HF **Docker** Spaces: creation requires PRO, verified in HF docs.
- Remotion Lambda: needs an AWS account with a card.
- Fly.io, Railway, Oracle and Cloud Run: card-gated.
- Render and Koyeb free tiers: too small.

claude.ai connectors time out after about 240 s per tool call. That is why all long steps run through `start_job` / `job_status`.

## 7. Exact installation instructions (iPhone only)

**A. Make a film in a Claude Code cloud session (recommended).**
1. In the Claude app, open **Code**, choose this repository, and select the environment *Builder-Baseerah film production* (already created; it allows the model and footage hosts).
2. Ask Claude: *"Use the arabic-poetry-cinematic-film-director skill to make a film from <link to my video>."*
3. Approve the `arabic-poetry-film` MCP server when Claude Code asks.
4. If the toolchain is missing in a fresh container, Claude installs it:
   - `python3 -m venv /opt/poetry-film/venv && /opt/poetry-film/venv/bin/pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu && /opt/poetry-film/venv/bin/pip install -r sutoor-film/mcp/requirements.txt`
   - `cd sutoor-film/remotion && npm ci`
5. Get the video into the session by a share link (Google Drive "anyone with the link") or by uploading it in the chat.

**B. Add the remote connector to ordinary Claude chats (optional).** See §4.1.

**C. Install the custom skill on claude.ai (optional).** Download `sutoor-film/skills/arabic-poetry-cinematic-film-director.zip` from GitHub in Safari, then claude.ai → Settings → Capabilities → Skills → Upload.

## 8. Compatibility verification

| Check | Result |
|---|---|
| Arabic shaping with full harakat in Chromium (Remotion) | ✅ Every hemistich rendered as stills and reviewed |
| Amiri shadda+haraka stacking vs Markazi | ✅ Amiri correct; Markazi detaches the shadda (rejected) |
| Docker image (python 3.12 + Node 22 + Chromium) | ✅ Built on GitHub Actions; 18/18 smoke checks |
| MCP over stdio, HTTP and Gradio | ✅ |
| iPhone use | ✅ Claude Code on the web (this session) is the documented iPhone route. ⚠️ The HF Space connector is not deployed yet |
| Model downloads behind the proxy | ✅ After allowing `download-r2.pytorch.org`, `us.aws.cdn.hf.co`, `release-assets.githubusercontent.com` and setting `HF_HUB_DISABLE_XET=1` |

## 9. Known limitations (honest list)

- **Footage resolution.** Free Mixkit clips are 1080p at best, some 720p, and none were 4K-downloadable. The master is therefore 16:9 with a 2.39:1 scope matte at native resolution. The vertical edition crops a 4:5 window, a 1.25× upscale.
- **Licences.** 7 of the first 13 Mixkit picks turned out to be under Mixkit's *Restricted* licence (personal use only; "never… in a film"). All 7 were replaced with verified `videoFree` clips before the final render. One shot (the forge) is Wikimedia CC BY 3.0 and credited in the film.
- **No period archery or sword footage under a free licence.** Act V uses lightning and embers; Act VI uses the sea against rock and the Alhambra. These are metaphors, not literal images.
- **The two supplied love verses are not in the recording,** so they are not in the film. The recited verse «وَهانَ…» is included with its canonical tashkeel.
- **MMS_FA weights are CC-BY-NC.** The timings are computed data, but if you monetise the film, re-run alignment with an Apache-2.0 Arabic CTC model (e.g. jonatasgrosman XLSR Arabic) to be safe.
- **The recitation belongs to its reciter and publisher** (Abdullah Al-Anzi; the source video was branded *Sutoor / مايكس*). Make sure you have their permission to publish the derivative.
- **I cannot listen.** Audio quality is verified by measurement: loudness, spectra, ASR on stems, pitch and chroma checks of the score. Please listen once on headphones.
- **The score is an original, modest-scale sampler arrangement,** not a recorded orchestra. Pizzicato chroma "smear" is inherent to the samples.
- **Wikimedia rate-limits this container's shared IP** (HTTP 429). Searches may need to be retried later.
- **The HF Gradio Space is not deployed.** Its Node 22 bootstrap (checksum-verified download from nodejs.org) is untested on Hugging Face.
- **The cloud container restarted several times during production.** Work survived because it was committed, and media lived on disk.

## 10. Actual end-to-end testing results

See `docs/qc-report.md` for the final film QC. Pipeline and infrastructure tests:

| Test | Result |
|---|---|
| Voice separation, music-only outro level | Mel-Band −240 dB (digital silence), BS-RoFormer −104 dB, htdemucs_ft −67 dB |
| Inter-verse pauses, vocal vs original | 5–19 dB lower |
| Whisper on the removed music stems | No speech detected (no voice loss) |
| Recited verses (Whisper large-v3) | 6 verses; order يدفن، نعد، نرتبط، وهان، رماني، فصرت |
| Intro/verse cut | 1.699 s, chosen by re-transcribing from 3 candidate cuts |
| Score pitch audit | All instruments verified. Timpani 1 (F♯) and a contaminated contrabass tremolo (C♯) were found and replaced |
| Mix | −14.1 LUFS, −1.0 dBTP; voice 12–18 dB over music during words |
| MCP local end-to-end (real media) | 15/15 calls passed, including 3 security rejections |
| MCP Docker CI (synthetic media) | Run 1: failed (no gcc). Run 2: failed (Node 18). **Run 3: passed 18/18** |
| Custom skill, RED baseline (3 runs) | Whisper timing used as final 2/3; whole bayt shown early 3/3; pause gating proposed 3/3; unsourced tashkeel 3/3 |
| Custom skill, GREEN | 0/3, 1/3, 0/3, 0/3 respectively; intro boundary noticed 3/3 |
| Custom skill, REFACTOR | **3/3 runs pass all 7 criteria** |
