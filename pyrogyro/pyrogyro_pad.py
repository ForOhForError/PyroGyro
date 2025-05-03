import colorsys
import enum
import logging
import re
import typing
import uuid
from dataclasses import dataclass, field

import sdl3
import vgamepad as vg

import pyrogyro
from pyrogyro.constants import DEFAULT_POLL_RATE
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
from pyrogyro.web import WebServer

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
    _preserved: typing.Set[MapDirectSource] = field(default_factory=set)

    def put_input(
        self, source: MapDirectSource, value: typing.Union[Vec2, float, bool]
    ):
        self._inputs[source] = value
        self._changed.add(source)

    def get_inputs(self):
        out = {}
        for key in self._changed:
            val = self._inputs[key]
            out[key] = val
        return out

    def set_preserved(self, source: MapDirectSource, preserved: bool):
        if preserved:
            if source not in self._preserved:
                self._preserved.add(source)
        else:
            if source in self._preserved:
                self._preserved.remove(source)

    def clear(self):
        self._changed.clear()
        self._changed |= self._preserved


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
    def __init__(
        self,
        sdl_joystick,
        mapping: Mapping | None = None,
        web_server: WebServer | None = None,
        parent: typing.Union["PyroGyroMapper", None] = None,
    ):
        self.parent = parent
        self.logger = logging.getLogger("PyroGyroPad")
        if not mapping:
            mapping = Mapping()
        self.mapping = mapping
        self.web_server = web_server
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
        self.mkb_state = {}

        self.delta_time = 0
        self.gyro_update = False
        self.last_gyro_time = 0

        self.combo_sources = {}
        self.combo_presses_active = set()
        self.gravity = Vec3()
        self.gyro_vec = Vec3()
        self.accel_vec = Vec3()
        self.leftover_vel = Vec2()
        self.paired_axis_event_sink = {}

        self.touchpad_state = {}
        self.touchpad_update = False

    @property
    def poll_rate(self):
        return self.parent.poll_rate if self.parent else DEFAULT_POLL_RATE

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
                target_enum.down()
            else:
                target_enum.up()
        elif isinstance(target_enum, KeyboardKeyTarget) and old_value != target_value:
            if target_value:
                target_enum.down()
            else:
                target_enum.up()
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
        if new_mapping and (new_mapping != self.mapping):
            self.logger.info(
                f"Applying mapping '{new_mapping.name}' to PyroGyro pad for controller '{controller_name}'"
            )
            self.mapping = new_mapping
            self.mapping.reset()

    def set_gyro_calibrating(self, calibrating: bool):
        self.gyro_calibrating = calibrating
        if calibrating:
            self.gyro_calibration.reset()

    def send_value(self, source_value, target, source=None):
        match type(target):
            case pyrogyro.io_types.DoubleAxisTarget:
                if isinstance(source_value, Vec2):
                    match target:
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
                match target:
                    case SingleAxisTarget.X_L2:
                        self.vpad.left_trigger_float(float_val)
                    case SingleAxisTarget.X_R2:
                        self.vpad.right_trigger_float(float_val)
            case pyrogyro.io_types.ButtonTarget:
                if to_bool(source_value):
                    self.vpad.press_button(target.value)
                else:
                    self.vpad.release_button(target.value)
            case pyrogyro.io_types.KeyboardKeyTarget:
                self.set_mkb_bool_state(target, to_bool(source_value))
            case pyrogyro.io_types.MouseButtonTarget:
                self.set_mkb_bool_state(target, to_bool(source_value))
            case pyrogyro.io_types.MouseTarget:
                if isinstance(source_value, Vec2):
                    target.move_mouse(
                        source_value.x,
                        source_value.y,
                    )
            case pyrogyro.io_types.LayerTarget:
                self.mapping.set_layer_activation(target.layer, bool(source_value))

    def on_poll_start(self):
        self.gyro_vec.set_value(0, 0, 0)
        self.accel_vec.set_value(0, 0, 0)
        self.delta_time = 0.0
        self.gyro_update = False
        self.touchpad_update = False

    def send_to_web_server(self, event, value):
        remap = {"l3": "lstick", "r3": "rstick"}
        if isinstance(value, bool) or isinstance(value, float):
            value = to_float(value)
            source = event.name.lower()
            source = remap.get(source, source)

            if self.web_server:
                self.web_server.send_message(
                    {"source": source, "type": "float", "value": value}
                )
        elif isinstance(value, Vec2):
            if event != GyroSource.GYRO:
                source = event.name.lower()
                source = remap.get(source, source)

                if self.web_server:
                    self.web_server.send_message(
                        {"source": source, "type": "vec2", "x": value.x, "y": value.y}
                    )

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
                    self.gyro_update = True
                    gyro_raw.set_value(*sensor_event.data)
                    # SDL3 outputs gyro in radians per second
                    gyro_raw *= RADIANS_TO_DEGREES
                    if self.last_gyro_time == None:
                        self.last_gyro_time = timestamp
                    self.delta_time += (timestamp - self.last_gyro_time) / 1000000000.0
                    self.last_gyro_time = timestamp
                if sensor_type == sdl3.SDL_SENSOR_ACCEL:
                    accel.set_value(*sensor_event.data)
                if self.gyro_calibrating:
                    self.gyro_calibration.update(gyro_raw)
                    self.gyro_update = False
                else:
                    self.gyro_vec += gyro_raw
                    self.accel_vec += accel
            case evt_type if evt_type in (
                sdl3.SDL_EVENT_GAMEPAD_TOUCHPAD_DOWN,
                sdl3.SDL_EVENT_GAMEPAD_TOUCHPAD_MOTION,
                sdl3.SDL_EVENT_GAMEPAD_TOUCHPAD_UP,
            ):
                self.touchpad_update = True
                touch_event = sdl_event.gtouchpad
                pad_id = touch_event.touchpad
                finger_id = touch_event.finger
                key_tuple = (pad_id, finger_id)
                if sdl_event.type == sdl3.SDL_EVENT_GAMEPAD_TOUCHPAD_UP:
                    if key_tuple in self.touchpad_state:
                        self.touchpad_state.pop(key_tuple)
                else:
                    x, y, pressure = touch_event.x, touch_event.y, touch_event.pressure
                    self.touchpad_state[key_tuple] = Vec2(x, y)

    def send_changed_input_values(self, delta_time: float = 0.0):
        changed_inputs = self.input_store.get_inputs()
        for source in changed_inputs:
            value = changed_inputs.get(source)
            target_raw = self.mapping.map.get(source)
            for target in (
                target_raw if isinstance(target_raw, typing.Sequence) else (target_raw,)
            ):
                if target:
                    if isinstance(target, InputPreserver):
                        self.input_store.set_preserved(
                            source, target.preserve_input(value)
                        )
                    if type(target) in MapDirectTargetTypes:
                        self.send_value(value, target, source=source)
                    else:
                        complex_output_dict = resolve_outputs(
                            dict(),
                            target,
                            value,
                            delta_time=delta_time,
                            real_world_calibration=self.mapping.get_real_world_calibration(),
                            in_game_sens=self.mapping.get_in_game_sens(),
                            os_mouse_speed=self.mapping.get_os_mouse_speed_correction(),
                        )
                        for mapped_output_key in complex_output_dict:
                            self.send_value(
                                complex_output_dict[mapped_output_key],
                                mapped_output_key,
                                source=source,
                            )
            self.send_to_web_server(source, value)
        self.input_store.clear()

    def update(self, time_now: float):
        delta_max = 5 / self.poll_rate
        if not self.last_timestamp:
            self.last_timestamp = time_now
        delta_time = time_now - self.last_timestamp
        if delta_time > delta_max:
            self.logger.debug(f"got delayed update clocking at {delta_time}")
            delta_time = 0
        self.led.update(time_now)
        color = self.led.get_rgb_color()
        color_r, color_g, color_b = (
            int(color.x * 255),
            int(color.y * 255),
            int(color.z * 255),
        )
        sdl3.SDL_SetGamepadLED(self.sdl_pad, color_r, color_g, color_b)
        if self.gyro_update:
            self.gyro_vec = self.gyro_calibration.calibrated(self.gyro_vec)
            adjusted_delta = self.delta_time if self.delta_time <= delta_max else 0
            sensor_fusion_gravity(
                self.gravity, self.gyro_vec, self.accel_vec, adjusted_delta
            )
            pixel_vel = self.mapping.gyro.mode.gyro_pixels(
                self.gyro_vec,
                self.gravity.normalized(),
                adjusted_delta,
                real_world_calibration=self.mapping.get_real_world_calibration(),
                in_game_sens=self.mapping.get_in_game_sens(),
            )
            self.input_store.put_input(GyroSource.GYRO, pixel_vel)
        if self.touchpad_update:
            self.input_store.put_input(TouchSource.TOUCHPAD, self.touchpad_state)
        self.send_changed_input_values(delta_time=delta_time)
        self.vpad.update()
        self.last_timestamp = time_now
