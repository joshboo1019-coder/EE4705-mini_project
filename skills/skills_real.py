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
        self._renderer = mujoco.Renderer(self._model, height=240, width=320)
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
    #      side edge before reaching the far end);
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
                                    max_segments: Optional[int] = None) -> str:
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
            self._face_waypoint(target_x, target_y)
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

    def _face_waypoint(self, target_x: float, target_y: float) -> None:
        """Closed-loop turn (reusing turn()'s own [TURN] diagnostic) to
        face a world-frame waypoint, using the same yaw convention as
        _yaw_from_wxyz (yaw=0 faces +x, positive yaw turns toward +y)."""
        pose = self.get_robot_pose()
        bearing_deg = math.degrees(math.atan2(target_y - pose.y, target_x - pose.x))
        turn_needed = _wrap_deg(bearing_deg - pose.yaw_deg)
        if abs(turn_needed) > 1.0:
            self.turn(turn_needed)

    def climb_stairs(self, target_x: float, target_y: float,
                      width_axis: Optional[str] = None,
                      width_center: Optional[float] = None,
                      width_limit: Optional[float] = None,
                      segment_len: float = 0.3, speed: float = 0.3) -> str:
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
        one didn't finish" and not continue onward from here."""
        return self._walk_terrain_segment_loop(
            target_x, target_y, segment_len=segment_len, speed=speed,
            width_axis=width_axis, width_center=width_center,
            width_limit=width_limit,
        )

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

    def get_camera_frame(self) -> np.ndarray:
        with self._frame_lock:
            if self._latest_frame is None:
                return np.zeros((240, 320, 3), dtype=np.uint8)
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
                self._renderer = mujoco.Renderer(self._model, height=240, width=320)
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
        print("\n--- Closed-loop turn ---")
        skills.turn(90.0)
        print(f"pose after closed-loop turn: {skills.get_robot_pose()}")

        print("\n--- Open-loop (timing-only) turn, for comparison ---")
        t0 = time.time()
        skills.move(vx=0.0, vy=0.0, wz=0.6, duration=1.5)  # guessed duration, no feedback
        pose = skills.get_robot_pose()
        print(
            f"[OPEN-LOOP] commanded 1.5s @ wz=0.6, wall_time={time.time() - t0:.2f}s, "
            f"resulting yaw={pose.yaw_deg:.1f} deg (compare against a 90 deg target)"
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
