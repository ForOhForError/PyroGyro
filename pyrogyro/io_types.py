import collections.abc
import enum
import logging
import types
import typing

import sdl3
from pyautogui import KEYBOARD_KEYS, MIDDLE, PRIMARY, SECONDARY
from pydantic import BaseModel, BeforeValidator, PlainSerializer
from vgamepad import DS4_BUTTONS, XUSB_BUTTON

from pyrogyro.math import *

EnumNameSerializer = PlainSerializer(
    lambda e: e.name, return_type="str", when_used="always"
)


def enum_or_by_name(T):
    def constructed_by_object_or_name(v: str | T) -> T:
        if isinstance(v, T):
            return v
        try:
            return T[v]
        except (KeyError, TypeError):
            raise ValueError("invalid value")

    return typing.Annotated[
        T, EnumNameSerializer, BeforeValidator(constructed_by_object_or_name)
    ]


KeyboardKeyTarget = enum.Enum(
    "KeyboardKeyTarget", {key.upper(): key for key in KEYBOARD_KEYS}
)


class ButtonTarget(enum.Enum):
    X_A = XUSB_BUTTON.XUSB_GAMEPAD_A
    X_B = XUSB_BUTTON.XUSB_GAMEPAD_B
    X_X = XUSB_BUTTON.XUSB_GAMEPAD_X
    X_Y = XUSB_BUTTON.XUSB_GAMEPAD_Y
    X_DOWN = XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN
    X_LEFT = XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT
    X_RIGHT = XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT
    X_UP = XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP
    X_L1 = XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER
    X_L3 = XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB
    X_R1 = XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER
    X_R3 = XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB
    X_START = XUSB_BUTTON.XUSB_GAMEPAD_START
    X_BACK = XUSB_BUTTON.XUSB_GAMEPAD_BACK
    X_GUIDE = XUSB_BUTTON.XUSB_GAMEPAD_GUIDE


class MouseTarget(enum.Enum):
    MOUSE = "MOUSE"


class MouseButtonTarget(enum.Enum):
    LMOUSE = PRIMARY
    RMOUSE = SECONDARY
    MMOUSE = MIDDLE


class SDLButtonSource(enum.Enum):
    INVALID = sdl3.SDL_GAMEPAD_BUTTON_INVALID
    S = sdl3.SDL_GAMEPAD_BUTTON_SOUTH
    E = sdl3.SDL_GAMEPAD_BUTTON_EAST
    W = sdl3.SDL_GAMEPAD_BUTTON_WEST
    N = sdl3.SDL_GAMEPAD_BUTTON_NORTH
    BACK = sdl3.SDL_GAMEPAD_BUTTON_BACK
    GUIDE = sdl3.SDL_GAMEPAD_BUTTON_GUIDE
    START = sdl3.SDL_GAMEPAD_BUTTON_START
    L3 = sdl3.SDL_GAMEPAD_BUTTON_LEFT_STICK
    R3 = sdl3.SDL_GAMEPAD_BUTTON_RIGHT_STICK
    L1 = sdl3.SDL_GAMEPAD_BUTTON_LEFT_SHOULDER
    R1 = sdl3.SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER
    UP = sdl3.SDL_GAMEPAD_BUTTON_DPAD_UP
    DOWN = sdl3.SDL_GAMEPAD_BUTTON_DPAD_DOWN
    LEFT = sdl3.SDL_GAMEPAD_BUTTON_DPAD_LEFT
    RIGHT = sdl3.SDL_GAMEPAD_BUTTON_DPAD_RIGHT
    M1 = sdl3.SDL_GAMEPAD_BUTTON_MISC1
    RP1 = sdl3.SDL_GAMEPAD_BUTTON_RIGHT_PADDLE1
    LP1 = sdl3.SDL_GAMEPAD_BUTTON_LEFT_PADDLE1
    RP2 = sdl3.SDL_GAMEPAD_BUTTON_RIGHT_PADDLE2
    LP2 = sdl3.SDL_GAMEPAD_BUTTON_LEFT_PADDLE2
    TOUCHPAD = sdl3.SDL_GAMEPAD_BUTTON_TOUCHPAD
    M2 = sdl3.SDL_GAMEPAD_BUTTON_MISC2
    M3 = sdl3.SDL_GAMEPAD_BUTTON_MISC3
    M4 = sdl3.SDL_GAMEPAD_BUTTON_MISC4
    M5 = sdl3.SDL_GAMEPAD_BUTTON_MISC5
    M6 = sdl3.SDL_GAMEPAD_BUTTON_MISC6
    COUNT = sdl3.SDL_GAMEPAD_BUTTON_COUNT


class SingleAxisSource(enum.Enum):
    LSTICK_X = sdl3.SDL_GAMEPAD_AXIS_LEFTX
    LSTICK_Y = sdl3.SDL_GAMEPAD_AXIS_LEFTY
    RSTICK_X = sdl3.SDL_GAMEPAD_AXIS_RIGHTX
    RSTICK_Y = sdl3.SDL_GAMEPAD_AXIS_RIGHTY
    L2 = sdl3.SDL_GAMEPAD_AXIS_LEFT_TRIGGER
    R2 = sdl3.SDL_GAMEPAD_AXIS_RIGHT_TRIGGER


class DoubleAxisSource(enum.Enum):
    LSTICK = (SingleAxisSource.LSTICK_X, SingleAxisSource.LSTICK_Y)
    RSTICK = (SingleAxisSource.RSTICK_X, SingleAxisSource.RSTICK_Y)

    def get_other_axis(self, axis_enum):
        if axis_enum == self.value[0]:
            return self.value[1]
        elif axis_enum == self.value[1]:
            return self.value[0]
        return None


class SingleAxisTarget(enum.Enum):
    X_L2 = "X_L2"
    X_R2 = "X_R2"
    X_LSTICK_X = "X_LSTICK_X"
    X_LSTICK_Y = "X_LSTICK_Y"
    X_RSTICK_X = "X_RSTICK_X"
    X_RSTICK_Y = "X_RSTICK_Y"


class DoubleAxisTarget(enum.Enum):
    X_LSTICK = (
        SingleAxisTarget.X_LSTICK_X,
        SingleAxisTarget.X_LSTICK_Y,
    )
    X_RSTICK = (
        SingleAxisTarget.X_RSTICK_X,
        SingleAxisTarget.X_RSTICK_Y,
    )


class GyroSource(enum.Enum):
    GYRO = "GYRO"


Vec2Source = typing.Union[enum_or_by_name(DoubleAxisSource), GyroSource]
FloatSource = typing.Union[enum_or_by_name(SingleAxisSource)]
BinarySource = typing.Union[enum_or_by_name(SDLButtonSource)]


def get_double_source_for_axis(single_axis_source):
    for double_axis_enum in DoubleAxisSource:
        if single_axis_source in double_axis_enum.value:
            return double_axis_enum
    return None


MapDirectSource = typing.Union[Vec2Source, FloatSource, BinarySource]

MapDirectTarget = typing.Union[
    enum_or_by_name(KeyboardKeyTarget),
    enum_or_by_name(ButtonTarget),
    enum_or_by_name(SingleAxisTarget),
    enum_or_by_name(DoubleAxisTarget),
    enum_or_by_name(MouseButtonTarget),
    enum_or_by_name(MouseTarget),
    None,
]
MapDirectTargetTypes = (
    KeyboardKeyTarget,
    ButtonTarget,
    SingleAxisTarget,
    DoubleAxisTarget,
    MouseButtonTarget,
    MouseTarget,
    types.NoneType,
)


class MapComplexTarget(BaseModel):
    output: MapDirectTarget
    on: str

    def __hash__(self):
        return hash((self.output, self.on))


class AsDpad(BaseModel):
    map_as: typing.Literal["DPAD"] = "DPAD"
    UP: typing.Optional["MapTarget"] = None
    RIGHT: typing.Optional["MapTarget"] = None
    DOWN: typing.Optional["MapTarget"] = None
    LEFT: typing.Optional["MapTarget"] = None

    def map_to_outputs(self, input_value):
        outputs = {}
        if isinstance(input_value, Vec2):
            length = input_value.length()
            if length > 0.1:
                angle = input_value.angle()
                if self.UP:
                    outputs[self.UP] = (angle >= 310 and angle <= 360) or (
                        angle >= 0 and angle <= 50
                    )
                if self.LEFT:
                    outputs[self.LEFT] = angle >= 40 and angle <= 140
                if self.DOWN:
                    outputs[self.DOWN] = angle >= 130 and angle <= 230
                if self.RIGHT:
                    outputs[self.RIGHT] = angle >= 220 and angle <= 320
            else:
                for out in (self.UP, self.RIGHT, self.DOWN, self.LEFT):
                    if out:
                        outputs[out] = False
        return outputs


MapTarget = typing.Union[MapDirectTarget, MapComplexTarget, AsDpad]
MapSource = typing.Union[MapDirectSource, typing.Sequence[MapDirectSource]]


def to_float(in_val):
    if isinstance(in_val, bool):
        return 1.0 if in_val else 0.0
    return float(in_val)


def to_bool(in_val):
    if isinstance(in_val, float):
        return True if abs(in_val) >= 0.01 else False
    return bool(in_val)
