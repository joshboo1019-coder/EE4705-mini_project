"""
tools/record_take.py — [B] record one take of a project command on ONE monitor.
Written by Student B. Used for the final videos (docs/VIDEO_CUES.md).

    eval/run_env.sh tools/record_take.py --geom 2560x1440+745+2160 --display :1 \
        --command "eval/run_env.sh tools/video_task2_demo.py --gui --overlay-geom 1280x720+745+2880" \
        --ready "\\[V2\\] ready" --done "\\[V2\\] done" --term-h 720 --out ~/Videos/candidates/x.mp4

Opens the command in a terminal (left half of the monitor, or the top `--term-h`
pixels), moves the platform's browser panel to the right half, grabs a test
frame, records the monitor region with ffmpeg (optionally with microphone
audio, `--audio`), and stops when `--done` appears in the terminal output.
`--type LINE` (repeatable) types command lines into the terminal, each after
the previous `[DONE]` / `[CMD] rejected` ("!LINE": don't wait for it to finish;
"&2.5 LINE": wait 2.5 s, then type — e.g. a stop while a program runs); `--interactive` instead waits for the
person at the keyboard (they type `v` + ENTER and speak) until ENTER is pressed
in the shell that runs this script.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from eval.e2e import stage as stg  # noqa: E402
from eval.e2e.stage import Stage, grab_frame, video_duration  # noqa: E402

END = r"\[DONE\]|\[CMD\] rejected"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--command", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--display", default=":1")
    ap.add_argument("--geom", required=True, help="monitor WxH+X+Y from xrandr --listmonitors")
    ap.add_argument("--ready", default=r"Type an English command")
    ap.add_argument("--done", default=None)
    ap.add_argument("--type", action="append", default=[], help="line to type (repeatable)")
    ap.add_argument("--interactive", action="store_true")
    ap.add_argument("--audio", action="store_true", help="also record the default microphone")
    ap.add_argument("--term-h", type=int, default=None)
    ap.add_argument("--font", type=int, default=15)
    ap.add_argument("--timeout", type=float, default=600)
    ap.add_argument("--log", default=None)
    ap.add_argument("--no-panel", action="store_true")
    args = ap.parse_args()
    stg.set_geometry(args.geom)
    out = Path(args.out).expanduser()
    log = Path(args.log or out.with_suffix(".terminal.log"))
    st = Stage(args.display, font_size=args.font, term_h=args.term_h)
    try:
        st.open_terminal(args.command, log, title="demo")
        if st.wait_for(args.ready, 150) is None:
            raise SystemExit("never became ready")
        if not args.no_panel:
            st.open_panel(timeout=40)
        time.sleep(1.0)
        # test frame: only project windows must be visible
        test = out.with_suffix(".testframe.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "x11grab", "-video_size",
                        f"{stg.WIDTH}x{stg.HEIGHT}", "-i", f"{args.display}+{stg.OX},{stg.OY}",
                        "-frames:v", "1", str(test)], check=False)
        print(f"[REC] test frame: {test}", flush=True)
        if args.audio:
            st.start_recording_av(out)
        else:
            st.start_recording(out, fps=30)
        t0 = time.time()
        time.sleep(1.0)
        for line in args.type:
            if line.startswith("!"):          # type, don't wait (e.g. a program to stop)
                st.type_line(line[1:])
                st.wait_for(r"\[(REPEAT|MOVE|EXEC)\]", 30)
                continue
            if line.startswith("&"):          # "&<s> text": wait <s> seconds, then type
                delay, _, line = line[1:].partition(" ")
                time.sleep(float(delay))
            st.type_line(line)
            st.wait_for(END, 300)
            st.wait_for(r"^\0never$", 2.5)
        if args.interactive:
            input("[REC] recording — speak your segment in the demo terminal; press ENTER here to stop: ")
        elif args.done:
            st.wait_for(args.done, args.timeout)
            time.sleep(2.0)
        else:
            time.sleep(2.0)
        print(f"[REC] {time.time() - t0:.1f} s recorded", flush=True)
    finally:
        st.stop_recording()
        st.close()
        held = stg.held_keys(args.display)
        if held is not None:
            print(f"[REC] keys held on {args.display} after close: {held}", flush=True)
    d = video_duration(out)
    grab_frame(out, max(d - 1.5, 0.5), out.with_suffix(".lastframe.jpg"), scale="1280:720")
    print(f"[REC] wrote {out} ({d:.1f} s)", flush=True)


if __name__ == "__main__":
    main()
