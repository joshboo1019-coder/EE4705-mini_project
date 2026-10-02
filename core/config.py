"""
config.py — Shared constants. Edit freely; these are just numbers, not
interfaces, so there's little risk of merge conflicts here. Still, agree
on units/keys as a group before changing anything below.
"""

# --- Task 2 (Student A) ----------------------------------------------------
SCENE_PATH = "assets/scenes/custom_scene.xml"
CAMERA_HZ = 15  # perception rate; render every N physics steps accordingly

# Ground-truth object positions in world (x, y) meters, keyed "<color>_<class>".
# Filled in by Student A when the scene is built (Task 2.iii). Used ONLY for
# the [FOUND] distance log / Task 4 evaluation — never for steering.
OBJECT_POSITIONS = {
    "green_chair": (-2.0, 2.0),
    "red_chair": (-2.0, -2.0),
    "orange_sports ball": (-3.5, 0.0),
    "red_stop sign": (-1.3, 0.0),
    "yellow_stop sign": (-4.5, 2.0),
    "green_stop sign": (-4.5, -2.0),
    "blue_chair": (3.45, 2.0),
}

# --- Task 3 (Student B) -----------------------------------------------------
LLM_SERVICE = "qwen-flash"   # swap to compare >=2 services, e.g. "gpt-5-nano"
LLM_TIMEOUT_S = 15

# --- Task 4 (Student C) -----------------------------------------------------
YOLO_MODEL = "yolo11n.pt"
YOLO_CONF_THRESHOLD = 0.2
YOLO_IMGSZ = 960  # inference size for 640x480 camera frames
FOUND_DETECTION_CONF_THRESHOLD = 0.1
FOUND_DISTANCE_M = 0.8
APPROACH_TIMEOUT_S = 180.0
SEARCH_TURN_DEG = 30.0
MAX_MISSES_BEFORE_LOST = 5
CENTER_TOLERANCE_PX = 20
APPROACH_VX = 0.3
APPROACH_STEP_S = 0.5
APPROACH_STUCK_TIMEOUT_S = 4.0
APPROACH_STUCK_PROGRESS_FRACTION = 0.25
REACQUIRE_MISSES = 3        # consecutive misses before starting a sweep
REACQUIRE_MAX_ATTEMPTS = 4  # sweeps before falling back to full rotation search
REACQUIRE_STRAFE_VY = 0.4   # m/s sideways
REACQUIRE_STRAFE_S = 1.0    # base sweep duration, grows with each attempt
