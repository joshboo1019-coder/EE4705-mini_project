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
        self._target_history = []
        if self.debug_dir is not None:
            self.debug_dir.mkdir(parents=True, exist_ok=True)

    def detect(self, frame: np.ndarray,
               conf_threshold: Optional[float] = None) -> List[Detection]:
        frame_index = self._debug_frame_index
        if self.debug_dir is not None:
            self._debug_frame_index += 1
            Image.fromarray(np.asarray(frame, dtype=np.uint8)).save(
                self.debug_dir / f"frame_{frame_index:06d}.png"
            )

        results = self.model.predict(
            frame,
            conf=(self.conf_threshold if conf_threshold is None
                  else conf_threshold),
            imgsz=config.YOLO_IMGSZ,
            verbose=False,
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

    def clear_target_history(self) -> None:
        self._target_history.clear()

    def remember_target(self, frame: np.ndarray, detection: Detection) -> None:
        rgb_frame = np.asarray(frame, dtype=np.uint8)
        success, encoded = cv2.imencode(
            ".png", cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)
        )
        if not success:
            return

        self._target_history.append((
            encoded.tobytes(), tuple(detection.bbox),
            detection.class_name, detection.color,
        ))
        del self._target_history[:-5]

    def recover_target(self, frame: np.ndarray, object_class: str,
                       color: str,
                       search_bbox: Optional[tuple] = None) -> Optional[Detection]:
        current = np.asarray(frame, dtype=np.uint8)
        frame_height, frame_width = current.shape[:2]
        search_x = 0
        search_y = 0
        search_region = current
        if search_bbox is not None:
            x1, y1, x2, y2 = search_bbox
            search_x = max(0, min(frame_width, int(x1)))
            search_y = max(0, min(frame_height, int(y1)))
            x2 = max(search_x, min(frame_width, int(x2)))
            y2 = max(search_y, min(frame_height, int(y2)))
            search_region = current[search_y:y2, search_x:x2]
            if search_region.size == 0:
                return None
        search_height, search_width = search_region.shape[:2]
        best_match = None

        for encoded, bbox, stored_class, stored_color in reversed(self._target_history):
            if stored_class != object_class or stored_color != color:
                continue

            reference_bgr = cv2.imdecode(
                np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_COLOR
            )
            if reference_bgr is None:
                continue
            reference = cv2.cvtColor(reference_bgr, cv2.COLOR_BGR2RGB)
            ref_height, ref_width = reference.shape[:2]
            x1, y1, x2, y2 = bbox
            x1 = max(0, min(ref_width, int(x1)))
            y1 = max(0, min(ref_height, int(y1)))
            x2 = max(x1, min(ref_width, int(x2)))
            y2 = max(y1, min(ref_height, int(y2)))
            target_crop = reference[y1:y2, x1:x2]
            crop_height, crop_width = target_crop.shape[:2]
            if crop_width < 20 or crop_height < 20:
                continue

            patch_width = max(16, int(crop_width * 0.6))
            patch_height = max(16, int(crop_height * 0.6))
            x_positions = sorted({0, (crop_width - patch_width) // 2,
                                  crop_width - patch_width})
            y_positions = sorted({0, (crop_height - patch_height) // 2,
                                  crop_height - patch_height})
            patch_origins = (
                (x_positions[0], y_positions[0]),
                (x_positions[-1], y_positions[0]),
                (x_positions[0], y_positions[-1]),
                (x_positions[-1], y_positions[-1]),
                (x_positions[1], y_positions[1]),
            )

            for patch_x, patch_y in patch_origins:
                patch = target_crop[
                    patch_y:patch_y + patch_height,
                    patch_x:patch_x + patch_width,
                ]
                if float(np.std(patch)) < 5.0:
                    continue
                for scale in (0.75, 1.0, 1.25, 1.5, 2.0):
                    scaled_width = int(patch.shape[1] * scale)
                    scaled_height = int(patch.shape[0] * scale)
                    if scaled_width > search_width or scaled_height > search_height:
                        continue
                    interpolation = (cv2.INTER_AREA if scale < 1.0
                                     else cv2.INTER_LINEAR)
                    template = cv2.resize(
                        patch, (scaled_width, scaled_height),
                        interpolation=interpolation,
                    )
                    scores = cv2.matchTemplate(
                        search_region, template, cv2.TM_CCOEFF_NORMED
                    )
                    _, score, _, location = cv2.minMaxLoc(scores)
                    match_region = search_region[
                        location[1]:location[1] + scaled_height,
                        location[0]:location[0] + scaled_width,
                    ]
                    if score < 0.78 or self._target_color_fraction(
                            match_region, color) < 0.10:
                        continue

                    candidate = (score, location, scale, patch_x, patch_y,
                                 crop_width, crop_height)
                    if best_match is None or score > best_match[0]:
                        best_match = candidate

        if best_match is None:
            return None

        score, location, scale, patch_x, patch_y, crop_width, crop_height = best_match
        recovered_x1 = max(0.0, search_x + location[0] - patch_x * scale)
        recovered_y1 = max(0.0, search_y + location[1] - patch_y * scale)
        recovered_x2 = min(frame_width, recovered_x1 + crop_width * scale)
        recovered_y2 = min(frame_height, recovered_y1 + crop_height * scale)
        print(f"[TRACK] recovered {color} {object_class} in live frame "
              f"score={score:.2f}")
        return Detection(
            class_name=object_class,
            color=color,
            conf=float(score),
            bbox=(recovered_x1, recovered_y1, recovered_x2, recovered_y2),
        )

    @staticmethod
    def _target_color_fraction(region: np.ndarray, color: str) -> float:
        if region.size == 0:
            return 0.0
        hsv = cv2.cvtColor(region, cv2.COLOR_RGB2HSV)
        hue = hsv[..., 0]
        saturation = hsv[..., 1]
        value = hsv[..., 2]
        valid = (saturation >= 64) & (value >= 32)
        if color == "red":
            matches = (hue < 8) | (hue >= 173)
        elif color == "orange":
            matches = (hue >= 8) & (hue < 23)
        elif color == "yellow":
            matches = (hue >= 23) & (hue < 35)
        elif color == "green":
            matches = (hue >= 35) & (hue < 80)
        elif color == "blue":
            matches = (hue >= 80) & (hue < 130)
        elif color == "purple":
            matches = (hue >= 130) & (hue < 145)
        elif color == "pink":
            matches = (hue >= 145) & (hue < 173)
        else:
            return 0.0
        return float(np.count_nonzero(matches & valid) / region.shape[0] / region.shape[1])

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
    perception = RealPerception()
    detections = perception.detect(frame)

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
    