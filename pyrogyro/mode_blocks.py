
import logging

from pyrogyro.config_blocks import ConfigBlock, PyroGyroBaseModel
import typing
from pyrogyro.math import *
from pydantic import Field, create_model

ZERO_VEC2 = Vec2()

class StickToMouse(ConfigBlock):
    class Inputs(PyroGyroBaseModel):
        STICK: Vec2 = Field(default_factory=Vec2)
    
    class Outputs(PyroGyroBaseModel):
        MOUSE: Vec2 = Field(default_factory=Vec2)
        
    class Config(PyroGyroBaseModel):
        real_world_calibration: float = 360.0
        in_game_sens: float = 1.0
        sens: typing.Union[float, typing.Tuple[float, float]] = 1.0
        power: float = 1.0
        invert_x: bool = False
        invert_y: bool = False
        accel_rate: float = 0.0
        accel_cap: float = 1000000.0
        deadzone_outer: float = 0.1
        deadzone_inner: float = 0.1

    def post_init(self, *args, **kwargs):
        self._max_output_thresh = 1.0 - self.config.deadzone_outer

    def _interp_input(self, input_vec: Vec2):
        magnitude = (
            input_vec.length() / self._max_output_thresh
            if self._max_output_thresh != 0
            else 1.0
        )
        progress = magnitude**self.config.power
        return Vec2.lerp(ZERO_VEC2, input_vec.normalized(), progress)

    @property
    def sens_vec(self):
        if isinstance(self.config.sens, float) or isinstance(self.config.sens, int):
            return Vec2(self.config.sens, self.config.sens)
        elif isinstance(self.config.sens, tuple):
            return Vec2(*self.config.sens)
        else:
            return Vec2()

    def get_velocity_vec(
        self,
        input_value,
        delta_time,
        os_mouse_speed=1.0,
    ):
        vel_vec = (
            self.sens_vec
            * min(self._accel_mult, self.config.accel_cap)
            * (self.config.real_world_calibration / os_mouse_speed / self.config.in_game_sens)
            * delta_time
        )
        input_value = self._interp_input(input_value)
        vel_vec.set_value(
            vel_vec.x * input_value.x * (-1 if self.config.invert_x else 1),
            vel_vec.y * input_value.y * (-1 if self.config.invert_y else 1),
        )
        return vel_vec
    
    def process(self, delta_time: float = 0):
        if isinstance(self.inputs.STICK, Vec2):
            input_vec:Vec2 = self.inputs.STICK
            magnitude = input_vec.length()
            full_tilt = magnitude >= self._max_output_thresh
            if not full_tilt:
                self._accel_mult = 1.0
            if magnitude >= self.config.deadzone_inner:
                result = self.get_velocity_vec(
                    input_vec,
                    delta_time
                )
                if full_tilt:
                    self._accel_mult = min(
                        self._accel_mult + (delta_time * self.config.accel_rate),
                        self.config.accel_cap,
                    )
            else:
                result = Vec2()
            self.set_output("MOUSE", result)

class StickDpad(ConfigBlock):
    _config_slots = ("deadzone", "divisions", "overlap_degrees")
    
    class Inputs(PyroGyroBaseModel):
        STICK: Vec2 = Field(default_factory=Vec2)
    
    class Outputs(PyroGyroBaseModel):
        UP:float|bool = False
        LEFT:float|bool = False
        DOWN:float|bool = False
        RIGHT:float|bool = False
    
    class Config(PyroGyroBaseModel):
        deadzone:float = 0.3
        divisions:float = 4
        overlap_degrees:float = 15
    
    def post_init(self, *args, **kwargs):
        if self.config.divisions != 4:
            self._outputs = [f"PAD_{(ix+1)}" for ix in range(self.config.divisions)]
            self.Outputs = create_model(
                "Outputs",
                __base__=PyroGyroBaseModel,
                **{out_name: (float|bool, False) for out_name in self._outputs} # type: ignore
            )
        else:
            self._outputs = ["UP","LEFT","DOWN","RIGHT"]
        half_slife_size = 180 / self.config.divisions
        self._bounds = []
        
        for ix in range(self.config.divisions):
            base = (half_slife_size * ix * 2)
            bound_min, bound_max = (base-half_slife_size-self.config.overlap_degrees)%360, (base+half_slife_size+self.config.overlap_degrees)%360
            self._bounds.append((bound_min,bound_max))

    def process(self, delta_time: float = 0):
        if isinstance(self.inputs.STICK, Vec2):
            input_vec:Vec2 = self.inputs.STICK
            length = input_vec.length()
            input_on = length > self.config.deadzone
            angle = input_vec.angle()
            for ix in range(len(self._bounds)):
                bound_min, bound_max = self._bounds[ix]
                output_slot = False
                if bound_min > bound_max:
                    if not (bound_max < angle < bound_min):
                        output_slot = input_on
                elif bound_min <= angle <= bound_max:
                    output_slot = input_on
                self.set_output(self._outputs[ix], output_slot)

def register_blocks():
    ConfigBlock.register_block_class("STICK_TO_MOUSE", StickToMouse)
    ConfigBlock.register_block_class("STICK_DPAD", StickDpad)

class GridSticks(ConfigBlock):
    pass