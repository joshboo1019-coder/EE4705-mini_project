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
from typing import List, Optional
import cv2
import numpy as np
from PIL import Image, ImageDraw

from core.interfaces import PerceptionAPI
from core.schema import Detection
from core import config

class RealPerception(PerceptionAPI):
    def __init__(self, model_path: str = config.YOLO_MODEL,
                 debug_dir: Optional[str] = None):
        from ultralytics import YOLO

        self.model = YOLO(model_path)
        self.conf_threshold = config.YOLO_CONF_THRESHOLD
        self.debug_dir = Path(debug_dir) if debug_dir else None
        self._debug_frame_index = 0
        if self.debug_dir is not None:
            self.debug_dir.mkdir(parents=True, exist_ok=True)

    def detect(self, frame: np.ndarray) -> List[Detection]:
        frame_index = self._debug_frame_index
        if self.debug_dir is not None:
            self._debug_frame_index += 1
            Image.fromarray(np.asarray(frame, dtype=np.uint8)).save(
                self.debug_dir / f"frame_{frame_index:06d}.png"
            )

        results = self.model.predict(
            frame, conf=self.conf_threshold, verbose=False
        )
        detections = []
        for result in results:
            for box_index, box in enumerate(result.boxes):
                conf = float(box.conf[0].item())
                bbox = tuple(float(value) for value in box.xyxy[0].tolist())
                class_id = int(box.cls[0].item())
                class_name = self.model.names[class_id]
                color = self._grounded_color(frame, bbox)
                if self.debug_dir is not None:
                    height, width = frame.shape[:2]
                    x1, y1, x2, y2 = bbox
                    x1 = max(0, min(width, int(np.floor(x1))))
                    y1 = max(0, min(height, int(np.floor(y1))))
                    x2 = max(0, min(width, int(np.ceil(x2))))
                    y2 = max(0, min(height, int(np.ceil(y2))))
                    if x2 > x1 and y2 > y1:
                        crop = np.asarray(frame[y1:y2, x1:x2], dtype=np.uint8)
                        safe_name = class_name.replace(" ", "_").replace("/", "_")
                        Image.fromarray(crop).save(
                            self.debug_dir
                            / f"frame_{frame_index:06d}_box_{box_index:02d}_{safe_name}.png"
                        )
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
        """Classify rendered RGB pixels inside the detection, independently of YOLO."""
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

        box_width = x2 - x1
        box_height = y2 - y1
        inner_x1 = x1 + box_width // 4
        inner_x2 = x2 - box_width // 4
        inner_y1 = y1 + box_height // 4
        inner_y2 = y2 - box_height // 4
        rgb = frame[inner_y1:inner_y2, inner_x1:inner_x2, :3]
        if rgb.size == 0:
            return "unknown"

        if rgb.dtype != np.uint8:
            rgb = rgb.astype(np.float32)
            if rgb.max() <= 1.0:
                rgb *= 255.0
            rgb = np.clip(rgb, 0.0, 255.0).astype(np.uint8)

        # MuJoCo's renderer returns RGB with scene lighting already applied.
        # HSV hue keeps the material color stable as that lighting changes value.
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        hue = hsv[..., 0].astype(np.float32) * 2.0
        saturation = hsv[..., 1]
        value = hsv[..., 2]
        valid_hues = hue[(saturation >= 64) & (value >= 32)]
        if valid_hues.size == 0:
            if self.debug_dir is not None:
                print("[HSV] no pixels passed saturation/value filters")
            return "unknown"

        # Unwrap at the largest hue gap so red hues on either side of 0/360
        # produce a median near red instead of an unrelated midpoint.
        ordered_hues = np.sort(valid_hues)
        gaps = np.diff(np.concatenate((ordered_hues, ordered_hues[:1] + 360.0)))
        gap_index = int(np.argmax(gaps))
        start = (gap_index + 1) % ordered_hues.size
        unwrapped = np.concatenate((ordered_hues[start:], ordered_hues[:start] + 360.0))
        median_hue = float(np.median(unwrapped) % 360.0)
        if self.debug_dir is not None:
            print(
                f"[HSV] hue={median_hue:.1f} "
                f"sat={float(np.median(saturation)) / 255.0:.3f} "
                f"value={float(np.median(value)) / 255.0:.3f}"
            )

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
    