import collections.abc
import enum
import logging
import time
import types
import typing

import sdl3
from pyautogui import KEYBOARD_KEYS, MIDDLE, PRIMARY, SECONDARY
from pydantic import BaseModel, BeforeValidator, PlainSerializer
from vgamepad import DS4_BUTTONS, XUSB_BUTTON

from pyrogyro.math import *
from pyrogyro.platform_util import keyDown, keyUp, mouseDown, mouseUp, move_mouse

EnumNameSerializer = PlainSerializer(
    lambda e: e.name, return_type="str", when_used="always"
)

COMPLEX_TARGET_CLASSES: typing.List[type] = []


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


class Processable:
    def process_input(self, event, graph=None, pad=None):
        # logging.debug(f"processing {self} - {event}")
        pass

    def handle_tick(self, delta_time: float = 0.0, graph=None, pad=None):
        pass


def ensure_complex_target(value: typing.Any) -> typing.Any:
    for cls in COMPLEX_TARGET_CLASSES:
        try:
            logging.info(f"trying {cls} for {value}")
            return cls.model_validate(value)
        except ValueError as ex:
            logging.debug(f"failed with error: {ex}")
    raise ValueError("Could not parse complex target")


class ComplexTargetBase(Processable, BaseModel):
    pass


ComplexTarget = typing.Annotated[
    ComplexTargetBase, BeforeValidator(ensure_complex_target)
]


class Keynum(Processable, enum.Enum):
    def up(self):
        keyUp(self.value)

    def down(self):
        keyDown(self.value)

    def process_input(self, event, graph=None, pad=None):
        if to_bool(event.value):
            self.down()
        else:
            self.up()


KeyboardKeyTarget = enum.Enum(
    "KeyboardKeyEnum", {key.upper(): key for key in KEYBOARD_KEYS}, type=Keynum
)


class ButtonTarget(Processable, enum.Enum):
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

    def process_input(
        self, event, graph=None, pad: typing.ForwardRef("PyroGyroPad") | None = None
    ):
        if pad:
            if to_bool(event.value):
                logging.info("pressing")
                pad.vpad.press_button(self.value)
            else:
                logging.info("releasing")
                pad.vpad.release_button(self.value)


class MouseTarget(Processable, enum.Enum):
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


class MouseButtonTarget(Processable, enum.Enum):
    LMOUSE = PRIMARY
    RMOUSE = SECONDARY
    MMOUSE = MIDDLE

    def up(self):
        mouseUp(button=self.value)

    def down(self):
        mouseDown(button=self.value)

    def process_input(
        self, event, graph=None, pad: typing.ForwardRef("PyroGyroPad") | None = None
    ):
        if to_bool(event.value):
            self.down()
        else:
            self.up()


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


class DoubleAxisSource(enum.Enum):
    LSTICK = (SingleAxisSource.LSTICK_X, SingleAxisSource.LSTICK_Y)
    RSTICK = (SingleAxisSource.RSTICK_X, SingleAxisSource.RSTICK_Y)

    def get_other_axis(self, axis_enum):
        if axis_enum == self.value[0]:
            return self.value[1]
        elif axis_enum == self.value[1]:
            return self.value[0]
        return None


class SingleAxisTarget(Processable, enum.Enum):
    X_L2 = "X_L2"
    X_R2 = "X_R2"
    X_LSTICK_X = "X_LSTICK_X"
    X_LSTICK_Y = "X_LSTICK_Y"
    X_RSTICK_X = "X_RSTICK_X"
    X_RSTICK_Y = "X_RSTICK_Y"

    def process_input(
        self, event, graph=None, pad: typing.ForwardRef("PyroGyroPad") | None = None
    ):
        float_val = to_float(event.value)
        if pad:
            match self:
                case SingleAxisTarget.X_L2:
                    pad.vpad.left_trigger_float(float_val)
                case SingleAxisTarget.X_R2:
                    pad.vpad.right_trigger_float(float_val)


class DoubleAxisTarget(Processable, enum.Enum):
    X_LSTICK = (
        SingleAxisTarget.X_LSTICK_X,
        SingleAxisTarget.X_LSTICK_Y,
    )
    X_RSTICK = (
        SingleAxisTarget.X_RSTICK_X,
        SingleAxisTarget.X_RSTICK_Y,
    )

    def process_input(
        self, event, graph=None, pad: typing.ForwardRef("PyroGyroPad") | None = None
    ):
        if pad:
            if isinstance(event.value, Vec2):
                match self:
                    case DoubleAxisTarget.X_LSTICK:
                        pad.vpad.left_joystick_float(event.value.x, -event.value.y)
                    case DoubleAxisTarget.X_RSTICK:
                        pad.vpad.right_joystick_float(event.value.x, -event.value.y)


class LayerTarget(BaseModel, Processable):
    map_as: typing.Literal["LAYER"]
    layer: str

    def __hash__(self):
        return hash(self.layer)

    def process_input(
        self, event, graph=None, pad: typing.ForwardRef("PyroGyroPad") | None = None
    ):
        if graph:
            pass


class GyroSource(enum.Enum):
    GYRO = "GYRO"


class TouchSource(enum.Enum):
    TOUCHPAD = "TOUCHPAD"


Vec2Source = typing.Union[enum_or_by_name(DoubleAxisSource), GyroSource]
FloatSource = typing.Union[enum_or_by_name(SingleAxisSource)]
BinarySource = typing.Union[enum_or_by_name(SDLButtonSource)]
DictSource = typing.Union[enum_or_by_name(TouchSource)]


def get_double_source_for_axis(single_axis_source):
    for double_axis_enum in DoubleAxisSource:
        if single_axis_source in double_axis_enum.value:
            return double_axis_enum
    return None


MapDirectSource = typing.Union[Vec2Source, FloatSource, BinarySource, DictSource]
ComboableSource = typing.Union[MapDirectSource]

MapDirectTarget = typing.Union[
    enum_or_by_name(KeyboardKeyTarget),
    enum_or_by_name(ButtonTarget),
    enum_or_by_name(SingleAxisTarget),
    enum_or_by_name(DoubleAxisTarget),
    enum_or_by_name(MouseButtonTarget),
    enum_or_by_name(MouseTarget),
    LayerTarget,
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
    LayerTarget,
)

MapTarget = typing.Union[
    MapDirectTarget,
    ComplexTarget,
]
MapSource = typing.Union[MapDirectSource]


class DetailedMapping(BaseModel):
    input: MapSource
    output: MapTarget


BasicMapping = collections.abc.Mapping[
    MapSource, typing.Union[MapTarget, typing.Sequence[MapTarget]]
]
BasicMappingOrListOfMappings = typing.Union[
    BasicMapping, typing.Sequence[typing.Union[DetailedMapping, BasicMapping]]
]


def register_map_target(target):
    COMPLEX_TARGET_CLASSES.append(target)


def to_float(in_val):
    if isinstance(in_val, bool):
        return 1.0 if in_val else 0.0
    return float(in_val)


def to_bool(in_val):
    if isinstance(in_val, float):
        return True if abs(in_val) >= 0.01 else False
    return bool(in_val)


class EventType(enum.Enum):
    PRESS = enum.auto()
    HOLD = enum.auto()
    UPDATE = enum.auto()
    RELEASE = enum.auto()


class InputEvent:
    def __init__(
        self,
        source: MapSource,
        event_type: EventType,
        value: typing.Any,
        timestamp: int = 0,
    ):
        self.source = source
        self.event_type = event_type
        self.value = value
        self.timestamp = timestamp
        self.deferred_event = False
        self.defer_until: int = 0

    def __repr__(self):
        return f"[InputEvent: {self.source} got {self.event_type} with {self.value}]"

    def defer_event(self, defer_timestamp: int):
        self.deferred_event = True
        self.defer_until = defer_timestamp

    @property
    def is_processable(self, now: int | None = None):
        if not now:
            now = time.monotonic_ns()
        if self.deferred_event:
            return now >= self.defer_until
        else:
            return True
