import colorsys
import ctypes
import dataclasses
import enum
import importlib.metadata
import logging
import os.path
import re
import sys
import threading
import time
import typing
import uuid
from pathlib import Path

import sdl3
import vgamepad as vg
from pydantic import ValidationError
from ruamel.yaml.scanner import ScannerError

import pyrogyro.io_types
from pyrogyro.constants import (
    DEBUG,
    DEFAULT_POLL_RATE,
    LOG_FORMAT,
    LOG_FORMAT_DEBUG,
    LOG_LEVEL,
    SHOW_STARTUP_VERSION_MODULES,
    VID_PID_IGNORE_LIST,
    icon_location,
)
from pyrogyro.mapping import Mapping
from pyrogyro.math import *
from pyrogyro.platform import (
    init_window_listener,
    set_console_title,
    set_console_visibility,
)
from pyrogyro.pyrogyro_pad import PyroGyroPad
from pyrogyro.system_tray import SystemTray
from pyrogyro.web import WebServer

EVENT_TYPES_FILTER = set()

EVENT_TYPES_IGNORE = set(
    (
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
)

EVENT_TYPES_PASS_TO_PAD = set(
    (
        sdl3.SDL_EVENT_GAMEPAD_AXIS_MOTION,
        sdl3.SDL_EVENT_GAMEPAD_BUTTON_DOWN,
        sdl3.SDL_EVENT_GAMEPAD_BUTTON_UP,
        sdl3.SDL_EVENT_GAMEPAD_TOUCHPAD_DOWN,
        sdl3.SDL_EVENT_GAMEPAD_TOUCHPAD_MOTION,
        sdl3.SDL_EVENT_GAMEPAD_TOUCHPAD_UP,
        sdl3.SDL_EVENT_GAMEPAD_SENSOR_UPDATE,
        sdl3.SDL_EVENT_GAMEPAD_TOUCHPAD_DOWN,
        sdl3.SDL_EVENT_GAMEPAD_TOUCHPAD_MOTION,
        sdl3.SDL_EVENT_GAMEPAD_TOUCHPAD_UP,
    )
)


@sdl3.SDL_EventFilter
def event_filter(userdata, event):
    return not (event.contents.type in EVENT_TYPES_FILTER)


class PyroGyroMapper:
    def __init__(self, poll_rate=DEFAULT_POLL_RATE):
        self.logger = logging.getLogger("PyroGyroMapper")
        self.visible = True
        self.running = True
        self.poll_rate = poll_rate
        self.systray = None
        self.window_listener = None
        self.do_platform_setup()
        self.calibrating = False
        self.web_server = WebServer()
        self.config_lock = threading.Lock()

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
                    try:
                        mapping: Mapping = Mapping.load_from_file(
                            file_handle=config_path
                        )
                        if mapping.autoload != None:
                            self.logger.debug(
                                f"Pushed autoload mapping for file {config_path}"
                            )
                            self.autoload_configs[config_path] = (
                                mapping,
                                os.path.getmtime(config_path),
                            )
                    except ValidationError as validation_error:
                        self.logger.info(
                            f"Error loading config {config_path}; skipping"
                        )
                        self.logger.debug(f"== VALIDATION ERRORS ==")
                        err_count = 1
                        for error in validation_error.errors():
                            self.logger.debug(
                                f"{err_count}: {error.get('type')} AT {error.get('loc')}: {error.get('msg')}"
                            )
                            err_count += 1
                    except ScannerError as scanner_error:
                        self.logger.info(
                            f"Error parsing config {config_path}; skipping"
                        )
                        self.logger.debug(f"{scanner_error}")
                    except Exception as other_error:
                        self.logger.info(
                            f"Unknown error loading config {config_path}; skipping"
                        )
                        self.logger.debug(f"{type(other_error)}: {other_error}")
        to_remove = []
        for config_path in self.autoload_configs:
            if config_path not in config_path_list:
                to_remove.append(config_path)
                self.logger.debug(f"Removed autoload mapping for file {config_path}")
        for config_path in to_remove:
            self.autoload_configs.pop(config_path)

    def autoload_refresh_and_evaluate(self, exe_name, window_title):
        with self.config_lock:
            self.refresh_autoload_mappings()
            configs_to_check = [
                mapping_tuple[0] for mapping_tuple in self.autoload_configs.values()
            ]
            self.logger.debug(f"checking {len(configs_to_check)} config(s)")
            for pyropad in self.pyropads.values():
                pyropad.evaluate_autoload_mappings(
                    configs_to_check, exe_name, window_title
                )

    def on_focus_change(self, exe_name, window_title):
        self.logger.debug(f"window changed to: {window_title} ({exe_name})")
        self.autoload_refresh_and_evaluate(exe_name, window_title)

    def do_platform_setup(self):
        set_console_title("PyroGyro Console")

    def on_quit_callback(self, userdata, entry):
        self.running = False

    def init_systray(self):
        self.logger.info("Starting Tray Icon")
        self.systray = SystemTray("PyroGyro", icon_location())
        self.systray.add_menu_option("Quit", callback=self.on_quit_callback)
        self.systray.add_menu_option("Toggle Console", callback=self.toggle_vis)
        if self.web_server:
            self.systray.add_menu_option(
                "Open Web Console", callback=self.web_server.open_web_ui
            )

    def init_window_listener(self):
        self.logger.info("Starting Window Listener")
        self.window_listener = init_window_listener(
            on_focus_change=self.on_focus_change
        )

    def start_calibration(self):
        self.logger.info("Starting gyro calibration on all devices")
        for pyropad in self.pyropads.values():
            pyropad.set_gyro_calibrating(True)

    def end_calibration(self):
        self.logger.info("Ending gyro calibration on all devices")
        for pyropad in self.pyropads.values():
            pyropad.set_gyro_calibrating(False)

    def handle_console_input(self, console_input: str):
        if console_input:
            match console_input:
                case com if "calibrate".startswith(com.lower()):
                    self.calibrating = not self.calibrating
                    if self.calibrating:
                        self.start_calibration()
                    else:
                        self.end_calibration()

    def console_input_loop(self):
        try:
            while True:
                console_input = input("")
                self.handle_console_input(console_input)
        except (EOFError, KeyboardInterrupt):
            pass

    def start_console_input_thread(self):
        threading.Thread(target=self.console_input_loop, daemon=True).start()

    def toggle_vis(self, *args):
        self.visible = not self.visible
        set_console_visibility(self.visible)

    @classmethod
    def init_sdl(cls):
        sdl3.SDL_SetHint(sdl3.SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS, "1".encode())
        sdl_init_flags = (
            sdl3.SDL_INIT_VIDEO
            | sdl3.SDL_INIT_GAMEPAD
            | sdl3.SDL_INIT_HAPTIC
            | sdl3.SDL_INIT_SENSOR
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
                self.pyropads[joy_uuid] = PyroGyroPad(
                    self.sdl_joysticks[joy_uuid],
                    web_server=self.web_server,
                    parent=self,
                )
        to_remove = []
        for joy_uuid in self.pyropads:
            if joy_uuid not in self.sdl_joysticks:
                self.logger.info(f"Removing pad for removed device {joy_uuid}")
                to_remove.append(joy_uuid)
        for joy_uuid in to_remove:
            pyropad = self.pyropads.pop(joy_uuid)
            pyropad.cleanup()

    def input_poll(self):
        while self.running:
            start_time = time.time_ns()
            ns_per_poll = int(1000000000 / self.poll_rate)
            populate_pads = False
            event = sdl3.SDL_Event()
            for pypad in self.pyropads.values():
                pypad.on_poll_start()
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
            if self.systray:
                self.systray.update()
            for pypad in self.pyropads.values():
                pypad.update(time.time())
            poll_ns = time.time_ns() - start_time
            sdl3.SDL_DelayNS(ns_per_poll - poll_ns)

    def run(self):
        self.logger.info("PyroGyro Starting")
        for module_name in SHOW_STARTUP_VERSION_MODULES:
            self.logger.info(
                f"{module_name} version {importlib.metadata.version(module_name)}"
            )
        self.init_systray()
        self.init_window_listener()
        self.start_console_input_thread()
        self.web_server.run_in_thread()
        sdl3.SDL_SetEventFilter(event_filter, None)

        if self.window_listener:
            self.window_listener.process_current_window()
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
