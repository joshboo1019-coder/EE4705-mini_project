# Owner: Student B (Task 3 + bonuses)
"""
eval/e2e/demo_bonus.py — Student B. Typed demo for Video_Bonus (one take).

    eval/run_env.sh eval/e2e/demo_bonus.py [--out ~/Videos/Video_Bonus_typed_auto.mp4]

Fresh launch of `main.py --gui` on the virtual display (eval/e2e/stage.py),
every command typed with xdotool exactly like a person, the whole take
recorded, then one frame per segment extracted for checking and the clip
trimmed (boot lines before the first command, idle tail after the last).
Writes <out>, <out minus .mp4>_raw.mp4, <out minus .mp4>_segments.json and
one jpg per segment next to it.

The segment list is the cue sheet (also in eval/video_bonus.md). Moves are
chosen to stay on the clear floor around the spawn point: the rough-terrain
track starts at x ~ 1.3-1.5 m ahead of the spawn heading (+x) and the red stop
sign stands at (-1.3, 0) behind it.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from eval.e2e.stage import Stage, ensure_xvfb, grab_frame, video_duration  # noqa: E402

END = r"\[DONE\]|\[CMD\] rejected"

# (segment title, [(typed text, wait regex, timeout s, pause after s)])
SEGMENTS = [
    ("1 look x2", [
        ("turn around", END, 60, 1.0),
        ("what can you see?", END, 60, 2.5),
        ("turn right 45 degrees", END, 60, 1.0),
        ("is there a chair in front of you?", END, 60, 2.5)]),
    # Segment 3's green-chair goto failed at close range in takes 1 and 2
    # (navigation's frame-filling-chair C1 issue, docs/TEAM_HANDOFF.md C4); the
    # until_see part worked. A ball-only variant (take 3) was aborted: it ends at
    # the ball, and "go back to where you started" would then walk straight
    # through the red stop-sign pole at (-1.3, 0). Kept as is; see MORNING_BRIEF.
    ("2 multi-goal mission", [
        ("go to the red chair, then the orange ball", END, 300, 2.5)]),
    ("3 until_see then goto", [
        ("keep turning until you see the green chair, then go to it", END, 300, 2.5)]),
    ("4 1 m square, then return home", [
        ("go back to where you started", END, 120, 1.0),
        ("turn left 90 degrees", END, 60, 1.0),
        ("walk in a square with 1 meter sides", END, 150, 2.0),
        ("go back to where you started", END, 120, 2.5)]),
    ("5 undo / 'no, the other way'", [
        ("turn left 45 degrees", END, 60, 1.0),
        ("no, the other way", END, 60, 1.5),
        ("undo that", END, 60, 2.5)]),
    ("6 what did you just do?", [
        ("what did you just do?", END, 60, 2.5)]),
    ("7 mid-program stop", [
        ("walk forward half a meter and back half a meter, three times",
         r"\[REPEAT\] iteration=2/", 60, 0.0),
        ("stop", r"\[DONE\]", 30, 2.5)]),
    ("8 non-English, then the redirect", [
        ("gira a la derecha noventa grados", END, 60, 2.0),
        ("turn right 90 degrees", END, 60, 3.0)]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path.home() / "Videos" / "Video_Bonus_typed_auto.mp4"))
    ap.add_argument("--display", default=":99")
    ap.add_argument("--segments", nargs="*", default=None,
                    help="subset by number, e.g. 1 2 (look x2, multi-goal); default all")
    ap.add_argument("--geom", default=None, help="record WxH+X+Y of the X screen (one monitor)")
    ap.add_argument("--font", type=int, default=12)
    args = ap.parse_args()
    out = Path(args.out).expanduser()
    raw = out.with_name(out.stem + "_raw.mp4")
    log = out.with_name(out.stem + "_terminal.log")
    if args.geom:
        from eval.e2e import stage as _stage
        _stage.set_geometry(args.geom)
    if args.display == ":99":
        ensure_xvfb(args.display)
    st = Stage(args.display, font_size=args.font)
    marks = {"segments": []}
    lines = []
    try:
        st.open_terminal("eval/run_env.sh main.py --gui", log, title="demo")
        if st.wait_for(r"Type an English command", 150) is None:
            raise SystemExit("main.py never became ready")
        st.open_panel(timeout=40)
        st.start_recording(raw)
        t0 = time.time()
        time.sleep(2.0)
        chosen = [sg for sg in SEGMENTS if not args.segments or sg[0].split()[0] in args.segments]
        for title, steps in chosen:
            seg = {"title": title, "start": round(time.time() - t0, 2), "steps": []}
            for text, wait, timeout, pause in steps:
                ts = time.time() - t0
                st.type_line(text)
                end = st.wait_for(wait, timeout, on_line=lambda l: lines.append(l))
                seg["steps"].append({"text": text, "typed_at": round(ts, 2),
                                     "end_line": end, "ended_at": round(time.time() - t0, 2)})
                # let the trailing Robot:/[MULTI] lines arrive, then pause for the viewer
                st.wait_for(r"^\0never$", 1.5 + pause, on_line=lambda l: lines.append(l))
            seg["end"] = round(time.time() - t0, 2)
            marks["segments"].append(seg)
            print(f"[DEMO] {title}: {seg['start']}-{seg['end']} s", flush=True)
        time.sleep(1.0)
    finally:
        st.stop_recording()
        st.close()
    dur = video_duration(raw)
    first = marks["segments"][0]["start"] if marks["segments"] else 0.0
    last = marks["segments"][-1]["end"] if marks["segments"] else dur
    start, stop = max(first - 1.0, 0.0), min(last + 1.0, dur)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-to", f"{stop:.2f}",
                    "-i", str(raw), "-c:v", "libx264", "-preset", "medium", "-crf", "21",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], check=True)
    for k, seg in enumerate(marks["segments"], 1):
        t = seg["end"] - 1.0 - start
        img = out.with_name(f"{out.stem}_seg{k}.jpg")
        grab_frame(out, t, img, scale="960:540")
        seg["frame"] = str(img)
        seg["start_in_clip"] = round(seg["start"] - start, 2)
    marks.update(raw=str(raw), out=str(out), trimmed_from=start, trimmed_to=stop,
                 duration_s=round(video_duration(out), 1))
    out.with_name(out.stem + "_segments.json").write_text(json.dumps(marks, indent=1))
    print(f"[DEMO] wrote {out} ({marks['duration_s']} s)", flush=True)


if __name__ == "__main__":
    main()
