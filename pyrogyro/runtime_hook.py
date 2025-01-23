import sys
import importlib

# Really annoying fix, but seems to work fine.

def init(self):
    pass

sys.modules['sdl3.__init__.SDL'] = init
from sdl3 import SDL
sys.modules['sdl3.__init__.SDL'] = SDL
