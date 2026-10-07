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


def _run(
    cmd: list[str],
    *,
    timeout_s: int,
    env: dict[str, str],
    is_cancelled: Callable[[], bool] | None = None,
) -> tuple[int, str, str, bool, bool]:
    """Run ``cmd``; returns (code, stdout, stderr, timed_out, cancelled).

    The pipes are drained on two daemon threads so a chatty process cannot block on a full pipe,
    and the wait polls ``is_cancelled`` so a cancel kills the whole process tree within ~0.2 s."""
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
            for chunk in iter(lambda: stream.read(8192), ""):
                sink.append(chunk)

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
) -> GodotRun:
    """Run ``exe --headless --path project *args``; never raises on a non-zero exit code.

    ``is_cancelled`` is polled while Godot runs; when it turns true the process tree is killed
    and the result has ``cancelled=True``."""
    cmd = [str(exe), "--headless", "--path", str(project), *args]
    env = dict(os.environ)
    env["RPGGEN"] = "1"
    log.debug("running %s", cmd)
    try:
        code, out, err, timed_out, cancelled = _run(
            cmd, timeout_s=timeout_s, env=env, is_cancelled=is_cancelled
        )
    except FileNotFoundError as exc:
        raise RpgGenError("ENV-001", path=str(exe)) from exc
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"godot_{log_name}.log"
    with open(log_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(out)
        if err:
            if out and not out.endswith("\n"):
                fh.write("\n")
            fh.write(err)
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
