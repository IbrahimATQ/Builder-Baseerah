#!/usr/bin/env python3
"""Learned slow motion for the coffee film: RIFE v4.25 / v4.26 frame interpolation on the CPU, 4K, 10-bit in and out.

What it does
  * decodes source frames [round(start*fps) .. round(end*fps)] of a prepared 2160x3840 10-bit clip exactly by frame
    index (ffmpeg `select`, BT.709 limited range -> 16-bit RGB, no 8-bit step),
  * between every pair of neighbouring real frames inserts factor-1 frames at t = k/factor, predicted by RIFE's IFNet
    (one network pass per new frame, arbitrary timestep; no recursive halving, so 3x is as clean as 2x),
  * keeps every real frame untouched, and writes all frames at the same fps as the source
    -> playback speed = 1/factor of the prepared clip (the prepared clips are already 0.8x real time, so
       factor 2 = 0.4x real time, factor 3 = 0.27x real time),
  * encodes 10-bit H.264 (High 10, x264 crf 10, BT.709 tags) or ProRes 422 HQ, and writes a JSON sidecar
    listing, for every output frame, the source frame position it shows (e.g. 62.333) and whether it is real.

Model
  IFNet of RIFE v4.25/v4.26 (Practical-RIFE by hzwer, MIT licence, (c) 2021 hzwer), re-typed here from the
  official train_log/IFNet_HDv3.py of RIFEv4.26_0921.zip (huggingface.co/hzwer/RIFE) and model/warplayer.py
  (github.com/hzwer/Practical-RIFE) after review. The arithmetic is the official forward; only memory handling
  differs: block inputs are resampled piece by piece (never as one full-resolution concatenation), the first
  stride-2 conv and the last transposed conv of a block run in exact horizontal strips when the tensor is large,
  the previous block's full-resolution outputs are freed as soon as they are consumed, and each real frame's encoder
  features are cached across pairs and timesteps. Checked against a literal re-implementation of the official
  forward: max abs difference 2.4e-5 (0..1 range) on real frames; the strip convolutions are bit-identical.
  Weights: a state dict in .safetensors (Comfy-Org/Frame-Interpolation `rife_v4.25.safetensors`, keys "blocks.N.")
  or the official flownet.pkl (keys "module.blockN."), loaded with torch.load(weights_only=True). No pickled code
  is ever executed. Provenance and licence record: /home/user/coffee/slowmo/provenance.json

Scale
  RIFE estimates flow on a downscaled copy (scale 0.5 is the authors' recommendation for 4K, 1.0 = full resolution);
  warping and blending always happen on the full-resolution frame. Frames are zero-padded right/bottom to a multiple
  of max(128, 128/scale) as in the official inference script, then cropped back. On this machine (2 threads), a
  full 2160x3840 frame takes ~10.5 s per new frame at scale 1.0 (python peak ~2.5 GB, + ~0.75 GB for the two
  ffmpeg pipes) and ~6-7 s at scale 0.5.

Usage (what produced /home/user/coffee/slowmo/a_2x.mp4, a_3x.mp4, b_2x.mp4)
  export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
  python -I slowmo.py /home/user/coffee/prep/pourcup.mp4 a_3x.mp4 --start 2.6 --end 4.2 --factor 3 --scale 1.0 \
      --weights /home/user/coffee/slowmo/dl/rife426/RIFEv4.26_0921/flownet.pkl
  options: [--crop X,Y,W,H] (even numbers, full-resolution pixel box) [--threads 2] [--codec x264|prores] [--crf 10]
  python -I slowmo.py SRC.mp4 OUT.mp4 --start 2.6 --end 4.2 --factor 2 --method minterpolate   (ffmpeg baseline)
  Output: OUT.mp4 (2160x3840, 24 fps, yuv420p10le High 10, BT.709) + OUT.json (per output frame: src_frame, real).

  As a library: load_model(path), decode_frames(...), Interpolator(model, scale).iter_between(a, b, ts, key_a, key_b)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

# --------------------------------------------------------------------------------------------- model (RIFE v4.25/26)


def _conv(cin, cout, k=3, s=1, p=1, d=1):
    return nn.Sequential(nn.Conv2d(cin, cout, k, s, p, dilation=d, bias=True), nn.LeakyReLU(0.2, True))


class Head(nn.Module):
    def __init__(self):
        super().__init__()
        self.cnn0 = nn.Conv2d(3, 16, 3, 2, 1)
        self.cnn1 = nn.Conv2d(16, 16, 3, 1, 1)
        self.cnn2 = nn.Conv2d(16, 16, 3, 1, 1)
        self.cnn3 = nn.ConvTranspose2d(16, 4, 4, 2, 1)
        self.relu = nn.LeakyReLU(0.2, True)

    def forward(self, x):
        x = self.relu(self.cnn0(x))
        x = self.relu(self.cnn1(x))
        x = self.relu(self.cnn2(x))
        return self.cnn3(x)


class ResConv(nn.Module):
    def __init__(self, c, dilation=1):
        super().__init__()
        self.conv = nn.Conv2d(c, c, 3, 1, dilation, dilation=dilation, groups=1)
        self.beta = nn.Parameter(torch.ones((1, c, 1, 1)), requires_grad=True)
        self.relu = nn.LeakyReLU(0.2, True)

    def forward(self, x):
        return self.relu(self.conv(x) * self.beta + x)


class IFBlock(nn.Module):
    def __init__(self, in_planes, c=64):
        super().__init__()
        self.conv0 = nn.Sequential(_conv(in_planes, c // 2, 3, 2, 1), _conv(c // 2, c, 3, 2, 1))
        self.convblock = nn.Sequential(*[ResConv(c) for _ in range(8)])
        self.lastconv = nn.Sequential(nn.ConvTranspose2d(c, 4 * 13, 4, 2, 1), nn.PixelShuffle(2))

    def forward(self, parts, flow=None, scale=1.0):
        # identical to interpolating torch.cat(parts) (bilinear resampling is per channel, and a factor of exactly 1
        # is an exact copy), but never builds a resampled copy of the full-resolution concatenation
        down = [_resize(p, 1.0 / scale) for p in parts]
        if flow is not None:
            down.append(_resize(flow, 1.0 / scale) * (1.0 / scale))
        if down[0].shape[2] * down[0].shape[3] > 1_500_000:
            # large input: run the first stride-2 conv in horizontal strips straight from the parts (exact: each strip
            # gets its 1-row halo), so the full-resolution concatenation is never built
            first = self.conv0[0]
            feat = self.conv0[1](first[1](_conv_s2_strips(first[0], down)))
        else:
            feat = self.conv0(torch.cat(down, 1))
        del down
        parts.clear()
        feat = self.convblock(feat)
        if feat.shape[2] * feat.shape[3] * 16 > 1_500_000 * 4:
            tmp = _resize(_lastconv_strips(self.lastconv[0], self.lastconv[1], feat), scale)  # exact, less memory
        else:
            tmp = _resize(self.lastconv(feat), scale)
        del feat
        return tmp[:, :4] * scale, tmp[:, 4:5], tmp[:, 5:]


def _conv_s2_strips(conv: nn.Conv2d, parts, rows=128):
    """conv (3x3, stride 2, padding 1) of torch.cat(parts, 1), computed in strips of `rows` output rows."""
    h = parts[0].shape[2]
    ho = (h - 1) // 2 + 1
    out = []
    for a in range(0, ho, rows):
        b = min(ho, a + rows)
        lo, hi = 2 * a - 1, 2 * b            # input rows 2a-1 .. 2b-1 inclusive
        xs = torch.cat([p[:, :, max(lo, 0):min(hi, h)] for p in parts], 1)
        xs = F.pad(xs, (0, 0, max(0, -lo), max(0, hi - h)))
        out.append(F.conv2d(xs, conv.weight, conv.bias, stride=2, padding=(0, 1)))
        del xs
    return torch.cat(out, 2)


def _lastconv_strips(convt: nn.ConvTranspose2d, shuffle: nn.PixelShuffle, x, rows=32):
    """PixelShuffle(ConvTranspose2d(k=4, s=2, p=1)(x)) computed in strips of `rows` input rows: output rows 2a..2b-1 of
    the transposed conv only depend on input rows a-1..b, so each strip is exact; avoids a multi-GB col2im buffer."""
    h = x.shape[2]
    out = []
    for a in range(0, h, rows):
        b = min(h, a + rows)
        s0, e0 = max(a - 1, 0), min(b + 1, h)
        y = F.conv_transpose2d(x[:, :, s0:e0], convt.weight, convt.bias, stride=2, padding=(0, 1))
        y = y[:, :, 2 * a - 2 * s0 + 1: 2 * b - 2 * s0 + 1]
        out.append(shuffle(y))
        del y
    return torch.cat(out, 2)


def _resize(x, f):
    return x if f == 1.0 else F.interpolate(x, scale_factor=f, mode="bilinear", align_corners=False)


_GRID: dict = {}


def warp(x, flow):
    """Backward warp (model/warplayer.py of Practical-RIFE)."""
    k = (str(flow.device), tuple(flow.shape))
    if k not in _GRID:
        h, w = flow.shape[2], flow.shape[3]
        gx = torch.linspace(-1.0, 1.0, w, device=flow.device).view(1, 1, 1, w).expand(flow.shape[0], -1, h, -1)
        gy = torch.linspace(-1.0, 1.0, h, device=flow.device).view(1, 1, h, 1).expand(flow.shape[0], -1, -1, w)
        _GRID.clear()
        _GRID[k] = torch.cat([gx, gy], 1)
    f = torch.cat([flow[:, 0:1] / ((x.shape[3] - 1.0) / 2.0), flow[:, 1:2] / ((x.shape[2] - 1.0) / 2.0)], 1)
    g = (_GRID[k] + f).permute(0, 2, 3, 1)
    return F.grid_sample(x, g, mode="bilinear", padding_mode="border", align_corners=True)


class IFNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.block0 = IFBlock(7 + 8, c=192)
        self.block1 = IFBlock(8 + 4 + 8 + 8, c=128)
        self.block2 = IFBlock(8 + 4 + 8 + 8, c=96)
        self.block3 = IFBlock(8 + 4 + 8 + 8, c=64)
        self.block4 = IFBlock(8 + 4 + 8 + 8, c=32)
        self.encode = Head()

    def forward_feats(self, img0, img1, f0, f1, timestep, scale_list):
        """img0/img1: (1,3,H,W) in 0..1; f0/f1: self.encode(img); timestep float. Returns the merged frame and
        the final flow (for diagnostics)."""
        t = img0[:, :1] * 0 + timestep
        blocks = [self.block0, self.block1, self.block2, self.block3, self.block4]
        flow = mask = feat = wimg0 = wimg1 = None
        for i, blk in enumerate(blocks):
            if flow is None:
                flow, mask, feat = blk([img0, img1, f0, f1, t], None, scale=scale_list[i])
            else:
                # the block empties `parts` once it has consumed them, so the previous block's full-resolution
                # outputs are freed early (same arithmetic as the official forward, lower peak memory)
                parts = [wimg0, wimg1, warp(f0, flow[:, :2]), warp(f1, flow[:, 2:4]), t, mask, feat]
                del wimg0, wimg1, mask, feat
                fd, mask, feat = blk(parts, flow, scale=scale_list[i])
                flow = flow + fd
                del fd
            wimg0 = warp(img0, flow[:, :2])
            wimg1 = warp(img1, flow[:, 2:4])
        m = torch.sigmoid(mask)
        return wimg0 * m + wimg1 * (1 - m), flow, m


def load_model(path: str) -> IFNet:
    if path.endswith(".safetensors"):
        from safetensors.torch import load_file
        sd = load_file(path)
    else:
        sd = torch.load(path, map_location="cpu", weights_only=True)
    clean = {}
    for k, v in sd.items():
        k = k.replace("module.", "")
        if k.startswith("blocks."):
            n, rest = k[len("blocks."):].split(".", 1)
            k = f"block{n}.{rest}"
        clean[k] = v.float()
    net = IFNet()
    missing, unexpected = net.load_state_dict(clean, strict=False)
    unexpected = [k for k in unexpected if not k.startswith(("teacher.", "caltime."))]  # training-only heads
    if missing or unexpected:
        raise RuntimeError(f"weights do not match RIFE v4.25/26 IFNet: missing={missing[:5]} unexpected={unexpected[:5]}")
    return net.eval()


class Interpolator:
    def __init__(self, net: IFNet, scale: float = 1.0):
        self.net, self.scale = net, scale
        self.scale_list = [16 / scale, 8 / scale, 4 / scale, 2 / scale, 1 / scale]
        self.mult = int(max(128, 128 / scale))
        self._cache: dict = {}

    def _prep(self, key, img: np.ndarray):
        """img: HxWx3 float32 0..1 -> padded tensor + encoder features (cached by key)."""
        if key in self._cache:
            return self._cache[key]
        h, w = img.shape[:2]
        ph, pw = -(-h // self.mult) * self.mult, -(-w // self.mult) * self.mult
        x = torch.from_numpy(np.ascontiguousarray(img.transpose(2, 0, 1)))[None]
        x = F.pad(x, (0, pw - w, 0, ph - h))
        with torch.inference_mode():
            f = self.net.encode(x)
        if len(self._cache) >= 2:
            self._cache.pop(next(iter(self._cache)))
        self._cache[key] = (x, f)
        return x, f

    def frames_between(self, a, b, timesteps, key_a=None, key_b=None):
        return list(self.iter_between(a, b, timesteps, key_a, key_b))

    def iter_between(self, a, b, timesteps, key_a=None, key_b=None):
        """a, b: HxWx3 float32 RGB 0..1 (a may be None if key_a is still cached). Returns a list of HxWx3 float32
        frames at the given timesteps (0<t<1)."""
        h, w = b.shape[:2]
        x0, f0 = self._prep(key_a if key_a is not None else id(a), a)
        x1, f1 = self._prep(key_b if key_b is not None else id(b), b)
        for t in timesteps:
            with torch.inference_mode():
                y, _, _ = self.net.forward_feats(x0, x1, f0, f1, float(t), self.scale_list)
                y = y[0, :, :h, :w].clamp_(0, 1).permute(1, 2, 0).contiguous().numpy()
            yield y
            del y


# --------------------------------------------------------------------------------------------- video I/O (10-bit safe)

_SWS = "accurate_rnd+full_chroma_int+full_chroma_inp"


def probe(src: str) -> tuple[int, int, float]:
    o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate",
                        "-of", "json", src], capture_output=True, text=True, check=True).stdout
    s = json.loads(o)["streams"][0]
    n, d = s["r_frame_rate"].split("/")
    return int(s["width"]), int(s["height"]), float(n) / float(d)


def decode_frames(src: str, first: int, last: int, crop=None):
    """Yield (index, HxWx3 float32 RGB 0..1) for source frames first..last (inclusive), exact by frame number."""
    w, h, _ = probe(src)
    if crop:
        x, y, w, h = crop
    vf = f"select='between(n\\,{first}\\,{last})'"
    if crop:
        vf += f",crop={w}:{h}:{x}:{y}"
    vf += f",scale=in_color_matrix=bt709:in_range=tv:flags={_SWS},format=rgb48le"
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-threads", "2", "-filter_threads", "1", "-i", src, "-an", "-vf", vf, "-fps_mode", "passthrough", "-f", "rawvideo",
                          "-pix_fmt", "rgb48le", "-"], stdout=subprocess.PIPE)
    nbytes = w * h * 3 * 2
    i = first
    try:
        while True:
            buf = p.stdout.read(nbytes)
            if len(buf) < nbytes:
                break
            yield i, np.frombuffer(buf, np.uint16).reshape(h, w, 3).astype(np.float32) / 65535.0
            i += 1
    finally:
        p.stdout.close()
        p.wait()


class Encoder:
    def __init__(self, out: str, w: int, h: int, fps: float, codec: str = "x264", crf: int = 10, preset: str = "slow"):
        self.w, self.h = w, h
        if codec == "prores":
            venc = ["-vf", f"scale=out_color_matrix=bt709:out_range=tv:flags={_SWS},format=yuv422p10le", "-c:v", "prores_ks",
                    "-profile:v", "3", "-vendor", "apl0", "-threads", "2"]
        else:
            venc = ["-vf", f"scale=out_color_matrix=bt709:out_range=tv:flags={_SWS},format=yuv420p10le", "-c:v", "libx264",
                    "-preset", preset, "-crf", str(crf), "-profile:v", "high10", "-x264-params", "threads=2:rc-lookahead=12"]
        self.p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-filter_threads", "1", "-f", "rawvideo", "-pix_fmt", "rgb48le", "-s", f"{w}x{h}",
                                   "-r", str(fps), "-i", "-"] + venc + ["-color_primaries", "bt709", "-color_trc", "bt709",
                                   "-colorspace", "bt709", "-color_range", "tv", "-movflags", "+faststart", "-an", out],
                                  stdin=subprocess.PIPE)

    def write(self, img: np.ndarray):
        x = np.clip(img, 0, 1) * 65535.0
        x += 0.5
        self.p.stdin.write(x.astype(np.uint16).tobytes())

    def close(self):
        self.p.stdin.close()
        if self.p.wait() != 0:
            raise RuntimeError("ffmpeg encoder failed")


# --------------------------------------------------------------------------------------------- drivers


def run_rife(src, out, start, end, factor, weights, scale=1.0, crop=None, codec="x264", crf=10, log=print):
    w, h, fps = probe(src)
    first, last = round(start * fps), round(end * fps)
    if crop:
        w, h = crop[2], crop[3]
    net = load_model(weights)
    ip = Interpolator(net, scale)
    enc = Encoder(out, w, h, fps, codec, crf)
    ts = [k / factor for k in range(1, factor)]
    manifest, prev, times = [], None, []
    import resource
    for i, img in decode_frames(src, first, last, crop):
        if prev is not None:
            t0 = time.time()
            for t, m in zip(ts, ip.iter_between(prev[1], img, ts, key_a=prev[0], key_b=i)):
                enc.write(m)
                manifest.append({"src_frame": round(prev[0] + t, 4), "real": False})
                del m
            times.append((time.time() - t0) / len(ts))
            log(f"  pair {prev[0]}->{i}: {times[-1]:.2f} s/frame, peak RSS {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024:.0f} MB",
                file=sys.stderr)
        else:
            ip._prep(i, img)  # first frame: cache its padded tensor and encoder features
        enc.write(img)
        manifest.append({"src_frame": i, "real": True})
        prev = (i, None)  # its padded tensor and features stay in the Interpolator cache
    enc.close()
    info = {"src": src, "out": out, "method": f"RIFE IFNet ({os.path.basename(weights)}), scale {scale}", "factor": factor,
            "fps": fps, "first_src_frame": first, "last_src_frame": last, "crop_xywh": crop, "frames": len(manifest),
            "seconds": round(len(manifest) / fps, 3), "speed_vs_prepared_clip": round(1 / factor, 4),
            "speed_vs_real_time": round(0.8 / factor, 4),
            "sec_per_new_frame": round(float(np.mean(times)), 2) if times else None,
            "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024), "map": manifest}
    json.dump(info, open(os.path.splitext(out)[0] + ".json", "w"), indent=1)
    return info


def run_minterpolate(src, out, start, end, factor, crop=None, crf=10):
    w, h, fps = probe(src)
    first, last = round(start * fps), round(end * fps)
    vf = f"select='between(n\\,{first}\\,{last})',setpts=N/({fps}*TB)"
    if crop:
        vf += f",crop={crop[2]}:{crop[3]}:{crop[0]}:{crop[1]}"
    vf += (f",minterpolate=fps={fps * factor}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,setpts=N/({fps}*TB)")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-threads", "2", "-filter_threads", "1", "-i", src, "-an", "-vf", vf, "-r", str(fps),
                    "-c:v", "libx264", "-x264-params", "threads=2", "-preset", "slow",
                    "-crf", str(crf), "-pix_fmt", "yuv420p10le", "-profile:v", "high10", "-color_primaries", "bt709", "-color_trc",
                    "bt709", "-colorspace", "bt709", out], check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--start", type=float, required=True, help="seconds in SRC (first real frame = round(start*fps))")
    ap.add_argument("--end", type=float, required=True, help="seconds in SRC (last real frame = round(end*fps))")
    ap.add_argument("--factor", type=int, default=2, help="2 = twice as many frames (half speed), 3, 4 ...")
    ap.add_argument("--method", choices=["rife", "minterpolate"], default="rife")
    ap.add_argument("--weights", default="/home/user/coffee/slowmo/dl/rife426/RIFEv4.26_0921/flownet.pkl",
                    help="RIFE v4.25/4.26 state dict (.pkl via weights_only, or .safetensors)")
    ap.add_argument("--scale", type=float, default=1.0, help="RIFE flow scale: 1.0 (used for the film; best in tests), 0.5 (official 4K advice, faster)")
    ap.add_argument("--crop", default=None, help="X,Y,W,H pixel box (even numbers) to process instead of the full frame")
    ap.add_argument("--codec", choices=["x264", "prores"], default="x264")
    ap.add_argument("--crf", type=int, default=10)
    ap.add_argument("--threads", type=int, default=2)
    a = ap.parse_args()
    torch.set_num_threads(a.threads)
    crop = tuple(int(v) for v in a.crop.split(",")) if a.crop else None
    if a.method == "minterpolate":
        run_minterpolate(a.src, a.out, a.start, a.end, a.factor, crop, a.crf)
        return
    info = run_rife(a.src, a.out, a.start, a.end, a.factor, a.weights, a.scale, crop, a.codec, a.crf)
    info.pop("map")
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
