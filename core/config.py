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
    "green_chair": (2.0, 1.0),
    "red_chair": (2.0, -1.0),
    "orange_sports ball": (3.5, 0.0),
}

# --- Task 3 (Student B) -----------------------------------------------------
LLM_SERVICE = "qwen-flash"   # swap to compare >=2 services, e.g. "gpt-5-nano"
LLM_TIMEOUT_S = 15

# --- Task 4 (Student C) -----------------------------------------------------
YOLO_MODEL = "yolo11n.pt"
YOLO_CONF_THRESHOLD = 0.5
FOUND_DISTANCE_M = 0.80
APPROACH_TIMEOUT_S = 60.0
SEARCH_TURN_DEG = 30.0
MAX_MISSES_BEFORE_LOST = 5
CENTER_TOLERANCE_PX = 20
APPROACH_VX = 0.3
APPROACH_STEP_S = 0.5
