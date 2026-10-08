"""The Godot version rpggen builds projects for: the single place to change on a Godot update.

``python tools/bump_godot.py 4.8.1`` rewrites this file, the CI workflows and the error-code
texts, and lists what still needs a person (re-running the Godot probes and the test pass).
"""

from __future__ import annotations

VERSION = "4.7.2"  # the validated version: downloaded by the app, used by CI, named in messages
STATUS = "stable"

# The SHA-512 of the official zip of VERSION for each platform, as published in the release's
# SHA512-SUMS.txt (https://github.com/godotengine/godot/releases/tag/4.7.2-stable). A download
# must match this value, so that a changed release or a tampered mirror is refused even when its
# own checksum file agrees with it. ``tools/bump_godot.py`` rewrites it; compare the new values
# with the release page by eye before committing.
SHA512 = {
    "windows": "83decd58fdf67b9d657958a1ae6bf1929c20785315a81effe245874cdc57acb709bf868e00778a96984338c1b29dafdb453c6847747694621c6ecf5da2259993",
    "linux": "9aa00f7a605200940bce3027a567b782f49bd8e940dd06ae9e987bd65aee1b1467edd56ed84fcdcbdd44354bf613bdbb4e5d2913e925850368e150c59ed54c65",
    "macos": "38aa16e5bba2083941fc5b3e54be0089bd4cc35e32415f5b9fd9a8a6a7b9818255d44532ea8ef94b5aef56c4b407c2d634fa4f657e4ebe681ebbf59b7bac69ca",
}

_parts = VERSION.split(".")
MAJOR, MINOR, PATCH = int(_parts[0]), int(_parts[1]), int(_parts[2])
MAJOR_MINOR = f"{MAJOR}.{MINOR}"  # the series the gate accepts (4.7.x)
SUPPORTED = (MAJOR, MINOR, PATCH, STATUS)
