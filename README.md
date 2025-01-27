# PyroGyro

Yet Another (Gyro) Gamepad Mapper, written in Python for hackability.

## Usage

Requires [ViGEmBus](https://github.com/nefarius/ViGEmBus) installed on a Windows system. May do cross-platform, we'll see.

At the moment, PyroGyro reads non-virtual gamepads using SDL3, and can output either to Virtual Xbox controllers (1 created per gamepad) or to keyboard.

It supports hotplugged devices, but only reads a single config file at the moment. This config file can be modified at will, however.

## Config format

Configs are currently specified as a yaml (.yml) file.
The current default config maps any input controller to an Xbox controller.
Each device plugged in will pick up this config by default.

```yaml
name: Default Mapping
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
