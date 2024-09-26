"""Platform specific VT100 terminals."""

import platform
import sys

from .vt100_terminal import Vt100Terminal

__all__ = ["get_platform_terminal"]

__version__ = "0.2.0"


def get_platform_terminal() -> Vt100Terminal:
    """
    Return a platform specific terminal.

    Raises
    ------
    RuntimeError
        If terminal isn't interactive or terminal doesn't support VT100 sequences.
    """
    if not sys.stdin.isatty():
        raise RuntimeError("Terminal is non-interactive.")

    if platform.system() == "Windows":
        from .windows_terminal import is_vt100_enabled

        if not is_vt100_enabled():
            raise RuntimeError("Terminal does not support VT100.")

        from .windows_terminal import WindowsTerminal

        return WindowsTerminal()

    else:
        from .linux_terminal import LinuxTerminal

        return LinuxTerminal()
