"""The environment of the programs rpggen starts: Godot, git, 7-Zip, the editor (T12.63).

The frozen Linux build's bootloader points ``LD_LIBRARY_PATH`` at the bundle (and keeps the
user's value in ``LD_LIBRARY_PATH_ORIG``), and the Qt runtime hook sets ``QT_PLUGIN_PATH``. A
child that inherits them loads the bundle's copies of system libraries (fontconfig, X11, zlib):
Godot can abort on start. ``restore_library_path`` puts the user's value back as soon as the
frozen app starts (the dynamic loader read the variable when the process started, so rpggen
itself is not affected); ``child_env`` also leaves out the variables that only the bundle needs.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping, MutableMapping

LIBRARY_PATH_VARS = ("LD_LIBRARY_PATH",)
# set for the app's own Qt; another Qt program would load the bundle's plugins
BUNDLE_ONLY_VARS = ("QT_PLUGIN_PATH", "QML2_IMPORT_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH")
BUNDLE_ONLY_PREFIXES = ("_PYI_", "_MEI")


def _frozen(frozen: bool | None) -> bool:
    return bool(getattr(sys, "frozen", False)) if frozen is None else frozen


def restore_library_path(
    environ: MutableMapping[str, str] | None = None, frozen: bool | None = None
) -> None:
    """The frozen app: the user's own ``LD_LIBRARY_PATH`` again (none when they had none)."""
    if not _frozen(frozen):
        return
    env = os.environ if environ is None else environ
    for var in LIBRARY_PATH_VARS:
        original = env.pop(f"{var}_ORIG", None)
        if original is not None:
            env[var] = original
        else:
            env.pop(var, None)


def child_env(
    base: Mapping[str, str] | None = None, frozen: bool | None = None
) -> dict[str, str] | None:
    """The environment for a program rpggen starts, or None (inherit it unchanged) when rpggen
    is not frozen and ``base`` is not given."""
    if not _frozen(frozen):
        return None if base is None else dict(base)
    env = dict(os.environ if base is None else base)
    restore_library_path(env, frozen=True)
    for key in list(env):
        if key in BUNDLE_ONLY_VARS or key.startswith(BUNDLE_ONLY_PREFIXES):
            del env[key]
    return env
