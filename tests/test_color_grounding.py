"""
Colour grounding (perception_real._grounded_color) on synthetic crops.
Written by Student B (assist Task 4). No YOLO, no sim.

Colours are the rendered ones measured in this scene's dog-camera frames
(docs/task4_color_grounding.md): floor/sky hue ~210 deg at S ~130-170,
graded objects at S >= 206.

    python -m pytest -q tests/test_color_grounding.py
"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from perception.perception_real import RealPerception  # noqa: E402

W, H = 320, 240
FLOOR_LIGHT = (51, 77, 102)    # checker floor, hue 210
FLOOR_DARK = (26, 51, 77)      # navy checker, hue 210
SKY = (45, 70, 98)
RED = (151, 14, 14)
GREEN = (12, 111, 20)
BLUE = (20, 51, 151)           # blue_chair as rendered, hue ~226
ORANGE = (242, 140, 26)
ORANGE_HIGHLIGHT = (255, 236, 160)


@pytest.fixture(scope="module")
def perception():
    p = RealPerception.__new__(RealPerception)   # skip loading YOLO
    p.debug_dir = None
    return p


def scene():
    """Sky above a navy checker floor, like the dog camera's view."""
    img = np.zeros((H, W, 3), np.uint8)
    img[: H // 3] = SKY
    yy, xx = np.mgrid[H // 3:H, 0:W]
    checker = ((yy // 20 + xx // 20) % 2).astype(bool)
    img[H // 3:][checker] = FLOOR_LIGHT
    img[H // 3:][~checker] = FLOOR_DARK
    return img


def thin_chair(img, box, color, t=3):
    """Chair seen from the front: two legs, a seat bar and a backrest outline,
    `t` px thick. Most of the box stays background."""
    x1, y1, x2, y2 = box
    mid = (y1 + y2) // 2
    img[y1:y2, x1:x1 + t] = color             # left leg + back post
    img[y1:y2, x2 - t:x2] = color             # right leg + back post
    img[mid:mid + t, x1:x2] = color           # seat
    img[y1:y1 + t, x1:x2] = color             # top of the backrest
    return img


def test_thin_red_frame_on_blue_background_is_red(perception):
    box = (120, 60, 200, 200)
    img = thin_chair(scene(), box, RED)
    assert perception._grounded_color(img, box) == "red"


def test_thin_green_frame_is_green(perception):
    box = (100, 70, 170, 210)
    img = thin_chair(scene(), box, GREEN, t=2)
    assert perception._grounded_color(img, box) == "green"


def test_solid_blue_object_on_navy_floor_is_blue(perception):
    box = (130, 100, 190, 190)
    img = scene()
    img[110:180, 140:180] = BLUE
    assert perception._grounded_color(img, box) == "blue"


def test_orange_ball_with_clipped_highlight_is_orange(perception):
    box = (130, 130, 190, 190)
    img = scene()
    yy, xx = np.mgrid[0:H, 0:W]
    r2 = (xx - 160) ** 2 + (yy - 160) ** 2
    img[r2 <= 28 ** 2] = ORANGE
    img[(xx - 152) ** 2 + (yy - 150) ** 2 <= 9 ** 2] = ORANGE_HIGHLIGHT   # specular spot
    assert perception._grounded_color(img, box) == "orange"


def test_mostly_background_is_unknown(perception):
    box = (100, 90, 220, 220)
    img = scene()
    img[150:152, 150:152] = RED            # 4 stray pixels
    assert perception._grounded_color(img, box) == "unknown"


def test_floor_and_sky_alone_are_not_blue(perception):
    img = scene()
    for box in [(0, 0, 320, 80), (0, 100, 320, 240), (60, 40, 260, 200), (0, 0, 320, 240)]:
        assert perception._grounded_color(img, box) == "unknown", box


def test_object_larger_than_its_box_keeps_its_colour(perception):
    """Close range: the chair sticks ~10 px out of its box (left, right, top),
    so its colour is in the ring too; it must not be treated as background.
    (A box deep inside a solid object, with the ring full of the object's
    colour, gives "unknown" - see docs/task4_color_grounding.md.)"""
    img = scene()
    img[40:240, 60:280] = GREEN
    img[120:240, 100:240] = FLOOR_DARK     # gap under the seat
    assert perception._grounded_color(img, (70, 50, 270, 240)) == "green"


def test_invalid_boxes_are_unknown(perception):
    img = scene()
    assert perception._grounded_color(img, (50, 50, 50, 80)) == "unknown"
    assert perception._grounded_color(img, (400, 300, 500, 400)) == "unknown"
    assert perception._grounded_color(img[..., 0], (0, 0, 10, 10)) == "unknown"
