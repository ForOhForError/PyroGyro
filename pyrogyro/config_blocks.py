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

    def get_value(self, block, slot):
        b = self.blocks.get(block)
        if b:
            return b[slot]
        else:
            return None

    @classmethod
    def load_from_file(cls, file_handle):
        parsed_from_file = tomlkit.load(file_handle)
        return cls(parsed_from_file)
    
    def resolve(self):
        # event_queue = [("pad", "N", True)]
        # for event in event_queue:
        #     block, slot, value = event
        #     b = self.blocks.get(block)
        #     if b:
        #         b[slot] = value
        for block in self.get_resolution_order():
            for slot in block.output_slots():
                if block[slot]:
                    output_value = block@slot
                    for dest_name, dest_slot in block.get_destinations(slot):
                        dest = self.blocks.get(dest_name)
                        if dest:
                            dest[dest_slot] = output_value
    
    def get_resolution_order(self) -> list['ConfigBlock']:
        order = []
        visit = set()
        done = set()
        
        for block in self.blocks.values():
            if block.is_source():
                order.append(block)
                visit.add(block)
        
        while len(visit) > 0:
            next = visit.pop()
            for slot in next.output_slots():
                for block_name, slot_name in next.get_destinations(slot):
                    logging.info(f"{slot}->{block_name}.{slot_name}")
                    block = self.blocks.get(block_name)
                    logging.info(f"checking {block}")
                    if block and (block not in done) and (block not in visit):
                        logging.info(f"visiting {block_name}")
                        visit.add(block)
                        order.append(block)
            done.add(next)
        return order

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

    def __matmul__(self, slot):
        if slot in self.output_slots():
            return self.get_output_value(slot)
        else:
            raise KeyError(f"No output slot {slot}")

    def get_output_value(self, slot) -> typing.Any:
        return None

    def get_destinations(self, slot) -> typing.List[typing.Tuple[str,str]]:
        if slot in self._output_slots():
            dest = self[slot]
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

    def __getitem__(self, key):
        if key in self._input_slots() or key in self._config_slots() or key in self._output_slots():
            if hasattr(self, key):
                return getattr(self, key)
            else:
                return None
        else:
            raise KeyError(f"{type(self).__name__} has no readable slot {key}")

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