# Ported from the examples at:
# http://gyrowiki.wikidot.com/blog:player-space-gyro-and-alternatives-explained
# http://gyrowiki.wikidot.com/blog:finding-gravity-with-sensor-fusion
# Thanks JibbSmart! :)

import enum
import logging
import math
import typing
from dataclasses import dataclass, field
from queue import deque

from pyrogyro.math import *
from pyrogyro.config_blocks import ConfigBlock

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

SMOOTHING_HALF_TIME = 0.25
SHAKINESS_MAX_THRESHOLD = 0.4
SHAKINESS_MIN_THRESHOLD = 0.01
CORRECTION_STILL_RATE = 1
CORRECTION_SHAKY_RATE = 0.1
CORRECTION_GYRO_FACTOR = 0.1
CORRECTION_GYRO_MIN_THRESHOLD = 0.05
CORRECTION_GYRO_MAX_THRESHOLD = 0.25
CORRECTION_MIN_SPEED = 0.01

def sensor_fusion_gravity_fancy(
    gravity: Vec3, smooth_accel: Vec3, shakiness: float, gyro: Vec3, accel: Vec3, delta_seconds: float, nudge_value=0.02
):
    # convert gyro input to reverse rotation
    reverse_rotation = Quat.angle_axis(gyro.length() * delta_seconds, -gyro.x, -gyro.y, -gyro.z)
    #rotate gravity vector
    gravity.mul(reverse_rotation)
    smooth_accel.mul(reverse_rotation)
    smooth_interpolator = 2**(-delta_seconds/SMOOTHING_HALF_TIME)
    shakiness *= smooth_interpolator
    shakiness = max(shakiness, (accel-smooth_accel).length())
    smooth_accel = lerp(accel, smooth_accel, smooth_interpolator)

    gravity_delta = (accel*-1) - gravity
    gravity_delta_direction = gravity_delta.normalized()
    
    if SHAKINESS_MAX_THRESHOLD > SHAKINESS_MIN_THRESHOLD:
        correction_rate = clamp((shakiness-SHAKINESS_MAX_THRESHOLD)/(SHAKINESS_MAX_THRESHOLD-SHAKINESS_MIN_THRESHOLD), 0, 1)
    elif shakiness > SHAKINESS_MAX_THRESHOLD:
        correction_rate = CORRECTION_SHAKY_RATE
    else:
        correction_rate = CORRECTION_STILL_RATE

    # limit in proportion to rotation rate
    angle_rate = gyro.length() * math.pi / 180
    correction_limit = angle_rate * gravity.length() * CORRECTION_GYRO_FACTOR
    if correction_rate > correction_limit:
        if CORRECTION_GYRO_MAX_THRESHOLD > CORRECTION_GYRO_MIN_THRESHOLD:
            close_enough_factor = clamp((gravity_delta.length()-CORRECTION_GYRO_MIN_THRESHOLD)/(CORRECTION_GYRO_MAX_THRESHOLD-CORRECTION_GYRO_MIN_THRESHOLD), 0, 1)
        elif gravity_delta.length() > CORRECTION_GYRO_MIN_THRESHOLD:
            close_enough_factor = 1
        else:
            close_enough_factor = 0
        correction_rate = correction_rate + (correction_limit - correction_rate) * close_enough_factor

    # finally, let's always allow a little bit of correction
    correction_rate = max(correction_rate, CORRECTION_MIN_SPEED)

    # apply correction
    correction = gravity_delta_direction * (correction_rate * delta_seconds)
    if correction.length()**2 < gravity_delta.length()**2:
        gravity += correction
    else:
        gravity += gravity_delta
    return gravity


def gyro_camera_local(gyro: Vec3, delta_seconds: float, yaw_turn_axis: bool = True):
    if yaw_turn_axis:
        yaw_vel = gyro.y * delta_seconds
    else:
        yaw_vel = gyro.z * delta_seconds
    pitch_vel = gyro.x * delta_seconds
    return Vec2(yaw_vel, pitch_vel)


def gyro_camera_local_ow(gyro: Vec3, delta_seconds: float):
    yaw_axes = Vec2(gyro.y, gyro.z)
    if abs(yaw_axes.x) > abs(yaw_axes.y):
        yaw_direction = sign(yaw_axes.x)
    else:
        yaw_direction = sign(yaw_axes.y)

    yaw_vel = yaw_axes.length() * yaw_direction * delta_seconds
    pitch_vel = gyro.x * delta_seconds
    return Vec2(yaw_vel, pitch_vel)


def gyro_camera_world(gyro: Vec3, grav_norm: Vec3, delta_seconds: float):
    flatness = abs(grav_norm.y)  # 1 when controller is flat
    upness = abs(grav_norm.z)  # 1 when controller is upright
    side_reduction = clamp((max(flatness, upness) - 0.125) / 0.125, 0, 1)
    pitch_vel = 0.0

    # world space yaw velocity (negative because gravity points down)
    yaw_vel = gyro.dot(grav_norm) * delta_seconds * -1

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
        pitch_vel = gyro.dot(pitch_vector) * side_reduction * delta_seconds
    return Vec2(yaw_vel, pitch_vel)


def gyro_camera_player_turn(
    gyro: Vec3,
    grav_norm: Vec3,
    delta_seconds: float,
    yaw_relax_factor=1.41,
):
    # use world yaw for yaw direction, local combined yaw for magnitude
    world_yaw = gyro.y * grav_norm.y + gyro.z * grav_norm.z
    # dot product but just yaw and roll
    yaw_vel = (
        -sign(world_yaw)
        * min(abs(world_yaw) * yaw_relax_factor, Vec2(gyro.y, gyro.z).length())
        * delta_seconds
    )

    pitch_vel = gyro.x * delta_seconds
    return Vec2(yaw_vel, pitch_vel)


def gyro_camera_player_lean(
    gyro: Vec3,
    grav_norm: Vec3,
    delta_seconds: float,
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
                * delta_seconds
            )

    pitch_vel = gyro.x * delta_seconds
    return Vec2(yaw_vel, pitch_vel)


class GyroMode(enum.Enum):
    OFF = "OFF"
    LOCAL = "LOCAL"
    LOCAL_OW = "LOCAL_OW"
    WORLD = "WORLD"
    PLAYER_TURN = "PLAYER_TURN"
    PLAYER_LEAN = "PLAYER_LEAN"

@dataclass
class GyroData:
    gyro: Vec3
    gravity_normal: Vec3

class GyroConfig(ConfigBlock):
    mode: GyroMode = GyroMode.OFF
    sens: float | typing.Tuple[float, float] = 1.0
    fast_sens: typing.Optional[float | typing.Tuple[float, float]] = None
    slow_threshold: float = 0.0
    fast_threshold: float = 0.0
    real_world_calibration: float = 1.0
    in_game_sens: float = 1.0
    smooth_window: typing.Optional[int] = None
    smooth_threshold: typing.Optional[float] = None
    tightening_theshold: typing.Optional[float] = None
    smooth_buffer = deque()
    
    _input_slots = ("GYRO", "GYRO_ON", "GYRO_OFF")
    _output_slots = ("MOUSE",)
    _config_slots = ("real_world_calibration","in_game_sens","mode","sens","fast_sens","slow_threshold","fast_threshold","smooth_window","smooth_threshold","tightening_theshold")

    def post_init(self, *args, **kwargs):
        if isinstance(self.mode,str):
            self.mode = GyroMode[self.mode]

    def get_smoothed_gyro(self, sample: Vec2):
        self.smooth_buffer.append(sample)
        if len(self.smooth_buffer) > (self.smooth_window if self.smooth_window else 0):
            self.smooth_buffer.popleft()
        smoothed = Vec2()
        for entry in self.smooth_buffer:
            smoothed += entry
        smoothed /= len(self.smooth_buffer)
        return smoothed

    def get_tiered_smoothed_gyro(
        self, sample: Vec2, smooth_thresh: float, delta_seconds: float
    ):
        smooth_thresh *= delta_seconds
        half_thresh = smooth_thresh * 0.5
        sample_len = sample.length()
        if half_thresh != 0:
            direct_weight = (sample_len - half_thresh) / half_thresh
        else:
            direct_weight = 0
        direct_weight = clamp(direct_weight, 0.0, 1.0)
        return (sample * direct_weight) + self.get_smoothed_gyro(
            sample * (1.0 - direct_weight)
        )

    def get_tightened_sample(
        self, sample: Vec2, threshold: float, delta_seconds: float
    ):
        threshold *= delta_seconds
        sample_len = sample.length()
        if sample_len < threshold:
            if threshold == 0:
                input_scale = 0
            else:
                input_scale = sample_len / threshold
            return sample * input_scale
        return sample

    def get_slow_sens(self):
        if isinstance(self.sens, (float, int)):
            return self.sens, self.sens
        else:
            return self.sens

    def get_fast_sens(self):
        if self.fast_sens:
            if isinstance(self.fast_sens, (float, int)):
                return self.fast_sens, self.fast_sens
            else:
                return self.fast_sens
        else:
            return self.get_slow_sens()

    def get_accel_sens(
        self, gyro: Vec2, slow_threshold: float, fast_threshold: float, delta_seconds
    ):
        slow_threshold *= delta_seconds
        fast_threshold *= delta_seconds
        speed = gyro.length()
        slow_sens_x, slow_sens_y = self.get_slow_sens()
        fast_sens_x, fast_sens_y = self.get_fast_sens()
        thresh_dist = fast_threshold - slow_threshold
        slow_fast_factor = (
            (speed - slow_threshold) / thresh_dist if thresh_dist != 0 else 0
        )
        return lerp(slow_sens_x, fast_sens_x, slow_fast_factor), lerp(
            slow_sens_y, fast_sens_y, slow_fast_factor
        )

    def gyro_camera(self, gyro: Vec3, grav_norm: Vec3, delta_seconds: float):
        match self.mode:
            case GyroMode.OFF:
                calibrated_gyro = Vec2(0, 0)
            case GyroMode.LOCAL:
                calibrated_gyro = gyro_camera_local(gyro, delta_seconds)
            case GyroMode.LOCAL_OW:
                calibrated_gyro = gyro_camera_local_ow(gyro, delta_seconds)
            case GyroMode.WORLD:
                calibrated_gyro = gyro_camera_world(gyro, grav_norm, delta_seconds)
            case GyroMode.PLAYER_TURN:
                calibrated_gyro = gyro_camera_player_turn(
                    gyro, grav_norm, delta_seconds
                )
            case GyroMode.PLAYER_LEAN:
                calibrated_gyro = gyro_camera_player_lean(
                    gyro, grav_norm, delta_seconds
                )
            case _:
                calibrated_gyro = Vec2(0, 0)
        if self.smooth_window:
            if self.smooth_threshold:
                calibrated_gyro = self.get_tiered_smoothed_gyro(
                    calibrated_gyro, self.smooth_threshold, delta_seconds
                )
            else:
                calibrated_gyro = self.get_smoothed_gyro(calibrated_gyro)

        if self.tightening_theshold:
            calibrated_gyro = self.get_tightened_sample(
                calibrated_gyro, self.tightening_theshold, delta_seconds
            )

        gyro_sens_x, gyro_sens_y = self.get_accel_sens(
            calibrated_gyro, self.slow_threshold, self.fast_threshold, delta_seconds
        )
        calibrated_gyro.x *= gyro_sens_x
        calibrated_gyro.y *= gyro_sens_y
        return calibrated_gyro

    def gyro_pixels(
        self,
        gyro: Vec3,
        grav_norm: Vec3,
        delta_seconds: float = 0.0,
        real_world_calibration: float = 1.0,
        in_game_sens: float = 1.0,
    ):
        os_mouse_speed = 1.0
        mouse_calib = real_world_calibration / os_mouse_speed / in_game_sens
        camera_vec = self.gyro_camera(gyro, grav_norm, delta_seconds)
        camera_vec *= mouse_calib
        camera_vec *= -1
        return camera_vec
    
    def process(self, delta_time:float=0):
        slot_input = self._input_vals.get("GYRO")
        if slot_input:
            if isinstance(slot_input.value, GyroData):
                gyro_data:GyroData = slot_input.value
                gyro_pixels = self.gyro_pixels(
                    gyro_data.gyro,
                    gyro_data.gravity_normal,
                    delta_time,
                    self.real_world_calibration,
                    self.in_game_sens
                )
                self.set_output_val("MOUSE",gyro_pixels)

def register_blocks():
    ConfigBlock.register_block_class("GYRO_TO_MOUSE", GyroConfig)