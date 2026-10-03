"""
hard_scene.py -- Change contributed by Student B (assist), pending review by
Student C (perception/ is C's area). OPTIONAL stress-test scene; the default
scene (assets/scenes/custom_scene.xml, config.SCENE_PATH) is untouched.

`main.py --scene hard` loads assets/scenes/custom_scene_hard.xml: the default
scene plus
  * a SECOND green chair next to the orange ball (same colour, same shape),
  * two grey walls (1.2 m high) that hide the yellow and the green stop sign
    from the spawn,
  * colour distractors that are not targets: an orange box near the ball and
    a red box near the red chair,
  * dimmer lighting (LIGHT_SCALE, applied at runtime -- see apply_lighting).
See docs/hard_scene.md for the layout, what each change stresses and the
headless findings.

Ground truth here is for LOGGING / EVALUATION ONLY (the [FOUND] d= and
[RANGE] ground_truth= log lines, and the e2e S6 suite). Nothing in this module
is read by navigation or perception to steer.

The two green chairs and navigation._find_target_body_id: that function looks
up the target body (for its live height) by material-name tokens + geometry
and raises LookupError if TWO bodies match. The second chair therefore uses
the material `chair_green2_mat` (same rgba): its name has no `green` token, so
the lookup still returns exactly one body (green chair #1). Both chairs stand
on the floor, so the height navigation reads from #1 is also correct for #2.
navigation.py is unchanged.

Standalone:  python -m perception.hard_scene     (validates + prints layout)
"""

import math
import xml.etree.ElementTree as ET
from pathlib import Path

from core import config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HARD_SCENE_PATH = "assets/scenes/custom_scene_hard.xml"
BASE_SCENE = PROJECT_ROOT / config.SCENE_PATH

# Targets, keyed like config.OBJECT_POSITIONS ("<color>_<class>"); a second
# instance of the same colour+class gets a "#N" suffix. Logging only.
OBJECT_POSITIONS_HARD = {
    "green_chair#1": (-2.0, 2.0),        # the default scene's green chair
    "green_chair#2": (-3.5, 1.1),        # NEW: next to the orange ball
    "red_chair": (-2.0, -2.0),
    "orange_sports ball": (-3.5, 0.0),
    "red_stop sign": (-1.3, 0.0),
    "yellow_stop sign": (-4.5, 2.0),     # hidden from the spawn by wall_north
    "green_stop sign": (-4.5, -2.0),     # hidden from the spawn by wall_south
    "blue_chair": (3.45, 2.0),           # on the stairs, as in the default scene
}
# Which instance a plain key ("green_chair") refers to in the logs by default.
DEFAULT_INSTANCE = {"green_chair": "green_chair#1"}

# Non-target colour distractors: name -> ((x, y), half-size (x, y, z), rgba).
DISTRACTORS_HARD = {
    "orange_box": ((-3.6, -0.9), (0.2, 0.2, 0.2), "0.95 0.55 0.10 1"),   # ball's rgba
    "red_box": ((-2.3, -3.1), (0.2, 0.2, 0.2), "0.75 0.10 0.10 1"),      # red chair's rgba
}
# Occluding walls: name -> ((x, y), half-size (x, y, z)). 1.2 m high, 10 cm thick.
WALLS_HARD = {
    "wall_north": ((-4.0, 2.25), (0.05, 0.8, 0.6)),     # y in [1.45, 3.05]
    "wall_south": ((-4.0, -2.25), (0.05, 0.8, 0.6)),    # y in [-3.05, -1.45]
}
WALL_RGBA = "0.55 0.55 0.55 1"
# Scale for every light in the composed model + the headlight (diffuse,
# ambient, specular). compose_scene() imports only <geom>/<body> from a map
# file, so the robot XML's lights cannot be dimmed from the scene XML.
LIGHT_SCALE = 0.55

SPAWN = (0.0, 0.0)
FREE_X = (-6.0, -1.0)   # perception/scenarios.py: terrain-free region west of the spawn
FREE_Y_MAX = 3.5
MIN_GAP_M = 1.0         # every wall keeps one end with >= 1 m of open floor

_FOOTPRINT_M = {"chair": 0.31, "stop sign": 0.15, "sports ball": 0.11}


def plain_key(instance_key: str) -> str:
    return instance_key.split("#", 1)[0]


def instances(key: str) -> list:
    """All instance keys of a plain "<color>_<class>" key in the hard scene."""
    return [k for k in OBJECT_POSITIONS_HARD if plain_key(k) == key]


def apply_to_config(gt_instance: str | None = None) -> dict:
    """Mutate config.OBJECT_POSITIONS in place (like scenarios.apply_to_config)
    so the [FOUND] d= / [RANGE] ground_truth= logs use the hard scene. A plain
    key with two instances ("green_chair") is mapped to DEFAULT_INSTANCE, or
    to `gt_instance` (e.g. "green_chair#2") when given. Returns the mapping
    plain key -> instance key used. Logging only."""
    chosen = dict(DEFAULT_INSTANCE)
    if gt_instance is not None:
        if gt_instance not in OBJECT_POSITIONS_HARD:
            raise SystemExit(f"--gt-instance {gt_instance!r} is not one of "
                             f"{list(OBJECT_POSITIONS_HARD)}")
        chosen[plain_key(gt_instance)] = gt_instance
    config.OBJECT_POSITIONS.clear()
    used = {}
    for inst, pos in OBJECT_POSITIONS_HARD.items():
        key = plain_key(inst)
        if inst == chosen.get(key, inst):
            config.OBJECT_POSITIONS[key] = pos
            used[key] = inst
    return used


def apply_lighting(skills, scale: float = LIGHT_SCALE) -> None:
    """Dim the composed model's lights and headlight in place (render-only:
    no effect on physics). Uses RealSkills' private _model, like
    scenarios.place_robot; a no-op for MockSkills."""
    model = getattr(skills, "_model", None)
    if model is None:
        return
    for arr in (model.light_diffuse, model.light_ambient, model.light_specular):
        arr[:] = arr * scale
    hl = model.vis.headlight
    hl.diffuse[:] = hl.diffuse * scale
    hl.ambient[:] = hl.ambient * scale
    hl.specular[:] = hl.specular * scale
    print(f"[HARD] lighting scaled to {scale:.0%}: headlight diffuse="
          f"{tuple(round(float(v), 2) for v in hl.diffuse)} ambient="
          f"{tuple(round(float(v), 2) for v in hl.ambient)}, {model.nlight} light(s)")


def scene_path() -> Path:
    return PROJECT_ROOT / HARD_SCENE_PATH


def geom_labels(xml_path: Path | None = None) -> dict:
    """compose_scene() renames map geoms to map_custom_scene_<i> in document
    order (bare geoms and every geom inside imported bodies). Rebuild that
    order to label trace contacts: {"map_custom_scene_<i>": "<body name>" |
    "terrain"}. Logging only (eval/e2e S6)."""
    root = ET.parse(xml_path or scene_path()).getroot()
    labels, i = {}, 0
    for el in root.find("worldbody"):
        if el.tag == "geom":
            labels[f"map_custom_scene_{i}"] = "floor" if el.get("name") == "floor" else "terrain"
            i += 1
        elif el.tag == "body":
            for _ in el.findall(".//geom"):
                labels[f"map_custom_scene_{i}"] = el.get("name")
                i += 1
    return labels


# --------------------------------------------------------------------------
# Validation (pure geometry, no sim)

def _seg_hits_box(p, q, c, half) -> bool:
    """2-D segment p->q intersects the axis-aligned rectangle (c, half)?"""
    t0, t1 = 0.0, 1.0
    for k in (0, 1):
        d = q[k] - p[k]
        lo, hi = c[k] - half[k], c[k] + half[k]
        if abs(d) < 1e-12:
            if not lo <= p[k] <= hi:
                return False
            continue
        a, b = (lo - p[k]) / d, (hi - p[k]) / d
        t0, t1 = max(t0, min(a, b)), min(t1, max(a, b))
        if t0 > t1:
            return False
    return True


def occluded_from(viewer, target_xy, lateral_half: float = 0.15) -> str:
    """'hidden' if every sight line from `viewer` to the target's centre and
    both lateral edges crosses a wall (walls are taller than every target and
    than the camera), 'partial' if some do, else 'visible'."""
    tx, ty = target_xy
    ang = math.atan2(ty - viewer[1], tx - viewer[0]) + math.pi / 2
    pts = [(tx + s * lateral_half * math.cos(ang), ty + s * lateral_half * math.sin(ang))
           for s in (-1, 0, 1)]
    hits = [any(_seg_hits_box(viewer, p, c, h[:2]) for c, h in WALLS_HARD.values())
            for p in pts]
    return "hidden" if all(hits) else ("partial" if any(hits) else "visible")


def validate() -> list:
    """Assert the layout rules; return report lines."""
    out = []
    props = {k: v for k, v in OBJECT_POSITIONS_HARD.items() if k != "blue_chair"}
    for k, (x, y) in props.items():
        assert FREE_X[0] <= x <= FREE_X[1] and abs(y) <= FREE_Y_MAX, f"{k} outside the free region"
    for name, ((x, y), h) in {**WALLS_HARD, **{k: (v[0], v[1]) for k, v in DISTRACTORS_HARD.items()}}.items():
        assert FREE_X[0] <= x - h[0] and x + h[0] <= FREE_X[1] and abs(y) + h[1] <= FREE_Y_MAX, \
            f"{name} outside the free region"
    for name, ((x, y), h) in WALLS_HARD.items():
        north, south = y + h[1], y - h[1]
        out.append(f"{name}: x={x:+.2f}, y in [{south:+.2f}, {north:+.2f}], height {2 * h[2]:.1f} m")
    for k, xy in OBJECT_POSITIONS_HARD.items():
        out.append(f"from the spawn: {k:20s} {occluded_from(SPAWN, xy)}")
    return out


def print_layout(used: dict | None = None) -> None:
    print("\n=== Hard scene (assets/scenes/custom_scene_hard.xml) ===")
    for k, (x, y) in OBJECT_POSITIONS_HARD.items():
        print(f"  target     {k:20s} ({x:+.2f}, {y:+.2f})")
    for k, ((x, y), _, _) in DISTRACTORS_HARD.items():
        print(f"  distractor {k:20s} ({x:+.2f}, {y:+.2f})")
    for k, ((x, y), h) in WALLS_HARD.items():
        print(f"  wall       {k:20s} x={x:+.2f} y=[{y - h[1]:+.2f}, {y + h[1]:+.2f}]")
    if used:
        print("  logs ([FOUND] d=, [RANGE] ground_truth=) measure to: "
              + ", ".join(f"{k} -> {v}" for k, v in used.items() if k != v))
    print(f"  lighting x{LIGHT_SCALE}\n")


if __name__ == "__main__":
    for line in validate():
        print(line)
    print_layout()
