import dataclasses
import enum
import time

from string import ascii_uppercase

from pyrogyro.io_types import *
from pyrogyro.math import *

from pyrogyro.config_blocks import ConfigBlock, PyroGyroBaseModel


class Chord(ConfigBlock):
    @dataclass
    class Inputs(PyroGyroBaseModel):
        CHORD: float = 0
        IN: float = 0

    @dataclass
    class Outputs(PyroGyroBaseModel):
        CHORD: float = 0
        NORMAL: float = 0

    def process(self, delta_time: float = 0):
        if self.inputs.CHORD:
            self.outputs.CHORD = self.inputs.IN
            self.outputs.NORMAL = 0
        else:
            self.outputs.NORMAL = self.inputs.IN
            self.outputs.CHORD = 0


class Simulpress(ConfigBlock):
    class State(enum.Enum):
        UNPRESSED = 0
        PARTIAL = 1
        LOCKED_OUT = 2
        PRESSED = 3

    @dataclass
    class Inputs(PyroGyroBaseModel):
        A: float = 0
        B: float = 0

    @dataclass
    class Outputs(PyroGyroBaseModel):
        OUT: float = 0

    @dataclass
    class Config(PyroGyroBaseModel):
        button_count: int = 2
        window_ms: int = 20

    def post_init(self, *args, **kwargs):
        self._state = Simulpress.State.UNPRESSED
        self._deadline_ns = 0

    def post_config(self, *args, **kwargs):
        self.config.button_count = clamp(self.config.button_count, 26, 0)
        self.Inputs = dataclasses.make_dataclass(
            "Inputs",
            [
                (ascii_uppercase[ix], float, dataclasses.field(default=0))
                for ix in range(self.config.button_count)
            ],
            bases=(PyroGyroBaseModel,),
        )
        self.Outputs = dataclasses.make_dataclass(
            "Outputs",
            [
                (ascii_uppercase[ix], float, dataclasses.field(default=0))
                for ix in range(self.config.button_count)
            ]
            + [("OUT", float, dataclasses.field(default=0))],
            bases=(PyroGyroBaseModel,),
        )

    def process(self, delta_time: float = 0):
        pressed_arr = [
            self.get_input(ascii_uppercase[ix])
            for ix in range(self.config.button_count)
        ]
        match self._state:
            case Simulpress.State.UNPRESSED:
                if all(pressed_arr):
                    self._state = Simulpress.State.PRESSED
                    self.set_output("OUT", 1)
                elif any(pressed_arr):
                    self._state = Simulpress.State.PARTIAL
                    self._deadline_ns = time.time_ns() + (
                        self.config.window_ms * 1000000
                    )
            case Simulpress.State.PARTIAL:
                now = time.time_ns()
                if now >= self._deadline_ns:
                    self._state = Simulpress.State.LOCKED_OUT
                else:
                    if all(pressed_arr):
                        self._state = Simulpress.State.PRESSED
                        self.set_output("OUT", 1)
            case Simulpress.State.LOCKED_OUT:
                if not any(pressed_arr):
                    self._state = Simulpress.State.UNPRESSED
            case Simulpress.State.PRESSED:
                if not any(pressed_arr):
                    self._state = Simulpress.State.UNPRESSED
                    self.set_output("OUT", 0)
        if self._state == Simulpress.State.LOCKED_OUT:
            for ix in range(self.config.button_count):
                self.set_output(
                    ascii_uppercase[ix], self.get_input(ascii_uppercase[ix])
                )
        else:
            for ix in range(self.config.button_count):
                self.set_output(ascii_uppercase[ix], 0)


class Multiplier(ConfigBlock):
    @dataclass
    class Inputs(PyroGyroBaseModel):
        IN: Vec2 | Vec3 | float = dataclasses.field(default_factory=Vec2)

    @dataclass
    class Outputs(PyroGyroBaseModel):
        OUT: Vec2 | Vec3 | float = dataclasses.field(default_factory=Vec2)

    @dataclass
    class Config(PyroGyroBaseModel):
        factor: float = 1

    def process(self, delta_time: float = 0):
        try:
            val = self.inputs.IN
            val = val * self.config.factor
            self.set_output("OUT", val)
        except Exception:
            pass


def register_blocks():
    ConfigBlock.register_block_class("MULT", Multiplier)
    ConfigBlock.register_block_class("SIMULPRESS", Simulpress)
    ConfigBlock.register_block_class("CHORD", Chord)
