import ctypes
import platform

import sdl3
import logging

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
        
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020
        WS_EX_TOPMOST = 0x00000008
        WS_EX_COMPOSITED = 0x02000000
        
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_NOACTIVATE = 0x0010
        
        LWA_ALPHA = 0x00000002

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

        def set_console_title(title: str):  # type: ignore
            kernel32.SetConsoleTitleW(title)

        def set_console_visibility(visibility: bool):
            hWnd = kernel32.GetConsoleWindow()
            user32.ShowWindow(hWnd, 1 if visibility else 0)

        def init_window_listener(on_focus_change):  # type: ignore
            window_listener = WindowChangeEventListener(callback=on_focus_change)
            window_listener.listen_in_thread()
            return window_listener

        def get_os_mouse_speed():
            get_mouse_speed = 0x0070
            speed = ctypes.c_int()
            user32.SystemParametersInfoA(get_mouse_speed, 0, ctypes.byref(speed), 0)
            return float(speed.value)
        
        def set_window_passthrough(window, passthrough=True):
            """
            Makes an SDL window passthrough with windows API calls.
            
            Just a straight port of https://github.com/libsdl-org/SDL/pull/14561/
            """
            win_props = sdl3.SDL_GetWindowProperties(window)
            hwnd = ctypes.c_void_p()
            hwnd = sdl3.SDL_GetPointerProperty(win_props, sdl3.SDL_PROP_WINDOW_WIN32_HWND_POINTER, hwnd)
            logging.debug(f"Window hwnd: {hwnd}")
            style = user32.GetWindowLongA(hwnd, GWL_EXSTYLE)
            
            if passthrough:
                key = ctypes.c_int64(0)
                alpha = ctypes.c_int64(0)
                flags = ctypes.c_int64(0)
                if (style & WS_EX_LAYERED):
                    user32.GetLayeredWindowAttributesA(hwnd, ctypes.pointer(key), ctypes.pointer(alpha), ctypes.pointer(flags))
                style |= (WS_EX_TRANSPARENT | WS_EX_LAYERED)
                user32.SetWindowLongA(hwnd, GWL_EXSTYLE, style)
                user32.SetLayeredWindowAttributes(hwnd, key, alpha, flags)
            else:
                style &= ~WS_EX_TRANSPARENT
                if ((style & (WS_EX_LAYERED | LWA_ALPHA)) == WS_EX_LAYERED):
                    style &= ~WS_EX_LAYERED
                user32.SetWindowLong(hwnd, GWL_EXSTYLE, style)

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

        def set_window_passthrough(window, passthrough=True):
            pass

        def init_window_listener(on_focus_change):
            return None

        def get_os_mouse_speed():
            return 1.0
