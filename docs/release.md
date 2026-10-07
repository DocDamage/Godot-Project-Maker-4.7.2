# Releasing rpggen

## What a release contains

| File | What |
|------|------|
| `rpggen-<version>-setup.exe` | Inno Setup installer: per-user install (no administrator), Start-menu shortcut, uninstaller, license page with MIT + the third-party notices |
| `rpggen-<version>-portable.zip` | the same one-folder build, unzip and run `rpggen\rpggen.exe` |
| `SHA256SUMS.txt` | SHA-256 of both files |

The one-folder build (`dist/rpggen/`) holds `rpggen.exe` (windowed GUI) and `rpggen-cli.exe`
(console) sharing one set of libraries. `tools/package.py` builds it with PyInstaller using
`packaging/rpggen.spec`, creates `dist/LICENSE_AND_NOTICES.txt`, the portable zip, optionally the
installer (`--installer`, needs Inno Setup 6) and the checksums, and with `--smoke` generates the
sample pack through the frozen `rpggen-cli.exe` (expects exit code 0).

## Procedure

1. All milestone gates are done and CI is green on `main` (Windows and Ubuntu).
2. One version number everywhere: `rpggen/__init__.py`, `pyproject.toml`, the runtime
   `godot_templates/addons/rpg_runtime/VERSION` (and a `CHANGELOG.md` heading),
   `godot_templates/addons/rpg_project_tools/plugin.cfg`, `packaging/version_info.txt` and
   `packaging/installer.iss`. `tests/unit/test_release.py` fails when they disagree.
3. `docs/dev/implementation_notes.md` has no unresolved *stop and report* items and the held-out results
   are published in [coverage.md](coverage.md).
4. Tag and push: `git tag v1.0.0 && git push origin v1.0.0`. `.github/workflows/release.yml` checks
   that the tag equals `v<version>`, builds, runs the frozen smoke test, signs (below), and attaches
   the files and `SHA256SUMS.txt` to the GitHub Release.
5. Download the release on a clean machine, verify the checksum, run the installer, press *Try with
   sample pack*.

Local test build: `python tools/package.py --smoke --godot <Godot exe> [--installer]`.

## Code signing

Windows SmartScreen warns about unsigned downloads. The plan:

1. **Apply** to an open-source signing program. [SignPath Foundation](https://signpath.org/)
   offers free code signing for qualifying open-source projects; confirm the current terms and
   eligibility when you apply (they change). A low-cost signing service or an OV/EV certificate is
   the alternative.
2. When approved, create the project (`rpggen`) and signing policy (`release-signing`) in SignPath,
   connect the GitHub repository, and set in the repository settings: the **variable**
   `SIGNPATH_ORGANIZATION_ID` and the **secret** `SIGNPATH_API_TOKEN`. `release.yml` then signs
   `rpggen.exe`, `rpggen-cli.exe` and the installer; nothing else changes. Without the variable the
   signing steps are skipped and the files are published unsigned.
3. **Until signing exists:** publish the SHA-256 sums (done by the workflow) and tell users, in the
   README, to click *More info → Run anyway* only after comparing the checksum. Add a screenshot of
   the SmartScreen dialog to the README when the first release is out (it needs a real Windows
   machine; `tools/make_doc_screenshots.py` cannot render OS dialogs).

Signing is a **human step**: it needs an account, and its approval is outside this repository.

## Third-party notices

Keep `THIRD_PARTY_NOTICES.md` in step with `[project].dependencies` in `pyproject.toml`
(`test_release.py` checks that every dependency is named). Note the LGPL components (Qt/PySide6,
py7zr) are shipped as separate libraries in the one-folder build so users can replace them.
Audio durations are read by rpggen's own parser (`core/audio_info.py`); do not add a GPL
dependency (a test keeps a deny-list).

## Updating for a new Godot version

The targeted Godot version lives in one file, `rpggen/godot_target.py`. To move to another
release:

```bash
python tools/bump_godot.py 4.7.3      # rewrites it, the CI/release workflows and the error texts
python tools/bump_godot.py --check    # verifies nothing disagrees (a unit test runs this)
```

The app's version gate, the **Download Godot** button, `tools/fetch_godot.py` and the generated
`project.godot` all read that file. The tool prints a checklist of what a person must still do:
re-run the API probes in `godot_templates/tests/probes`, the integration tests and the GDScript
tests with the new Godot, and review any golden diff. A patch release of the same series (4.7.x)
already works without a bump: the app accepts it with a warning (`ENV-003`).

## Before you tag

Run the manual test pass of M11 (T11.29 in `docs/spec/M11_pre_release.md`) on a clean Windows
machine with the installer, with the Godot you download from the welcome view, and record each
row as passed or ticketed. The automated gate (T11.30) is `tests/unit`, `tests/gui`, the
integration tests with `RPGGEN_GODOT` set, the GDScript tests (`python -m rpggen.dev godot-test`)
and `python tools/make_doc_screenshots.py` when a page changed.
