import logging
import re
import typing

from pydantic import Field, create_model
import sdl3
import vgamepad as vg

from pyrogyro.constants import DEFAULT_POLL_RATE
from pyrogyro.gamepad_motion import GyroCalibration, sensor_fusion_gravity, sensor_fusion_gravity_fancy, GyroData
from pyrogyro.io_types import *
from pyrogyro.math import *

from pyrogyro.config_blocks import ConfigBlock, PyroGyroBaseModel

PAD_OUTPUTS = {
    "GYRO": (GyroData,Field(default_factory=GyroData)),
    "TOUCHPAD_PRESS": (float, 0),
    "PADS": (float, 0),
}
for sdl_button_enum in SDLButtonSource:
    PAD_OUTPUTS[sdl_button_enum.name] = (float|bool, False)
for sdl_axis_enum in SingleAxisSource:
    PAD_OUTPUTS[sdl_axis_enum.name] = (float, 0)
for sdl_double_axis_enum in DoubleAxisSource:
    PAD_OUTPUTS[sdl_double_axis_enum.name] = (Vec2, Field(default_factory=Vec2))

class InputPad(ConfigBlock):
    logger = logging.getLogger("InputPad")
    Outputs = create_model("Outputs",__base__=PyroGyroBaseModel,**PAD_OUTPUTS)
    
    class Inputs(PyroGyroBaseModel):
        RUMBLE: Vec2 = Field(default_factory=Vec2)
        LED: Vec3 = Field(default_factory=Vec3)

    class Config(PyroGyroBaseModel):
        controller_name: str = ".*"
        multi_pad_mode: str = ""
        fancy_gravity: bool = False

    def __del__(self):
        if self.sdl_pad:
            sdl3.SDL_CloseGamepad(self.sdl_pad)

    @classmethod
    def is_source(cls) -> bool:
        return True

    def processable(self) -> bool:
        return True if self.sdl_pad else False

    def post_init(self, *args, **kwargs):
        self.sdl_id: sdl3.SDL_JoystickID | None = None
        self.sdl_pad: sdl3.SDL_POINTER[sdl3.SDL_Gamepad] | None = None
        self.gyro_calibrating = False
        self.gyro_calibration = GyroCalibration()
        self.last_timestamp = None
        self.last_gyro_time = None
        self.delta_time = 0.0
        self.gyro_update = False

    def init_gyro(self):
        gyro_sensors = (
            sdl3.SDL_SENSOR_GYRO,
            sdl3.SDL_SENSOR_GYRO_L,
            sdl3.SDL_SENSOR_GYRO_R,
        )
        accel_sensors = (
            sdl3.SDL_SENSOR_ACCEL,
            sdl3.SDL_SENSOR_ACCEL_L,
            sdl3.SDL_SENSOR_ACCEL_R,
        )
        if self.sdl_pad:
            for gyro_sensor in gyro_sensors:
                if sdl3.SDL_GamepadHasSensor(self.sdl_pad, gyro_sensor): # type: ignore
                    self.logger.info("Gyro Sensor Detected")
                    sdl3.SDL_SetGamepadSensorEnabled(self.sdl_pad, gyro_sensor, True) # type: ignore
            for accel_sensor in accel_sensors:
                if sdl3.SDL_GamepadHasSensor(self.sdl_pad, accel_sensor): # type: ignore
                    self.logger.info("Accel Sensor Detected")
                    sdl3.SDL_SetGamepadSensorEnabled(self.sdl_pad, accel_sensor, True) # type: ignore

    def process(self, delta_time: float = 0):
        if self.gyro_update:
            delta_max = 5 / DEFAULT_POLL_RATE
            if delta_time > delta_max:
                self.logger.debug(f"got delayed update clocking at {delta_time}")
                delta_time = 0
            self.outputs.GYRO.gyro = self.gyro_calibration.calibrated(self.outputs.GYRO.gyro)
            adjusted_delta = delta_time if delta_time <= delta_max else 0
            if self.config.fancy_gravity:
                sensor_fusion_gravity_fancy(
                    self.outputs.GYRO, adjusted_delta
                )
            else:
                sensor_fusion_gravity(
                    self.outputs.GYRO, adjusted_delta
                )
        self.gyro_update = False

    def process_source_end(self, delta_time: float = 0):
        if self.sdl_pad:
            rumble = self.inputs.RUMBLE
            if rumble:
                rumble_vec = to_vec2(rumble)
                sdl3.SDL_RumbleGamepad(
                    self.sdl_pad, int(abs(rumble_vec)), int(abs(rumble_vec.y)), 1000 # type: ignore
                )
            led = self.inputs.LED
            if led:
                color = to_vec3(led)
                color_r, color_g, color_b = (
                    int(color.x * 255),
                    int(color.y * 255),
                    int(color.z * 255),
                )
                sdl3.SDL_SetGamepadLED(self.sdl_pad, color_r, color_g, color_b) # type: ignore

    def poll_start(self):
        self.outputs.GYRO.gyro = Vec3()
        self.outputs.GYRO.accel = Vec3()

    def set_gyro_calibrating(self, calibrating: bool):
        self.gyro_calibrating = calibrating
        if calibrating:
            self.gyro_calibration.reset()

    def handle_event(self, sdl_event):
        gyro_raw = Vec3()
        accel = Vec3()
        match sdl_event.type:
            case sdl3.SDL_EVENT_GAMEPAD_BUTTON_DOWN | sdl3.SDL_EVENT_GAMEPAD_BUTTON_UP:
                button_event = sdl_event.gbutton
                timestamp = int(button_event.timestamp)
                enum_val = SDLButtonSource(int(button_event.button))
                button_name = enum_val.name
                self.set_output(button_name, bool(button_event.down))
                self.logger.info(
                    f"{button_name} {'pressed' if button_event.down else 'released'}"
                )
            case sdl3.SDL_EVENT_GAMEPAD_AXIS_MOTION:
                axis_event = sdl_event.gaxis
                timestamp = int(axis_event.timestamp)
                axis_id = axis_event.axis
                axis = SingleAxisSource(axis_id)
                double_axis = DoubleAxisSource.from_single(axis)
                if double_axis:
                    val = self.get_output(double_axis.name)
                    val = axis.write_vec(val, axis_event.value / 32768.0)
                    self.set_output(double_axis.name, val)
                else:
                    self.set_output(axis.name, axis_event.value / 32768.0)
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
                elif sensor_type == sdl3.SDL_SENSOR_ACCEL:
                    accel.set_value(*sensor_event.data)
                if self.gyro_calibrating:
                    self.gyro_calibration.update(gyro_raw)
                    self.gyro_update = False
                else:
                    self.outputs.GYRO.gyro += gyro_raw
                    self.outputs.GYRO.accel += accel
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
                # if sdl_event.type == sdl3.SDL_EVENT_GAMEPAD_TOUCHPAD_UP:
                #     if key_tuple in self.touchpad_state:
                #         self.touchpad_state.pop(key_tuple)
                # else:
                #     x, y, pressure = touch_event.x, touch_event.y, touch_event.pressure
                #     self.touchpad_state[key_tuple] = Vec3(x, y, pressure)
            case _:
                self.logger.info("event type: " + str(evt_type))

    def claim_pad(self, pad_id_list: list[sdl3.SDL_JoystickID]):
        claimed = set()
        if self.sdl_id in pad_id_list:
            pad_id_list.remove(self.sdl_id)
        else:
            new_pad_id = None
            for pad_id in pad_id_list:
                pad_name_bytes = sdl3.SDL_GetGamepadNameForID(pad_id)
                pad_name = (
                    pad_name_bytes.decode() if pad_name_bytes else "[Name Unknown]"  # type: ignore
                )
                if re.fullmatch(self.controller_name, pad_name):
                    if self.sdl_pad:
                        sdl3.SDL_CloseGamepad(self.sdl_pad)
                    self.sdl_id = pad_id
                    self.sdl_pad = sdl3.SDL_OpenGamepad(pad_id)
                    self.init_gyro()
                    self.logger.info(f"Using Controller '{pad_name}'")
                    claimed.add(pad_id)
                    new_pad_id = pad_id
                    break
            if new_pad_id:
                pad_id_list.remove(new_pad_id)
        return self.sdl_id

    def pre_init(self, *args, **kwargs):
        self.controller_name = ".*"
        self.multi_pad_mode = "duplicate"


ConfigBlock.register_block_class("PAD", InputPad)

XBOX_BUTTON_MAP = {
    "A": vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
    "B": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
    "X": vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
    "Y": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
    "DOWN": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
    "LEFT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
    "RIGHT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
    "UP": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
    "L1": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
    "L3": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
    "R1": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
    "R3": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
    "START": vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
    "BACK": vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
    "GUIDE": vg.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE,
}

XBOX_INPUTS = {
    "L2":(float,0),
    "R2":(float,0),
    "LSTICK":(Vec2,Field(default_factory=Vec2)),
    "RSTICK":(Vec2,Field(default_factory=Vec2)),
}
for button_name in XBOX_BUTTON_MAP:
    XBOX_INPUTS[button_name] = (float|bool, False)

class XboxPad(ConfigBlock):
    Inputs = create_model("Inputs",__base__=PyroGyroBaseModel,**XBOX_INPUTS)
    class Outputs(PyroGyroBaseModel):
        RUMBLE: Vec2 = Field(default_factory=Vec2)

    def post_init(self, *args, **kwargs):
        self.vpad: vg.VX360Gamepad | None = None

    def process(self, delta_time: float = 0):
        if self.vpad:
            for slot in self.input_slots():
                value = self.get_input(slot)
                match slot:
                    case "L2":
                        if value != None:
                            self.vpad.left_trigger_float(to_float(value))
                    case "R2":
                        if value != None:
                            self.vpad.right_trigger_float(to_float(value))
                    case "LSTICK":
                        if value != None:
                            vec_in = to_vec2(value)
                            self.vpad.left_joystick_float(vec_in.x, -vec_in.y)
                    case "RSTICK":
                        if value != None:
                            vec_in = to_vec2(value)
                            self.vpad.right_joystick_float(vec_in.x, -vec_in.y)
                    case _:
                        if to_bool(value):
                            self.vpad.press_button(XBOX_BUTTON_MAP[slot])
                        else:
                            self.vpad.release_button(XBOX_BUTTON_MAP[slot])
            self.vpad.update()

    def on_unload(self):
        if self.vpad:
            self.vpad.unregister_notification()  # type: ignore
            self.vpad = None

    def on_load(self):
        self.vpad = vg.VX360Gamepad()
        self.vpad.register_notification(callback_function=self.virtual_pad_callback)  # type: ignore

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

        vec = self.get_output("RUMBLE")
        if not isinstance(vec, Vec2):
            vec = Vec2()
        vec.set_value(low_frequency_rumble, high_frequency_rumble)


ConfigBlock.register_block_class("XBOX", XboxPad)

# class Activator(ConfigBlock):
#     @classmethod
#     def input_slots(cls) -> typing.List[str]:
#         return ["IN"]

#     @classmethod
#     def output_slots(cls) -> typing.List[str]:
#         return ["OUT"]

# ConfigBlock.register_block_class("ACTIVATOR", Activator)
