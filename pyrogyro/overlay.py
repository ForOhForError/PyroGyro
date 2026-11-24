import ctypes
import time
import math

import sdl3
import logging

import pyrogyro.pyrogyro

from pyrogyro.constants import resource_location, OVERLAY_FPS_SHOWN, OVERLAY_FPS_HIDDEN
from pyrogyro.platform_util import set_window_passthrough

from queue import Queue, Empty

"""
Overlay proof of concept. Uses windows-only platform specific code for enabling mouse passthrough, currently
ported from the PR for adding this support natively

See:
https://github.com/libsdl-org/SDL/issues/12683
https://github.com/libsdl-org/SDL/pull/14561
"""

NS_PER_SECOND = 1000000000
CIRCLE_SIZE = 30
FONT_SIZE = 20

TEXT_FADE_TIME = 1
TEXT_FADE_AFTER = 4


def get_text_alpha(lifetime_seconds: float):
    if lifetime_seconds >= TEXT_FADE_AFTER:
        alpha = 1 - ((lifetime_seconds - TEXT_FADE_AFTER) / TEXT_FADE_TIME)
        if alpha <= 0:
            return 0
        else:
            return int(255 * alpha)
    else:
        return 255


class Overlay:
    def __init__(self):
        self.logger = logging.getLogger("Pyrogyro Overlay")
        self.fps_target = OVERLAY_FPS_HIDDEN
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

        self.log_texts = []
        self.log_queue = Queue()

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

        self.init_assets()

    def init_assets(self):
        self.textures = {}
        renderer = self.renderer_ptr.contents
        self.textures["circle"] = sdl3.IMG_LoadTexture(
            renderer, resource_location("test.png").encode()
        )
        self.font = sdl3.TTF_OpenFont(
            resource_location("ttf/whitrabt.ttf").encode(), FONT_SIZE
        )
        self.font_emoji = sdl3.TTF_OpenFont(
            resource_location("ttf/notoemoji.ttf").encode(), FONT_SIZE
        )
        sdl3.TTF_AddFallbackFont(self.font, self.font_emoji)
        self.text_engine = sdl3.TTF_CreateRendererTextEngine(renderer)

    def log_to_overlay(self, text, color=(255, 255, 255)):
        self.log_queue.put((text, color))

    def read_log_queue(self):
        now = time.time_ns()
        try:
            while True:
                text, color = self.log_queue.get_nowait()
                self.log_texts.append(
                    (
                        sdl3.TTF_CreateText(
                            self.text_engine, self.font, text.encode(), 0
                        ),
                        color,
                        now,
                    )
                )
        except Empty:
            pass

    def set_hidden(self, hidden: bool):
        if hidden != self.hidden:
            self.hidden = hidden
            window = self.window_ptr.contents
            if self.hidden:
                self.fps_target = OVERLAY_FPS_HIDDEN
                sdl3.SDL_HideWindow(window)
                set_window_passthrough(window, False)
            else:
                self.fps_target = OVERLAY_FPS_SHOWN
                sdl3.SDL_ShowWindow(window)
                set_window_passthrough(window, True)

    def toggle_hidden(self):
        self.set_hidden(not self.hidden)

    def display_loop(self):
        window, renderer = self.window_ptr.contents, self.renderer_ptr.contents

        src_rect = sdl3.SDL_FRect(0, 0, 100, 100)
        dest_rec = sdl3.SDL_FRect(0, 0, CIRCLE_SIZE, CIRCLE_SIZE)

        src_rect_ptr = sdl3.SDL_POINTER[sdl3.SDL_FRect](src_rect)
        dest_rec_ptr = sdl3.SDL_POINTER[sdl3.SDL_FRect](dest_rec)

        center = 0, 0
        step = 0
        rad = 100

        start_time = time.time_ns()
        while self.run:
            self.read_log_queue()
            new_time = time.time_ns()
            ns_per_poll = int(NS_PER_SECOND / self.fps_target)
            delta_time = new_time - start_time
            start_time = new_time
            sdl3.SDL_SetRenderDrawColor(renderer, 0, 0, 0, 0)
            sdl3.SDL_RenderClear(renderer)
            screen_rect = sdl3.SDL_Rect(0, 0, 0, 0)
            mouse_x, mouse_y = ctypes.c_float(0), ctypes.c_float(0)
            mouse_x_pointer, mouse_y_pointer = (
                sdl3.SDL_POINTER[ctypes.c_float](mouse_x),
                sdl3.SDL_POINTER[ctypes.c_float](mouse_y),
            )
            sdl3.SDL_GetGlobalMouseState(mouse_x_pointer, mouse_y_pointer)
            pix_x, pix_y = int(mouse_x.value), int(mouse_y.value)
            mouse_point = sdl3.SDL_Point(pix_x, pix_y)
            display_no = sdl3.SDL_GetDisplayForPoint(mouse_point)
            sdl3.SDL_GetDisplayBounds(display_no, screen_rect)

            sdl3.SDL_SetWindowSize(window, screen_rect.w, screen_rect.h)
            sdl3.SDL_SetWindowPosition(window, screen_rect.x, screen_rect.y)

            # Render application
            pyrogyro.pyrogyro.PyroGyroMapper.instance().render(
                renderer, screen_rect.w, screen_rect.h, delta_time
            )

            # Render log lines
            line_y = 5.0
            font_size = float(sdl3.TTF_GetFontSize(self.font))
            for log_line in self.log_texts[:]:
                log_text, color, life_begin = log_line
                alpha = get_text_alpha((new_time - life_begin) / NS_PER_SECOND)
                if alpha == 0:
                    self.log_texts.remove(log_line)
                    sdl3.TTF_DestroyText(log_text)
                else:
                    # self.set_hidden(False)
                    sdl3.TTF_SetTextColor(log_text, color[0], color[1], color[2], alpha)
                    sdl3.TTF_DrawRendererText(log_text, 5, int(line_y))
                    line_y += (font_size + 3) * log_text.contents.num_lines

            # Render test pattern
            step += 60 * delta_time / NS_PER_SECOND
            step %= 360
            rads = math.radians(step)
            center = pix_x - screen_rect.x, pix_y - screen_rect.y
            x_pos = center[0] - CIRCLE_SIZE / 2 + rad * math.cos(rads)
            y_pos = center[1] - CIRCLE_SIZE / 2 + rad * math.sin(rads)
            dest_rec.x = x_pos
            dest_rec.y = y_pos
            sdl3.SDL_RenderTexture(
                renderer, self.textures["circle"], src_rect_ptr, dest_rec_ptr
            )

            sdl3.SDL_RenderPresent(renderer)

            poll_ns = time.time_ns() - start_time
            sdl3.SDL_DelayNS(ns_per_poll - poll_ns)
