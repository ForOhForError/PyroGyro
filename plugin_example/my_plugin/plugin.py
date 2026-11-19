from dataclasses import dataclass
from pyrogyro.config_blocks import ConfigBlock, PyroGyroBaseModel

import logging


class PluginBlock(ConfigBlock):
    @dataclass
    class Inputs(PyroGyroBaseModel):
        IN: float = 0

    def on_press(self, slot: str, slot_input):
        logging.info(f"Pressed with value {self.inputs.IN}")


def init_plugin():
    ConfigBlock.register_block_class("PLUGIN_BLOCK", PluginBlock)
