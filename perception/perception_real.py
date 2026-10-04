# Change contributed by Student B (assist), reviewed by Student C (colour-grounding fix)
# Change contributed by Student B (assist), pending review by Student C:
# colour-plate fallback for "stop sign" (detect_color_plate, branch
# iter/stopsign-plate, docs/iter_stopsign_plate.md). Image pixels only.
"""
perception_real.py — STUDENT C OWNS THIS FILE (half of Task 4, 60% w/ nav).

Implements PerceptionAPI: YOLO detection + HSV-based color grounding on
Task 2's camera frames. Depends only on numpy arrays in, Detection list
out — never imports skills_real.py, so you can develop/test this with
saved images or a webcam before Student A's simulation is ready.

Colour-grounding fix contributed by Student B (assist), reviewed by Student C.

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

_TARGET_HISTORY_LIMIT = 8
_MIN_COLOR_SATURATION = 64
_MIN_COLOR_VALUE = 32
_COLOR_HUE_RANGES = {
    "red": ((0.0, 15.0), (345.0, 360.0)),
    "orange": ((15.0, 42.0),),
    "yellow": ((42.0, 78.0),),
    "green": ((78.0, 170.0),),
    # The blue checker floor is around 210 degrees; scene chairs use a
    # more saturated blue near 233 degrees.
    "blue": ((220.0, 250.0),),
    "purple": ((250.0, 305.0),),
    "pink": ((305.0, 345.0),),
}
# Colour grounding (_grounded_color). Tuned offline on rendered dog-camera
# frames (tools/task4_color_testset.py, docs/task4_color_grounding.md).
_GROUND_MIN_SATURATION = 160    # drop grey/white pixels, the beige terrain (S ~70) and most of the
                                # floor/sky (S ~130-170); graded objects render at S >= 206
_GROUND_MIN_VALUE = 32          # drop near-black pixels (shadows)
_GROUND_MAX_VALUE = 250         # drop clipped highlights: their hue drifts (orange -> yellow)
_GROUND_RING_FRAC = 0.15        # background ring width, as a fraction of the bbox's longer side
_GROUND_RING_MIN_PX = 4
_GROUND_BG_MIN_FRAC = 0.02      # a colour (within the tolerances below) is background if it covers
_GROUND_BG_RATIO = 1.0          # >= 2% of the ring AND is >= 1.0x as dense in the ring as in the bbox
_GROUND_BG_HUE_TOL = 10.0       # colour tolerance: +-10 deg hue ...
_GROUND_BG_SAT_TOL = 1          # ... and +-1 saturation cell (32 wide)
_GROUND_HUE_BIN = 10.0          # dominant-hue histogram bin (deg)
_GROUND_BIN_FINE = 2.0          # background-model hue cell (deg)
_GROUND_CENTER_SIGMA = 0.5      # centre weighting of the hue vote (1.0 = bbox half-size)
_GROUND_MIN_FG_PX = 12          # fewer foreground pixels than this -> "unknown"
_GROUND_MIN_FG_FRAC = 0.002     # ... or than this fraction of the bbox area


# Colour-plate fallback for "stop sign" (docs/iter_stopsign_plate.md). The
# scene's signs are a "+" of two flat 0.30 m plates at z 0.70-1.00 m on a
# grey pole; yolo11n almost never calls them "stop sign". Only used by
# navigation when the requested class is "stop sign" and YOLO has no
# matching detection. Image pixels only, no simulator state.
_PLATE_MIN_SATURATION = 160      # same cut as colour grounding
_PLATE_MIN_VALUE = 32
_PLATE_MAX_VALUE = 250
_PLATE_MIN_AREA_PX = 120         # ~11x11 px: plate to ~7 m; drops chair-backrest fragments
_PLATE_MIN_FILL = 0.45           # blob area / bbox area (plate is solid)
_PLATE_ASPECT_RANGE = (0.55, 2.2)  # bbox height / width, whole plate in view
_PLATE_MAX_BOTTOM_FRAC = 0.35    # plate bottom (z 0.70 m) sits above the camera:
                                 # its bbox ends in the upper ~third of the frame;
                                 # chairs/balls and floor reflections reach lower
_PLATE_MAX_HEIGHT_FRAC = 0.30    # a whole plate never fills a third of the frame height
_PLATE_EDGE_PX = 1               # bbox touching the top edge = plate cut by the frame
_PLATE_CUT_MIN_WIDTH_PX = 20
_PLATE_BAR_OPEN_PX = 9           # bars narrower than this are removed (plate >= ~14 px wide to ~7 m)
_PLATE_CUT_MAX_ASPECT = 1.6     # cut plate: visible height / width


def detect_color_plate(frame: np.ndarray, color: str) -> Optional[Detection]:
    """Find a flat sign plate of `color`: the largest compact blob of that
    colour whose bbox ends in the upper part of the image (the plate is
    mounted above the camera). Returns a Detection labelled "stop sign" or
    None. A plate cut by the top edge (close range) is accepted with a
    looser shape test."""
    if (color not in _COLOR_HUE_RANGES or frame.ndim < 3
            or frame.shape[2] < 3):
        return None
    rgb = np.ascontiguousarray(np.asarray(frame)[..., :3], dtype=np.uint8)
    height, width = rgb.shape[:2]
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    hue = hsv[..., 0].astype(np.float32) * 2.0
    mask = (_hue_color_mask(hue, color)
            & (hsv[..., 1] >= _PLATE_MIN_SATURATION)
            & (hsv[..., 2] >= _PLATE_MIN_VALUE)
            & (hsv[..., 2] <= _PLATE_MAX_VALUE)).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    # a horizontal opening cuts thin vertical bars of the same colour (a
    # chair's edge-on backrest or leg in front of a far sign) off the plate
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,
                            np.ones((1, _PLATE_BAR_OPEN_PX), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    best = None
    for i in range(1, n):
        x, y, w, h, area = (int(v) for v in stats[i])
        if area < _PLATE_MIN_AREA_PX or w <= 0 or h <= 0:
            continue
        if y + h > _PLATE_MAX_BOTTOM_FRAC * height:
            continue
        fill = area / float(w * h)
        if fill < _PLATE_MIN_FILL:
            continue
        cut_top = y <= _PLATE_EDGE_PX
        if cut_top:
            if w < _PLATE_CUT_MIN_WIDTH_PX or h > _PLATE_CUT_MAX_ASPECT * w:
                continue
        else:
            aspect = h / float(w)
            if not (_PLATE_ASPECT_RANGE[0] <= aspect <= _PLATE_ASPECT_RANGE[1]):
                continue
            if h > _PLATE_MAX_HEIGHT_FRAC * height:
                continue
        score = 0.25 + 0.5 * min(1.0, fill)
        if best is None or area > best[0]:
            best = (area, score, (float(x), float(y), float(x + w), float(y + h)))
    if best is None:
        return None
    return Detection(class_name="stop sign", color=color, conf=best[1],
                     bbox=best[2])


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
                    f"conf={detection.conf:.2f} "
                    f"bbox=[{', '.join(f'{coord:.2f}' for coord in detection.bbox)}]"
                )
        return detections

    def detect_plate(self, frame: np.ndarray, color: str) -> Optional[Detection]:
        """Colour-plate fallback for a requested "stop sign" (see
        detect_color_plate). Logs an extra [PLATE] line; handout lines unchanged."""
        detection = detect_color_plate(frame, color)
        if detection is not None:
            print(f"[PLATE] class=stop sign color={color} "
                  f"conf={detection.conf:.2f} "
                  f"bbox=[{', '.join(f'{c:.2f}' for c in detection.bbox)}]")
        return detection

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
        del self._target_history[:-_TARGET_HISTORY_LIMIT]

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
        if region.size == 0 or color not in _COLOR_HUE_RANGES:
            return 0.0
        hsv = cv2.cvtColor(region, cv2.COLOR_RGB2HSV)
        hue = hsv[..., 0].astype(np.float32) * 2.0
        saturation = hsv[..., 1]
        value = hsv[..., 2]
        valid = ((saturation >= _MIN_COLOR_SATURATION)
                 & (value >= _MIN_COLOR_VALUE))
        matches = _hue_color_mask(hue, color)
        return float(np.count_nonzero(matches & valid) / region.shape[0] / region.shape[1])

    def _grounded_color(self, frame: np.ndarray, bbox: tuple) -> str:
        """Classify rendered RGB pixels inside the detection, independently of YOLO.

        Thin objects (chair frames, sign poles) leave most of their bbox to
        background, and this scene's floor and sky are blue, so background
        pixels must not vote:
          1. model the background from a ring of pixels just outside the bbox
             and drop bbox pixels close to it in hue and saturation;
          2. drop low-saturation, near-black and clipped-highlight pixels;
          3. take the dominant hue (histogram mode, wrapping at 0/360) of the
             pixels left over the FULL bbox, weighted towards its centre,
             and name it;
          4. too few pixels left -> "unknown" rather than a guess.
        """
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

        ring = max(_GROUND_RING_MIN_PX,
                   int(round(_GROUND_RING_FRAC * max(x2 - x1, y2 - y1))))
        ox1, oy1 = max(0, x1 - ring), max(0, y1 - ring)
        ox2, oy2 = min(width, x2 + ring), min(height, y2 + ring)
        rgb = frame[oy1:oy2, ox1:ox2, :3]
        if rgb.dtype != np.uint8:
            rgb = rgb.astype(np.float32)
            if rgb.max() <= 1.0:
                rgb *= 255.0
            rgb = np.clip(rgb, 0.0, 255.0).astype(np.uint8)

        # MuJoCo's renderer returns RGB with scene lighting already applied.
        hsv = cv2.cvtColor(np.ascontiguousarray(rgb), cv2.COLOR_RGB2HSV)
        hue = hsv[..., 0].astype(np.float32) * 2.0
        saturation = hsv[..., 1]
        value = hsv[..., 2]
        inside = np.zeros(hue.shape, dtype=bool)
        inside[y1 - oy1:y2 - oy1, x1 - ox1:x2 - ox1] = True
        chromatic = ((saturation >= _GROUND_MIN_SATURATION)
                     & (value >= _GROUND_MIN_VALUE)
                     & (value <= _GROUND_MAX_VALUE))

        # Background colour cells: a (hue, saturation) cell is background if
        # it is common in the ring AND at least as dense there as inside the
        # bbox. Floor and sky pass both tests; an object that sticks out of
        # its bbox is still denser inside, so its own colour is kept.
        n_hue = int(round(360.0 / _GROUND_BIN_FINE))
        hue_cell = (hue / _GROUND_BIN_FINE).astype(np.int32) % n_hue
        sat_cell = (saturation // 32).astype(np.int32)
        background = np.zeros((n_hue, 8), dtype=bool)
        n_ring = np.count_nonzero(~inside)
        if n_ring > 0:
            ring_density = _cell_density(hue_cell, sat_cell, ~inside & chromatic, n_ring)
            box_density = _cell_density(hue_cell, sat_cell, inside & chromatic,
                                        np.count_nonzero(inside))
            background = ((ring_density >= _GROUND_BG_MIN_FRAC)
                          & (ring_density >= _GROUND_BG_RATIO * box_density))

        # Hues with no colour name (the 170-220 deg gap: floor reflections)
        # can't be the answer, so they don't vote either.
        named = np.zeros(hue.shape, dtype=bool)
        for name in _COLOR_HUE_RANGES:
            named |= _hue_color_mask(hue, name)
        foreground = inside & chromatic & named & ~background[hue_cell, sat_cell]
        n_fg = int(np.count_nonzero(foreground))
        box_area = (x2 - x1) * (y2 - y1)
        if n_fg < max(_GROUND_MIN_FG_PX, _GROUND_MIN_FG_FRAC * box_area):
            if self.debug_dir is not None:
                print(f"[HSV] only {n_fg} foreground pixels -> unknown")
            return "unknown"

        # Dominant hue: circular histogram mode, smoothed with its neighbours
        # so a peak split across two bins still wins.
        # Pixels are weighted towards the bbox centre (Gaussian, sigma as a
        # fraction of the half-size): YOLO centres its box on the object it
        # found, so a second object caught at the box's edge votes less.
        fg_hue = hue[foreground]
        ys, xs = np.nonzero(foreground)
        dx = (xs + ox1 + 0.5 - 0.5 * (x1 + x2)) / (0.5 * (x2 - x1))
        dy = (ys + oy1 + 0.5 - 0.5 * (y1 + y2)) / (0.5 * (y2 - y1))
        weight = np.exp(-(dx * dx + dy * dy) / (2.0 * _GROUND_CENTER_SIGMA ** 2))
        n_bins = int(round(360.0 / _GROUND_HUE_BIN))
        hist = np.bincount((fg_hue / _GROUND_HUE_BIN).astype(np.int32) % n_bins,
                           weights=weight, minlength=n_bins)
        smooth = hist + 0.5 * (np.roll(hist, 1) + np.roll(hist, -1))
        peak = (int(np.argmax(smooth)) + 0.5) * _GROUND_HUE_BIN
        # refine: circular mean of the pixels within one bin of the peak
        diff = (fg_hue - peak + 180.0) % 360.0 - 180.0
        near = np.abs(diff) <= 1.5 * _GROUND_HUE_BIN
        dominant = float((peak + np.mean(diff[near])) % 360.0)
        color = "unknown"
        for name in _COLOR_HUE_RANGES:
            if _hue_color_mask(np.array([dominant]), name)[0]:
                color = name
                break
        if self.debug_dir is not None:
            print(f"[HSV] color={color} dominant_hue={dominant:.1f} "
                  f"n_fg_px={n_fg} share={near.mean():.2f}")
        return color


def _cell_density(hue_cell: np.ndarray, sat_cell: np.ndarray, mask: np.ndarray,
                  n_total: int) -> np.ndarray:
    """Fraction of n_total pixels in each (hue, saturation) cell, summed over
    the background colour tolerance (hue wraps around, saturation doesn't)."""
    n_hue = int(round(360.0 / _GROUND_BIN_FINE))
    hist = np.zeros((n_hue, 8), dtype=np.float64)
    np.add.at(hist, (hue_cell[mask], sat_cell[mask]), 1.0)
    k = int(round(_GROUND_BG_HUE_TOL / _GROUND_BIN_FINE))
    out = np.zeros_like(hist)
    for dh in range(-k, k + 1):
        rolled = np.roll(hist, dh, axis=0)
        for ds in range(-_GROUND_BG_SAT_TOL, _GROUND_BG_SAT_TOL + 1):
            if ds > 0:
                out[:, ds:] += rolled[:, :-ds]
            elif ds < 0:
                out[:, :ds] += rolled[:, -ds:]
            else:
                out += rolled
    return out / max(n_total, 1)


def _hue_color_mask(hue_degrees: np.ndarray, color: str) -> np.ndarray:
    mask = np.zeros(hue_degrees.shape, dtype=bool)
    for lower, upper in _COLOR_HUE_RANGES[color]:
        mask |= (hue_degrees >= lower) & (hue_degrees < upper)
    return mask


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
    