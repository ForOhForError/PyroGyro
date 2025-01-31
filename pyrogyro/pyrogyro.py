# https://github.com/yannbouteiller/vgamepad/
# https://github.com/Aermoss/PySDL3/
# https://wiki.libsdl.org/SDL3/APIByCategory

import colorsys
import ctypes
import dataclasses
import enum
import importlib.metadata
import logging
import os.path
import platform
import re
import sys
import threading
import time
import typing
import uuid
from pathlib import Path

import pyautogui
import sdl3
import vgamepad as vg
from infi.systray import SysTrayIcon

import pyrogyro.io_types
from pyrogyro.constants import (
    DEBUG,
    LOG_FORMAT,
    LOG_FORMAT_DEBUG,
    LOG_LEVEL,
    SHOW_STARTUP_VERSION_MODULES,
    VID_PID_IGNORE_LIST,
    icon_location,
)
from pyrogyro.mapping import Mapping
from pyrogyro.math import *
from pyrogyro.monitor_focus import WindowChangeEventListener
from pyrogyro.pyrogyro_pad import PyroGyroPad

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

SDLCALL = ctypes.CFUNCTYPE(
    ctypes.c_bool, ctypes.c_void_p, ctypes.POINTER(sdl3.SDL_Event)
)


@SDLCALL
def event_filter(userdata, event):
    return not (event.contents.type in EVENT_TYPES_FILTER)


EVENT_TYPES_FILTER = tuple()

EVENT_TYPES_IGNORE = (
    sdl3.SDL_EVENT_JOYSTICK_AXIS_MOTION,
    sdl3.SDL_EVENT_JOYSTICK_BALL_MOTION,
    sdl3.SDL_EVENT_JOYSTICK_HAT_MOTION,
    sdl3.SDL_EVENT_JOYSTICK_BUTTON_DOWN,
    sdl3.SDL_EVENT_JOYSTICK_BUTTON_UP,
    sdl3.SDL_EVENT_JOYSTICK_ADDED,
    sdl3.SDL_EVENT_JOYSTICK_REMOVED,
    sdl3.SDL_EVENT_JOYSTICK_BATTERY_UPDATED,
    sdl3.SDL_EVENT_JOYSTICK_UPDATE_COMPLETE,
    sdl3.SDL_EVENT_GAMEPAD_UPDATE_COMPLETE,
)

EVENT_TYPES_PASS_TO_PAD = (
    sdl3.SDL_EVENT_GAMEPAD_AXIS_MOTION,
    sdl3.SDL_EVENT_GAMEPAD_BUTTON_DOWN,
    sdl3.SDL_EVENT_GAMEPAD_BUTTON_UP,
    sdl3.SDL_EVENT_GAMEPAD_TOUCHPAD_DOWN,
    sdl3.SDL_EVENT_GAMEPAD_TOUCHPAD_MOTION,
    sdl3.SDL_EVENT_GAMEPAD_TOUCHPAD_UP,
    sdl3.SDL_EVENT_GAMEPAD_SENSOR_UPDATE,
)


class PyroGyroMapper:
    def __init__(self, poll_rate=1000):
        self.logger = logging.getLogger("PyroGyroMapper")
        self.visible = True
        self.running = True
        self.poll_rate = poll_rate
        self.systray = None
        self.window_listener = None
        self.platform = platform.system()
        self.do_platform_setup()

        self.pyropads = {}
        self.autoload_configs = {}
        self.sdl_joysticks = {}

    def refresh_autoload_mappings(self):
        config_path_list = set(Path("configs").rglob("*.yml"))
        for config_path in config_path_list:
            mod_time = os.path.getmtime(config_path)
            if (
                config_path not in self.autoload_configs
                or self.autoload_configs[config_path][1] != mod_time
            ):
                with open(config_path) as config_handle:
                    mapping: Mapping = Mapping.load_from_file(file_handle=config_path)
                    if mapping.autoload != None:
                        self.logger.debug(
                            f"Pushed autoload mapping for file {config_path}"
                        )
                        self.autoload_configs[config_path] = (
                            mapping,
                            os.path.getmtime(config_path),
                        )
        to_remove = []
        for config_path in self.autoload_configs:
            if config_path not in config_path_list:
                to_remove.append(config_path)
                self.logger.debug(f"Removed autoload mapping for file {config_path}")
        for config_path in to_remove:
            self.autoload_configs.pop(config_path)

    def autoload_refresh_and_evaluate(self, exe_name, window_title):
        self.refresh_autoload_mappings()
        configs_to_check = [
            mapping_tuple[0] for mapping_tuple in self.autoload_configs.values()
        ]
        self.logger.debug(f"checking {len(configs_to_check)} config(s)")
        for pyropad in self.pyropads.values():
            pyropad.evaluate_autoload_mappings(configs_to_check, exe_name, window_title)

    def on_focus_change(self, exe_name, window_title):
        self.logger.debug(f"window changed to: {window_title} ({exe_name})")
        self.autoload_refresh_and_evaluate(exe_name, window_title)

    def do_platform_setup(self):
        if self.platform == "Windows":
            self.kernel32 = ctypes.WinDLL("kernel32")
            self.user32 = ctypes.WinDLL("user32")
            self.kernel32.SetConsoleTitleW("PyroGyro Console")

    def on_quit_callback(self, *args, **kwargs):
        self.running = False

    def init_systray(self):
        if self.platform == "Windows":
            self.logger.info("Starting Tray Icon")
            menu_options = (("Toggle Console", None, self.toggle_vis),)
            self.systray = SysTrayIcon(
                icon_location(), "PyroGyro", menu_options, on_quit=self.on_quit_callback
            )
            self.systray.start()

    def init_window_listener(self):
        if self.platform == "Windows":
            self.logger.info("Starting Window Listener")
            self.window_listener = WindowChangeEventListener(
                callback=self.on_focus_change
            )
            self.window_listener.listen_in_thread()

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
        sdl_init_flags = (
            sdl3.SDL_INIT_GAMEPAD | sdl3.SDL_INIT_HAPTIC | sdl3.SDL_INIT_SENSOR
        )
        sdl3.SDL_Init(sdl_init_flags)

    def populate_joystick_list(self, ignore_virtual=True):
        self.logger.info("== Gamepads currently connected: ==")
        ignore_list = set(
            (
                (pypad.vpad.get_vid(), pypad.vpad.get_pid())
                for pypad in self.pyropads.values()
            )
        ).union(set(VID_PID_IGNORE_LIST))
        joystick_ids = sdl3.SDL_GetGamepads(None)

        joysticks = {}

        joy_ix = 0
        while joystick_ids[joy_ix] != 0:
            joystick_id = joystick_ids[joy_ix]

            pid = sdl3.SDL_GetJoystickProductForID(joystick_id)
            vid = sdl3.SDL_GetJoystickVendorForID(joystick_id)
            is_virtual = (vid, pid) in ignore_list
            joy_name_bytes = sdl3.SDL_GetJoystickNameForID(joystick_id)
            joystick_name = (
                joy_name_bytes.decode() if joy_name_bytes else "[Name Unknown]"
            )
            joystick_uuid_bytes = sdl3.SDL_GetGamepadGUIDForID(joystick_id).data[0:16]
            joystick_uuid = uuid.UUID(bytes=bytes(joystick_uuid_bytes))

            if not (is_virtual and ignore_virtual):
                joysticks[joystick_uuid] = joystick_id

            self.logger.info(
                f"Gamepad {joy_ix}: {joystick_name} ({joystick_uuid}) {'(Virtual)' if is_virtual else ''}"
            )
            joy_ix += 1
        self.logger.info("==")
        sdl3.SDL_free(joystick_ids)
        self.sdl_joysticks = joysticks

    def create_device_map(self):
        for joy_uuid in self.sdl_joysticks:
            if joy_uuid not in self.pyropads:
                joystick_id = self.sdl_joysticks[joy_uuid]
                self.logger.info(f"Registering pad for new device {joy_uuid}")
                self.pyropads[joy_uuid] = PyroGyroPad(self.sdl_joysticks[joy_uuid])
        to_remove = []
        for joy_uuid in self.pyropads:
            if joy_uuid not in self.sdl_joysticks:
                self.logger.info(f"Removing pad for removed device {joy_uuid}")
                to_remove.append(joy_uuid)
        for joy_uuid in to_remove:
            self.pyropads.pop(joy_uuid)

    def input_poll(self):
        while self.running:
            populate_pads = False
            event = sdl3.SDL_Event()
            while sdl3.SDL_PollEvent(event):
                match event.type:
                    case evt_type if evt_type in EVENT_TYPES_PASS_TO_PAD:
                        gamepad_event = event.gdevice
                        joystick_uuid_bytes = sdl3.SDL_GetGamepadGUIDForID(
                            gamepad_event.which
                        ).data[0:16]
                        joystick_uuid = uuid.UUID(bytes=bytes(joystick_uuid_bytes))
                        pypad = self.pyropads.get(joystick_uuid)
                        if pypad:
                            pypad.handle_event(event)
                    case sdl3.SDL_EVENT_GAMEPAD_ADDED | sdl3.SDL_EVENT_GAMEPAD_REMOVED:
                        populate_pads = True
                    case evt_type if evt_type in EVENT_TYPES_IGNORE:
                        pass
                    case _:
                        self.logger.debug(
                            f"fallthrough, ignoring gamepad event of type {hex(event.type)}"
                        )
            if populate_pads:
                self.populate_joystick_list()
                self.create_device_map()
                if self.window_listener:
                    exe_name, window_title = self.window_listener.get_current_focus()
                else:
                    exe_name, window_title = "pyrogyro.exe", "PyroGyro Console"
                self.autoload_refresh_and_evaluate(exe_name, window_title)
            sdl3.SDL_UpdateGamepads()
            time_now = time.time()
            for pypad in self.pyropads.values():
                pypad.update(time_now)
            time.sleep(1.0 / self.poll_rate)

    def process_sdl_event(self, event):
        pass

    def run(self):
        self.logger.info("PyroGyro Starting")
        for module_name in SHOW_STARTUP_VERSION_MODULES:
            self.logger.info(
                f"{module_name} version {importlib.metadata.version(module_name)}"
            )
        self.init_systray()
        self.init_window_listener()
        sdl3.SDL_SetEventFilter(event_filter, None)

        self.refresh_autoload_mappings()

        try:
            self.input_poll()
        except KeyboardInterrupt:
            pass
        except BaseException:
            self.logger.exception("Unhandled Error; Exiting")
        finally:
            self.running = False
            if self.systray:
                self.systray.shutdown()
            if self.window_listener:
                self.window_listener.stop()


def appmain(*args, **kwargs):
    logging.basicConfig(
        level=LOG_LEVEL, format=LOG_FORMAT_DEBUG if DEBUG else LOG_FORMAT
    )
    PyroGyroMapper.init_sdl()
    PyroGyroMapper().run()


if __name__ == "__main__":
    appmain(sys.argv)
