# Releasing rpggen

## What a release contains

| File | Built on | What |
|------|----------|------|
| `rpggen-<version>-setup.exe` | `windows-latest` | Inno Setup installer: per-user install (no administrator), Start-menu shortcut, uninstaller, license page with MIT + the third-party notices |
| `rpggen-<version>-portable.zip` | `windows-latest` | the same one-folder build, unzip and run `rpggen\rpggen.exe` |
| `rpggen-<version>-x86_64.AppImage` | `ubuntu-22.04` | the Linux one-folder build in an AppImage (`AppRun` starts the GUI; `… cli <args>` the CLI) |
| `rpggen-<version>-linux-x86_64.tar.gz` | `ubuntu-22.04` | the same build as a folder: `rpggen/rpggen`, `rpggen/rpggen-cli` |
| `rpggen-<version>-macos-arm64.zip` | `macos-14` | `rpggen.app` (both executables in `Contents/MacOS`), zipped with `ditto`; unsigned |
| `SHA256SUMS.txt` | publish job | SHA-256 of every file above |

The one-folder build holds `rpggen` (windowed GUI) and `rpggen-cli` (console) sharing one set of
libraries (`.exe` on Windows; inside `rpggen.app` on macOS). `tools/package.py` builds the packages
of the platform it runs on with PyInstaller using `packaging/rpggen.spec`, creates
`dist/LICENSE_AND_NOTICES.txt` and the checksums, and with `--smoke` generates the sample pack
through the frozen `rpggen-cli` (expects exit code 0). Windows: the portable zip and, with
`--installer` (Inno Setup 6), the installer. Linux: the tar.gz and the AppImage (`--no-appimage`
skips it); the AppImage is made from `packaging/linux/` (`AppRun`, `rpggen.desktop`,
`rpggen.png`) with appimagetool 1.9.1 and the type2 runtime of release 20251108, both downloaded
to `.cache/appimage` and checked against the SHA-256 pinned in `tools/package.py`. macOS: the
`.app` zip.

The release workflow runs one build job per platform, each with its own frozen smoke test against
the Godot 4.7.2 of that platform (`tools/fetch_godot.py`; the macOS download is the
`macos.universal` zip with its pinned SHA-512). The `publish` job collects the files, writes one
`SHA256SUMS.txt`, checks that every platform is there and attaches everything to the release.

**Libraries of the frozen Linux build.** The bootloader points `LD_LIBRARY_PATH` at the bundle.
The entry points put the user's value back at start (`rpggen/procenv.py`), and every program rpggen
starts (Godot, git, 7-Zip, the editor) gets `procenv.child_env()`, without the bundle's library
and Qt plugin paths. Otherwise Godot loads the bundle's copies of system libraries and can abort.

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

Local test build: `python tools/package.py --smoke --godot <Godot exe> [--installer]`. On Windows
with WSL the Linux packages can be built the same way inside the distribution (Python 3.12, the
Linux lock file, the Linux Godot).

## A reproducible, gated build

* **The lock file.** The release is built from `requirements/release.txt` (every version and hash,
  Python 3.12 on Windows), installed with `pip install --require-hashes -r requirements/release.txt`
  and `pip install --no-build-isolation --no-deps -e .`; never from "whatever is latest". After a
  change to the dependencies in `pyproject.toml` regenerate it and commit it:

  ```bat
  pip install pip-tools
  pip-compile --generate-hashes --allow-unsafe --extra dev --extra maps --strip-extras -o requirements/release.txt pyproject.toml
  ```

  CI regenerates the file and fails when it differs, so a stale lock never reaches a tag.

  The Linux and macOS builds install from `requirements/release-linux.txt` and
  `requirements/release-macos.txt`: the same versions (they are compiled with `release.txt` as a
  constraint, and `test_release.py` checks that every shared package has the same version), without
  the Windows-only packages and, on macOS, with `macholib` for PyInstaller. Regenerate them after
  `release.txt`, with [uv](https://docs.astral.sh/uv/):

  ```bat
  uv pip compile pyproject.toml --extra dev --extra maps --generate-hashes --python-version 3.12 --python-platform x86_64-manylinux_2_35 --constraint requirements/release.txt -o requirements/release-linux.txt
  uv pip compile pyproject.toml --extra dev --extra maps --generate-hashes --python-version 3.12 --python-platform aarch64-apple-darwin --constraint requirements/release.txt -o requirements/release-macos.txt
  ```

  The Linux target is glibc 2.35 (Ubuntu 22.04, the build runner): PySide6 6.11 publishes Linux
  wheels for glibc 2.34 and later only, so that is the oldest Linux rpggen runs on.
* **The whole suite first.** `release.yml` calls `ci.yml` (unit, GUI, GDScript, integration, perf on
  Windows and Ubuntu) on the tagged commit before it builds anything.
* **The gate.** A tag build stops while `docs/coverage.md` still has a `*(pending)*` row: the
  held-out accuracy table (T10.09, T10.10) must be filled in with numbers measured on real packs.
* **Pinned actions.** Every third-party action in `.github/workflows/` is pinned to a full commit
  SHA with its tag in a comment; Dependabot proposes updates weekly.

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

### macOS: signing and notarization (a later step)

The macOS app is unsigned for 1.0: PyInstaller gives it an ad-hoc signature (which lets it start
on Apple silicon), and Gatekeeper asks the user to confirm the first launch (the README explains
how). To ship without that step:

1. Join the Apple Developer Program and create a *Developer ID Application* certificate.
2. Store the certificate (p12, base64) and its password as repository secrets, import them into a
   temporary keychain in the `macos` job, and pass `codesign_identity` and an entitlements file to
   `BUNDLE`/`EXE` in `packaging/rpggen.spec` (hardened runtime; PySide6 needs
   `com.apple.security.cs.disable-library-validation`).
3. Notarize the zip with `xcrun notarytool submit … --wait` (an App Store Connect API key as
   secrets), staple the ticket to the app with `xcrun stapler staple rpggen.app`, and zip again.

Until then the release notes and the README carry the Gatekeeper note.

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
