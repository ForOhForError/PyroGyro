import dataclasses
import enum

import typing
import logging
import tomlkit

from pyrogyro.constants import DEBUG
from pyrogyro.io_types import to_bool
from pyrogyro.math import *

CONFIG_LOGGER = logging.getLogger("Config")


@dataclass
class PyroGyroBaseModel:
    @classmethod
    def load_from_dict(cls, data) -> typing.Self:
        cleaned_data = {key: val for key, val in data.items() if key in cls.fields()}
        return cls(**cleaned_data)

    def __post_init__(self, *args, **kwargs):
        # Cast enums by name
        for field in self.instance_fields():
            if isinstance(field.type, type) and issubclass(field.type, enum.Enum):
                setattr(self, field.name, field.type[getattr(self, field.name)])

    def reset_io(self):
        for field in self.instance_fields():
            name, default_value = (
                field.name,
                field.default_factory()
                if field.default_factory != dataclasses.MISSING
                else field.default,
            )
            setattr(self, name, default_value)

    def refresh_field_cache(self):
        self._fields = dataclasses.fields(self)

    def instance_fields(self):
        if not hasattr(self, "_fields"):
            self._fields = dataclasses.fields(self)
        return self._fields

    def instance_field_names(self):
        return [field.name for field in self.instance_fields()]

    @classmethod
    def fields(cls) -> list[str]:
        return [field.name for field in dataclasses.fields(cls)]


@dataclass
class NoData(PyroGyroBaseModel):
    pass


class PyroGyroConfig:
    def __init__(self, data):
        self.blocks: dict[str, ConfigBlock] = {}
        self.name = data.get("name", "PyroGyro Config")
        self.autoload = data.get("autoload", False)
        self.autoload_exe_name = data.get("autoload_exe_name", ".*")
        self.autoload_window_name = data.get("autoload_window_name", ".*")
        for key, value in data.items():
            if isinstance(value, dict):
                block = ConfigBlock.parse_from_dict(value)
                self.blocks[key] = block

    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self):
        return f"{type(self).__name__}({self.name}: {len(self.blocks)} blocks)"

    def print_config(self):
        for block_name, block in self.blocks.items():
            logging.debug(f"[{block_name}]")
            block.print_config()

    @classmethod
    def load_from_file(cls, file_handle):
        parsed_from_file = tomlkit.load(file_handle)
        return cls(parsed_from_file)

    def count_autoload_specificity(self):
        if self.autoload:
            return sum(
                (
                    1 if val != ".*" else 0
                    for val in (self.autoload_exe_name, self.autoload_window_name)
                )
            )
        return 0

    def unload(self):
        for block in self.blocks.values():
            block.unload()

    def load(self):
        for block in self.blocks.values():
            block.load()

    def do_load_unload(self):
        active = self.get_resolution_order()
        for block in active:
            block.load()
        for block in self.blocks.values():
            if block not in active:
                block.unload()

    def get_blocks_by_type(self, type_check) -> list:
        return [
            block
            for block in self.blocks.values()
            if issubclass(type_check, type(block))
        ]

    def reset(self):
        for block in self.blocks.values():
            block.reset_io()

    def process(self, delta_time: float = 0.0):
        sources = set()
        resolution_order = self.get_resolution_order()
        for block in resolution_order:
            if block.is_source():
                sources.add(block)
            block.process_inputs()
            block.process(delta_time=delta_time)
            block.flip_inputs()
            for slot in block.output_slots():
                output_value = block.get_output(slot)
                if output_value != None:
                    for dest_name, dest_slot in block.get_destinations(slot):
                        dest = self.blocks.get(dest_name)
                        if dest:
                            dest.set_input(dest_slot, output_value)
        for block in sources:
            block.process_source_end(delta_time=delta_time)

    def get_resolution_order(self) -> list["ConfigBlock"]:
        order = []
        visit = set()
        done = set()

        for block in self.blocks.values():
            if block.is_source() and block.processable():
                order.append(block)
                visit.add(block)

        while len(visit) > 0:
            next = visit.pop()
            for slot in next.output_slots():
                for block_name, slot_name in next.get_destinations(slot):
                    block = self.blocks.get(block_name)
                    if block and (block not in done) and (block not in visit):
                        visit.add(block)
                        order.append(block)
            done.add(next)
        return order


class ConfigBlock:
    class Register:
        BLOCK_TYPES: typing.Dict[str, type] = {}

    Inputs: type[PyroGyroBaseModel] = NoData
    Outputs: type[PyroGyroBaseModel] = NoData
    Config: type[PyroGyroBaseModel] = NoData

    def __init__(self, data: typing.Dict[str, typing.Any], *args, **kwargs):
        self.pre_init(*args, **kwargs)

        self.config: self.Config = self.Config.load_from_dict(data)
        self.post_config(*args, **kwargs)
        self.inputs: self.Inputs = self.Inputs()
        self.old_inputs: self.Inputs = self.Inputs()
        self.outputs: self.Outputs = self.Outputs()
        self._output_dests: dict[str, str | list[str]] = {}
        self._loaded: bool = False
        self._suppress = set()
        for key in data:
            if key == "TYPE" or key in self.config_slots():
                pass
            elif key in self.output_slots():
                try:
                    self._output_dests[key] = data[key]
                except ValueError:
                    CONFIG_LOGGER.exception("Error setting slot")
            else:
                CONFIG_LOGGER.error(f"{type(self).__name__} has no slot {key}")
        self.post_init(*args, **kwargs)

    def post_config(self, *args, **kwargs):
        pass

    def suppress_set(self) -> typing.Set[str]:
        return self._suppress

    def print_config(self):
        for conf_slot in self.Config.fields():
            logging.debug(f"{conf_slot} = {getattr(self.config, conf_slot)}")
        for dest_source in self._output_dests:
            logging.debug(f"{dest_source} -> {self._output_dests[dest_source]}")

    def reset_io(self):
        self._suppress.clear()
        self.old_inputs.reset_io()
        self.inputs.reset_io()
        self.outputs.reset_io()

    def flip_inputs(self):
        self.inputs, self.old_inputs = self.old_inputs, self.inputs
        self.inputs.reset_io()

    def reset_input(self):
        self.inputs.reset_io()

    def reset_output(self):
        self.outputs.reset_io()

    def output_slots(self):
        return self.outputs.instance_field_names()

    def input_slots(self):
        return self.inputs.instance_field_names()

    def config_slots(self):
        return self.config.instance_field_names()

    def process_inputs(self):
        for slot in self.inputs.instance_field_names():
            old_value = getattr(self.old_inputs, slot)
            new_value = getattr(self.inputs, slot)
            old_bool, new_bool = to_bool(old_value), to_bool(new_value)
            if old_bool != new_bool:
                if old_bool:
                    self.on_release(slot, new_value)
                else:
                    self.on_press(slot, new_value)
            else:
                self.on_update(slot, new_value)

    def set_input(self, slot: str, value):
        setattr(self.inputs, slot, getattr(self.inputs, slot) + value)

    def set_output(self, slot: str, value):
        setattr(self.outputs, slot, value)

    def get_input(self, slot: str):
        return getattr(self.inputs, slot)

    def get_output(self, slot: str):
        return getattr(self.outputs, slot)

    @classmethod
    def register_block_class(cls, block_type: str, type_obj: typing.Type):
        cls.Register.BLOCK_TYPES[block_type] = type_obj

    @classmethod
    def get_block_class(cls, block_type):
        return cls.Register.BLOCK_TYPES.get(block_type)

    @classmethod
    def parse_from_dict(cls, data: typing.Dict[str, typing.Any]):
        block_type = data.get("TYPE", None)
        if block_type == None:
            raise ValueError("Block has no type")
        block_class = ConfigBlock.get_block_class(block_type)
        if not block_class:
            raise ValueError(f"'{block_type}' is not a valid type")
        return block_class(data)

    def on_press(self, slot: str, slot_input):
        pass

    def on_release(self, slot: str, slot_input):
        pass

    def on_update(self, slot: str, slot_input):
        pass

    def process(self, delta_time: float = 0):
        pass

    def process_source_end(self, delta_time: float = 0):
        pass

    def on_load(self):
        pass

    def on_unload(self):
        pass

    def load(self):
        if not self._loaded:
            self.on_load()
            self._loaded = True

    def unload(self):
        if self._loaded:
            self.reset_io()
            self.on_unload()
            self._loaded = False

    def get_destinations(self, slot) -> typing.List[typing.Tuple[str, str]]:
        if slot in self.output_slots():
            dest = self._output_dests.get(slot)
            if not dest:
                return []
            elif isinstance(dest, str):
                dest_block, dest_slot = dest.split(".")
                return [(dest_block, dest_slot)]
            else:
                dests = []
                for dest_entry in dest:
                    dest_block, dest_slot = dest_entry.split(".")
                    dests.append((dest_block, dest_slot))
                return dests
        return []

    @classmethod
    def is_source(cls) -> bool:
        return False

    def processable(self) -> bool:
        return True

    def pre_init(self, *args, **kwargs):
        pass

    def post_init(self, *args, **kwargs):
        pass

    def activate(self):
        pass

    def deactivate(self):
        pass

    def __del__(self):
        self.deactivate()


# Some basic operator blocks


class Multiplier(ConfigBlock):
    class Inputs(PyroGyroBaseModel):
        IN: Vec2 | Vec3 | float = Vec2()

    class Outputs(PyroGyroBaseModel):
        OUT: Vec2 | Vec3 | float = Vec2()

    class Config(PyroGyroBaseModel):
        factor: float = 1

    def process(self, delta_time: float = 0):
        try:
            val = self.inputs.IN
            val = val * self.config.factor
            self.set_output("OUT", val)
        except Exception:
            pass


ConfigBlock.register_block_class("MULT", Multiplier)
