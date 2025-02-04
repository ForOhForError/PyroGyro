import math
from dataclasses import dataclass


def lerp(start, end, progress):
    delta = clamp(progress, 1.0, 0.0)
    deltnt = 1.0 - delta
    return start * deltnt + end * delta


def clamp(input, max_val, min_val):
    return max(min(input, max_val), min_val)


def sign(input):
    return -1 if input < 0 else 1


RADIANS_TO_DEGREES = 360 / (2 * math.pi)


@dataclass
class Vec2:
    x: float = 0
    y: float = 0

    def __mul__(self, other):
        return Vec2(self.x * other, self.y * other)

    def set_value(self, x: float, y: float):
        self.x, self.y = x, y

    def length(self):
        return math.sqrt(self.x**2 + self.y**2)

    def __add__(self, other):
        if isinstance(other, Vec2):
            return Vec2(self.x + other.x, self.y + other.y)
        else:
            return Vec2(self.x + other, self.y + other)

    def __iadd__(self, other):
        if isinstance(other, Vec2):
            self.x = self.x + other.x
            self.y = self.y + other.y
        else:
            self.x = self.x + other
            self.y = self.y + other
        return self

    def __itruediv__(self, other):
        self.x, self.y = self.x / other, self.y / other
        return self

    def __truediv__(self, other):
        return Vec2(self.x / other, self.y / other)

    def angle(self):
        return (math.atan2(self.x, self.y) * RADIANS_TO_DEGREES) + 180.0


@dataclass
class Vec3:
    x: float = 0
    y: float = 0
    z: float = 0

    def set_value(self, x: float, y: float, z: float):
        self.x, self.y, self.z = x, y, z

    def is_zero_vector(self):
        return self.x == 0 and self.y == 0 and self.z == 0

    def __truediv__(self, other):
        other = float(other)
        return Vec3(self.x / other, self.y / other, self.z / other)

    def __mul__(self, other):
        if isinstance(other, Vec3):
            return self.cross(other)
        else:
            return Vec3(self.x * other, self.y * other, self.z * other)

    def __add__(self, other):
        if isinstance(other, Vec3):
            return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)
        else:
            return Vec3(self.x + other, self.y + other, self.z + other)

    def __sub__(self, other):
        if isinstance(other, Vec3):
            return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)
        else:
            return Vec3(self.x - other, self.y - other, self.z - other)

    @classmethod
    def lerp(cls, start: "Vec3", end: "Vec3", delta: float):
        return cls().set_lerp(start, end, delta)

    def set_lerp(self, start: "Vec3", end: "Vec3", delta: float):
        delta = clamp(delta, 1.0, 0.0)
        deltnt = 1.0 - delta
        self.x, self.y, self.z = (
            start.x * deltnt + end.x * delta,
            start.y * deltnt + end.y * delta,
            start.z * deltnt + end.z * delta,
        )
        return self

    def cross(self, other):
        return Vec3(
            self.y * other.z - other.y * self.z,
            self.z * other.x - other.z * self.x,
            self.x * other.y - other.x * self.y,
        )

    def dot(self, other):
        return self.x * other.x + self.y * other.y + self.z * other.z

    def mul(self, other):
        if isinstance(other, Vec3):
            cross = self.cross(other)
            self.x = cross.x
            self.y = cross.y
            self.z = cross.z
        elif isinstance(other, Quat):
            temp = other * Quat(0.0, self.x, self.y, self.z) * other.inverse()
            self.x, self.y, self.z = temp.x, temp.y, temp.z
        else:
            self.x = self.x * other
            self.y = self.y * other
            self.z = self.z * other

    def __iadd__(self, other):
        if isinstance(other, Vec3):
            self.x = self.x + other.x
            self.y = self.y + other.y
            self.z = self.z + other.z
        else:
            self.x = self.x + other
            self.y = self.y + other
            self.z = self.z + other
        return self

    def length(self):
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)

    def normalized(self):
        return Vec3(self.x, self.y, self.z).normalize()

    def normalize(self):
        current_len = self.length()
        if current_len != 0:
            self.x = self.x / current_len
            self.y = self.y / current_len
            self.z = self.z / current_len
        return self


@dataclass
class Quat:
    w: float
    x: float
    y: float
    z: float

    def inverse(self):
        return Quat(self.w, -self.x, -self.y, -self.z)

    def __mul__(self, other):
        if isinstance(other, Quat):
            return Quat(
                self.w * other.w
                - self.x * other.x
                - self.y * other.y
                - self.z * other.z,
                self.w * other.x
                + self.x * other.w
                + self.y * other.z
                - self.z * other.y,
                self.w * other.y
                - self.x * other.z
                + self.y * other.w
                + self.z * other.x,
                self.w * other.z
                + self.x * other.y
                - self.y * other.x
                + self.z * other.w,
            )
        else:
            return Quat(self.y * other, self.x * other, self.y * other, self.z * other)

    @classmethod
    def angle_axis(cls, in_angle: float, in_x: float, in_y: float, in_z: float):
        sin_half_angle = math.sin(in_angle * 0.5)
        in_axis = Vec3(in_x, in_y, in_z)
        in_axis.normalize()
        in_axis.mul(in_axis * sin_half_angle)
        result = cls(math.cos(in_angle * 0.5), in_axis.x, in_axis.y, in_axis.z)
        return result
