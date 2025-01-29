import logging
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
DEBUG = True
LOG_LEVEL = logging.DEBUG
LOG_FORMAT = "%(message)s"
LOG_FORMAT_DEBUG = "%(relativeCreated)6d  %(threadName)s | %(filename)s:%(lineno)d | %(name)s - %(levelname)s | %(message)s"

DEFAULT_CONFIG_FILE = "configs/xbox.yml"

VID_PID_IGNORE_LIST = ((1118, 654),)  # Ignore ViGEmBus-mapped virtual devices

SHOW_STARTUP_VERSION_MODULES = ("pyrogyro", "pysdl3")


def icon_location():
    return (ROOT_DIR / "res" / "pyrogyro.ico").as_posix()
