import collections.abc
import sys
import typing

from pydantic import BaseModel, Field
from ruamel.yaml import YAML, CommentedMap, CommentedSeq

from pyrogyro.gamepad_motion import GyroConfig, GyroMode
from pyrogyro.io_types import (
    ButtonTarget,
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
                1 if val != "*" else 0
                for val in (
                    self.match_exe_name,
                    self.match_window_name,
                    self.match_controller_name,
                )
            )
        )


_BasicMapping = collections.abc.Mapping[MapSource, MapTarget]
_BasicMappingOrListOfMappings = typing.Union[
    _BasicMapping, typing.Sequence[typing.Union[DetailedMapping, _BasicMapping]]
]


class Mapping(BaseModel):
    name: str = "Empty Mapping"
    autoload: typing.Optional[AutoloadConfig] = None
    mapping: _BasicMappingOrListOfMappings = Field(default_factory=CommentedMap)
    gyro: GyroMapping = Field(default_factory=GyroMapping)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._loaded_yml_map = None
        self._combo_map = {}

    @property
    def map(self):
        if isinstance(self.mapping, typing.Sequence):
            return {}
        else:
            return self.mapping

    def count_autoload_specificity(self):
        if self.autoload:
            return self.autoload.count_specificity()
        return 0

    def add_mapping(self, source: MapSource, button_out: MapTarget):
        self.map[source] = MapTarget
        self._update_combo_mappings()

    def _update_combo_mappings(self):
        combo_map = {}
        for key in self.map.keys():
            if isinstance(key, typing.Sequence):
                combo_map[key] = self.map[key]
        self._combo_map = combo_map

    def _valid_for_combo(self, source: MapSource) -> bool:
        for combo_key in self._combo_map:
            if source in combo_key:
                return True
        return False

    def save_to_file(self, file_handle=sys.stdout):
        obj_out = self.model_dump(exclude_none=True, exclude_unset=True)
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
    xbox_config = get_default_mapping()
    with open("configs/default_xbox.yml", "w") as xbox_config_file:
        xbox_config.save_to_file(xbox_config_file)
