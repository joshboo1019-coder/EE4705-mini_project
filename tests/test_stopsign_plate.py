# Change contributed by Student B (assist), pending review by Student C
"""Colour-plate fallback for "stop sign" (branch iter/stopsign-plate,
docs/iter_stopsign_plate.md). Synthetic frames only, no simulator."""

import numpy as np

from core.schema import Detection
from perception import navigation
from perception.perception_real import detect_color_plate

H, W = 480, 640
SKY = (40, 60, 110)          # dark blue, like the scene background
YELLOW = (242, 204, 13)      # sign_yellow_mat
ORANGE = (242, 140, 25)      # ball_orange_mat
GREEN = (25, 153, 51)        # sign_green_mat


def _frame():
    f = np.zeros((H, W, 3), np.uint8)
    f[:] = SKY
    return f


def test_whole_plate_above_horizon_is_a_stop_sign():
    f = _frame()
    f[80:120, 300:340] = YELLOW
    d = detect_color_plate(f, "yellow")
    assert d is not None
    assert d.class_name == "stop sign" and d.color == "yellow"
    x1, y1, x2, y2 = d.bbox
    assert (x1, y1, x2, y2) == (300.0, 80.0, 340.0, 120.0)


def test_wrong_colour_or_low_blob_is_rejected():
    f = _frame()
    f[80:120, 300:340] = ORANGE           # orange ball colour, not yellow
    assert detect_color_plate(f, "yellow") is None
    g = _frame()
    g[200:260, 300:360] = YELLOW          # reaches below the horizon band
    assert detect_color_plate(g, "yellow") is None


def test_chair_shaped_blob_is_rejected():
    f = _frame()
    f[60:400, 250:400] = GREEN            # tall blob down to the floor
    assert detect_color_plate(f, "green") is None


def test_plate_cut_by_top_edge_is_accepted():
    f = _frame()
    f[0:40, 220:420] = GREEN
    d = detect_color_plate(f, "green")
    assert d is not None and d.bbox[1] == 0.0


class _FakePerception:
    def __init__(self, yolo, plate):
        self.yolo, self.plate, self.plate_calls = yolo, plate, 0

    def detect(self, frame, conf_threshold=None):
        return list(self.yolo)

    def detect_plate(self, frame, color):
        self.plate_calls += 1
        return self.plate


def test_wrapper_adds_plate_only_without_yolo_sign():
    plate = Detection("stop sign", "red", 0.6, (300, 80, 340, 120))
    fake = _FakePerception([Detection("chair", "green", 0.9, (0, 0, 10, 10))], plate)
    wrapped = navigation._PlateFallbackPerception(fake, "red")
    dets = wrapped.detect(None)
    assert dets[-1] is plate and len(dets) == 2
    yolo_sign = Detection("stop sign", "red", 0.5, (1, 1, 5, 5))
    fake2 = _FakePerception([yolo_sign], plate)
    assert navigation._PlateFallbackPerception(fake2, "red").detect(None) == [yolo_sign]
    assert fake2.plate_calls == 0


def test_sign_range_model():
    a, b = navigation._SIGN_RANGE_FROM_HEIGHT
    h = b / (2.0 - a)
    d = Detection("stop sign", "red", 0.6, (300, 100, 340, 100 + h))
    assert abs(navigation._sign_planar_range(d, (H, W, 3)) - 2.0) < 1e-6
    cut = Detection("stop sign", "red", 0.6, (220, 0, 420, 40))
    a, b = navigation._SIGN_RANGE_FROM_WIDTH
    assert abs(navigation._sign_planar_range(cut, (H, W, 3)) - (a + b / 200)) < 1e-6
