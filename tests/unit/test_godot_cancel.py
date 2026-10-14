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


# ------------------------------------------------------------------------ live output (T12.19)


def _fake_godot(tmp_path: Path, body: str) -> Path:
    """A "Godot" that runs ``body`` (Python); the arguments rpggen passes are ignored."""
    script = tmp_path / "fake.py"
    script.write_text(body, encoding="utf-8")
    if sys.platform == "win32":
        fake = tmp_path / "fake_godot.bat"
        fake.write_text(f'@"{sys.executable}" "{script}"\r\n')
    else:
        fake = tmp_path / "fake_godot.sh"
        fake.write_text(f'#!/bin/sh\n"{sys.executable}" "{script}"\n')
        fake.chmod(0o755)
    return fake


PAUSING = (
    "import sys, time\n"
    "print('first line', flush=True)\n"
    "time.sleep(1.5)\n"
    "print('error text', file=sys.stderr, flush=True)\n"
    "print('second line', flush=True)\n"
)


def test_on_line_receives_lines_before_the_process_exits(tmp_path: Path) -> None:
    fake = _fake_godot(tmp_path, PAUSING)
    seen: list[tuple[float, str]] = []
    started = time.monotonic()
    run = godot.run_godot(
        fake,
        tmp_path,
        [],
        timeout_s=60,
        log_name="live",
        log_dir=tmp_path / "logs",
        on_line=lambda line: seen.append((time.monotonic() - started, line)),
    )
    total = time.monotonic() - started
    lines = [line for _t, line in seen]
    # The program prints its last two lines one right after the other, to two pipes that are
    # read by two threads: which of the two is handed on first is not decided by rpggen (it
    # was "error text" nearly always, and now and then it was not). What is: every line
    # arrives, a stream keeps its own order, and a line printed 1.5 s before the others is
    # there before them.
    assert lines[0] == "first line" and sorted(lines[1:]) == ["error text", "second line"]
    assert seen[0][0] < total - 1.0  # the first line came while the program was still running
    assert run.stdout.splitlines() == ["first line", "second line"]
    assert run.stderr.strip() == "error text"
    # the log has both streams, every line whole and once
    logged = run.log_path.read_text(encoding="utf-8").splitlines()
    assert logged[0] == "first line" and sorted(logged[1:]) == ["error text", "second line"]


def test_the_log_file_is_written_while_the_process_runs_and_survives_a_cancel(
    tmp_path: Path,
) -> None:
    fake = _fake_godot(
        tmp_path, "import time\nprint('before the crash', flush=True)\ntime.sleep(60)\n"
    )
    flag = threading.Event()
    log_dir = tmp_path / "logs"
    log_path = log_dir / "godot_crash.log"

    def watcher() -> None:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if log_path.exists() and "before the crash" in log_path.read_text(encoding="utf-8"):
                flag.set()  # the line is already on disk although Godot is still running
                return
            time.sleep(0.05)

    threading.Thread(target=watcher, daemon=True).start()
    started = time.monotonic()
    run = godot.run_godot(
        fake,
        tmp_path,
        [],
        timeout_s=120,
        log_name="crash",
        log_dir=log_dir,
        is_cancelled=flag.is_set,
    )
    assert run.cancelled and time.monotonic() - started < 15
    assert "before the crash" in log_path.read_text(encoding="utf-8")


def test_a_chatty_program_is_still_cancelled_within_a_fraction_of_a_second(tmp_path: Path) -> None:
    fake = _fake_godot(
        tmp_path,
        "import sys, time\nwhile True:\n    print('x' * 200, flush=True)\n    time.sleep(0.001)\n",
    )
    flag = threading.Event()
    threading.Timer(1.0, flag.set).start()
    lines: list[str] = []
    started = time.monotonic()
    run = godot.run_godot(
        fake,
        tmp_path,
        [],
        timeout_s=120,
        log_name="chatty",
        log_dir=tmp_path / "logs",
        is_cancelled=flag.is_set,
        on_line=lines.append,
    )
    assert run.cancelled and time.monotonic() - started < 3.5  # 1 s + the kill (0.2 s poll)
    assert len(lines) > 50


def test_the_step_protocol_is_parsed() -> None:
    parse = godot.parse_step
    assert parse("@rpggen step build 7/31 tileset") == ("build", 7, 31, "tileset")
    assert parse("@rpggen step validate 12/12 scenes and menus\r") == (
        "validate",
        12,
        12,
        "scenes and menus",
    )
    assert parse("@rpggen step build 1/2") == ("build", 1, 2, "")
    for other in ("[rpggen] INFO running x", "@rpggen steps", "", "  text @rpggen step a 1/2 b"):
        assert parse(other) is None


def test_the_forwarder_batches_prefixes_and_keeps_progress_lines_out_of_the_log() -> None:
    logs: list[str] = []
    steps: list[tuple[str, int, int, str]] = []
    forwarder = godot.LineForwarder(
        "build", logs.append, lambda *a: steps.append(a), interval=3600, max_batch=3
    )
    for line in ("one", "@rpggen step build 1/2 first", "two", "three", "four", "five"):
        forwarder.feed(line)
    assert logs == [] and steps == [("build", 1, 2, "first")]  # nothing sent before a tick
    forwarder.close()  # sends what is left, at most 3 lines at a time
    assert logs == ["[godot] one\n[godot] two\n[godot] three", "[godot] four\n[godot] five"]
    assert steps == [("build", 1, 2, "first")]  # build has the protocol: no "last line" steps


def test_without_the_protocol_the_last_line_stands_in_for_the_step() -> None:
    logs: list[str] = []
    steps: list[tuple[str, int, int, str]] = []
    forwarder = godot.LineForwarder(
        "import", logs.append, lambda *a: steps.append(a), interval=3600
    )
    for line in ("importing a.png", "importing b.png", ""):
        forwarder.feed(line)
    forwarder.close()
    assert steps == [("import", 0, 0, "importing b.png")]


def test_the_forwarder_sends_on_its_own_timer() -> None:
    logs: list[str] = []
    forwarder = godot.LineForwarder("import", logs.append, interval=0.05)
    forwarder.feed("hello")
    deadline = time.monotonic() + 3
    while not logs and time.monotonic() < deadline:
        time.sleep(0.02)
    forwarder.close()
    assert logs == ["[godot] hello"]
