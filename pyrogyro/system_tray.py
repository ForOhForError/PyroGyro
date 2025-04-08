import ctypes
import threading

import sdl3

class SystemTray:
    def __init__(self, title: str, icon_path: str):
        self.title = title
        self.icon = None
        self.ready = False
        if icon_path:
            self._load_icon(icon_path)
        self.tray = None
        self.init_tray()
        while not self.ready:
            sdl3.SDL_DelayNS(100)
        self.callbacks = {}

    def init_tray(self):
        title_p = ctypes.c_char_p(self.title.encode())
        self.tray = sdl3.SDL_CreateTray(self.icon, title_p)
        self.menu = sdl3.SDL_CreateTrayMenu(self.tray)
        self.ready = True

    def _load_icon(self, icon_path: str):
        icon_path = ctypes.c_char_p(icon_path.encode())
        self.icon = sdl3.IMG_Load(icon_path)

    def add_menu_option(
        self, option_text, callback=None, userdata=None, checkbox=False
    ):
        option_text_p = ctypes.c_char_p(option_text.encode())
        entry_type = (
            sdl3.SDL_TRAYENTRY_CHECKBOX if checkbox else sdl3.SDL_TRAYENTRY_BUTTON
        )
        entry = sdl3.SDL_InsertTrayEntryAt(self.menu, -1, option_text_p, entry_type)
        if callback:
            callback = sdl3.SDL_TrayCallback(callback)
            sdl3.SDL_SetTrayEntryCallback(entry, callback, userdata)
            self.callbacks[option_text] = callback

    def shutdown(self):
        if self.tray:
            sdl3.SDL_DestroyTray(self.tray)
            self.tray = None
        if self.icon:
            sdl3.SDL_DestroySurface(self.icon)
            self.icon = None

    def update(self):
        sdl3.SDL_GET_BINARY(sdl3.SDL_BINARY).SDL_UpdateTrays()

    def __del__(self):
        self.shutdown()
