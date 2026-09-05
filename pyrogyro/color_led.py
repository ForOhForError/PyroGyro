from pyrogyro.math import *
import colorsys
import enum
import typing
from dataclasses import dataclass, field

HSV_ROYGBIV = (
    Vec3(x=0, y=1, z=1),
    Vec3(x=1, y=1, z=1),
)

RGB_PYRO_GYRO = (
    Vec3(x=55 / 255.0, y=113 / 255.0, z=163 / 255.0),
    Vec3(x=255 / 255.0, y=209 / 255.0, z=65 / 255.0),
)


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


@dataclass
class LerpableLED:
    _current_color: Vec3 = field(default_factory=Vec3)
    color_sequence: typing.Sequence[Vec3] = field(default_factory=list)
    index_start: int = 0
    index_end: int = 0
    start_ts: typing.Optional[int] = None
    duration_per_color: float = 1
    color_space: ColorSpace = ColorSpace.RGB
    instant_loop: bool = False

    def set_sequence(
        self,
        color_sequence: typing.Sequence[Vec3],
        color_space=ColorSpace.RGB,
        duration_per_color=1,
        instant_loop=False,
    ):
        self.instant_loop = instant_loop
        self.color_sequence = color_sequence
        self.color_space = color_space
        self.index_start = 0
        self.duration_per_color = duration_per_color
        if len(self.color_sequence) > 1:
            self.index_end = 1
        else:
            self.index_end = 0
        return self

    def update(self, timestamp):
        if self.start_ts == None:
            self.start_ts = timestamp
        time_delta = timestamp - self.start_ts
        if self.duration_per_color == 0:
            delta = 0
        else:
            delta = time_delta / self.duration_per_color
        start, end = (
            self.color_sequence[self.index_start],
            self.color_sequence[self.index_end],
        )
        self._current_color.set_lerp(start, end, delta)
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
            self.start_ts = timestamp

    def get_rgb_color(self):
        return self.color_space.to_rgb(self._current_color)


def get_default_led():
    return LerpableLED().set_sequence(
        HSV_ROYGBIV,
        color_space=ColorSpace.HSV,
        duration_per_color=10,
        instant_loop=False,
    )
