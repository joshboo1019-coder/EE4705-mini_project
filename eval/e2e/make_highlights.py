"""
eval/e2e/make_highlights.py — Student B. ~/Videos/e2e/highlights.mp4 for the
morning review: short captioned excerpts of e2e clips, concatenated.

    python eval/e2e/make_highlights.py spec.json [--out ~/Videos/e2e/highlights.mp4]

spec.json: [{"clip": "<path>", "start": s, "dur": s, "speed": 1.0, "caption": "..."}, ...]
Each excerpt is scaled to 1280x720, sped up by `speed`, captioned at the top,
and the pieces are concatenated (H.264, no audio).
"""

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def esc(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’")
            .replace("%", "\\%").replace(",", "\\,"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--out", default=str(Path.home() / "Videos" / "e2e" / "highlights.mp4"))
    args = ap.parse_args()
    spec = json.loads(Path(args.spec).read_text())
    tmp = Path(tempfile.mkdtemp(prefix="highlights_"))
    parts = []
    for k, s in enumerate(spec):
        part = tmp / f"part{k:02d}.mp4"
        speed = float(s.get("speed", 1.0))
        cap = esc(s["caption"])
        vf = (f"setpts=PTS/{speed},scale=1280:720,"
              f"drawbox=x=0:y=0:w=iw:h=44:color=black@0.75:t=fill,"
              f"drawtext=fontfile={FONT}:text='{cap}':fontcolor=white:fontsize=22:x=14:y=11")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(s.get("start", 0)), "-t", str(s["dur"]),
                        "-i", s["clip"], "-an", "-vf", vf, "-r", "25", "-c:v", "libx264",
                        "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p", str(part)], check=True)
        parts.append(part)
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    out = Path(args.out).expanduser()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", "-movflags", "+faststart", str(out)], check=True)
    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                          "default=nk=1:nw=1", str(out)], capture_output=True, text=True).stdout.strip()
    print(f"wrote {out} ({float(dur):.1f} s)")


if __name__ == "__main__":
    main()
