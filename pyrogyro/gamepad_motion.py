# Ported from the examples at:
# http://gyrowiki.wikidot.com/blog:player-space-gyro-and-alternatives-explained
# http://gyrowiki.wikidot.com/blog:finding-gravity-with-sensor-fusion
# Thanks JibbSmart! :)

import enum
import math
from dataclasses import dataclass, field

from pyrogyro.io_types import enum_or_by_name
from pyrogyro.math import *


@dataclass
class GyroCalibration:
    calibration: Vec3 = field(default_factory=Vec3)
    num_samples: int = 0

    def reset(self):
        self.calibration.set_value(0, 0, 0)
        self.num_samples = 0

    def update(self, vel_sample: Vec3):
        self.num_samples += 1
        self.calibration += vel_sample

    @property
    def calibration_offset(self):
        if self.num_samples == 0:
            return Vec3()
        else:
            return self.calibration / self.num_samples

    def calibrated(self, uncalibrated_gyro):
        return uncalibrated_gyro - self.calibration_offset


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


def gyro_camera_local(
    gyro: Vec3, delta_seconds: float, gyro_sens: float = 1, yaw_turn_axis: bool = True
):
    if yaw_turn_axis:
        yaw_vel = gyro.y * gyro_sens * delta_seconds
    else:
        yaw_vel = gyro.z * gyro_sens * delta_seconds
    pitch_vel = gyro.x * gyro_sens * delta_seconds
    return Vec2(yaw_vel, pitch_vel)


def gyro_camera_local_ow(gyro: Vec3, delta_seconds: float, gyro_sens: float = 1):
    yaw_axes = Vec2(gyro.y, gyro.z)
    if abs(yaw_axes.x) > abs(yaw_axes.y):
        yaw_direction = sign(yaw_axes.x)
    else:
        yaw_direction = sign(yaw_axes.y)

    yaw_vel = yaw_axes.length() * yaw_direction * gyro_sens * delta_seconds
    pitch_vel = gyro.x * gyro_sens * delta_seconds
    return Vec2(yaw_vel, pitch_vel)


def gyro_camera_world(
    gyro: Vec3, grav_norm: Vec3, delta_seconds: float, gyro_sens: float = 1
):
    flatness = abs(grav_norm.y)  # 1 when controller is flat
    upness = abs(grav_norm.z)  # 1 when controller is upright
    side_reduction = clamp((max(flatness, upness) - 0.125) / 0.125, 0, 1)
    pitch_vel = 0.0

    # world space yaw velocity (negative because gravity points down)
    yaw_vel = gyro.dot(grav_norm) * gyro_sens * delta_seconds * -1

    # project pitch axis onto gravity plane
    grav_dot_pitch_axis = grav_norm.x
    # shortcut for (1, 0, 0).Dot(gravNorm)
    pitch_vector = Vec3(1, 0, 0) - grav_norm * grav_dot_pitch_axis
    # that's all it took!

    # normalize. it'll be zero if pitch and gravity are parallel, which we ignore
    if not pitch_vector.is_zero_vector():
        pitch_vector.normalize()
        # camera pitch velocity just like yaw velocity at the beginning
        # (but squish to 0 when controller is on its side)
        pitch_vel = gyro.dot(pitch_vector) * side_reduction * gyro_sens * delta_seconds
    return Vec2(yaw_vel, pitch_vel)


def gyro_camera_player_turn(
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
    side_reduction = clamp((max(flatness, upness) - 0.125) / 0.125, 0, 1)

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


class GyroMode(enum.Enum):
    OFF = "OFF"
    LOCAL = "LOCAL"
    LOCAL_OW = "LOCAL_OW"
    WORLD = "WORLD"
    PLAYER_TURN = "PLAYER_TURN"
    PLAYER_LEAN = "PLAYER_LEAN"


@dataclass
class GyroConfig:
    gyro_mode: enum_or_by_name(GyroMode) = GyroMode.OFF
    gyro_sens: float = 1.0

    def gyro_camera(self, gyro: Vec3, grav_norm: Vec3, delta_seconds: float):
        match self.gyro_mode:
            case GyroMode.OFF:
                return Vec2(0, 0)
            case GyroMode.LOCAL:
                return gyro_camera_local(gyro, delta_seconds, gyro_sens=self.gyro_sens)
            case GyroMode.LOCAL_OW:
                return gyro_camera_local_ow(
                    gyro, delta_seconds, gyro_sens=self.gyro_sens
                )
            case GyroMode.WORLD:
                return gyro_camera_world(
                    gyro, grav_norm, delta_seconds, gyro_sens=self.gyro_sens
                )
            case GyroMode.PLAYER_TURN:
                return gyro_camera_player_turn(
                    gyro, grav_norm, delta_seconds, gyro_sens=self.gyro_sens
                )
            case GyroMode.PLAYER_LEAN:
                return gyro_camera_player_lean(
                    gyro, grav_norm, delta_seconds, gyro_sens=self.gyro_sens
                )
