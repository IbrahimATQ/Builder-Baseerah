#!/bin/bash
# Render both editions with Remotion, then finish: full-range BT.601 -> limited BT.709,
# black-preserving overlay grain inside the picture only, H.264 High + faststart.
# Usage: bash render_and_finish.sh REMOTION_DIR WORK_DIR OUT_DIR
set -euo pipefail
REMOTION=$1; WORK=$2; OUT=$3
B=${REMOTION_BROWSER:-/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell}
mkdir -p "$WORK" "$OUT"
( cd "$REMOTION"
  npx remotion render NisalScope "$WORK/scope_raw.mp4" --codec=h264 --crf=10 --audio-codec=aac --audio-bitrate=320k --concurrency=4 --browser-executable="$B"
  npx remotion render NisalVertical "$WORK/vertical_raw.mp4" --codec=h264 --crf=10 --audio-codec=aac --audio-bitrate=320k --concurrency=4 --browser-executable="$B" )

finish() { # in out W H Y crf
  local D; D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$1")
  ffmpeg -v error -y -i "$1" -f lavfi -i "color=c=0x808080:s=${3}x${4}:r=30:d=${D},format=yuv420p,noise=c0s=22:c0f=t" \
    -filter_complex "[0:v]scale=in_range=pc:out_range=tv:in_color_matrix=bt601:out_color_matrix=bt709,format=yuv420p,split[a][b];[b]crop=${3}:${4}:0:${5}[pic];[pic][1:v]blend=all_mode=overlay:all_opacity=0.32,format=yuv420p[g];[a][g]overlay=0:${5}:shortest=1:format=yuv420,format=yuv420p[v]" \
    -map "[v]" -map 0:a -c:v libx264 -preset slow -crf "$6" -profile:v high -level 4.1 -pix_fmt yuv420p \
    -color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709 -tag:v avc1 -c:a copy -movflags +faststart \
    -metadata title="النِصالُ عَلى النِصالِ" -metadata artist="Poetry: al-Mutanabbi; recitation: Abdullah Al-Anzi" "$2"
}
finish "$WORK/scope_raw.mp4" "$OUT/Nisal-ala-Nisal_16x9_scope.mp4" 1920 803 138 17
finish "$WORK/vertical_raw.mp4" "$OUT/Nisal-ala-Nisal_9x16_vertical.mp4" 1080 1350 250 18
ffmpeg -v error -y -i "$OUT/Nisal-ala-Nisal_16x9_scope.mp4" -c:v libx264 -preset slow -crf 22 -profile:v high -level 4.1 -pix_fmt yuv420p \
  -color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709 -tag:v avc1 -c:a copy -movflags +faststart -map_metadata 0 \
  "$OUT/Nisal-ala-Nisal_16x9_scope_share.mp4"
echo FINISHED
