"""The Godot version rpggen builds projects for: the single place to change on a Godot update.

``python tools/bump_godot.py 4.8.1`` rewrites this file, the CI workflows and the error-code
texts, and lists what still needs a person (re-running the Godot probes and the test pass).
"""

from __future__ import annotations

VERSION = "4.7.2"  # the validated version: downloaded by the app, used by CI, named in messages
STATUS = "stable"

_parts = VERSION.split(".")
MAJOR, MINOR, PATCH = int(_parts[0]), int(_parts[1]), int(_parts[2])
MAJOR_MINOR = f"{MAJOR}.{MINOR}"  # the series the gate accepts (4.7.x)
SUPPORTED = (MAJOR, MINOR, PATCH, STATUS)
