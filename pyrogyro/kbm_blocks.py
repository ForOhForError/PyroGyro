import logging
import typing

from pyrogyro.io_types import *
from pyrogyro.math import *

from pyrogyro.config_blocks import ConfigBlock, InputValue


class Keyboard(ConfigBlock):
    @classmethod
    def input_slots(cls) -> typing.List[str]:
        return [key.name for key in KeyboardKey]

    def on_press(self, slot: str, slot_input: InputValue):
        KeyboardKey[slot].press()

    def on_release(self, slot: str, slot_input: InputValue):
        KeyboardKey[slot].release()

MOUSE_POSITION_SLOTS = ["MOVE", "ABSOLUTE"]

class Mouse(ConfigBlock):
    mouse_move_vec = Vec2()
    mouse_set_vec = Vec2()
    
    def process(self, delta_time: float = 0):
        x, y = move_mouse(self.mouse_move_vec.x, self.mouse_move_vec.y)
        self.mouse_move_vec.set_value(x, y)

    @classmethod
    def input_slots(cls) -> typing.List[str]:
        return [mb.name for mb in MouseButtonTarget] + MOUSE_POSITION_SLOTS

    def on_update(self, slot: str, slot_input: InputValue):
        if slot_input:
            vec = to_vec2(slot_input.value)
            match slot:
                case "MOVE":
                    self.mouse_move_vec += vec
                case "ABSOLUTE":
                    self.mouse_set_vec += vec

    def on_press(self, slot: str, slot_input: InputValue):
        if slot not in MOUSE_POSITION_SLOTS:
            MouseButtonTarget[slot].press()

    def on_release(self, slot: str, slot_input: InputValue):
        if slot not in MOUSE_POSITION_SLOTS:
            MouseButtonTarget[slot].release()


ConfigBlock.register_block_class("KEYBOARD", Keyboard)
ConfigBlock.register_block_class("MOUSE", Mouse)