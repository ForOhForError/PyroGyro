import logging
import typing

from pyrogyro.io_types import *
from pyrogyro.math import *

from pyrogyro.config_blocks import ConfigBlock, PyroGyroBaseModel

from dataclasses import dataclass, make_dataclass, field


def to_underscordinal(name: str) -> str:
    if len(name) == 1 and (not name.isidentifier()):
        return "_ord_{}".format(ord(name))
    return name


def from_underscordinal(name: str) -> str:
    if name.startswith("_ord_"):
        return chr(int(name[5:]))
    return name


class UnderscordinalResolver:
    def __setattr__(self, name: str, value: typing.Any) -> None:
        if len(name) == 1 and (not name.isidentifier()):
            name = to_underscordinal(name)
        return super().__setattr__(name, value)

    def __getattr__(self, name):
        if len(name) == 1 and (not name.isidentifier()):
            name = to_underscordinal(name)
        return super().__getattribute__(name)


class Keyboard(ConfigBlock):
    Inputs = make_dataclass(
        "Inputs",
        [
            (to_underscordinal(keynum.name), float | bool, field(default=False))
            for keynum in KeyboardKey
        ],
        bases=(PyroGyroBaseModel, UnderscordinalResolver),
    )

    def on_press(self, slot: str, slot_input):
        KeyboardKey[from_underscordinal(slot)].press()

    def on_release(self, slot: str, slot_input):
        KeyboardKey[from_underscordinal(slot)].release()


MOUSE_POSITION_SLOTS = ("MOVE", "ABSOLUTE")


class Mouse(ConfigBlock):
    self_managed_inputs = ("MOVE", "SET")

    @dataclass
    class Inputs(PyroGyroBaseModel):
        MOVE: Vec2 = field(default_factory=Vec2)
        SET: Vec2 = field(default_factory=Vec2)
        RIGHT: float | bool = False
        LEFT: float | bool = False
        MIDDLE: float | bool = False

    def post_init(self, *args, **kwargs):
        self.leftover = Vec2()

    def process(self, delta_time: float = 0):
        x, y = move_mouse(
            self.inputs.MOVE.x + self.leftover.x, self.inputs.MOVE.y + self.leftover.y
        )
        self.leftover.set_value(x, y)

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
