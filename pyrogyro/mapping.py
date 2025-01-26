import collections.abc
import sys
import typing
from enum import Flag

import vgamepad as vg
from pydantic import BaseModel, BeforeValidator, PlainSerializer
from ruamel.yaml import YAML, CommentedMap

from pyrogyro.constants import SDLButtonEnum

yaml = YAML()
yaml.compact(seq_seq=False, seq_map=False)

EnumNameSerializer = PlainSerializer(
    lambda e: e.name, return_type="str", when_used="always"
)


def enum_or_by_name(T):
    def constructed_by_object_or_name(v: str | T) -> T:
        if isinstance(v, T):
            return v
        try:
            return T[v]
        except KeyError:
            raise ValueError("invalid value")

    return typing.Annotated[
        T, EnumNameSerializer, BeforeValidator(constructed_by_object_or_name)
    ]


class Mapping(BaseModel):
    name: str
    mapping: collections.abc.Mapping[
        enum_or_by_name(SDLButtonEnum), enum_or_by_name(vg.XUSB_BUTTON)
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._loaded_yml_map = None

    def map_button(self, button_in: SDLButtonEnum, button_out: vg.XUSB_BUTTON):
        self.mapping[button_in] = button_out

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
        return constructed_mapping


def get_default_mapping():
    return Mapping(
        name="Default Mapping",
        mapping=CommentedMap(
            {
                SDLButtonEnum.NORTH: vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
                SDLButtonEnum.SOUTH: vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
                SDLButtonEnum.EAST: vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
                SDLButtonEnum.WEST: vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
                SDLButtonEnum.BACK: vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
                SDLButtonEnum.START: vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
                SDLButtonEnum.DPAD_UP: vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
                SDLButtonEnum.DPAD_DOWN: vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
                SDLButtonEnum.DPAD_LEFT: vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
                SDLButtonEnum.DPAD_RIGHT: vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
                SDLButtonEnum.LEFT_SHOULDER: vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
                SDLButtonEnum.RIGHT_SHOULDER: vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
                SDLButtonEnum.LEFT_STICK: vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
                SDLButtonEnum.RIGHT_STICK: vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
                SDLButtonEnum.GUIDE: vg.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE,
            }
        ),
    )


def generate_default_mapping_files():
    xbox_config = get_default_mapping()
    with open("configs/xbox.yml", "w") as xbox_config_file:
        xbox_config.save_to_file(xbox_config_file)
