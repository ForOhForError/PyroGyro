# https://github.com/yannbouteiller/vgamepad/
# https://github.com/Aermoss/PySDL3/
# https://wiki.libsdl.org/SDL3/APIByCategory

import ctypes
import importlib.metadata
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

import pyrogyro.io_types
from pyrogyro.constants import (
    DEBUG,
    DEFAULT_CONFIG_FILE,
    LOG_FORMAT,
    LOG_FORMAT_DEBUG,
    LOG_LEVEL,
    SHOW_STARTUP_VERSION_MODULES,
    VID_PID_IGNORE_LIST,
    icon_location,
)
from pyrogyro.gamepad_motion import (
    Vec2, Vec3,
    gyro_camera_player,
    gyro_camera_player_lean,
    sensor_fusion_gravity,
)
from pyrogyro.io_types import (
    XUSB_BUTTON,
    DoubleAxisSource,
    DoubleAxisTarget,
    KeyboardKeyTarget,
    SDLButtonSource,
    SingleAxisSource,
    SingleAxisTarget,
    getPossibleAxisPairs,
    to_bool,
    to_float,
)
from pyrogyro.mapping import Mapping
from pyrogyro.monitor_focus import WindowChangeEventListener

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


class PyroGyroPad:
    def __init__(self, sdl_joystick, mapping: Mapping | None = None):
        self.logger = logging.getLogger("PyroGyroPad")
        if not mapping:
            with open(DEFAULT_CONFIG_FILE) as config_file:
                mapping = Mapping.load_from_file(config_file)
        self.mapping = mapping
        self.vpad = vg.VX360Gamepad()
        self.sdl_pad = sdl3.SDL_OpenGamepad(sdl_joystick)
        self.last_gyro_timestamp = None
        self.last_accel_timestamp = None
        if sdl3.SDL_GamepadHasSensor(self.sdl_pad, sdl3.SDL_SENSOR_GYRO):
            self.logger.info("Gyro Sensor Detected")
            sdl3.SDL_SetGamepadSensorEnabled(self.sdl_pad, sdl3.SDL_SENSOR_GYRO, True)
        if sdl3.SDL_GamepadHasSensor(self.sdl_pad, sdl3.SDL_SENSOR_ACCEL):
            self.logger.info("Accel Sensor Detected")
            sdl3.SDL_SetGamepadSensorEnabled(self.sdl_pad, sdl3.SDL_SENSOR_ACCEL, True)

        self.left_stick = [0.0, 0.0]
        self.right_stick = [0.0, 0.0]

        self.mouse_vel = [0.0, 0.0]
        self.combo_sources = {}
        self.combo_presses_active = set()
        self.gravity = Vec3()
        self.leftover_vel = Vec2()

    def send_value(self, source_value, target_enum):
        match type(target_enum):
            case pyrogyro.io_types.SingleAxisTarget:
                float_val = to_float(source_value)
                match target_enum:
                    case SingleAxisTarget.XUSB_GAMEPAD_L2:
                        self.vpad.left_trigger_float(float_val)
                    case SingleAxisTarget.XUSB_GAMEPAD_R2:
                        self.vpad.right_trigger_float(float_val)
                    case SingleAxisTarget.XUSB_GAMEPAD_LSTICK_X:
                        self.left_stick[0] = float_val
                        self.vpad.left_joystick_float(
                            self.left_stick[0], -self.left_stick[1]
                        )
                    case SingleAxisTarget.XUSB_GAMEPAD_LSTICK_Y:
                        self.left_stick[1] = float_val
                        self.vpad.left_joystick_float(
                            self.left_stick[0], -self.left_stick[1]
                        )
                    case SingleAxisTarget.XUSB_GAMEPAD_RSTICK_X:
                        self.right_stick[0] = float_val
                        self.vpad.right_joystick_float(
                            self.right_stick[0], -self.right_stick[1]
                        )
                    case SingleAxisTarget.XUSB_GAMEPAD_RSTICK_Y:
                        self.right_stick[1] = float_val
                        self.vpad.right_joystick_float(
                            self.right_stick[0], -self.right_stick[1]
                        )
            case pyrogyro.io_types.XUSB_BUTTON:
                if to_bool(source_value):
                    self.vpad.press_button(target_enum.value)
                else:
                    self.vpad.release_button(target_enum.value)
            case pyrogyro.io_types.KeyboardKeyTarget:
                if to_bool(source_value):
                    pyautogui.keyDown(target_enum.value)
                else:
                    pyautogui.keyUp(target_enum.value)
            case pyrogyro.io_types.MouseTarget:
                if to_bool(source_value):
                    pyautogui.mouseDown(button=target_enum.value)
                else:
                    pyautogui.mouseUp(button=target_enum.value)

    def handle_event(self, sdl_event):
        gyro_x, gyro_y, gyro_z = 0.0, 0.0, 0.0
        accel_x, accel_y, accel_z = 0.0, 0.0, 0.0
        delta_time = 0
        match sdl_event.type:
            case sdl3.SDL_EVENT_GAMEPAD_BUTTON_DOWN | sdl3.SDL_EVENT_GAMEPAD_BUTTON_UP:
                button_event = sdl_event.gbutton
                timestamp = int(button_event.timestamp)
                enum_val = SDLButtonSource(int(button_event.button))
                button_name = enum_val.name
                self.logger.info(
                    f"{button_name} {'pressed' if button_event.down else 'released'}"
                )
                target_enum = self.mapping.mapping.get(enum_val)
                if self.mapping._valid_for_combo(enum_val):
                    if button_event.down:
                        self.combo_sources[enum_val] = timestamp
                    else:
                        if enum_val in self.combo_sources:
                            self.combo_sources.pop(enum_val)
                if target_enum:
                    self.send_value(button_event.down, target_enum)
            case sdl3.SDL_EVENT_GAMEPAD_AXIS_MOTION:
                axis_event = sdl_event.gaxis
                axis_id = axis_event.axis
                enum_val = SingleAxisSource(axis_id)
                target_enum = self.mapping.mapping.get(enum_val)
                if not target_enum:
                    for double_enum in getPossibleAxisPairs(enum_val):
                        if double_enum in self.mapping.mapping:
                            source_1, source_2 = double_enum.value
                            target_1, target_2 = self.mapping.mapping[double_enum].value
                            target_enum = target_1 if enum_val == source_1 else target_2
                if target_enum:
                    self.send_value(axis_event.value / 32768.0, target_enum)
            case sdl3.SDL_EVENT_GAMEPAD_SENSOR_UPDATE:
                sensor_event = sdl_event.gsensor
                sensor_type = sensor_event.sensor
                if sensor_type == sdl3.SDL_SENSOR_GYRO:
                    gyro_x, gyro_y, gyro_z = sensor_event.data  # pitch/yaw/roll
                    timestamp = sensor_event.sensor_timestamp
                    if self.last_gyro_timestamp == None:
                        self.last_gyro_timestamp = timestamp
                    delta_time = (
                        timestamp - self.last_gyro_timestamp
                    ) / 1000000.0  # convert to seconds
                    self.last_gyro_timestamp = timestamp
                if sensor_type == sdl3.SDL_SENSOR_ACCEL:
                    accel_x, accel_y, accel_z = sensor_event.data  # pitch/yaw/roll
                    timestamp = sensor_event.sensor_timestamp
                    if self.last_accel_timestamp == None:
                        self.last_accel_timestamp = timestamp
                    delta_time = (
                        timestamp - self.last_accel_timestamp
                    ) / 1000000.0  # convert to seconds
                    self.last_accel_timestamp = timestamp
                ##
                gyro_vec = Vec3(gyro_x, gyro_y, gyro_z)
                accel_vec = Vec3(accel_x, accel_y, accel_z)
                sensor_fusion_gravity(self.gravity, gyro_vec, accel_vec, delta_time)
                currentMouseX, currentMouseY = pyautogui.position()
                camera_vel = gyro_camera_player(
                    gyro_vec, self.gravity.normalized(), delta_time, gyro_sens=1
                )
                
                camera_vel += self.leftover_vel
                vel_x, vel_y = int(camera_vel.x), int(camera_vel.y)
                self.leftover_vel.x, self.leftover_vel.y = camera_vel.x - vel_x, camera_vel.y - vel_y
                pyautogui.moveTo(currentMouseX - vel_x, currentMouseY - vel_y)

    def update(self):
        self.vpad.update()


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
        self.sdl_joysticks = {}

    def on_focus_change(self, exe_name, window_title):
        self.logger.debug(f"window changed to: {window_title} ({exe_name})")

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
            sdl3.SDL_UpdateGamepads()
            for pypad in self.pyropads.values():
                pypad.update()
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
