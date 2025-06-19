import collections.abc
import enum
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

KeyboardKeyEnum = enum.Enum(
    "KeyboardKeyEnum", {key.upper(): key for key in KEYBOARD_KEYS}
)

class KeyboardKeyTarget(enum.Enum):
    def up(self):
        keyUp(self.value)

    def down(self):
        keyDown(self.value)

KeyboardKeyTarget._member_map_.update(KeyboardKeyEnum._member_map_)


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._leftover_vel = Vec2()

    def move_mouse(self, x: float, y: float):
        self._leftover_vel.set_value(
            *move_mouse(x, y, self._leftover_vel.x, self._leftover_vel.y)
        )


class MouseButtonTarget(enum.Enum):
    LMOUSE = PRIMARY
    RMOUSE = SECONDARY
    MMOUSE = MIDDLE

    def up(self):
        mouseUp(button=self.value)

    def down(self):
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


class LayerTarget(BaseModel):
    map_as: typing.Literal["LAYER"]
    layer: str

    def __hash__(self):
        return hash(self.layer)


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

BasicMapping = collections.abc.Mapping[
    "MapSource", typing.Union["MapTarget", typing.Sequence["MapTarget"]]
]
BasicMappingOrListOfMappings = typing.Union[
    BasicMapping, typing.Sequence[typing.Union["DetailedMapping", BasicMapping]]
]

def resolve_outputs(
    resolve_dict,
    target,
    value,
    delta_time=0.0,
    real_world_calibration=1.0,
    in_game_sens=1.0,
    os_mouse_speed=1.0,
    **kwargs
):
    if type(target) in MapDirectTargetTypes:
        resolve_dict[target] = value
    else:
        rec_updates = target.map_to_outputs(
            value,
            delta_time=delta_time,
            real_world_calibration=real_world_calibration,
            in_game_sens=in_game_sens,
            os_mouse_speed=os_mouse_speed,
        )
        for key in rec_updates:
            resolve_outputs(
                resolve_dict,
                key,
                rec_updates[key],
                real_world_calibration=real_world_calibration,
                in_game_sens=in_game_sens,
                os_mouse_speed=os_mouse_speed,
                **kwargs
            )
    return resolve_dict


class MapComplexTarget(BaseModel):
    output: MapDirectTarget
    on: str

    def __hash__(self):
        return hash((self.output, self.on))


ZERO_VEC2 = Vec2()


class AndTarget(BaseModel):
    AND: BasicMappingOrListOfMappings

    def map_to_outputs(self, input_value, **kwargs):
        print(dir(self))
        if to_bool(input_value):
            return resolve_outputs({}, self.AND, input_value, **kwargs)
        else:
            return {}


class AsAim(BaseModel):
    map_as: typing.Literal["AIM"]
    o: "MapTarget"
    sens: typing.Union[float, typing.Tuple[float, float]] = 360.0
    power: float = 1.0
    invert_x: bool = False
    invert_y: bool = False
    accel_rate: float = 0.0
    accel_cap: float = 1000000.0
    deadzone_outer: float = 0.1
    deadzone_inner: float = 0.1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._accel_mult = 1.0
        self._output_vec = Vec2()
        self._max_output_thresh = 1.0 - self.deadzone_outer

    def _interp_input(self, input_vec: Vec2):
        magnitude = (
            input_vec.length() / self._max_output_thresh
            if self._max_output_thresh != 0
            else 1.0
        )
        progress = magnitude**self.power
        return Vec2.lerp(ZERO_VEC2, input_vec.normalized(), progress)

    @property
    def sens_vec(self):
        if isinstance(self.sens, float) or isinstance(self.sens, int):
            return Vec2(self.sens, self.sens)
        elif isinstance(self.sens, tuple):
            return Vec2(*self.sens)
        else:
            return ZERO_VEC2

    def get_velocity_vec(
        self,
        input_value,
        delta_time,
        real_world_calibration=1.0,
        in_game_sens=1.0,
        os_mouse_speed=1.0,
    ):
        vel_vec = (
            self.sens_vec
            * min(self._accel_mult, self.accel_cap)
            * (real_world_calibration / os_mouse_speed / in_game_sens)
            * delta_time
        )
        input_value = self._interp_input(input_value)
        vel_vec.set_value(
            vel_vec.x * input_value.x * (-1 if self.invert_x else 1),
            vel_vec.y * input_value.y * (-1 if self.invert_y else 1),
        )
        return vel_vec

    def map_to_outputs(
        self,
        input_value,
        delta_time=0.0,
        real_world_calibration=1.0,
        in_game_sens=1.0,
        os_mouse_speed=1.0,
        **kwargs
    ):
        result = ZERO_VEC2
        if isinstance(input_value, Vec2):
            magnitude = input_value.length()
            full_tilt = magnitude >= self._max_output_thresh
            if not full_tilt:
                self._accel_mult = 1.0
            if magnitude >= self.deadzone_inner:
                result = self.get_velocity_vec(
                    input_value,
                    delta_time,
                    real_world_calibration=real_world_calibration,
                    in_game_sens=in_game_sens,
                    os_mouse_speed=os_mouse_speed,
                )
                if full_tilt:
                    self._accel_mult = min(
                        self._accel_mult + (delta_time * self.accel_rate),
                        self.accel_cap,
                    )
        return resolve_outputs(
            {},
            self.o,
            result,
            delta_time=delta_time,
            real_world_calibration=real_world_calibration,
            in_game_sens=in_game_sens,
            os_mouse_speed=os_mouse_speed,
            **kwargs
        )


class AsDpad(BaseModel):
    map_as: typing.Literal["DPAD"]
    UP: typing.Optional["MapTarget"] = None
    RIGHT: typing.Optional["MapTarget"] = None
    DOWN: typing.Optional["MapTarget"] = None
    LEFT: typing.Optional["MapTarget"] = None

    def __hash__(self):
        return hash((self.map_as))

    def map_to_outputs(self, input_value, **kwargs):
        outputs = {}
        if isinstance(input_value, Vec2):
            length = input_value.length()
            if length > 0.1:
                angle = input_value.angle()
                if self.UP:
                    resolve_outputs(
                        outputs,
                        self.UP,
                        (angle >= 310 and angle <= 360) or (angle >= 0 and angle <= 50),
                        **kwargs
                    )
                if self.LEFT:
                    resolve_outputs(
                        outputs, self.LEFT, angle >= 40 and angle <= 140, **kwargs
                    )
                if self.DOWN:
                    resolve_outputs(
                        outputs, self.DOWN, angle >= 130 and angle <= 230, **kwargs
                    )
                if self.RIGHT:
                    resolve_outputs(
                        outputs, self.RIGHT, angle >= 220 and angle <= 320, **kwargs
                    )
            else:
                for out in (self.UP, self.RIGHT, self.DOWN, self.LEFT):
                    if out:
                        outputs[out] = False
        return outputs


class AsGridSticks(BaseModel):
    map_as: typing.Literal["GRID_STICKS"]
    pad_fingers: typing.Optional[
        typing.Mapping[int, typing.Mapping[int, "MapTarget"]]
    ] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._start_points = {}

    def map_to_outputs(self, input_value, **kwargs):
        outputs = {}
        if isinstance(input_value, dict):
            to_remove = set()
            for finger_index in set(self._start_points.keys()):
                if finger_index not in input_value:
                    self._start_points.pop(finger_index)
                    if self.pad_fingers:
                        target = self.pad_fingers.get(finger_index[0], {}).get(
                            finger_index[1]
                        )
                        if target:
                            resolve_outputs(outputs, target, Vec2(0, 0), **kwargs)
            for finger_index in input_value:
                entry = input_value[finger_index]
                if isinstance(entry, Vec2):
                    if finger_index not in self._start_points:
                        self._start_points[finger_index] = entry
                    result = entry - self._start_points[finger_index]
                    if self.pad_fingers:
                        target = self.pad_fingers.get(finger_index[0], {}).get(
                            finger_index[1]
                        )
                        if target:
                            resolve_outputs(outputs, target, result, **kwargs)
        return outputs


MapTarget = typing.Union[
    MapDirectTarget, MapComplexTarget, AsDpad, AsAim, AsGridSticks, AndTarget
]
MapSource = typing.Union[MapDirectSource]


class DetailedMapping(BaseModel):
    input: MapSource
    output: MapTarget


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
    def __init__(self, source:MapSource, event_type:EventType, value: typing.Any, timestamp:int = 0):
        self.source = source
        self.event_type = event_type
        self.value = value
        self.timestamp = timestamp
        self.deferred_event = False
        self.defer_until: int = 0

    def defer_event(self, defer_timestamp:int):
        self.deferred_event = True
        self.defer_until = defer_timestamp
    
    def is_processable(self, now: int|None=None):
        if not now:
            now = time.monotonic_ns()
        if self.deferred_event:
            return now >= self.defer_until
        else:
            return True
