import importlib
import sys
from pathlib import Path

import pyrogyro.constants

# Really annoying fix, but seems to work fine.


def init(self):
    pass


sys.modules["sdl3.__init__.SDL"] = init
from sdl3 import SDL

sys.modules["sdl3.__init__.SDL"] = SDL

# correct root dir for bundled EXE
pyrogyro.constants.ROOT_DIR = Path(__file__).parent
