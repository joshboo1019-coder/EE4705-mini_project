# Owner: Student A (Task 2)
# Change contributed by Student B (assist), pending review by Student A
"""
tests/test_panel_camera.py -- [assist A] the browser panel's Camera dropdown
reaches the renderer in main.py --gui (fix/panel-camera).

RuntimeControl applies panel.consume_camera_change() only in update_command(),
which RealSkills._sim_loop never calls, so RealSkills applies the camera change
itself once per tick -- and nothing else from the panel (no map change, no keys).
Fake runtime/panel, no simulator.
"""

import os
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
# same default as eval/run_env.sh: the platform cloned beside the repo
os.environ.setdefault("QUADRUPED_MUJOCO_ROOT", str(ROOT.parent / "quadruped_mujoco"))
try:
    from skills.skills_real import RealSkills  # noqa: E402
except RuntimeError as e:                     # platform not installed: nothing to test
    pytest.skip(f"quadruped_mujoco platform not found: {e}", allow_module_level=True)


class _FakePanel:
    def __init__(self, camera=None, map_name=None):
        self.pending_camera, self.pending_map = camera, map_name
        self.pressed_keys = {"w"}
        self.camera_calls = self.map_calls = 0

    def consume_camera_change(self):
        self.camera_calls += 1
        c, self.pending_camera = self.pending_camera, None
        return c

    def consume_map_change(self):          # must never be called by RealSkills
        self.map_calls += 1
        m, self.pending_map = self.pending_map, None
        return m


class _LockSpy:
    def __init__(self):
        self._lock = threading.Lock()
        self.entered = 0

    def __enter__(self):
        self._lock.acquire()
        self.entered += 1
        return self

    def __exit__(self, *exc):
        self._lock.release()


class _FakeRuntime:
    def __init__(self, panel):
        self.panel = panel
        self.render_lock = _LockSpy()
        self.browser_camera_mode = "tracking"
        self.pending_map = None


def _skills(runtime):
    s = RealSkills.__new__(RealSkills)     # no sim: only the tick hook is under test
    s._runtime = runtime
    return s


def test_camera_change_is_applied_under_the_render_lock():
    rt = _FakeRuntime(_FakePanel(camera="dog_front_camera"))
    _skills(rt)._apply_panel_camera_change()
    assert rt.browser_camera_mode == "dog_front_camera"
    assert rt.render_lock.entered == 1


def test_switching_back_to_tracking():
    panel = _FakePanel(camera="dog_front_camera")
    rt = _FakeRuntime(panel)
    s = _skills(rt)
    s._apply_panel_camera_change()
    panel.pending_camera = "tracking"
    s._apply_panel_camera_change()
    assert rt.browser_camera_mode == "tracking"


def test_no_pending_change_keeps_the_view_and_takes_no_lock():
    rt = _FakeRuntime(_FakePanel(camera=None))
    _skills(rt)._apply_panel_camera_change()
    assert rt.browser_camera_mode == "tracking" and rt.render_lock.entered == 0


def test_map_changes_and_panel_keys_are_not_consumed():
    panel = _FakePanel(camera="dog_front_camera", map_name="stairs")
    rt = _FakeRuntime(panel)
    _skills(rt)._apply_panel_camera_change()
    assert panel.map_calls == 0 and panel.pending_map == "stairs"
    assert rt.pending_map is None and panel.pressed_keys == {"w"}


def test_no_panel_or_no_runtime_is_a_no_op():
    for rt in (None, type("NoPanel", (), {"panel": None})(), type("Bare", (), {})()):
        _skills(rt)._apply_panel_camera_change()   # must not raise
