#!/usr/bin/env bash
# tools/concat_bonus.sh — [B] Video_Bonus = (a) typed segments + (b) speech segment.
# Written by Student B. Scales both to 1920x1080, 30 fps, H.264 + AAC (a silent track is added
# to a part without audio), then concatenates.
#   tools/concat_bonus.sh A.mp4 B.mp4 [OUT]   (default OUT: ~/Videos/candidates/Video_Bonus_final.mp4)
set -euo pipefail
A="$1"; B="$2"; OUT="${3:-$HOME/Videos/candidates/Video_Bonus_final.mp4}"
TMP=$(mktemp -d "${TMPDIR:-/tmp}/concat_bonus.XXXXXX")
norm() {  # in out
  if ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$1" | grep -q .; then
    ffmpeg -v error -y -i "$1" -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,setsar=1" \
      -c:v libx264 -preset medium -crf 21 -pix_fmt yuv420p -c:a aac -ar 48000 -ac 2 -b:a 160k "$2"
  else
    ffmpeg -v error -y -i "$1" -f lavfi -i anullsrc=r=48000:cl=stereo -shortest \
      -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,setsar=1" \
      -c:v libx264 -preset medium -crf 21 -pix_fmt yuv420p -c:a aac -ar 48000 -ac 2 -b:a 160k "$2"
  fi
}
norm "$A" "$TMP/a.mp4"
norm "$B" "$TMP/b.mp4"
printf "file '%s'\nfile '%s'\n" "$TMP/a.mp4" "$TMP/b.mp4" > "$TMP/list.txt"
ffmpeg -v error -y -f concat -safe 0 -i "$TMP/list.txt" -c copy -movflags +faststart "$OUT"
echo "wrote $OUT ($(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT") s, $(du -h "$OUT" | cut -f1))"
