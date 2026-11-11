
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

def smoothed_float_sample(input_sample:float, samples:list[float], current_sample:int, smooth_window:int):
    samples[current_sample] = input_sample
    average = 0.0
    for sample in samples:
        average += sample
    average /= smooth_window
    return average
 
def tiered_smoothed_rotation(input_rotation:float, threshold1:float, threshold2:float, samples:list[float], current_sample:int, smooth_window:int):
    inputMagnitude = abs(input_rotation)
    directWeight = (inputMagnitude - threshold1) / (threshold2 - threshold1)
    directWeight = clamp(directWeight, 0.0, 1.0)
    return (input_rotation * directWeight) + smoothed_float_sample(input_rotation * (1.0 - directWeight), samples, current_sample, smooth_window)

class FlickStick(ConfigBlock):
    class Inputs(PyroGyroBaseModel):
        STICK: Vec2 = Field(default_factory=Vec2)
    
    class Outputs(PyroGyroBaseModel):
        MOUSE: Vec2 = Field(default_factory=Vec2)
    
    class Config(PyroGyroBaseModel):
        real_world_calibration: float = 360.0
        flick_time: float = 0.1
        deadzone: float = 0.1
        flick_threshold: float = 0.9
        turn_smooth_threshold: float = 0.1
        smooth_window: int = 1
    
    def post_init(self, *args, **kwargs):
        self.flick_progress:float = 0.0
        self.flick_size:float = 0
        self.last_stick:Vec2 = Vec2()
        self.smooth_buffer:list[float] = [0.0 for _ in range(self.config.smooth_window)]
        self.current_sample:int = 0
    
    def process(self, delta_time: float = 0):
        if isinstance(self.inputs.STICK, Vec2):
            stick_vec:Vec2 = self.inputs.STICK
            
            result = 0.0
            last_length = self.last_stick.length()
            length = stick_vec.length()
            
            if length >= self.config.flick_threshold:
                if last_length < self.config.flick_threshold:
                    # Start flick
                    logging.debug("Start flick")
                    self.flick_progress = 0.0
                    self.flick_size = stick_vec.angle()
                else:
                    # Turn
                    stick_angle = stick_vec.angle()
                    last_stick_angle = self.last_stick.angle()
                    delta_angle = wrap(stick_angle-last_stick_angle,-180, 180)
                    self.current_sample = (self.current_sample + 1) % self.config.smooth_window
                    result += tiered_smoothed_rotation(
                        delta_angle, 
                        self.config.turn_smooth_threshold/2, 
                        self.config.turn_smooth_threshold,
                        self.smooth_buffer,
                        self.current_sample,
                        self.config.smooth_window
                    )
            else:
                # Turn cleanup
                if last_length >= self.config.flick_threshold:
                    for i in range(self.config.smooth_window):
                        self.smooth_buffer[i] = 0.0
            
            last_flick_progress = self.flick_progress
            if last_flick_progress < self.config.flick_time:
                self.flick_progress = min(self.flick_progress+delta_time, self.config.flick_time)
                last_norm_progress = last_flick_progress / self.config.flick_time
                this_norm_progress = self.flick_progress / self.config.flick_time
                eased_last_norm = ease_out_norm(last_norm_progress)
                eased_this_norm = ease_out_norm(this_norm_progress)
                logging.debug(f"flick progress: {self.flick_progress}")
                result += (eased_this_norm-eased_last_norm) * self.flick_size
            
            if result:
                logging.debug(f"result: {result}")
            
            self.outputs.MOUSE.x = result * self.config.real_world_calibration
            self.last_stick.set_value(stick_vec.x,stick_vec.y)

class StickDpad(ConfigBlock):
    class Inputs(PyroGyroBaseModel):
        STICK: Vec2 = Field(default_factory=Vec2)
    
    class Outputs(PyroGyroBaseModel):
        UP:float|bool = False
        LEFT:float|bool = False
        DOWN:float|bool = False
        RIGHT:float|bool = False
    
    class Config(PyroGyroBaseModel):
        deadzone:float = 0.3
        divisions:int = 4
        offset_degrees:float = 0
        overlap_degrees:float = 15
    
    def post_config(self, *args, **kwargs):
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
            base = (half_slife_size * ix * 2)+self.config.offset_degrees
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
    ConfigBlock.register_block_class("FLICK_STICK", FlickStick)

class GridSticks(ConfigBlock):
    pass