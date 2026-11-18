#!/bin/bash
# Render the Journey edition at 2160x3840 (the 1080x1920 composition at scale 2: text and vectors are
# drawn at full 4K, the picture is the 4K plate) and finish it: full-range BT.601 -> limited BT.709,
# fine temporal grain over picture AND text, H.264 High 5.1 + faststart; plus a 1080x1920 share copy.
# Usage: bash render_journey.sh REMOTION_DIR WORK_DIR OUT_DIR
set -euo pipefail
REMOTION=$1; WORK=$2; OUT=$3
B=${REMOTION_BROWSER:-/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell}
mkdir -p "$WORK" "$OUT"
( cd "$REMOTION" && npx remotion render NisalJourney "$WORK/journey_raw.mp4" --scale=2 --codec=h264 --crf=12 \
    --audio-codec=aac --audio-bitrate=320k --concurrency=${CONCURRENCY:-3} --browser-executable="$B" )
D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$WORK/journey_raw.mp4")
ffmpeg -v error -y -i "$WORK/journey_raw.mp4" -f lavfi -i "color=c=0x808080:s=2160x3840:r=24:d=$D,format=yuv420p,noise=c0s=7:c0f=t" \
  -filter_complex "[0:v]scale=in_range=pc:out_range=tv:in_color_matrix=bt601:out_color_matrix=bt709,format=yuv420p[a];[a][1:v]blend=all_mode=overlay:all_opacity=0.55,format=yuv420p[v]" \
  -map "[v]" -map 0:a -c:v libx264 -preset slow -crf 16 -profile:v high -level 5.1 -pix_fmt yuv420p -shortest \
  -color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709 -tag:v avc1 -c:a copy -movflags +faststart \
  -metadata title="النِصالُ عَلى النِصالِ — Journey" -metadata artist="Poetry: al-Mutanabbi; recitation: Abdullah Al-Anzi" \
  "$OUT/Nisal-ala-Nisal_Journey_4K_9x16.mp4"
ffmpeg -v error -y -i "$OUT/Nisal-ala-Nisal_Journey_4K_9x16.mp4" -vf "scale=1080:1920:flags=lanczos" -c:v libx264 -preset slow -crf 19 \
  -profile:v high -level 4.1 -pix_fmt yuv420p -color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709 -tag:v avc1 \
  -c:a copy -movflags +faststart -map_metadata 0 "$OUT/Nisal-ala-Nisal_Journey_1080x1920_share.mp4"
echo FINISHED
