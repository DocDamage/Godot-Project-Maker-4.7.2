from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from rpggen.core import godot


def _alive(pid: int) -> bool:
    if sys.platform == "win32":
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True, check=False
        ).stdout
        return str(pid) in out
    try:
        import os

        os.kill(pid, 0)
    except OSError:
        return False
    return True


def test_cancel_kills_the_process_and_its_children_quickly(tmp_path: Path) -> None:
    child_pid = tmp_path / "child.pid"
    code = (
        "import subprocess, sys, time\n"
        "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"open(r'{child_pid}', 'w').write(str(c.pid))\n"
        "time.sleep(60)\n"
    )
    flag = threading.Event()
    threading.Timer(1.5, flag.set).start()
    start = time.monotonic()
    result = godot._run(
        [sys.executable, "-c", code], timeout_s=120, env={}, is_cancelled=flag.is_set
    )
    elapsed = time.monotonic() - start
    assert result[4] is True and result[3] is False
    assert elapsed < 4.5  # flag at 1.5 s, killed within 2 s of it
    pid = int(child_pid.read_text())
    deadline = time.monotonic() + 3
    while _alive(pid) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not _alive(pid)


def test_run_godot_reports_cancelled_and_writes_the_log(tmp_path: Path, monkeypatch) -> None:
    flag = threading.Event()
    threading.Timer(0.5, flag.set).start()
    if sys.platform == "win32":
        fake = tmp_path / "fake_godot.bat"
        fake.write_text(f'@"{sys.executable}" -c "import time; time.sleep(60)"\r\n')
    else:
        fake = tmp_path / "fake_godot.sh"
        fake.write_text("#!/bin/sh\nsleep 60\n")
        fake.chmod(0o755)
    run = godot.run_godot(
        fake,
        tmp_path,
        [],
        timeout_s=120,
        log_name="x",
        log_dir=tmp_path / "logs",
        is_cancelled=flag.is_set,
    )
    assert run.cancelled and not run.timed_out
    assert run.log_path.exists()


def test_normal_runs_still_return_output_and_timeouts_still_work() -> None:
    code, out, err, timed_out, cancelled = godot._run(
        [sys.executable, "-c", "import sys; print('hi'); print('e', file=sys.stderr); sys.exit(3)"],
        timeout_s=30,
        env={},
    )
    assert (code, out.strip(), err.strip(), timed_out, cancelled) == (3, "hi", "e", False, False)
    code, _o, _e, timed_out, cancelled = godot._run(
        [sys.executable, "-c", "import time; time.sleep(60)"], timeout_s=1, env={}
    )
    assert timed_out and not cancelled and code == -1


@pytest.mark.parametrize("big", [200_000])
def test_a_chatty_process_cannot_block_on_a_full_pipe(big: int) -> None:
    code, out, _err, timed_out, _c = godot._run(
        [sys.executable, "-c", f"print('x' * {big})"], timeout_s=30, env={}
    )
    assert code == 0 and not timed_out and len(out.strip()) == big
