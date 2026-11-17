#!/bin/bash
# Render the Ember edition (full-screen 9:16 reel) and finish it like the other editions:
# full-range BT.601 -> limited BT.709, black-preserving overlay grain over the whole frame,
# H.264 High + faststart. Usage: bash render_ember.sh REMOTION_DIR WORK_DIR OUT_DIR
set -euo pipefail
REMOTION=$1; WORK=$2; OUT=$3
B=${REMOTION_BROWSER:-/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell}
mkdir -p "$WORK" "$OUT"
( cd "$REMOTION" && npx remotion render NisalPaper "$WORK/paper_raw.mp4" --codec=h264 --crf=10 --audio-codec=aac --audio-bitrate=320k --concurrency=4 --browser-executable="$B" )
D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$WORK/paper_raw.mp4")
ffmpeg -v error -y -i "$WORK/paper_raw.mp4" -f lavfi -i "color=c=0x808080:s=1080x1920:r=30:d=$D,format=yuv420p,noise=c0s=20:c0f=t" \
  -filter_complex "[0:v]scale=in_range=pc:out_range=tv:in_color_matrix=bt601:out_color_matrix=bt709,format=yuv420p[a];[a][1:v]blend=all_mode=overlay:all_opacity=0.28,format=yuv420p[v]" \
  -map "[v]" -map 0:a -c:v libx264 -preset slow -crf 18 -profile:v high -level 4.1 -pix_fmt yuv420p -shortest \
  -color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709 -tag:v avc1 -c:a copy -movflags +faststart \
  -metadata title="النِصالُ عَلى النِصالِ — Paper" -metadata artist="Poetry: al-Mutanabbi; recitation: Abdullah Al-Anzi" "$OUT/Nisal-ala-Nisal_Paper_9x16.mp4"
echo FINISHED
