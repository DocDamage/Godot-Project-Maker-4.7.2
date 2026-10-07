# PyInstaller spec: one-folder build with two executables sharing one set of libraries.
#   rpggen.exe      windowed GUI (no console)
#   rpggen-cli.exe  console build for scripts and CI
# Build from the repository root:  python -m PyInstaller packaging/rpggen.spec --noconfirm
# Output:                          dist/rpggen/
import os

from PyInstaller.utils.hooks import collect_data_files

ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))
VERSION_FILE = os.path.join(SPECPATH, "version_info.txt")

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
datas += tree(os.path.join(ROOT, "docs"), "docs", skip_dirs={"spec", "dev"})
datas += [(os.path.join(ROOT, name), ".") for name in ("LICENSE", "THIRD_PARTY_NOTICES.md", "README.md")]
datas += [(os.path.join(ROOT, "rpggen", "schema", f), os.path.join("rpggen", "schema"))
          for f in os.listdir(os.path.join(ROOT, "rpggen", "schema")) if f.endswith(".json")]
datas += [
    (os.path.join(ROOT, "rpggen", "gui", name), os.path.join("rpggen", "gui"))
    for name in ("style.qss", "style_light.qss")
]
datas += collect_data_files("jsonschema_specifications")  # referenced schemas of jsonschema

hidden = []


def analysis(script):
    return Analysis(
        [os.path.join(SPECPATH, script)],
        pathex=[ROOT],
        binaries=[],
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
    console=False, version=VERSION_FILE, icon=os.path.join(ROOT, "packaging", "rpggen.ico"),
    upx=False,
)
cli_exe = EXE(
    cli_pyz, cli_a.scripts, [], exclude_binaries=True, name="rpggen-cli",
    console=True, version=VERSION_FILE, icon=os.path.join(ROOT, "packaging", "rpggen.ico"),
    upx=False,
)
COLLECT(
    gui_exe, gui_a.binaries, gui_a.datas,
    cli_exe, cli_a.binaries, cli_a.datas,
    strip=False, upx=False, name="rpggen",
)
