# Owner: Student C (Task 4)
# Change contributed by Student B (assist), pending review by Student C
"""
tests/test_c2_margin.py — Student B (assist), pending review by Student C.
The approach stops at config.APPROACH_STOP_M (estimated range), a margin
below FOUND_DISTANCE_M; the stop check (C2) still uses FOUND_DISTANCE_M.
See docs/task4_c2_margin.md.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config
from perception import navigation


class _Skills:
    def __init__(self):
        self.moves, self.stops = [], 0

    def move(self, vx, vy, wz, duration):
        self.moves.append((vx, vy, wz, duration))

    def stop(self):
        self.stops += 1


def test_stop_threshold_is_below_the_found_definition():
    assert config.FOUND_DISTANCE_M == 0.8                 # evaluation definition unchanged
    assert 0.0 < config.APPROACH_STOP_M < config.FOUND_DISTANCE_M
    assert navigation._approach_stop_m() == config.APPROACH_STOP_M


def test_approach_keeps_walking_between_stop_and_found_distance():
    s = _Skills()
    d = (config.APPROACH_STOP_M + config.FOUND_DISTANCE_M) / 2   # inside the margin
    dur = navigation._approach_step(s, d)
    assert dur > 0 and s.moves and s.stops == 0
    # the last step lands on APPROACH_STOP_M, never past it
    assert abs(s.moves[0][3] * config.APPROACH_VX - (d - config.APPROACH_STOP_M)) < 1e-9


def test_approach_stops_at_the_stop_threshold():
    s = _Skills()
    assert navigation._approach_step(s, config.APPROACH_STOP_M) == 0.0
    assert s.stops == 1 and not s.moves


def test_far_target_uses_the_normal_step():
    s = _Skills()
    navigation._approach_step(s, 3.0)
    assert s.moves[0] == (abs(config.APPROACH_VX), 0.0, 0.0, config.APPROACH_STEP_S)


def test_per_class_thresholds():
    for cls, stop in config.APPROACH_STOP_M_BY_CLASS.items():
        assert navigation._approach_stop_m(cls) == stop < config.FOUND_DISTANCE_M
    assert navigation._approach_stop_m("stop sign") == config.APPROACH_STOP_M
    s = _Skills()
    assert navigation._approach_step(s, 0.7, navigation._approach_stop_m("sports ball")) == 0.0
    s = _Skills()
    assert navigation._approach_step(s, 0.7, navigation._approach_stop_m("chair")) > 0.0


def test_without_the_config_values_behaviour_is_unchanged(monkeypatch):
    monkeypatch.delattr(config, "APPROACH_STOP_M")
    monkeypatch.delattr(config, "APPROACH_STOP_M_BY_CLASS")
    assert navigation._approach_stop_m("chair") == config.FOUND_DISTANCE_M
