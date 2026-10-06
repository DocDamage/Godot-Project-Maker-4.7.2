from __future__ import annotations

import logging
import sys
from pathlib import Path

FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def configure(log_dir: Path, verbose: bool) -> None:
    """File handler (DEBUG) at ``log_dir/rpggen.log`` plus a console handler (INFO or DEBUG)."""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    for handler in list(root.handlers):
        if getattr(handler, "_rpggen", False):
            root.removeHandler(handler)
            handler.close()
    formatter = logging.Formatter(FORMAT)
    file_handler = logging.FileHandler(log_dir / "rpggen.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(formatter)
    new_handlers: tuple[logging.Handler, ...] = (file_handler, console)
    for handler in new_handlers:
        handler._rpggen = True  # type: ignore[attr-defined]
        root.addHandler(handler)
