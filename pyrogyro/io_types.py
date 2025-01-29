import collections.abc
import enum
import logging
import typing

import sdl3
from pyautogui import KEYBOARD_KEYS, MIDDLE, PRIMARY, SECONDARY
from pydantic import BaseModel, BeforeValidator, PlainSerializer
from vgamepad import XUSB_BUTTON

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


class MouseTarget(enum.Enum):
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


class SingleAxisTarget(enum.Enum):
    XUSB_GAMEPAD_L2 = "XUSB_GAMEPAD_L2"
    XUSB_GAMEPAD_R2 = "XUSB_GAMEPAD_R2"
    XUSB_GAMEPAD_LSTICK_X = "XUSB_GAMEPAD_LSTICK_X"
    XUSB_GAMEPAD_LSTICK_Y = "XUSB_GAMEPAD_LSTICK_Y"
    XUSB_GAMEPAD_RSTICK_X = "XUSB_GAMEPAD_RSTICK_X"
    XUSB_GAMEPAD_RSTICK_Y = "XUSB_GAMEPAD_RSTICK_Y"


class DoubleAxisTarget(enum.Enum):
    XUSB_GAMEPAD_LSTICK = (
        SingleAxisTarget.XUSB_GAMEPAD_LSTICK_X,
        SingleAxisTarget.XUSB_GAMEPAD_LSTICK_Y,
    )
    XUSB_GAMEPAD_RSTICK = (
        SingleAxisTarget.XUSB_GAMEPAD_RSTICK_X,
        SingleAxisTarget.XUSB_GAMEPAD_RSTICK_Y,
    )


def getPossibleAxisPairs(singleAxisSource):
    matches = []
    for doubleAxisEnum in DoubleAxisSource:
        if singleAxisSource in doubleAxisEnum.value:
            matches.append(doubleAxisEnum)
    return matches


MapDirectSource = typing.Union[
    enum_or_by_name(DoubleAxisSource),
    enum_or_by_name(SingleAxisSource),
    enum_or_by_name(SDLButtonSource),
]
MapDirectTarget = typing.Union[
    enum_or_by_name(KeyboardKeyTarget),
    enum_or_by_name(XUSB_BUTTON),
    enum_or_by_name(SingleAxisTarget),
    enum_or_by_name(DoubleAxisTarget),
    enum_or_by_name(MouseTarget),
    None,
]


class MapComplexTarget(BaseModel):
    output: MapDirectTarget
    on: str

    def __hash__(self):
        return hash((self.output, self.on))


MapTarget = typing.Union[MapDirectTarget, MapComplexTarget]
MapSource = typing.Union[MapDirectSource, typing.Sequence[MapDirectSource]]


def to_float(in_val):
    if isinstance(in_val, bool):
        return 1.0 if in_val else 0.0
    return float(in_val)


def to_bool(in_val):
    if isinstance(in_val, float):
        return True if abs(in_val) >= 0.01 else False
    return bool(in_val)
