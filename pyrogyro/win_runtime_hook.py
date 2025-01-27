import logging
from pathlib import Path

import pyrogyro.constants

# Correct root dir for bundled EXE
pyrogyro.constants.ROOT_DIR = Path(__file__).parent
pyrogyro.constants.DEBUG = False
pyrogyro.constants.LOG_LEVEL = logging.INFO
