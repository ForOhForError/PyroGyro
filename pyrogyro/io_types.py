import enum
import typing

import sdl3
from pyautogui import KEYBOARD_KEYS, MIDDLE, PRIMARY, SECONDARY

from pyrogyro.math import *
from pyrogyro.platform_util import keyDown, keyUp, mouseDown, mouseUp, move_mouse


class Keynum(enum.Enum):
    def release(self):
        keyUp(self.value)

    def press(self):
        keyDown(self.value)


KeyboardKey: type[enum.Enum] = enum.Enum(
    "KeyboardKeyEnum", {key.upper(): key for key in KEYBOARD_KEYS}, type=Keynum
)  # type: ignore


class MouseTarget(enum.Enum):
    MOUSE = "MOUSE"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._leftover_vel = Vec2()

    def move_mouse(self, x: float, y: float):
        self._leftover_vel.set_value(
            *move_mouse(x, y, self._leftover_vel.x, self._leftover_vel.y)
        )

    def process_input(
        self, event, graph=None, pad: typing.ForwardRef("PyroGyroPad") | None = None
    ):
        if pad:
            if isinstance(event.value, Vec2):
                self.move_mouse(event.value.x, event.value.y)


class MouseButtonTarget(enum.Enum):
    LEFT = PRIMARY
    RIGHT = SECONDARY
    MIDDLE = MIDDLE

    def release(self):
        mouseUp(button=self.value)

    def press(self):
        mouseDown(button=self.value)


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
    TOUCHPAD_PRESS = sdl3.SDL_GAMEPAD_BUTTON_TOUCHPAD
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

    def write_vec(self, vec, value):
        if not isinstance(vec, Vec2):
            vec = Vec2()
        match self:
            case SingleAxisSource.LSTICK_X | SingleAxisSource.RSTICK_X:
                vec.x = value
            case SingleAxisSource.LSTICK_Y | SingleAxisSource.RSTICK_Y:
                vec.y = value
        return vec


class DoubleAxisSource(enum.Enum):
    LSTICK = (SingleAxisSource.LSTICK_X, SingleAxisSource.LSTICK_Y)
    RSTICK = (SingleAxisSource.RSTICK_X, SingleAxisSource.RSTICK_Y)

    @classmethod
    def from_single(cls, axis: SingleAxisSource):
        match axis:
            case SingleAxisSource.LSTICK_X | SingleAxisSource.LSTICK_Y:
                return cls.LSTICK
            case SingleAxisSource.RSTICK_X | SingleAxisSource.RSTICK_Y:
                return cls.RSTICK
        return None

    def get_other_axis(self, axis_enum):
        if axis_enum == self.value[0]:
            return self.value[1]
        elif axis_enum == self.value[1]:
            return self.value[0]
        return None


class GyroSource(enum.Enum):
    GYRO = "GYRO"


class TouchSource(enum.Enum):
    TOUCHPAD = "TOUCHPAD"


def to_vec2(in_val):
    if isinstance(in_val, Vec2):
        return in_val
    else:
        return Vec2()

def to_vec3(in_val):
    if isinstance(in_val, Vec3):
        return in_val
    else:
        return Vec3()

def to_float(in_val):
    if isinstance(in_val, bool):
        return 1.0 if in_val else 0.0
    return float(in_val)


def to_bool(in_val):
    if isinstance(in_val, float):
        return True if abs(in_val) >= 0.01 else False
    return bool(in_val)
