"""Build the release artifacts of this platform (T10.02, T12.63).

    python tools/package.py [--installer] [--smoke] [--godot PATH] [--skip-build]

Steps: PyInstaller one-folder build -> dist/LICENSE_AND_NOTICES.txt -> (with --smoke) generate the
sample pack with the frozen rpggen-cli -> the platform's packages -> SHA256SUMS.txt.

* Windows: dist/rpggen/ (rpggen.exe + rpggen-cli.exe) -> rpggen-<v>-portable.zip and, with
  --installer, the Inno Setup installer rpggen-<v>-setup.exe.
* Linux: dist/rpggen/ -> rpggen-<v>-linux-x86_64.tar.gz and rpggen-<v>-x86_64.AppImage (the
  pinned appimagetool and AppImage runtime are downloaded to .cache/appimage and checked against
  their SHA-256 first). Build on the oldest supported distribution (glibc floor).
* macOS: dist/rpggen.app (rpggen + rpggen-cli in Contents/MacOS) -> rpggen-<v>-macos-<arch>.zip,
  made with ``ditto`` so that the links and modes inside the app survive. Unsigned.

Signing happens between the build and the checksums in the release workflow, so run this
script with --skip-build to only (re)create the packages and the checksums.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DIST = REPO / "dist"
CACHE = REPO / ".cache" / "appimage"
LINUX_FILES = REPO / "packaging" / "linux"
IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
EXE_SUFFIX = ".exe" if IS_WINDOWS else ""
APP = DIST / ("rpggen.app" if IS_MAC else "rpggen")

# The AppImage tools, pinned by release and SHA-256 (the digests GitHub lists for the assets).
APPIMAGETOOL = (
    "https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage",
    "ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0",
)
APPIMAGE_RUNTIME = (
    "https://github.com/AppImage/type2-runtime/releases/download/20251108/runtime-x86_64",
    "2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d",
)


def version() -> str:
    sys.path.insert(0, str(REPO))
    from rpggen import __version__

    return __version__


def exe_dir() -> Path:
    """The folder that holds rpggen and rpggen-cli."""
    return APP / "Contents" / "MacOS" if IS_MAC else APP


def executable(name: str) -> Path:
    return exe_dir() / f"{name}{EXE_SUFFIX}"


def build_bundle() -> None:
    shutil.rmtree(REPO / "build", ignore_errors=True)
    shutil.rmtree(DIST / "rpggen", ignore_errors=True)
    shutil.rmtree(DIST / "rpggen.app", ignore_errors=True)
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "packaging/rpggen.spec", "--noconfirm", "--clean"],
        cwd=REPO,
        check=True,
    )
    for name in ("rpggen", "rpggen-cli"):
        if not executable(name).is_file():
            raise SystemExit(f"the build did not produce {executable(name).name}")


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


# ------------------------------------------------------------------ Linux


def linux_tarball(ver: str) -> Path:
    """rpggen-<v>-linux-x86_64.tar.gz with an ``rpggen/`` folder (modes and links kept)."""
    out = DIST / f"rpggen-{ver}-linux-x86_64.tar.gz"
    out.unlink(missing_ok=True)
    with tarfile.open(out, "w:gz") as tf:
        tf.add(APP, arcname="rpggen")
        tf.add(DIST / "LICENSE_AND_NOTICES.txt", arcname="rpggen/LICENSE_AND_NOTICES.txt")
    return out


def _pinned_download(url: str, sha256: str, dst: Path) -> Path:
    """``url`` into ``dst`` unless a file with the right SHA-256 is there already."""

    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    if dst.is_file() and digest(dst) == sha256:
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    part = dst.with_name(dst.name + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "rpggen-release"})
    with urllib.request.urlopen(request, timeout=120) as resp, part.open("wb") as out:  # noqa: S310
        shutil.copyfileobj(resp, out)
    if digest(part) != sha256:
        part.unlink()
        raise SystemExit(f"{url}: the SHA-256 does not match the pinned value")
    part.replace(dst)
    dst.chmod(0o755)
    return dst


def app_dir(root: Path) -> Path:
    """The AppDir: AppRun, the desktop entry and icon, and the bundle in usr/lib/rpggen."""
    shutil.rmtree(root, ignore_errors=True)
    lib = root / "usr" / "lib" / "rpggen"
    shutil.copytree(APP, lib, symlinks=True)
    shutil.copy2(DIST / "LICENSE_AND_NOTICES.txt", lib / "LICENSE_AND_NOTICES.txt")
    shutil.copy2(LINUX_FILES / "AppRun", root / "AppRun")
    (root / "AppRun").chmod(0o755)
    shutil.copy2(LINUX_FILES / "rpggen.desktop", root / "rpggen.desktop")
    shutil.copy2(LINUX_FILES / "rpggen.png", root / "rpggen.png")
    shutil.copy2(LINUX_FILES / "rpggen.png", root / ".DirIcon")
    apps = root / "usr" / "share" / "applications"
    icons = root / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps"
    apps.mkdir(parents=True)
    icons.mkdir(parents=True)
    shutil.copy2(LINUX_FILES / "rpggen.desktop", apps / "rpggen.desktop")
    shutil.copy2(LINUX_FILES / "rpggen.png", icons / "rpggen.png")
    return root


def appimage(ver: str) -> Path:
    tool = _pinned_download(*APPIMAGETOOL, CACHE / "appimagetool-x86_64.AppImage")
    runtime = _pinned_download(*APPIMAGE_RUNTIME, CACHE / "runtime-x86_64")
    out = DIST / f"rpggen-{ver}-x86_64.AppImage"
    out.unlink(missing_ok=True)
    root = app_dir(DIST / "rpggen.AppDir")
    # no FUSE on CI runners and in containers: the tool unpacks itself and runs
    env = {**os.environ, "ARCH": "x86_64", "APPIMAGE_EXTRACT_AND_RUN": "1"}
    subprocess.run(
        [str(tool), "--no-appstream", "--runtime-file", str(runtime), str(root), str(out)],
        cwd=DIST,
        env=env,
        check=True,
    )
    shutil.rmtree(root, ignore_errors=True)
    if not out.is_file():
        raise SystemExit("appimagetool did not produce the AppImage")
    out.chmod(0o755)
    return out


# ------------------------------------------------------------------ macOS


def mac_arch() -> str:
    return "arm64" if platform.machine() in ("arm64", "aarch64") else "x86_64"


def mac_zip(ver: str) -> Path:
    """rpggen-<v>-macos-<arch>.zip holding rpggen.app (``ditto`` keeps links, modes and
    extended attributes, which a plain zip would lose)."""
    out = DIST / f"rpggen-{ver}-macos-{mac_arch()}.zip"
    out.unlink(missing_ok=True)
    # nothing is added to the app after the build: that would break PyInstaller's ad-hoc
    # signature (LICENSE and THIRD_PARTY_NOTICES.md are bundled by the spec)
    subprocess.run(
        ["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(APP), str(out)], check=True
    )
    return out


# ------------------------------------------------------------------ all platforms


def bundled(name: str) -> Path:
    """A data folder inside the build: under _internal (PyInstaller 6, Windows and Linux) or in
    the app's Resources (macOS)."""
    for candidate in (
        APP / "_internal" / name,
        APP / "Contents" / "Resources" / name,
        APP / "Contents" / "Frameworks" / name,
        APP / name,
    ):
        if candidate.exists():
            return candidate
    raise SystemExit(f"{name} is not in the build")


def smoke(godot: str | None) -> None:
    """The frozen CLI must generate the bundled sample pack (exit code 0)."""
    godot = godot or os.environ.get("RPGGEN_GODOT")
    if not godot:
        raise SystemExit("--smoke needs --godot or RPGGEN_GODOT")
    with tempfile.TemporaryDirectory(prefix="rpggen-frozen-") as tmp:
        target = Path(tmp) / "out"
        cmd = [
            str(executable("rpggen-cli")),
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
    # libsndfile is in the build and decodes Ogg Vorbis (T13.17)
    cmd = [str(executable("rpggen-cli")), "audio-check"]
    print("frozen smoke test:", " ".join(cmd))
    code = subprocess.run(cmd, check=False).returncode
    if code != 0:
        raise SystemExit(f"frozen smoke test: the audio decode failed (exit code {code})")
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
    parser.add_argument("--skip-build", action="store_true", help="reuse the build in dist/")
    parser.add_argument(
        "--installer", action="store_true", help="also build the Inno Setup installer (Windows)"
    )
    parser.add_argument("--smoke", action="store_true", help="run the frozen smoke test")
    parser.add_argument("--godot", help="Godot executable for --smoke")
    parser.add_argument(
        "--no-appimage", action="store_true", help="Linux: only the tar.gz (no download)"
    )
    args = parser.parse_args()
    DIST.mkdir(exist_ok=True)
    ver = version()
    if not args.skip_build:
        build_bundle()
    write_license_file()
    if args.smoke:
        smoke(args.godot)
    if IS_WINDOWS:
        print("portable zip:", portable_zip(ver))
        if args.installer:
            print("installer:", installer(ver))
    elif IS_MAC:
        print("app zip:", mac_zip(ver))
    else:
        print("tarball:", linux_tarball(ver))
        if not args.no_appimage:
            print("AppImage:", appimage(ver))
    print("checksums:", checksums())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
