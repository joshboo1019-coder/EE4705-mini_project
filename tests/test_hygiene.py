# Owner: ALL (fix/hygiene)
"""
tests/test_hygiene.py -- [ALL] harness and CLI hygiene (fix/hygiene).

  * the e2e/recording harness stops the program under test with a real SIGINT
    to the terminal's child process group, never a synthetic ctrl+c keystroke
    (`xdotool key ctrl+c` left Ctrl and C held on the X server's XTEST keyboard);
  * EOF on stdin (Ctrl+D / end of piped input) quits main.py cleanly after the
    queued commands;
  * `eval/run_env.sh main.py --mock` works without the quadruped_mujoco platform.
"""

import os
import signal
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.schema import CommandQueue  # noqa: E402
from eval.e2e import stage  # noqa: E402


def test_child_pgids_finds_the_terminal_child_group_and_sigint_stops_it():
    # stand-in for xterm: a parent whose child runs in its own session/group
    code = ("import subprocess; p = subprocess.Popen(['sleep', '30'], start_new_session=True); "
            "print(p.pid, flush=True); p.wait()")
    term = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    try:
        child = int(term.stdout.readline())
        assert stage._child_pgids(term.pid) == [child]
        for pgid in stage._child_pgids(term.pid):
            os.killpg(pgid, signal.SIGINT)
        assert term.wait(timeout=5) == 0
    finally:
        if term.poll() is None:
            term.kill()


def test_close_sends_no_synthetic_ctrl_c_and_releases_keys():
    src = (ROOT / "eval" / "e2e" / "stage.py").read_text()
    close = src[src.index("    def close(self)"):src.index("def _child_pgids")]
    assert '"ctrl+c"' not in close and "'ctrl+c'" not in close
    assert "os.killpg(pgid, signal.SIGINT)" in close
    assert "release_keys(self.display)" in close
    assert "Control_L" in stage.MODIFIER_KEYS and "c" in stage.MODIFIER_KEYS


def test_eof_closes_the_queue_input(monkeypatch):
    from dialogue import chat_interface

    def eof(_prompt=""):
        raise EOFError
    monkeypatch.setattr("builtins.input", eof)
    q = CommandQueue()
    chat_interface._chat_loop(q)          # returns at once on EOF
    assert q.input_closed()


def test_run_forever_returns_after_eof_when_the_queue_is_drained():
    from dialogue.executor import CommandExecutor
    from skills.skills_mock import MockSkills
    from perception.perception_mock import MockPerception
    q = CommandQueue()
    ex = CommandExecutor(MockSkills(), MockPerception(), q)
    t = threading.Thread(target=ex.run_forever, kwargs={"poll_timeout": 0.05}, daemon=True)
    t.start()
    t.join(0.3)
    assert t.is_alive()                   # input still open: keeps waiting
    q.close_input()
    t.join(3.0)
    assert not t.is_alive()


def test_mock_runs_without_the_platform_and_quits_on_eof():
    env = dict(os.environ, QUADRUPED_MUJOCO_ROOT="/nonexistent/quadruped_mujoco")
    r = subprocess.run([str(ROOT / "eval" / "run_env.sh"), "main.py", "--mock"], input="\n",
                       env=env, cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
    assert "quadruped_mujoco not found" not in r.stderr
    assert "[CHAT] input closed (EOF)" in r.stdout
