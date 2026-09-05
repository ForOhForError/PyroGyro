from pydantic import BaseModel, Field
import typing
import logging
import vgamepad as vg

from functools import cache

CONFIG_LOGGER = logging.getLogger("Config")


def parse_block(data: typing.Dict[str, typing.Any]):
    block_type = data.get("TYPE", None)
    if block_type == None:
        raise ValueError("Block has no type")
    block_class = ConfigBlock.get_block_class(block_type)
    if not block_class:
        raise ValueError(f"'{block_type}' is not a valid type")
    return block_class(data)


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
    @cache
    def slots(cls) -> typing.List[str]:
        return []

    def __setitem__(self, key, val):
        if key in self.slots():
            setattr(self, key, val)
        else:
            raise KeyError(f"{type(self).__name__} has no slot {key}")

    def __getitem__(self, key, default=None):
        if key in self.slots():
            if hasattr(self, key):
                return getattr(self, key)
            else:
                return default
        else:
            raise KeyError(f"{type(self).__name__} has no slot {key}")

    def __init__(self, data: typing.Dict[str, typing.Any]):
        for key in data:
            if key == "TYPE":
                pass
            elif key in self.slots():
                try:
                    self[key] = data[key]
                except ValueError:
                    CONFIG_LOGGER.exception("Error setting slot")
            else:
                CONFIG_LOGGER.error(f"{type(self).__name__} has no slot {key}")


class TestBlock(ConfigBlock):
    @classmethod
    @cache
    def slots(cls) -> typing.List[str]:
        return ["test_slot"]


if __name__ == "__main__":
    ConfigBlock.register_block_class("test", TestBlock)
    logging.basicConfig(level=logging.DEBUG)
    data = {"TYPE": "test", "test_slot": "bonk"}
    i = parse_block(data)
    print(i, i["test_slot"])
