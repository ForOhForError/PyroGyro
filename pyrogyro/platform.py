import ctypes
import platform

from pyrogyro.math import *

SYSTEM = platform.system()

match SYSTEM:
    case "Windows":
        import pydirectinput
        from infi.systray import SysTrayIcon
        from pydirectinput import keyDown, keyUp, mouseDown, mouseUp
        from pydirectinput import moveRel as _movemouse

        from pyrogyro.monitor_focus import WindowChangeEventListener

        pydirectinput.FAILSAFE = False
        pydirectinput.PAUSE = 0

        kernel32 = ctypes.WinDLL("kernel32")
        user32 = ctypes.WinDLL("user32")

        def move_mouse(
            x: float,
            y: float,
            extra_x: float = 0.0,
            extra_y: float = 0.0,
        ):
            vel_x = x + extra_x
            vel_y = y + extra_y
            _movemouse(int(vel_x), int(vel_y), relative=True)
            leftover_x = vel_x % sign(vel_x)
            leftover_y = vel_y % sign(vel_y)
            return leftover_x, leftover_y

        def set_console_title(title: str):
            kernel32.SetConsoleTitleW(title)

        def set_console_visibility(visibility: bool):
            hWnd = kernel32.GetConsoleWindow()
            user32.ShowWindow(hWnd, 1 if visibility else 0)

        def init_systray(
            icon_location, tray_title, menu_options, on_quit=None, **kwargs
        ):
            systray = SysTrayIcon(
                icon_location,
                tray_title,
                menu_options,
                on_quit=on_quit,
            )
            systray.start()
            return systray

        def init_window_listener(on_focus_change):
            window_listener = WindowChangeEventListener(callback=on_focus_change)
            window_listener.listen_in_thread()
            return window_listener

    case _:
        import pyautogui
        from pyautogui import keyDown, keyUp, mouseDown, mouseUp
        from pyautogui import moveRel as _movemouse

        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0

        def move_mouse(
            x: float,
            y: float,
            extra_x: float = 0.0,
            extra_y: float = 0.0,
        ):
            vel_x = x + extra_x
            vel_y = y + extra_y
            _movemouse(int(vel_x), int(vel_y))
            leftover_x = vel_x % sign(vel_x)
            leftover_y = vel_y % sign(vel_y)
            return leftover_x, leftover_y

        def set_console_title(title):
            pass

        def set_console_visibility(visibility: bool):
            pass

        def init_systray(
            icon_location, tray_title, menu_options, on_quit=None, **kwargs
        ):
            return None

        def init_window_listener(on_focus_change):
            return None
