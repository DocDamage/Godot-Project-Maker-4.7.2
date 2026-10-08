"""Entry point of rpggen.exe (the windowed build)."""

from __future__ import annotations

import io
import multiprocessing
import sys


def main() -> int:
    # A windowed Windows build has no console: stdout/stderr are None and would break print().
    if sys.stdout is None:
        sys.stdout = io.StringIO()
    if sys.stderr is None:
        sys.stderr = io.StringIO()
    from rpggen import procenv
    from rpggen.cli import main as cli_main

    procenv.restore_library_path()  # children get the user's LD_LIBRARY_PATH, not the bundle's

    return cli_main(sys.argv[1:] or ["gui"])


if __name__ == "__main__":
    multiprocessing.freeze_support()  # analysis uses processes; needed in the frozen app
    raise SystemExit(main())
