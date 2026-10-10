"""One-click fixes for common failures (T12.41).

A registry maps an issue code to the buttons its row offers. An action only changes the
``WizardState`` and navigates (to a page, to the help, to a folder); nothing runs until a person
clicks, and the generation itself is started by the Generate page when it is shown.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from rpggen.errors import Issue
from rpggen.gui.state import WizardState

EXPORT_HELP_ANCHOR = "1. Install"  # the section that says where export templates come from


@dataclass(frozen=True)
class Fix:
    action: str
    label: str


class Navigation(Protocol):
    """What an action may ask of the window."""

    def go_to_project(self) -> None: ...

    def generate_again(self) -> None: ...

    def show_help(self, anchor: str) -> None: ...

    def open_folder(self) -> None: ...

    def resolve_conflicts(self, file: str | None) -> None: ...

    def repair_world(self) -> None: ...

    def open_log(self, name: str) -> None: ...

    def show_asset(self, file: str) -> bool: ...

    def open_failed_folder(self) -> None: ...


_GODOT = (
    Fix("download_godot", "Download Godot 4.7.2"),
    Fix("choose_godot", "Choose Godot…"),
)

FIXES: dict[str, tuple[Fix, ...]] = {
    "ENV-001": _GODOT,
    "ENV-002": _GODOT,
    "ENV-009": (Fix("choose_output", "Choose another output folder"),),
    "ENV-010": (Fix("export_help", "How to install export templates"),),
    "ASSET-010": (Fix("use_placeholder", "Use a placeholder and generate again"),),
    "REGEN-006": (Fix("accept_upgrade", "Accept the runtime upgrade and generate again"),),
    "REGEN-001": (Fix("resolve_conflicts", "Resolve conflicts"),),
    # T13.24: a map that cannot be reached, a door that leads nowhere
    "VAL-027": (Fix("repair_world", "Repair the world…"),),
    "VAL-028": (Fix("repair_world", "Repair the world…"),),
}

# T15.21: fixes that depend on what an issue carries, not on its code, so that a fix never
# needs a code that does not bring the detail. ``detail["log"]`` is the failed phase's log
# file, ``detail["file"]`` a file Godot named.
OPEN_LOG = Fix("open_log", "Open the log")
SHOW_ASSET = Fix("show_asset", "Show this asset in the audit")
OPEN_FAILED_FOLDER = Fix("open_failed_folder", "Open failed folder")
DETAIL_FIXES: tuple[tuple[str, Fix], ...] = (("log", OPEN_LOG), ("file", SHOW_ASSET))

# the widget of the Project page that the action points at
FOCUS = {
    "download_godot": "downloadGodotButton",
    "choose_godot": "browseGodotButton",
    "choose_output": "browseTargetButton",
}


def fixes_for(code: str) -> tuple[Fix, ...]:
    """The buttons of an issue code; a code that is not registered has none."""
    return FIXES.get(code, ())


def fixes_for_issue(
    issue: Issue, *, names_asset: bool = False, has_failed_folder: bool = False
) -> tuple[Fix, ...]:
    """Every button of an issue: those of its code, then those of what it carries. *Show this
    asset* needs ``names_asset`` (the file is an asset of the catalog), *Open failed folder*
    a folder that was kept."""
    out = list(fixes_for(issue.code))
    for key, fix in DETAIL_FIXES:
        value = issue.detail.get(key)
        if not isinstance(value, str) or not value:
            continue
        if fix is SHOW_ASSET and not names_asset:
            continue
        out.append(fix)
    if issue.detail.get("log") and has_failed_folder:
        out.append(OPEN_FAILED_FOLDER)
    return tuple(out)


def apply(fix: Fix, issue: Issue, state: WizardState, nav: Navigation) -> bool:
    """Carry out ``fix`` for ``issue``: change ``state``, then navigate. False when it cannot be
    done (an issue without the detail the action needs)."""
    action = fix.action
    if action in FOCUS:
        state.project_focus = FOCUS[action]
        nav.go_to_project()
    elif action == "export_help":
        nav.show_help(EXPORT_HELP_ANCHOR)
    elif action == "use_placeholder":
        role = issue.detail.get("role")
        if not isinstance(role, str) or not role:
            return False
        state.placeholders.add(role)
        state.run_result = None
        nav.generate_again()
    elif action == "accept_upgrade":
        state.accept_runtime_upgrade = True
        state.run_result = None
        nav.generate_again()
    elif action == "resolve_conflicts":  # T12.58: the resolver, showing the issue's file
        file = issue.file or issue.detail.get("file")  # REGEN-001 names the file in ``file``
        nav.resolve_conflicts(file if isinstance(file, str) and file else None)
    elif action == "repair_world":  # T13.24: shows what it would do before it writes
        nav.repair_world()
    elif action == "open_log":
        name = issue.detail.get("log")
        if not isinstance(name, str) or not name:
            return False
        nav.open_log(name)
    elif action == "show_asset":
        file = issue.detail.get("file")
        return isinstance(file, str) and bool(file) and nav.show_asset(file)
    elif action == "open_failed_folder":
        nav.open_failed_folder()
    else:
        return False
    return True
