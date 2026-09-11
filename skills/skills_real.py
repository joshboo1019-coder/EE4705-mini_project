"""
skills_real.py — STUDENT A OWNS THIS FILE. Task 2 (60%).

Implements SkillsAPI on top of the example platform
(https://github.com/aoqianz/quadruped_mujoco), or whatever platform you
chose from Section V. As long as RealSkills satisfies
core.interfaces.SkillsAPI, Student B's executor and Student C's
navigation code need zero changes.

Also owns: scene building (assets/scenes/custom_scene.xml — see
assets/scenes/README.md), and the background camera-capture thread.

Test this file completely on its own before anyone else needs it (run
from the project root so the `core` package resolves):
    python -m skills.skills_real            # native MuJoCo viewer, keyboard test
    python -m skills.skills_real --gui      # browser control panel
"""

import time
import threading
from typing import Optional

import numpy as np

from core.interfaces import SkillsAPI
from core.schema import RobotPose
from core import config

# TODO(Student A): these come from the example repo (or your platform's
# equivalent). e.g.:
# from quadruped_mujoco.eg import play as platform


class RealSkills(SkillsAPI):
    def __init__(self, scene_path: str = config.SCENE_PATH):
        # TODO(Student A): initialize the sim / load the ONNX policy /
        # register your custom scene as a MapSpec, e.g.:
        #   self.sim = platform.init(scene_path=scene_path)
        self.sim = None

        self._latest_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        self._stop_camera_thread = threading.Event()
        self._camera_thread = threading.Thread(
            target=self._camera_loop, daemon=True
        )
        self._camera_thread.start()

    # ------------------------------------------------------------------
    # SkillsAPI
    # ------------------------------------------------------------------

    def move(self, vx: float, vy: float, wz: float, duration: float) -> None:
        """Push (vx, vy, wz) into the platform's command queue for
        `duration` seconds, replacing get_commands() in eg/play.py, then
        block until it's done. Physics/policy stepping must continue to
        run at their normal rates while this blocks."""
        # TODO(Student A): implement using your platform's velocity-command
        # interface. Example shape:
        #   t0 = time.time()
        #   while time.time() - t0 < duration:
        #       self.sim.set_cmd(vx, vy, wz)
        #       self.sim.step()   # advances physics/policy one tick
        raise NotImplementedError

    def turn(self, angle_deg: float) -> None:
        """Closed-loop turn: read true yaw from mj_data.qpos (quaternion ->
        yaw via atan2(2(wz+xy), 1-2(y^2+z^2))) each control step, drive wz
        proportionally to the remaining error, stop within tolerance, then
        print the [TURN] line. Do NOT use open-loop timing."""
        # TODO(Student A): implement closed-loop turn using get_robot_pose()
        # in a small control loop, then:
        #   final_error = ...
        #   print(f"[TURN] target={angle_deg:.1f} deg final_error={final_error:.1f} deg")
        raise NotImplementedError

    def stop(self) -> None:
        # TODO(Student A): zero the command
        raise NotImplementedError

    def get_camera_frame(self) -> np.ndarray:
        with self._frame_lock:
            if self._latest_frame is None:
                return np.zeros((240, 320, 3), dtype=np.uint8)
            return self._latest_frame.copy()

    def get_robot_pose(self) -> RobotPose:
        # TODO(Student A): read qpos, compute yaw, return RobotPose
        raise NotImplementedError

    # ------------------------------------------------------------------
    # internal
    # ------------------------------------------------------------------

    def _camera_loop(self) -> None:
        """Renders the onboard front camera offscreen at
        config.CAMERA_HZ (10-20 Hz) and stores the latest frame."""
        period = 1.0 / config.CAMERA_HZ
        while not self._stop_camera_thread.is_set():
            # TODO(Student A): offscreen-render dog_front_camera, e.g.:
            #   frame = self.sim.render_camera("dog_front_camera")
            frame = np.zeros((240, 320, 3), dtype=np.uint8)
            with self._frame_lock:
                self._latest_frame = frame
            time.sleep(period)

    def shutdown(self) -> None:
        self._stop_camera_thread.set()
        self._camera_thread.join(timeout=1.0)


if __name__ == "__main__":
    # TODO(Student A): standalone keyboard-driven test harness (W/S/A/D/Q/E),
    # exactly like the deliverable in Task 2.i. Keep this runnable on its
    # own so you never need Student B/C's code to verify Task 2 works.
    print("Run this to keyboard-test the platform + camera + skills in isolation.")
