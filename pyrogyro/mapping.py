import collections.abc
import logging
import sys
import typing

from pydantic import BaseModel, Field
from ruamel.yaml import YAML, CommentedMap, CommentedSeq

from pyrogyro.gamepad_motion import GyroConfig, GyroMode
from pyrogyro.io_types import (
    AndTarget,
    ButtonTarget,
    BasicMapping,
    BasicMappingOrListOfMappings,
    DetailedMapping,
    DoubleAxisSource,
    DoubleAxisTarget,
    MapComplexTarget,
    MapSource,
    MapTarget,
    SDLButtonSource,
    SingleAxisSource,
    SingleAxisTarget,
    enum_or_by_name,
)
from pyrogyro.platform import get_os_mouse_speed

yaml = YAML()
yaml.compact(seq_seq=False, seq_map=False)


class GyroMapping(BaseModel):
    mode: GyroConfig = Field(default_factory=GyroConfig)
    output: typing.Optional[enum_or_by_name(DoubleAxisTarget)] = None


class AutoloadConfig(BaseModel):
    match_exe_name: str = ".*"
    match_window_name: str = ".*"
    match_controller_name: str = ".*"

    @classmethod
    def get_match_all(cls):
        return cls(
            match_exe_name=".*", match_window_name=".*", match_controller_name=".*"
        )

    def count_specificity(self):
        return sum(
            (
                1 if val != ".*" else 0
                for val in (
                    self.match_exe_name,
                    self.match_window_name,
                    self.match_controller_name,
                )
            )
        )


class Layer(BaseModel):
    mapping: BasicMappingOrListOfMappings = Field(default_factory=CommentedMap)
    gyro: GyroMapping = Field(default_factory=GyroMapping)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._active_mapping = {}
        self._stale = True

    @property
    def map(self):
        self.refresh_active_mapping()
        return self._active_mapping

    def refresh_active_mapping(self):
        # these probably need to be deep updates
        if self._stale:
            self._active_mapping.clear()
            if isinstance(self.mapping, typing.Sequence):
                for entry in self.mapping:
                    if isinstance(entry, DetailedMapping):
                        self._active_mapping[entry.input] = entry.output
                    else:
                        self._active_mapping.update(entry)
            else:
                self._active_mapping.update(self.mapping)
            self._stale = False


_MAPPING_FIELD_ORDER = (
    "name",
    "autoload",
    "real_world_calibration",
    "in_game_sens",
    "mapping",
    "gyro",
    "layers",
)


class Mapping(Layer):
    name: str = "Default Mapping"
    autoload: typing.Optional[AutoloadConfig] = None
    layers: collections.abc.Mapping[str, Layer] = Field(default_factory=CommentedMap)
    real_world_calibration: typing.Optional[float] = None
    in_game_sens: typing.Optional[float] = None
    counter_os_mouse_speed: typing.Optional[bool] = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._loaded_yml_map = None
        self._active_layers = set()

    def get_in_game_sens(self):
        return self.in_game_sens if self.in_game_sens else 1.0

    def get_real_world_calibration(self):
        return (
            self.real_world_calibration if self.real_world_calibration else (16.0 / 3)
        )

    def get_os_mouse_speed_correction(self):
        return get_os_mouse_speed() if self.counter_os_mouse_speed else 1.0

    def reset(self):
        self._active_layers.clear()
        self._stale = True

    @property
    def map(self):
        self.refresh_active_mapping()
        return self._active_mapping

    def set_layer_activation(self, layer_name: str, active: bool):
        if layer_name in self.layers:
            if active:
                if layer_name not in self._active_layers:
                    logging.info(f"Activated layer {layer_name}")
                    self._active_layers.add(layer_name)
                    self._stale = True
            else:
                if layer_name in self._active_layers:
                    logging.info(f"Deactivated layer {layer_name}")
                    self._active_layers.remove(layer_name)
                    self._stale = True

    def refresh_active_mapping(self):
        if self._stale:
            self._active_mapping.clear()
            if isinstance(self.mapping, typing.Sequence):
                for entry in self.mapping:
                    if isinstance(entry, DetailedMapping):
                        if isinstance(entry, DetailedMapping):
                            self._active_mapping[entry.input] = entry.output
                    else:
                        self._active_mapping.update(entry)
            else:
                self._active_mapping.update(self.mapping)
            for layer in self.layers:
                if layer in self._active_layers:
                    self._active_mapping.update(self.layers[layer].map)
            self._stale = False

    def count_autoload_specificity(self):
        if self.autoload:
            return self.autoload.count_specificity()
        return 0

    def save_to_file(self, file_handle=sys.stdout):
        obj_out_direct = self.model_dump(exclude_none=True, exclude_unset=True)
        obj_out_sorted = {}
        for key in _MAPPING_FIELD_ORDER:
            if key in obj_out_direct:
                obj_out_sorted[key] = obj_out_direct.pop(key)
        for key in obj_out_direct:
            obj_out_sorted[key] = obj_out_direct.get(key)
        if self._loaded_yml_map:
            commented_out = CommentedMap(obj_out_sorted)
            commented_out = commented_out.copy_attributes(self._loaded_yml_map)
            obj_out_sorted = commented_out
        yaml.dump(obj_out_sorted, file_handle)

    @classmethod
    def load_from_file(cls, file_handle=sys.stdin):
        parsed_from_file = yaml.load(file_handle)
        constructed_mapping = cls.parse_obj(parsed_from_file)
        constructed_mapping._loaded_yml_map = parsed_from_file
        return constructed_mapping


def get_default_xbox_mapping():
    return Mapping(
        name="Default Xbox Controller",
        autoload=AutoloadConfig.get_match_all(),
        mapping=dict(
            {
                SDLButtonSource.N: ButtonTarget.X_Y,
                SDLButtonSource.S: ButtonTarget.X_A,
                SDLButtonSource.E: ButtonTarget.X_B,
                SDLButtonSource.W: ButtonTarget.X_X,
                SDLButtonSource.BACK: ButtonTarget.X_BACK,
                SDLButtonSource.START: ButtonTarget.X_START,
                SDLButtonSource.UP: ButtonTarget.X_UP,
                SDLButtonSource.DOWN: ButtonTarget.X_DOWN,
                SDLButtonSource.LEFT: ButtonTarget.X_LEFT,
                SDLButtonSource.RIGHT: ButtonTarget.X_RIGHT,
                SDLButtonSource.L1: ButtonTarget.X_L1,
                SDLButtonSource.R1: ButtonTarget.X_R1,
                SDLButtonSource.L3: ButtonTarget.X_L3,
                SDLButtonSource.R3: ButtonTarget.X_R3,
                SDLButtonSource.GUIDE: ButtonTarget.X_GUIDE,
                SingleAxisSource.L2: SingleAxisTarget.X_L2,
                SingleAxisSource.R2: SingleAxisTarget.X_R2,
                DoubleAxisSource.LSTICK: DoubleAxisTarget.X_LSTICK,
                DoubleAxisSource.RSTICK: DoubleAxisTarget.X_RSTICK,
            }
        ),
    )


def generate_default_mapping_files():
    xbox_config = get_default_xbox_mapping()
    with open("configs/default_xbox.yml", "w") as xbox_config_file:
        xbox_config.save_to_file(xbox_config_file)
