"""Entry point of rpggen-cli.exe (the console build)."""

from __future__ import annotations

import multiprocessing
import sys


def main() -> int:
    from rpggen.cli import main as cli_main

    return cli_main(sys.argv[1:])


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
