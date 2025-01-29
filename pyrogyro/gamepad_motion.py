# Ported from the examples at:
# http://gyrowiki.wikidot.com/blog:player-space-gyro-and-alternatives-explained
# http://gyrowiki.wikidot.com/blog:finding-gravity-with-sensor-fusion
# Thanks JibbSmart! :)

import math
from dataclasses import dataclass


def clamp(input, max_val, min_val):
    return max(min(input, max_val), min_val)


def sign(input):
    return -1 if input < 0 else 1


@dataclass
class Vec2:
    x: float = 0
    y: float = 0

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


@dataclass
class Vec3:
    x: float = 0
    y: float = 0
    z: float = 0

    def is_zero_vector(self):
        return self.x == 0 and self.y == 0 and self.z == 0

    def __mul__(self, other):
        if isinstance(other, Vec3):
            return Vec3(self.x * other.x, self.y * other.y, self.z * other.z)
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

    def cross(self, other):
        return Vec3(
            self.y * other.z - other.y * self.z,
            self.z * other.x - other.z * self.x,
            self.x * other.y - other.x * self.y,
        )

    def mul(self, other):
        if isinstance(other, Vec3):
            self.x = self.x * other.x
            self.y = self.y * other.y
            self.z = self.z * other.z
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


def sensor_fusion_gravity(
    gravity: Vec3, gyro: Vec3, accel: Vec3, delta_seconds: float, nudge_value=0.02
):
    # convert gyro input to reverse rotation
    rotation = Quat.angle_axis(gyro.length() * delta_seconds, -gyro.x, -gyro.y, -gyro.z)

    # rotate gravity vector
    gravity.mul(rotation)

    # nudge towards gravity according to current acceleration
    newGravity = accel * -1
    gravity += (newGravity - gravity) * nudge_value
    return gravity


def gyro_camera_player_lean(
    gyro: Vec3,
    grav_norm: Vec3,
    delta_seconds: float,
    gyro_sens: float = 1,
    roll_relax_factor: float = 1.15,
):
    # some info about the controller's orientation that we'll use to smooth over boundaries
    flatness = abs(grav_norm.y)  # 1 when controller is flat
    upness = abs(grav_norm.z)  # 1 when controller is upright
    side_reduction = clamp(((max(flatness, upness) - 0.125) / 0.125), 0, 1)

    # project pitch axis onto gravity plane
    grav_dot_pitch_axis = grav_norm.x
    pitch_vector = Vec3(1, 0, 0) - grav_norm * grav_dot_pitch_axis

    yaw_vel = 0

    if not pitch_vector.is_zero_vector():
        roll_vector = pitch_vector.cross(grav_norm)
        if not roll_vector.is_zero_vector():
            roll_vector.normalize()
            world_roll = gyro.y * roll_vector.y + gyro.z * roll_vector.z
            yaw_vel = (
                -sign(world_roll)
                * side_reduction
                * min(
                    abs(world_roll) * roll_relax_factor, Vec2(gyro.y, gyro.z).length()
                )
                * gyro_sens
                * delta_seconds
            )

    pitch_vel = gyro.x * gyro_sens * delta_seconds
    return Vec2(yaw_vel, pitch_vel)


def gyro_camera_player(
    gyro: Vec3,
    grav_norm: Vec3,
    delta_seconds: float,
    gyro_sens: float = 1,
    yaw_relax_factor=1.41,
):
    # use world yaw for yaw direction, local combined yaw for magnitude
    world_yaw = gyro.y * grav_norm.y + gyro.z * grav_norm.z
    # dot product but just yaw and roll
    yaw_vel = (
        -sign(world_yaw)
        * min(abs(world_yaw) * yaw_relax_factor, Vec2(gyro.y, gyro.z).length())
        * gyro_sens
        * delta_seconds
    )

    pitch_vel = gyro.x * gyro_sens * delta_seconds
    return Vec2(yaw_vel, pitch_vel)
