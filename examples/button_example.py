"""Using batio to create a button in the terminal."""

import asyncio

from batio import get_platform_terminal
from batio.events import CursorPositionResponseEvent, Event, KeyEvent, MouseEvent, Point

NORMAL = (221, 228, 237), (42, 60, 160)
HOVER = (255, 240, 246), (50, 72, 192)
PRESS = (255, 240, 246), (196, 162, 25)


async def main():
    """Create a pressable button."""
    terminal = get_platform_terminal()
    button_origin = Point(0, 0)
    ctrl_c_pressed = False
    button_pressed = False

    def collides_button(point) -> bool:
        x, y = button_origin
        cx, cy = point
        return x <= cx < x + 8 and y <= cy < y + 3

    def draw_button(foreground, background):
        terminal.line_feed(2)
        terminal.cursor_previous_line(2)
        terminal.sgr_parameters(
            foreground_color=foreground, background_color=background
        )
        terminal.write("        \n Button \n        ")
        terminal.cursor_previous_line(2)
        terminal.reset_attributes()
        terminal.flush()

    def event_handler(events: list[Event]) -> None:
        nonlocal ctrl_c_pressed, button_pressed
        for event in events:
            if isinstance(event, KeyEvent) and event.key == "c" and event.ctrl:
                ctrl_c_pressed = True
            elif isinstance(event, MouseEvent):
                if button_pressed:
                    if event.event_type == "mouse_up":
                        button_pressed = False
                        draw_button(*HOVER if collides_button(event.pos) else NORMAL)
                elif event.event_type == "mouse_down" and collides_button(event.pos):
                    button_pressed = True
                    draw_button(*PRESS)
                else:
                    draw_button(*HOVER if collides_button(event.pos) else NORMAL)
            elif isinstance(event, CursorPositionResponseEvent):
                nonlocal button_origin
                button_origin = event.pos

    terminal.raw_mode()
    terminal.attach(event_handler)
    terminal.enable_mouse_support()
    terminal.hide_cursor()
    terminal.flush()

    draw_button(*NORMAL)
    terminal.request_cursor_position_report()

    while not ctrl_c_pressed:
        await asyncio.sleep(0)

    terminal.reset_attributes()
    terminal.erase_in_display()
    terminal.show_cursor()
    terminal.disable_mouse_support()
    terminal.flush()
    terminal.unattach()
    terminal.restore_console()


if __name__ == "__main__":
    asyncio.run(main())
