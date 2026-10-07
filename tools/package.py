"""Build the Windows release artifacts (T10.02).

    python tools/package.py [--installer] [--smoke] [--godot PATH] [--skip-build]

Steps: PyInstaller one-folder build -> dist/rpggen/ (rpggen.exe + rpggen-cli.exe) ->
dist/LICENSE_AND_NOTICES.txt -> portable zip -> (with --installer) Inno Setup installer ->
(with --smoke) generate the sample pack with the frozen rpggen-cli.exe -> SHA256SUMS.txt.

Signing happens between the build and the checksums in the release workflow, so run this
script with --skip-build to only (re)create the zip, the installer and the checksums.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DIST = REPO / "dist"
APP = DIST / "rpggen"


def version() -> str:
    sys.path.insert(0, str(REPO))
    from rpggen import __version__

    return __version__


def build_bundle() -> None:
    shutil.rmtree(REPO / "build", ignore_errors=True)
    shutil.rmtree(APP, ignore_errors=True)
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "packaging/rpggen.spec", "--noconfirm", "--clean"],
        cwd=REPO,
        check=True,
    )
    for exe in ("rpggen.exe", "rpggen-cli.exe"):
        if not (APP / exe).is_file():
            raise SystemExit(f"the build did not produce {exe}")


def write_license_file() -> Path:
    out = DIST / "LICENSE_AND_NOTICES.txt"
    text = (REPO / "LICENSE").read_text(encoding="utf-8")
    notices = (REPO / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    out.write_text(f"{text}\n\n{'=' * 72}\n\n{notices}", encoding="utf-8", newline="\n")
    return out


def portable_zip(ver: str) -> Path:
    out = DIST / f"rpggen-{ver}-portable.zip"
    out.unlink(missing_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(APP.rglob("*")):
            if path.is_file():
                zf.write(path, Path("rpggen") / path.relative_to(APP))
    return out


def find_iscc() -> str | None:
    found = shutil.which("iscc")
    if found:
        return found
    for base in (os.environ.get("PROGRAMFILES(X86)"), os.environ.get("PROGRAMFILES")):
        if base:
            candidate = Path(base) / "Inno Setup 6" / "ISCC.exe"
            if candidate.is_file():
                return str(candidate)
    return None


def installer(ver: str) -> Path:
    iscc = find_iscc()
    if iscc is None:
        raise SystemExit("Inno Setup (iscc) was not found; install it or omit --installer")
    subprocess.run([iscc, f"/DAppVersion={ver}", "packaging/installer.iss"], cwd=REPO, check=True)
    out = DIST / f"rpggen-{ver}-setup.exe"
    if not out.is_file():
        raise SystemExit("Inno Setup did not produce the installer")
    return out


def bundled(name: str) -> Path:
    """A data folder inside the one-folder build (PyInstaller 6 keeps them under _internal)."""
    inner = APP / "_internal" / name
    return inner if inner.exists() else APP / name


def smoke(godot: str | None) -> None:
    """The frozen CLI must generate the bundled sample pack (exit code 0)."""
    godot = godot or os.environ.get("RPGGEN_GODOT")
    if not godot:
        raise SystemExit("--smoke needs --godot or RPGGEN_GODOT")
    with tempfile.TemporaryDirectory(prefix="rpggen_frozen_") as tmp:
        target = Path(tmp) / "out"
        cmd = [
            str(APP / "rpggen-cli.exe"),
            "generate",
            "--pack",
            str(bundled("sample_pack")),
            "--target",
            str(target),
            "--godot",
            godot,
        ]
        print("frozen smoke test:", " ".join(cmd))
        code = subprocess.run(cmd, check=False).returncode
        if code != 0:
            raise SystemExit(f"frozen smoke test failed (exit code {code})")
        if not (target / "project.godot").is_file():
            raise SystemExit("frozen smoke test: no project was written")
    print("frozen smoke test passed")


def checksums() -> Path:
    out = DIST / "SHA256SUMS.txt"
    lines = []
    for path in sorted(DIST.glob("rpggen-*")):
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            lines.append(f"{digest}  {path.name}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skip-build", action="store_true", help="reuse dist/rpggen")
    parser.add_argument(
        "--installer", action="store_true", help="also build the Inno Setup installer"
    )
    parser.add_argument("--smoke", action="store_true", help="run the frozen smoke test")
    parser.add_argument("--godot", help="Godot executable for --smoke")
    args = parser.parse_args()
    DIST.mkdir(exist_ok=True)
    ver = version()
    if not args.skip_build:
        build_bundle()
    write_license_file()
    if args.smoke:
        smoke(args.godot)
    print("portable zip:", portable_zip(ver))
    if args.installer:
        print("installer:", installer(ver))
    print("checksums:", checksums())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
