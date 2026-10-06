from __future__ import annotations

import logging
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from rpggen.errors import Issue, IssueList, RpgGenError

log = logging.getLogger(__name__)

IMPORT_TIMEOUT_S = 600
BUILD_TIMEOUT_S = 600
VALIDATE_TIMEOUT_S = 300
SMOKE_TIMEOUT_S = 300
VERSION_TIMEOUT_S = 30

SUPPORTED_VERSION = (4, 7, 2, "stable")

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?\.([a-z0-9]+)")


@dataclass(frozen=True, slots=True)
class GodotRun:
    returncode: int
    stdout: str
    stderr: str
    log_path: Path
    timed_out: bool


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
    """No issues for 4.7.2.stable; ENV-003 warning for another 4.7.x stable; else ENV-002."""
    if v == SUPPORTED_VERSION:
        return []
    if v[0] == 4 and v[1] == 7 and v[3] == "stable":
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
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
            capture_output=True,
            check=False,
        )
    else:  # pragma: no cover - POSIX fallback
        proc.kill()


def _run(cmd: list[str], *, timeout_s: int, env: dict[str, str]) -> tuple[int, str, str, bool]:
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    try:
        out, err = proc.communicate(timeout=timeout_s)
        return proc.returncode, out or "", err or "", False
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        try:
            out, err = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive
            proc.kill()
            out, err = "", ""
        return -1, out or "", err or "", True


def run_godot(
    exe: Path,
    project: Path,
    args: list[str],
    *,
    timeout_s: int,
    log_name: str,
    log_dir: Path,
) -> GodotRun:
    """Run ``exe --headless --path project *args``; never raises on a non-zero exit code."""
    cmd = [str(exe), "--headless", "--path", str(project), *args]
    env = dict(os.environ)
    env["RPGGEN"] = "1"
    log.debug("running %s", cmd)
    try:
        code, out, err, timed_out = _run(cmd, timeout_s=timeout_s, env=env)
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
    return GodotRun(code, out, err, log_path, timed_out)


def detect_version(exe: Path) -> tuple[int, int, int, str]:
    """Run ``godot --version`` (no project) and parse the result."""
    console = find_console_exe(Path(exe))
    if not console.exists():
        raise RpgGenError("ENV-001", path=str(exe))
    env = dict(os.environ)
    env["RPGGEN"] = "1"
    try:
        code, out, _err, timed_out = _run(
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
    return sorted(found.values(), key=lambda p: (str(p).casefold(), str(p)))


def import_project(exe: Path, project: Path, log_dir: Path) -> GodotRun:
    """Import the project's resources headless (``--import``, verified in T1.06)."""
    return run_godot(
        find_console_exe(Path(exe)),
        project,
        ["--import"],
        timeout_s=IMPORT_TIMEOUT_S,
        log_name="import",
        log_dir=log_dir,
    )
