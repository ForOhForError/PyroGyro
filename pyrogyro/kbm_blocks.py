import logging
import typing

from pyrogyro.io_types import *
from pyrogyro.math import *

from pyrogyro.config_blocks import ConfigBlock, InputValue


class Keyboard(ConfigBlock):
    def process(self, time_now: float = 0):
        pass

    @classmethod
    def input_slots(cls) -> typing.List[str]:
        return [key.name for key in KeyboardKey]

    def on_press(self, slot: str, slot_input: InputValue):
        KeyboardKey[slot].press()

    def on_release(self, slot: str, slot_input: InputValue):
        KeyboardKey[slot].release()


class Mouse(ConfigBlock):
    def process(self, time_now: float = 0):
        pass

    @classmethod
    def input_slots(cls) -> typing.List[str]:
        return [key.name for key in MouseButtonTarget]

    def on_press(self, slot: str, slot_input: InputValue):
        KeyboardKey[slot].press()

    def on_release(self, slot: str, slot_input: InputValue):
        KeyboardKey[slot].release()


ConfigBlock.register_block_class("KEYBOARD", Keyboard)
