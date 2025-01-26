import enum
import logging
from pathlib import Path

import sdl3

ROOT_DIR = Path(__file__).parent.parent
DEBUG = True
LOG_LEVEL = logging.DEBUG
LOG_FORMAT = "%(message)s"
LOG_FORMAT_DEBUG = "%(relativeCreated)6d  %(threadName)s | %(filename)s:%(lineno)d | %(name)s - %(levelname)s | %(message)s"


def icon_location():
    return (ROOT_DIR / "res" / "pyrogyro.ico").as_posix()


class SDLButtonEnum(enum.Enum):
    INVALID = sdl3.SDL_GAMEPAD_BUTTON_INVALID
    SOUTH = sdl3.SDL_GAMEPAD_BUTTON_SOUTH
    EAST = sdl3.SDL_GAMEPAD_BUTTON_EAST
    WEST = sdl3.SDL_GAMEPAD_BUTTON_WEST
    NORTH = sdl3.SDL_GAMEPAD_BUTTON_NORTH
    BACK = sdl3.SDL_GAMEPAD_BUTTON_BACK
    GUIDE = sdl3.SDL_GAMEPAD_BUTTON_GUIDE
    START = sdl3.SDL_GAMEPAD_BUTTON_START
    LEFT_STICK = sdl3.SDL_GAMEPAD_BUTTON_LEFT_STICK
    RIGHT_STICK = sdl3.SDL_GAMEPAD_BUTTON_RIGHT_STICK
    LEFT_SHOULDER = sdl3.SDL_GAMEPAD_BUTTON_LEFT_SHOULDER
    RIGHT_SHOULDER = sdl3.SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER
    DPAD_UP = sdl3.SDL_GAMEPAD_BUTTON_DPAD_UP
    DPAD_DOWN = sdl3.SDL_GAMEPAD_BUTTON_DPAD_DOWN
    DPAD_LEFT = sdl3.SDL_GAMEPAD_BUTTON_DPAD_LEFT
    DPAD_RIGHT = sdl3.SDL_GAMEPAD_BUTTON_DPAD_RIGHT
    MISC1 = sdl3.SDL_GAMEPAD_BUTTON_MISC1
    RIGHT_PADDLE1 = sdl3.SDL_GAMEPAD_BUTTON_RIGHT_PADDLE1
    LEFT_PADDLE1 = sdl3.SDL_GAMEPAD_BUTTON_LEFT_PADDLE1
    RIGHT_PADDLE2 = sdl3.SDL_GAMEPAD_BUTTON_RIGHT_PADDLE2
    LEFT_PADDLE2 = sdl3.SDL_GAMEPAD_BUTTON_LEFT_PADDLE2
    TOUCHPAD = sdl3.SDL_GAMEPAD_BUTTON_TOUCHPAD
    MISC2 = sdl3.SDL_GAMEPAD_BUTTON_MISC2
    MISC3 = sdl3.SDL_GAMEPAD_BUTTON_MISC3
    MISC4 = sdl3.SDL_GAMEPAD_BUTTON_MISC4
    MISC5 = sdl3.SDL_GAMEPAD_BUTTON_MISC5
    MISC6 = sdl3.SDL_GAMEPAD_BUTTON_MISC6
    COUNT = sdl3.SDL_GAMEPAD_BUTTON_COUNT
