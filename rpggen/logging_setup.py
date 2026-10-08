from __future__ import annotations

import contextlib
import logging
import logging.handlers
import re
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path

FORMAT = "%(asctime)s %(levelname)-7s [%(run_id)s] %(name)s: %(message)s"
LOG_NAME = "rpggen.log"
MAX_BYTES = 2 * 1024 * 1024  # a log file is rotated at 2 MB ...
BACKUPS = 5  # ... and five older ones are kept (rpggen.log.1 ... rpggen.log.5)

_run_id = "-"  # the generation that is running now; "-" outside a run
_RECORD_START = re.compile(r"^\d{4}-\d{2}-\d{2} ")


def new_run_id() -> str:
    """Eight hex characters that tie the lines of one generation together (and the report)."""
    return uuid.uuid4().hex[:8]


def current_run_id() -> str:
    return _run_id


@contextlib.contextmanager
def run_context(run_id: str) -> Iterator[str]:
    """Every log record made while this is open carries ``run_id`` (from any thread)."""
    global _run_id
    previous, _run_id = _run_id, run_id
    try:
        yield run_id
    finally:
        _run_id = previous


class RunIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = _run_id
        return True


def configure(log_dir: Path, verbose: bool) -> None:
    """A rotating file handler (DEBUG, 5 x 2 MB) at ``log_dir/rpggen.log`` plus a console handler
    (INFO or DEBUG). The command line and the wizard use the same folder (``paths.log_dir()``)."""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    for handler in list(root.handlers):
        if getattr(handler, "_rpggen", False):
            root.removeHandler(handler)
            handler.close()
    formatter = logging.Formatter(FORMAT)
    run_filter = RunIdFilter()
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / LOG_NAME, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    new_handlers: tuple[logging.Handler, ...] = (file_handler, console)
    for handler in new_handlers:
        handler.setFormatter(formatter)
        handler.addFilter(run_filter)
        handler._rpggen = True  # type: ignore[attr-defined]
        root.addHandler(handler)


def log_files(log_dir: Path) -> list[Path]:
    """The log and its rotated copies, oldest first."""
    log_dir = Path(log_dir)
    older = [log_dir / f"{LOG_NAME}.{n}" for n in range(BACKUPS, 0, -1)]
    return [p for p in (*older, log_dir / LOG_NAME) if p.is_file()]


def read_run_lines(log_dir: Path, run_id: str) -> list[str]:
    """The lines of the application log that belong to one run (``[run_id]`` in the header of a
    record; the lines of a traceback follow the record they belong to)."""
    wanted = f"[{run_id}]"
    kept: list[str] = []
    inside = False
    for path in log_files(log_dir):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if _RECORD_START.match(line):
                inside = wanted in line.split(": ", 1)[0]
            if inside:
                kept.append(line)
    return kept


def tail_lines(log_dir: Path, count: int = 300) -> list[str]:
    """The last ``count`` lines of the application log (for a crash outside any run)."""
    lines: list[str] = []
    for path in log_files(log_dir):
        lines.extend(path.read_text(encoding="utf-8", errors="replace").splitlines())
    return lines[-count:]
