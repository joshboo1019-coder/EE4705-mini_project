# Change contributed by Student B (assist), pending review by Student C:
# stop signs are now the octagonal STOP plate (mesh "stopsign_octagon" from
# custom_scene.xml's <asset>, textures assets/scenes/textures/stopsign_*.png,
# see tools/make_stopsign_assets.py and docs/task4_stopsign.md) instead of the
# two crossed square boxes. Positions, pole and heights are unchanged.
"""
scenarios.py -- Student C. Ten reproducible Task 4 test scenarios, each with
its own object layout and robot start pose.

Used by perception/task4_cli.py via `--scenario N`. For a chosen scenario it:
  1. generates a scene XML (custom_scene.xml terrain + THIS scenario's
     objects) in the caller-provided output directory,
  2. overwrites core.config.OBJECT_POSITIONS in memory (so the CLI parser and
     the [FOUND] distance log use this scenario's objects -- the file on
     disk is never touched; ground truth is still logging-only),
  3. teleports the robot to the scenario's start pose after boot,
  4. appends a result row to docs/test_result/task4_trials.csv.

Only the free region west of spawn is used (x in [-6, -1], |y| <= 3.5), which
is clear of the stairs, tilted plate and rubble in custom_scene.xml.

Standalone:  python -m perception.scenarios        (lists scenarios)
"""

import csv
import math
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from core import config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASE_SCENE = PROJECT_ROOT / "assets" / "scenes" / "custom_scene.xml"
RESULTS_CSV = PROJECT_ROOT / "docs" / "test_result" / "task4_trials.csv"
SIGN_TEXTURE_DIR = PROJECT_ROOT / "assets" / "scenes" / "textures"
SIGN_PLATE_YAWS = (0.0, 90.0)   # (B, assist) two crossed plates, same as custom_scene.xml

# Placement limits (see module docstring).
OBJ_X_RANGE = (-6.0, -1.0)
OBJ_Y_MAX = 3.5
ROBOT_X_RANGE = (-5.0, 0.0)
ROBOT_Y_MAX = 3.3
MIN_SEPARATION_M = 1.0   # object-object and robot-object

COLOR_RGBA = {
    "red": "0.80 0.08 0.08 1",
    "green": "0.10 0.55 0.15 1",
    "blue": "0.05 0.15 0.90 1",
    "yellow": "0.95 0.80 0.05 1",
    "orange": "0.95 0.55 0.10 1",
    "purple": "0.55 0.10 0.75 1",
    "pink": "0.95 0.20 0.55 1",
}
SUPPORTED_CLASSES = ("chair", "stop sign", "sports ball")


@dataclass
class Obj:
    cls: str
    color: str
    x: float
    y: float
    yaw: float = 0.0   # chairs only (deg); signs/balls look the same from any side

    @property
    def key(self) -> str:
        return f"{self.color}_{self.cls}"


@dataclass
class Scenario:
    idx: int
    name: str
    description: str
    robot: tuple                     # (x, y, yaw_deg); yaw 0 faces +x, 180 faces -x
    objects: List[Obj]
    start_visible: bool              # expected: is a typical target in view at start?
    absent: List[str] = field(default_factory=list)  # keys accepted by the CLI but NOT in the scene

    @property
    def keys(self) -> List[str]:
        return [o.key for o in self.objects] + list(self.absent)


def _original_layout():
    return [
        Obj("chair", "green", -2.0, 2.0), Obj("chair", "red", -2.0, -2.0),
        Obj("sports ball", "orange", -3.5, 0.0), Obj("stop sign", "red", -1.3, 0.0),
        Obj("stop sign", "yellow", -4.5, 2.0), Obj("stop sign", "green", -4.5, -2.0),
    ]


SCENARIOS: List[Scenario] = [
    Scenario(1, "baseline_facing", "Original 6-object layout, robot faces the cluster.",
             (0.0, 0.0, 180.0), _original_layout(), True),
    Scenario(2, "baseline_facing_away", "Original layout, robot faces away: must search first.",
             (0.0, 0.0, 0.0), _original_layout(), False),
    Scenario(3, "chairs_three_colors", "Red/green/blue chairs: same-class color disambiguation.",
             (-0.5, 0.0, 180.0),
             [Obj("chair", "green", -3.5, 1.5), Obj("chair", "red", -3.5, -1.5),
              Obj("chair", "blue", -5.0, 0.0)], True),
    Scenario(4, "chairs_flanking", "Chairs off to either side, ball dead ahead, robot faces +x.",
             (-1.0, 0.0, 0.0),
             [Obj("chair", "red", -3.0, -2.5), Obj("chair", "green", -3.0, 2.5),
              Obj("sports ball", "orange", -2.3, 0.0)], False),
    Scenario(5, "far_small_target", "Small ball 5+ m away (zoom pass), signs nearer.",
             (-0.2, 0.0, 180.0),
             [Obj("sports ball", "orange", -5.5, 0.5), Obj("stop sign", "red", -3.0, -2.5),
              Obj("stop sign", "yellow", -3.0, 2.5)], True),
    Scenario(6, "stop_signs_occlusion", "Three stop signs, one chair partly in front of another.",
             (-0.2, 0.0, 180.0),
             [Obj("chair", "green", -2.5, 0.0), Obj("stop sign", "red", -4.0, 0.3),
              Obj("stop sign", "green", -5.2, -0.3), Obj("stop sign", "yellow", -3.2, -2.3)], True),
    Scenario(7, "side_start_hidden", "Robot faces -y, every object is behind/beside it.",
             (-2.0, -3.0, -90.0),
             [Obj("chair", "green", -2.0, 0.5), Obj("stop sign", "yellow", -4.5, 1.5),
              Obj("sports ball", "orange", -3.5, -1.0)], False),
    Scenario(8, "surrounded", "Robot in the middle of a ring of objects, facing 45 deg.",
             (-3.0, 0.0, 45.0),
             [Obj("chair", "green", -3.0, 2.5), Obj("chair", "red", -3.0, -2.5),
              Obj("chair", "blue", -5.5, 0.0), Obj("sports ball", "orange", -1.2, 0.0),
              Obj("stop sign", "red", -5.0, 2.5)], False),
    Scenario(9, "short_approach", "Target only ~1.2 m away: tests stopping at the 0.8 m threshold.",
             (-1.0, 0.0, 180.0),
             [Obj("stop sign", "red", -2.2, 0.3), Obj("chair", "green", -3.5, -1.5),
              Obj("stop sign", "yellow", -4.5, 1.5)], True),
    Scenario(10, "absent_target",
             "'blue chair' is accepted by the CLI but NOT in the scene (red/green chairs are): "
             "expect [MISSION] status=FAIL reason=target_not_found.",
             (-1.0, 0.0, 180.0),
             [Obj("chair", "green", -3.0, 1.8), Obj("chair", "red", -3.0, -1.8),
              Obj("stop sign", "yellow", -4.8, 0.0)], True,
             absent=["blue_chair"]),
]


# --------------------------------------------------------------------------
def get_scenario(token: str) -> Scenario:
    for s in SCENARIOS:
        if token == str(s.idx) or token == s.name:
            return s
    raise SystemExit(f"Unknown scenario {token!r}. Use 1-{len(SCENARIOS)} or a name: "
                     f"{[s.name for s in SCENARIOS]}")


def validate(s: Scenario) -> None:
    rx, ry, _ = s.robot
    assert ROBOT_X_RANGE[0] <= rx <= ROBOT_X_RANGE[1] and abs(ry) <= ROBOT_Y_MAX, \
        f"scenario {s.idx}: robot start outside the safe region"
    keys = [o.key for o in s.objects]
    assert len(set(keys)) == len(keys), f"scenario {s.idx}: duplicate color+class"
    for o in s.objects:
        assert o.cls in SUPPORTED_CLASSES and o.color in COLOR_RGBA, f"bad object {o}"
        assert OBJ_X_RANGE[0] <= o.x <= OBJ_X_RANGE[1] and abs(o.y) <= OBJ_Y_MAX, \
            f"scenario {s.idx}: {o.key} outside the terrain-free region"
        assert math.hypot(o.x - rx, o.y - ry) >= MIN_SEPARATION_M, \
            f"scenario {s.idx}: {o.key} too close to the robot start"
    for i, a in enumerate(s.objects):
        for b in s.objects[i + 1:]:
            assert math.hypot(a.x - b.x, a.y - b.y) >= MIN_SEPARATION_M, \
                f"scenario {s.idx}: {a.key} and {b.key} overlap"


def build_scene_xml(s: Scenario, output_dir: Path) -> Path:
    """Write the scenario scene XML to the caller-provided output directory."""
    validate(s)
    tree = ET.parse(BASE_SCENE)   # ElementTree drops comments, which is fine
    root = tree.getroot()
    root.set("model", f"scenario_{s.idx:02d}")
    asset, world = root.find("asset"), root.find("worldbody")
    for b in list(world.findall("body")):
        world.remove(b)

    for color in sorted({o.color for o in s.objects}):
        ET.SubElement(asset, "material", name=f"gen_{color}_mat",
                      rgba=COLOR_RGBA[color], specular="0.1", shininess="0.1")
    # (B, assist) the scenario XML is written elsewhere, so give the base
    # scene's texture files absolute paths; then one textured material per
    # sign colour. The name keeps the colour token and "sign", which
    # navigation._find_target_body_id matches on.
    for tex in asset.findall("texture"):
        if tex.get("file") and not Path(tex.get("file")).is_absolute():
            tex.set("file", str((BASE_SCENE.parent / tex.get("file")).resolve()))
    for color in sorted({o.color for o in s.objects if o.cls == "stop sign"}):
        ET.SubElement(asset, "texture", name=f"gen_{color}_sign_tex", type="2d",
                      file=str(SIGN_TEXTURE_DIR / f"stopsign_{color}.png"))
        ET.SubElement(asset, "material", name=f"gen_{color}_sign_mat",
                      texture=f"gen_{color}_sign_tex", rgba="1 1 1 1",
                      specular="0.2", shininess="0.2")

    def geom(parent, typ, size, pos, mat):
        ET.SubElement(parent, "geom", type=typ, size=size, pos=pos, material=mat)

    for o in s.objects:
        mat = f"gen_{o.color}_mat"
        name = o.key.replace(" ", "_")
        if o.cls == "chair":
            b = ET.SubElement(world, "body", name=name, pos=f"{o.x} {o.y} 0",
                              euler=f"0 0 {o.yaw}")
            for sx in (0.18, -0.18):
                for sy in (0.18, -0.18):
                    geom(b, "box", "0.02 0.02 0.21", f"{sx} {sy} 0.21", mat)
            geom(b, "box", "0.22 0.22 0.02", "0 0 0.44", mat)
            geom(b, "box", "0.22 0.02 0.22", "0 -0.20 0.66", mat)
        elif o.cls == "stop sign":
            b = ET.SubElement(world, "body", name=name, pos=f"{o.x} {o.y} 0")
            geom(b, "cylinder", "0.025 0.375", "0 0 0.375", "sign_pole_mat")
            for yaw in SIGN_PLATE_YAWS:   # (B, assist) octagonal STOP plate
                ET.SubElement(b, "geom", type="mesh", mesh="stopsign_octagon", pos="0 0 0.85",
                              euler=f"0 0 {yaw:g}", material=f"gen_{o.color}_sign_mat")
        else:  # sports ball
            b = ET.SubElement(world, "body", name=name, pos=f"{o.x} {o.y} 0.11")
            geom(b, "sphere", "0.11", "0 0 0", mat)

    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / f"scenario_{s.idx:02d}_{s.name}.xml"
    ET.indent(root)
    tree.write(out, encoding="utf-8")
    return out


def apply_to_config(s: Scenario) -> None:
    """Mutate OBJECT_POSITIONS in place (every module shares this dict).
    Absent targets get a far-away dummy position so the CLI accepts them
    and the logged ground-truth distance is obviously huge."""
    config.OBJECT_POSITIONS.clear()
    for o in s.objects:
        config.OBJECT_POSITIONS[o.key] = (o.x, o.y)
    for k in s.absent:
        config.OBJECT_POSITIONS[k] = (99.0, 99.0)


def place_robot(skills, x: float, y: float, yaw_deg: float, settle_s: float = 2.0) -> None:
    """Teleport a RealSkills robot to (x, y, yaw). Uses RealSkills' private
    _data/_model (it has no spawn parameter and skills_real.py is Student A's),
    so keep this in the test harness. The sim thread keeps stepping while we
    write, so a rare bad landing is possible: if the robot falls, just rerun."""
    import mujoco
    skills.stop()
    d = skills._data
    half = math.radians(yaw_deg) / 2.0
    d.qpos[0:3] = (x, y, 0.42)
    d.qpos[3:7] = (math.cos(half), 0.0, 0.0, math.sin(half))
    d.qvel[:] = 0.0
    mujoco.mj_forward(skills._model, d)
    skills._obs_history.reset()
    skills._last_action_isaac[:] = 0.0
    time.sleep(settle_s)
    p = skills.get_robot_pose()
    print(f"[SCENARIO] robot placed at x={p.x:.2f} y={p.y:.2f} yaw={p.yaw_deg:.1f} "
          f"trunk_z={skills.get_trunk_height():.2f} m")


def log_trial(s: Scenario, object_class: str, color: str, success: bool,
              pose, elapsed_s: float) -> None:
    key = f"{color}_{object_class}"
    ox, oy = config.OBJECT_POSITIONS[key]
    d = math.hypot(pose.x - ox, pose.y - oy)
    distractor = any(o.cls == object_class and o.color != color for o in s.objects)
    RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    new = not RESULTS_CSV.exists()
    with RESULTS_CSV.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "scenario", "name", "target", "success",
                        "final_d_m", "elapsed_s", "start_visible_expected",
                        "same_class_distractor", "target_in_scene"])
        w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), s.idx, s.name, key,
                    int(success), f"{d:.2f}", f"{elapsed_s:.1f}",
                    int(s.start_visible), int(distractor), int(key not in s.absent)])
    print(f"[SCENARIO] logged trial -> {RESULTS_CSV}")


def print_scenario(s: Scenario) -> None:
    print(f"\n=== Scenario {s.idx}: {s.name} ===\n{s.description}")
    print(f"Robot start: x={s.robot[0]} y={s.robot[1]} yaw={s.robot[2]} deg | "
          f"target visible at start (expected): {s.start_visible}")
    print("Valid targets: " + ", ".join(k.replace("_", " ") for k in s.keys))
    print("Example: go to the " + s.keys[0].replace("_", " ") + "\n")


def print_scenarios() -> None:
    for s in SCENARIOS:
        print_scenario(s)


if __name__ == "__main__":
    for sc in SCENARIOS:
        validate(sc)
    print_scenarios()