#!/usr/bin/env bash
# tools/record_bonus.sh — [B] Video_Bonus part (b): the SPEECH segment, performed live.
# Written by Student B. Records ONLY the primary monitor (auto-detected from xrandr, or --geom),
# with microphone audio, while you speak into main.py's push-to-talk.
#
#   tools/record_bonus.sh                 # live: you type v + ENTER in the demo terminal and speak
#   tools/record_bonus.sh --dry-run       # no speech: the same sentences are typed (proves the script)
#   tools/record_bonus.sh --out FILE --geom 2560x1440+745+2160
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="$HOME/Videos/candidates/Video_Bonus_speech.mp4"
GEOM=""
DRY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --out) OUT="$2"; shift 2 ;;
    --geom) GEOM="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    *) echo "unknown arg $1" >&2; exit 2 ;;
  esac
done
if [[ -z "$GEOM" ]]; then   # the primary monitor (marked * by xrandr)
  GEOM=$(xrandr --listmonitors | awk '/\*/{split($3,a,"[/x+]"); print a[1]"x"a[3]"+"a[5]"+"a[6]; exit}')
fi
S1="turn left ninety degrees"
S2="walk forward for three seconds, then turn back"
S3="向前走三秒"
cat <<TXT
=== Video_Bonus speech segment — recording monitor $GEOM -> $OUT ===
When the demo terminal shows 'Type an English command', for EACH sentence:
  1. click into the demo terminal, type  v  and press ENTER,
  2. right after ENTER, say the sentence clearly, then stay quiet for 1 s,
  3. wait for [DONE] (or '[CMD] rejected') before the next one.
Sentences, in order:
  1. "$S1"
  2. "$S2"              (multi-step)
  3. "$S3"  (Mandarin: xiang qian zou san miao — must be rejected, never executed)
The [STT] text=... lines must be visible. Press ENTER in THIS shell when done.
TXT
export QUADRUPED_MUJOCO_ROOT="${QUADRUPED_MUJOCO_ROOT:-$(cd .. && pwd)/quadruped_mujoco}"
ARGS=(--display "${DISPLAY:-:1}" --geom "$GEOM" --out "$OUT" --command "eval/run_env.sh main.py --gui")
if [[ $DRY -eq 1 ]]; then
  # stand-in for speech: the same sentences typed (the Mandarin one becomes an ASCII stand-in)
  eval/run_env.sh tools/record_take.py "${ARGS[@]}" --audio \
      --type "$S1" --type "$S2" --type "avancez tout droit"
else
  eval/run_env.sh tools/record_take.py "${ARGS[@]}" --audio --interactive
fi
