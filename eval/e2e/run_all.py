# Owner: Student B (Task 3 + bonuses)
"""
eval/e2e/run_all.py — Student B. End-to-end harness on the real sim.

    eval/run_env.sh eval/e2e/run_all.py --suites S1 S2 S3 S4 [S5] --label baseline
        [--s3-path main|driver] [--no-video] [--only S3_03 ...]

Each scenario starts from a fresh sim launch at a defined start pose, runs on
the virtual display (eval/e2e/stage.py), and — unless --no-video — is recorded
as its own clip in ~/Videos/e2e/<run>/<suite>_<scenario>.mp4 (never in the
repo). Results go to eval/e2e/results/<run>/:
    summary.md            per-suite tables (clip name in each row)
    <scenario>.log        the demo terminal's output
    <scenario>.trace.jsonl  ground-truth pose/tilt/contacts (logging only)
    results.jsonl         one record per scenario
    frames/<scenario>.jpg  the verified frame of each clip

Suites
  S1 Task 2   closed-loop turns 45/90/180 x3, A's open-loop timed turns x3,
              one timed 3 s move (driver eval/e2e/drivers/s1_task2.py).
  S2 Task 3   the Video_Task3 a-g script typed into `main.py --gui`.
              Pass = expected [CMD] lines, every turn within 2 deg, no
              contact or fall.
  S3 Task 4   Student C's 10 scenarios, each a typed utterance through
              parse_command -> executor -> navigation.goto_object.
              Success = [MISSION] SUCCESS and true d <= 0.80 m and C1.
  S4 Bonus    3 look questions at fixed poses + the 2-goal mission.
  S5 B upgrades (b/upgrade): programs, return home, status, stop, ...
The real LLM (config.LLM_SERVICE, qwen-flash) is used throughout.
"""

import argparse
import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from eval.e2e.stage import (Stage, ensure_xvfb, grab_frame,  # noqa: E402
                            video_duration)

RESULTS = ROOT / "eval" / "e2e" / "results"
VIDEOS = Path.home() / "Videos" / "e2e"
PROMPT_READY = r"Type an English command"
CMD_END = r"\[DONE\]|\[CMD\] rejected"
FALL_Z = 0.20          # trunk height (m) below which we call it a fall
FALL_TILT = 45.0       # roll/pitch (deg) beyond which we call it a fall


@dataclass
class Step:
    text: str
    wait: str = CMD_END
    timeout: float = 90.0
    expect: Optional[str] = None      # regex the [CMD]/reject line must match


@dataclass
class Scenario:
    suite: str
    name: str
    launch: str
    steps: List[Step] = field(default_factory=list)
    ready: str = PROMPT_READY
    driver_done: Optional[str] = None  # driver scenarios: wait for this line
    driver_timeout: float = 240.0
    meta: dict = field(default_factory=dict)

    @property
    def sid(self) -> str:
        return f"{self.suite}_{self.name}"


# ---------------------------------------------------------------------------
# Suite definitions
# ---------------------------------------------------------------------------

def suite_s1() -> List[Scenario]:
    d = "eval/run_env.sh eval/e2e/drivers/s1_task2.py --gui --mode {}"
    return [Scenario("S1", m, d.format(m), ready=r"\[S1\] ready",
                     driver_done=r"\[S1\] done", driver_timeout=300)
            for m in ("closed", "open", "move")]


S2_SCRIPT = [
    ("a", "turn left 90 degrees", r"\[CMD\] actions=turn\(90 deg\) n=1$"),
    ("b", "walk forward for three seconds, then turn back",
     r"\[CMD\] actions=move\(vx=0\.8, 3\.0 s\), turn\(180 deg\) n=2$"),
    ("c", "walk forward for two seconds, then turn right 90 degrees",
     r"\[CMD\] actions=move\(vx=0\.8, 2\.0 s\), turn\(-90 deg\) n=2$"),
    ("d", "sidestep to your left for two seconds",
     r"\[CMD\] actions=move\(vx=0, vy=0\.8, 2\.0 s\) n=1$"),
    ("e", "do that again, but slower",
     r"\[CMD\] actions=move\(vx=0, vy=0\.[2-5]\d*, 2\.0 s\) n=1$"),
    ("f", "fly to the roof", r"\[CMD\] rejected reason=impossible:"),
    ("g", "avancez tout droit", r"\[CMD\] rejected reason=non-English$"),
]


def suite_s2() -> List[Scenario]:
    return [Scenario("S2", "video_task3", "eval/run_env.sh main.py --gui",
                     steps=[Step(t, expect=e, timeout=60) for _, t, e in S2_SCRIPT])]


# scenario idx -> (target key, typed utterance, paraphrase?, expected outcome)
S3_TABLE = {
    1: ("red_chair", "go to the red chair", False, "SUCCESS"),
    2: ("orange_sports ball", "find the orange ball", True, "SUCCESS"),
    3: ("green_chair", "go to the green chair", False, "SUCCESS"),
    4: ("red_chair", "walk over to the red chair", True, "SUCCESS"),
    5: ("yellow_stop sign", "go to the yellow stop sign", False, "SUCCESS"),
    6: ("green_stop sign", "go to the green stop sign", False, "SUCCESS"),
    7: ("orange_sports ball", "please head over to the orange ball", True, "SUCCESS"),
    8: ("blue_chair", "go to the blue chair", False, "SUCCESS"),
    9: ("red_stop sign", "go to the red stop sign", False, "SUCCESS"),
    10: ("blue_chair", "go to the blue chair", False, "FAIL:target_not_found"),
}


def suite_s3(path: str) -> List[Scenario]:
    out = []
    for idx, (key, text, para, expected) in S3_TABLE.items():
        if path == "main":
            launch = f"eval/run_env.sh main.py --gui --scenario {idx}"
        else:
            launch = f"eval/run_env.sh eval/e2e/drivers/scenario_main.py --gui --scenario {idx}"
        out.append(Scenario("S3", f"{idx:02d}", launch,
                            steps=[Step(text, timeout=170)],
                            meta={"scenario": idx, "target": key, "paraphrase": para,
                                  "expected": expected}))
    return out


def suite_s4() -> List[Scenario]:
    look = [Step("turn around", timeout=60),
            Step("what can you see?", timeout=60),
            Step("turn right 45 degrees", timeout=60),
            Step("is there a chair in front of you?", timeout=60),
            Step("turn left 90 degrees", timeout=60),
            Step("what colour is the ball ahead?", timeout=60)]
    mission = [Step("go to the red chair, then the orange ball", timeout=300)]
    return [Scenario("S4", "look", "eval/run_env.sh main.py --gui", steps=look),
            Scenario("S4", "multigoal", "eval/run_env.sh main.py --gui", steps=mission)]


# S5 (b/upgrade). Moves are chosen to stay on the clear floor: the robot spawns
# at the origin facing +x and the rough-terrain track starts at x ~ 1.5 m, so
# walking programs either turn left first (clear strip along +y) or stay in
# x in [0, 1]. The non-English case is typed in Spanish: xdotool can't type
# CJK into the xterm reliably (Mandarin is covered offline and by speech).
S5_STEPS = [
    ("until_see", ["keep turning until you see the orange ball, then go to it",
                   "what have you seen?"], 300),
    # facing +y first: a square from the spawn heading (+x) brushes the low
    # terrain pieces at x ~ 1.0-1.3 m (S5 dry run, trace contacts)
    ("square", ["turn left 90 degrees", "walk in a square with 1 meter sides"], 150),
    ("return_home", ["turn left 90 degrees, then walk forward for two seconds",
                     "go back to where you started",
                     "how far are you from the start?"], 120),
    ("status", ["turn left 90 degrees", "what did you just do?"], 60),
    ("estop", None, 60),
    ("non_english", ["gira a la izquierda noventa grados", "turn left 90 degrees"], 60),
    ("out_of_range", ["walk forward for a hundred meters", "why did you reject that?"], 60),
    # turns > 180 deg are split into <= 120 deg chunks (RealSkills.turn goes the short way)
    ("spin", ["spin around twice"], 90),
]


def suite_s5() -> List[Scenario]:
    out = []
    for name, texts, to in S5_STEPS:
        if name == "estop":
            # "stop" is typed while the program is still walking.
            steps = [Step("walk forward 1 meter and back 1 meter, three times",
                          wait=r"\[(MOVE|REPEAT)\]|\[EXEC\] action=1/", timeout=40),
                     Step("stop", wait=r"\[DONE\]", timeout=30),
                     Step("what did you just do?", timeout=40)]
        else:
            steps = [Step(t, timeout=to) for t in texts]
        out.append(Scenario("S5", name, "eval/run_env.sh main.py --gui", steps=steps))
    return out


# S7: the blue chair on the stairs (default scene) through Student C's own
# sequence, tools/visual_test_blue_chair_stairs.py: walk to the stairs, detect,
# climb, then navigation.goto_object for the final approach. No LLM.
def suite_s7() -> List[Scenario]:
    return [Scenario("S7", "blue_chair_stairs",
                     "eval/run_env.sh tools/visual_test_blue_chair_stairs.py",
                     ready=r"Booting RealSkills",
                     driver_done=r"goto_object returned success=|\[MISSION\] status=FAIL reason=(approach|climb)_",
                     driver_timeout=420)]


# ---------------------------------------------------------------------------
# Running one scenario
# ---------------------------------------------------------------------------

class Run:
    def __init__(self, label: str, video: bool, display: str):
        self.stamp = time.strftime("%Y%m%d-%H%M") + f"_{label}"
        self.dir = RESULTS / self.stamp
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "frames").mkdir(exist_ok=True)
        self.vdir = VIDEOS / self.stamp
        self.video = video
        self.display = display
        self.records = []
        self.crashes_in_a_row = 0

    def run(self, sc: Scenario) -> dict:
        log = self.dir / f"{sc.sid}.log"
        trace = self.dir / f"{sc.sid}.trace.jsonl"
        trace.write_text("")
        clip = self.vdir / f"{sc.sid}.mp4" if self.video else None
        lines: List[tuple] = []
        rec = {"suite": sc.suite, "scenario": sc.name, "launch": sc.launch,
               "clip": str(clip.relative_to(VIDEOS)) if clip else None,
               "meta": sc.meta, "steps": [], "crash": False}
        st = Stage(self.display, font_size=getattr(self, "font", 12))
        t_start = time.time()
        try:
            st.open_terminal(sc.launch, log, title=f"demo {sc.sid}",
                             env={"E2E_TRACE_FILE": str(trace)})
            ok = st.wait_for(sc.ready, 150, on_line=lambda l: lines.append((time.time(), l)))
            if ok is None:
                rec["crash"] = True
                rec["error"] = "never became ready"
                return rec
            st.open_panel(timeout=40)
            if clip:
                st.start_recording(clip)
                time.sleep(1.5)
            if sc.driver_done:
                done = st.wait_for(sc.driver_done, sc.driver_timeout,
                                   on_line=lambda l: lines.append((time.time(), l)))
                rec["steps"].append({"text": None, "done": bool(done)})
                if done is None:
                    rec["crash"] = "Traceback" in st.full_log()
            for step in sc.steps:
                t0 = time.time()
                lines.append((t0, f"### >>> typed: {step.text}"))
                st.type_line(step.text)
                end = st.wait_for(step.wait, step.timeout,
                                  on_line=lambda l: lines.append((time.time(), l)))
                rec["steps"].append({"text": step.text, "t_typed": t0,
                                     "t_end": time.time(), "end_line": end,
                                     "timed_out": end is None})
                if end is None and st.term and st.term.poll() is not None:
                    rec["crash"] = True
                    break
                # let trailing lines ([MULTI], Robot: summary) arrive
                st.wait_for(r"^\0never$", 1.5, on_line=lambda l: lines.append((time.time(), l)))
            st.wait_for(r"^\0never$", 2.0, on_line=lambda l: lines.append((time.time(), l)))
        finally:
            st.close()
        rec["wall_s"] = round(time.time() - t_start, 1)
        full = log.read_text(errors="replace") if log.exists() else ""
        if "Traceback" in full and not _only_shutdown_tracebacks(full):
            rec["traceback"] = True
        rec["lines"] = [(round(t, 2), l) for t, l in lines]
        rec["trace"] = _read_trace(trace)
        if clip and clip.exists():
            rec["frame"] = self._verify_clip(clip, sc)
        return rec

    def _verify_clip(self, clip: Path, sc: Scenario) -> dict:
        dur = video_duration(clip)
        out = self.dir / "frames" / f"{sc.sid}.jpg"
        ok = grab_frame(clip, max(dur - 1.5, 0.5), out, scale="960:540")
        info = {"duration_s": round(dur, 1), "frame": str(out.relative_to(ROOT)) if ok else None}
        if ok:
            info.update(_frame_check(out))
        if not ok or not info.get("ok"):
            info["deleted"] = True
            try:
                clip.unlink()
            except OSError:
                pass
        return info


def _only_shutdown_tracebacks(text: str) -> bool:
    """Ctrl+C at teardown prints KeyboardInterrupt + EGL clean-up tracebacks."""
    blocks = text.split("Traceback (most recent call last):")[1:]
    return all(("KeyboardInterrupt" in b or "EGL" in b or "glCheckError" in b) for b in blocks)


def _read_trace(path: Path) -> List[dict]:
    out = []
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "x" in r:
                out.append(r)
    return out


def _frame_check(img: Path) -> dict:
    """Automatic check of the verified frame: the terminal half has text
    (bright pixels on black) and the panel half is a rendered page."""
    import numpy as np
    from PIL import Image
    a = np.asarray(Image.open(img).convert("L"), dtype=np.float32)
    h, w = a.shape
    term, panel = a[:, : w // 2], a[:, w // 2:]
    term_text = float((term > 150).mean())
    panel_std = float(panel.std())
    ok = 0.002 < term_text < 0.5 and panel_std > 15
    return {"ok": ok, "term_text_frac": round(term_text, 4), "panel_std": round(panel_std, 1)}


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def _classify_contacts(trace: List[dict], objects: dict, target: Optional[str]) -> dict:
    """F5 (logging only): count trace samples in contact with the target, with
    another scene object, or with terrain, by matching each contacted body's
    world xy to the scenario's object positions (within 0.35 m)."""
    out = {"target": 0, "objects": 0, "terrain": 0, "objects_hit": []}
    hit = set()
    for r in trace:
        kinds = set()
        for name, xy in (r.get("contact_xy") or {}).items():
            best = min(objects.items(), key=lambda kv: math.hypot(kv[1][0] - xy[0], kv[1][1] - xy[1]),
                       default=None)
            if best and math.hypot(best[1][0] - xy[0], best[1][1] - xy[1]) <= 0.35:
                kinds.add("target" if best[0] == target else "objects")
                hit.add(best[0])
            else:
                kinds.add("terrain")
        if not r.get("contact_xy") and r.get("contacts"):
            kinds.add("terrain")       # old traces without body xy
        for k in kinds:
            out[k] += 1
    out["objects_hit"] = sorted(hit)
    return out


def _trace_checks(trace: List[dict]) -> dict:
    if not trace:
        return {"trace": False}
    contacts = sorted({c for r in trace for c in r.get("contacts", [])})
    fall = any(r["z"] < FALL_Z or abs(r["roll"]) > FALL_TILT or abs(r["pitch"]) > FALL_TILT
               for r in trace)
    max_tilt = max(max(abs(r["roll"]), abs(r["pitch"])) for r in trace)
    return {"trace": True, "contacts": contacts, "fall": fall, "max_tilt_deg": round(max_tilt, 1)}


def _pose_at(trace: List[dict], t: float) -> Optional[dict]:
    best = None
    for r in trace:
        if r["t"] <= t:
            best = r
        else:
            break
    return best


def evaluate(rec: dict) -> dict:
    suite = rec["suite"]
    lines = [l for _, l in rec.get("lines", [])]
    ev = _trace_checks(rec.get("trace", []))
    if rec.get("crash"):
        ev["pass"] = False
        ev["why"] = rec.get("error", "crash")
        return ev
    if suite == "S1":
        rows = [l for l in lines if "[S1] mode=" in l]
        errs = [float(m.group(1)) for l in rows if (m := re.search(r"error=([+-][\d.]+)", l))]
        ev["rows"] = rows
        if rec["scenario"] == "closed":
            ev["max_abs_error"] = round(max(map(abs, errs)), 1) if errs else None
            ev["pass"] = bool(errs) and len(errs) == 9 and max(map(abs, errs)) <= 2.0
        elif rec["scenario"] == "open":
            ev["mean_abs_error"] = round(sum(map(abs, errs)) / len(errs), 1) if errs else None
            ev["pass"] = len(errs) == 9          # informational: recorded, not judged
        else:
            m = next((re.search(r"distance=([\d.]+)", l) for l in rows), None)
            ev["distance_m"] = float(m.group(1)) if m else None
            ev["pass"] = m is not None and not ev.get("fall", False)
        return ev
    if suite == "S2":
        cmd_lines = [re.sub(r"^(User: )+", "", l) for l in lines if "[CMD]" in l]
        got, ok_all = [], True
        for (tag, text, expect) in S2_SCRIPT:
            match = next((c for c in cmd_lines if re.search(expect, c)), None)
            got.append({"step": tag, "text": text, "ok": match is not None,
                        "line": match})
            ok_all &= match is not None
        turns = [float(m.group(1)) for l in lines
                 if (m := re.search(r"\[TURN\] target=[-\d.]+ deg final_error=(-?[\d.]+)", l))]
        ev.update(cmd=got, turn_errors=turns,
                  turns_ok=bool(turns) and all(abs(e) <= 2.0 for e in turns))
        ev["pass"] = ok_all and ev["turns_ok"] and not ev.get("fall") and not ev.get("contacts")
        return ev
    if suite == "S3":
        return _eval_s3(rec, lines, ev)
    if suite == "S4":
        if rec["scenario"] == "look":
            # the VLM answer is the Robot: line right after each [VLM] line
            # (b/upgrade also prints talk-back "Robot: Done: ..." after turns)
            answers = [lines[i + 1].split("Robot: ", 1)[1] for i, l in enumerate(lines[:-1])
                       if "[VLM]" in l and "Robot: " in lines[i + 1]]
            frames = [m.group(1) for l in lines if (m := re.search(r"\[VLM\].* frame=(\S+)", l))]
            ev.update(answers=answers, frames=frames, n_answers=len(answers))
            ev["pass"] = len(answers) == 3          # correctness judged by hand in summary.md
        else:
            multi = next((l for l in lines if "[MULTI]" in l), None)
            founds = [l for l in lines if "[FOUND]" in l]
            ev.update(multi=multi, found=founds)
            ev["pass"] = bool(multi and "status=SUCCESS" in multi)
            ds = [float(m.group(1)) for l in founds if (m := re.search(r" d=([\d.]+) m", l))]
            ev["true_d_at_stops"] = ds
            ev["strict_c2"] = bool(ds) and all(d <= 0.80 for d in ds)
        return ev
    if suite == "S5":
        return _eval_s5(rec, lines, ev)
    if suite == "S7":
        clean = [re.sub(r"^(User: )+", "", l) for l in lines]
        rng = [m.groups() for l in clean
               if (m := re.search(r"\[RANGE\] .*estimated_planar=([\d.]+) m ground_truth=([\d.]+) m(?: phase=(\w+))?", l))]
        mission = next((l for l in clean if l.startswith("[MISSION]")), None)
        found = next((l for l in clean if l.startswith("[FOUND]")), None)
        d = float(m.group(1)) if found and (m := re.search(r" d=([\d.]+) m", found)) else None
        errs = [round(float(gt) - float(est), 2) for est, gt, _ in rng]
        ev.update(mission=mission, found=found, true_d=d, range_pairs=len(rng),
                  err_first=errs[0] if errs else None, err_last=errs[-1] if errs else None,
                  err_mean=round(sum(errs) / len(errs), 2) if errs else None,
                  climb=next((l.strip() for l in clean if "climb outcome=" in l), None))
        ev["pass"] = bool(mission and "SUCCESS" in mission and d is not None and d <= 0.80)
        return ev
    return ev


def _eval_s5(rec: dict, lines: List[str], ev: dict) -> dict:
    """Automatic checks for the B-upgrade scenarios (ground truth = trace, logging only)."""
    name = rec["scenario"]
    clean = [re.sub(r"^(User: )+", "", l) for l in lines]
    ev["key_lines"] = [l for l in clean if re.search(
        r"^\[(CMD|PLAN|MOVE|REPEAT|UNTIL|ESTOP|MULTI|FOUND|MISSION|DONE|GOAL)\]|^Robot: |^### >>>", l)]
    tr = rec.get("trace") or []
    start = tr[0] if tr else None
    end = tr[-1] if tr else None
    dist_home = (math.hypot(end["x"] - start["x"], end["y"] - start["y"]) if tr else None)
    robot = [l for l in clean if l.startswith("Robot: ")]
    has = lambda pat: any(re.search(pat, l) for l in clean)
    checks = {}
    if name == "until_see":
        checks = {"until_line": has(r"^\[UNTIL\]"), "found_ball": has(r"^\[FOUND\] class=sports ball"),
                  "mission_success": has(r"^\[MISSION\] status=SUCCESS"), "summary": len(robot) >= 2}
    elif name == "square":
        moves = [l for l in clean if l.startswith("[MOVE]")]
        checks = {"plan": has(r"^\[PLAN\]"), "four_sides": len(moves) >= 4,
                  "closed_back_within_0.5m": dist_home is not None and dist_home <= 0.5,
                  "summary": bool(robot)}
        ev["moves"] = moves
    elif name == "return_home":
        checks = {"plan": has(r"^\[PLAN\]"), "home_within_0.3m": dist_home is not None and dist_home <= 0.3,
                  "status_answer": len(robot) >= 3}
    elif name == "status":
        checks = {"answer_mentions_turn": any("turn" in l.lower() for l in robot[1:])}
    elif name == "estop":
        m = next((re.search(r"\[ESTOP\] latency=([\d.]+) ms", l) for l in clean if "[ESTOP]" in l), None)
        ev["estop_latency_ms"] = float(m.group(1)) if m else None
        checks = {"estop_line": m is not None, "no_llm_for_stop": not any(
            "### >>> typed: stop" in l for l in clean) or not has(r"^\[CMD\] actions=stop")}
    elif name == "non_english":
        checks = {"rejected_non_english": has(r"^\[CMD\] rejected reason=non-English"),
                  "suggestion": any("Did you mean" in l for l in robot),
                  # the redirect is parsed as turn(90 deg); since F3 it runs as 45-deg chunks
                  "redirect_turned": has(r"^\[CMD\] actions=turn\(90 deg\) n=1") and has(r"^\[TURN\] ")}
    elif name == "spin":
        yaws = [r["yaw"] for r in tr]
        total = 0.0
        for a, b in zip(yaws, yaws[1:]):
            total += (b - a + 180.0) % 360.0 - 180.0
        ev["total_rotation_deg"] = round(total, 1)
        turns = [l for l in clean if l.startswith("[TURN]")]
        checks = {"chunked_turns": len(turns) >= 6, "rotated_~720": abs(abs(total) - 720.0) <= 30.0}
    elif name == "out_of_range":
        checks = {"rejected_out_of_range": has(r"^\[CMD\] rejected reason=out_of_range"),
                  "suggestion": len(robot) >= 1, "why_answer": len(robot) >= 2}
    ev["checks"] = checks
    ev["dist_end_from_start_m"] = round(dist_home, 2) if dist_home is not None else None
    ev["pass"] = bool(checks) and all(checks.values()) and not ev.get("fall")
    return ev


def _eval_s3(rec: dict, lines: List[str], ev: dict) -> dict:
    from perception import scenarios
    meta = rec["meta"]
    sc = scenarios.get_scenario(str(meta["scenario"]))
    key = meta["target"]
    color, cls = key.split("_", 1)
    objs = {o.key: (o.x, o.y) for o in sc.objects}
    scene_pairs = {(o.cls, o.color) for o in sc.objects}
    cmd = next((re.sub(r"^(User: )+", "", l) for l in lines if "[CMD] actions=" in l), None)
    rejected = next((l for l in lines if "[CMD] rejected" in l), None)
    detects = [m.groups() for l in lines
               if (m := re.search(r"\[DETECT\] class=(.+?) color=(\S+) conf", l))]
    relevant = [(c, col) for c, col in detects if c in scenarios.SUPPORTED_CLASSES]
    correct = [p for p in relevant if p in scene_pairs]
    target_seen = sum(1 for p in relevant if p == (cls, color))
    mission = next((l for l in lines if re.match(r"^(User: )*\[MISSION\] status=", l)), None)
    found = next((l for l in lines if re.match(r"^(User: )*\[FOUND\] ", l)), None)
    stop_check = [l for l in lines if "phase=stop_check" in l]
    done = next((l for l in lines if "[DONE]" in l), None)
    t = None
    if done and (m := re.search(r"t=([\d.]+) s", done)):
        t = float(m.group(1))
    # true distance at the stop: last trace pose (ground truth, logging only)
    true_d = None
    tr = rec.get("trace") or []
    if tr and key in objs:
        end_t = max((s.get("t_end") or 0) for s in rec["steps"]) if rec["steps"] else tr[-1]["t"]
        p = _pose_at(tr, end_t) or tr[-1]
        ox, oy = objs[key]
        true_d = round(math.hypot(p["x"] - ox, p["y"] - oy), 2)
    est_stop = None
    if stop_check and (m := re.search(r"estimated_planar=([\d.]+)", stop_check[-1])):
        est_stop = float(m.group(1))
    status = None
    if mission:
        status = "SUCCESS" if "status=SUCCESS" in mission else "FAIL:" + (
            re.search(r"reason=(\S+)", mission).group(1) if "reason=" in mission else "?")
    c1 = bool(stop_check) or bool(found)
    c2_est = est_stop is not None and est_stop <= 0.80
    c3 = bool(found)
    if meta["expected"].startswith("FAIL"):
        success = status == meta["expected"]
    else:
        success = status == "SUCCESS" and true_d is not None and true_d <= 0.80 and c1
    ev["contact_classes"] = _classify_contacts(rec.get("trace") or [], objs, key)
    ev.update(cmd=cmd, rejected=rejected,
              search=any("[SEARCH]" in l for l in lines),
              detect_total=len(relevant), detect_correct=len(correct),
              target_detections=target_seen, mission=status, found=found,
              time_s=t, true_d=true_d, est_d_stop=est_stop,
              C1=c1, C2_est=c2_est, C2_true=(true_d is not None and true_d <= 0.80), C3=c3,
              pass_=success)
    ev["pass"] = success
    return ev


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _yn(v):
    return "✅" if v else ("❌" if v is not None else "–")


def write_summary(run: Run, records: List[dict]) -> Path:
    out = [f"# e2e run `{run.stamp}`", "",
           f"Commit: `{_git('rev-parse', '--short', 'HEAD')}` on `{_git('branch', '--show-current')}`. "
           f"LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/{run.stamp}/` "
           f"({'recorded' if run.video else 'not recorded'}).", ""]
    by = {}
    for r in records:
        by.setdefault(r["suite"], []).append(r)
    if "S1" in by:
        out += ["## S1 — Task 2 skills", "",
                "| Scenario | Result | Pass | Fall / contacts | Clip |", "|---|---|---|---|---|"]
        for r in by["S1"]:
            e = r["eval"]
            res = {"closed": f"max \\|error\\| {e.get('max_abs_error')}°",
                   "open": f"mean \\|error\\| {e.get('mean_abs_error')}°",
                   "move": f"distance {e.get('distance_m')} m"}[r["scenario"]]
            out.append(f"| {r['scenario']} | {res} | {_yn(e.get('pass'))} | "
                       f"{_yn(not e.get('fall'))} fall, {len(e.get('contacts', []))} contacts | {_clip(r)} |")
        out.append("")
        for r in by["S1"]:
            out += ["```"] + r["eval"].get("rows", []) + ["```"]
        out.append("")
    if "S2" in by:
        for r in by["S2"]:
            e = r["eval"]
            out += ["## S2 — Task 3 (Video_Task3 script a–g, typed into main.py)", "",
                    f"Pass: {_yn(e.get('pass'))} · turn errors {e.get('turn_errors')} · "
                    f"fall {_yn(not e.get('fall'))} · contacts {e.get('contacts') or 'none'} · "
                    f"max tilt {e.get('max_tilt_deg')}° · clip {_clip(r)}", "",
                    "| Step | Typed | [CMD] line | OK |", "|---|---|---|---|"]
            for c in e.get("cmd", []):
                out.append(f"| {c['step']} | `{c['text']}` | `{c['line']}` | {_yn(c['ok'])} |")
            out.append("")
    if "S3" in by:
        out += ["## S3 — Task 4 (C's 10 scenarios, typed utterance)", "",
                "Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: "
                "the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.", "",
                "| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Contacts (target / other objects / terrain, samples) | Clip |",
                "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        n_ok = 0
        for r in by["S3"]:
            e = r["eval"]
            n_ok += bool(e.get("pass"))
            para = " (paraphrase)" if r["meta"].get("paraphrase") else ""
            out.append(
                f"| {r['scenario']} | `{r['steps'][0]['text'] if r['steps'] else ''}`{para} | "
                f"{_yn(bool(e.get('cmd')) and not e.get('rejected'))} | {_yn(e.get('search'))} | "
                f"{e.get('detect_correct')}/{e.get('detect_total')} (target {e.get('target_detections')}) | "
                f"{e.get('mission')} | {e.get('time_s')} | {e.get('est_d_stop')} | {e.get('true_d')} | "
                f"{_yn(e.get('C1'))} | {_yn(e.get('C2_est'))} | {_yn(e.get('C2_true'))} | "
                f"{_yn(e.get('C3'))} | {_yn(e.get('pass'))} | {_cc(e)} | {_clip(r)} |")
        tgt_hits = sum(1 for r in by["S3"] if (r["eval"].get("contact_classes") or {}).get("target"))
        out += ["", f"**S3 success: {n_ok}/{len(by['S3'])}** · runs with target contact: {tgt_hits}", ""]
    if "S4" in by:
        out += ["## S4 — Bonus", ""]
        for r in by["S4"]:
            e = r["eval"]
            if r["scenario"] == "look":
                out += [f"Look (clip {_clip(r)}): VLM answers (correctness checked by hand against the frames):", ""]
                for q, a, f in zip(["what can you see? (after turn around)",
                                    "is there a chair in front of you? (after turn right 45)",
                                    "what colour is the ball ahead? (after turn left 90)"],
                                   e.get("answers", []) + [""] * 3, e.get("frames", []) + [""] * 3):
                    out.append(f"- **{q}** → {a} (`{f}`)")
                out.append("")
            else:
                out += [f"Multi-goal (clip {_clip(r)}): `{e.get('multi')}` · true d at stops "
                        f"{e.get('true_d_at_stops')} · strict C2 {_yn(e.get('strict_c2'))}", ""]
    if "S5" in by:
        out += ["## S5 — B upgrades (typed into main.py)", "",
                "| Scenario | Checks | Pass | Fall / contacts | Clip |", "|---|---|---|---|---|"]
        for r in by["S5"]:
            e = r["eval"]
            chk = ", ".join(f"{k} {_yn(v)}" for k, v in (e.get("checks") or {}).items())
            if e.get("estop_latency_ms") is not None:
                chk += f", latency {e['estop_latency_ms']} ms"
            if e.get("total_rotation_deg") is not None:
                chk += f", rotated {e['total_rotation_deg']}°"
            out.append(f"| {r['scenario']} | {chk} | {_yn(e.get('pass'))} | "
                       f"{_yn(not e.get('fall'))} fall, {len(e.get('contacts', []))} contacts | {_clip(r)} |")
        out.append("")
        for r in by["S5"]:
            out += [f"### {r['scenario']}", "", "```"] + r["eval"].get("key_lines", [])[:40] + ["```", ""]
    if "S7" in by:
        out += ["## S7 — blue chair on the stairs (C's stairs sequence, default scene)", "",
                "| Mission | [FOUND] | true d | range pairs | true − est (first / last / mean) | Climb | Pass | Clip |",
                "|---|---|---|---|---|---|---|---|"]
        for r in by["S7"]:
            e = r["eval"]
            out.append(f"| `{e.get('mission')}` | `{e.get('found')}` | {e.get('true_d')} | {e.get('range_pairs')} | "
                       f"{e.get('err_first')} / {e.get('err_last')} / {e.get('err_mean')} | `{e.get('climb')}` | "
                       f"{_yn(e.get('pass'))} | {_clip(r)} |")
        out.append("")
    crashed = [r["suite"] + "_" + r["scenario"] for r in records if r.get("crash")]
    deleted = [r["suite"] + "_" + r["scenario"] for r in records if (r.get("frame") or {}).get("deleted")]
    out += ["## Run notes", "",
            f"- Crashed / never ready: {crashed or 'none'}",
            f"- Clips deleted by the frame check: {deleted or 'none'}", ""]
    path = run.dir / "summary.md"
    path.write_text("\n".join(out))
    return path


def _cc(e):
    c = e.get("contact_classes") or {}
    if not c:
        return "–"
    hit = f" ({', '.join(c.get('objects_hit', []))})" if c.get("objects_hit") else ""
    return f"{c.get('target', 0)} / {c.get('objects', 0)} / {c.get('terrain', 0)}{hit}"


def _clip(r):
    if not r.get("clip"):
        return "–"
    if (r.get("frame") or {}).get("deleted"):
        return f"~~{r['clip']}~~ (failed frame check)"
    return f"`{r['clip']}`"


def _git(*args):
    import subprocess
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def reeval(run_dir: Path) -> None:
    """Re-score a finished run from results.jsonl + the trace files (no sim)."""
    run = Run.__new__(Run)
    run.stamp, run.dir, run.video = run_dir.name, run_dir, True
    records = []
    for line in (run_dir / "results.jsonl").read_text().splitlines():
        rec = json.loads(line)
        rec["trace"] = _read_trace(run_dir / f"{rec['suite']}_{rec['scenario']}.trace.jsonl")
        rec["eval"] = evaluate(rec)
        records.append(rec)
    with (run_dir / "results.jsonl").open("w") as jf:
        for rec in records:
            jf.write(json.dumps({k: v for k, v in rec.items() if k != "trace"}, default=str) + "\n")
    print(f"[E2E] re-scored: {write_summary(run, records)}")


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suites", nargs="+", default=["S1", "S2", "S3", "S4"])
    ap.add_argument("--label", default="run")
    ap.add_argument("--s3-path", choices=("main", "driver"), default="main")
    ap.add_argument("--no-video", action="store_true")
    ap.add_argument("--only", nargs="*", default=None, help="scenario ids, e.g. S3_03")
    ap.add_argument("--display", default=":99")
    ap.add_argument("--geom", default=None, help="record WxH+X+Y of the X screen (one monitor)")
    ap.add_argument("--font", type=int, default=12)
    ap.add_argument("--reeval", metavar="RUN_DIR", help="re-score a finished run offline")
    args = ap.parse_args()
    if args.reeval:
        reeval(Path(args.reeval))
        return

    if args.geom:
        from eval.e2e import stage as _stage
        _stage.set_geometry(args.geom)
    if args.display == ":99":
        ensure_xvfb(args.display)
    run = Run(args.label, not args.no_video, args.display)
    run.font = args.font
    scen: List[Scenario] = []
    for s in args.suites:
        scen += {"S1": suite_s1, "S2": suite_s2, "S3": lambda: suite_s3(args.s3_path),
                 "S4": suite_s4, "S5": suite_s5, "S7": suite_s7}[s]()
    if args.only:
        scen = [s for s in scen if s.sid in args.only]
    print(f"[E2E] run {run.stamp}: {len(scen)} scenarios -> {run.dir}", flush=True)
    records = []
    with (run.dir / "results.jsonl").open("a") as jf:
        for sc in scen:
            if run.crashes_in_a_row >= 3:
                print(f"[E2E] 3 crashes in a row: skipping {sc.sid}", flush=True)
                continue
            print(f"[E2E] {sc.sid}: {sc.launch}", flush=True)
            rec = run.run(sc)
            rec["eval"] = evaluate(rec)
            run.crashes_in_a_row = run.crashes_in_a_row + 1 if rec.get("crash") else 0
            slim = {k: v for k, v in rec.items() if k not in ("trace",)}
            jf.write(json.dumps(slim, default=str) + "\n")
            jf.flush()
            records.append(rec)
            e = rec["eval"]
            print(f"[E2E] {sc.sid}: pass={e.get('pass')} wall={rec.get('wall_s')} s "
                  f"clip={rec.get('clip')} frame_ok={(rec.get('frame') or {}).get('ok')}", flush=True)
            write_summary(run, records)
    print(f"[E2E] summary: {write_summary(run, records)}", flush=True)


if __name__ == "__main__":
    main()
