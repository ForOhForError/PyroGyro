from pydantic import BaseModel, Field
import typing
import logging
import vgamepad as vg
import tomlkit

from functools import cache

CONFIG_LOGGER = logging.getLogger("Config")

class Config:
    def __init__(self, data):
        self.blocks = {}
        self.name = data.get("name", "PyroGyro Config")
        self.autoload = data.get("autoload", True)
        self.autoload_exe_name = data.get("autoload_exe_name", self.name)
        self.autoload_window_name = data.get("autoload_window_name", self.name)
        for key, value in data.items():
            if isinstance(value, dict):
                block = ConfigBlock.parse_from_dict(value)
                self.blocks[key] = block

    def __str__(self):
        return f"{type(self).__name__}({self.name}: {len(self.blocks)} blocks)"

    @classmethod
    def load_from_file(cls, file_handle):
        parsed_from_file = tomlkit.load(file_handle)
        return cls(parsed_from_file)

class ConfigBlock:
    class Register:
        BLOCK_TYPES: typing.Dict[str, type] = {}

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

    @classmethod
    def is_source(cls) -> bool:
        return False

    @classmethod
    @cache
    def _input_slots(cls) -> typing.List[str]:
        return cls.input_slots()
    
    @classmethod
    def input_slots(cls) -> typing.List[str]:
        return []
    
    @classmethod
    @cache
    def _output_slots(cls) -> typing.List[str]:
        return cls.output_slots()
    
    @classmethod
    def output_slots(cls) -> typing.List[str]:
        return []
    
    @classmethod
    @cache
    def _config_slots(cls) -> typing.List[str]:
        return cls.config_slots()
    
    @classmethod
    def config_slots(cls) -> typing.List[str]:
        return []

    def __setitem__(self, key, val):
        if key in self._input_slots() or key in self._config_slots():
            setattr(self, key, val)
        elif key in self._output_slots():
            setattr(self, key, val)
        else:
            raise KeyError(f"{type(self).__name__} has no assignable slot {key}")

    def __getitem__(self, key, default=None):
        if key in self._input_slots() or key in self._config_slots():
            if hasattr(self, key):
                return getattr(self, key)
            else:
                return default
        else:
            raise KeyError(f"{type(self).__name__} has no readable slot {key}")

    def pre_init(self, *args, **kwargs):
        pass
    
    def post_init(self, *args, **kwargs):
        pass

    def __init__(self, data: typing.Dict[str, typing.Any], *args, **kwargs):
        self.pre_init(*args, **kwargs)
        for key in data:
            if key == "TYPE":
                pass
            elif key in self._output_slots():
                try:
                    self[key] = data[key]
                except ValueError:
                    CONFIG_LOGGER.exception("Error setting slot")
            elif key in self._input_slots() or key in self._config_slots():
                try:
                    self[key] = data[key]
                except ValueError:
                    CONFIG_LOGGER.exception("Error setting slot")
            else:
                CONFIG_LOGGER.error(f"{type(self).__name__} has no slot {key}")
        self.post_init(*args, **kwargs)