# Owner: Student B (Task 3 + bonuses)
"""
eval/e2e/stage.py — Student B. A virtual "stage" for recorded end-to-end runs.

Everything happens on a virtual X display (Xvfb, default :99, 1920x1080), so
nothing on the real screen is recorded and screen lock can't interfere:

    left half   demo terminal (xterm, large font) running the command under test
    right half  the browser control panel (http://127.0.0.1:8765, the
                platform's third-person "tracking" camera by default)

Commands are typed into the terminal with xdotool, exactly as a person would,
and ffmpeg records the display. The terminal's output is also tee'd to a log
file, which the harness parses.

Xvfb / xterm / xdotool need not be installed system-wide: point E2E_XROOT at a
directory where their .deb packages were unpacked (`apt-get download xvfb
xserver-common libxfont2 libxcvt0 xdotool libxdo3 xterm libutempter0`, then
`dpkg -x <deb> $E2E_XROOT` for each). No sudo needed.
"""

import os
import re
import shlex
import signal
import socket
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Callable, List, Optional

REPO = Path(__file__).resolve().parents[2]
XROOT = Path(os.environ.get("E2E_XROOT", "/tmp/e2e-xroot"))
WIDTH, HEIGHT = 1920, 1080
TERM_W = 960                       # terminal on the left, panel on the right
PANEL_URL = "http://127.0.0.1:8765"


def _bin(name: str) -> str:
    p = XROOT / "usr" / "bin" / name
    return str(p) if p.exists() else name


def _xenv(display: str) -> dict:
    env = dict(os.environ)
    env["DISPLAY"] = display
    lib = XROOT / "usr" / "lib" / "x86_64-linux-gnu"
    if lib.exists():
        env["LD_LIBRARY_PATH"] = str(lib)
    return env


def xdotool(display: str, *args: str, check: bool = True) -> str:
    r = subprocess.run([_bin("xdotool"), *args], env=_xenv(display),
                       capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"xdotool {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout.strip()


def ensure_xvfb(display: str = ":99") -> Optional[subprocess.Popen]:
    """Start Xvfb on `display` unless something already serves it."""
    n = display.lstrip(":")
    if Path(f"/tmp/.X11-unix/X{n}").exists():
        try:
            xdotool(display, "getdisplaygeometry")
            return None
        except RuntimeError:
            pass
    p = subprocess.Popen(
        [_bin("Xvfb"), display, "-screen", "0", f"{WIDTH}x{HEIGHT}x24",
         "-nolisten", "tcp", "-xkbdir", "/usr/share/X11/xkb"],
        env=_xenv(display), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)
    for _ in range(50):
        time.sleep(0.1)
        try:
            xdotool(display, "getdisplaygeometry")
            return p
        except RuntimeError:
            continue
    raise RuntimeError(f"Xvfb did not come up on {display}")


def port_open(port: int = 8765) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


class Stage:
    """One recorded scenario: terminal + panel + recorder on the virtual display."""

    def __init__(self, display: str = ":99", font_size: int = 12):
        self.display = display
        self.font_size = font_size
        self.term: Optional[subprocess.Popen] = None
        self.term_win: Optional[str] = None
        self.browser: Optional[subprocess.Popen] = None
        self.recorder: Optional[subprocess.Popen] = None
        self.log_path: Optional[Path] = None
        self._log_pos = 0
        self._buf = ""

    # ---- terminal -------------------------------------------------------
    def open_terminal(self, command: str, log_path: Path, title: str = "demo",
                      env: Optional[dict] = None) -> None:
        """Run `command` (a shell command line, run from the repo root) in an
        xterm on the left half; its stdout+stderr are tee'd to `log_path`."""
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("")
        self._log_pos, self._buf = 0, ""
        script = self.log_path.with_suffix(".sh")
        script.write_text(
            "#!/bin/bash\n"
            f"cd {shlex.quote(str(REPO))}\n"
            "export PS1='$ '\n"
            + "".join(f"export {k}={shlex.quote(str(v))}\n" for k, v in (env or {}).items()) +
            f"printf '$ %s\\n' {shlex.quote(command)}\n"
            f"{command} 2>&1 | tee -a {shlex.quote(str(self.log_path))}\n"
            "sleep 3600\n")
        script.chmod(0o755)
        self.term = subprocess.Popen(
            [_bin("xterm"), "-T", title, "-geometry", "80x40+0+0",
             "-fa", "DejaVu Sans Mono", "-fs", str(self.font_size),
             "-bg", "black", "-fg", "#e8e8e8", "-sl", "5000", "+sb",
             "-e", str(script)],
            env=_xenv(self.display), stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True)
        for _ in range(50):
            time.sleep(0.1)
            wins = xdotool(self.display, "search", "--pid", str(self.term.pid),
                           check=False).split()
            if wins:
                self.term_win = wins[-1]
                break
        if self.term_win is None:
            raise RuntimeError("xterm window did not appear")
        xdotool(self.display, "windowsize", self.term_win, str(TERM_W), str(HEIGHT))
        xdotool(self.display, "windowmove", self.term_win, "0", "0")
        xdotool(self.display, "mousemove", str(WIDTH - 1), str(HEIGHT - 1))

    def type_line(self, text: str, delay_ms: int = 35) -> None:
        """Type `text` + Enter into the demo terminal, like a person."""
        xdotool(self.display, "windowfocus", "--sync", self.term_win, check=False)
        xdotool(self.display, "type", "--window", self.term_win,
                "--delay", str(delay_ms), text)
        time.sleep(0.2)
        xdotool(self.display, "key", "--window", self.term_win, "Return")

    def new_output(self) -> str:
        """Log text written since the last call."""
        if not self.log_path or not self.log_path.exists():
            return ""
        with self.log_path.open("r", errors="replace") as f:
            f.seek(self._log_pos)
            chunk = f.read()
            self._log_pos = f.tell()
        return chunk

    def wait_for(self, pattern: str, timeout: float,
                 on_line: Optional[Callable[[str], None]] = None) -> Optional[str]:
        """Wait until a log line matches `pattern` (regex); returns the line."""
        rx = re.compile(pattern)
        end = time.time() + timeout
        while time.time() < end:
            self._buf += self.new_output()
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                if on_line:
                    on_line(line)
                if rx.search(line):
                    return line
            if self.term and self.term.poll() is not None:
                return None
            time.sleep(0.1)
        return None

    def full_log(self) -> str:
        return self.log_path.read_text(errors="replace") if self.log_path else ""

    # ---- panel ----------------------------------------------------------
    def open_panel(self, timeout: float = 60.0) -> bool:
        """Place the browser panel on the right half. With --gui the platform
        (runtime_control/panel.py) opens the panel itself, as a Chrome app
        window with a throwaway temp profile, on our DISPLAY; we only wait
        for that window and move it."""
        end = time.time() + timeout
        win = None
        while time.time() < end:
            wins = xdotool(self.display, "search", "--onlyvisible", "--name", "MiniLab",
                           check=False).split()
            if wins:
                win = wins[-1]
                break
            time.sleep(0.5)
        if win is None:
            return False
        time.sleep(1.0)
        xdotool(self.display, "windowsize", win, str(WIDTH - TERM_W), str(HEIGHT), check=False)
        xdotool(self.display, "windowmove", win, str(TERM_W), "0", check=False)
        self.panel_win = win
        time.sleep(3.0)        # page load + first video frames
        xdotool(self.display, "mousemove", str(WIDTH - 1), str(HEIGHT - 1), check=False)
        if self.term_win:
            xdotool(self.display, "windowactivate", self.term_win, check=False)
            xdotool(self.display, "windowfocus", self.term_win, check=False)
        return True

    # ---- recorder -------------------------------------------------------
    def start_recording(self, out: Path, fps: int = 20) -> None:
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        self.recorder = subprocess.Popen(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
             "-f", "x11grab", "-framerate", str(fps), "-draw_mouse", "0",
             "-video_size", f"{WIDTH}x{HEIGHT}", "-i", self.display,
             "-c:v", "h264_nvenc", "-preset", "p5", "-cq", "26", "-pix_fmt", "yuv420p",
             str(out)],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=open(str(out) + ".ffmpeg.txt", "w"), start_new_session=True)
        self.recording_path = out

    def stop_recording(self) -> Optional[Path]:
        if not self.recorder:
            return None
        try:
            self.recorder.stdin.write(b"q")
            self.recorder.stdin.flush()
            self.recorder.wait(timeout=15)
        except Exception:
            _killpg(self.recorder, signal.SIGINT)
        self.recorder = None
        err = Path(str(self.recording_path) + ".ffmpeg.txt")
        if err.exists() and err.stat().st_size == 0:
            err.unlink()
        return self.recording_path

    # ---- teardown -------------------------------------------------------
    def close(self) -> None:
        self.stop_recording()
        if self.term and self.term.poll() is None:
            # Ctrl+C the program under test first, so the sim shuts down cleanly.
            try:
                xdotool(self.display, "key", "--window", self.term_win, "ctrl+c", check=False)
                time.sleep(3.0)
            except Exception:
                pass
        for p in (self.browser, self.term):
            if p and p.poll() is None:
                _killpg(p, signal.SIGTERM)
        for p in (self.browser, self.term):
            if p:
                try:
                    p.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    _killpg(p, signal.SIGKILL)
        self.browser = self.term = None
        # The platform's panel window (a Chrome app with a temp profile).
        subprocess.run(["pkill", "-f", "user-data-dir=/tmp/himloco_runtime_ui_"],
                       capture_output=True)
        # Nothing may keep the panel port: the next scenario needs it.
        for _ in range(40):
            if not port_open():
                break
            time.sleep(0.25)
        _kill_stray_sims()


def _killpg(p: subprocess.Popen, sig) -> None:
    try:
        os.killpg(p.pid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def _kill_stray_sims() -> None:
    """Kill leftover sim processes this harness started: `main.py` or an
    eval/e2e driver, running with this repo as their working directory."""
    out = subprocess.run(["pgrep", "-af", "python"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        pid, _, cmd = line.partition(" ")
        if not (" main.py" in cmd or "eval/e2e/drivers" in cmd):
            continue
        try:
            cwd = Path(os.readlink(f"/proc/{pid}/cwd"))
        except OSError:
            continue
        if cwd != REPO or int(pid) == os.getpid():
            continue
        try:
            os.kill(int(pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, ValueError):
            pass


def grab_frame(video: Path, t: float, out: Path, scale: str = "1920:1080") -> bool:
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(t, 0):.2f}",
                        "-i", str(video), "-frames:v", "1", "-vf", f"scale={scale}",
                        str(out)], capture_output=True)
    return r.returncode == 0 and Path(out).exists()


def video_duration(video: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nk=1:nw=1", str(video)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0
