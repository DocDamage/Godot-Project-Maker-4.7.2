# PyInstaller spec: one-folder build with two executables sharing one set of libraries.
#   rpggen(.exe)      windowed GUI (no console)
#   rpggen-cli(.exe)  console build for scripts and CI
# Build from the repository root:  python -m PyInstaller packaging/rpggen.spec --noconfirm
# Output:  dist/rpggen/ (Windows, Linux); dist/rpggen.app with both executables in
#          Contents/MacOS (macOS, T12.63)
import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))
IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
# the Windows version resource; Linux and macOS have none (the .app gets an Info.plist below)
VERSION_FILE = os.path.join(SPECPATH, "version_info.txt") if IS_WINDOWS else None
ICON = os.path.join(ROOT, "packaging", "rpggen.ico")  # converted with Pillow on macOS
sys.path.insert(0, ROOT)
from rpggen import __version__ as APP_VERSION  # noqa: E402

EXCLUDED_QT = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel", "PySide6.QtWebSockets", "PySide6.QtWebView",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput", "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras",
    "PySide6.QtMultimediaWidgets", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets",
    "PySide6.QtQuick3D", "PySide6.QtQuickControls2", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtGraphs", "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtSql", "PySide6.QtTest",
    "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtPositioning", "PySide6.QtSensors",
    "PySide6.QtSerialPort", "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtSvgWidgets",
    "PySide6.QtTextToSpeech", "PySide6.QtHelp", "PySide6.QtDesigner", "PySide6.QtUiTools",
    "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtSpatialAudio", "PySide6.QtStateMachine",
    "tkinter", "unittest", "pytest", "mypy", "ruff",
]


def tree(src, dest, skip_dirs=(), skip_suffixes=()):
    """(source, destination-folder) pairs for every file under ``src``."""
    out = []
    for folder, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        rel = os.path.relpath(folder, src)
        for name in files:
            if name.endswith(tuple(skip_suffixes)):
                continue
            out.append((os.path.join(folder, name), os.path.normpath(os.path.join(dest, rel))))
    return out


datas = []
# The Godot template project, without its tests and the editor's import cache.
datas += tree(os.path.join(ROOT, "godot_templates"), "godot_templates", skip_dirs={"tests", ".godot"})
datas += tree(os.path.join(ROOT, "sample_pack"), "sample_pack")
datas += tree(os.path.join(ROOT, "sample_pack_side"), "sample_pack_side")
# the samples of the arcade kinds (T16.17), of the farm and of the isometric view (T17.17)
for _sample in ("sample_pack_shmup", "sample_pack_gun", "sample_pack_race", "sample_pack_farm",
                "sample_pack_iso"):
    datas += tree(os.path.join(ROOT, _sample), _sample)
datas += tree(os.path.join(ROOT, "docs"), "docs", skip_dirs={"spec", "dev"})
datas += [(os.path.join(ROOT, name), ".") for name in ("LICENSE", "THIRD_PARTY_NOTICES.md", "README.md")]
datas += [(os.path.join(ROOT, "rpggen", "schema", f), os.path.join("rpggen", "schema"))
          for f in os.listdir(os.path.join(ROOT, "rpggen", "schema")) if f.endswith(".json")]
# the confidence calibration and the vision step's rules, fitted on the answer key (T17.34)
datas += [(os.path.join(ROOT, "rpggen", "data", f), os.path.join("rpggen", "data"))
          for f in os.listdir(os.path.join(ROOT, "rpggen", "data")) if f.endswith(".json")]
# the stylesheet template and the icon set (T15.01, T15.04)
datas += [(os.path.join(ROOT, "rpggen", "gui", "style.qss.in"), os.path.join("rpggen", "gui"))]
ICONS = os.path.join(ROOT, "rpggen", "gui", "icons")
datas += [(os.path.join(ICONS, f), os.path.join("rpggen", "gui", "icons"))
          for f in sorted(os.listdir(ICONS)) if f.endswith(".svg")]

datas += collect_data_files("jsonschema_specifications")  # referenced schemas of jsonschema

hidden = ["psutil"]  # imported inside a function (promote.editor_open)
hidden += ["zstandard"]  # imported by name (adapters.tiled, T13.14)
# soundfile is imported inside functions (audio_info, T13.17); libsndfile ships in the wheel as
# the package _soundfile_data, which nothing imports by name
hidden += ["soundfile", "_soundfile_data", "_cffi_backend"]
datas += collect_data_files("_soundfile_data")
binaries = collect_dynamic_libs("_soundfile_data")


def analysis(script):
    return Analysis(
        [os.path.join(SPECPATH, script)],
        pathex=[ROOT],
        binaries=binaries,
        datas=datas,
        hiddenimports=hidden,
        excludes=EXCLUDED_QT,
        noarchive=False,
    )


gui_a = analysis("entry_gui.py")
cli_a = analysis("entry_cli.py")
MERGE((gui_a, "entry_gui", "rpggen"), (cli_a, "entry_cli", "rpggen-cli"))

gui_pyz = PYZ(gui_a.pure)
cli_pyz = PYZ(cli_a.pure)

gui_exe = EXE(
    gui_pyz, gui_a.scripts, [], exclude_binaries=True, name="rpggen",
    console=False, version=VERSION_FILE, icon=ICON, upx=False,
)
cli_exe = EXE(
    cli_pyz, cli_a.scripts, [], exclude_binaries=True, name="rpggen-cli",
    console=True, version=VERSION_FILE, icon=ICON, upx=False,
)
coll = COLLECT(
    gui_exe, gui_a.binaries, gui_a.datas,
    cli_exe, cli_a.binaries, cli_a.datas,
    strip=False, upx=False, name="rpggen",
)
if IS_MAC:
    # The first executable of the COLLECT (the GUI) is the app's CFBundleExecutable; rpggen-cli
    # sits next to it in Contents/MacOS. Unsigned: notarization is a later step (docs/release.md).
    BUNDLE(
        coll,
        name="rpggen.app",
        icon=ICON,
        bundle_identifier="io.github.docdamage.rpggen",
        version=APP_VERSION,
        info_plist={
            "CFBundleName": "rpggen",
            "CFBundleDisplayName": "rpggen",
            "CFBundleExecutable": "rpggen",
            "CFBundleShortVersionString": APP_VERSION,
            "LSMinimumSystemVersion": "13.0",
            "NSHighResolutionCapable": True,
        },
    )
