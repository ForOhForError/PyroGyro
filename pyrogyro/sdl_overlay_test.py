import ctypes
import time
import math

from sdl3 import *

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

def main():
    win_name = ctypes.c_char_p(b"Hello GL")

    SDL_SetHint(SDL_HINT_VIDEO_DOUBLE_BUFFER, "1".encode())
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
    
    window_ptr, renderer_ptr = LP_SDL_Window(), LP_SDL_Renderer()

    success = SDL_CreateWindowAndRenderer(
        win_name,
        screen_width,
        screen_height,
        SDL_WINDOW_BORDERLESS | SDL_WINDOW_TRANSPARENT | SDL_WINDOW_ALWAYS_ON_TOP | SDL_WINDOW_NOT_FOCUSABLE | SDL_WINDOW_HIDDEN,
        window_ptr,
        renderer_ptr
    )
    if not success:
        print("couldn't create window")
        return
    
    window, renderer = window_ptr.contents, renderer_ptr.contents
    
    SDL_SetWindowRelativeMouseMode(
        window, True
    )

    screen_surface = SDL_GetWindowSurface(window)
    gHelloWorld = SDL_LoadPNG(b"res/test.png")
    tex = SDL_CreateTextureFromSurface(renderer, gHelloWorld);
    

    # SDL_HideWindow(window)
    SDL_ShowWindow(window)

    start = time.time()
    run = True

    center = 0,0
    step = 0
    rad = 100
    
    hidden = False
    do_hidden_toggle = False

    event = SDL_Event()
    try:
        while run:
            while SDL_PollEvent(event):
                pass
            SDL_ClearSurface(screen_surface, 0, 0, 0, 0)
            rads = math.radians(step)
            x_pos = center[0] + rad * math.cos(rads)
            y_pos = center[1] + rad * math.sin(rads)
            SDL_BlitSurface(gHelloWorld, None, screen_surface, SDL_Rect(int(x_pos),int(y_pos)))
            
            
            mouse_x, mouse_y = ctypes.c_float(0), ctypes.c_float(0)
            mouse_x_pointer, mouse_y_pointer = LP_c_float(mouse_x), LP_c_float(mouse_y)
            SDL_GetGlobalMouseState(mouse_x_pointer, mouse_y_pointer)
            pix_x, pix_y = int(mouse_x.value), int(mouse_y.value)
            mouse_point = SDL_Point(pix_x, pix_y)
            display_no = SDL_GetDisplayForPoint(mouse_point)
            
            screen_rect = SDL_Rect(0, 0, 0, 0)
            SDL_GetDisplayBounds(display_no, screen_rect)
            
            center = screen_rect.w//2,screen_rect.h//2
            
            SDL_SetWindowSize(window, screen_rect.w, screen_rect.h)
            SDL_SetWindowPosition(window, screen_rect.x, screen_rect.y)
            
            SDL_WriteSurfacePixel(screen_surface, pix_x-screen_rect.x, pix_y-screen_rect.y, 0, 0, 0, 0)
            
            
            SDL_SetWindowShape(window, screen_surface)
            
            SDL_UpdateWindowSurface(window)
            if do_hidden_toggle and step == 359:
                hidden = not hidden
                if hidden:
                    SDL_HideWindow(window)
                else:
                    SDL_ShowWindow(window)
            step = (step+1) % 360
            SDL_Delay(10)
            

    except KeyboardInterrupt:
        pass
    SDL_Quit()


if __name__ == "__main__":
    main()
