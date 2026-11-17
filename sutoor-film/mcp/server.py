#!/usr/bin/env python3
"""ARABIC POETRY FILM PRODUCTION MCP — one remote connector for the whole pipeline.

Tools (all media stays on this server; nothing is uploaded to third-party AI services):
  import_media, list_assets, inspect_media, extract_audio, separate_voice, transcribe_arabic,
  sync_subtitles, search_footage, download_licensed_media, edit_video, create_composition,
  mix_audio, render_film, inspect_output

Security model
  * No arbitrary shell or ffmpeg filter strings: every tool builds argument lists itself.
  * Asset names are validated and resolved inside WORKSPACE (no path traversal).
  * Downloads: footage only from an allowlist of licensed-media CDNs; imports only over HTTPS to
    public IPs (blocks SSRF into private networks), with a size cap.
  * Endpoint path can be made unguessable with MCP_PATH (claude.ai custom connectors are OAuth or
    authless; a secret path is the pragmatic protection for a personal deployment).

Run:  python server.py            (streamable HTTP on $HOST:$PORT$MCP_PATH, default 0.0.0.0:7860/mcp)
"""
from __future__ import annotations

import base64
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError  # message is shown to the client

HERE = Path(__file__).resolve().parent
PIPELINE = Path(os.environ.get("PIPELINE_DIR", HERE.parent / "pipeline"))
REMOTION = Path(os.environ.get("REMOTION_DIR", HERE.parent / "remotion"))
WORKSPACE = Path(os.environ.get("MCP_WORKSPACE", HERE / "workspace")).resolve()
WORKSPACE.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(PIPELINE))

MAX_IMPORT_BYTES = int(os.environ.get("MAX_IMPORT_BYTES", 600 * 1024 * 1024))
FOOTAGE_HOSTS = {"assets.mixkit.co", "cdn.pixabay.com", "upload.wikimedia.org"}
UA = "arabic-poetry-film-mcp/1.0 (personal film production)"
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$")

GRADES = {  # per-act palettes (see skill references/direction.md)
    "neutral": "eq=saturation=0.85",
    "mortality": "eq=saturation=0.6:contrast=1.06,colorbalance=bs=0.04:bm=0.02",
    "preparation": "colorbalance=rh=0.06:gh=0.02:bh=-0.05:rs=-0.02,eq=saturation=0.8",
    "time": "colorbalance=bs=0.07:bm=0.04:rh=-0.02,eq=saturation=0.7:brightness=-0.02",
    "detachment": "eq=saturation=0.55,colorbalance=rh=0.04:bh=-0.03",
    "suffering": "eq=contrast=1.12:saturation=0.75,colorbalance=rh=0.07:bs=-0.03",
    "endurance": "eq=contrast=1.08:saturation=0.85,colorbalance=rh=0.08:gh=0.03:bh=-0.06",
}

server = MCPServer(
    name="arabic-poetry-film-production",
    title="ARABIC POETRY FILM PRODUCTION MCP",
    version="1.0.0",
    instructions=(
        "Produce cinematic films from Arabic poetry recitations. Typical order: import_media -> "
        "inspect_media -> extract_audio -> separate_voice -> transcribe_arabic -> sync_subtitles -> "
        "search_footage -> download_licensed_media -> edit_video -> mix_audio -> create_composition -> "
        "render_film -> inspect_output. Subtitle only what is recited; never gate pauses."
    ),
)


# ----------------------------------------------------------------- helpers
def _asset(name: str, must_exist: bool = True) -> Path:
    if not NAME_RE.match(name or ""):
        raise ToolError(f"invalid asset name: {name!r}")
    p = (WORKSPACE / name).resolve()
    if WORKSPACE not in p.parents:
        raise ToolError("asset outside workspace")
    if must_exist and not p.exists():
        raise ToolError(f"no such asset: {name}")
    return p


def _run(args: list[str], timeout: int = 3600, cwd: Path | None = None) -> str:
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    if r.returncode != 0:
        text = r.stderr + r.stdout
        key = [ln for ln in text.splitlines() if "Error" in ln or "error:" in ln][:3]
        raise ToolError(f"{Path(args[0]).name} failed: {' | '.join(key)[:600]} … {text[-700:]}")
    return r.stdout + r.stderr


def _ffprobe(p: Path) -> dict:
    out = _run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(p)])
    return json.loads(out[out.index("{"):])


def _loudness(p: Path) -> dict:
    out = _run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(p), "-af", "ebur128=peak=true", "-f", "null", "-"])
    tail = out[out.rfind("Summary:"):]
    grab = lambda k: (re.search(rf"{k}:\s+(-?[\d.]+)", tail) or [None, None])[1]  # noqa: E731
    return {"integrated_lufs": grab("I"), "lra_lu": grab("LRA"), "true_peak_dbfs": grab("Peak")}


def _public_https(url: str) -> None:
    u = urllib.parse.urlparse(url)
    if u.scheme != "https" or not u.hostname:
        raise ToolError("only https URLs are accepted")
    for info in socket.getaddrinfo(u.hostname, 443):
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ToolError("refusing to fetch from a non-public address")


def _download(url: str, dest: Path) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    total = 0
    try:
        r = urllib.request.urlopen(req, timeout=120)
    except urllib.error.HTTPError as e:
        raise ToolError(f"download failed: HTTP {e.code} for {urllib.parse.urlparse(url).hostname}")
    with r, open(dest, "wb") as f:
        while chunk := r.read(1 << 20):
            total += len(chunk)
            if total > MAX_IMPORT_BYTES:
                f.close()
                dest.unlink(missing_ok=True)
                raise ToolError("file exceeds size limit")
            f.write(chunk)
    return total


def _licences() -> dict:
    p = WORKSPACE / "licences.json"
    return json.loads(p.read_text()) if p.exists() else {}


# ----------------------------------------------------------------- tools
@server.tool()
def import_media(filename: str, url: str = "", base64_data: str = "") -> dict:
    """Bring a recitation video/audio into the workspace, from a public HTTPS link (e.g. a shared
    iCloud/Drive direct-download link) or from base64 data (small files). Returns the asset name."""
    dest = _asset(filename, must_exist=False)
    if url:
        _public_https(url)
        size = _download(url, dest)
    elif base64_data:
        raw = base64.b64decode(base64_data)
        if len(raw) > MAX_IMPORT_BYTES:
            raise ToolError("file exceeds size limit")
        dest.write_bytes(raw)
        size = len(raw)
    else:
        raise ToolError("give url or base64_data")
    return {"asset": dest.name, "bytes": size}


@server.tool()
def list_assets() -> list[dict]:
    """List files in the production workspace with sizes."""
    return [{"asset": p.name, "bytes": p.stat().st_size} for p in sorted(WORKSPACE.iterdir()) if p.is_file()]


@server.tool()
def inspect_media(asset: str) -> dict:
    """Inspect an uploaded media file: duration, video size/fps/codec, audio format, loudness."""
    p = _asset(asset)
    info = _ffprobe(p)
    streams = [
        {k: s.get(k) for k in ("codec_type", "codec_name", "width", "height", "r_frame_rate", "sample_rate", "channels", "duration")}
        for s in info.get("streams", [])
    ]
    res = {"duration_s": float(info["format"].get("duration", 0)), "streams": streams}
    if any(s["codec_type"] == "audio" for s in streams):
        res["loudness"] = _loudness(p)
    return res


@server.tool()
def extract_audio(asset: str, sample_rate: int = 44100) -> dict:
    """Extract the audio track as 16-bit PCM WAV (44.1 kHz suits the separation models)."""
    src = _asset(asset)
    out = _asset(Path(asset).stem + f"_audio{sample_rate // 1000}k.wav", must_exist=False)
    _run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vn", "-ac", "2", "-ar", str(int(sample_rate)), "-c:a", "pcm_s16le", str(out)])
    return {"asset": out.name, "probe": inspect_media(out.name)}


@server.tool()
def separate_voice(asset: str, model: str = "vocals_mel_band_roformer.ckpt", music_only_start: float = -1, music_only_end: float = -1) -> dict:
    """Separate the reciter's voice from background music (Mel-Band RoFormer by default; also
    'model_bs_roformer_ep_368_sdr_12.9628.ckpt' or 'htdemucs_ft.yaml'). If a music-only region is
    given, reports the vocal-stem level there (leakage) relative to the whole stem."""
    allowed = {"vocals_mel_band_roformer.ckpt", "model_bs_roformer_ep_368_sdr_12.9628.ckpt", "htdemucs_ft.yaml"}
    if model not in allowed:
        raise ToolError(f"model must be one of {sorted(allowed)}")
    src = _asset(asset)
    outdir = WORKSPACE / ("sep_" + Path(model).stem)
    outdir.mkdir(exist_ok=True)
    _run(["audio-separator", str(src), "-m", model, "--model_file_dir", str(WORKSPACE / ".models"),
          "--output_dir", str(outdir), "--output_format", "WAV", "--log_level", "warning"], timeout=7200)
    produced = {}
    for f in outdir.glob(f"{src.stem}_*.wav"):
        stem = re.search(r"_\((\w+)\)_", f.name).group(1).lower()
        stem = "voice" if stem == "vocals" else "music"
        dest = WORKSPACE / f"{src.stem}_{stem}_{Path(model).stem[:24]}.wav"
        shutil.move(str(f), dest)
        produced[stem] = dest.name
    qc: dict[str, Any] = {}
    if music_only_end > music_only_start >= 0:
        import numpy as np
        import soundfile as sf

        y, sr = sf.read(WORKSPACE / produced["voice"], dtype="float32", always_2d=True)
        y = y.mean(1)
        db = lambda x: float(20 * np.log10(np.sqrt(np.mean(x**2)) + 1e-12))  # noqa: E731
        qc = {"voice_stem_db": round(db(y), 1), "music_only_region_db": round(db(y[int(music_only_start * sr):int(music_only_end * sr)]), 1)}
    return {"assets": produced, "qc": qc}


@server.tool()
def transcribe_arabic(asset: str, model: str = "large-v3") -> dict:
    """Transcribe Arabic speech with faster-whisper (no diacritics; use it to check WHAT is recited,
    not for subtitle timing). Returns segments with word timestamps."""
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    from align_recitation import load_mono16k
    from faster_whisper import WhisperModel

    if model not in {"large-v3", "large-v3-turbo", "medium", "small"}:
        raise ToolError("unsupported model")
    audio = load_mono16k(str(_asset(asset))).squeeze(0).numpy()
    m = WhisperModel(model, device="cpu", compute_type="int8")
    segs, info = m.transcribe(audio, language="ar", word_timestamps=True, beam_size=5, condition_on_previous_text=False)
    return {"segments": [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
                          "words": [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)} for w in s.words or []]}
                         for s in segs]}


@server.tool()
def sync_subtitles(asset: str, verses: list[dict], intro: str = "") -> dict:
    """Force-align the EXACT diacritised text to the voice (MMS_FA). `verses` = [{"sadr": ..., "ajuz": ...}]
    in RECITED order; `intro` = any spoken words before the first verse. Writes a hemistich-level SRT
    (sadr and ajuz as separate cues) and a JSON timing asset."""
    from align_recitation import load_mono16k, mms_align

    lines = ([("intro", intro)] if intro else []) + [
        (f"v{i + 1}{part}", v[key]) for i, v in enumerate(verses) for part, key in (("a", "sadr"), ("b", "ajuz"))
    ]
    words, owner = [], []
    for key, text in lines:
        for w in text.split():
            words.append(w)
            owner.append(key)
    aligned = mms_align(load_mono16k(str(_asset(asset))), words)
    for a in aligned:
        a["line"] = owner[a["index"]]
    hem: dict[str, dict] = {}
    for a in aligned:
        h = hem.setdefault(a["line"], {"start": a["start"], "end": a["end"], "words": []})
        h["end"] = a["end"]
        h["words"].append(a["word"])
    ts = lambda t: f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d},{int(round(t % 1 * 1000)):03d}"  # noqa: E731
    cues = [(k, v) for k, v in hem.items() if k != "intro"]
    srt = []
    for i, (k, v) in enumerate(cues):
        nxt = cues[i + 1][1]["start"] if i + 1 < len(cues) else v["end"] + 1.0
        srt.append(f"{i + 1}\n{ts(max(0, v['start'] - 0.12))} --> {ts(max(v['end'] + 0.3, nxt - 0.05) if k.endswith('b') else nxt - 0.05)}\n{' '.join(v['words'])}\n")
    base = Path(asset).stem
    _asset(base + "_hemistichs.srt", False).write_text("\n".join(srt), encoding="utf-8")
    _asset(base + "_alignment.json", False).write_text(json.dumps({"words": aligned, "hemistichs": hem}, ensure_ascii=False, indent=1), encoding="utf-8")
    low = [a for a in aligned if a["score"] < 0.4]
    return {"srt": base + "_hemistichs.srt", "timing": base + "_alignment.json",
            "hemistichs": {k: {"start": v["start"], "end": v["end"]} for k, v in hem.items()},
            "low_confidence_words": low}


@server.tool()
def search_footage(query: str, source: str = "mixkit", limit: int = 12) -> list[dict]:
    """Search freely licensed cinematic footage. source: 'mixkit' (no key; Mixkit Free License),
    'wikimedia' (PD/CC0/CC-BY only are returned), or 'pixabay' (needs PIXABAY_API_KEY env)."""
    limit = max(1, min(int(limit), 40))
    if source == "mixkit":
        from mixkit_catalog import harvest

        tag = re.sub(r"[^a-z0-9-]+", "-", query.lower()).strip("-")
        items = list(harvest([tag], pages=1, delay=0).values())
        return [{"id": str(i["id"]), "title": i["title"], "page_url": i["page_url"], "preview": i["preview_360"],
                 "download": i["download_1080"], "fallback_download": i["download_720"], "license": i["license"]} for i in items[:limit]]
    if source == "wikimedia":
        q = urllib.parse.urlencode({"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
                                    "gsrsearch": f"{query} filetype:video", "gsrlimit": limit, "prop": "imageinfo",
                                    "iiprop": "url|extmetadata|size"})
        req = urllib.request.Request(f"https://commons.wikimedia.org/w/api.php?{q}", headers={"User-Agent": UA})
        try:
            data = json.load(urllib.request.urlopen(req, timeout=60))
        except urllib.error.HTTPError as e:
            raise ToolError(f"Wikimedia API returned HTTP {e.code}" + (" (rate limited; retry later)" if e.code == 429 else ""))
        out = []
        for p in (data.get("query", {}).get("pages", {}) or {}).values():
            ii = (p.get("imageinfo") or [{}])[0]
            lic = ii.get("extmetadata", {}).get("LicenseShortName", {}).get("value", "")
            if not re.search(r"public domain|cc0|^cc by \d|^cc-by-\d|^cc by$", lic, re.I) or re.search(r"sa|nc|nd", lic, re.I):
                continue
            out.append({"id": p["title"], "title": p["title"], "download": ii.get("url"), "license": lic,
                        "attribution": re.sub("<[^>]+>", "", ii.get("extmetadata", {}).get("Artist", {}).get("value", ""))})
        return out
    if source == "pixabay":
        key = os.environ.get("PIXABAY_API_KEY")
        if not key:
            raise ToolError("PIXABAY_API_KEY is not configured on this server")
        q = urllib.parse.urlencode({"key": key, "q": query, "per_page": max(3, limit), "safesearch": "true"})
        data = json.load(urllib.request.urlopen(f"https://pixabay.com/api/videos/?{q}", timeout=60))
        return [{"id": str(h["id"]), "title": h.get("tags", ""), "page_url": h.get("pageURL"),
                 "download": (h["videos"].get("large") or h["videos"].get("medium"))["url"], "license": "Pixabay Content License"}
                for h in data.get("hits", [])[:limit]]
    raise ToolError("source must be mixkit, wikimedia or pixabay")


@server.tool()
def download_licensed_media(url: str, filename: str, license: str, source_page: str = "", attribution: str = "") -> dict:
    """Download a footage/audio file from an allowlisted licensed-media CDN and record its licence."""
    host = urllib.parse.urlparse(url).hostname or ""
    if host not in FOOTAGE_HOSTS:
        raise ToolError(f"host not allowlisted: {host}")
    dest = _asset(filename, must_exist=False)
    size = _download(url, dest)
    lic = _licences()
    lic[dest.name] = {"url": url, "license": license, "source_page": source_page, "attribution": attribution}
    (WORKSPACE / "licences.json").write_text(json.dumps(lic, indent=1, ensure_ascii=False))
    return {"asset": dest.name, "bytes": size, "probe": inspect_media(dest.name)}


@server.tool()
def edit_video(asset: str, output: str, start: float = 0.0, duration: float = 5.0, width: int = 1920, height: int = 1080,
               grade: str = "neutral", speed: float = 1.0, fps: int = 30) -> dict:
    """Trim, re-frame (scale + centre crop), retime and colour-grade a clip with a named palette:
    neutral, mortality, preparation, time, detachment, suffering, endurance."""
    if grade not in GRADES:
        raise ToolError(f"grade must be one of {sorted(GRADES)}")
    if not (0.25 <= speed <= 4 and 16 <= width <= 3840 and 16 <= height <= 3840 and 0 < duration <= 120 and 1 <= fps <= 60):
        raise ToolError("parameter out of range")
    src, out = _asset(asset), _asset(output, must_exist=False)
    vf = (f"setpts=PTS/{speed},scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,"
          f"crop={width}:{height},fps={fps},{GRADES[grade]},format=yuv420p")
    _run(["ffmpeg", "-v", "error", "-y", "-ss", str(start), "-i", str(src), "-t", str(duration * speed), "-an",
          "-vf", vf, "-c:v", "libx264", "-preset", "slow", "-crf", "14", str(out)])
    return {"asset": out.name, "probe": inspect_media(out.name)}


@server.tool()
def mix_audio(voice: str, music: str, timing: str, ambience: str = "", output_prefix: str = "mix") -> dict:
    """Mix voice + music (+ ambience) with ducking driven by aligned word timings, then master to
    -14 LUFS / -1 dBTP. `timing` is a JSON asset with duration, voice_film_start and words[film_start, film_end]."""
    import mix_master
    import numpy as np
    import soundfile as sf

    amb = ambience
    if not amb:
        amb_p = _asset(output_prefix + "_silence.wav", False)
        t = json.loads(_asset(timing).read_text())
        sf.write(amb_p, np.zeros((int(t["duration"] * 48000), 2), np.float32), 48000)
        amb = amb_p.name
    outdir = WORKSPACE / (output_prefix + "_out")
    mix_master.main(str(_asset(timing)), str(_asset(voice)), str(_asset(music)), str(_asset(amb)), str(outdir))
    final = WORKSPACE / f"{output_prefix}_master.wav"
    shutil.copy(outdir / "mix_master.wav", final)
    return {"asset": final.name, "report": json.loads((outdir / "mix_report.json").read_text())}


@server.tool()
def create_composition(edl: dict) -> dict:
    """Validate and install an edit decision list (shots, verses, title, credits, audio) for the
    Remotion film, copying referenced workspace assets into the Remotion project."""
    need = {"fps", "duration", "audio", "title", "credits", "shots", "verses"}
    missing = need - set(edl)
    if missing:
        raise ToolError(f"edl missing {sorted(missing)}")
    pub = REMOTION / "public"
    for shot in edl["shots"]:
        src = _asset(Path(shot["src"]).name)
        (pub / "shots").mkdir(parents=True, exist_ok=True)
        shutil.copy(src, pub / "shots" / src.name)
        shot["src"] = f"shots/{src.name}"
    a = _asset(Path(edl["audio"]).name)
    (pub / "audio").mkdir(parents=True, exist_ok=True)
    shutil.copy(a, pub / "audio" / a.name)
    edl["audio"] = f"audio/{a.name}"
    (REMOTION / "src" / "edl.json").write_text(json.dumps(edl, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"installed": True, "shots": len(edl["shots"]), "verses": len(edl["verses"]), "duration": edl["duration"]}


@server.tool()
def render_film(composition: str = "NisalScope", output: str = "film.mp4", crf: int = 14) -> dict:
    """Render the installed composition with Remotion (NisalScope = 1920x1080 2.39:1 scope matte,
    NisalVertical = 1080x1920) to H.264 + AAC, then add fine film grain and +faststart."""
    if composition not in {"NisalScope", "NisalVertical"}:
        raise ToolError("unknown composition")
    raw = WORKSPACE / ("raw_" + _asset(output, False).name)
    args = ["npx", "remotion", "render", composition, str(raw), "--codec=h264", f"--crf={int(crf)}",
            "--audio-codec=aac", "--audio-bitrate=320k", "--concurrency=4"]
    browser = os.environ.get("REMOTION_BROWSER")
    if browser:
        args.append(f"--browser-executable={browser}")
    _run(args, timeout=7200, cwd=REMOTION)
    out = _asset(output, False)
    _run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-vf", "noise=c0s=6:c0f=t,format=yuv420p", "-c:v", "libx264",
          "-preset", "slow", "-crf", str(int(crf)), "-profile:v", "high", "-c:a", "copy", "-movflags", "+faststart", str(out)])
    return {"asset": out.name, "probe": inspect_media(out.name)}


@server.tool()
def inspect_output(asset: str, stills: int = 6) -> dict:
    """QC a rendered film: format, loudness, and a contact sheet of evenly spaced frames (PNG asset)."""
    p = _asset(asset)
    meta = inspect_media(asset)
    n = max(1, min(int(stills), 24))
    sheet = _asset(Path(asset).stem + "_contact.png", False)
    dur = meta["duration_s"]
    _run(["ffmpeg", "-v", "error", "-y", "-i", str(p), "-vf", f"fps={n / max(dur, 0.1)},scale=480:-2,tile={min(n, 6)}x{(n + 5) // 6}",
          "-frames:v", "1", str(sheet)])
    return {"meta": meta, "contact_sheet": sheet.name, "licences": _licences()}


if __name__ == "__main__":
    server.run(
        "streamable-http",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", 7860)),
        streamable_http_path=os.environ.get("MCP_PATH", "/mcp"),
    )
