import colorsys
import dataclasses
import enum
import logging
import re
import typing
import uuid

import pyautogui
import sdl3
import vgamepad as vg

from pyrogyro.gamepad_motion import (
    gyro_camera_local,
    gyro_camera_local_ow,
    gyro_camera_player_lean,
    gyro_camera_player_turn,
    gyro_camera_world,
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
from pyrogyro.mapping import AutoloadConfig, Mapping
from pyrogyro.math import *

ROYGBIV = (
    Vec3(x=0, y=1, z=1),
    Vec3(x=1, y=1, z=1),
)


class ColorSpace(enum.Enum):
    RGB = "RGB"
    HSV = "HSV"

    def to_rgb(self, in_color: Vec3):
        match self.value:
            case self.HSV.value:
                rgb = colorsys.hsv_to_rgb(in_color.x, in_color.y, in_color.z)
                return Vec3(x=rgb[0], y=rgb[1], z=rgb[2])
            case self.RGB.value:
                return in_color
        return in_color


@dataclasses.dataclass
class LerpableLED:
    current_color: Vec3 = Vec3
    color_sequence: typing.Sequence[Vec3] = dataclasses.field(default_factory=list)
    index_start: int = 0
    index_end: int = 0
    start_ts: typing.Optional[int] = None
    duration_per_color: float = 1
    color_space: ColorSpace = ColorSpace.RGB

    def set_sequence(
        self,
        color_sequence: typing.Sequence[Vec3],
        color_space=ColorSpace.RGB,
        duration_per_color=1,
    ):
        self.color_sequence = color_sequence
        self.color_space = color_space
        self.index_start = 0
        self.duration_per_color = duration_per_color
        if len(self.color_sequence) > 1:
            self.index_end = 1
        else:
            self.index_end = 0
        return self

    def update(self, timestamp, units_in_second=1000.0):
        if self.start_ts == None:
            self.start_ts = timestamp
        time_delta = (timestamp - self.start_ts) / units_in_second
        if self.duration_per_color == 0:
            delta = 0
        else:
            delta = time_delta / self.duration_per_color
        start, end = (
            self.color_sequence[self.index_start],
            self.color_sequence[self.index_end],
        )
        self.current_color.set_lerp(self.current_color, start, end, delta)
        if delta >= 1.0:
            self.index_start = (self.index_start + 1) % len(self.color_sequence)
            self.index_end = (self.index_end + 1) % len(self.color_sequence)
            self.start_ts = timestamp

    def get_rgb_color(self):
        return self.color_space.to_rgb(self.current_color)


class PyroGyroPad:
    def __init__(self, sdl_joystick, mapping: Mapping | None = None):
        self.logger = logging.getLogger("PyroGyroPad")
        if not mapping:
            mapping = Mapping()
        self.mapping = mapping
        self.vpad = vg.VX360Gamepad()
        self.sdl_pad = sdl3.SDL_OpenGamepad(sdl_joystick)
        self.vpad.register_notification(callback_function=self.virtual_pad_callback)
        self.led = LerpableLED().set_sequence(
            ROYGBIV, color_space=ColorSpace.HSV, duration_per_color=5
        )
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

        self.combo_sources = {}
        self.combo_presses_active = set()
        self.gravity = Vec3()
        self.gyro_vec = Vec3()
        self.accel_vec = Vec3()
        self.leftover_vel = Vec2()

    def virtual_pad_callback(
        self, client, target, large_motor, small_motor, led_number, user_data
    ):
        """
        Callback function triggered at each received state change

        :param client: vigem bus ID
        :param target: vigem device ID
        :param large_motor: integer in [0, 255] representing the state of the large motor
        :param small_motor: integer in [0, 255] representing the state of the small motor
        :param led_number: integer in [0, 255] representing the state of the LED ring
        :param user_data: placeholder, do not use
        """
        low_frequency_rumble = int(large_motor / 255 * 0xFFFF)
        high_frequency_rumble = int(small_motor / 255 * 0xFFFF)
        # we get updates as rumble changes changes, so just set duration to a second
        # and have later updates overwrite that
        sdl3.SDL_RumbleGamepad(
            self.sdl_pad, low_frequency_rumble, high_frequency_rumble, 1000
        )

    @property
    def real_controller_name(self):
        return sdl3.SDL_GetGamepadName(self.sdl_pad).decode()

    @property
    def real_controller_uuid(self):
        joystick_uuid_bytes = sdl3.SDL_GetGamepadGUID(self.sdl_pad).data[0:16]
        joystick_uuid = uuid.UUID(bytes=bytes(joystick_uuid_bytes))
        return joystick_uuid

    def evaluate_autoload_mappings(self, mappings, exe_name, window_title):
        potential_mappings = []
        controller_name = self.real_controller_name
        new_mapping = None
        for mapping in mappings:
            if all(
                (
                    re.fullmatch(
                        mapping.autoload.match_controller_name, controller_name
                    ),
                    re.fullmatch(mapping.autoload.match_window_name, window_title),
                    re.fullmatch(mapping.autoload.match_exe_name, exe_name),
                    mapping != self.mapping,
                )
            ):
                potential_mappings.append(mapping)
        if potential_mappings:
            if len(potential_mappings) == 1:
                new_mapping = potential_mappings[0]
            else:
                potential_mappings.sort(key=AutoloadConfig.count_specificity)
                best_match = potential_mappings[-1]
                final_value = best_match.autoload.count_specificity()
                remaining_mappings = len(
                    [
                        mapping
                        for mapping in potential_mappings
                        if mapping.count_specificity() == final_value
                    ]
                )
                if remaining_mappings == 1:
                    new_mapping = best_match
        if new_mapping:
            self.logger.info(
                f"Applying mapping '{new_mapping.name}' to PyroGyro pad for controller '{controller_name}'"
            )
            self.mapping = new_mapping

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
            case pyrogyro.io_types.MouseButtonTarget:
                if to_bool(source_value):
                    pyautogui.mouseDown(button=target_enum.value)
                else:
                    pyautogui.mouseUp(button=target_enum.value)

    def mouse_calib_mult(
        self,
        real_world_sens: float = 1.0,
        os_mouse_speed: float = 1.0,
        in_game_sens: float = 1.0,
    ):
        if os_mouse_speed == 0:
            return 0
        if in_game_sens == 0:
            return 0
        return real_world_sens / os_mouse_speed / in_game_sens

    def move_mouse(
        self,
        x: float,
        y: float,
        calib_mult: float = 1.0,
        extra_x: float = 0.0,
        extra_y: float = 0.0,
    ):
        vel_x = x + extra_x
        vel_y = y + extra_y
        current_x, current_y = pyautogui.position()
        pyautogui.moveTo(current_x - int(vel_x), current_y - int(vel_y))
        return vel_x % 1, vel_y % 1

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

                self.gyro_vec.x, self.gyro_vec.y, self.gyro_vec.z = (
                    gyro_x,
                    gyro_y,
                    gyro_z,
                )
                self.accel_vec.x, self.accel_vec.y, self.accel_vec.z = (
                    accel_x,
                    accel_y,
                    accel_z,
                )
                sensor_fusion_gravity(
                    self.gravity, self.gyro_vec, self.accel_vec, delta_time
                )
                camera_vel = self.mapping.gyro.mode.gyro_camera(
                    self.gyro_vec, self.gravity.normalized(), delta_time
                )
                self.leftover_vel.x, self.leftover_vel.y = self.move_mouse(
                    camera_vel.x,
                    camera_vel.y,
                    calib_mult=self.mouse_calib_mult(),
                    extra_x=self.leftover_vel.x,
                    extra_y=self.leftover_vel.y,
                )

    def update(self, time_now: float):
        timestamp_ms = int(time_now * 1000)
        self.led.update(timestamp_ms)
        color = self.led.get_rgb_color()
        color_r, color_g, color_b = (
            int(color.x * 255),
            int(color.y * 255),
            int(color.z * 255),
        )
        sdl3.SDL_SetGamepadLED(self.sdl_pad, color_r, color_g, color_b)
        self.vpad.update()
