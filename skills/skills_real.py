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
        Ctrl+C -- but a SEPARATE issue has since turned up specifically
        when something also calls get_camera_frame() (i.e. Task 4 /
        goto_object()): the offscreen mujoco.Renderer used for that
        (self._renderer, wholly separate from this native window) can
        apparently start failing on every call once the native window
        exists, likely a GL-context conflict between the two in one
        process. When that happens get_camera_frame() silently returns
        the same STALE frame forever -- it looks like the robot's own
        view has frozen even though its real pose keeps changing (yaw
        drifting while detected bbox positions barely move is the
        tell). This used to fail completely silently; _maybe_render_camera
        now logs a [CAMERA] line (rate-limited) the moment rendering
        starts failing, so it's diagnosable instead of just timing out
        looking like a navigation bug. Until this is confirmed fixed,
        prefer gui=True (the browser panel) for anything that calls
        get_camera_frame() -- Task 4, or Task 3 with --real-perception;
        native_viewer is fine for Task 2 and Task 3's default (mock
        perception never touches the camera feed at all).
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
            height_range=(0.20, 0.35),
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
            # silent `return`, which is exactly how a real bug (this
            # offscreen mujoco.Renderer failing on every call once a
            # native_viewer=True GLFW window is also open in this process
            # -- observed as perception.detect() reading a frozen frame the
            # whole run, even while the robot was visibly turning per its
            # real pose) went completely invisible. Print once, then at
            # most once every 5s, so a persistent failure is impossible to
            # miss without spamming every render tick (CAMERA_HZ, e.g. 15/s).
            now = time.time()
            if now - self._last_render_error_log >= 5.0:
                print(f"[CAMERA] render failed ({exc!r}) -- get_camera_frame() "
                      f"is returning a STALE frame until this clears. If "
                      f"you're running with native_viewer=True, try gui=True "
                      f"(the browser panel) instead -- this offscreen "
                      f"renderer and the native GLFW window may be "
                      f"conflicting over the GL context in this process.")
                self._last_render_error_log = now
            return
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
# exists there), and the native GLFW viewer has intermittently segfaulted
# on keypress -- specifically on keypress, through its key_callback. Per
# the team's own decision (docs/DECISIONS.md), keyboard control goes
# through the platform's browser panel (--gui) when a visual is wanted,
# since nothing here has ever pressed a key INTO the native window itself.
# --native opts into that native window anyway, on the theory that since
# this harness (and tools/visual_test_task*.py) never sends it a
# keypress, the one documented crash trigger never fires -- try it, but
# fall back to --gui if it's unstable on your machine.
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
             "panel -- confirmed to run cleanly on WSL2 (a full scripted "
             "move/turn sequence and a clean exit); the one crash found "
             "(segfault on exit) was a missing skills.shutdown() call "
             "before process exit, now fixed everywhere in this file. "
             "Mutually exclusive with --gui.",
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
