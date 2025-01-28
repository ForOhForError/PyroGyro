import collections.abc
import sys
import typing

from pydantic import BaseModel
from ruamel.yaml import YAML, CommentedMap, CommentedSeq

from pyrogyro.io_types import (
    XUSB_BUTTON,
    DoubleAxisSource,
    DoubleAxisTarget,
    MapComplexTarget,
    MapSource,
    MapTarget,
    SDLButtonSource,
    SingleAxisSource,
    SingleAxisTarget,
)

yaml = YAML()
yaml.compact(seq_seq=False, seq_map=False)


class Mapping(BaseModel, frozen=True):
    name: str
    mapping: collections.abc.Mapping[MapSource, MapTarget]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._loaded_yml_map = None

    def add_mapping(self, source: MapSource, button_out: MapTarget):
        self.mapping[source] = MapTarget

    def save_to_file(self, file_handle=sys.stdout):
        obj_out = self.model_dump()
        if self._loaded_yml_map:
            commented_out = CommentedMap(obj_out)
            commented_out = commented_out.copy_attributes(self._loaded_yml_map)
            obj_out = commented_out
        yaml.dump(obj_out, file_handle)

    @classmethod
    def load_from_file(cls, file_handle=sys.stdin):
        parsed_from_file = yaml.load(file_handle)
        constructed_mapping = cls.parse_obj(parsed_from_file)
        constructed_mapping._loaded_yml_map = parsed_from_file
        print(constructed_mapping)
        return constructed_mapping


def get_default_mapping():
    return Mapping(
        name="Default Mapping",
        mapping=dict(
            {
                SDLButtonSource.N: XUSB_BUTTON.XUSB_GAMEPAD_Y,
                SDLButtonSource.S: XUSB_BUTTON.XUSB_GAMEPAD_A,
                SDLButtonSource.E: XUSB_BUTTON.XUSB_GAMEPAD_B,
                SDLButtonSource.W: XUSB_BUTTON.XUSB_GAMEPAD_X,
                SDLButtonSource.BACK: XUSB_BUTTON.XUSB_GAMEPAD_BACK,
                SDLButtonSource.START: XUSB_BUTTON.XUSB_GAMEPAD_START,
                SDLButtonSource.UP: XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
                SDLButtonSource.DOWN: XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
                SDLButtonSource.LEFT: XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
                SDLButtonSource.RIGHT: XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
                SDLButtonSource.L1: XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
                SDLButtonSource.R1: XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
                SDLButtonSource.L3: XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
                SDLButtonSource.R3: XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
                SDLButtonSource.GUIDE: XUSB_BUTTON.XUSB_GAMEPAD_GUIDE,
                SingleAxisSource.L2: SingleAxisTarget.XUSB_GAMEPAD_L2,
                SingleAxisSource.R2: SingleAxisTarget.XUSB_GAMEPAD_R2,
                DoubleAxisSource.LSTICK: DoubleAxisTarget.XUSB_GAMEPAD_LSTICK,
                DoubleAxisSource.RSTICK: DoubleAxisTarget.XUSB_GAMEPAD_RSTICK,
            }
        ),
    )


def generate_default_mapping_files():
    xbox_config = get_default_mapping()
    with open("configs/xbox.yml", "w") as xbox_config_file:
        xbox_config.save_to_file(xbox_config_file)
