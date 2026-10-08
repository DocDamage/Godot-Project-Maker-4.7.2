"""What the command-line commands share (T12.28): exit codes, the ``--json`` document and Ctrl+C.

The exit codes (documented in the README and ``docs/user_guide.md``):

====  =====================================================================================
0     OK
1     generation failed (``BUILD``, ``VAL``, ``SMOKE``, ``REGEN``, ``TILE`` errors)
2     usage error (a missing or unknown argument, an unknown preset)
3     environment or input (``ENV``, ``ARCH``, ``CAT``, ``ASSET``, ``ADAPT`` errors)
4     cancelled with Ctrl+C (the work folder is discarded; nothing is delivered)
70    internal error (``BUILD-005``: report it, with a diagnostic bundle)
====  =====================================================================================

With ``--json`` the one document of the command goes to stdout and every human line to stderr.
"""

from __future__ import annotations

import contextlib
import json
import signal
import sys
import threading
from collections.abc import Callable, Iterable, Iterator
from typing import Any

from rpggen.errors import Issue, Severity

OK = 0
FAILED = 1
USAGE = 2
INPUT = 3
CANCELLED = 4
INTERNAL = 70

JSON_VERSION = 1

# The groups of codes that mean "what you gave rpggen is wrong", not "generation went wrong".
INPUT_GROUPS = frozenset({"ENV", "ARCH", "CAT", "ASSET", "ADAPT"})


def exit_code_for(issues: Iterable[Issue], *, cancelled: bool = False) -> int:
    """The exit code of a run that did not succeed (``OK`` is the caller's to return).

    A cancelled run is 4 and an unplanned exception (``BUILD-005``) is 70. Otherwise the first
    error decides: a problem with the environment or the input is 3, anything else is 1.
    """
    if cancelled:
        return CANCELLED
    errors = [i for i in issues if i.severity is Severity.ERROR]
    if any(i.code == "BUILD-005" for i in errors):
        return INTERNAL
    if errors and errors[0].code.split("-", 1)[0] in INPUT_GROUPS:
        return INPUT
    return FAILED


def issue_json(issue: Issue) -> dict[str, Any]:
    """An issue as the documents show it: ``file`` is always there, ``null`` when it is not one."""
    return {
        "code": issue.code,
        "severity": str(issue.severity),
        "message": issue.message,
        "fix": issue.fix,
        "file": issue.file,
    }


class Output:
    """The words of one command. Without ``--json`` everything goes to stdout, as it always did;
    with it the human lines go to stderr and :meth:`done` prints the document on stdout."""

    def __init__(self, command: str, as_json: bool = False) -> None:
        self.command = command
        self.as_json = as_json

    def say(self, text: str = "") -> None:
        print(text, file=sys.stderr if self.as_json else sys.stdout, flush=True)

    def issues(self, issues: Iterable[Issue]) -> None:
        for issue in issues:
            self.say(f"{issue.severity.value.upper():7} {issue.code}: {issue.message}")
            if issue.severity is Severity.ERROR:
                self.say(f"        fix: {issue.fix}")

    def done(self, code: int, **fields: Any) -> int:
        """Print the document (``--json`` only) and return ``code``. The envelope comes first:
        ``json_version``, ``command``, ``ok`` and ``exit_code``."""
        if self.as_json:
            document = {
                "json_version": JSON_VERSION,
                "command": self.command,
                "ok": code == OK,
                "exit_code": code,
                **fields,
            }
            sys.stdout.write(json.dumps(document, indent=2) + "\n")
            sys.stdout.flush()
        return code

    def usage(self, text: str) -> int:
        """A usage error: the words go to the human channel and, with ``--json``, into the
        document's ``error`` field."""
        self.say(f"rpggen {self.command}: {text}")
        return self.done(USAGE, error=text)


@contextlib.contextmanager
def interruptible() -> Iterator[Callable[[], bool]]:
    """Ctrl+C asks the running command to stop at its next check (``is_cancelled`` becomes true)
    instead of raising where it happens to be, so that the work folder can be discarded. A second
    Ctrl+C raises ``KeyboardInterrupt`` as usual. Outside the main thread nothing is installed."""
    asked = threading.Event()

    def handler(signum: int, frame: Any) -> None:
        if asked.is_set():
            signal.default_int_handler(signum, frame)  # raises KeyboardInterrupt
        asked.set()
        print("Stopping... (press Ctrl+C again to quit at once)", file=sys.stderr, flush=True)

    previous = None
    installed = False
    try:
        previous = signal.signal(signal.SIGINT, handler)
        installed = True
    except ValueError:  # not the main thread
        pass
    try:
        yield asked.is_set
    finally:
        if installed:
            signal.signal(signal.SIGINT, previous if previous is not None else signal.SIG_DFL)
