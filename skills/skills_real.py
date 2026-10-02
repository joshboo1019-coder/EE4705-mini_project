"""
skills_real.py — STUDENT A OWNS THIS FILE. Task 2 (60%).

Implements SkillsAPI on top of the example platform
(https://github.com/aoqianz/quadruped_mujoco).

As long as RealSkills satisfies core.interfaces.SkillsAPI, Student B's
executor and Student C's navigation code need zero changes.

Also owns: scene building (assets/scenes/custom_scene.xml — see
assets/scenes/README.md), and the background camera-capture thread.

--------------------------------------------------------------------------
How this fits together with eg/play.py
--------------------------------------------------------------------------
Rather than re-implementing the joint remapping / PD control / ONNX
observation building from scratch (easy to get subtly wrong), this module
imports the pure, reusable pieces straight out of the platform's own
`eg/play.py` (they're defined at module scope, outside its
`if __name__ == "__main__":` guard, so they're safe to import):

    quat_rotate_inverse, ObsHistoryBuffer, build_single_obs, reset_robot,
    MUJOCO_TO_ISAAC, ISAAC_TO_MUJOCO, DEFAULT_ANGLES_ISAAC,
    DEFAULT_ANGLES_MUJOCO, tau limits, MAP_SPECS, ROBOT_CAMERAS,
    CAMERA_OPTIONS, DEFAULT_CONFIG, DEFAULT_ONNX, DEFAULT_ROBOT_XML

What this module does NOT reuse from play.py, because it needs different
behavior than a human-at-a-keyboard demo:
  - command sourcing: play.py reads a physical/browser keyboard.
    RealSkills is driven programmatically by move()/turn()/stop() calls
    from the executor, so it keeps its own thread-safe "current command"
    array and a background thread that steps physics+policy continuously
    at the real-time-locked rate — move()/turn() just set that shared
    command and block, they don't run their own physics loop.
  - evdev keyboard capture: nothing here reads a physical keyboard, since
    move()/turn()/stop() are called programmatically. This module runs
    headless (no viewer) by default so it works identically on any
    machine and over SSH/CI; the standalone test harness at the bottom
    can optionally open a visual -- the browser control panel (`--gui`,
    the team's confirmed-working path) or the native MuJoCo window
    (`--native`, untested here but worth trying since the one documented
    WSL2 crash was specifically on-keypress and nothing in this codebase
    ever presses a key into that window).

--------------------------------------------------------------------------
Setting PLATFORM_ROOT
--------------------------------------------------------------------------
This file needs to find your clone of quadruped_mujoco on disk. Point the
QUADRUPED_MUJOCO_ROOT environment variable at it, e.g. (bash):

    export QUADRUPED_MUJOCO_ROOT=~/EE4705-mini_project/quadruped_mujoco

or edit PLATFORM_ROOT below to a hardcoded path. If neither is set, this
module tries a couple of common relative locations before giving up with a
clear error.

Test this file completely on its own before anyone else needs it (run
from the project root so the `core` package resolves):
    python -m skills.skills_real            # headless, typed-command test
    python -m skills.skills_real --gui      # browser control panel at
                                             # http://localhost:8765
    python -m skills.skills_real --native   # native MuJoCo window (try me)
"""

import math
import os
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import numpy as np

from core.interfaces import SkillsAPI
from core.schema import RobotPose
from core import config

# ---------------------------------------------------------------------------
# Locate + import the platform. We only need module-level helpers/constants
# from eg/play.py (no code inside its __main__ guard runs on import), plus
# runtime_control's public API.
# ---------------------------------------------------------------------------


def _find_platform_root() -> Path:
    env = os.environ.get("QUADRUPED_MUJOCO_ROOT")
    candidates = []
    if env:
        candidates.append(Path(env))
    here = Path(__file__).resolve().parent
    candidates += [
        here.parent / "quadruped_mujoco",           # sibling of project root
        here.parent.parent / "quadruped_mujoco",     # sibling of project root's parent
        Path.home() / "EE4705-mini_project" / "quadruped_mujoco",
    ]
    for c in candidates:
        if (c / "eg" / "play.py").is_file():
            return c
    raise RuntimeError(
        "Could not locate your quadruped_mujoco clone.\n"
        "Set the QUADRUPED_MUJOCO_ROOT environment variable to its path, e.g.\n"
        "    export QUADRUPED_MUJOCO_ROOT=~/EE4705-mini_project/quadruped_mujoco\n"
        f"(tried: {', '.join(str(c) for c in candidates)})"
    )


PLATFORM_ROOT = _find_platform_root()
for p in (str(PLATFORM_ROOT), str(PLATFORM_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

import mujoco  # noqa: E402  (only available once PLATFORM_ROOT/venv is on sys.path)
import onnxruntime as ort  # noqa: E402

from eg import play as platform  # noqa: E402
from runtime_control import (  # noqa: E402
    RuntimeScene,
    make_runtime_config,
    compute_pd_torques,
    scale_torque_limits,
    MotorCommandDelay,
)

# NOTE: play.py defines these three only inside its own
# `if __name__ == "__main__":` block, so they are NOT importable as
# HISTORY_LEN etc. (that's the AttributeError you'd get if you
# tried). Their values come straight from play.py's source, just declared
# here instead so they're actually reachable on import.
NUM_ONE_STEP_OBS = 46
HISTORY_LEN = 6
NUM_ACTIONS = 12

CAMERA_HEIGHT_PX = 480
CAMERA_WIDTH_PX = 640

# This file lives at <project_root>/skills/skills_real.py, so its own
# location pins down the project root regardless of the CURRENT WORKING
# DIRECTORY the interpreter happens to be launched from. That matters
# because config.SCENE_PATH ("assets/scenes/custom_scene.xml") is a
# relative path: resolving it against cwd instead of this would silently
# fall back to the platform's bundled (empty) rc26_track map any time
# something is run from outside the project root -- e.g. `cd tools &&
# python visual_test_task2.py`, or an IDE "Run" button whose cwd isn't the
# project root -- with no error, just a scene with none of the graded
# objects in it.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------


class RealSkills(SkillsAPI):
    def __init__(self, scene_path: str = config.SCENE_PATH, gui: bool = False,
                 default_camera: Optional[str] = None,
                 native_viewer: bool = False):
        """Builds the MuJoCo scene, loads the ONNX policy, and starts a
        persistent background thread that keeps physics+policy stepping at
        the platform's real-time-locked rate. move()/turn()/stop() just
        read/write the shared command array that thread consumes; they
        never step physics themselves, so the robot keeps standing/moving
        between calls exactly like it would under a human at the keyboard.

        default_camera: which browser-panel camera is selected when the
        panel first loads (gui=True). One of platform.CAMERA_OPTIONS's
        keys -- "tracking" (third-person follow, the platform's own
        default), "dog_front_camera" (onboard front/first-person),
        "dog_rear_overhead_camera", or "dog_top_camera". None (default)
        leaves the platform's own default ("tracking") unchanged. The
        panel's camera dropdown still lists all of them regardless --
        this only picks which one is selected before you touch it.
        Ignored when native_viewer=True (the native window has no camera
        dropdown; see setup_tracking_camera below).

        native_viewer: open the native MuJoCo (GLFW) window instead of the
        browser panel, mutually exclusive with gui (native_viewer=True
        forces the browser panel off, since running both doubles the
        render work and the platform's own viewer_context() only allows
        one at a time). Confirmed on the team's WSL2 machine to run a
        full scripted move/turn/strafe sequence and exit cleanly on
        Ctrl+C. An earlier note here warned that Task 4 (anything calling
        get_camera_frame()) could time out under native_viewer=True due to
        a suspected GL-context conflict freezing the offscreen camera
        feed -- that theory is now DISPROVEN: a real failed run reproduced
        the exact same timeout with native_viewer=False (gui=True) too,
        and with no [CAMERA] render failed line at all, so the offscreen
        renderer was never the problem. The actual cause was a bug in
        perception/navigation.py's _steer_to_center() (too-short move()
        duration for the walking policy to act on before it got reset/
        damped back to zero) -- unrelated to which viewer is open, now
        fixed there. native_viewer is fine to use for any task, including
        Task 4. _maybe_render_camera still logs a rate-limited [CAMERA]
        render failed line if the offscreen renderer genuinely does fail
        for some other reason -- that diagnostic is still worth watching
        for, it just isn't implicated in the Task 4 timeout bug above.
        """
        # play.py loads its own yaml.dog.yaml directly at module/main scope
        # rather than through a public loader function, so we read the same
        # bundled file the same way here.
        import yaml

        with open(platform.DEFAULT_CONFIG, "r") as f:
            self._cfg = yaml.safe_load(f)

        self.simulation_dt = float(self._cfg["simulation_dt"])
        self.control_decimation = int(self._cfg["control_decimation"])
        self.kps = np.array(self._cfg["kps"], dtype=np.float64)
        self.kds = np.array(self._cfg["kds"], dtype=np.float64)
        self.action_scale = float(self._cfg["action_scale"])
        self.ang_vel_scale = float(self._cfg["ang_vel_scale"])
        self.dof_pos_scale = float(self._cfg["dof_pos_scale"])
        self.dof_vel_scale = float(self._cfg["dof_vel_scale"])
        self.cmd_scale = np.array(self._cfg["cmd_scale"], dtype=np.float64)
        self.clip_obs = float(self._cfg.get("clip_obs", 100.0))

        # Use the caller-supplied scene (Student A's custom map with the
        # graded objects) if it exists; otherwise fall back to the
        # platform's own bundled rc26_track so this file still runs before
        # the custom scene is built (Task 2.iii).
        #
        # scene_path is normally config.SCENE_PATH, a path RELATIVE to the
        # project root -- resolve it against PROJECT_ROOT (this file's own
        # location), not against whatever the current working directory
        # happens to be, so the custom scene loads correctly no matter
        # where the interpreter was launched from. An absolute scene_path
        # (if a caller ever passes one) is used as-is.
        map_specs = dict(platform.MAP_SPECS)
        custom = Path(scene_path)
        if not custom.is_absolute():
            custom = (PROJECT_ROOT / custom).resolve()
        if custom.is_file():
            from runtime_control import MapSpec

            map_specs = {"custom_scene": MapSpec(custom)}
            default_map = "custom_scene"
            print(f"[SCENE] using custom scene: {custom}")
        else:
            default_map = "rc26_track"
            print(f"[SCENE] custom scene not found at {custom} -- falling "
                  f"back to the platform's bundled rc26_track (no graded "
                  f"objects). If that's not what you expected, check that "
                  f"assets/scenes/custom_scene.xml exists in the project.")

        if native_viewer and gui:
            raise ValueError(
                "native_viewer=True and gui=True can't both be set -- the "
                "platform only supports one display at a time (running "
                "both renders every frame twice). Pick one."
            )
        # The browser panel (RuntimeControl's own gui flag) and the native
        # GLFW window are mutually exclusive display paths; native_viewer
        # forces the browser panel off here so scene.viewer(browser_only=
        # False) below is the only thing rendering.
        # Trunk-height command range the ONNX policy was trained/tuned over
        # (passed to the browser panel's own height slider too, via
        # height_range= below) -- stored so crouch()/stand()/set_height()
        # can clamp into it instead of sending the policy a height_cmd it
        # was never trained on.
        self._height_range = (0.28, 0.35)

        runtime_config = make_runtime_config(
            gui=gui and not native_viewer,
            title="MiniLab 1.3 — RealSkills",
            maps={k: k for k in map_specs},
            map_spawns={
                name: {"position": [0.0, 0.0, 0.42], "quaternion": [1.0, 0.0, 0.0, 0.0]}
                for name in map_specs
            },
            kp=float(self.kps[0]),
            kd=float(self.kds[0]),
            torque_limit=platform.TAU_LIMIT_CALF,
            initial_position=(0.0, 0.0, 0.42),
            initial_quaternion=(1.0, 0.0, 0.0, 0.0),
            command=(1.0, 1.0, 1.0, 0.25),
            height_range=self._height_range,
            cameras=platform.CAMERA_OPTIONS,
            port=8765,
        )

        # make_runtime_config() picks its own default_camera as the FIRST
        # key of the `cameras` dict it was given (platform.CAMERA_OPTIONS,
        # whose first key is "tracking" -- third-person). Override that
        # choice post-hoc, rather than reordering CAMERA_OPTIONS itself, so
        # every other camera stays selectable in the panel's dropdown; this
        # only changes which one is selected when the panel first loads.
        if default_camera is not None:
            if default_camera not in runtime_config["runtime_ui"]["cameras"]:
                raise ValueError(
                    f"default_camera={default_camera!r} is not one of "
                    f"{list(runtime_config['runtime_ui']['cameras'])}"
                )
            runtime_config["runtime_ui"]["default_camera"] = default_camera

        self._scene = RuntimeScene(
            robot_xml=platform.DEFAULT_ROBOT_XML,
            map_specs=map_specs,
            runtime_config=runtime_config,
            robot_body_name="trunk",
            robot_cameras=platform.ROBOT_CAMERAS,
            dynamic_obstacle_map="dynamic_obstacles" if "dynamic_obstacles" in map_specs else None,
            output_name="minilab_scene.xml",
        )
        self._scene.open()
        self._model = self._scene.model
        self._model.opt.timestep = self.simulation_dt
        self._data = self._scene.data
        self._runtime = self._scene.runtime

        # Native viewer setup. No key_callback is passed (None), since
        # nothing here ever drives it by keyboard -- the whole point of
        # trying this path is that our test scripts don't press keys.
        # launch_passive() opens a real GLFW window and can fail (missing
        # display, no GLFW libs, etc.) or -- per this file's WSL2 history --
        # crash outright; either way that shouldn't take the whole harness
        # down silently; a clean ImportError/RuntimeError is caught and
        # reported, but a genuine native segfault is a process-level crash
        # no try/except here can catch. That's the actual risk being taken
        # by opting into native_viewer=True.
        self._native_viewer_cm = None
        self._native_viewer = None
        if native_viewer:
            try:
                self._native_viewer_cm = self._scene.viewer(
                    browser_only=False, key_callback=None
                )
                self._native_viewer = self._native_viewer_cm.__enter__()
                # default_camera picks a fixed onboard camera (e.g.
                # "dog_front_camera") the same way it does for the browser
                # panel; "tracking" (or None) falls back to a third-person
                # follow cam, same framing as play.py's non-gui default.
                if default_camera and default_camera != "tracking":
                    cam_id = mujoco.mj_name2id(
                        self._model, mujoco.mjtObj.mjOBJ_CAMERA, default_camera
                    )
                    if cam_id < 0:
                        raise ValueError(
                            f"default_camera={default_camera!r} is not a "
                            f"camera in the composed model"
                        )
                    self._native_viewer.cam.type = mujoco.mjtCamera.mjCAMERA_FIXED
                    self._native_viewer.cam.fixedcamid = cam_id
                else:
                    from runtime_control.integration import setup_tracking_camera
                    setup_tracking_camera(
                        self._native_viewer, self._model, "trunk",
                        distance=2.0, azimuth=135.0, elevation=-25.0,
                    )
                print("[VIEWER] native MuJoCo window opened (no keyboard "
                      "wired up -- close the window or Ctrl+C to stop).")
            except Exception as exc:
                print(f"[VIEWER] native viewer failed to open ({exc!r}); "
                      f"continuing headless. Use gui=True for the browser "
                      f"panel instead.")
                self._native_viewer_cm = None
                self._native_viewer = None

        platform.reset_robot(self._model, self._data, platform.DEFAULT_ANGLES_MUJOCO)

        # ONNX policy
        onnx_path = str(platform.DEFAULT_ONNX)
        self._policy = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
        self._policy_in = self._policy.get_inputs()[0].name
        self._policy_out = self._policy.get_outputs()[0].name

        self._obs_history = platform.ObsHistoryBuffer(
            HISTORY_LEN, NUM_ONE_STEP_OBS
        )
        self._last_action_isaac = np.zeros(NUM_ACTIONS, dtype=np.float64)

        # Warm up the observation history with the standing pose at zero cmd,
        # exactly like play.py does before its main loop.
        for _ in range(HISTORY_LEN):
            obs = self._warmup_obs()
            self._obs_history.push(obs)

        # Built directly rather than pulled from play.py (there it's an
        # inline module-level array, not an importable function): hip,
        # thigh, calf per leg, in MuJoCo joint order (FL, FR, RR, RL).
        self._tau_limits_mujoco = self._build_tau_limits()

        self._motor_delay = MotorCommandDelay(self.simulation_dt)

        # Shared, thread-safe state.
        self._cmd_lock = threading.Lock()
        self._cmd = np.zeros(3, dtype=np.float64)  # vx, vy, wz — physical units
        self._height_cmd = 0.25

        self._pose_lock = threading.Lock()
        self._pose = RobotPose(x=0.0, y=0.0, yaw_deg=0.0)

        self._latest_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()

        self._sim_time = 0.0
        self._sim_time_lock = threading.Lock()

        self._stop_event = threading.Event()
        self._count = 0

        # One background thread does both physics/policy stepping AND
        # camera rendering, since both need the same mj_data and mujoco
        # isn't thread-safe to touch from two threads concurrently.
        # before: self._renderer = mujoco.Renderer(self._model, height=240, width=320)
        self._renderer = mujoco.Renderer(self._model, height=CAMERA_HEIGHT_PX, width=CAMERA_WIDTH_PX)
        self._render_period = 1.0 / config.CAMERA_HZ
        self._next_render_time = 0.0
        self._last_render_error_log = 0.0

        self._sim_thread = threading.Thread(target=self._sim_loop, daemon=True)
        self._sim_thread.start()

        # Give the sim thread a moment to publish a first pose/frame so
        # get_robot_pose()/get_camera_frame() don't hand back zeros the
        # instant __init__ returns.
        time.sleep(max(0.2, 5 * self.simulation_dt))

    # ------------------------------------------------------------------
    # SkillsAPI
    # ------------------------------------------------------------------

    def move(self, vx: float, vy: float, wz: float, duration: float) -> None:
        """Push (vx, vy, wz) into the shared command for `duration` seconds
        of SIMULATED time, then zero it. Physics/policy keep stepping in
        the background thread throughout — this call only blocks the
        caller, it never blocks the sim."""
        with self._cmd_lock:
            self._cmd[:] = (vx, vy, wz)

        target = self._get_sim_time() + duration
        while self._get_sim_time() < target and not self._stop_event.is_set():
            time.sleep(0.01)

        with self._cmd_lock:
            self._cmd[:] = (0.0, 0.0, 0.0)

    def turn(self, angle_deg: float) -> None:
        """Closed-loop turn: repeatedly read true yaw via get_robot_pose(),
        drive wz proportionally to the remaining signed error, stop within
        tolerance (or after a timeout so a bad gain never hangs forever),
        then print the required [TURN] line."""
        start_yaw = self.get_robot_pose().yaw_deg
        target_yaw = start_yaw + angle_deg

        tolerance_deg = 2.0
        # Retuned from 0.1 -> 1.0 after on-robot testing: at kp_turn=1.0 the
        # command saturates to full power (wz=+-1.0, matching what a held
        # 'q'/'e' keypress sends in play.py's get_commands()) for any error
        # above ~1 deg, i.e. near-bang-bang control with only the last
        # degree or so of proportional ramp-down. Empirically this converges
        # reliably to within ~2 deg of target across repeated trials (see
        # Task 2 report), so it's kept over the gentler 0.1 ramp.
        kp_turn = 1.0
        max_wz = 1.0
        # Generous ceiling so a slow but correct turn still finishes instead
        # of timing out early, even though kp_turn=1.0 usually converges
        # well before this deadline.
        timeout_s = max(5.0, abs(angle_deg) / 6.0 + 3.0)

        deadline = self._get_sim_time() + timeout_s
        final_error = angle_deg

        while self._get_sim_time() < deadline and not self._stop_event.is_set():
            current_yaw = self.get_robot_pose().yaw_deg
            error = _wrap_deg(target_yaw - current_yaw)
            final_error = error
            if abs(error) <= tolerance_deg:
                break
            wz = max(-max_wz, min(max_wz, kp_turn * error))
            with self._cmd_lock:
                self._cmd[:] = (0.0, 0.0, wz)
            time.sleep(0.02)

        with self._cmd_lock:
            self._cmd[:] = (0.0, 0.0, 0.0)

        print(f"[TURN] target={angle_deg:.1f} deg final_error={final_error:.1f} deg")

    def stop(self) -> None:
        with self._cmd_lock:
            self._cmd[:] = (0.0, 0.0, 0.0)

    # ------------------------------------------------------------------
    # Body-height control (crouch/stand). Not part of core.interfaces.
    # SkillsAPI -- Task 3/4 never need it, and that interface is frozen by
    # group agreement (core/schema.py's own header) -- so this is a
    # RealSkills-only extra, called directly if you want it (e.g. from
    # your own keyboard harness commands or a standalone demo script),
    # not through the executor/LLM command pipeline.
    #
    # height_cmd is a feature the ONNX policy already reads every control
    # tick (see build_single_obs's height_cmd= argument in _sim_loop and
    # _warmup_obs) -- self._height_cmd was previously set once at __init__
    # and never touched again, so the policy was always being asked for
    # the same 0.25 m stance. These methods are the first thing to
    # actually change it at runtime.
    #
    # Which direction is "crouch" vs "stand" (larger height_cmd = taller
    # stance, smaller = crouched) is inferred from height_range being
    # handed to the platform as a trunk-height range in meters, and 0.25
    # (the old fixed default) sitting near its lower-middle -- consistent
    # with 0.25 being an ordinary walking stance rather than either
    # extreme. If crouch() looks like it's standing taller instead of
    # crouching down when you watch the browser panel, the two are
    # simply swapped from what was guessed here; flip which bound each
    # method targets.
    #
    # height_range's lower bound was originally 0.20, then raised to
    # 0.28 after a real run (see set_height()'s own docstring below)
    # showed crouch() targeting 0.20 barely moved the trunk at all even
    # with extra settle time -- i.e. 0.20 was below a stance the
    # policy/PD loop can actually hold, not just a slow transition. 0.28
    # is a real-run-confirmed reachable floor; if a future run shows
    # otherwise, raise it further rather than assuming 0.20-0.27 works.
    def set_height(self, height_cmd: float, settle_s: float = 1.0,
                   step_size: float = 0.02, step_hold_s: float = 0.3) -> None:
        """Change the commanded trunk height and hold still for `settle_s`
        simulated seconds so the robot actually reaches the new stance
        before this returns, rather than reporting done mid-transition.
        Clamped into self._height_range so an out-of-range value never
        reaches a policy that was never trained on it.

        RAMPED, not a single instantaneous jump: a real run showed stand()
        (0.25->0.35, legs straightening) tracking its target closely, while
        crouch() (0.25->0.20, legs bending under load) moved almost nothing
        even when the target was held for several extra seconds through a
        following turn() call -- ruling out "just needed more settle time".
        That asymmetry is consistent with a big one-shot downward setpoint
        change being harder for the policy/PD loop to track than an
        upward one, so instead of writing self._height_cmd once, this
        walks it toward the target in `step_size` increments (default
        0.02 m), holding `step_hold_s` sim-seconds at each intermediate
        step before taking the next one, then finishes with the original
        full `settle_s` hold at the final target. Prints one [HEIGHT] line
        per intermediate step plus the final one, each with the commanded
        value and the trunk's actual measured world-frame z
        (self._data.qpos[2]) at that point -- so if it still plateaus
        short of the target with small steps, the per-step lines show
        exactly where it stalls, which points at a hard torque/stability
        limit rather than a step-size problem (in which case, note that in
        the report rather than keep shrinking step_size)."""
        height_cmd = max(self._height_range[0], min(self._height_range[1], height_cmd))
        z_before = float(self._data.qpos[2])

        with self._cmd_lock:
            self._cmd[:] = (0.0, 0.0, 0.0)

        start = self._height_cmd
        distance = height_cmd - start
        n_steps = max(1, int(abs(distance) / step_size))
        for i in range(1, n_steps + 1):
            intermediate = start + distance * (i / n_steps)
            self._height_cmd = intermediate

            hold_until = self._get_sim_time() + step_hold_s
            while self._get_sim_time() < hold_until and not self._stop_event.is_set():
                time.sleep(0.01)

            z_step = float(self._data.qpos[2])
            print(f"[HEIGHT] step {i}/{n_steps} target={intermediate:.2f} m "
                  f"trunk_z={z_step:.2f} m")

        # Final hold at the exact target, in case rounding in the ramp
        # above left height_cmd slightly off it.
        self._height_cmd = height_cmd
        target_time = self._get_sim_time() + settle_s
        while self._get_sim_time() < target_time and not self._stop_event.is_set():
            time.sleep(0.01)

        z_after = float(self._data.qpos[2])
        print(f"[HEIGHT] target={height_cmd:.2f} m trunk_z_before={z_before:.2f} m "
              f"trunk_z_after={z_after:.2f} m")

    def crouch(self) -> None:
        """Command the lower end of self._height_range -- see the class
        comment above set_height() for why this is the guessed "crouch"
        direction and how to flip it if a real run shows otherwise."""
        self.set_height(self._height_range[0])

    def stand(self) -> None:
        """Command the upper end of self._height_range -- see the class
        comment above set_height() for why this is the guessed "stand"
        direction and how to flip it if a real run shows otherwise."""
        self.set_height(self._height_range[1])

    def get_trunk_height(self) -> float:
        """Diagnostic helper: the trunk's actual measured world-frame z
        (self._data.qpos[2]), independent of what height_cmd currently
        is. Not part of core.interfaces.SkillsAPI, same as crouch()/
        stand() -- added specifically so a test script can read the
        trunk's real physical height before ever calling set_height(),
        to check whether it naturally settles to some resting height on
        its own (e.g. after a reset) regardless of height_cmd, rather
        than only being able to compare before/after a height command
        the way set_height()'s own [HEIGHT] print does."""
        return float(self._data.qpos[2])

    # ------------------------------------------------------------------
    # Terrain traversal (stairs / rough terrain). Not part of core.
    # interfaces.SkillsAPI, same reasoning as crouch()/stand()/
    # get_trunk_height() above -- that interface is frozen by group
    # agreement, and Task 2/3/4's executor/navigation code never calls
    # these. Ported in from tools/visual_test_rough_terrain.py (where
    # this logic was first written and verified against two real runs on
    # this project's own custom_scene.xml staircases/rubble patch -- see
    # that script's own module docstring for the full history) so any
    # script can reuse it directly off a RealSkills instance instead of
    # reimplementing it.
    #
    # climb_stairs() and cross_rough_terrain() are both thin wrappers
    # around the same engine, _walk_terrain_segment_loop(), which
    # repeatedly:
    #   1. re-faces the target waypoint via turn() before EVERY segment
    #      (not just once before the whole walk -- a real run showed a
    #      single step-edge yaw nudge otherwise goes uncorrected and
    #      compounds into the robot drifting off the structure's own
    #      side edge before reaching the far end). _face_waypoint() also
    #      OPTIONALLY supports an explicit cross-track recentering bias
    #      (width_axis/width_center + recenter_gain) for exactly this
    #      drift -- but it is OFF by default (recenter_gain=0.0) after
    #      three real runs on stairs_steep's own crossing told a
    #      consistent story: the plain version (no recentering) drifted
    #      from y=6.02 toward the edge but still climbed real height
    #      (trunk_z up to ~0.65 m) before a safe, caught edge_drift abort
    #      at y=5.43 (real edge 5.25); turning recentering ON, at TWO
    #      different gains/caps, both made things WORSE, not better --
    #      one triggered a stumble (trunk_z jumped +0.176 m in one
    #      segment) that ended in "stuck", and the other stalled the
    #      robot almost immediately (barely any x progress at all across
    #      4 straight segments, trunk_z never climbing past 0.29 m --
    #      never even making it over the first riser). Interrupting a
    #      steep-riser climbing gait with extra turn commands, even small
    #      capped ones, looks to hurt more than the drift itself did, so
    #      recentering is now opt-in (pass recenter_gain > 0 explicitly)
    #      rather than default-on. See _face_waypoint's own comment for
    #      the full mechanism and all three runs' exact numbers;
    #   2. walks one short segment with move();
    #   3. logs pose + trunk height, flagging a single-segment trunk_z
    #      DELTA above max_height_jump as a likely stumble/launch (NOT an
    #      absolute height check -- get_trunk_height() is the trunk's
    #      absolute world-frame z, so standing on an elevated staircase
    #      peak reads a high-but-correct value on its own; only a sudden
    #      single-segment CHANGE is actually anomalous);
    #   4. aborts with "edge_drift" if a width_axis/width_center/
    #      width_limit guard is given and tripped (use this for a
    #      staircase's own strip -- there's a real fall-off-the-side
    #      edge to guard against; leave it unset for an open patch like
    #      rubble, which has no equivalent edge);
    #   5. aborts with "stuck" if stuck_segments_before_abort consecutive
    #      segments each cover under stuck_dist_fraction of their own
    #      planned distance (added after a real run where an earlier
    #      incident left the robot essentially stuck/fallen, and the
    #      walk kept logging segments of a robot that wasn't moving at
    #      all instead of saying so).
    #   6. otherwise keeps walking segments until the robot actually
    #      ARRIVES (within arrival_tolerance of the target) -- it does
    #      NOT give up after some fixed, precomputed segment count. A
    #      real run showed why that matters: stairs_gentle's crossing
    #      was budgeted 20 segments up front (total_dist/segment_len at
    #      the START), but climbing the stairs while re-facing every
    #      segment made each one cover noticeably less than segment_len
    #      (yaw correction eats into forward progress) -- by segment 20
    #      the robot was still 2.71 m short of the target, genuinely
    #      still making progress (not stuck), just slower than the
    #      budget assumed. The caller then moved on to the NEXT feature
    #      from that still-mid-climb, unfinished position, which is
    #      exactly the kind of corrupted-starting-state chain this
    #      engine's stuck-detector exists to prevent elsewhere. Looping
    #      on actual arrival instead of a precomputed count fixes this
    #      at the source: a feature's walk only ends when the robot
    #      either truly gets there, or a real failure (stuck/edge_drift)
    #      is detected -- never "ran out of its turn". max_segments is
    #      still a hard safety cap (so a genuinely endless drift can't
    #      hang forever), generous relative to the straight-line segment
    #      count so a real, slower-than-nominal climb has room to finish;
    #      hitting it returns "incomplete" rather than silently stopping.
    # Returns one of "completed", "edge_drift", "stuck", or "incomplete"
    # -- a caller chaining multiple walks (e.g. an approach then a
    # crossing, or one feature then the next) should treat anything
    # other than "completed" as "did not actually finish" and NOT start
    # the next walk from this one's end position (see run_feature()/
    # main() in tools/visual_test_rough_terrain.py for a worked example:
    # it now stops running further features entirely the moment one
    # doesn't come back "completed", rather than chaining onward from an
    # unfinished or fallen state).
    def _walk_terrain_segment_loop(self, target_x: float, target_y: float,
                                    segment_len: float, speed: float,
                                    width_axis: Optional[str] = None,
                                    width_center: Optional[float] = None,
                                    width_limit: Optional[float] = None,
                                    max_height_jump: float = 0.15,
                                    stuck_dist_fraction: float = 0.25,
                                    stuck_segments_before_abort: int = 3,
                                    arrival_tolerance: Optional[float] = None,
                                    max_segments: Optional[int] = None,
                                    recenter_gain: float = 0.0,
                                    max_recenter_turn_deg: float = 6.0) -> str:
        pose = self.get_robot_pose()
        total_dist = math.hypot(target_x - pose.x, target_y - pose.y)

        # Arrival band defaults to half a segment -- tight enough to mean
        # "actually there", loose enough that one segment's worth of
        # overshoot/undershoot doesn't bounce it back and forth forever.
        if arrival_tolerance is None:
            arrival_tolerance = segment_len * 0.5
        # Safety cap, not a target budget: a real climb can take several
        # times the straight-line segment count once re-facing/slowdowns
        # are accounted for (see the class comment above), so this is
        # deliberately generous (4x the straight-line estimate, floor of
        # 20) rather than the old "exactly total_dist/segment_len and no
        # more". Only hit by a genuine endless drift, which the width/
        # stuck guards below should normally catch first anyway.
        if max_segments is None:
            nominal = max(1, round(total_dist / segment_len))
            max_segments = max(20, nominal * 4)

        segment_duration = segment_len / speed
        prev_trunk_z = self.get_trunk_height()
        stuck_streak = 0
        i = 0

        while True:
            dist_remaining = math.hypot(target_x - pose.x, target_y - pose.y)
            if dist_remaining <= arrival_tolerance:
                self.stop()
                return "completed"
            if i >= max_segments:
                print(f"    !! still {dist_remaining:.2f} m short of the "
                      f"target after {i} segments (safety cap {max_segments}) "
                      f"-- stopping rather than walking indefinitely; this "
                      f"wasn't flagged stuck/edge_drift, so it was still "
                      f"making SOME progress, just too slowly to finish "
                      f"within a generous budget")
                self.stop()
                return "incomplete"

            i += 1
            self._face_waypoint(target_x, target_y, width_axis=width_axis,
                                 width_center=width_center,
                                 recenter_gain=recenter_gain,
                                 max_recenter_turn_deg=max_recenter_turn_deg)
            pose_before = self.get_robot_pose()
            self.move(vx=speed, vy=0.0, wz=0.0, duration=segment_duration)
            pose = self.get_robot_pose()
            trunk_z = self.get_trunk_height()
            dist_remaining = math.hypot(target_x - pose.x, target_y - pose.y)
            height_delta = trunk_z - prev_trunk_z
            prev_trunk_z = trunk_z
            flag = ""
            if abs(height_delta) > max_height_jump:
                flag = (f"  <-- trunk_z jumped {height_delta:+.3f} m in one "
                         f"segment, likely stumble/launch")
            print(f"    [{i}/~{max(1, round(total_dist / segment_len))}] "
                  f"x={pose.x:.2f} y={pose.y:.2f} yaw={pose.yaw_deg:.1f} "
                  f"trunk_z={trunk_z:.3f} m (dist remaining="
                  f"{dist_remaining:.2f} m){flag}")

            if width_axis is not None:
                lateral = pose.y if width_axis == "y" else pose.x
                if abs(lateral - width_center) > width_limit:
                    print(f"    !! drifted {width_axis}={lateral:.2f} past the "
                          f"+/-{width_limit:.2f} m margin around "
                          f"{width_axis}={width_center:.2f} -- stopping before "
                          f"it walks off the structure's edge")
                    self.stop()
                    return "edge_drift"

            moved_this_segment = math.hypot(pose.x - pose_before.x, pose.y - pose_before.y)
            if moved_this_segment < stuck_dist_fraction * segment_len:
                stuck_streak += 1
                if stuck_streak >= stuck_segments_before_abort:
                    print(f"    !! moved only {moved_this_segment:.3f} m "
                          f"(planned {segment_len:.2f} m) for "
                          f"{stuck_streak} segments running -- robot appears "
                          f"stuck/fallen, not just slow; stopping rather than "
                          f"logging more segments of a robot that isn't moving")
                    self.stop()
                    return "stuck"
            else:
                stuck_streak = 0

    def _face_waypoint(self, target_x: float, target_y: float,
                        width_axis: Optional[str] = None,
                        width_center: Optional[float] = None,
                        recenter_gain: float = 0.0,
                        max_recenter_turn_deg: float = 6.0) -> None:
        """Closed-loop turn (reusing turn()'s own [TURN] diagnostic) to
        face a world-frame waypoint, using the same yaw convention as
        _yaw_from_wxyz (yaw=0 faces +x, positive yaw turns toward +y).

        Plain pure-pursuit (bearing-to-target only, no width_axis) has a
        real failure mode a run on stairs_steep's own crossing surfaced:
        as the robot drifts sideways off a strip's centerline, the
        bearing-to-target angle grows in step with the robot's own
        (disturbed) yaw, so the TURN-NEEDED error between them can stay
        under the 1 deg deadband below the whole time even while the
        robot keeps sliding toward the edge -- bearing-to-a-fixed-point-
        far-ahead is just a weak corrective signal when something (an
        asymmetric stair-riser disturbance, in that run) is actively
        pushing the robot off-center every segment. That run's own
        numbers: climbing from (0.9,6.0) toward (5.0,6.0) with
        width_center=6.0, y drifted 6.02->5.43 over 10 segments while
        logged TURN corrections mostly went silent (deadbanded) for the
        back half of that drift, and it hit the edge_drift guard at
        y=5.43 (real physical edge is y=5.25).

        Fix: when width_axis/width_center are given (i.e. this waypoint
        sits on a guarded strip), bias the bearing calculation with an
        explicit proportional cross-track term -- not just bearing to
        the far-off target, but bearing amplified by how far off the
        centerline the robot currently is. This makes the correction
        react to CURRENT lateral error directly (classic cross-track/
        path-following control) instead of only to the angle-to-a-
        distant-point, which is what let the drift above go uncorrected.
        REVISED after a real run with an earlier version of this method
        (recenter_gain=1.5, no cap): it DID engage (a [TURN] line on
        almost every segment, versus the earlier uncorrected run's mostly
        silent back half), but several of those corrective turns were
        themselves large (targets of 5.6, 3.2, -7.3 deg), and right in
        that stretch yaw spiked to 20.3 deg and trunk_z jumped +0.176 m
        in one segment -- a real stumble, not just drift -- ending in
        "stuck" rather than the earlier run's "edge_drift" (which, in
        hindsight, was actually the SAFER outcome: caught before any
        physical stumble). The smaller 1-3 deg corrections earlier in
        that same crossing caused no anomaly (trunk_z climbed normally
        through the first few steps) -- frequent LARGE re-orientations
        while already balancing on stair risers look to be the actual
        destabilizing factor, not frequent correction per se.

        Fix: the plain bearing-to-target (needed for the normal, often-
        large initial reorientation at the start of a crossing -- e.g.
        turning ~75-90 deg to face a detour waypoint) is left uncapped,
        but the EXTRA angle contributed by the cross-track recentering
        bias is clamped to max_recenter_turn_deg (default 6.0) before
        being added back in. So a legitimate "turn toward the target"
        is never limited, but "turn further because of drift" can only
        nudge a few degrees per segment, however large the cross-track
        error currently is -- multiple smaller nudges across segments
        instead of one potentially destabilizing big one. recenter_gain
        mainly matters below the cap (how quickly small errors ramp up
        toward it).

        REVISED AGAIN after a real run with THIS capped version
        (recenter_gain=1.0, max_recenter_turn_deg=6.0): no stumble this
        time (trunk_z stayed flat, 0.275-0.286), but it was WORSE in a
        different way -- x barely moved at all for 4 straight segments
        (1.07, 1.06, 1.07, 1.07) and trunk_z never climbed past 0.286 m,
        i.e. it never even got over the first riser before the stuck-
        detector fired. Two different recentering configurations have
        now each made this specific crossing worse than doing nothing:
        the plain, uncorrected engine (the version BEFORE any of this
        recentering logic existed) got furthest of all three attempts --
        it climbed real height (trunk_z up to ~0.65 m) over several
        risers before eventually drifting into a safe, caught
        edge_drift abort. That's a consistent pattern, not one noisy
        run: interrupting a tall-riser climbing gait with EXTRA turn
        commands, however small/capped, seems to break its rhythm more
        than an uncorrected lateral drift hurts -- plausibly because the
        policy needs a stable heading command to execute the climbing
        motion, and any added mid-climb re-aiming disrupts that.

        CONCLUSION: recenter_gain now defaults to 0.0 (off) -- width_axis/
        width_center still enable the plain edge_drift SAFETY GUARD (via
        _walk_terrain_segment_loop, unaffected by this), just not the
        active recentering bias. A caller can still opt in by passing
        recenter_gain > 0 explicitly, but on the evidence so far that is
        not recommended for climb_stairs() on a tall-riser staircase like
        this project's own stairs_steep -- the uncorrected drift-then-
        safe-abort is the better real-world outcome of the three tried."""
        pose = self.get_robot_pose()
        bearing_plain_deg = math.degrees(math.atan2(target_y - pose.y, target_x - pose.x))

        if width_axis is not None and width_center is not None:
            dx = target_x - pose.x
            dy = target_y - pose.y
            if width_axis == "y":
                cross_track_error = width_center - pose.y
                dy = dy + recenter_gain * cross_track_error
            else:  # "x"
                cross_track_error = width_center - pose.x
                dx = dx + recenter_gain * cross_track_error
            bearing_biased_deg = math.degrees(math.atan2(dy, dx))
            extra = _wrap_deg(bearing_biased_deg - bearing_plain_deg)
            extra = max(-max_recenter_turn_deg, min(max_recenter_turn_deg, extra))
            bearing_deg = bearing_plain_deg + extra
        else:
            bearing_deg = bearing_plain_deg

        turn_needed = _wrap_deg(bearing_deg - pose.yaw_deg)
        if abs(turn_needed) > 1.0:
            self.turn(turn_needed)

    def climb_stairs(self, target_x: float, target_y: float,
                      width_axis: Optional[str] = None,
                      width_center: Optional[float] = None,
                      width_limit: Optional[float] = None,
                      segment_len: float = 0.3, speed: float = 0.3,
                      recenter_gain: float = 0.0,
                      max_recenter_turn_deg: float = 6.0,
                      climb_height_cmd: Optional[float] = None) -> str:
        """Walk to (target_x, target_y) across a staircase, re-facing the
        target every short segment and logging a trunk-height profile
        that should track the stairs' own step heights (see the class
        comment above _walk_terrain_segment_loop for exactly what's
        logged/guarded). Pass width_axis/width_center/width_limit for a
        staircase strip with a real fall-off-the-side edge -- e.g. for
        this project's own custom_scene.xml stairs_gentle (y=2.0 strip,
        ~1.0 m half-width in y) something like width_axis="y",
        width_center=2.0, width_limit=0.8 (leave a margin short of the
        strip's actual physical half-width, so a drift is caught before
        the robot is actually past the edge, not after -- see
        tools/visual_test_rough_terrain.py's own FEATURES dict for the
        values already tuned against a real run on both of this
        project's staircases).

        segment_len is deliberately short (0.3 m default) relative to a
        typical stair tread depth (0.3-0.5 m in this project's own
        scene) so the printed trunk-height trace actually resolves
        individual steps rather than averaging across several of them.

        Keeps walking until it actually ARRIVES at the target (or a
        real failure is detected) rather than giving up after a fixed
        segment count -- see _walk_terrain_segment_loop's own comment
        for why that matters on a real climb.

        Returns "completed", "edge_drift", "stuck", or "incomplete" --
        see _walk_terrain_segment_loop's own comment for what each
        means. Only "completed" means it actually got there; a caller
        chaining features/steps should treat any other value as "this
        one didn't finish" and not continue onward from here.

        recenter_gain controls how hard _face_waypoint pulls the robot
        back toward width_center every segment when it's drifted off it
        (see that method's own comment for the real-run failure this
        fixes -- a stairs_steep crossing drifting from the centerline
        toward the edge without ever tripping the per-segment turn
        deadband). 1.5 is a first-pass guess, not yet verified against a
        real run; raise it if a future run still drifts toward an edge,
        lower it if the robot visibly zig-zags/overcorrects instead.
        max_recenter_turn_deg caps how much of any single segment's turn
        can come from the recentering bias specifically (as opposed to
        the plain "face the target" turn, which is never capped) -- see
        _face_waypoint's own comment for the real-run stumble this is
        now tuned against.

        climb_height_cmd: requested attempt at "make the robot lift its
        legs higher" for a tall-riser climb. IMPORTANT CAVEAT, read
        before relying on this: there is NO exposed control anywhere in
        this codebase over how high a foot swings mid-stride -- that is
        entirely internal to the trained ONNX walking policy's learned
        behavior. The complete set of inputs the policy ever receives is
        (vx, vy, wz) and height_cmd (see build_single_obs's own argument
        list, called from _sim_loop/_warmup_obs above) -- nothing in
        there is a per-step foot-clearance parameter. height_cmd is a
        desired STANDING stance height, not a swing-height command.
        Commanding it toward the top of self._height_range (the trained
        range's upper bound, 0.35 m by default) before a climb is the
        closest available proxy -- a taller commanded stance plausibly
        gives the legs more extension margin to clear a riser before
        going straight -- but whether that changes actual step height
        during the climb is UNVERIFIED; it may do nothing, since nothing
        here actually reaches into the policy's swing trajectory.

        When given (or left as None, which defaults to self._height_
        range[1]), the stance height is raised via set_height() BEFORE
        the climb starts and restored to whatever it was before,
        afterward -- regardless of whether the climb outcome was
        "completed", "stuck", "edge_drift", or "incomplete". Pass
        climb_height_cmd=False (or any falsy non-None/non-float caller
        convention isn't supported here -- pass the CURRENT height_cmd
        value explicitly, or skip calling climb_stairs with this kwarg
        and call set_height() yourself beforehand) if you want to opt
        out of the raise-then-restore behavior entirely; there's no
        separate boolean flag for that, since raising toward the trained
        range's own upper bound is meant to be a safe default (it's a
        value the policy was already trained to hold, just like
        stand() already commands -- see stand()'s own comment above)."""
        original_height_cmd = self._height_cmd
        target_height = (climb_height_cmd if climb_height_cmd is not None
                          else self._height_range[1])
        if abs(target_height - original_height_cmd) > 1e-6:
            print(f"  [CLIMB] raising stance height to {target_height:.2f} m "
                  f"(from {original_height_cmd:.2f} m) before the climb -- "
                  f"see climb_stairs()'s own docstring for why this is only "
                  f"a PROXY for 'lift legs higher', not a literal one")
            self.set_height(target_height)
        try:
            outcome = self._walk_terrain_segment_loop(
                target_x, target_y, segment_len=segment_len, speed=speed,
                width_axis=width_axis, width_center=width_center,
                width_limit=width_limit, recenter_gain=recenter_gain,
                max_recenter_turn_deg=max_recenter_turn_deg,
            )
        finally:
            if abs(self._height_cmd - original_height_cmd) > 1e-6:
                print(f"  [CLIMB] restoring stance height to "
                      f"{original_height_cmd:.2f} m after the climb")
                self.set_height(original_height_cmd)
        return outcome

    def cross_rough_terrain(self, target_x: float, target_y: float,
                             segment_len: float = 0.3, speed: float = 0.3) -> str:
        """Walk to (target_x, target_y) across an uneven/rubble patch --
        same engine as climb_stairs(), just with no width_axis/width_
        limit guard by default: an open rough-terrain patch (like this
        project's own rubble feature in custom_scene.xml) has no
        equivalent "fall off the strip's side edge" failure mode to
        guard against the way a narrow staircase does. Still gets the
        same re-facing, per-segment trunk-height delta flagging, and
        stuck-detector as climb_stairs() -- a stuck/fallen robot on
        rough terrain is just as real a failure mode as on stairs (a
        real run found exactly this: ~3% of the commanded distance
        actually covered over 22 segments, after an earlier incident on
        a staircase left the robot stuck/fallen).

        Also keeps walking until it actually arrives rather than giving
        up after a fixed segment count (see _walk_terrain_segment_loop).

        Returns "completed", "stuck", or "incomplete" in practice
        (width_axis is unset here so "edge_drift" can't trigger, but is
        still a possible return value if you pass width_axis explicitly
        via the underlying engine)."""
        return self._walk_terrain_segment_loop(
            target_x, target_y, segment_len=segment_len, speed=speed,
        )

    # ------------------------------------------------------------------
    # High-speed running on open/flat ground. Not part of core.interfaces.
    # SkillsAPI, same reasoning as crouch()/stand()/climb_stairs() above --
    # that interface is frozen by group agreement. Distinct from climb_
    # stairs()/cross_rough_terrain() above: those are deliberately SLOW
    # (0.3 m/s default) and re-face every short segment, which is the
    # right choice for a staircase/rubble patch with a real risk of
    # stepping wrong, but is not what you want on open ground where the
    # goal is covering distance quickly without the robot visibly
    # lurching at the start or pitching/stumbling on a sudden stop.
    #
    # NOT YET VERIFIED AGAINST A REAL RUN -- every tuned parameter in
    # climb_stairs()/cross_rough_terrain() (segment_len, speed,
    # recenter_gain, max_recenter_turn_deg, ...) got there through
    # several rounds of real hardware testing; run_fast() below has none
    # of that yet. Its design is reasoned from what those real runs
    # already taught this file about this specific policy/platform,
    # though, not a blind guess:
    #   - move() ends every call by hard-zeroing the command (see move()
    #     above) -- a single call from a high vx straight to 0 is exactly
    #     the kind of abrupt transition that showed up as instability
    #     elsewhere in this file (e.g. _face_waypoint's own comment on
    #     large sudden turn commands destabilizing a stair climb). Ramping
    #     vx up over several short move() calls, and back down the same
    #     way, avoids ever handing the policy one single large step
    #     change in commanded velocity.
    #   - frequent re-turning mid-motion was shown (same _face_waypoint
    #     comment) to be able to destabilize this policy even at modest
    #     magnitudes -- so heading is corrected only periodically during
    #     the cruise phase (every heading_correction_interval sim-
    #     seconds), not every short segment the way the cautious terrain
    #     engine does, trading a little path accuracy for fewer
    #     destabilizing interruptions at speed.
    # Treat max_speed/accel_segments/decel_segments/ramp_segment_duration
    # as first-pass starting points, not tuned values -- the first real
    # run's printed [RUN] trace (position/speed every segment, same
    # convention as climb_stairs()'s own per-segment logging) is what
    # actually tunes these, the same way every terrain-engine parameter
    # above was tuned from real evidence rather than guessed once and
    # left alone.
    def run_fast(self, target_x: float, target_y: float,
                 max_speed: float = 1.0,
                 accel_segments: int = 5,
                 decel_segments: int = 5,
                 ramp_segment_duration: float = 0.15,
                 cruise_segment_duration: float = 0.2,
                 heading_correction_interval: float = 1.0,
                 arrival_tolerance: float = 0.3,
                 max_duration_s: float = 30.0,
                 max_height_jump: float = 0.15,
                 stuck_dist_fraction: float = 0.25,
                 stuck_segments_before_abort: int = 3) -> str:
        """Run to (target_x, target_y) on open/flat ground at up to
        max_speed m/s, without the abrupt start/stop this file's other
        move()-based helpers can produce when used at higher speed:

          1. Faces the target once up front (an ordinary turn() call,
             same as _face_waypoint's own uncapped "face the target"
             behavior -- a real reorientation before moving is fine,
             it's reorienting WHILE already moving fast that's riskier).
          2. ACCELERATES: vx ramps linearly from 0 to max_speed over
             accel_segments short move() calls (ramp_segment_duration
             each) rather than one call straight to max_speed.
          3. CRUISES at max_speed in longer move() calls
             (cruise_segment_duration each), re-facing the target only
             every heading_correction_interval sim-seconds rather than
             every segment (see the class comment above for why -- this
             policy showed real instability from frequent re-turning
             while already in motion).
          4. BRAKES GENTLY: once close enough that decel_segments more
             cruise-speed segments would overshoot, vx ramps linearly
             back down to 0 over decel_segments short move() calls,
             instead of one abrupt stop() from full speed.

        Every phase checks dist-to-target and arrival_tolerance first,
        so a short trip can skip straight to (or through) any phase that
        isn't needed -- this never walks past the target just to
        "finish" a ramp.

        max_duration_s is a hard safety cap (same spirit as
        _walk_terrain_segment_loop's max_segments): if the robot hasn't
        arrived by then, this returns "timeout" rather than running
        forever on a bad heading/obstruction.

        Returns "completed" (arrived within arrival_tolerance), "timeout"
        (ran out of time), "stuck" (see below), or "incomplete" (braking
        finished but still outside twice arrival_tolerance -- e.g. the
        cruise-to-brake handoff undershot). No edge_drift-style guard
        here -- this is meant for open ground, not a staircase strip
        with a real fall-off-the-side edge (use climb_stairs() for
        that).

        Each segment's print line includes trunk_z and, if it jumps more
        than max_height_jump (default 0.15 m, same default as _walk_
        terrain_segment_loop's own stumble flag) from the previous
        segment, a "<-- trunk_z jumped ... likely impact/stumble" note --
        same delta-based diagnostic climb_stairs() uses.

        REVISED after a real run aimed deliberately at a known object
        (tools/visual_test_run_fast.py's own collision test): the robot
        drove straight into it and got physically stuck pushing against
        it -- position frozen for dozens of consecutive cruise segments,
        well within the object's own radius, while still commanding full
        vx every segment. TWO problems that run surfaced, both fixed
        now: (1) the printed x/y/yaw in each [RUN] line were the PRE-
        move pose (captured before that segment's move() call), not the
        POST-move pose -- stale by one segment, inconsistent with trunk_z
        in the same line (which WAS post-move) and with climb_stairs()'s
        own convention; both are now consistently post-move. (2) with no
        stuck-detector, that collision would have run for the full
        max_duration_s (30 s default) before returning "timeout" -- the
        real run had to be interrupted by hand before reaching it. Added
        a stuck-detector with the SAME parameters/logic as _walk_terrain_
        segment_loop's own (stuck_dist_fraction, stuck_segments_before_
        abort): if a segment covers less than stuck_dist_fraction of the
        distance that segment's own vx*duration implied, for
        stuck_segments_before_abort segments running, stop and return
        "stuck" immediately -- a handful of segments (well under a
        second of sim time at the defaults), not the full timeout.

        REVISED AGAIN after the NEXT real run with that stuck-detector in
        place: it worked correctly on a genuine collision (stuck 0.31 m
        from a real object, after covering several real meters first),
        but ALSO fired as a false positive on a different scenario --
        frozen 4.34 m from the nearest object, yaw drifting steadily
        (145.9 -> 157.3 deg) with near-zero translation, right after a
        163.5 deg initial turn chained in from wherever the previous
        scenario left the robot facing. Not a collision -- the gait
        hadn't recovered from that large in-place rotation before being
        asked to accelerate immediately.

        REVISED AGAIN after the real run that exercised this for the
        first time: a single fixed 0.3 s hold was not enough -- on a
        smaller ~109 deg turn, the robot still froze with yaw drifting
        for several MORE segments after the hold. turn() converging
        doesn't mean the robot's physical angular momentum from the spin
        has actually dissipated, and no single fixed guess can know how
        long that takes for a given turn size. Replaced with a loop that
        holds in short bursts and checks yaw between them, stopping once
        yaw drift goes below a small tolerance (or a generous cap is
        hit) -- see the comment inline at that turn call, a few lines
        below, for the exact numbers. Not yet re-verified against a real
        run with this version of the fix in place."""
        pose = self.get_robot_pose()
        dist_remaining = math.hypot(target_x - pose.x, target_y - pose.y)
        if dist_remaining <= arrival_tolerance:
            return "completed"

        bearing_deg = math.degrees(math.atan2(target_y - pose.y, target_x - pose.x))
        turn_needed = _wrap_deg(bearing_deg - pose.yaw_deg)
        if abs(turn_needed) > 1.0:
            self.turn(turn_needed)
            if abs(turn_needed) > 45.0:
                # REVISED after a real run (tools/visual_test_run_fast.py's
                # collision test, chained right after a scenario that left
                # the robot facing a very different direction): a 163.5 deg
                # initial turn, immediately followed by demanding
                # acceleration, produced a "stuck" result 4.34 m from the
                # nearest object -- position frozen while yaw kept drifting
                # (145.9 -> 152.0 -> 157.3 deg) for several segments, not
                # the signature of hitting something. That's the gait not
                # having recovered from a large in-place rotation before
                # being asked to translate at speed, the same kind of
                # instability large re-orientations caused elsewhere in
                # this file (see _face_waypoint's own comment on stairs_
                # steep).
                #
                # REVISED AGAIN after the real run that exercised this
                # exact fix for the first time: a single fixed 0.3 s hold
                # was NOT enough. On a ~109 deg initial turn (smaller than
                # the 163.5 deg case above), the robot froze at the very
                # start of the accel ramp with yaw STILL drifting for
                # several MORE segments afterward (162.2 -> 164.9 -> 166.7
                # -> 169.8 -> 172.7 deg, each one only 0.15-0.2 s apart) --
                # turn()'s own convergence (it stops once yaw is within
                # its own tolerance of the target) doesn't mean the
                # robot's physical angular momentum from a big in-place
                # spin has actually dissipated by then, and a single
                # guessed hold duration can't know how long that takes
                # for a given turn size.
                #
                # Fixed by holding in repeated short bursts and actually
                # checking yaw between them, instead of one fixed-length
                # guess: keep holding until yaw stops changing much
                # (< 1 deg over a burst) or a generous cap is hit, so the
                # hold is only as long as this particular turn needs.
                settle_burst_s = 0.3
                max_settle_total_s = 1.8
                settle_drift_tolerance_deg = 1.0
                total_settled = 0.0
                prev_yaw = self.get_robot_pose().yaw_deg
                while total_settled < max_settle_total_s:
                    self.move(vx=0.0, vy=0.0, wz=0.0, duration=settle_burst_s)
                    total_settled += settle_burst_s
                    cur_yaw = self.get_robot_pose().yaw_deg
                    yaw_drift = abs(_wrap_deg(cur_yaw - prev_yaw))
                    prev_yaw = cur_yaw
                    if yaw_drift < settle_drift_tolerance_deg:
                        break

        deadline = self._get_sim_time() + max_duration_s
        last_correction_time = self._get_sim_time()
        prev_trunk_z = self.get_trunk_height()
        stuck_streak = 0

        def _height_flag(trunk_z: float) -> str:
            nonlocal prev_trunk_z
            delta = trunk_z - prev_trunk_z
            prev_trunk_z = trunk_z
            if abs(delta) > max_height_jump:
                return (f"  <-- trunk_z jumped {delta:+.3f} m in one "
                         f"segment, likely impact/stumble")
            return ""

        def _check_stuck(pose_before, pose_after, vx: float, duration: float) -> str:
            nonlocal stuck_streak
            expected = abs(vx) * duration
            if expected <= 1e-9:
                return ""
            moved = math.hypot(pose_after.x - pose_before.x, pose_after.y - pose_before.y)
            if moved < stuck_dist_fraction * expected:
                stuck_streak += 1
            else:
                stuck_streak = 0
            if stuck_streak >= stuck_segments_before_abort:
                return (f"  <-- moved only {moved:.3f} m of an expected "
                         f"~{expected:.3f} m for {stuck_streak} segments "
                         f"running, likely blocked/collided")
            return ""

        # --- Accelerate ---
        for i in range(1, accel_segments + 1):
            if self._get_sim_time() >= deadline:
                self.stop()
                return "timeout"
            pose_before = self.get_robot_pose()
            dist_remaining = math.hypot(target_x - pose_before.x, target_y - pose_before.y)
            if dist_remaining <= arrival_tolerance:
                self.stop()
                return "completed"
            vx = max_speed * (i / accel_segments)
            self.move(vx=vx, vy=0.0, wz=0.0, duration=ramp_segment_duration)
            pose = self.get_robot_pose()
            trunk_z = self.get_trunk_height()
            height_flag = _height_flag(trunk_z)
            stuck_flag = _check_stuck(pose_before, pose, vx, ramp_segment_duration)
            print(f"  [RUN] accel {i}/{accel_segments} vx={vx:.2f} m/s "
                  f"x={pose.x:.2f} y={pose.y:.2f} yaw={pose.yaw_deg:.1f} "
                  f"trunk_z={trunk_z:.3f} m (dist remaining="
                  f"{dist_remaining:.2f} m){height_flag}{stuck_flag}")
            if stuck_flag:
                self.stop()
                return "stuck"

        # --- Cruise ---
        # Rough distance the braking ramp below will cover (average of
        # max_speed and 0, over decel_segments short calls) -- stop
        # cruising with roughly that much distance left so braking isn't
        # rushed into fewer segments than decel_segments asked for.
        decel_distance_estimate = (max_speed * 0.5 * decel_segments
                                    * ramp_segment_duration)
        while True:
            if self._get_sim_time() >= deadline:
                self.stop()
                return "timeout"
            pose_before = self.get_robot_pose()
            dist_remaining = math.hypot(target_x - pose_before.x, target_y - pose_before.y)
            if dist_remaining <= max(arrival_tolerance, decel_distance_estimate):
                break
            if self._get_sim_time() - last_correction_time >= heading_correction_interval:
                bearing_deg = math.degrees(math.atan2(target_y - pose_before.y, target_x - pose_before.x))
                turn_needed = _wrap_deg(bearing_deg - pose_before.yaw_deg)
                if abs(turn_needed) > 2.0:
                    self.turn(turn_needed)
                last_correction_time = self._get_sim_time()
            self.move(vx=max_speed, vy=0.0, wz=0.0, duration=cruise_segment_duration)
            pose = self.get_robot_pose()
            trunk_z = self.get_trunk_height()
            height_flag = _height_flag(trunk_z)
            stuck_flag = _check_stuck(pose_before, pose, max_speed, cruise_segment_duration)
            print(f"  [RUN] cruise vx={max_speed:.2f} m/s x={pose.x:.2f} "
                  f"y={pose.y:.2f} yaw={pose.yaw_deg:.1f} trunk_z={trunk_z:.3f} m "
                  f"(dist remaining={dist_remaining:.2f} m){height_flag}{stuck_flag}")
            if stuck_flag:
                self.stop()
                return "stuck"

        # --- Brake gently ---
        for i in range(decel_segments, 0, -1):
            if self._get_sim_time() >= deadline:
                self.stop()
                return "timeout"
            pose_before = self.get_robot_pose()
            dist_remaining = math.hypot(target_x - pose_before.x, target_y - pose_before.y)
            if dist_remaining <= arrival_tolerance:
                break
            vx = max_speed * (i / decel_segments)
            self.move(vx=vx, vy=0.0, wz=0.0, duration=ramp_segment_duration)
            pose = self.get_robot_pose()
            trunk_z = self.get_trunk_height()
            height_flag = _height_flag(trunk_z)
            stuck_flag = _check_stuck(pose_before, pose, vx, ramp_segment_duration)
            print(f"  [RUN] decel {decel_segments - i + 1}/{decel_segments} "
                  f"vx={vx:.2f} m/s x={pose.x:.2f} y={pose.y:.2f} "
                  f"yaw={pose.yaw_deg:.1f} trunk_z={trunk_z:.3f} m "
                  f"(dist remaining={dist_remaining:.2f} m){height_flag}{stuck_flag}")
            if stuck_flag:
                self.stop()
                return "stuck"

        self.stop()
        pose = self.get_robot_pose()
        dist_remaining = math.hypot(target_x - pose.x, target_y - pose.y)
        print(f"  [RUN] stopped at x={pose.x:.2f} y={pose.y:.2f} "
              f"(dist remaining={dist_remaining:.2f} m)")
        return "completed" if dist_remaining <= arrival_tolerance * 2 else "incomplete"

    def get_camera_frame(self) -> np.ndarray:
        with self._frame_lock:
            if self._latest_frame is None:
                return np.zeros((CAMERA_HEIGHT_PX, CAMERA_WIDTH_PX, 3), dtype=np.uint8)
            return self._latest_frame.copy()

    def get_robot_pose(self) -> RobotPose:
        with self._pose_lock:
            return RobotPose(x=self._pose.x, y=self._pose.y, yaw_deg=self._pose.yaw_deg)

    # ------------------------------------------------------------------
    # internal
    # ------------------------------------------------------------------

    def _get_sim_time(self) -> float:
        with self._sim_time_lock:
            return self._sim_time

    def _warmup_obs(self) -> np.ndarray:
        quat_wxyz = self._data.qpos[3:7]
        quat_xyzw = np.array([quat_wxyz[1], quat_wxyz[2], quat_wxyz[3], quat_wxyz[0]])
        omega = self._data.qvel[3:6]
        joint_q_mujoco = self._data.qpos[7:19]
        joint_dq_mujoco = self._data.qvel[6:18]
        joint_q_isaac = joint_q_mujoco[platform.MUJOCO_TO_ISAAC]
        joint_dq_isaac = joint_dq_mujoco[platform.MUJOCO_TO_ISAAC]
        return platform.build_single_obs(
            quat_xyzw,
            omega,
            joint_q_isaac,
            joint_dq_isaac,
            self._last_action_isaac if hasattr(self, "_last_action_isaac") else np.zeros(12),
            platform.DEFAULT_ANGLES_ISAAC,
            np.zeros(3),
            self.cmd_scale,
            self.ang_vel_scale,
            self.dof_pos_scale,
            self.dof_vel_scale,
            self.clip_obs,
            height_cmd=self._height_cmd if hasattr(self, "_height_cmd") else 0.25,
        )

    def _build_tau_limits(self) -> np.ndarray:
        # hip, thigh, calf per leg x4, in MuJoCo joint order.
        per_leg = np.array(
            [platform.TAU_LIMIT_HIP_THIGH, platform.TAU_LIMIT_HIP_THIGH, platform.TAU_LIMIT_CALF]
        )
        return np.tile(per_leg, 4)

    def _publish_pose(self) -> None:
        quat_wxyz = self._data.qpos[3:7]
        yaw = _yaw_from_wxyz(quat_wxyz)
        with self._pose_lock:
            self._pose = RobotPose(
                x=float(self._data.qpos[0]),
                y=float(self._data.qpos[1]),
                yaw_deg=math.degrees(yaw),
            )

    def _maybe_render_camera(self, sim_time: float) -> None:
        if sim_time < self._next_render_time:
            return
        self._next_render_time = sim_time + self._render_period
        try:
            self._renderer.update_scene(self._data, camera="dog_front_camera")
            frame = self._renderer.render()
        except Exception as exc:
            # Camera name mismatch or renderer hiccup — keep the last good
            # frame rather than crashing the sim thread. This used to be a
            # silent `return`, which is exactly how a real bug (an EGL/GLX
            # context problem in this offscreen mujoco.Renderer) went
            # completely invisible: perception.detect() would keep reading a
            # frozen frame for the whole run even while the robot's real
            # pose kept changing, which looks exactly like a navigation
            # failure ([MISSION] status=FAIL reason=not_found after a full
            # sweep) rather than a rendering one. This is NOT specific to
            # native_viewer=True -- an earlier version of this message
            # suggested switching to gui=True (the browser panel) as a fix,
            # but that was wrong: it's been reproduced under gui=True too
            # (EGL_BAD_ACCESS on eglMakeCurrent, MUJOCO_GL=egl), most likely
            # this offscreen renderer's own GL/EGL context contending with
            # whatever the runtime's own browser-preview rendering uses,
            # independent of which display mode is active.
            #
            # Rather than staying stuck on a stale frame for the rest of the
            # run, try to self-heal: close and recreate the renderer (its
            # GL/EGL context may be in a genuinely broken state, not just
            # momentarily busy) and retry once immediately. If that also
            # fails, fall back to the old behavior (keep the last good
            # frame) -- but the NEXT call gets a freshly recreated renderer
            # to try again, rather than being permanently stuck on whatever
            # object failed once.
            now = time.time()
            if now - self._last_render_error_log >= 5.0:
                print(f"[CAMERA] render failed ({exc!r}) -- get_camera_frame() "
                      f"may be returning a STALE frame; attempting to "
                      f"recreate the offscreen renderer to recover.")
                self._last_render_error_log = now
            try:
                try:
                    self._renderer.close()
                except Exception:
                    pass  # best-effort; a context already in a bad state may not close cleanly
                self._renderer = mujoco.Renderer(self._model, height=CAMERA_HEIGHT_PX, width=CAMERA_WIDTH_PX)
                self._renderer.update_scene(self._data, camera="dog_front_camera")
                frame = self._renderer.render()
            except Exception:
                return  # still broken -- keep the last good frame, try again next tick
        with self._frame_lock:
            self._latest_frame = frame

    def _sim_loop(self) -> None:
        real_start = time.time()
        while not self._stop_event.is_set():
            step_start = time.time()

            with self._cmd_lock:
                vx, vy, wz = self._cmd

            runtime_state = None
            if self._runtime is not None:
                runtime_state = self._runtime.runtime_control(self._model, self._data)
                if self._runtime.consume_reset():
                    platform.reset_robot(self._model, self._data, platform.DEFAULT_ANGLES_MUJOCO)
                    self._obs_history.reset()
                    self._last_action_isaac[:] = 0.0
                    self._count = 0

            joint_q_mujoco = self._data.qpos[7:19]
            joint_dq_mujoco = self._data.qvel[6:18]
            joint_q_isaac = joint_q_mujoco[platform.MUJOCO_TO_ISAAC]
            joint_dq_isaac = joint_dq_mujoco[platform.MUJOCO_TO_ISAAC]

            quat_wxyz = self._data.qpos[3:7]
            quat_xyzw = np.array([quat_wxyz[1], quat_wxyz[2], quat_wxyz[3], quat_wxyz[0]])
            omega = self._data.qvel[3:6]

            if self._count % self.control_decimation == 0:
                cmd = np.array([vx, vy, wz], dtype=np.float64)
                obs = platform.build_single_obs(
                    quat_xyzw,
                    omega,
                    joint_q_isaac,
                    joint_dq_isaac,
                    self._last_action_isaac,
                    platform.DEFAULT_ANGLES_ISAAC,
                    cmd,
                    self.cmd_scale,
                    self.ang_vel_scale,
                    self.dof_pos_scale,
                    self.dof_vel_scale,
                    self.clip_obs,
                    height_cmd=self._height_cmd,
                )
                self._obs_history.push(obs)
                obs_input = self._obs_history.get().astype(np.float32)
                action_isaac = self._policy.run(
                    [self._policy_out], {self._policy_in: obs_input}
                )[0][0]
                action_isaac = np.clip(action_isaac, -10.0, 10.0)
                self._last_action_isaac = action_isaac

            target_q_isaac = (
                self._last_action_isaac * self.action_scale + platform.DEFAULT_ANGLES_ISAAC
            )
            target_q_mujoco = target_q_isaac[platform.ISAAC_TO_MUJOCO]

            # Pull kp/kd/torque_limit/motor_strength/motor_delay_ms from the
            # runtime (so a browser panel, if open with --gui, can still
            # tune these live); fall back to the yaml-config defaults when
            # there's no panel (runtime_state is None or missing a key).
            kp = runtime_state.get("kp", self.kps) if runtime_state else self.kps
            kd = runtime_state.get("kd", self.kds) if runtime_state else self.kds
            motor_strength = runtime_state.get("motor_strength", 1.0) if runtime_state else 1.0
            motor_delay_ms = runtime_state.get("motor_delay_ms", 0.0) if runtime_state else 0.0
            torque_limit_scale = runtime_state.get("torque_limit", platform.TAU_LIMIT_CALF) if runtime_state else platform.TAU_LIMIT_CALF

            effective_tau_limits = scale_torque_limits(
                self._tau_limits_mujoco, torque_limit_scale, reference_limit=platform.TAU_LIMIT_CALF
            )
            applied_target_q = self._motor_delay.apply(target_q_mujoco, motor_delay_ms)

            tau = compute_pd_torques(
                applied_target_q,
                joint_q_mujoco,
                joint_dq_mujoco,
                kp,
                kd,
                motor_strength=motor_strength,
                torque_limit=effective_tau_limits,
            )
            self._data.ctrl[: NUM_ACTIONS] = tau

            if self._runtime is not None:
                self._runtime.apply_external_forces(self._model, self._data)

            mujoco.mj_step(self._model, self._data)
            self._count += 1

            with self._sim_time_lock:
                self._sim_time += self.simulation_dt

            self._publish_pose()
            self._maybe_render_camera(self._get_sim_time())
            if self._native_viewer is not None:
                try:
                    self._native_viewer.sync()
                except Exception:
                    # Window closed, or a non-fatal viewer error -- stop
                    # trying to sync it but keep the sim thread (and any
                    # browser/headless consumers) running normally.
                    self._native_viewer = None

            elapsed = time.time() - step_start
            sleep_left = self.simulation_dt - elapsed
            if sleep_left > 0:
                time.sleep(sleep_left)

    def shutdown(self) -> None:
        self._stop_event.set()
        self._sim_thread.join(timeout=2.0)
        if self._native_viewer_cm is not None:
            try:
                self._native_viewer_cm.__exit__(None, None, None)
            except Exception:
                pass  # best-effort close; a crashed/closed window is fine here
        self._scene.close()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _yaw_from_wxyz(quat_wxyz) -> float:
    """MuJoCo free-joint quaternion order is (w, x, y, z). Standard
    yaw-from-quaternion formula (matches core.interfaces.SkillsAPI /
    core.schema.RobotPose docstring):
        yaw = atan2(2*(w*z + x*y), 1 - 2*(y^2 + z^2))
    """
    w, x, y, z = quat_wxyz
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def _wrap_deg(angle_deg: float) -> float:
    """Wrap an angle to (-180, 180], so turn() always takes the shorter
    signed path toward the target."""
    return (angle_deg + 180.0) % 360.0 - 180.0


# ---------------------------------------------------------------------------
# standalone test harness — Task 2.i deliverable.
#
# Deliberately defaults to no viewer at all (headless): on this team's
# WSL2 laptop, evdev can't see /dev/input (no physical-keyboard path
# exists there). Per the team's own decision (docs/DECISIONS.md),
# keyboard control goes through the platform's browser panel (--gui)
# when a visual is wanted.
#
# --native opts into the native GLFW window anyway. An earlier version of
# this comment theorized that since this harness never wires a key
# INTO the native window itself (key_callback=None -- typed commands
# here go through Python's own input(), not the window), the one
# documented native-viewer crash trigger (segfault-on-keypress through
# key_callback) would never fire. That theory is now known incomplete:
# this exact harness (`python -m skills.skills_real --native`) has since
# segfaulted on the very first typed command anyway -- no key_callback
# involved at all, no Python traceback either (a hard native crash).
# Root cause not yet found; a plausible mechanism is that the native
# window is opened on whichever thread constructs RealSkills, but
# viewer.sync() is then called every tick from the separate _sim_loop
# background thread -- cross-thread GLFW/GL context handling is exactly
# the kind of thing that can run fine for a while under one scheduling
# pattern and crash under another, and this harness's long idle gap in
# input() before the first command differs from tools/visual_test_task2.
# py --native's scripted, no-idle-gap sequence, which HAS run clean
# end-to-end. Until this is actually root-caused: use --gui for this
# harness if you hit a crash, don't treat --native as reliable here.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Standalone RealSkills test harness")
    parser.add_argument(
        "--gui", action="store_true", help="also open the browser control panel for a visual"
    )
    parser.add_argument(
        "--native", action="store_true",
        help="open the native MuJoCo (GLFW) window instead of the browser "
             "panel -- EXPERIMENTAL for this interactive harness specifically: "
             "it has segfaulted on the first typed command on at least one "
             "WSL2 machine, root cause not yet found (see the comment above "
             "this block). The exit-crash bug (missing skills.shutdown() "
             "before process exit) is fixed and unrelated to that. If you "
             "hit a crash, use --gui instead. Mutually exclusive with --gui.",
    )
    parser.add_argument(
        "--compare-turn",
        action="store_true",
        help="run the open-loop-vs-closed-loop turn comparison for the Task 2 report",
    )
    parser.add_argument(
        "--angles",
        type=float,
        nargs="+",
        default=[90.0],
        metavar="DEG",
        help="target angle(s) in degrees to test with --compare-turn, e.g. "
             "--angles 45 90 180. Defaults to [90.0] (the original single-"
             "angle behavior) if omitted, so existing report data at 90 deg "
             "stays reproducible by running with no --angles flag at all.",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=1,
        metavar="N",
        help="repeat the closed-loop/open-loop pair this many times PER "
             "angle in --angles (default 1). Each angle's N trials are run "
             "back-to-back before moving to the next angle.",
    )
    args = parser.parse_args()
    if args.gui and args.native:
        parser.error("--gui and --native are mutually exclusive -- pick one display")

    print("Booting RealSkills (this loads the ONNX policy and opens the MuJoCo scene)...")
    skills = RealSkills(gui=args.gui, native_viewer=args.native)
    print("Ready.")
    if args.gui:
        print("Browser panel: http://localhost:8765")
    elif args.native:
        print("Native viewer: check for a MuJoCo window (or console output "
              "above if it failed to open).")

    if args.compare_turn:
        # Open-loop reference point: a real run calibrated "1.5s @ wz=0.6"
        # as the (wrong, systematically-biased) open-loop guess for a 90 deg
        # turn -- see docs/turn_accuracy_data.md. There is no measured
        # open-loop formula for OTHER angles (nobody has calibrated one),
        # so for --angles other than 90 this harness does the same naive
        # thing an open-loop implementation actually would: linearly scale
        # that one calibration point by angle (duration = 1.5 * |angle|/90,
        # same wz magnitude/sign as the angle's sign). This is deliberately
        # NOT a better model -- the whole point of this comparison is that
        # open-loop timing doesn't generalize, so extrapolating one
        # guessed data point linearly is exactly the kind of mistake an
        # open-loop implementation would actually make. If the real
        # turning dynamics aren't linear in angle (e.g. a fixed spin-up/
        # spin-down cost per turn, independent of distance), this scaling
        # will itself be measurably wrong in a way worth reporting.
        base_angle, base_duration, base_wz = 90.0, 1.5, 0.6

        results = []
        for angle in args.angles:
            open_loop_duration = base_duration * (abs(angle) / base_angle)
            open_loop_wz = math.copysign(base_wz, angle) if angle != 0 else 0.0
            for trial in range(1, args.trials + 1):
                label = f"angle={angle:.1f} deg, trial {trial}/{args.trials}"

                print(f"\n--- Closed-loop turn ({label}) ---")
                skills.turn(angle)
                closed_pose = skills.get_robot_pose()
                print(f"pose after closed-loop turn: {closed_pose}")

                print(f"\n--- Open-loop (timing-only) turn, for comparison ({label}) ---")
                t0 = time.time()
                skills.move(vx=0.0, vy=0.0, wz=open_loop_wz, duration=open_loop_duration)
                open_pose = skills.get_robot_pose()
                wall_time = time.time() - t0
                print(
                    f"[OPEN-LOOP] commanded {open_loop_duration:.2f}s @ wz={open_loop_wz:.2f}, "
                    f"wall_time={wall_time:.2f}s, resulting yaw={open_pose.yaw_deg:.1f} deg "
                    f"(target magnitude {angle:.1f} deg)"
                )
                results.append({
                    "angle": angle,
                    "trial": trial,
                    "open_loop_duration": open_loop_duration,
                    "open_loop_wz": open_loop_wz,
                    "open_loop_wall_time": wall_time,
                })

        print("\n--- Summary (raw numbers -- compute |error| against each row's own "
              "target angle; closed-loop error is also in each [TURN] line above) ---")
        for r in results:
            print(
                f"angle={r['angle']:.1f} trial={r['trial']} "
                f"open_loop_duration={r['open_loop_duration']:.2f}s "
                f"open_loop_wz={r['open_loop_wz']:.2f} "
                f"open_loop_wall_time={r['open_loop_wall_time']:.2f}s"
            )
        skills.shutdown()
        raise SystemExit(0)

    print(
        "\nType a command and press Enter:\n"
        "  w / s        forward / backward 0.5s\n"
        "  a / d        strafe left / right 0.5s\n"
        "  q / e        turn left / right (closed-loop, 15 deg)\n"
        "  c / t        crouch / stand (body-height change, see [HEIGHT] line)\n"
        "  p            print current pose\n"
        "  x            stop\n"
        "  quit         exit\n"
    )
    try:
        while True:
            cmd = input("> ").strip().lower()
            if cmd == "w":
                skills.move(vx=0.5, vy=0.0, wz=0.0, duration=0.5)
            elif cmd == "s":
                skills.move(vx=-0.5, vy=0.0, wz=0.0, duration=0.5)
            elif cmd == "a":
                skills.move(vx=0.0, vy=0.5, wz=0.0, duration=0.5)
            elif cmd == "d":
                skills.move(vx=0.0, vy=-0.5, wz=0.0, duration=0.5)
            elif cmd == "q":
                skills.turn(15.0)
            elif cmd == "e":
                skills.turn(-15.0)
            elif cmd == "c":
                skills.crouch()
            elif cmd == "t":
                skills.stand()
            elif cmd == "p":
                print(skills.get_robot_pose())
            elif cmd == "x":
                skills.stop()
            elif cmd in ("quit", "exit"):
                break
            else:
                print("unrecognized command")
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        skills.shutdown()
        print("\nShut down cleanly.")
