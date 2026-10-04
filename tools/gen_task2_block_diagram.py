# Owner: Student A (Task 2)
"""
tools/gen_task2_block_diagram.py -- generates the Task 2 control-pipeline
block diagram for the report (docs/task2_block_diagram.svg / .png).

Not part of the graded pipeline itself -- this is a one-off documentation
generator. Re-run it if the pipeline description changes (e.g. CAMERA_HZ
is retuned, or the observation dimension changes) so the diagram stays
accurate; it is NOT regenerated automatically.

Draws two swim lanes inside the single `_sim_loop` background thread
(skills/skills_real.py):
  1. Motion control pipeline: skill call -> observation build -> ONNX
     policy @ 50 Hz -> joint remap -> PD torque loop @ 200 Hz physics
     (decimation 4) -> MuJoCo physics -- with a feedback arrow back to
     the skill call for closed-loop turn()'s true-yaw correction.
  2. Camera/perception pipeline: same background thread -> offscreen
     render of dog_front_camera @ CAMERA_HZ (15 Hz) -> get_camera_frame()
     -> YOLO detection (Task 4) -> steer-to-center feedback into the
     skill call.

Renders to SVG by hand (no graphviz/cairosvg available in the sandbox
that wrote this), then rasterizes to PNG via a headless Chromium
screenshot (Playwright, pre-installed in this environment) so there is
a ready-to-embed PNG for Word/PowerPoint/PDF reports as well as a
scalable SVG.
"""

import html

CANVAS_W = 1560
CANVAS_H = 850

BOX_FILL_MOTION = "#dbe9ff"
BOX_STROKE_MOTION = "#2457a8"
BOX_FILL_CAMERA = "#dff6e0"
BOX_STROKE_CAMERA = "#2a8f3f"
BOX_FILL_SHARED = "#fff2cf"
BOX_STROKE_SHARED = "#b8860b"
LANE_FILL = "#f7f9fc"
TEXT_COLOR = "#1a1a1a"

svg_parts = []


def esc(s):
    return html.escape(s)


def box(x, y, w, h, lines, fill, stroke, font_size=14, bold_first=True):
    svg_parts.append(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" ry="10" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
    )
    n = len(lines)
    line_height = font_size + 6.5
    start_y = y + h / 2 - (n - 1) * line_height / 2 + font_size / 3
    for i, line in enumerate(lines):
        weight = "700" if (bold_first and i == 0) else "400"
        fs = font_size + 1.5 if (bold_first and i == 0) else font_size
        svg_parts.append(
            f'<text x="{x + w / 2}" y="{start_y + i * line_height}" '
            f'text-anchor="middle" font-family="Helvetica, Arial, sans-serif" '
            f'font-size="{fs}" font-weight="{weight}" fill="{TEXT_COLOR}">{esc(line)}</text>'
        )


def straight_arrow(x1, y1, x2, y2, color="#333333"):
    svg_parts.append(
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
        f'stroke-width="2.2" marker-end="url(#arrowhead)"/>'
    )


def curved_arrow(x1, y1, x2, y2, c1, c2, color="#333333"):
    path = f'M {x1} {y1} C {c1[0]} {c1[1]}, {c2[0]} {c2[1]}, {x2} {y2}'
    svg_parts.append(
        f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2.4" '
        f'marker-end="url(#arrowhead)"/>'
    )


def text(x, y, s, size=13, weight="400", color="#333333", anchor="start"):
    svg_parts.append(
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="Helvetica, Arial, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{color}">{esc(s)}</text>'
    )


# --- Background + defs ---------------------------------------------------
svg_parts.append(f'<rect x="0" y="0" width="{CANVAS_W}" height="{CANVAS_H}" fill="#ffffff"/>')
svg_parts.append(
    """
    <defs>
      <marker id="arrowhead" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
        <polygon points="0 0, 10 4, 0 8" fill="#333333"/>
      </marker>
    </defs>
    """
)

# Title
text(CANVAS_W / 2, 38, "Task 2 Control Pipeline — RealSkills / _sim_loop",
     size=24, weight="700", color=TEXT_COLOR, anchor="middle")
text(CANVAS_W / 2, 60,
     "Both lanes run inside the same background thread — one render/physics/policy iteration advances both every tick",
     size=13.5, color="#555555", anchor="middle")

# Outer thread container
svg_parts.append(
    f'<rect x="30" y="80" width="{CANVAS_W-60}" height="{CANVAS_H-110}" rx="14" ry="14" '
    f'fill="{LANE_FILL}" stroke="#aab4c2" stroke-width="2" stroke-dasharray="3,3"/>'
)
text(55, 108, "skills_real.py: _sim_loop (single background thread, started by RealSkills)",
     size=14.5, weight="700", color="#555555")

# === LANE 1: Motion control pipeline ======================================
lane1_y = 140
text(55, lane1_y - 12, "Motion control pipeline (every tick, 200 Hz physics)",
     size=15, weight="700", color=BOX_STROKE_MOTION)

bw, bh = 192, 100
gap = 26
x0 = 55
y1 = lane1_y

boxes1 = [
    ["Skill call", "move(vx,vy,wz,dur)", "turn(angle_deg)", "run_fast(x,y)"],
    ["Build observation", "46-dim state +", "6-frame history", "(build_single_obs)"],
    ["ONNX policy", "inference @ 50 Hz", "(every 4th", "physics step)"],
    ["Joint order remap", "IsaacGym ->", "MuJoCo leg/", "joint ordering"],
    ["PD torque loop", "@ 200 Hz physics", "(decimation = 4)"],
    ["MuJoCo physics step", "mj_step(model, data)", "robot actuation"],
]

xs1 = []
x = x0
for _lines in boxes1:
    xs1.append(x)
    x += bw + gap

for lines, bx in zip(boxes1, xs1):
    box(bx, y1, bw, bh, lines, BOX_FILL_MOTION, BOX_STROKE_MOTION)

for i in range(len(xs1) - 1):
    straight_arrow(xs1[i] + bw, y1 + bh / 2, xs1[i + 1], y1 + bh / 2)

# qpos readback box, directly under the physics box
fb_y = y1 + bh + 55
qpos_w, qpos_h = 235, 55
qpos_x = xs1[-1] + bw - qpos_w
box(qpos_x, fb_y, qpos_w, qpos_h,
    ["mj_data.qpos", "atan2(2(wz*xy), 1-2(y^2+z^2))"],
    BOX_FILL_SHARED, BOX_STROKE_SHARED, font_size=12.5)
straight_arrow(xs1[-1] + bw - 40, y1 + bh, qpos_x + qpos_w - 40, fb_y, color="#555555")
text(qpos_x + qpos_w / 2, fb_y - 8, "reads true yaw from", size=11.5, anchor="middle", color="#555555")

# Feedback curves back to the Skill call box, both landing in the gap
# between the two lanes so their labels never cross box text.
gap_top = fb_y + qpos_h + 15
gap_bot = lane1_y + bh + 300  # placeholder, replaced once lane2_y is known

skill_bottom_x = xs1[0] + bw * 0.35
skill_bottom_x2 = xs1[0] + bw * 0.65
skill_bottom_y = y1 + bh

curved_arrow(
    qpos_x + 30, fb_y + qpos_h,
    skill_bottom_x2, skill_bottom_y,
    c1=(qpos_x - 250, fb_y + 170),
    c2=(skill_bottom_x2 + 350, skill_bottom_y + 130),
    color="#b8860b",
)

# === LANE 2: Camera / perception pipeline =================================
lane2_y = fb_y + qpos_h + 150
text(55, lane2_y - 12, "Camera / perception pipeline (same thread, every tick, throttled to CAMERA_HZ)",
     size=15, weight="700", color=BOX_STROKE_CAMERA)

bw2, bh2 = 225, 100
gap2 = 24
boxes2 = [
    ["Rate throttle", "render only every", "Nth tick so renders", "land at CAMERA_HZ = 15 Hz"],
    ["Offscreen render", "dog_front_camera via its", "own mujoco.Renderer", "(separate from viewer/panel)"],
    ["Publish frame", "get_camera_frame()", "returns latest published", "frame (non-blocking)"],
    ["YOLO detection", "(Task 4 / Student C)", "bbox + class + confidence"],
    ["_steer_to_center()", "bbox-offset -> proportional", "wz steering command"],
]

xs2 = []
x = x0
for _lines in boxes2:
    xs2.append(x)
    x += bw2 + gap2

for lines, bx in zip(boxes2, xs2):
    box(bx, lane2_y, bw2, bh2, lines, BOX_FILL_CAMERA, BOX_STROKE_CAMERA)

for i in range(len(xs2) - 1):
    straight_arrow(xs2[i] + bw2, lane2_y + bh2 / 2, xs2[i + 1], lane2_y + bh2 / 2)

# Feedback curve: steer -> skill call, landing at the other point under Skill call
curved_arrow(
    xs2[-1] + bw2 / 2, lane2_y,
    skill_bottom_x, skill_bottom_y,
    c1=(xs2[-1] + bw2 / 2 - 300, lane2_y - 170),
    c2=(skill_bottom_x + 300, skill_bottom_y + 170),
    color="#2a8f3f",
)

# Labels for both feedback curves, placed in the open gap between lanes
# (not attached to curve midpoints, so they can't collide with box text).
label_y1 = gap_top + 18
label_y2 = label_y1 + 20
text(skill_bottom_x2 + 60, label_y1,
     "closed-loop turn(): reads true yaw back, corrects until |error| < 2 deg",
     size=12.5, color="#8a6d00")
text(skill_bottom_x2 + 60, label_y2,
     "steering: _steer_to_center()'s wz command feeds into the next move()/run_fast() call",
     size=12.5, color="#1f6b30")

# Legend / notes box at the bottom
notes_y = lane2_y + bh2 + 50
svg_parts.append(
    f'<rect x="55" y="{notes_y}" width="{CANVAS_W-130}" height="175" rx="10" ry="10" '
    f'fill="#ffffff" stroke="#cccccc" stroke-width="1.5"/>'
)
notes = [
    "Why decimation = 4: physics steps at 200 Hz but the ONNX policy only needs fresh actions at 50 Hz "
    "(200 / 4 = 50) -- the PD torque loop re-applies the same policy output across the 4 intermediate physics steps.",
    "Why CAMERA_HZ = 15: inside the handout's recommended 10-20 Hz range -- fast enough that steer-to-center sees "
    "a near-continuous bbox signal, but far below the 50 Hz policy / 200 Hz physics rate so the offscreen render "
    "call doesn't compete with the control loop for CPU time (see core/config.py's own comment on CAMERA_HZ).",
    "Why the joint remap exists: the ONNX policy was trained in IsaacGym, whose leg/joint ordering differs from "
    "MuJoCo's -- actions must be permuted to the right joint before the PD loop applies them, or torques go to the wrong leg.",
    "turn() is closed-loop (reads true yaw back from mj_data.qpos and corrects); move() and run_fast() are open-loop "
    "velocity commands with no position feedback inside this diagram's loop -- run_fast() adds its own accelerate/"
    "cruise/brake ramp but still no obstacle avoidance.",
]
ny = notes_y + 24
for note in notes:
    words = note.split(" ")
    line = ""
    lines_out = []
    for w in words:
        test_line = (line + " " + w).strip()
        if len(test_line) > 150:
            lines_out.append(line)
            line = w
        else:
            line = test_line
    if line:
        lines_out.append(line)
    text(75, ny, "• " + lines_out[0], size=12.5, color="#333333")
    ny += 16
    for extra in lines_out[1:]:
        text(92, ny, extra, size=12.5, color="#333333")
        ny += 16
    ny += 6

svg = (
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W}" height="{CANVAS_H}" '
    f'viewBox="0 0 {CANVAS_W} {CANVAS_H}">' + "".join(svg_parts) + "</svg>"
)

out_svg = "docs/task2_block_diagram.svg"
with open(out_svg, "w") as f:
    f.write(svg)
print(f"wrote {out_svg}")
