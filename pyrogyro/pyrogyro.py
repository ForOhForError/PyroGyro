import importlib.metadata
import logging
import os
import os.path
import re
import sys
import threading
import time
import uuid
from pathlib import Path

from pyrogyro.project_util import setup_pysdl_env_vars

setup_pysdl_env_vars()

import sdl3

import pyrogyro.io_types
from pyrogyro.constants import (
    DEBUG,
    DEFAULT_POLL_RATE,
    LOG_FORMAT,
    LOG_FORMAT_DEBUG,
    LOG_LEVEL,
    SHOW_STARTUP_VERSION_MODULES,
    VID_PID_IGNORE_LIST,
    EXPERIMENT_OVERLAY,
    resource_location,
)
from pyrogyro.math import *
from pyrogyro.config_blocks import ConfigBlock, PyroGyroConfig
from pyrogyro.platform_util import (
    init_window_listener,
    set_console_title,
    set_console_visibility,
    is_minimized,
)
from pyrogyro.pyrogyro_pad import InputPad
from pyrogyro.system_tray import SystemTray
from pyrogyro.web import WebServer
import pyrogyro.overlay

import pyrogyro.misc_blocks
import pyrogyro.kbm_blocks
import pyrogyro.gamepad_motion
import pyrogyro.mode_blocks
import pyrogyro.color_led

pyrogyro.misc_blocks.register_blocks()
pyrogyro.kbm_blocks.register_blocks()
pyrogyro.gamepad_motion.register_blocks()
pyrogyro.mode_blocks.register_blocks()
pyrogyro.color_led.register_blocks()


EVENT_TYPES_FILTER = set(
    range(sdl3.SDL_EVENT_WINDOW_SHOWN, sdl3.SDL_EVENT_WINDOW_HDR_STATE_CHANGED + 1)
)

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
        sdl3.SDL_EVENT_MOUSE_ADDED,
        sdl3.SDL_EVENT_KEYBOARD_ADDED,
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


@sdl3.SDL_EventFilter  # type: ignore
def event_filter(userdata, event):
    return not (event.contents.type in EVENT_TYPES_FILTER)


NS_PER_SECOND = 1000000000


class PyroGyroMapper:
    _singleton_instance: "PyroGyroMapper|None" = None

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
        self.overlay = pyrogyro.overlay.Overlay() if EXPERIMENT_OVERLAY else None
        self.config_lock = threading.Lock()

        self.active_config: PyroGyroConfig | None = None
        self.pad_map: dict[sdl3.SDL_JoystickID, InputPad] = {}
        self.autoload_configs = {}
        self.sdl_joysticks = {}

    def get_poll_rate(self):
        return self.poll_rate

    @classmethod
    def instance(cls) -> "PyroGyroMapper":
        if cls._singleton_instance == None:
            cls._singleton_instance = cls()
        return cls._singleton_instance

    def parse_config_from_file(self, config_path) -> PyroGyroConfig | None:
        config: PyroGyroConfig | None = None
        try:
            with open(config_path, "rb") as config_handle:
                config = PyroGyroConfig.load_from_file(file_handle=config_handle)
        except FileNotFoundError:
            self.logger.info(f"Could not find file {config_path}")
        except Exception as other_error:
            self.logger.info(f"Unknown error loading config {config_path}; skipping")
            self.logger.debug(f"{type(other_error)}: {other_error}")
        return config

    def refresh_autoload_mappings(self):
        config_path_list = set(Path("configs").rglob("*.toml"))
        for config_path in config_path_list:
            mod_time = os.path.getmtime(config_path)
            if (
                config_path not in self.autoload_configs
                or self.autoload_configs[config_path][1] != mod_time
            ):
                config = self.parse_config_from_file(config_path)
                if config:
                    if config.autoload:
                        self.logger.debug(
                            f"Pushed autoload mapping for file {config_path}"
                        )
                        self.autoload_configs[config_path] = (
                            config,
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
        with self.config_lock:
            self.refresh_autoload_mappings()
            configs_to_check = [
                mapping_tuple[0] for mapping_tuple in self.autoload_configs.values()
            ]
            self.logger.debug(f"checking {len(configs_to_check)} config(s)")
            potential_mappings = []
            old_mapping = self.active_config
            new_mapping = None
            mapping: PyroGyroConfig
            for mapping in configs_to_check:
                if all(
                    (
                        re.fullmatch(mapping.autoload_window_name, window_title),
                        re.fullmatch(mapping.autoload_exe_name, exe_name),
                    )
                ):
                    potential_mappings.append(mapping)
            if potential_mappings:
                if len(potential_mappings) == 1:
                    new_mapping = potential_mappings[0]
                else:
                    potential_mappings.sort(
                        key=PyroGyroConfig.count_autoload_specificity
                    )
                    best_match = potential_mappings[-1]
                    final_value = best_match.count_autoload_specificity()
                    remaining_mappings = len(
                        [
                            mapping
                            for mapping in potential_mappings
                            if mapping.count_autoload_specificity() == final_value
                        ]
                    )
                    if remaining_mappings == 1:
                        new_mapping = best_match
            if new_mapping is not old_mapping:
                self.active_config = new_mapping
                if old_mapping:
                    old_mapping.unload()
                if self.active_config:
                    log_line = f"Switched to config {self.active_config.name}"
                    self.logger.info(log_line)
                    if self.overlay:
                        self.overlay.log_to_overlay(log_line)
                    self.active_config.load()
                    self.create_device_map()
                else:
                    self.logger.info(f"Deactivated all configs.")

    def load_config_from_file(self, file_name: str):
        config = self.parse_config_from_file(file_name)
        old_config = self.active_config
        if config:
            self.active_config = config
            if old_config:
                old_config.unload()
            if self.active_config:
                self.logger.info(f"Switched to config {self.active_config.name}")
                self.active_config.load()
                self.create_device_map()

    def on_focus_change(self, exe_name, window_title):
        self.logger.debug(f"window changed to: {window_title} ({exe_name})")
        self.autoload_refresh_and_evaluate(exe_name, window_title)

    def do_platform_setup(self):
        set_console_title("PyroGyro Console")

    def on_quit_callback(self, userdata, entry):
        self.running = False

    def init_systray(self):
        self.logger.info("Starting Tray Icon")
        self.systray = SystemTray("PyroGyro", resource_location("pyrogyro2.ico"))
        self.systray.add_menu_option("Quit", callback=self.on_quit_callback)
        self.systray.add_menu_option("Toggle Console", callback=self.toggle_vis)
        self.systray.add_menu_option("Toggle Overlay", callback=self.toggle_overlay)
        if self.web_server:
            self.systray.add_menu_option(
                "Open Web Console", callback=self.web_server.open_web_ui
            )

    def init_window_listener(self):
        self.logger.info("Starting Window Listener")
        self.window_listener = init_window_listener(
            on_focus_change=self.on_focus_change
        )

    def set_calibration(self, *args, calibrating: bool | None = None):
        if calibrating == None:
            self.calibrating = not self.calibrating
        else:
            self.calibrating = calibrating
        if self.calibrating:
            self.logger.info("Starting gyro calibration on all devices")
        else:
            self.logger.info("Ending gyro calibration on all devices")
        for pad in self.pad_map.values():
            pad.set_gyro_calibrating(self.calibrating)

    def print_keylist(self, *args):
        self.logger.info(" == MAPPABLE KEYS == ")
        for key in pyrogyro.io_types.KeyboardKey:
            self.logger.info(f" * {repr(key.name)[1:-1]}")

    def print_registered_block(self, *args):
        if len(args):
            block_type = args[0]
            block_class: type[ConfigBlock] | None = ConfigBlock.get_block_class(
                block_type
            )
            if block_class:
                self.logger.info(f"== {block_type} ==")
                self.logger.info(f"= Config =")
                for field in block_class.Config.fields():
                    self.logger.info(f" * {field}")
                self.logger.info(f"= Input =")
                for field in block_class.Inputs.fields():
                    self.logger.info(f" * {field}")
                self.logger.info(f"= Output =")
                for field in block_class.Outputs.fields():
                    self.logger.info(f" * {field}")
                self.logger.info(f"====")
            else:
                self.logger.info(f"No block with name '{block_type}'")
        else:
            self.logger.info("== Blocks ==")
            for block_type in ConfigBlock.get_block_keys():
                self.logger.info(f" * {block_type}")

    def console_commands(self) -> dict:
        return {
            "calibrate": self.set_calibration,
            "keylist": self.print_keylist,
            "overlay": self.toggle_overlay,
            "load": self.load_config_from_file,
            "block": self.print_registered_block,
        }

    def handle_console_input(self, console_input: str):
        if console_input:
            commands = console_input.split()
            command_string = commands[0].lower()
            match = None
            for command in self.console_commands():
                if command.startswith(command_string):
                    if not match:
                        match = command
                    else:
                        match = None
                        self.logger.info(f"Ambiguous command {command_string}")
                        break
            if match:
                self.console_commands()[match](*commands[1:])

    def console_input_loop(self):
        try:
            while self.running:
                console_input = input("")
                self.handle_console_input(console_input)
        except (EOFError, KeyboardInterrupt):
            pass

    def minimize_to_tray_loop(self):
        while self.running:
            if is_minimized():
                set_console_visibility(False)
                self.visible = False
            sdl3.SDL_Delay(1000)

    def overlay_loop(self):
        if self.overlay:
            self.overlay.display_loop()

    def start_console_input_thread(self):
        threading.Thread(target=self.console_input_loop, daemon=True).start()

    def start_minimize_to_tray_thread(self):
        threading.Thread(target=self.minimize_to_tray_loop, daemon=True).start()

    def start_overlay_thread(self):
        threading.Thread(target=self.overlay_loop, daemon=True).start()

    def toggle_vis(self, *args):
        self.visible = not self.visible
        set_console_visibility(self.visible)

    def toggle_overlay(self, *args):
        if self.overlay:
            self.overlay.toggle_hidden()

    @classmethod
    def init_sdl(cls):
        sdl3.SDL_SetHint(sdl3.SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS, "1".encode())  # type: ignore
        sdl3.SDL_SetHint(sdl3.SDL_HINT_GAMECONTROLLER_SENSOR_FUSION, "1".encode())  # type: ignore
        sdl3.SDL_SetHint(sdl3.SDL_HINT_JOYSTICK_HIDAPI_STEAM, "1".encode())  # type: ignore
        sdl3.SDL_SetHint(sdl3.SDL_HINT_VIDEO_DOUBLE_BUFFER, "1".encode())  # type: ignore

        # The format of the string is a comma separated list of USB VID/PID pairs in hexadecimal form
        gamepad_ignore_hint = ",".join(
            [f"{vidpid[0]:#06x}/{vidpid[1]:#06x}" for vidpid in VID_PID_IGNORE_LIST]
        )
        sdl3.SDL_SetHint(
            sdl3.SDL_HINT_GAMECONTROLLER_IGNORE_DEVICES,  # type: ignore
            gamepad_ignore_hint.encode(),  # type: ignore
        )

        sdl_init_flags = (
            sdl3.SDL_INIT_VIDEO
            | sdl3.SDL_INIT_GAMEPAD
            | sdl3.SDL_INIT_HAPTIC
            | sdl3.SDL_INIT_SENSOR
        )
        sdl3.SDL_Init(sdl_init_flags)  # type: ignore
        sdl3.TTF_Init()

    def update_devices(self):
        self.populate_joystick_list()
        self.create_device_map()
        if self.window_listener:
            exe_name, window_title = self.window_listener.get_current_focus()  # type: ignore
        else:
            exe_name, window_title = "pyrogyro.exe", "PyroGyro Console"
        self.autoload_refresh_and_evaluate(exe_name, window_title)

    def populate_joystick_list(self, ignore_virtual=True):
        self.logger.info("== Gamepads currently connected: ==")
        joystick_ids = sdl3.SDL_GetGamepads(None)  # type: ignore

        joysticks = {}

        joy_ix = 0
        while joystick_ids[joy_ix] != 0:  # type: ignore
            joystick_id = joystick_ids[joy_ix]  # type: ignore

            pid = sdl3.SDL_GetJoystickProductForID(joystick_id)
            vid = sdl3.SDL_GetJoystickVendorForID(joystick_id)
            is_virtual = (vid, pid) in VID_PID_IGNORE_LIST
            joy_name_bytes = sdl3.SDL_GetJoystickNameForID(joystick_id)
            joystick_name = (
                joy_name_bytes.decode() if joy_name_bytes else "[Name Unknown]"  # type: ignore
            )
            joystick_uuid_bytes = sdl3.SDL_GetGamepadGUIDForID(joystick_id).data[0:16]  # type: ignore
            joystick_uuid = uuid.UUID(bytes=bytes(joystick_uuid_bytes))

            if not (is_virtual and ignore_virtual):
                joysticks[joystick_uuid] = joystick_id

            self.logger.info(
                f"Gamepad {joy_ix}: {joystick_name} ({joystick_uuid}) {'(Virtual)' if is_virtual else ''}"
            )
            joy_ix += 1
        self.logger.info("==")
        sdl3.SDL_free(joystick_ids)  # type: ignore
        self.sdl_joysticks = joysticks

    def create_device_map(self):
        pad_ids = list(self.sdl_joysticks.values())
        self.pad_map.clear()
        if self.active_config:
            pad_blocks = self.active_config.get_blocks_by_type(InputPad)
            pad_block: InputPad
            for pad_block in pad_blocks:
                pad_id = pad_block.claim_pad(pad_ids)
                if pad_id:
                    self.pad_map[pad_id] = pad_block
            self.active_config.do_load_unload()

    def input_poll(self):
        last_time = time.time_ns()
        while self.running:
            start_time = time.time_ns()
            delta_time = (start_time - last_time) / NS_PER_SECOND
            last_time = start_time
            ns_per_poll = int(NS_PER_SECOND / self.poll_rate)
            populate_pads = False
            event = sdl3.SDL_Event()
            for pypad in self.pad_map.values():
                pypad.poll_start()
            while sdl3.SDL_PollEvent(event):  # type: ignore
                match event.type:  # type: ignore
                    case evt_type if evt_type in EVENT_TYPES_PASS_TO_PAD:
                        gamepad_event = event.gdevice  # type: ignore
                        pad_id = gamepad_event.which
                        pad_block = self.pad_map.get(pad_id)
                        if pad_block:
                            pad_block.handle_event(event)
                    case sdl3.SDL_EVENT_GAMEPAD_ADDED | sdl3.SDL_EVENT_GAMEPAD_REMOVED:
                        populate_pads = True
                    case evt_type if evt_type in EVENT_TYPES_IGNORE:
                        pass
                    case sdl3.SDL_EVENT_QUIT:
                        self.running = False
                    case _:
                        self.logger.debug(
                            f"fallthrough, ignoring gamepad event of type {hex(event.type)}"  # type: ignore
                        )
            if populate_pads:
                self.update_devices()
            if self.systray:
                self.systray.update()
            if self.active_config:
                self.active_config.process(delta_time=delta_time)
            poll_ns = time.time_ns() - start_time
            delay_ns = ns_per_poll - poll_ns
            sdl3.SDL_DelayNS(delay_ns)  # type: ignore

    def run(self):
        self.logger.info("PyroGyro Starting")
        for module_name in SHOW_STARTUP_VERSION_MODULES:
            self.logger.info(
                f"{module_name} version {importlib.metadata.version(module_name)}"
            )
        self.init_systray()
        self.init_window_listener()
        self.start_console_input_thread()
        self.start_overlay_thread()
        self.start_minimize_to_tray_thread()
        self.web_server.run_in_thread()
        sdl3.SDL_SetEventFilter(event_filter, None)  # type: ignore

        if self.window_listener:
            self.window_listener.process_current_window()
        self.refresh_autoload_mappings()
        self.update_devices()

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
    PyroGyroMapper.instance().run()


def profile():
    import cProfile
    import pstats
    from pyrogyro.constants import ROOT_DIR

    logging.basicConfig(
        level=LOG_LEVEL, format=LOG_FORMAT_DEBUG if DEBUG else LOG_FORMAT
    )
    PyroGyroMapper.init_sdl()
    with cProfile.Profile() as pr:
        PyroGyroMapper.instance().run()
        stats = pstats.Stats(pr)
        stats.sort_stats(pstats.SortKey.TIME)
        stats.print_stats(0.1)
        stats.dump_stats(ROOT_DIR / "pyrogyro.prof")


if __name__ == "__main__":
    appmain(sys.argv)
