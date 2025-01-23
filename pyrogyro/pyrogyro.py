# https://github.com/yannbouteiller/vgamepad?tab=readme-ov-file#getting-started
# https://github.com/Aermoss/PySDL3/blob/main/sdl3/SDL_joystick.py
# https://wiki.libsdl.org/SDL3/APIByCategory

import ctypes
import vgamepad as vg
import sdl3
import uuid

from pathlib import Path

import time

import sys

from infi.systray import SysTrayIcon

kernel32 = ctypes.WinDLL('kernel32')
user32 = ctypes.WinDLL('user32')
import threading

import pyautogui


def init_sdl():
    sdl3.SDL_SetHint(sdl3.SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS.encode(), "1".encode())
    sdl3.SDL_Init(sdl3.SDL_INIT_GAMEPAD)
    
def get_gamepads(vpads=[], ignore_virtual=True):
    ignore_list = set(( (vpad.get_vid(), vpad.get_pid()) for vpad in vpads))
    joystick_ids = sdl3.SDL_GetGamepads(None)
    joysticks = []

    joy_ix = 0
    while joystick_ids[joy_ix] != 0:
        joystick_id = joystick_ids[joy_ix]
        
        pid = sdl3.SDL_GetJoystickProductForID(joystick_id)
        vid = sdl3.SDL_GetJoystickVendorForID(joystick_id)
        print(pid, vid)
        is_virtual = (vid, pid) in ignore_list
        joystick_name = sdl3.SDL_GetJoystickNameForID(joystick_id).decode()
        joystick_uuid_bytes = sdl3.SDL_GetGamepadGUIDForID(joystick_id).data[0:16]
        joystick_uuid = uuid.UUID(bytes=bytes(joystick_uuid_bytes))
        if not (ignore_virtual and is_virtual):
            joysticks.append([joystick_id, joystick_uuid, joystick_name])
        
        print(f"{joystick_name} ({joystick_uuid}) {'(Virtual)' if is_virtual else ''}")
        joy_ix += 1
    sdl3.SDL_free(joystick_ids)
    return joysticks

VISIBLE = 1

GAMEPADS = []

RUN = True

def input_poll(joy_id):
    global RUN
    pad = sdl3.SDL_OpenGamepad(joy_id)
    print(f"using pad: {sdl3.SDL_GetGamepadName(pad).decode()}")
    while RUN:
        sdl3.SDL_UpdateGamepads()
        if sdl3.SDL_GetGamepadButton(pad, sdl3.SDL_GAMEPAD_BUTTON_SOUTH):
            x,y = pyautogui.position()
            pyautogui.moveTo(x, y+1)
        time.sleep(1.0/100.0)

def appmain(*args, **kwargs):
    global RUN
    global GAMEPADS
    
    kernel32.SetConsoleTitleW("PyroGyro Console")
    
    def on_quit_callback(systray):
        pass
    
    def toggle_vis(systray):
        global VISIBLE
        print(VISIBLE)
        VISIBLE = (VISIBLE+1)%2
        hWnd = kernel32.GetConsoleWindow()
        user32.ShowWindow(hWnd, VISIBLE)
    
    menu_options = (('Toggle Console', None, toggle_vis),)

    icon_path = (Path(__file__).parent / "res" / "pyrogyro.ico").as_posix()
    
    with SysTrayIcon(icon_path, "PyroGyro", menu_options, on_quit=on_quit_callback) as systray:
        init_sdl()

        gamepad = vg.VX360Gamepad()
        time.sleep(1)
        GAMEPADS.append(gamepad)
        pads = get_gamepads(vpads=GAMEPADS)
        print(pads)
        
        if pads:
            t1 = threading.Thread(target=input_poll, args=(pads[0][0],))
            t1.start()
        else:
            t1 = None

        while RUN:
            try:
                command = input("> ")
                print(command)
            except KeyboardInterrupt:
                RUN = False
                break
        
        if t1:
            t1.join()

def map_inputs():
    pass

if __name__ == "__main__":
    appmain(sys.argv)