"""Example batio usage to print input events."""

import asyncio

from batio import get_platform_terminal
from batio.events import Event, KeyEvent


async def main():
    """Print terminal input events."""
    terminal = get_platform_terminal()
    ctrl_c_pressed = False

    def event_handler(events: list[Event]) -> None:
        nonlocal ctrl_c_pressed
        for event in events:
            if isinstance(event, KeyEvent) and event.key == "c" and event.ctrl:
                ctrl_c_pressed = True
            else:
                print(event)

    terminal.raw_mode()
    terminal.attach(event_handler)
    terminal.enable_mouse_support()
    terminal.enable_bracketed_paste()
    terminal.enable_reporting_focus()
    terminal.flush()

    while not ctrl_c_pressed:
        await asyncio.sleep(0)

    terminal.reset_attributes()
    terminal.disable_reporting_focus()
    terminal.disable_bracketed_paste()
    terminal.disable_mouse_support()
    terminal.flush()
    terminal.unattach()
    terminal.restore_console()


if __name__ == "__main__":
    asyncio.run(main())
