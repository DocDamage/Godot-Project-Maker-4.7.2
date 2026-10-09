from __future__ import annotations

import rpggen
from rpggen import cli


def test_import_and_version() -> None:
    assert rpggen.__version__ == "1.2.0"
    assert cli.main(["version"]) == 0


def test_unimplemented_commands_exit_2() -> None:
    assert cli.main(["generate"]) == 2
    assert cli.main(["analyze"]) == 2
