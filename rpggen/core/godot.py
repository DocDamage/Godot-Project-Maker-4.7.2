from __future__ import annotations

import contextlib
import logging
import os
import re
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from rpggen import godot_target
from rpggen.core import godot_fetch
from rpggen.errors import Issue, IssueList, RpgGenError

log = logging.getLogger(__name__)

IMPORT_TIMEOUT_S = 600
BUILD_TIMEOUT_S = 600
VALIDATE_TIMEOUT_S = 300
SMOKE_TIMEOUT_S = 300
VERSION_TIMEOUT_S = 30

SUPPORTED_VERSION = godot_target.SUPPORTED

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?\.([a-z0-9]+)")


@dataclass(frozen=True, slots=True)
class GodotRun:
    returncode: int
    stdout: str
    stderr: str
    log_path: Path
    timed_out: bool
    cancelled: bool = False


def parse_version(text: str) -> tuple[int, int, int, str]:
    """Parse the output of ``godot --version`` (first non-empty line)."""
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    m = _VERSION_RE.match(first)
    if not m:
        raise RpgGenError("ENV-002", found=text.strip()[:40])
    patch = int(m.group(3)) if m.group(3) is not None else 0
    return int(m.group(1)), int(m.group(2)), patch, m.group(4)


def _version_text(v: tuple[int, int, int, str]) -> str:
    return f"{v[0]}.{v[1]}.{v[2]}.{v[3]}"


def check_version(v: tuple[int, int, int, str]) -> list[Issue]:
    """No issues for the validated version; ENV-003 warning for another stable of the same
    series (4.7.x); else ENV-002."""
    if v == SUPPORTED_VERSION:
        return []
    if (v[0], v[1]) == (godot_target.MAJOR, godot_target.MINOR) and v[3] == "stable":
        issues = IssueList()
        issues.add("ENV-003", found=_version_text(v))
        return list(issues)
    raise RpgGenError("ENV-002", found=_version_text(v))


def find_console_exe(exe: Path) -> Path:
    """Return the ``*_console.exe`` sibling of a Windows GUI build if it exists."""
    exe = Path(exe)
    name = exe.name
    if name.lower().endswith(".exe") and "_console" not in name.lower():
        sibling = exe.with_name(exe.stem + "_console.exe")
        if sibling.exists():
            return sibling
    return exe


def find_gui_exe(exe: Path) -> Path:
    """The non-console sibling of a ``*_console.exe`` (the inverse of ``find_console_exe``): what a
    person opens, so that no console window sits behind the editor or the game. Any other
    executable is returned as it is."""
    exe = Path(exe)
    name = exe.name
    lowered = name.lower()
    if lowered.endswith("_console.exe"):
        sibling = exe.with_name(name[: -len("_console.exe")] + ".exe")
        if sibling.exists():
            return sibling
    return exe


def _kill_tree(proc: subprocess.Popen[str]) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
            capture_output=True,
            check=False,
        )
    else:
        try:  # the child runs in its own session (see _run), so its whole group goes
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()


PROTOCOL_PHASES = ("build", "validate")  # the phases that print "@rpggen step" lines
STEP_RE = re.compile(r"^@rpggen step (\w+) (\d+)/(\d+)(?: (.*))?$")


def parse_step(line: str) -> tuple[str, int, int, str] | None:
    """``@rpggen step <phase> <i>/<n> <label>`` as ``(phase, i, n, label)``; None for any other
    line. The builder and the validator print one such line per recipe and per check."""
    match = STEP_RE.match(line.strip())
    if match is None:
        return None
    return match.group(1), int(match.group(2)), int(match.group(3)), match.group(4) or ""


class LineForwarder:
    """Hands Godot's output to the callbacks of a run (T12.19).

    Progress lines (``parse_step``) go to ``on_step`` at once and are not forwarded. Every other
    line is prefixed ``[godot] `` and sent to ``on_log`` in batches (one every ``interval``, at
    most ``max_batch`` lines each, a burst waits for the next tick; ``close`` sends the rest). A
    phase without the protocol (the import, the smoke test) tells ``on_step(phase, 0, 0, last
    line)`` instead, so that a slow step still shows that something moves."""

    def __init__(
        self,
        phase: str,
        on_log: Callable[[str], None],
        on_step: Callable[[str, int, int, str], None] | None = None,
        *,
        interval: float = 0.1,
        max_batch: int = 200,
        prefix: str = "[godot] ",
    ) -> None:
        self.phase = phase
        self.on_log = on_log
        self.on_step = on_step
        self.interval = interval
        self.max_batch = max_batch
        self.prefix = prefix
        self._lines: list[str] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._last_line_steps = phase not in PROTOCOL_PHASES
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def feed(self, line: str) -> None:
        step = parse_step(line)
        if step is not None:
            if self.on_step is not None:
                self.on_step(*step)
            return
        with self._lock:
            self._lines.append(line)

    def _flush_once(self) -> bool:
        """Send one batch; True when lines are still waiting."""
        with self._lock:
            batch = self._lines[: self.max_batch]
            del self._lines[: self.max_batch]
            more = bool(self._lines)
        if batch:
            self.on_log("\n".join(self.prefix + line for line in batch))
            if self.on_step is not None and self._last_line_steps:
                last = next((ln for ln in reversed(batch) if ln.strip()), "")
                if last:
                    self.on_step(self.phase, 0, 0, last.strip())
        return more

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            self._flush_once()

    def close(self) -> None:
        """Stop the timer and send everything that is left."""
        self._stop.set()
        self._thread.join(timeout=2)
        while self._flush_once():
            pass


def _run(
    cmd: list[str],
    *,
    timeout_s: int,
    env: dict[str, str],
    is_cancelled: Callable[[], bool] | None = None,
    on_line: Callable[[str], None] | None = None,
    log_file: IO[str] | None = None,
) -> tuple[int, str, str, bool, bool]:
    """Run ``cmd``; returns (code, stdout, stderr, timed_out, cancelled).

    The pipes are drained on two daemon threads so a chatty process cannot block on a full pipe,
    and the wait polls ``is_cancelled`` so a cancel kills the whole process tree within ~0.2 s.

    Output is handled a line at a time, as it arrives: ``on_line(line)`` gets each line without
    its newline (from a drain thread) and ``log_file`` receives it at once, so that a crash or a
    cancel leaves the log of what happened and "Show details" can follow a long import."""
    write_lock = threading.Lock()
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        start_new_session=sys.platform != "win32",
    )
    out_parts: list[str] = []
    err_parts: list[str] = []

    def drain(stream: IO[str] | None, sink: list[str]) -> None:
        if stream is None:
            return
        with contextlib.suppress(OSError, ValueError):
            for line in iter(stream.readline, ""):
                sink.append(line)
                with write_lock:
                    if log_file is not None:
                        log_file.write(line if line.endswith("\n") else line + "\n")
                        log_file.flush()
                if on_line is not None:
                    on_line(line.rstrip("\r\n"))

    readers = [
        threading.Thread(target=drain, args=(proc.stdout, out_parts), daemon=True),
        threading.Thread(target=drain, args=(proc.stderr, err_parts), daemon=True),
    ]
    for reader in readers:
        reader.start()
    deadline = time.monotonic() + timeout_s
    timed_out = cancelled = False
    while True:
        try:
            proc.wait(timeout=0.2)
            break
        except subprocess.TimeoutExpired:
            pass
        if is_cancelled is not None and is_cancelled():
            cancelled = True
        elif time.monotonic() >= deadline:
            timed_out = True
        else:
            continue
        _kill_tree(proc)
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=10)
        break
    for reader in readers:
        reader.join(timeout=10)
    code = -1 if (timed_out or cancelled) else (proc.returncode or 0)
    return code, "".join(out_parts), "".join(err_parts), timed_out, cancelled


def run_godot(
    exe: Path,
    project: Path,
    args: list[str],
    *,
    timeout_s: int,
    log_name: str,
    log_dir: Path,
    is_cancelled: Callable[[], bool] | None = None,
    on_line: Callable[[str], None] | None = None,
) -> GodotRun:
    """Run ``exe --headless --path project *args``; never raises on a non-zero exit code.

    ``is_cancelled`` is polled while Godot runs; when it turns true the process tree is killed
    and the result has ``cancelled=True``. ``on_line`` receives every line of output as it is
    printed. The log file (``godot_<name>.log``, stdout and stderr in the order they came) is open
    from the start and written as lines arrive."""
    cmd = [str(exe), "--headless", "--path", str(project), *args]
    env = dict(os.environ)
    env["RPGGEN"] = "1"
    log.debug("running %s", cmd)
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"godot_{log_name}.log"
    with open(log_path, "w", encoding="utf-8", newline="\n") as fh:
        try:
            code, out, err, timed_out, cancelled = _run(
                cmd,
                timeout_s=timeout_s,
                env=env,
                is_cancelled=is_cancelled,
                on_line=on_line,
                log_file=fh,
            )
        except FileNotFoundError as exc:
            raise RpgGenError("ENV-001", path=str(exe)) from exc
    return GodotRun(code, out, err, log_path, timed_out, cancelled)


def detect_version(exe: Path) -> tuple[int, int, int, str]:
    """Run ``godot --version`` (no project) and parse the result."""
    console = find_console_exe(Path(exe))
    if not console.exists():
        raise RpgGenError("ENV-001", path=str(exe))
    env = dict(os.environ)
    env["RPGGEN"] = "1"
    try:
        code, out, _err, timed_out, _cancelled = _run(
            [str(console), "--version"], timeout_s=VERSION_TIMEOUT_S, env=env
        )
    except OSError as exc:
        raise RpgGenError("ENV-001", path=str(exe)) from exc
    if timed_out:
        raise RpgGenError("ENV-002", found="timed out")
    return parse_version(out)


def auto_find_godot() -> list[Path]:
    """Candidate Godot executables: $RPGGEN_GODOT, PATH matches, %LOCALAPPDATA%/Programs/Godot*."""
    found: dict[str, Path] = {}

    def add(p: Path) -> None:
        if p.is_file():
            found[str(p.resolve()).casefold()] = p

    env_exe = os.environ.get("RPGGEN_GODOT")
    if env_exe:
        add(Path(env_exe))
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry:
            continue
        d = Path(entry)
        try:
            for p in d.glob("[Gg]odot*.exe"):
                add(p)
        except OSError:
            continue
    managed = godot_fetch.managed_executable()
    if managed.is_file():
        found[str(managed.resolve()).casefold()] = managed
    local = os.environ.get("LOCALAPPDATA")
    if local:
        programs = Path(local) / "Programs"
        try:
            for d in programs.glob("[Gg]odot*"):
                if d.is_dir():
                    for p in d.glob("*.exe"):
                        add(p)
                else:
                    add(d)
        except OSError:
            pass
    # The copy rpggen downloaded itself comes first: it is the version the project is built for.
    return sorted(
        found.values(),
        key=lambda p: (p != managed, str(p).casefold(), str(p)),
    )


def import_project(
    exe: Path,
    project: Path,
    log_dir: Path,
    is_cancelled: Callable[[], bool] | None = None,
) -> GodotRun:
    """Import the project's resources headless (``--import``, verified in T1.06)."""
    return run_godot(
        find_console_exe(Path(exe)),
        project,
        ["--import"],
        timeout_s=IMPORT_TIMEOUT_S,
        log_name="import",
        log_dir=log_dir,
        is_cancelled=is_cancelled,
    )
