from pyrogyro.math import *
import colorsys
import enum
import typing
from dataclasses import dataclass, field

from pyrogyro.config_blocks import ConfigBlock

HSV_ROYGBIV = [
    Vec3(x=0, y=1, z=1),
    Vec3(x=1, y=1, z=1),
]

RGB_PYRO_GYRO = [
    Vec3(x=55 / 255.0, y=113 / 255.0, z=163 / 255.0),
    Vec3(x=255 / 255.0, y=209 / 255.0, z=65 / 255.0),
]

class ColorScheme(enum.Enum):
    RAINBOW = HSV_ROYGBIV



class ColorSpace(enum.Enum):
    RGB = "RGB"
    HSV = "HSV"

    def to_rgb(self, in_color: Vec3):
        match self.value:
            case self.HSV.value:
                rgb = colorsys.hsv_to_rgb(in_color.x, in_color.y, in_color.z)
                return Vec3(x=rgb[0], y=rgb[1], z=rgb[2])
            case self.RGB.value:
                return in_color
        return in_color



class ColorSequence(ConfigBlock):
    _output_slots = ("COLOR", )
    _config_slots = ("color_sequence", "duration_per_color", "instant_loop", "color_space")
    color_sequence: list = []
    index_start: int = 0
    index_end: int = 0
    start_ts: typing.Optional[int] = None
    duration_per_color: float = 1
    color_space: ColorSpace = ColorSpace.RGB
    instant_loop: bool = False
    current_color: Vec3 = Vec3()
    
    def post_init(self, *args, **kwargs):
        if isinstance(self.color_space, str):
            self.color_space = ColorSpace[self.color_space]
        
        if isinstance(self.color_sequence, str):
            self.color_sequence = ColorScheme[self.color_sequence].value
        
        self.index_start = 0
        if len(self.color_sequence) > 1:
            self.index_end = 1
        else:
            self.index_end = 0

    @classmethod
    def is_source(cls) -> bool:
        return True

    def process(self, delta_time: float = 0):
        if self.duration_per_color == 0:
            delta = 0
        else:
            delta = delta_time / self.duration_per_color
        start, end = (
            self.color_sequence[self.index_start],
            self.color_sequence[self.index_end],
        )
        self.current_color.set_lerp(start, end, delta)
        if delta >= 1.0:
            self.index_start = self.index_start + 1
            self.index_end = self.index_end + 1
            len_seq = len(self.color_sequence)
            if self.index_start == len_seq - 1 and self.instant_loop:
                self.index_start = 0
                self.index_end = 1 if len_seq > 1 else 0
            else:
                self.index_start = self.index_start % len_seq
                self.index_end = self.index_end % len_seq
        self.set_output_val("COLOR", self.get_rgb_color())

    def get_rgb_color(self):
        return self.color_space.to_rgb(self.current_color)

def register_blocks():
    ConfigBlock.register_block_class("COLOR_SEQUENCE", ColorSequence)