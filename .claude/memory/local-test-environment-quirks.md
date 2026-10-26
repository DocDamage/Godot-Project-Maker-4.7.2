---
name: local-test-environment-quirks
description: "How to get the rpggen test suite running on this machine (system Python, the FAT32 F: drive, where Godot is, what still needs care)"
metadata:
  node_type: memory
  type: reference
  originSessionId: b50f06c3-9e70-4eca-af84-3d3728b58919
  modified: 2026-10-25T22:31:27.642Z
---

State as of 2026-10-24 (the repo is at `F:\Godot Project Maker`):

- Use the system Python 3.13 (`python`, `C:\Python313`). On 2026-10-24 the user asked for the missing tools system-wide: `py7zr`, `zstandard` and `pytest-qt` are now installed (pip put them in the per-user site-packages, `C:\Users\Doc\AppData\Roaming\Python\Python313`, as it did Pillow, numpy and jsonschema; `C:\Python313` itself needs admin). The 7z/rar, Tiled-zstd and GUI tests pass with plain `python -m pytest` now; no scratch venv is needed. The repo's `.venv` is still broken (made for another account).
- **F: is FAT32.** It keeps no file time before 1980 and only every other second (`os.utime(p, (1, 1))` raises WinError 87), records no ownership (plain `git` says "dubious ownership": use `git -c safe.directory=* ...`, or `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0=*` for tests that run git), and cannot hold junctions (put a junction on C:, e.g. the session scratchpad). Two tests that set 1970 times were moved to 1982 on 2026-10-24.
- Do not set `APPDATA` for a Python process: it moves the per-user site-packages and imports such as `jsonschema` fail. Godot runs are fine without it.
- Godot 4.7.2 console is in the repo root (git-ignored): `Godot_v4.7.2-stable_win64_console.exe`; set `RPGGEN_GODOT` to it. Scratch work, `--basetemp`, `TEMP`/`TMP` go under `F:\rpggen_scratch\` (the project's rule).
- The whole unit suite takes about an hour here; the GDScript suite (`python -m rpggen.dev godot-test`) a few minutes. Running Godot at the same time slows the timing-sensitive cancel tests.
- `C:\Python313\Lib\site-packages\tests` is a stray package that **pylibyaml 0.1.0** installs (April 2026). The repo's `tests` has no `__init__.py`, so the stray regular package wins and test files that import `tests.gui...` fail to collect (5 GUI files; the whole run aborts at collection). Workaround without touching the system Python: run pytest through a wrapper that sets `sys.modules["tests"]` to a module whose `__path__` is the repo's `tests` folder, then calls `pytest.main`. Removing pylibyaml would fix it for good, but ask the user first.
- The display is scaled to 150 %; CONTRIBUTING (Documentation) says which Qt variables give 100 % screenshots.

- **F: is only ~34 GB and fills up**: on 2026-10-24 a batch of real-pack builds (each project 1-2 GB, plus pytest basetemps) filled it and the builds failed with ENV-005 / WinError 112. Delete each scratch build after use; deleting many files on FAT32 is very slow (minutes). The user cleared `F:\rpggen_scratch` once to make room.

- **Line endings:** the repo is LF and `core.autocrlf` is false. A Python patch script that writes with `open(p, "w")` writes CRLF on Windows (git warns "CRLF will be replaced by LF"); write with `newline="\n"` or bytes. On 2026-10-25 nine files had to be converted back.
- Scripts that call `inventory.build_inventory` start worker processes, so they must run from a file, not from `python - <<EOF` (stdin): the workers fail with `OSError: [Errno 22] ... '<stdin>'` and BrokenProcessPool.
- `rpggen.dev update-goldens` needs `python -m` without `-P` (with `-P` the repo is not on the path).

Earlier drive letters vanished mid-run (D:, then F: once): when a run fails broadly and fast, check the drive is still there.
