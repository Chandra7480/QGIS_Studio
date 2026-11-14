"""Universal AI GIS Studio — Mouse and Keyboard Controller.

Sends low-level input via Win32 SendInput. Coordinates are SCREEN pixels.
All operations default to the authorized QGIS window; callers must verify
the target is within QGIS before acting.
"""

import logging
import ctypes
from typing import Tuple

import win32api
import win32con

from core.emergency_stop import is_emergency_stop_active

logger = logging.getLogger("uagis.mouse_keyboard")

# SendInput structures
ULONG_PTR = ctypes.c_ulonglong


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong), ("wParamL", ctypes.c_ushort),
                ("wParamH", ctypes.c_ushort)]


class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

    _anonymous_ = ("_i",)
    _fields_ = [("type", ctypes.c_ulong), ("_i", _INPUT)]


INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x00008000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800

KEYEVENTF_KEYUP = 0x0002


class MouseKeyboardController:
    """Controls the mouse and keyboard via Win32 SendInput."""

    def __init__(self):
        self._extra = ctypes.c_ulonglong(0)

    def _check_emergency_stop(self) -> bool:
        """Check if emergency stop is active. Returns True if blocked."""
        if is_emergency_stop_active():
            logger.warning("Mouse/Keyboard operation blocked: emergency stop active")
            return True
        return False

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _send_input(self, inputs: list[ctypes.Structure]) -> int:
        n = len(inputs)
        arr = (INPUT * n)(*inputs)
        return ctypes.windll.user32.SendInput(n, ctypes.byref(arr),
                                              ctypes.sizeof(INPUT))

    @staticmethod
    def _screen_to_absolute(x: int, y: int) -> Tuple[int, int]:
        """Convert screen coords to SendInput absolute coords (0..65535)."""
        sw = ctypes.windll.user32.GetSystemMetrics(0)
        sh = ctypes.windll.user32.GetSystemMetrics(1)
        ax = int(x * 65535 / sw) if sw else 0
        ay = int(y * 65535 / sh) if sh else 0
        return ax, ay

    # ------------------------------------------------------------------ #
    # Mouse
    # ------------------------------------------------------------------ #
    def move(self, x: int, y: int) -> None:
        """Move the cursor to absolute screen position (x, y)."""
        if self._check_emergency_stop():
            return
        ax, ay = self._screen_to_absolute(x, y)
        inp = INPUT(type=INPUT_MOUSE,
                    _i=INPUT._INPUT(mi=MOUSEINPUT(dx=ax, dy=ay,
                                                  dwFlags=MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE)))
        self._send_input([inp])
        logger.debug("Mouse moved to (%d, %d)", x, y)

    def click(self, x: int | None = None, y: int | None = None,
              button: str = "left", double: bool = False) -> None:
        """Click (or double-click) at (x, y), or current position if omitted."""
        if self._check_emergency_stop():
            return
        if x is not None and y is not None:
            self.move(x, y)
        down = MOUSEEVENTF_LEFTDOWN if button == "left" else (
            MOUSEEVENTF_RIGHTDOWN if button == "right" else MOUSEEVENTF_MIDDLEDOWN)
        up = MOUSEEVENTF_LEFTUP if button == "left" else (
            MOUSEEVENTF_RIGHTUP if button == "right" else MOUSEEVENTF_MIDDLEUP)
        for _ in range(2 if double else 1):
            self._send_input([INPUT(type=INPUT_MOUSE,
                                    _i=INPUT._INPUT(mi=MOUSEINPUT(dwFlags=down)))])
            self._send_input([INPUT(type=INPUT_MOUSE,
                                    _i=INPUT._INPUT(mi=MOUSEINPUT(dwFlags=up)))])

    def drag(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """Drag from (x1, y1) to (x2, y2) using left button."""
        if self._check_emergency_stop():
            return
        self.move(x1, y1)
        self._send_input([INPUT(type=INPUT_MOUSE,
                                _i=INPUT._INPUT(mi=MOUSEINPUT(dwFlags=MOUSEEVENTF_LEFTDOWN)))])
        self.move(x2, y2)
        self._send_input([INPUT(type=INPUT_MOUSE,
                                _i=INPUT._INPUT(mi=MOUSEINPUT(dwFlags=MOUSEEVENTF_LEFTUP)))])

    def scroll(self, delta: int, x: int | None = None, y: int | None = None) -> None:
        """Scroll the wheel (delta positive=up, negative=down) at (x, y) or current."""
        if self._check_emergency_stop():
            return
        if x is not None and y is not None:
            self.move(x, y)
        inp = INPUT(type=INPUT_MOUSE,
                    _i=INPUT._INPUT(mi=MOUSEINPUT(mouseData=delta,
                                                  dwFlags=MOUSEEVENTF_WHEEL)))
        self._send_input([inp])

    # ------------------------------------------------------------------ #
    # Keyboard
    # ------------------------------------------------------------------ #
    def type_text(self, text: str) -> None:
        """Type text character by character."""
        if self._check_emergency_stop():
            return
        for ch in text:
            vk = win32api.VkKeyScanW(ch)
            scan = ctypes.c_ushort(0)  # use scan 0 with unicode flag handled below
            # Send key down
            inp_down = INPUT(type=INPUT_KEYBOARD,
                             _i=INPUT._INPUT(ki=KEYBDINPUT(wVk=vk & 0xFF,
                                                           dwFlags=0)))
            self._send_input([inp_down])
            inp_up = INPUT(type=INPUT_KEYBOARD,
                           _i=INPUT._INPUT(ki=KEYBDINPUT(wVk=vk & 0xFF,
                                                         dwFlags=KEYEVENTF_KEYUP)))
            self._send_input([inp_up])

    def hotkey(self, *keys: str) -> None:
        """Press a keyboard shortcut, e.g. hotkey('ctrl','s')."""
        if self._check_emergency_stop():
            return
        vks = [win32api.VkKeyScanW(k.upper()) & 0xFF for k in keys]
        # Press all down
        for vk in vks:
            self._send_input([INPUT(type=INPUT_KEYBOARD,
                                    _i=INPUT._INPUT(ki=KEYBDINPUT(wVk=vk,
                                                                  dwFlags=0)))])
        # Release all up (reverse order)
        for vk in reversed(vks):
            self._send_input([INPUT(type=INPUT_KEYBOARD,
                                    _i=INPUT._INPUT(ki=KEYBDINPUT(wVk=vk,
                                                                  dwFlags=KEYEVENTF_KEYUP)))])

    def press(self, key: str) -> None:
        """Press and release a single key."""
        if self._check_emergency_stop():
            return
        vk = win32api.VkKeyScanW(key) & 0xFF
        self._send_input([INPUT(type=INPUT_KEYBOARD,
                                _i=INPUT._INPUT(ki=KEYBDINPUT(wVk=vk, dwFlags=0)))])
        self._send_input([INPUT(type=INPUT_KEYBOARD,
                                _i=INPUT._INPUT(ki=KEYBDINPUT(wVk=vk,
                                                              dwFlags=KEYEVENTF_KEYUP)))])

    def get_position(self) -> Tuple[int, int]:
        """Return current cursor screen position (x, y)."""
        pt = ctypes.wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y
