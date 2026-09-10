import ctypes
import time
import math

import sdl3
import logging

from pyrogyro.constants import resource_location
from pyrogyro.platform_util import set_window_passthrough

"""
Overlay proof of concept. Uses windows-only platform specific code for enabling mouse passthrough, currently
ported from the PR for adding this support natively

See:
https://github.com/libsdl-org/SDL/issues/12683
https://github.com/libsdl-org/SDL/pull/14561
"""


class Overlay:
    def __init__(self):
        self.logger = logging.getLogger("Pyrogyro Overlay")
        win_name = ctypes.c_char_p(b"Pyrogyro Overlay")
        disp = sdl3.SDL_GetPrimaryDisplay()
        disp_mode = sdl3.SDL_GetCurrentDisplayMode(disp).contents

        screen_width = disp_mode.w
        screen_height = disp_mode.h
        self.window_ptr, self.renderer_ptr = (
            # The LP_ type hints are generated from docs, which fail in the pyinstaller distibutable.
            # Not too much of a pain to handle manually, for the moment.
            sdl3.SDL_POINTER[sdl3.SDL_Window](),
            sdl3.SDL_POINTER[sdl3.SDL_Renderer](),
        )

        success = sdl3.SDL_CreateWindowAndRenderer(
            win_name,
            screen_width,
            screen_height,
            sdl3.SDL_WINDOW_BORDERLESS
            | sdl3.SDL_WINDOW_TRANSPARENT
            | sdl3.SDL_WINDOW_ALWAYS_ON_TOP
            | sdl3.SDL_WINDOW_NOT_FOCUSABLE
            | sdl3.SDL_WINDOW_HIDDEN,
            self.window_ptr,
            self.renderer_ptr,
        )
        if not success:
            self.logger.debug("couldn't create window")
            return

        window = self.window_ptr.contents
        set_window_passthrough(window,True)

        sdl3.SDL_SetWindowRelativeMouseMode(window, True)
        sdl3.SDL_HideWindow(window)

        self.run = True
        self.hidden = True

    def toggle_hidden(self):
        self.hidden = not self.hidden
        window = self.window_ptr.contents
        if self.hidden:
            sdl3.SDL_HideWindow(window)
        else:
            sdl3.SDL_ShowWindow(window)

    def display_loop(self):
        window, renderer = self.window_ptr.contents, self.renderer_ptr.contents
        gHelloWorld = sdl3.SDL_LoadPNG(resource_location("test.png").encode())
        font = sdl3.TTF_OpenFont(resource_location("ttf/whitrabt.ttf").encode(), 20)
        text_engine = sdl3.TTF_CreateRendererTextEngine(renderer)
        text = sdl3.TTF_CreateText(text_engine, font, "Overlay Test :3".encode(), 0)
        sdl3.TTF_SetTextColor(text, 255, 255, 255, 255)
        tex = sdl3.SDL_CreateTextureFromSurface(renderer, gHelloWorld)

        src_rect = sdl3.SDL_FRect(0,0,100,100)
        dest_rec = sdl3.SDL_FRect(0,0,100,100)
        
        src_rect_ptr = sdl3.SDL_POINTER[sdl3.SDL_FRect](src_rect)
        dest_rec_ptr = sdl3.SDL_POINTER[sdl3.SDL_FRect](dest_rec)

        center = 0, 0
        step = 0
        rad = 100

        event = sdl3.SDL_Event()
        while self.run:
            sdl3.SDL_SetRenderDrawColor(renderer, 0, 0, 0, 0)
            sdl3.SDL_RenderClear(renderer)
            rads = math.radians(step)
            x_pos = center[0] + rad * math.cos(rads)
            y_pos = center[1] + rad * math.sin(rads)
            
            dest_rec.x = x_pos
            dest_rec.y = y_pos
            sdl3.SDL_RenderTexture(
                renderer, tex, src_rect_ptr, dest_rec_ptr
            )

            sdl3.TTF_DrawRendererText(text, x_pos, y_pos)

            mouse_x, mouse_y = ctypes.c_float(0), ctypes.c_float(0)
            mouse_x_pointer, mouse_y_pointer = (
                sdl3.SDL_POINTER[ctypes.c_float](mouse_x),
                sdl3.SDL_POINTER[ctypes.c_float](mouse_y),
            )
            sdl3.SDL_GetGlobalMouseState(mouse_x_pointer, mouse_y_pointer)
            pix_x, pix_y = int(mouse_x.value), int(mouse_y.value)
            mouse_point = sdl3.SDL_Point(pix_x, pix_y)
            display_no = sdl3.SDL_GetDisplayForPoint(mouse_point)

            screen_rect = sdl3.SDL_Rect(0, 0, 0, 0)
            sdl3.SDL_GetDisplayBounds(display_no, screen_rect)

            center = pix_x - screen_rect.x, pix_y - screen_rect.y

            sdl3.SDL_SetWindowSize(window, screen_rect.w, screen_rect.h)
            sdl3.SDL_SetWindowPosition(window, screen_rect.x, screen_rect.y)

            sdl3.SDL_RenderPresent(renderer)
            step = (step + 1) % 360
            sdl3.SDL_Delay(10)
