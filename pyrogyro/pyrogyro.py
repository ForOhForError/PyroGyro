# https://github.com/yannbouteiller/vgamepad?tab=readme-ov-file#getting-started
# https://github.com/Aermoss/PySDL3/blob/main/sdl3/SDL_joystick.py
# https://wiki.libsdl.org/SDL3/APIByCategory

import ctypes
import logging
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

from pyrogyro.constants import SDLButtonEnum, icon_location

SDLCALL = ctypes.CFUNCTYPE(
    ctypes.c_bool, ctypes.c_void_p, ctypes.POINTER(sdl3.SDL_Event)
)


@SDLCALL
def event_filter(userdata, event):
    logging.debug(f"SDL filter event: {event.contents.type}")
    return True


BASIC_IGNORE_LIST = ((1118, 654),)


class Mapping:
    def __init__(self):
        self.mapping = {
            SDLButtonEnum.NORTH: vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
            SDLButtonEnum.SOUTH: vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
            SDLButtonEnum.EAST: vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
            SDLButtonEnum.WEST: vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
        }


class PyroGyroPad:
    def __init__(self, sdl_joystick, mapping: Mapping | None = None):
        self.logger = logging.getLogger("pyrogyropad")
        if not mapping:
            mapping = Mapping()
        self.mapping = mapping
        self.vpad = vg.VX360Gamepad()
        self.sdl_pad = sdl3.SDL_OpenGamepad(sdl_joystick)

        self.left_stick = [0.0, 0.0]
        self.right_stick = [0.0, 0.0]

    def handle_event(self, sdl_event):
        match sdl_event.type:
            case evt_type if sdl_event.type in (
                sdl3.SDL_EVENT_GAMEPAD_BUTTON_DOWN,
                sdl3.SDL_EVENT_GAMEPAD_BUTTON_UP,
            ):
                button_event = sdl_event.gbutton
                enum_val = SDLButtonEnum(int(button_event.button))
                button_name = enum_val.name
                self.logger.info(
                    f"{button_name} {'pressed' if button_event.down else 'released'}"
                )
                button_to_process = self.mapping.mapping.get(enum_val)
                if button_to_process:
                    if button_event.down:
                        self.vpad.press_button(button_to_process)
                    else:
                        self.vpad.release_button(button_to_process)
            case SDL_EVENT_GAMEPAD_AXIS_MOTION:
                axis_event = sdl_event.gaxis
                match axis_event.axis:
                    case sdl3.SDL_GAMEPAD_AXIS_LEFTX:
                        if axis_event.value != -32768.0:
                            self.left_stick[0] = axis_event.value / 32768.0
                    case sdl3.SDL_GAMEPAD_AXIS_LEFTY:
                        self.left_stick[1] = axis_event.value / 32768.0
                    case sdl3.SDL_GAMEPAD_AXIS_RIGHTX:
                        self.right_stick[0] = axis_event.value / 32768.0
                    case sdl3.SDL_GAMEPAD_AXIS_RIGHTY:
                        self.right_stick[1] = axis_event.value / 32768.0
                self.vpad.left_joystick_float(
                    x_value_float=self.left_stick[0], y_value_float=-self.left_stick[1]
                )
                self.vpad.right_joystick_float(
                    x_value_float=self.right_stick[0],
                    y_value_float=-self.right_stick[1],
                )

    def update(self):
        self.vpad.update()


class PyroGyroMapper:
    def __init__(self, poll_rate=1000):
        self.logger = logging.getLogger("pyrogyro")
        self.visible = True
        self.running = True
        self.poll_rate = poll_rate
        self.systray = None
        self.platform = platform.system()
        self.do_platform_setup()

        self.pyropads = {}

        self.vpads = {}
        self.open_sdl_pads = {}
        self.mappings = {}

        self.sdl_joysticks = {}

    def on_focus_change(self, window_title, exe_path):
        print(window_title, exe_path)

    def do_platform_setup(self):
        if self.platform == "Windows":
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

    def populate_joystick_list(self, ignore_virtual=True):
        ignore_list = set(
            ((pypad.vpad.get_vid(), pypad.vpad.get_pid()) for pypad in self.pyropads)
        ).union(set(BASIC_IGNORE_LIST))
        joystick_ids = sdl3.SDL_GetGamepads(None)

        joy_ix = 0
        while joystick_ids[joy_ix] != 0:
            joystick_id = joystick_ids[joy_ix]

            pid = sdl3.SDL_GetJoystickProductForID(joystick_id)
            vid = sdl3.SDL_GetJoystickVendorForID(joystick_id)
            is_virtual = (vid, pid) in ignore_list
            joystick_name = sdl3.SDL_GetJoystickNameForID(joystick_id).decode()
            joystick_uuid_bytes = sdl3.SDL_GetGamepadGUIDForID(joystick_id).data[0:16]
            joystick_uuid = uuid.UUID(bytes=bytes(joystick_uuid_bytes))

            if not (is_virtual and ignore_virtual):
                self.sdl_joysticks[joystick_uuid] = joystick_id

            self.logger.info(
                f"Gamepad {joy_ix}: {joystick_name} ({joystick_uuid}) {'(Virtual)' if is_virtual else ''}"
            )
            joy_ix += 1
        sdl3.SDL_free(joystick_ids)

    def create_device_map(self):
        for joy_uuid in self.sdl_joysticks:
            if joy_uuid not in self.open_sdl_pads:
                joystick_id = self.sdl_joysticks[joy_uuid]
                self.pyropads[joy_uuid] = PyroGyroPad(self.sdl_joysticks[joy_uuid])

    def input_poll(self):
        while self.running:
            event = sdl3.SDL_Event()
            while sdl3.SDL_PollEvent(event):
                match event.type:
                    case (
                        evt_type
                    ) if sdl3.SDL_EVENT_GAMEPAD_AXIS_MOTION <= evt_type <= sdl3.SDL_EVENT_GAMEPAD_STEAM_HANDLE_UPDATED:
                        self.logger.debug(f"polled GAMEPAD event: f{event}")
                        gamepad_event = event.gdevice
                        joystick_uuid_bytes = sdl3.SDL_GetGamepadGUIDForID(
                            gamepad_event.which
                        ).data[0:16]
                        joystick_uuid = uuid.UUID(bytes=bytes(joystick_uuid_bytes))
                        pypad = self.pyropads.get(joystick_uuid)
                        if pypad:
                            pypad.handle_event(event)
                    case _:
                        pass
            sdl3.SDL_UpdateGamepads()
            for pypad in self.pyropads.values():
                pypad.update()
            time.sleep(1.0 / self.poll_rate)

    def process_sdl_event(self, event):
        pass

    def run(self):
        self.init_systray()
        # sdl3.SDL_SetEventFilter(event_filter, None)
        if self.systray:
            try:
                self.populate_joystick_list()
                self.create_device_map()
                self.input_poll()
            except KeyboardInterrupt:
                self.running = False
            finally:
                self.systray.shutdown()


def appmain(*args, **kwargs):
    logging.basicConfig(level=logging.INFO)
    PyroGyroMapper.init_sdl()
    PyroGyroMapper().run()


if __name__ == "__main__":
    appmain(sys.argv)
