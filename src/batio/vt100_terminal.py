"""Base for VT100 terminals."""

import asyncio
import os
import re
import sys
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Callable
from enum import Enum, auto
from io import StringIO
from time import perf_counter
from typing import Final, Literal

from .ansi_escapes import ANSI_ESCAPES
from .events import (
    ColorReportEvent,
    CursorPositionResponseEvent,
    DeviceAttributesReportEvent,
    Event,
    FocusEvent,
    KeyEvent,
    MouseButton,
    MouseEvent,
    MouseEventType,
    PasteEvent,
    PixelGeometryReportEvent,
    Point,
    Size,
    UnknownEscapeSequence,
)

CPR_RE: Final[re.Pattern[str]] = re.compile(r"\x1b\[(\d+);(\d+)R")
COLOR_RE: Final[re.Pattern[str]] = re.compile(
    r"\x1b\]1([10]);rgb:([0-9a-f]{4})/([0-9a-f]{4})/([0-9a-f]{4})\x1b\\"
)
DEVICE_ATTRIBUTES_RE: Final[re.Pattern[str]] = re.compile(r"\x1b\[\?[0-9;]+c")
PIXEL_GEOMETRY_RE: Final[re.Pattern[str]] = re.compile(r"\x1b\[([6|4]);(\d+);(\d+)t")
MOUSE_SGR_RE: Final[re.Pattern[str]] = re.compile(r"\x1b\[<(\d+);(\d+);(\d+)(m|M)")
PARAMS_RE: Final[re.Pattern[str]] = re.compile(r"[0-9;]")
BRACKETED_PASTE_START: Final[str] = "\x1b[200~"
BRACKETED_PASTE_END: Final[str] = "\x1b[201~"
FOCUS_IN: Final[str] = "\x1b[I"
FOCUS_OUT: Final[str] = "\x1b[O"
ESCAPE_TIMEOUT: Final[float] = 0.05
"""Time in seconds before escape buffer is reset."""
DRS_REQUEST_TIMEOUT: Final[float] = 0.1
"""
Time in seconds for the input parser to expect a response to a device status report
request.
"""


class ParserState(Enum):
    """State of VT100 input parser."""

    GROUND = auto()
    """Initial state."""
    ESCAPE = auto()
    """Start of an escape sequence."""
    CSI = auto()
    """Start of a control sequence."""
    OSC = auto()
    """Start of an operating system command sequence."""
    PARAMS = auto()
    """Collecting parameters of a control sequence."""
    PASTE = auto()
    """Collecting paste data."""
    EXECUTE_NEXT = auto()
    """Execute escape buffer after receiving next character."""


class Vt100Terminal(ABC):
    """
    Base for VT100 terminals.

    ``raw_mode()`` should be called before calling any other methods.
    ``restore_console()`` will return the console to its original mode if called after
    ``raw_mode()``.

    Once ``attach(event_handler)`` is called then whenever stdin has data, it will be
    read and input events will be generated and passed to ``event_handler``.  Call
    ``unattach()`` to stop listening to stdin.

    Attributes
    ----------
    in_alternate_screen : bool
        Whether the alternate screen buffer is enabled.

    Methods
    -------
    process_stdin()
        Read from stdin and feed data into input parser to generate events.
    raw_mode()
        Set terminal to raw mode.
    restore_console()
        Restore console to its original mode.
    attach(event_handler)
        Start generating events from stdin.
    unattach()
        Stop generating events from stdin.
    events()
        Return a list of input events and reset the event buffer.
    get_size()
        Get terminal size.
    write(data)
        Write ``data`` to output buffer.
    flush()
        Write buffer to output stream and flush.
    set_title(title)
        Set terminal title.
    enter_alternate_screen()
        Enter alternate screen buffer.
    exit_alternate_screen()
        Exit alternate screen buffer.
    enable_mouse_support()
        Enable mouse support in terminal.
    disable_mouse_support()
        Disable mouse support in terminal.
    enable_bracketed_paste()
        Enable bracketed paste in terminal.
    disable_bracketed_paste()
        Disable bracketed paste in terminal.
    enable_reporting_focus()
        Enable reporting terminal focus.
    disable_reporting_focus()
        Disable reporting terminal focus.
    show_cursor()
        Show cursor in terminal.
    hide_cursor()
        Hide cursor in terminal.
    request_cursor_position_report()
        Report current cursor position.
    request_foreground_color()
        Report terminal foreground color.
    request_background_color()
        Report terminal background color.
    request_device_attributes()
        Report device attributes.
    request_cell_geometry()
        Report pixel geometry per cell.
    request_terminal_geometry()
        Report pixel geometry of terminal.
    expect_dsr()
        Return whether a device status report is expected.
    line_feed(n)
        Move to next line, scrolling up if at bottom of screen.
    cursor_up(n)
        Move cursor up ``n`` rows.
    cursor_down(n)
        Move cursor down ``n`` rows.
    cursor_forward(n)
        Move cursor right ``n`` columns.
    cursor_back(n)
        Move cursor left ``n`` columns.
    cursor_next_line(n)
        Move cursor to beginning of the line ``n`` rows down.
    cursor_previous_line(n)
        Move cursor to beginning of the line ``n`` rows up.
    cursor_horizontal_absolute(n)
        Move the cursor to column ``n``.
    cursor_position(pos)
        Move cursor to ``pos``.
    erase_in_display(n)
        Clear part of the screen.
    erase_in_line(n)
        Erase part of the current line.
    scroll_up(n)
        Scroll up ``n`` rows.
    scroll_down(n)
        Scroll down ``n`` rows.
    save_current_cursor_position()
        Save the current cursor positon.
    restore_saved_cursor_position()
        Restore the saved cursor positon.
    reset_attributes()
        Reset character attributes.
    sgr_parameters(bold, faint, italic, ...)
        Select graphic rendition parameters.
    """

    def __init__(self):
        self.in_alternate_screen: bool = False
        """Whether the alternate screen buffer is enabled."""

        self._escape_buffer: StringIO | None = None
        """Escape sequence buffer."""
        self._paste_buffer: StringIO | None = None
        """Paste buffer."""
        self._event_buffer: list[Event] = []
        """Events generated during input parsing."""
        self._out_buffer: list[str] = []
        """
        Output buffer.

        Escapes for stdout are collected here before ``flush()`` is called.
        """
        self._state: ParserState = ParserState.GROUND
        """State of VT100 input parser."""
        self._reset_timer_handle: asyncio.TimerHandle | None = None
        """Timeout handle for executing escape buffer."""
        self._dsr_request_times: deque[float] = deque()
        """Device status report request times."""
        self._last_x: int = 0
        """Last mouse x-coordinate."""
        self._last_y: int = 0
        """Last mouse y-coordinate."""
        self._event_handler: Callable[[list[Event]], None] | None = None
        """Event handler set with ``attach()`` or unset with ``unattach()``."""

    @abstractmethod
    def process_stdin(self) -> None:
        """Read from stdin and feed data into input parser to generate events."""

    @abstractmethod
    def raw_mode(self) -> None:
        """Set terminal to raw mode."""

    @abstractmethod
    def restore_console(self) -> None:
        """Restore console to its original mode."""

    @abstractmethod
    def attach(self, event_handler: Callable[[list[Event]], None]) -> None:
        """
        Start generating events from stdin.

        Parameters
        ----------
        event_handler : Callable[[list[Event]], None]
            Callable that handles input events.
        """

    @abstractmethod
    def unattach(self) -> None:
        """Stop generating events from stdin."""

    def events(self) -> list[Event]:
        """Return a list of input events and reset the event buffer."""
        events = self._event_buffer
        self._event_buffer = []
        return events

    def get_size(self) -> Size:
        """Get terminal size."""
        cols, rows = os.get_terminal_size()
        return Size(cols, rows)

    def _feed(self, data: str) -> None:
        """Generate events from terminal input data."""
        if self._reset_timer_handle is not None:
            self._reset_timer_handle.cancel()
            self._reset_timer_handle = None

        for char in data:
            self._feed1(char)

        if self._state is ParserState.GROUND:
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            self._reset_timer_handle = loop.call_later(
                ESCAPE_TIMEOUT, self._reset_escape
            )

    def _feed1(self, char: str) -> None:
        """Feed a single character from terminal input into the parser."""
        if self._state is ParserState.OSC:
            self._escape_buffer.write(char)
            if char == "\\" and self._escape_buffer.getvalue().endswith("\x1b\\"):
                self._execute()
        elif self._state is not ParserState.PASTE and char == "\x1b":
            # Start a new escape (possibly canceling previous escape).
            self._escape_buffer = StringIO()
            self._escape_buffer.write(char)
            self._state = ParserState.ESCAPE
        elif self._state is ParserState.EXECUTE_NEXT:
            self._escape_buffer.write(char)
            self._execute()
        elif self._state is ParserState.PASTE:
            self._paste_buffer.write(char)
            if char == "~":
                paste = self._paste_buffer.getvalue()
                if paste.endswith(BRACKETED_PASTE_END):
                    self._event_buffer.append(PasteEvent(paste[:-6]))
                    self._paste_buffer = None
                    self._state = ParserState.GROUND
        elif self._state is ParserState.GROUND:
            if ord(char) < 0x20 or char == "\x7f" or char == "\x9b":
                self._escape_buffer = StringIO()
                self._escape_buffer.write(char)
                self._execute()
            else:
                self._event_buffer.append(KeyEvent(char))
        elif self._state is ParserState.ESCAPE:
            self._escape_buffer.write(char)
            if char == "[":
                self._state = ParserState.CSI
            elif char == "O":
                self._state = ParserState.EXECUTE_NEXT
            elif char == "]":
                self._state = ParserState.OSC
            else:
                self._execute()
        elif self._state is ParserState.CSI:
            self._escape_buffer.write(char)
            if char == "[":
                self._state = ParserState.EXECUTE_NEXT
            elif char == "<":
                self._state = ParserState.PARAMS
            elif PARAMS_RE.fullmatch(char) is None:
                self._execute()
            else:
                self._state = ParserState.PARAMS
        elif self._state is ParserState.PARAMS:
            self._escape_buffer.write(char)
            if PARAMS_RE.fullmatch(char) is None:
                self._execute()

    def _execute(self) -> None:
        """Produce an event from the escape buffer."""
        self._state = ParserState.GROUND
        escape = self._escape_buffer.getvalue()
        self._escape_buffer = None

        while len(self._dsr_request_times) > 0 and (
            perf_counter() - self._dsr_request_times[0] >= DRS_REQUEST_TIMEOUT
        ):
            self._dsr_request_times.popleft()

        if len(self._dsr_request_times) > 0 and self._execute_dsr_request(escape):
            return

        if escape == BRACKETED_PASTE_START:
            self._state = ParserState.PASTE
            self._paste_buffer = StringIO(newline=None)
        elif escape == FOCUS_IN:
            self._event_buffer.append(FocusEvent("in"))
        elif escape == FOCUS_OUT:
            self._event_buffer.append(FocusEvent("out"))
        elif sgr_match := MOUSE_SGR_RE.fullmatch(escape):
            info = int(sgr_match[1])
            x = int(sgr_match[2]) - 1
            y = int(sgr_match[3]) - 1
            dx = x - self._last_x
            dy = y - self._last_y
            self._last_x = x
            self._last_y = y
            state = sgr_match[4]
            button: MouseButton = ["left", "middle", "right", "no_button"][info % 4]
            event_type: MouseEventType

            if info & 64:
                event_type = "scroll_down" if info & 1 else "scroll_up"
                button = "no_button"
            elif info & 32:
                event_type = "mouse_move"
            elif state == "m":
                event_type = "mouse_up"
            else:
                event_type = "mouse_move" if button == "no_button" else "mouse_down"

            shift = bool(info & 4)
            alt = bool(info & 8)
            ctrl = bool(info & 16)

            self._event_buffer.append(
                MouseEvent(Point(x, y), button, event_type, alt, ctrl, shift, dx, dy)
            )
        elif escape in ANSI_ESCAPES:
            self._event_buffer.append(KeyEvent(*ANSI_ESCAPES[escape]))
        elif len(escape) == 2 and 32 <= ord(escape[1]) <= 126:
            self._event_buffer.append(KeyEvent(escape[1], alt=True))
        else:
            self._event_buffer.append(UnknownEscapeSequence(escape))

    def _execute_dsr_request(self, escape: str) -> bool:
        event: Event
        if cpr_match := CPR_RE.fullmatch(escape):
            y, x = cpr_match.groups()
            event = CursorPositionResponseEvent(Point(int(y) - 1, int(x) - 1))
        elif color_match := COLOR_RE.fullmatch(escape):
            kind, r, g, b = color_match.groups()
            event = ColorReportEvent(
                kind="fg" if kind == "0" else "bg",
                color=(int(r[:2], 16), int(g[:2], 16), int(b[:2], 16)),
            )
        elif device_attributes_match := DEVICE_ATTRIBUTES_RE.fullmatch(escape):
            device_attributes = device_attributes_match.group()[3:-1].split(";")
            event = DeviceAttributesReportEvent(frozenset(map(int, device_attributes)))
        elif pixel_geometry_match := PIXEL_GEOMETRY_RE.fullmatch(escape):
            kind, height, width = pixel_geometry_match.groups()
            event = PixelGeometryReportEvent(
                kind="cell" if kind == "6" else "terminal",
                geometry=Size(int(height), int(width)),
            )
        else:
            return False

        self._dsr_request_times.popleft()
        self._event_buffer.append(event)
        return True

    def _reset_escape(self) -> None:
        """Execute escape buffer after a timeout period."""
        if self._state is ParserState.PASTE:
            paste = self._paste_buffer.getvalue()
            self._paste_buffer = None
            self._state = ParserState.GROUND

            # Timed out during a paste. Check if there's a partial escape to remove
            # (maybe BRACKETED_PASTE_END was cutoff).
            partial_escape_index = paste.find("\x1b")
            if partial_escape_index != -1:
                ending = paste[partial_escape_index:]
                if BRACKETED_PASTE_END[: len(ending)] == ending:
                    paste = paste[:partial_escape_index]
            self._event_buffer.append(PasteEvent(paste))
            self._paste_buffer = None
        else:
            self._execute()

        if self._event_handler is not None:
            self._event_handler(self.events())

    def write(self, data: str) -> None:
        """
        Write ``data`` to output buffer.

        Parameters
        ----------
        data : str
            Data to write to output buffer.
        """
        self._out_buffer.append(data)

    def flush(self) -> None:
        """Write output buffer to stdout and flush."""
        if len(self._out_buffer) == 0:
            return

        data = "".join(self._out_buffer).encode(errors="replace")
        self._out_buffer.clear()
        sys.stdout.buffer.write(data)
        sys.stdout.flush()

    def set_title(self, title: str) -> None:
        """
        Set terminal title.

        Parameters
        ----------
        title : str
            The new terminal title.
        """
        self._out_buffer.append(f"\x1b]2;{title}\x07")

    def enter_alternate_screen(self) -> None:
        """Enter alternate screen buffer."""
        self._out_buffer.append("\x1b[?1049h\x1b[H")
        self.in_alternate_screen = True

    def exit_alternate_screen(self) -> None:
        """Exit alternate screen buffer."""
        self._out_buffer.append("\x1b[?1049l")
        self.in_alternate_screen = False

    def enable_mouse_support(self) -> None:
        """Enable mouse support in terminal."""
        self._out_buffer.append(
            "\x1b[?1000h"  # SET_VT200_MOUSE
            "\x1b[?1003h"  # SET_ANY_EVENT_MOUSE
            "\x1b[?1006h"  # SET_SGR_EXT_MODE_MOUSE
            "\x1b[?1015h"  # SET_URXVT_EXT_MODE_MOUSE
        )

    def disable_mouse_support(self) -> None:
        """Disable mouse support in terminal."""
        self._out_buffer.append(
            "\x1b[?1000l"  # SET_VT200_MOUSE
            "\x1b[?1003l"  # SET_ANY_EVENT_MOUSE
            "\x1b[?1015l"  # SET_SGR_EXT_MODE_MOUSE
            "\x1b[?1006l"  # SET_URXVT_EXT_MODE_MOUSE
        )

    def enable_bracketed_paste(self) -> None:
        """Enable bracketed paste in terminal."""
        self._out_buffer.append("\x1b[?2004h")

    def disable_bracketed_paste(self) -> None:
        """Disable bracketed paste in terminal."""
        self._out_buffer.append("\x1b[?2004l")

    def enable_reporting_focus(self) -> None:
        """Enable reporting terminal focus."""
        self._out_buffer.append("\x1b[?1004h")

    def disable_reporting_focus(self) -> None:
        """Disable reporting terminal focus."""
        self._out_buffer.append("\x1b[?1004l")

    def show_cursor(self) -> None:
        """Show cursor in terminal."""
        self._out_buffer.append("\x1b[?25h")

    def hide_cursor(self) -> None:
        """Hide cursor in terminal."""
        self._out_buffer.append("\x1b[?25l")

    def _request_dsr(self, request: str):
        """Send a DSR request."""
        self._dsr_request_times.append(perf_counter())
        self._out_buffer.append(request)
        self.flush()

    def request_cursor_position_report(self) -> None:
        """Report current cursor position."""
        self._request_dsr("\x1b[6n")

    def request_foreground_color(self) -> None:
        """Report terminal foreground color."""
        self._request_dsr("\x1b]10;?\x1b\\")

    def request_background_color(self) -> None:
        """Report terminal background color."""
        self._request_dsr("\x1b]11;?\x1b\\")

    def request_device_attributes(self) -> None:
        """Report device attributes."""
        self._request_dsr("\x1b[c")

    def request_cell_geometry(self) -> None:
        """Report pixel geometry per cell."""
        self._request_dsr("\x1b[16t")

    def request_terminal_geometry(self) -> None:
        """Report pixel geometry of terminal."""
        self._request_dsr("\x1b[14t")

    def expect_dsr(self) -> bool:
        """Return whether a device status report is expected."""
        return len(self._dsr_request_times) > 0

    def line_feed(self, n: int = 1) -> None:
        """
        Move to next line, scrolling up if at bottom of screen.

        Parameters
        ----------
        n : int, default: 1
            Number of times to repeat instruction.
        """
        self._out_buffer.append("\x0a" * n)

    def cursor_up(self, n: int = 1) -> None:
        """
        Move cursor up ``n`` rows.

        Parameters
        ----------
        n : int, default: 1
            Number of rows to move cursor.
        """
        self._out_buffer.append(f"\x1b[{n}A")

    def cursor_down(self, n: int = 1) -> None:
        """
        Move cursor down ``n`` rows.

        Parameters
        ----------
        n : int, default: 1
            Number of rows to move cursor.
        """
        self._out_buffer.append(f"\x1b[{n}B")

    def cursor_forward(self, n: int = 1) -> None:
        """
        Move cursor right ``n`` columns.

        Parameters
        ----------
        n : int, default: 1
            Number of columns to move cursor.
        """
        self._out_buffer.append(f"\x1b[{n}C")

    def cursor_back(self, n: int = 1) -> None:
        """
        Move cursor left ``n`` columns.

        Parameters
        ----------
        n : int, default: 1
            Number of columns to move cursor.
        """
        self._out_buffer.append(f"\x1b[{n}D")

    def cursor_next_line(self, n: int = 1) -> None:
        """
        Move cursor to beginning of the line ``n`` rows down.

        Parameters
        ----------
        n : int, default: 1
            Number of rows to move cursor.
        """
        self._out_buffer.append(f"\x1b[{n}E")

    def cursor_previous_line(self, n: int = 1) -> None:
        """
        Move cursor to beginning of the line ``n`` rows up.

        Parameters
        ----------
        n : int, default: 1
            Number of rows to move cursor.
        """
        self._out_buffer.append(f"\x1b[{n}F")

    def cursor_horizontal_absolute(self, n: int = 1) -> None:
        """
        Move the cursor to column ``n``.

        Parameters
        ----------
        n : int, default: 1
            Cursor's new column.
        """
        self._out_buffer.append(f"\x1b[{n}G")

    def cursor_position(self, pos: Point) -> None:
        """
        Move cursor to ``pos``.

        Parameters
        ----------
        pos : Point | None, default: None
            Cursor's new position.
        """
        x, y = pos
        self._out_buffer.append(f"\x1b[{y + 1};{x + 1}H")

    def erase_in_display(self, n: Literal[0, 1, 2, 3] = 0) -> None:
        """
        Clear part of the screen.

        Parameters
        ----------
        n : int, default: 0
            Determines which part of the screen to clear. If n is ``0``, clear from
            cursor to end of the screen. If n is ``1``, clear from cursor to beginning
            of the screen. If n is ``2``, clear entire screen. If n is ``3``, clear
            entire screen and delete all lines in scrollback buffer.
        """
        self._out_buffer.append(f"\x1b[{n}J")

    def erase_in_line(self, n: Literal[0, 1, 2] = 0) -> None:
        """
        Erase part of the current line.

        Parameters
        ----------
        n : int, default: 0
            Determines which part of the line to clear. If n is ``0``, clear from cursor
            to the end of line. If n is ``1``, clear from cursor to beginning of the
            line. If n is ``2``, clear entire line.
        """
        self._out_buffer.append(f"\x1b[{n}K")

    def scroll_up(self, n: int = 1) -> None:
        """
        Scroll up ``n`` rows.

        Parameters
        ----------
        n : int, default: 1
            Number of rows to move cursor.
        """
        self._out_buffer.append(f"\x1b[{n}S")

    def scroll_down(self, n: int = 1) -> None:
        """
        Scroll down ``n`` rows.

        Parameters
        ----------
        n : int, default: 1
            Number of rows to move cursor.
        """
        self._out_buffer.append(f"\x1b[{n}T")

    def save_current_cursor_position(self) -> None:
        """Save the current cursor positon."""
        self._out_buffer.append("\x1b7")

    def restore_saved_cursor_position(self) -> None:
        """Restore the saved cursor positon."""
        self._out_buffer.append("\x1b8")

    def reset_attributes(self) -> None:
        """Reset character attributes."""
        self._out_buffer.append("\x1b[0m")

    def sgr_parameters(
        self,
        bold: bool = False,
        faint: bool = False,
        italic: bool = False,
        underline: bool = False,
        blink: bool = False,
        reverse: bool = False,
        strikethrough: bool = False,
        overline: bool = False,
        foreground_color: tuple[int, int, int] | None = None,
        background_color: tuple[int, int, int] | None = None,
    ) -> None:
        """
        Select graphic rendition parameters.

        Parameters
        ----------
        bold : bool, default: False
            Whether bold is set.
        faint : bool, default: False
            Whether faint is set.
        italic : bool, default: False
            Whether italic is set.
        underline : bool, default: False
            Whether underline is set.
        blink : bool, default: False
            Whether blink is set.
        reverse : bool, default: False
            Whether reverse is set.
        strikethrough : bool, default: False
            Whether strikethrough is set.
        overline : bool, default: False
            Whether overline is set.
        foreground_color : tuple[int, int, int] | None, default: None
            Set foreground color if given.
        background_color : tuple[int, int, int] | None, default: None
            Set background color if given.
        """
        params = "1", "2", "3", "4", "5", "7", "9", "53"
        styles = bold, faint, italic, underline, blink, reverse, strikethrough, overline
        args = ";".join(param for param, style in zip(params, styles) if style)
        self._out_buffer.append(f"\x1b[{args}m")
        if foreground_color:
            self._out_buffer.append("\x1b[38;2;{};{};{}m".format(*foreground_color))
        if background_color:
            self._out_buffer.append("\x1b[48;2;{};{};{}m".format(*background_color))
