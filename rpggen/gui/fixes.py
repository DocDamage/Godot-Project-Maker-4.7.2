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
}

# the widget of the Project page that the action points at
FOCUS = {
    "download_godot": "downloadGodotButton",
    "choose_godot": "browseGodotButton",
    "choose_output": "browseTargetButton",
}


def fixes_for(code: str) -> tuple[Fix, ...]:
    """The buttons of an issue code; a code that is not registered has none."""
    return FIXES.get(code, ())


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
    else:
        return False
    return True
