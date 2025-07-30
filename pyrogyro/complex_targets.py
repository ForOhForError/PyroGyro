from pyrogyro.io_types import ComplexTargetBase, BasicMappingOrListOfMappings, to_bool, MapDirectTarget, MapTarget, register_map_target
from pyrogyro.math import Vec2
import typing

ZERO_VEC2 = Vec2()

def resolve_outputs(*args, **kwargs):
    return {}

# class MapComplexTarget(ComplexTargetBase):
#     output: MapDirectTarget
#     on: str

#     def __hash__(self):
#         return hash((self.output, self.on))

# class AndTarget(ComplexTargetBase):
#     AND: BasicMappingOrListOfMappings

#     def map_to_outputs(self, input_value, **kwargs):
#         print(dir(self))
#         if to_bool(input_value):
#             return resolve_outputs({}, self.AND, input_value, **kwargs)
#         else:
#             return {}


class AsAim(ComplexTargetBase):
    map_as: typing.Literal["AIM"]
    o: MapTarget
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
        **kwargs,
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
            **kwargs,
        )


class AsDpad(ComplexTargetBase):
    map_as: typing.Literal["DPAD"]
    UP: typing.Optional[MapTarget] = None
    RIGHT: typing.Optional[MapTarget] = None
    DOWN: typing.Optional[MapTarget] = None
    LEFT: typing.Optional[MapTarget] = None

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
                        **kwargs,
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


class AsGridSticks(ComplexTargetBase):
    map_as: typing.Literal["GRID_STICKS"]
    pad_fingers: typing.Optional[
        typing.Mapping[int, typing.Mapping[int, MapTarget]]
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

def register_complex_targets():
    for typ in [AsGridSticks, AsAim, AsDpad]:
        register_map_target(typ)