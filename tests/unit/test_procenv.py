"""T12.63: programs started by the frozen app do not inherit the bundle's library path."""

from __future__ import annotations

from rpggen import procenv

FROZEN_ENV = {
    "PATH": "/usr/bin",
    "HOME": "/home/me",
    "LD_LIBRARY_PATH": "/opt/rpggen/_internal",
    "LD_LIBRARY_PATH_ORIG": "/opt/mine",
    "QT_PLUGIN_PATH": "/opt/rpggen/_internal/PySide6/Qt/plugins",
    "_PYI_ARCHIVE_FILE": "/opt/rpggen/rpggen-cli",
    "_PYI_PARENT_PROCESS_LEVEL": "1",
}


def test_not_frozen_inherits_unchanged() -> None:
    assert procenv.child_env(frozen=False) is None
    assert procenv.child_env(FROZEN_ENV, frozen=False) == FROZEN_ENV
    env = dict(FROZEN_ENV)
    procenv.restore_library_path(env, frozen=False)
    assert env == FROZEN_ENV


def test_frozen_children_get_the_users_library_path_and_no_bundle_variables() -> None:
    env = procenv.child_env(FROZEN_ENV, frozen=True)
    assert env == {"PATH": "/usr/bin", "HOME": "/home/me", "LD_LIBRARY_PATH": "/opt/mine"}
    assert FROZEN_ENV["LD_LIBRARY_PATH"] == "/opt/rpggen/_internal"  # the base is not changed


def test_no_original_value_means_no_library_path() -> None:
    env = {"LD_LIBRARY_PATH": "/opt/rpggen/_internal", "PATH": "/usr/bin"}
    procenv.restore_library_path(env, frozen=True)
    assert env == {"PATH": "/usr/bin"}


def test_restoring_in_place_keeps_the_apps_own_qt_plugin_path() -> None:
    env = dict(FROZEN_ENV)
    procenv.restore_library_path(env, frozen=True)
    assert env["LD_LIBRARY_PATH"] == "/opt/mine" and "LD_LIBRARY_PATH_ORIG" not in env
    assert env["QT_PLUGIN_PATH"] == FROZEN_ENV["QT_PLUGIN_PATH"]  # the GUI still needs it
