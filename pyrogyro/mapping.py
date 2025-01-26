import sys
import typing
from enum import Flag

import vgamepad as vg
from pydantic import BaseModel, BeforeValidator, PlainSerializer
from ruamel.yaml import YAML

from pyrogyro.constants import SDLButtonEnum

yaml = YAML(typ="safe")

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
    mapping: typing.Mapping[
        enum_or_by_name(SDLButtonEnum), enum_or_by_name(vg.XUSB_BUTTON)
    ]

    def save_to_file(self, file_handle=sys.stdout):
        yaml.dump(self.model_dump(), file_handle)

    @classmethod
    def load_from_file(cls, file_handle=sys.stdin):
        return cls.parse_obj(yaml.load(file_handle))


def get_default_mapping():
    return Mapping(
        name="Default Mapping",
        mapping={
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
        },
    )
