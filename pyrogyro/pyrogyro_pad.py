import colorsys
import enum
import logging
import re
import typing
import uuid
from dataclasses import dataclass, field

import pyautogui
from pynput import mouse, keyboard
import sdl3
import vgamepad as vg

import pyrogyro
from pyrogyro.gamepad_motion import (
    GyroCalibration,
    gyro_camera_local,
    gyro_camera_local_ow,
    gyro_camera_player_lean,
    gyro_camera_player_turn,
    gyro_camera_world,
    sensor_fusion_gravity,
)
from pyrogyro.io_types import *
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


@dataclass
class InputStore:
    _inputs: typing.Mapping[BinarySource, typing.Union[Vec2, float, bool]] = field(
        default_factory=dict
    )
    _changed: typing.Set[MapDirectSource] = field(default_factory=set)

    def put_input(
        self, source: MapDirectSource, value: typing.Union[Vec2, float, bool]
    ):
        self._inputs[source] = value
        self._changed.add(source)

    def get_inputs(self):
        return {key: self._inputs[key] for key in self._changed}


@dataclass
class LerpableLED:
    current_color: Vec3 = field(default_factory=Vec3)
    color_sequence: typing.Sequence[Vec3] = field(default_factory=list)
    index_start: int = 0
    index_end: int = 0
    start_ts: typing.Optional[int] = None
    duration_per_color: float = 1
    color_space: ColorSpace = ColorSpace.RGB
    instant_loop: bool = False

    def set_sequence(
        self,
        color_sequence: typing.Sequence[Vec3],
        color_space=ColorSpace.RGB,
        duration_per_color=1,
        instant_loop=False,
    ):
        self.instant_loop = instant_loop
        self.color_sequence = color_sequence
        self.color_space = color_space
        self.index_start = 0
        self.duration_per_color = duration_per_color
        if len(self.color_sequence) > 1:
            self.index_end = 1
        else:
            self.index_end = 0
        return self

    def update(self, timestamp):
        if self.start_ts == None:
            self.start_ts = timestamp
        time_delta = timestamp - self.start_ts
        if self.duration_per_color == 0:
            delta = 0
        else:
            delta = time_delta / self.duration_per_color
        start, end = (
            self.color_sequence[self.index_start],
            self.color_sequence[self.index_end],
        )
        self.current_color.set_lerp(start, end, delta)
        if delta >= 1.0:
            self.index_start = self.index_start + 1
            self.index_end = self.index_end + 1
            len_seq = len(self.color_sequence)
            if self.index_start == len_seq - 1 and self.instant_loop:
                self.index_start = 0
                self.index_end = 1 if len_seq > 1 else 0
            else:
                self.index_start = self.index_start % len_seq
                self.index_end = self.index_end % len_seq
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
            ROYGBIV,
            color_space=ColorSpace.HSV,
            duration_per_color=10,
            instant_loop=True,
        )
        self.gyro_calibrating = False
        self.gyro_calibration = GyroCalibration()
        self.last_timestamp = None
        if sdl3.SDL_GamepadHasSensor(self.sdl_pad, sdl3.SDL_SENSOR_GYRO):
            self.logger.info("Gyro Sensor Detected")
            sdl3.SDL_SetGamepadSensorEnabled(self.sdl_pad, sdl3.SDL_SENSOR_GYRO, True)
        if sdl3.SDL_GamepadHasSensor(self.sdl_pad, sdl3.SDL_SENSOR_ACCEL):
            self.logger.info("Accel Sensor Detected")
            sdl3.SDL_SetGamepadSensorEnabled(self.sdl_pad, sdl3.SDL_SENSOR_ACCEL, True)

        self.input_store = InputStore()
        self.mouse_controller = mouse.Controller()
        self.keyboard_controller = keyboard.Controller()
        self.mkb_state = {}

        self.delta_time = 0
        self.last_gyro_time = 0

        self.combo_sources = {}
        self.combo_presses_active = set()
        self.gravity = Vec3()
        self.gyro_vec = Vec3()
        self.accel_vec = Vec3()
        self.leftover_vel = Vec2()
        self.paired_axis_event_sink = {}

    def cleanup(self):
        if self.vpad:
            self.vpad.unregister_notification()
            del self.vpad

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

    def set_mkb_bool_state(self, target_enum, target_value):
        old_value = self.mkb_state.get(target_enum, False)
        if isinstance(target_enum, MouseButtonTarget) and old_value != target_value:
            if target_value:
                self.mouse_controller.press(target_enum.value)
            else:
                self.mouse_controller.release(target_enum.value)
        elif isinstance(target_enum, KeyboardKeyTarget) and old_value != target_value:
            if target_value:
                self.keyboard_controller.press(target_enum.value)
            else:
                self.keyboard_controller.release(target_enum.value)
        self.mkb_state[target_enum] = target_value

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
                potential_mappings.sort(key=Mapping.count_autoload_specificity)
                best_match = potential_mappings[-1]
                final_value = best_match.autoload.count_specificity()
                remaining_mappings = len(
                    [
                        mapping
                        for mapping in potential_mappings
                        if mapping.autoload.count_specificity() == final_value
                    ]
                )
                if remaining_mappings == 1:
                    new_mapping = best_match
        if new_mapping:
            self.logger.info(
                f"Applying mapping '{new_mapping.name}' to PyroGyro pad for controller '{controller_name}'"
            )
            self.mapping = new_mapping

    def set_gyro_calibrating(self, calibrating: bool):
        self.gyro_calibrating = calibrating
        if calibrating:
            self.gyro_calibration.reset()
            self.gyro_calibrating = calibrating

    def send_value(self, source_value, target_enum, source=None):
        match type(target_enum):
            case pyrogyro.io_types.DoubleAxisTarget:
                if isinstance(source_value, Vec2):
                    match target_enum:
                        case DoubleAxisTarget.X_LSTICK:
                            self.vpad.left_joystick_float(
                                source_value.x, -source_value.y
                            )
                        case DoubleAxisTarget.X_RSTICK:
                            self.vpad.right_joystick_float(
                                source_value.x, -source_value.y
                            )
            case pyrogyro.io_types.SingleAxisTarget:
                float_val = to_float(source_value)
                match target_enum:
                    case SingleAxisTarget.X_L2:
                        self.vpad.left_trigger_float(float_val)
                    case SingleAxisTarget.X_R2:
                        self.vpad.right_trigger_float(float_val)
            case pyrogyro.io_types.ButtonTarget:
                if to_bool(source_value):
                    self.vpad.press_button(target_enum.value)
                else:
                    self.vpad.release_button(target_enum.value)
            case pyrogyro.io_types.KeyboardKeyTarget:
                self.set_mkb_bool_state(target_enum, to_bool(source_value))
            case pyrogyro.io_types.MouseButtonTarget:
                self.set_mkb_bool_state(target_enum, to_bool(source_value))
            case pyrogyro.io_types.MouseTarget:
                if isinstance(source_value, Vec2):
                    if source == GyroSource.GYRO:
                        self.move_mouse(
                            source_value.x,
                            source_value.y,
                        )
                    else:
                        self.move_mouse(
                            source_value.x * -3,
                            source_value.y * -3,
                        )

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
        #current_x, current_y = pyautogui.position()
        #pyautogui.moveTo(current_x - int(vel_x), current_y - int(vel_y))
        self.mouse_controller.move(-int(vel_x), -int(vel_y))
        return vel_x % 1, vel_y % 1

    def on_poll_start(self):
        self.gyro_vec.set_value(0, 0, 0)
        self.accel_vec.set_value(0, 0, 0)
        self.delta_time = 0.0

    def handle_event(self, sdl_event):
        gyro_raw = Vec3()
        accel = Vec3()
        match sdl_event.type:
            case sdl3.SDL_EVENT_GAMEPAD_BUTTON_DOWN | sdl3.SDL_EVENT_GAMEPAD_BUTTON_UP:
                button_event = sdl_event.gbutton
                timestamp = int(button_event.timestamp)
                enum_val = SDLButtonSource(int(button_event.button))
                button_name = enum_val.name
                self.logger.info(
                    f"{button_name} {'pressed' if button_event.down else 'released'}"
                )
                self.input_store.put_input(enum_val, button_event.down)
            case sdl3.SDL_EVENT_GAMEPAD_AXIS_MOTION:
                axis_event = sdl_event.gaxis
                axis_id = axis_event.axis
                enum_val = SingleAxisSource(axis_id)
                self.input_store.put_input(enum_val, axis_event.value / 32768.0)

                double_enum = get_double_source_for_axis(enum_val)
                if double_enum:
                    other_axis = double_enum.get_other_axis(enum_val)
                    if other_axis not in self.paired_axis_event_sink:
                        self.paired_axis_event_sink[enum_val] = (
                            axis_event.value / 32768.0
                        )
                    else:
                        self.paired_axis_event_sink[enum_val] = (
                            axis_event.value / 32768.0
                        )
                        this_value = axis_event.value / 32768.0
                        other_value = self.paired_axis_event_sink.get(other_axis)
                        if double_enum.value.index(enum_val) == 0:
                            target_value = Vec2(this_value, other_value)
                        else:
                            target_value = Vec2(other_value, this_value)
                        self.input_store.put_input(double_enum, target_value)
            case sdl3.SDL_EVENT_GAMEPAD_SENSOR_UPDATE:
                sensor_event = sdl_event.gsensor
                sensor_type = sensor_event.sensor
                timestamp = sensor_event.sensor_timestamp
                if sensor_type == sdl3.SDL_SENSOR_GYRO:
                    gyro_raw.set_value(*sensor_event.data)
                    if self.last_gyro_time == None:
                        self.last_gyro_time = timestamp
                    self.delta_time += (timestamp - self.last_gyro_time) / 1000000000.0
                if sensor_type == sdl3.SDL_SENSOR_ACCEL:
                    accel.set_value(*sensor_event.data)
                self.gyro_vec += gyro_raw
                self.accel_vec += accel
                if self.gyro_calibrating:
                    self.gyro_calibration.update(gyro_raw)

    def send_changed_input_values(self):
        changed_inputs = self.input_store.get_inputs()
        for source in changed_inputs:
            target = self.mapping.mapping.get(source)
            if target:
                self.send_value(changed_inputs.get(source), target, source=source)

    def update(self, time_now: float):
        if not self.last_timestamp:
            self.last_timestamp = time_now
        delta_time = time_now - self.last_timestamp
        self.led.update(time_now)
        color = self.led.get_rgb_color()
        color_r, color_g, color_b = (
            int(color.x * 255),
            int(color.y * 255),
            int(color.z * 255),
        )
        sdl3.SDL_SetGamepadLED(self.sdl_pad, color_r, color_g, color_b)
        self.gyro_vec = self.gyro_calibration.calibrated(self.gyro_vec)
        sensor_fusion_gravity(
            self.gravity, self.gyro_vec, self.accel_vec, self.delta_time
        )
        camera_vel = self.mapping.gyro.mode.gyro_camera(
            self.gyro_vec, self.gravity.normalized(), self.delta_time
        )
        self.input_store.put_input(GyroSource.GYRO, camera_vel)
        self.send_changed_input_values()
        self.vpad.update()
        self.last_timestamp = time_now
