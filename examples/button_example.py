"""Using batio to create a button in the terminal."""

import asyncio

from batio import get_platform_terminal
from batio.events import Event, KeyEvent, MouseEvent

NORMAL_COLOR_PAIR = 221, 228, 237, 42, 60, 160
HOVER_COLOR_PAIR = 255, 240, 246, 50, 72, 192
PRESS_COLOR_PAIR = 255, 240, 246, 196, 162, 25
COLOR_PAIR_ANSI = "\x1b[38;2;{};{};{};48;2;{};{};{}m"


async def main():
    """Create a pressable button."""
    ctrl_c_pressed = False
    terminal = get_platform_terminal()
    button_pressed = False

    def collides_button(point) -> bool:
        x, y = terminal.last_cursor_position_response
        cx, cy = point
        return x <= cx < x + 8 and y <= cy < y + 3

    def draw_button(color_pair):
        button_color = COLOR_PAIR_ANSI.format(*color_pair)
        terminal.write(button_color)
        terminal.write("        ")
        terminal.reset_attributes()
        terminal.write("\n")
        terminal.write(button_color)
        terminal.write(" button ")
        terminal.reset_attributes()
        terminal.write("\n")
        terminal.write(button_color)
        terminal.write("        ")
        terminal.write("\x1b[2F")  # Move to beginning of row two lines up.
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
                        draw_button(
                            HOVER_COLOR_PAIR
                            if collides_button(event.pos)
                            else NORMAL_COLOR_PAIR
                        )
                elif event.event_type == "mouse_down" and collides_button(event.pos):
                    button_pressed = True
                    draw_button(PRESS_COLOR_PAIR)
                else:
                    draw_button(
                        HOVER_COLOR_PAIR
                        if collides_button(event.pos)
                        else NORMAL_COLOR_PAIR
                    )

    terminal.raw_mode()
    terminal.attach(event_handler)
    terminal.enable_mouse_support()
    terminal.hide_cursor()
    terminal.flush()

    draw_button(NORMAL_COLOR_PAIR)
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
