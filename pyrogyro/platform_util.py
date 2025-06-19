import ctypes
import platform

import sdl3

from pyrogyro.math import *

SYSTEM = platform.system()

match SYSTEM:
    case "Windows":
        import pydirectinput
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

        def set_console_title(title: str): # type: ignore
            kernel32.SetConsoleTitleW(title)

        def set_console_visibility(visibility: bool):
            hWnd = kernel32.GetConsoleWindow()
            user32.ShowWindow(hWnd, 1 if visibility else 0)

        def init_window_listener(on_focus_change): # type: ignore
            window_listener = WindowChangeEventListener(callback=on_focus_change)
            window_listener.listen_in_thread()
            return window_listener

        def get_os_mouse_speed():
            get_mouse_speed = 0x0070
            speed = ctypes.c_int()
            user32.SystemParametersInfoA(get_mouse_speed, 0, ctypes.byref(speed), 0)
            return float(speed.value)

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

        def get_os_mouse_speed():
            return 1.0
