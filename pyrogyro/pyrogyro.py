# https://github.com/yannbouteiller/vgamepad?tab=readme-ov-file#getting-started
# https://github.com/Aermoss/PySDL3/blob/main/sdl3/SDL_joystick.py
# https://wiki.libsdl.org/SDL3/APIByCategory

import ctypes
import platform
import sys
import threading
import time
import uuid
from pathlib import Path

import pyautogui
import sdl3
import vgamepad as vg
from infi.systray import SysTrayIcon

from pyrogyro.constants import icon_location

SDLCALL = ctypes.CFUNCTYPE(
    ctypes.c_bool, ctypes.c_void_p, ctypes.POINTER(sdl3.SDL_Event)
)


@SDLCALL
def event_filter(userdata, event):
    print(event.contents.type)
    return True


class PyroGyroMapper:
    def __init__(self, poll_rate=1000):
        self.vpads = []
        self.visible = True
        self.running = True
        self.poll_rate = poll_rate
        self.systray = None
        self.platform = platform.system()

        self.do_platform_setup()

    def do_platform_setup(self):
        if self.platform == "Windows":
            print("wininit")
            self.kernel32 = ctypes.WinDLL("kernel32")
            self.user32 = ctypes.WinDLL("user32")
            self.kernel32.SetConsoleTitleW("PyroGyro Console")

    def on_quit_callback(self, *args, **kwargs):
        self.running = False

    def init_systray(self):
        if self.platform == "Windows":
            menu_options = (("Toggle Console", None, self.toggle_vis),)
            self.systray = SysTrayIcon(
                icon_location(), "PyroGyro", menu_options, on_quit=self.on_quit_callback
            )
            self.systray.start()

    def toggle_vis(self, *args):
        self.visible = not self.visible
        if self.platform == "Windows":
            hWnd = self.kernel32.GetConsoleWindow()
            self.user32.ShowWindow(hWnd, 1 if self.visible else 0)

    @classmethod
    def init_sdl(cls):
        sdl3.SDL_SetHint(
            sdl3.SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS.encode(), "1".encode()
        )
        sdl3.SDL_Init(sdl3.SDL_INIT_GAMEPAD)

    def get_gamepads(self, ignore_virtual=True):
        ignore_list = set(((vpad.get_vid(), vpad.get_pid()) for vpad in self.vpads))
        joystick_ids = sdl3.SDL_GetGamepads(None)
        joysticks = []

        joy_ix = 0
        while joystick_ids[joy_ix] != 0:
            joystick_id = joystick_ids[joy_ix]

            pid = sdl3.SDL_GetJoystickProductForID(joystick_id)
            vid = sdl3.SDL_GetJoystickVendorForID(joystick_id)
            print(pid, vid)
            is_virtual = (vid, pid) in ignore_list
            joystick_name = sdl3.SDL_GetJoystickNameForID(joystick_id).decode()
            joystick_uuid_bytes = sdl3.SDL_GetGamepadGUIDForID(joystick_id).data[0:16]
            joystick_uuid = uuid.UUID(bytes=bytes(joystick_uuid_bytes))
            if not (ignore_virtual and is_virtual):
                joysticks.append([joystick_id, joystick_uuid, joystick_name])

            print(
                f"{joystick_name} ({joystick_uuid}) {'(Virtual)' if is_virtual else ''}"
            )
            joy_ix += 1
        sdl3.SDL_free(joystick_ids)
        return joysticks

    def input_poll(self):
        # pad = sdl3.SDL_OpenGamepad(joy_id)
        while self.running:
            event = sdl3.SDL_Event()
            while sdl3.SDL_PollEvent(event):
                # print(sdl3.SDL_EventGetType)
                # print(event)
                pass
            sdl3.SDL_UpdateGamepads()
            time.sleep(1.0 / self.poll_rate)

    def process_sdl_event(self, event):
        pass

    def run(self):
        self.init_systray()
        sdl3.SDL_SetEventFilter(event_filter, None)
        if self.systray:
            try:
                pads = self.get_gamepads()
                print(pads)
                if pads:
                    self.input_poll()
            except KeyboardInterrupt:
                self.running = False
            finally:
                self.systray.shutdown()


def appmain(*args, **kwargs):
    PyroGyroMapper.init_sdl()
    PyroGyroMapper().run()


if __name__ == "__main__":
    appmain(sys.argv)
