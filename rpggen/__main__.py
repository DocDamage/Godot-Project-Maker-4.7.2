from __future__ import annotations

import multiprocessing

from rpggen.cli import main

if __name__ == "__main__":
    multiprocessing.freeze_support()  # analysis uses processes (needed in the frozen Windows app)
    raise SystemExit(main())
