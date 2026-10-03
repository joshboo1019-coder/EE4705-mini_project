"""
tools/check_stopsign_bodies.py -- does Task 4's target-body lookup still find
every graded object after the octagonal STOP plates went in? Written by
Student B (assist), pending review by Student C.

Composes each scene exactly like RealSkills does (platform robot + the scene
as a MapSpec, so bodies/materials get the custom_scene_ prefix) without
starting physics or a renderer, then calls
perception.navigation._find_target_body_id for every key the scene's
OBJECT_POSITIONS lists and checks the body it returns sits at that key's
(x, y). Covers the default scene and the 10 scenario scenes.

    python tools/check_stopsign_bodies.py          # exit code 1 on any mismatch
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import skills.skills_real as sr  # noqa: E402  (puts the platform on sys.path)
import mujoco  # noqa: E402
from runtime_control import MapSpec  # noqa: E402
from runtime_control.map_manager import compose_scene  # noqa: E402

from core import config  # noqa: E402
from perception import scenarios  # noqa: E402
from perception.navigation import _find_target_body_id  # noqa: E402


def compile_scene(scene: Path, tmp: Path):
    out = compose_scene(sr.platform.DEFAULT_ROBOT_XML, {"custom_scene": MapSpec(scene)},
                        tmp / f"{scene.stem}_composed.xml", robot_body_name="trunk",
                        robot_cameras=sr.platform.ROBOT_CAMERAS)
    return mujoco.MjModel.from_xml_path(str(out))


def check(label: str, model, positions: dict, absent=()) -> int:
    bad = 0
    for key, (x, y) in positions.items():
        colour, cls = key.split("_", 1)
        try:
            body = _find_target_body_id(model, colour, cls)
        except LookupError as e:
            body, err = None, str(e)
        else:
            err = ""
        if key in absent:
            ok = body is None
            msg = "absent, not found (expected)" if ok else f"absent but found body {body}"
        elif body is None:
            ok, msg = False, f"NOT FOUND {err}"
        else:
            bx, by = model.body_pos[body][:2]
            geoms = [g for g in range(model.ngeom) if model.geom_bodyid[g] == body]
            kinds = sorted({mujoco.mjtGeom(model.geom_type[g]).name[7:].lower() for g in geoms})
            mats = sorted({model.mat(model.geom_matid[g]).name for g in geoms if model.geom_matid[g] >= 0})
            ok = abs(bx - x) < 0.05 and abs(by - y) < 0.05
            msg = f"body {body} at ({bx:.2f}, {by:.2f}) geoms={kinds} materials={mats}"
        bad += not ok
        print(f"  [{'ok' if ok else 'FAIL'}] {label:28s} {key:18s} {msg}")
    return bad


def main():
    bad = 0
    saved = dict(config.OBJECT_POSITIONS)
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        model = compile_scene(scenarios.BASE_SCENE, tmp)
        bad += check("default custom_scene.xml", model, saved)
        for s in scenarios.SCENARIOS:
            xml = scenarios.build_scene_xml(s, tmp)
            model = compile_scene(xml, tmp)
            scenarios.apply_to_config(s)
            try:
                bad += check(f"scenario {s.idx} {s.name}", model, dict(config.OBJECT_POSITIONS), s.absent)
            finally:
                config.OBJECT_POSITIONS.clear()
                config.OBJECT_POSITIONS.update(saved)
    print("ALL OK" if not bad else f"{bad} FAILURES")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
