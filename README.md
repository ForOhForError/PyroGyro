# PyroGyro

Yet Another (Gyro) Gamepad Mapper, written in Python for hackability.

## Usage

Requires [ViGEmBus](https://github.com/nefarius/ViGEmBus) installed on a Windows system. May do cross-platform, we'll see.

At the moment, PyroGyro reads non-virtual gamepads using SDL3, and can output either to Virtual Xbox controllers (1 created per gamepad) or to keyboard/mouse.

It supports hotplugged devices, and autoloads configuration files as necessary.

## Config format

Configs are currently specified as a yaml (.yml) file.

Each config has a name, autoload settings, button mappings, and gyro settings.

Some example config files are listed below.

Note that autoloading will only check files in the `configs/` directory (though it will check sub-directories)

Example: Map all controllers to xbox mappings, on any window

```yaml
name: Default Xbox Controller
# if autoload is not in the config, or if it is left blank, a config won't be loaded at all. Currently it will match all windows on any controller, but will be overridden by more specific configs
autoload:
  match_exe_name: .*
  match_window_name: .*
  match_controller_name: .*
mapping:
  N: XUSB_GAMEPAD_Y
  S: XUSB_GAMEPAD_A
  E: XUSB_GAMEPAD_B
  W: XUSB_GAMEPAD_X
  BACK: XUSB_GAMEPAD_BACK
  START: XUSB_GAMEPAD_START
  UP: XUSB_GAMEPAD_DPAD_UP
  DOWN: XUSB_GAMEPAD_DPAD_DOWN
  LEFT: XUSB_GAMEPAD_DPAD_LEFT
  RIGHT: XUSB_GAMEPAD_DPAD_RIGHT
  L1: XUSB_GAMEPAD_LEFT_SHOULDER
  R1: XUSB_GAMEPAD_RIGHT_SHOULDER
  L3: XUSB_GAMEPAD_LEFT_THUMB
  R3: XUSB_GAMEPAD_RIGHT_THUMB
  GUIDE: XUSB_GAMEPAD_GUIDE
  L2: XUSB_GAMEPAD_L2
  R2: XUSB_GAMEPAD_R2
  LSTICK: XUSB_GAMEPAD_LSTICK
  RSTICK: XUSB_GAMEPAD_RSTICK
```

Example: Map a controller called "PS4 Controller" to player space gyro controls when on the desktop

```yaml
name: Gyro on Desktop
autoload:
  match_exe_name: explorer.exe
  match_window_name: .*
  match_controller_name: PS4 Controller
mapping:
  L2: RMOUSE
  R2: LMOUSE
  # Literally keyboard input
  N: N
  E: E
  S: S
  W: W
gyro:
  mode: 
    # supported modes are LOCAL, LOCAL_OW, WORLD, PLAYER_TURN, PLAYER_LEAN, and (of course) OFF
    gyro_mode: PLAYER_TURN
    # gyro sens is a litte off at the moment, 
    # as it applies it directly to the mouse gyro camera output
    gyro_sens: 2 
```

## Development

You'll need [Poetry](https://python-poetry.org/) and a working Python environment (3.11 and up)

* Clone the repo:  
 `git clone https://github.com/ForOhForError/PyroGyro`
* Install dependencies:  
 `poetry install --with=dev`  
 (should pull Windows DLLs in as necessary)
* Run from working tree:  
 `poetry run pyrogyro`
* Build (to Windows executable):  
 `poetry run dist`
