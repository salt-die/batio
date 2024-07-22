"""Terminal Events."""

from dataclasses import dataclass
from typing import Literal, NamedTuple

__all__ = [
    "Key",
    "Event",
    "ResizeEvent",
    "CursorPositionResponseEvent",
    "KeyEvent",
    "MouseEvent",
    "PasteEvent",
    "FocusEvent",
]

# fmt: off
type SpecialKey = Literal[
    "backspace", "delete", "down", "end", "enter", "escape", "f1", "f2", "f3", "f4",
    "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12", "f13", "f14", "f15", "f16",
    "f17", "f18", "f19", "f20", "f21", "f22", "f23", "f24", "home", "insert", "left",
    "page_down", "page_up", "right", "scroll_down", "scroll_up", "tab", "up",
]
"""A special keyboard key."""
type CharKey = Literal[
    " ", "!", '"', "#", "$", "%", "&", "'", "(", ")", "*", "+", ",", "-", ".", "/", "0",
    "1", "2", "3", "4", "5", "6", "7", "8", "9", ":", ";", "<", "=", ">", "?", "@", "A",
    "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R",
    "S", "T", "U", "V", "W", "X", "Y", "Z", "[", "\\", "]", "^", "_", "`", "a", "b",
    "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q", "r", "s",
    "t", "u", "v", "w", "x", "y", "z", "{", "|", "}", "~",
]
"""A printable character keyboard key."""
# fmt: on
type Key = SpecialKey | CharKey
"""A keyboard key."""
type MouseButton = Literal["left", "middle", "no_button", "right"]
"""A mouse button."""
type MouseEventType = Literal[
    "mouse_down", "mouse_move", "mouse_up", "scroll_down", "scroll_up"
]
"""A mouse event type."""


class Size(NamedTuple):
    """
    A rectangular area.

    Parameters
    ----------
    width : int
        The width of the area.
    height : int
        The height of the area.

    Attributes
    ----------
    width : int
        The width of the area.
    height : int
        The height of the area.
    """

    width: int
    height: int


class Point(NamedTuple):
    """
    A 2D point.

    Parameters
    ----------
    x : int
        The x-coordinate of the point.
    y : int
        The y-coordinate of the point.

    Attributes
    ----------
    x : int
        The x-coordinate of the point.
    y : int
        The y-coordinate of the point.
    """

    x: int
    y: int


class Event:
    """Base event."""


@dataclass
class UnknownEscapeSequence(Event):
    """
    Event generated from an unknown ansi escape sequence.

    Parameters
    ----------
    escape : str
        The unknown ansi escape sequence.

    Attributes
    ----------
    escape : str
        The unknown ansi escape sequence.
    """

    escape: str
    """The unknown ansi escape sequence."""


@dataclass
class ResizeEvent(Event):
    """
    A terminal resize event.

    Parameters
    ----------
    size : Size
        The new terminal size.

    Attributes
    ----------
    size : Size
        The new terminal size.
    """

    size: Size
    """The new terminal size."""


@dataclass
class CursorPositionResponseEvent(Event):
    """
    A cursor position response event.

    Parameters
    ----------
    pos : Point
        The reported cursor position.

    Attributes
    ----------
    pos : Point
        The reported cursor position.
    """

    pos: Point
    """The reported cursor position."""


@dataclass
class KeyEvent(Event):
    """
    A key event.

    Parameters
    ----------
    key : Key
        The pressed key.
    alt : bool, default: False
        Whether alt was pressed.
    ctrl : bool, default: False
        Whether ctrl was pressed.
    shift : bool, default: False
        Whether shift was pressed.

    Attributes
    ----------
    key : Key
        The pressed key.
    alt : bool
        Whether alt was pressed.
    ctrl : bool
        Whether ctrl was pressed.
    shift : bool
        Whether shift was pressed.
    meta : bool
        Alias for ``alt``.
    control : bool
        Alias for ``ctrl``.
    """

    key: Key
    """The pressed key."""
    alt: bool = False
    """Whether alt was pressed."""
    ctrl: bool = False
    """Whether ctrl was pressed."""
    shift: bool = False
    """Whether shift was pressed."""

    @property
    def meta(self) -> bool:
        """Alias for ``alt``."""
        return self.alt

    @meta.setter
    def meta(self, meta: bool):
        self.alt = meta

    @property
    def control(self) -> bool:
        """Alias for ``ctrl``."""
        return self.ctrl

    @control.setter
    def control(self, control: bool):
        self.ctrl = control


@dataclass
class MouseEvent(Event):
    """
    A mouse event.

    Parameters
    ----------
    pos : Point
        The mouse position.
    button : MouseButton
        The mouse button.
    event_type : MouseEventType
        The mouse event type.
    alt : bool
        Whether alt was pressed.
    ctrl : bool
        Whether ctrl was pressed.
    shift : bool
        Whether shift was pressed.
    dx : int
        The change in x-coordinate of the mouse position.
    dy : int
        The change in y-coordinate of the mouse position.
    nclicks : int, default: 0
        The number of consecutive ``"mouse_down"`` events with same button.

    Attributes
    ----------
    pos : Point
        The mouse position.
    button : MouseButton
        The mouse button.
    event_type : MouseEventType
        The mouse event type.
    alt : bool
        Whether alt was pressed.
    ctrl : bool
        Whether ctrl was pressed.
    shift : bool
        Whether shift was pressed.
    dx : int
        The change in x-coordinate of the mouse position.
    dy : int
        The change in y-coordinate of the mouse position.
    nclicks : int
        The number of consecutive ``"mouse_down"`` events with same button.
    meta : bool
        Alias for ``alt``.
    control : bool
        Alias for ``ctrl``.
    """

    pos: Point
    """The mouse position."""
    button: MouseButton
    """The mouse button."""
    event_type: MouseEventType
    """The mouse event type."""
    alt: bool
    """Whether alt was pressed."""
    ctrl: bool
    """Whether ctrl was pressed."""
    shift: bool
    """Whether shift was pressed."""
    dx: int
    """The change in x-coordinate of the mouse position."""
    dy: int
    """The change in y-coordinate of the mouse position."""
    nclicks: int = 0
    """The number of consecutive ``"mouse_down"`` events with same button."""

    @property
    def meta(self) -> bool:
        """Alias for ``alt``."""
        return self.alt

    @meta.setter
    def meta(self, meta: bool):
        self.alt = meta

    @property
    def control(self) -> bool:
        """Alias for ``ctrl``."""
        return self.ctrl

    @control.setter
    def control(self, control: bool):
        self.ctrl = control


@dataclass
class PasteEvent(Event):
    """
    A paste event.

    Parameters
    ----------
    paste : str
        The paste content.

    Attributes
    ----------
    paste : str
        The paste content.
    """

    paste: str
    """The paste content."""


@dataclass
class FocusEvent(Event):
    """
    A focus event.

    Parameters
    ----------
    focus : Literal["in", "out"]
        The type of focus; either ``"in"`` or ``"out"``.

    Attributes
    ----------
    focus : Literal["in", "out"]
        The type of focus; either ``"in"`` or ``"out"``.
    """

    focus: Literal["in", "out"]
    """The type of focus; either ``"in"`` or ``"out"``."""
