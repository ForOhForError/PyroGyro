import logging
import typing

from pydantic import Field, create_model

from pyrogyro.io_types import *
from pyrogyro.math import *

from pyrogyro.config_blocks import ConfigBlock, PyroGyroBaseModel

class Keyboard(ConfigBlock):
    Inputs = create_model("Inputs",__base__=PyroGyroBaseModel,**{keynum.name: (float|bool, False) for keynum in KeyboardKey})
    def on_press(self, slot: str, slot_input):
        KeyboardKey[slot].press()

    def on_release(self, slot: str, slot_input):
        KeyboardKey[slot].release()

MOUSE_POSITION_SLOTS = ("MOVE", "ABSOLUTE")

class Mouse(ConfigBlock):
    self_managed_inputs = ("MOVE", "SET")
    
    class Inputs(PyroGyroBaseModel):
        MOVE: Vec2 = Field(default_factory=Vec2)
        SET: Vec2 = Field(default_factory=Vec2)
        RIGHT: float|bool = False
        LEFT: float|bool = False
        MIDDLE: float|bool = False
    
    def process(self, delta_time: float = 0):
        x, y = move_mouse(self.inputs.MOVE.x, self.inputs.MOVE.y)
        self.inputs.MOVE.set_value(x, y)

    def on_update(self, slot: str, slot_input):
        if slot_input:
            vec = to_vec2(slot_input)
            match slot:
                case "MOVE":
                    self.inputs.MOVE += vec
                case "ABSOLUTE":
                    self.inputs.SET += vec

    def on_press(self, slot: str, slot_input):
        if slot not in MOUSE_POSITION_SLOTS:
            MouseButtonTarget[slot].press()

    def on_release(self, slot: str, slot_input):
        if slot not in MOUSE_POSITION_SLOTS:
            MouseButtonTarget[slot].release()

def register_blocks():
    ConfigBlock.register_block_class("KEYBOARD", Keyboard)
    ConfigBlock.register_block_class("MOUSE", Mouse)