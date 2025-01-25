import os
from pathlib import Path

import pyrogyro.constants

# Correct root dir for bundled EXE
pyrogyro.constants.ROOT_DIR = Path(__file__).parent
