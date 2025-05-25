import ctypes
import time

from sdl3 import *


def main():

    win_name = ctypes.c_char_p(b"Hello GL")

    SDL_Init(SDL_INIT_VIDEO)

    disp = SDL_GetPrimaryDisplay()
    disp_mode = SDL_GetCurrentDisplayMode(disp).contents

    screen_width = disp_mode.w
    screen_height = disp_mode.h

    box = SDL_Rect(0, 0, screen_width, screen_height)
    boxptr = LP_SDL_Rect(box)
    box_inner = SDL_Rect(1, 1, screen_width - 2, screen_height - 2)
    boxptr_inner = LP_SDL_Rect(box_inner)

    box2 = SDL_FRect(64, 64, 64, 64)
    boxptr2 = LP_SDL_FRect(box)

    window = SDL_CreateWindow(
        win_name,
        screen_width,
        screen_height,
        SDL_WINDOW_BORDERLESS \
        | SDL_WINDOW_TRANSPARENT \
        | SDL_WINDOW_ALWAYS_ON_TOP,
    )
    
    renderer = SDL_CreateRenderer(window, win_name);
    shape = SDL_CreateSurface(screen_width, screen_height, SDL_PIXELFORMAT_RGBA8888)
    screen_surface = SDL_GetWindowSurface(window)
    gHelloWorld = SDL_LoadBMP( b"res/test.bmp" )
    SDL_BlitSurface(gHelloWorld, None, screen_surface, None)
    SDL_FillSurfaceRect(shape, boxptr, 0xFFFFFFFF);
    SDL_FillSurfaceRect(shape, boxptr_inner, 0x00000000);
    tex = SDL_CreateTextureFromSurface(renderer, shape);
    SDL_RenderTexture(renderer, tex, None, None)
    SDL_SetWindowShape(window, screen_surface)
    SDL_UpdateWindowSurface(window)
    
    #SDL_HideWindow(window)
    #SDL_ShowWindow(window)

    start = time.time()
    run = True

    event = SDL_Event()
    try:
        while run:
            while SDL_PollEvent(event):
                pass
            SDL_Delay(100)
            
    except KeyboardInterrupt:
        pass
    SDL_Quit()


if __name__ == "__main__":
    main()
