import collections.abc
import logging
import sys
import typing

from pydantic import BaseModel, Field

# from ruamel.yaml import YAML, CommentedMap, CommentedSeq
import tomlkit

from pyrogyro.color_led import LerpableLED, get_default_led
from pyrogyro.complex_targets import register_complex_targets
from pyrogyro.control_graph import ControlGraph, ControlNode, GraphComponent, to_node
from pyrogyro.gamepad_motion import GyroConfig
from pyrogyro.io_types import (
    BasicMappingOrListOfMappings,
    ButtonTarget,
    DetailedMapping,
    DoubleAxisSource,
    DoubleAxisTarget,
    EventType,
    InputEvent,
    MapSource,
    MapTarget,
    SDLButtonSource,
    SingleAxisSource,
    SingleAxisTarget,
    enum_or_by_name,
)
from pyrogyro.platform_util import get_os_mouse_speed

# yaml = YAML()
# yaml.compact(seq_seq=False, seq_map=False)

register_complex_targets()


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


class Layer(GraphComponent):
    mapping: "BasicMappingOrListOfMappings" = Field(
        # default_factory=CommentedMap
        default_factory=dict
    )
    gyro: GyroConfig = Field(default_factory=GyroConfig)

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

    def to_node(
        self, root_graph: ControlGraph, on: MapSource | None = None
    ) -> ControlNode:
        return to_node(self.mapping, root_graph, on)


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
    layers: collections.abc.Mapping[str, Layer] = Field(
        # default_factory=CommentedMap
        default_factory=dict
    )
    led: LerpableLED = Field(default_factory=get_default_led)
    real_world_calibration: typing.Optional[float] = None
    in_game_sens: typing.Optional[float] = None
    counter_os_mouse_speed: typing.Optional[bool] = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._loaded_yml_map = None
        self._active_layers = set()
        self._control_graph = ControlGraph()

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
        print(obj_out_direct)
        obj_out_sorted = {}
        for key in _MAPPING_FIELD_ORDER:
            if key in obj_out_direct:
                obj_out_sorted[key] = obj_out_direct.pop(key)
        for key in obj_out_direct:
            obj_out_sorted[key] = obj_out_direct.get(key)
        if self._loaded_yml_map:
            pass
            # commented_out = CommentedMap(obj_out_sorted)
            # commented_out = commented_out.copy_attributes(self._loaded_yml_map)
            # obj_out_sorted = commented_out
        tomlkit.dump(obj_out_sorted, file_handle)

    @classmethod
    def load_from_file(cls, file_handle=sys.stdin):
        parsed_from_file = tomlkit.load(file_handle)
        constructed_mapping = cls.model_validate(parsed_from_file)
        constructed_mapping._loaded_yml_map = parsed_from_file
        graph = constructed_mapping._control_graph
        node = constructed_mapping.to_node(graph)
        node.always_active = True
        graph.set_main_layer(node)
        for layer_name, layer in constructed_mapping.layers.items():
            node = layer.to_node(graph)
            graph.set_layer(layer_name, node)
        graph.print_structure()
        constructed_mapping._control_graph = graph
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
            }  # type: ignore
        ),  # type: ignore
    )


def generate_default_mapping_files():
    xbox_config = get_default_xbox_mapping()
    with open("configs/default_xbox.toml", "w") as xbox_config_file:
        xbox_config.save_to_file(xbox_config_file)
