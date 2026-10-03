"""
tests/test_hard_scene.py -- Student B (assist), pending review by Student C.
The optional hard scene (perception/hard_scene.py, `main.py --scene hard`,
e2e S6). No sim, no renderer.
"""

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import main
from core import config
from perception import hard_scene as H

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def restore_config():
    saved = dict(config.OBJECT_POSITIONS)
    flags = (main.USE_REAL_SKILLS, main.USE_REAL_PERCEPTION)
    yield
    config.OBJECT_POSITIONS.clear()
    config.OBJECT_POSITIONS.update(saved)
    main.USE_REAL_SKILLS, main.USE_REAL_PERCEPTION = flags


def _bodies(path):
    world = ET.parse(path).getroot().find("worldbody")
    return {b.get("name"): b for b in world.findall("body")}


def test_default_scene_untouched_and_kept_inside_hard_scene():
    assert config.SCENE_PATH == "assets/scenes/custom_scene.xml"
    base, hard = _bodies(H.BASE_SCENE), _bodies(H.scene_path())
    canon = lambda b: [(e.tag, sorted(e.attrib.items())) for e in b.iter()]
    for name, body in base.items():
        assert canon(hard[name]) == canon(body)
    new = set(hard) - set(base)
    assert new == {"green_chair_2", *H.WALLS_HARD, *H.DISTRACTORS_HARD}


def test_xml_matches_ground_truth():
    hard = _bodies(H.scene_path())
    pos = lambda n: tuple(float(v) for v in hard[n].get("pos").split()[:2])
    assert pos("green_chair_2") == H.OBJECT_POSITIONS_HARD["green_chair#2"]
    assert pos("green_chair") == H.OBJECT_POSITIONS_HARD["green_chair#1"]
    for n, (xy, half) in H.WALLS_HARD.items():
        assert pos(n) == xy
        assert hard[n].find("geom").get("size") == " ".join(str(v) for v in half)
        assert 2 * half[2] == pytest.approx(1.2)
    for n, (xy, _, _) in H.DISTRACTORS_HARD.items():
        assert pos(n) == xy


def test_second_chair_material_has_no_green_token():
    """navigation._find_target_body_id matches material-name tokens; the 2nd
    chair must not be a second 'green' + 'chair' body (LookupError)."""
    chair2 = _bodies(H.scene_path())["green_chair_2"]
    mats = {g.get("material") for g in chair2.findall("geom")}
    assert mats == {"chair_green2_mat"} and "green" not in "chair_green2_mat".split("_")


def test_find_target_body_id_on_the_hard_scene():
    mujoco = pytest.importorskip("mujoco")
    from perception import navigation as nav
    model = mujoco.MjModel.from_xml_path(str(H.scene_path()))
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    for cls, color, key in [("chair", "green", "green_chair#1"), ("chair", "red", "red_chair"),
                            ("sports ball", "orange", "orange_sports ball"),
                            ("stop sign", "yellow", "yellow_stop sign")]:
        b = nav._find_target_body_id(model, color, cls)
        assert tuple(round(float(v), 2) for v in data.xpos[b][:2]) == H.OBJECT_POSITIONS_HARD[key]


def test_layout_rules_and_occlusion_from_the_spawn():
    H.validate()
    vis = {k: H.occluded_from(H.SPAWN, xy) for k, xy in H.OBJECT_POSITIONS_HARD.items()}
    assert vis["yellow_stop sign"] == vis["green_stop sign"] == "hidden"
    assert all(v == "visible" for k, v in vis.items() if "stop sign" not in k or k.startswith("red"))


def test_apply_to_config_instances(restore_config):
    used = H.apply_to_config()
    assert used["green_chair"] == "green_chair#1"
    assert config.OBJECT_POSITIONS["green_chair"] == (-2.0, 2.0)
    assert set(config.OBJECT_POSITIONS) == {H.plain_key(k) for k in H.OBJECT_POSITIONS_HARD}
    H.apply_to_config("green_chair#2")
    assert config.OBJECT_POSITIONS["green_chair"] == (-3.5, 1.1)
    with pytest.raises(SystemExit):
        H.apply_to_config("green_chair#3")


def test_main_load_hard_scene(restore_config):
    main.USE_REAL_SKILLS = False
    assert main.load_hard_scene() is None
    assert config.OBJECT_POSITIONS["green_chair"] == (-2.0, 2.0)
    main.USE_REAL_SKILLS = True
    assert Path(main.load_hard_scene("green_chair#2")) == H.scene_path()
    assert config.OBJECT_POSITIONS["green_chair"] == (-3.5, 1.1)


@pytest.mark.parametrize("argv", [["--scene", "hard", "--scenario", "3"],
                                  ["--gt-instance", "green_chair#2"]])
def test_main_rejects_flag_combinations(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["main.py", "--mock", *argv])
    with pytest.raises(SystemExit) as exc:
        main.main()
    assert exc.value.code == 2


def test_apply_lighting_scales_lights_and_headlight():
    import numpy as np

    class Vec:
        pass

    model = Vec()
    model.light_diffuse = np.ones((1, 3))
    model.light_ambient = np.zeros((1, 3))
    model.light_specular = np.full((1, 3), 0.3)
    model.nlight = 1
    model.vis = Vec()
    model.vis.headlight = Vec()
    model.vis.headlight.diffuse = np.full(3, 0.6)
    model.vis.headlight.ambient = np.full(3, 0.3)
    model.vis.headlight.specular = np.zeros(3)
    skills = Vec()
    skills._model = model
    H.apply_lighting(skills, 0.5)
    assert model.light_diffuse[0, 0] == pytest.approx(0.5)
    assert model.vis.headlight.diffuse[0] == pytest.approx(0.3)
    assert model.vis.headlight.ambient[0] == pytest.approx(0.15)
    H.apply_lighting(object())     # MockSkills: no-op


def test_geom_labels_cover_walls_and_boxes():
    labels = H.geom_labels()
    for name in (*H.WALLS_HARD, *H.DISTRACTORS_HARD, "green_chair_2"):
        assert name in labels.values()
    assert labels["map_custom_scene_0"] == "floor"


def test_s6_suite_and_scoring():
    from eval.e2e import run_all as R
    suite = R.suite_s6()
    assert len(suite) == 6 and all("main.py --gui --scene hard" in s.launch for s in suite)
    s2 = next(s for s in suite if s.name == "02_green_by_ball")
    assert "--gt-instance 'green_chair#2'" in s2.launch
    labels = H.geom_labels()
    wall = next(k for k, v in labels.items() if v == "wall_north")
    t0 = 1000.0
    trace = [{"t": t0 + i, "x": -2.9 * i / 10, "y": 1.1 * i / 10, "yaw": 0, "z": 0.33,
              "roll": 0, "pitch": 0} for i in range(11)]
    trace[3]["contacts"] = [f"FL_foot|{wall}"]
    rec = {"suite": "S6", "scenario": s2.name, "meta": s2.meta, "crash": False,
           "steps": [{"text": "x", "t_end": t0 + 10}],
           "lines": [(t0 + 1, "User: [CMD] actions=goto_object(class=chair, color=green) n=1"),
                     (t0 + 5, "[RANGE] estimated_planar=0.55 m ground_truth=0.6 m phase=stop_check"),
                     (t0 + 9.5, "[FOUND] class=chair color=green t=8.0 s d=0.60 m"),
                     (t0 + 10, "[MISSION] status=SUCCESS")],
           "trace": trace}
    ev = R.evaluate(rec)
    assert ev["went_to"] == "green_chair#2" and ev["true_d"] == pytest.approx(0.6)
    assert ev["touched"] == ["wall_north"] and ev["wall_contact"]
    assert ev["pass"] is True
