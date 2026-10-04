# Owner: ALL (backbone)
# Change contributed by Student B (assist), pending review by the group
"""
tests/test_handoff.py — BACKBONE (ALL). Full-pipeline integration check.

Where test_student_a/b/c.py each test one person's logic in isolation,
this test exercises the one place all three meet: main.py's own
build_skills() / build_perception() wiring, feeding a real CommandQueue
and CommandExecutor. USE_REAL_SKILLS / USE_REAL_PERCEPTION default to
True (the real modules); `python main.py --mock` wires the mocks instead.
The real classes are swapped for fakes here, so nothing boots the sim or
loads YOLO — it's the regression check that catches "the integration
point itself is broken", separate from any one student's own logic.

Run:
    python -m pytest -q tests/test_handoff.py
"""

import sys, os, types
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import main
from core.schema import CommandQueue, MoveCommand, TurnCommand
from skills.skills_mock import MockSkills
from perception.perception_mock import MockPerception


class _FakeRealSkills:
    def __init__(self, gui=False, native_viewer=False):
        self.gui = gui
        self.native_viewer = native_viewer


class _FakeRealPerception:
    pass


class _FakeExecutor:
    def __init__(self, skills, perception, queue):
        self.skills = skills
        self.perception = perception
        self.queue = queue

    def run_forever(self):
        pass


@pytest.fixture
def fake_real_modules(monkeypatch):
    """Stand-ins for skills_real / perception_real, so building the
    "real" wiring never starts MuJoCo or loads YOLO weights."""
    skills_real = types.ModuleType("skills.skills_real")
    skills_real.RealSkills = _FakeRealSkills
    perception_real = types.ModuleType("perception.perception_real")
    perception_real.RealPerception = _FakeRealPerception
    monkeypatch.setitem(sys.modules, "skills.skills_real", skills_real)
    monkeypatch.setitem(sys.modules, "perception.perception_real", perception_real)
    # main() may flip these for --mock; monkeypatch restores them afterwards.
    monkeypatch.setattr(main, "USE_REAL_SKILLS", main.USE_REAL_SKILLS)
    monkeypatch.setattr(main, "USE_REAL_PERCEPTION", main.USE_REAL_PERCEPTION)


def _run_main(monkeypatch, *argv):
    """main.main() with `argv`, minus the chat thread and the blocking
    executor loop. Returns the executor main() built."""
    executors = []

    def record_executor(skills, perception, queue):
        executors.append(_FakeExecutor(skills, perception, queue))
        return executors[-1]

    monkeypatch.setattr(sys, "argv", ["main.py", *argv])
    monkeypatch.setattr(main.chat_interface, "start_chat_thread", lambda queue: None)
    monkeypatch.setattr(main, "CommandExecutor", record_executor)
    main.main()
    assert len(executors) == 1
    return executors[0]


def test_main_wires_real_modules_by_default(fake_real_modules):
    assert main.USE_REAL_SKILLS is True
    assert main.USE_REAL_PERCEPTION is True
    assert isinstance(main.build_skills(), _FakeRealSkills)
    assert isinstance(main.build_perception(), _FakeRealPerception)


def test_main_without_flags_runs_the_real_modules(fake_real_modules, monkeypatch):
    executor = _run_main(monkeypatch)
    assert isinstance(executor.skills, _FakeRealSkills)
    assert isinstance(executor.perception, _FakeRealPerception)
    assert isinstance(executor.queue, CommandQueue)
    assert (executor.skills.gui, executor.skills.native_viewer) == (False, False)


def test_main_mock_flag_wires_mocks(fake_real_modules, monkeypatch):
    executor = _run_main(monkeypatch, "--mock")
    assert isinstance(executor.skills, MockSkills)
    assert isinstance(executor.perception, MockPerception)


@pytest.mark.parametrize(("flag", "gui", "native_viewer"), [
    ("--gui", True, False),
    ("--native", False, True),
])
def test_main_gui_and_native_flags_still_reach_real_skills(
        fake_real_modules, monkeypatch, flag, gui, native_viewer):
    executor = _run_main(monkeypatch, flag)
    assert isinstance(executor.skills, _FakeRealSkills)
    assert (executor.skills.gui, executor.skills.native_viewer) == (gui, native_viewer)


def test_executor_runs_a_batch_through_mains_own_wiring(fake_real_modules, monkeypatch):
    from dialogue.executor import CommandExecutor

    wired = _run_main(monkeypatch, "--mock")
    queue = CommandQueue()
    executor = CommandExecutor(wired.skills, wired.perception, queue)

    queue.push_many([
        MoveCommand(vx=0.8, vy=0.0, wz=0.0, duration=1.0),
        TurnCommand(angle_deg=180.0),
    ])
    executor._run_batch_starting_with(queue.pop())  # should not raise


if __name__ == "__main__":
    sys.exit(pytest.main(["-q", __file__]))
