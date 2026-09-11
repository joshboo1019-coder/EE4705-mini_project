"""
perception_real.py — STUDENT C OWNS THIS FILE (half of Task 4, 60% w/ nav).

Implements PerceptionAPI: YOLO detection + HSV-based color grounding on
Task 2's camera frames. Depends only on numpy arrays in, Detection list
out — never imports skills_real.py, so you can develop/test this with
saved images or a webcam before Student A's simulation is ready.

Test standalone (run from the project root so `core` resolves):
    python -m perception.perception_real --image path/to/test_frame.png
"""

from typing import List
import numpy as np

from core.interfaces import PerceptionAPI
from core.schema import Detection
from core import config

# TODO(Student C):
# from ultralytics import YOLO


class RealPerception(PerceptionAPI):
    def __init__(self, model_path: str = config.YOLO_MODEL):
        # TODO(Student C): self.model = YOLO(model_path)
        self.model = None
        self.conf_threshold = config.YOLO_CONF_THRESHOLD

    def detect(self, frame: np.ndarray) -> List[Detection]:
        # TODO(Student C):
        #   1. results = self.model.predict(frame, conf=self.conf_threshold, verbose=False)
        #   2. for each box: class_name = COCO name, bbox = (x1,y1,x2,y2)
        #   3. color = self._grounded_color(frame, bbox)
        #   4. print("[DETECT] class=... color=... conf=... bbox=...")
        raise NotImplementedError

    def _grounded_color(self, frame: np.ndarray, bbox: tuple) -> str:
        """Median-hue-in-HSV color classification over the pixels inside
        bbox. Do NOT rely on YOLO to know colors — compute it yourself."""
        # TODO(Student C): crop -> cv2.cvtColor(..., COLOR_RGB2HSV) ->
        # median hue -> bucket into a small named palette (red/green/
        # blue/yellow/...).
        raise NotImplementedError


if __name__ == "__main__":
    # TODO(Student C): load a test image, run detect(), draw + save boxes.
    # This is the "verify detection early" screenshot required by Task 2.iii
    # / Task 4.ii.
    print("Run this to test YOLO + color grounding on a saved frame.")
