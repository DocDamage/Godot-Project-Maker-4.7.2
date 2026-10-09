"""Progress of a generation on the taskbar button (Windows) or the dock icon (macOS) (T13.10).

Windows: ``ITaskbarList3`` through ``ctypes`` (a COM object called by its vtable; no dependency).
macOS: the dock badge shows how many steps are left. Elsewhere, and whenever anything here
fails, nothing happens: this is a nicety, and it never raises.
"""

from __future__ import annotations

import ctypes
import logging
import sys
from typing import Any

log = logging.getLogger(__name__)

# ITaskbarList3: the slots of its vtable (IUnknown has 3, ITaskbarList 5, ITaskbarList2 1)
_RELEASE, _HR_INIT, _SET_VALUE, _SET_STATE = 2, 3, 9, 10
TBPF_NOPROGRESS, TBPF_NORMAL, TBPF_ERROR = 0, 2, 4
CLSID_TASKBAR_LIST = "{56FDF344-FD6D-11d0-958A-006097C9A090}"
IID_TASKBAR_LIST3 = "{EA1AFB91-9E28-4B86-90E9-9E9F8A5EEFAF}"
CLSCTX_INPROC_SERVER = 1


class _Guid(ctypes.Structure):
    _fields_ = [
        ("d1", ctypes.c_ulong),
        ("d2", ctypes.c_ushort),
        ("d3", ctypes.c_ushort),
        ("d4", ctypes.c_ubyte * 8),
    ]


def _guid(text: str) -> _Guid:
    out = _Guid()
    if ctypes.windll.ole32.CLSIDFromString(ctypes.c_wchar_p(text), ctypes.byref(out)) != 0:  # type: ignore[attr-defined]
        raise OSError(f"not a GUID: {text}")
    return out


# ``ctypes.HRESULT`` exists on Windows only (and only there in the type stubs); this class is
# never made anywhere else.
_HRESULT: Any = getattr(ctypes, "HRESULT", ctypes.c_long)


class _WindowsTaskbar:
    """One ``ITaskbarList3`` for the process, made on first use."""

    def __init__(self) -> None:
        ole32 = ctypes.windll.ole32  # type: ignore[attr-defined]
        ole32.CoInitialize(None)  # Qt has done it on the GUI thread; a second call is counted
        self._pointer = ctypes.c_void_p()
        clsid, iid = _guid(CLSID_TASKBAR_LIST), _guid(IID_TASKBAR_LIST3)
        result = ole32.CoCreateInstance(
            ctypes.byref(clsid),
            None,
            CLSCTX_INPROC_SERVER,
            ctypes.byref(iid),
            ctypes.byref(self._pointer),
        )
        if result != 0 or not self._pointer:
            raise OSError(f"CoCreateInstance(TaskbarList) failed: {result:#x}")
        self._call(_HR_INIT, _HRESULT)

    def _call(self, slot: int, restype: Any, *args: Any, argtypes: tuple[Any, ...] = ()) -> Any:
        vtable = ctypes.cast(self._pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))
        prototype = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)  # type: ignore[attr-defined]
        return prototype(vtable.contents[slot])(self._pointer, *args)

    def set_value(self, hwnd: int, done: int, total: int) -> None:
        self._call(
            _SET_VALUE,
            _HRESULT,
            ctypes.c_void_p(hwnd),
            ctypes.c_ulonglong(done),
            ctypes.c_ulonglong(total),
            argtypes=(ctypes.c_void_p, ctypes.c_ulonglong, ctypes.c_ulonglong),
        )

    def set_state(self, hwnd: int, state: int) -> None:
        self._call(
            _SET_STATE,
            _HRESULT,
            ctypes.c_void_p(hwnd),
            ctypes.c_int(state),
            argtypes=(ctypes.c_void_p, ctypes.c_int),
        )


_taskbar: _WindowsTaskbar | None = None
_broken = False  # the COM object could not be made once: do not try again in this run


def _windows() -> _WindowsTaskbar | None:
    global _taskbar, _broken
    if _taskbar is None and not _broken:
        try:
            _taskbar = _WindowsTaskbar()
        except Exception:  # noqa: BLE001 - any failure means "no taskbar progress", nothing more
            _broken = True
            log.debug("no taskbar progress on this system", exc_info=True)
    return _taskbar


def _hwnd(window: Any) -> int:
    return int(window.winId()) if window is not None else 0


def _badge(number: int) -> None:
    from PySide6.QtGui import QGuiApplication

    setter = getattr(QGuiApplication, "setBadgeNumber", None)
    app = QGuiApplication.instance()
    if setter is not None and app is not None:
        app.setBadgeNumber(max(0, number))  # type: ignore[attr-defined]


def set_progress(window: Any, done: int, total: int) -> bool:
    """Show ``done`` of ``total`` on the window's taskbar button (Windows) or the steps left on
    the dock icon (macOS). True when something was shown."""
    global _broken
    try:
        if sys.platform == "win32":
            taskbar = _windows()
            hwnd = _hwnd(window)
            if taskbar is None or not hwnd or total <= 0:
                return False
            taskbar.set_state(hwnd, TBPF_NORMAL)
            taskbar.set_value(hwnd, max(0, min(done, total)), total)
            return True
        if sys.platform == "darwin":
            _badge(total - done)
            return True
    except Exception:  # noqa: BLE001 - see the module's first lines
        _broken = True
        log.debug("taskbar progress failed", exc_info=True)
    return False


def clear(window: Any, failed: bool = False) -> bool:
    """Take the progress away again; ``failed`` leaves the button red (Windows) until the
    window is activated and ``clear`` is called without it."""
    global _broken
    try:
        if sys.platform == "win32":
            taskbar = _windows()
            hwnd = _hwnd(window)
            if taskbar is None or not hwnd:
                return False
            taskbar.set_state(hwnd, TBPF_ERROR if failed else TBPF_NOPROGRESS)
            return True
        if sys.platform == "darwin":
            _badge(0)
            return True
    except Exception:  # noqa: BLE001
        _broken = True
        log.debug("taskbar progress failed", exc_info=True)
    return False
