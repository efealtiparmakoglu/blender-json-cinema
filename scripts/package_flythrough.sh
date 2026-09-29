#!/bin/zsh
# Flythrough karelerini GIF + MP4'e paketler (repo kökünden çalıştır).
# Kabuk erişimi olan her ortamda: scripts/package_flythrough.sh
set -euo pipefail
cd "$(dirname "$0")/../renders"

# 47 kare: 48. ilkinin kopyası (tam 360° tur) — döngüde tekrar etmesin
ffmpeg -y -framerate 12 -start_number 1 -i flythrough/frame_%04d.png -frames:v 47 \
  -filter_complex "[0:v]scale=640:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4" \
  flythrough.gif

ffmpeg -y -framerate 12 -start_number 1 -i flythrough/frame_%04d.png -frames:v 48 \
  -c:v libx264 -crf 18 -pix_fmt yuv420p -movflags +faststart \
  flythrough.mp4

ls -lh flythrough.gif flythrough.mp4
