import ctypes
import time
import math

import sdl3
import logging

"""
Overlay testing ground for future visible virtual menu stuff

currently we have to do some juggling to set the window shape every time it changes, and there's no way to make
rendered parts of the window be clickthrough with normal SDL calls. There's theoretically a solution for this in the works,
but it's not presently merged and is only slated for eventual implementation.

See:
https://github.com/libsdl-org/SDL/issues/12683

For the moment this is solved by punching a single pixel out of the buffer at the mouse position. This objectively sucks, but seems
to work mostly fine.
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
            sdl3.LP_SDL_Window(),
            sdl3.LP_SDL_Renderer(),
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
        gHelloWorld = sdl3.SDL_LoadPNG(b"res/test.png")
        font = sdl3.TTF_OpenFont(b"res/ttf/whitrabt.ttf", 20)
        text_engine = sdl3.TTF_CreateSurfaceTextEngine()
        text = sdl3.TTF_CreateText(text_engine, font, "Overlay Test :3".encode(), 0)
        sdl3.TTF_SetTextColor(text, 255, 255, 255, 255)
        tex = sdl3.SDL_CreateTextureFromSurface(renderer, gHelloWorld)
        screen_surface = sdl3.SDL_GetWindowSurface(window)

        center = 0, 0
        step = 0
        rad = 100

        event = sdl3.SDL_Event()
        while self.run:
            while sdl3.SDL_PollEvent(event):
                pass
            sdl3.SDL_ClearSurface(screen_surface, 0, 0, 0, 0)
            rads = math.radians(step)
            x_pos = center[0] + rad * math.cos(rads)
            y_pos = center[1] + rad * math.sin(rads)
            sdl3.SDL_BlitSurface(
                gHelloWorld, None, screen_surface, sdl3.SDL_Rect(int(x_pos), int(y_pos))
            )

            sdl3.TTF_DrawSurfaceText(text, int(x_pos), int(y_pos), screen_surface)

            mouse_x, mouse_y = ctypes.c_float(0), ctypes.c_float(0)
            mouse_x_pointer, mouse_y_pointer = (
                sdl3.LP_c_float(mouse_x),
                sdl3.LP_c_float(mouse_y),
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

            sdl3.SDL_WriteSurfacePixel(
                screen_surface, pix_x - screen_rect.x, pix_y - screen_rect.y, 0, 0, 0, 0
            )

            sdl3.SDL_SetWindowShape(window, screen_surface)

            sdl3.SDL_UpdateWindowSurface(window)
            step = (step + 1) % 360
            sdl3.SDL_Delay(10)
