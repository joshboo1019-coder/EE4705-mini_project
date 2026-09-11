"""
perception_mock.py — Fake PerceptionAPI for offline development/testing.

Student B: use this in tests/test_parser_with_mock.py so a goto_object
command can run end-to-end through the executor without YOLO installed.

Behavior: returns "not found" for the first N calls, then returns a
plausible detection, so you can exercise both the [SEARCH] and [FOUND]
branches of navigation.py.
"""

from typing import List
import numpy as np
from core.interfaces import PerceptionAPI
from core.schema import Detection


class MockPerception(PerceptionAPI):
    def __init__(self, misses_before_found: int = 3):
        self._calls = 0
        self._misses_before_found = misses_before_found

    def detect(self, frame: np.ndarray) -> List[Detection]:
        self._calls += 1
        if self._calls <= self._misses_before_found:
            return []
        det = Detection(
            class_name="chair", color="green", conf=0.83,
            bbox=(150, 120, 260, 340),
        )
        print(f"[DETECT] class={det.class_name} color={det.color} "
              f"conf={det.conf:.2f} bbox={list(det.bbox)}")
        return [det]
