"""
perception_real.py — STUDENT C OWNS THIS FILE (half of Task 4, 60% w/ nav).

Implements PerceptionAPI: YOLO detection + HSV-based color grounding on
Task 2's camera frames. Depends only on numpy arrays in, Detection list
out — never imports skills_real.py, so you can develop/test this with
saved images or a webcam before Student A's simulation is ready.

Test standalone (run from the project root so `core` resolves):
    python -m perception.perception_real --image path/to/test_frame.png
"""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import List
import numpy as np
from PIL import Image, ImageDraw

from core.interfaces import PerceptionAPI
from core.schema import Detection
from core import config

class RealPerception(PerceptionAPI):
    def __init__(self, model_path: str = config.YOLO_MODEL):
        from ultralytics import YOLO

        self.model = YOLO(model_path)
        self.conf_threshold = config.YOLO_CONF_THRESHOLD

    def detect(self, frame: np.ndarray) -> List[Detection]:
        results = self.model.predict(
            frame, conf=self.conf_threshold, verbose=False
        )
        detections = []
        for result in results:
            for box in result.boxes:
                conf = float(box.conf[0].item())
                bbox = tuple(float(value) for value in box.xyxy[0].tolist())
                class_id = int(box.cls[0].item())
                class_name = self.model.names[class_id]
                color = self._grounded_color(frame, bbox)
                detection = Detection(
                    class_name=class_name,
                    color=color,
                    conf=conf,
                    bbox=bbox,
                )
                detections.append(detection)
                print(
                    f"[DETECT] class={detection.class_name} color={detection.color} "
                    f"conf={detection.conf:.2f} bbox={list(detection.bbox)}"
                )
        return detections

    def _grounded_color(self, frame: np.ndarray, bbox: tuple) -> str:
        """Median-hue-in-HSV color classification over the pixels inside
        bbox. Do NOT rely on YOLO to know colors — compute it yourself."""
        if frame.ndim < 3 or frame.shape[2] < 3 or len(bbox) != 4:
            return "unknown"

        height, width = frame.shape[:2]
        x1, y1, x2, y2 = bbox
        x1 = max(0, min(width, int(np.floor(x1))))
        y1 = max(0, min(height, int(np.floor(y1))))
        x2 = max(0, min(width, int(np.ceil(x2))))
        y2 = max(0, min(height, int(np.ceil(y2))))
        if x2 <= x1 or y2 <= y1:
            return "unknown"

        rgb = frame[y1:y2, x1:x2, :3].astype(np.float32)
        if rgb.size == 0:
            return "unknown"
        if rgb.max() > 1.0:
            rgb /= 255.0
        rgb = np.clip(rgb, 0.0, 1.0)

        red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]
        maximum = np.max(rgb, axis=2)
        minimum = np.min(rgb, axis=2)
        delta = maximum - minimum

        hue = np.zeros_like(maximum)
        chromatic = delta > 0
        red_max = chromatic & (maximum == red)
        green_max = chromatic & (maximum == green)
        blue_max = chromatic & (maximum == blue)
        hue[red_max] = 60.0 * np.mod((green[red_max] - blue[red_max]) / delta[red_max], 6.0)
        hue[green_max] = 60.0 * ((blue[green_max] - red[green_max]) / delta[green_max] + 2.0)
        hue[blue_max] = 60.0 * ((red[blue_max] - green[blue_max]) / delta[blue_max] + 4.0)

        saturation = np.zeros_like(maximum)
        non_black = maximum > 0
        saturation[non_black] = delta[non_black] / maximum[non_black]
        valid_hues = hue[(saturation >= 0.2) & (maximum >= 0.15)]
        if valid_hues.size == 0:
            return "unknown"

        # Unwrap at the largest hue gap so red hues on either side of 0/360
        # produce a median near red instead of an unrelated midpoint.
        ordered_hues = np.sort(valid_hues)
        gaps = np.diff(np.concatenate((ordered_hues, ordered_hues[:1] + 360.0)))
        gap_index = int(np.argmax(gaps))
        start = (gap_index + 1) % ordered_hues.size
        unwrapped = np.concatenate((ordered_hues[start:], ordered_hues[:start] + 360.0))
        median_hue = float(np.median(unwrapped) % 360.0)

        if median_hue < 15.0 or median_hue >= 345.0:
            return "red"
        if median_hue < 45.0:
            return "orange"
        if median_hue < 70.0:
            return "yellow"
        if median_hue < 160.0:
            return "green"
        if median_hue < 260.0:
            return "blue"
        if median_hue < 290.0:
            return "purple"
        return "pink"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run YOLO and color grounding on a saved image."
    )
    parser.add_argument("--image", required=True, type=Path, help="input image path")
    args = parser.parse_args()
    if not args.image.is_file():
        parser.error(f"image file not found: {args.image}")

    image = Image.open(args.image).convert("RGB")
    frame = np.asarray(image)
    detections = RealPerception().detect(frame)

    output_stem = args.image.with_name(f"{args.image.stem}_detections")
    image_path = output_stem.with_suffix(".jpg")
    json_path = output_stem.with_suffix(".json")

    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)
    for detection in detections:
        x1, y1, x2, y2 = detection.bbox
        draw.rectangle((x1, y1, x2, y2), outline="red", width=3)
        label = f"{detection.color} {detection.class_name} {detection.conf:.2f}"
        draw.text((x1, max(0, y1 - 14)), label, fill="red")
    annotated.save(image_path)

    with json_path.open("w", encoding="utf-8") as output_file:
        json.dump([asdict(detection) for detection in detections], output_file, indent=2)
        output_file.write("\n")

    print(f"Saved annotated image: {image_path}")
    print(f"Saved detections JSON: {json_path}")
    