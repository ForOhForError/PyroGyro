# PyroGyro

Yet Another (Gyro) Gamepad Mapper, written in Python for hackability.

## Usage

Requires [ViGEmBus](https://github.com/nefarius/ViGEmBus) installed on a Windows system. May do cross-platform, we'll see.

Currently just a framework. Doesn't do much yet.

## Config format

Configs are currently specified as a yaml (.yml) file. 
The current default config maps any input controller to an Xbox controller.
Each device plugged in will pick up this config by default.

```yaml
name: Default Mapping
mapping:
  NORTH: XUSB_GAMEPAD_Y
  SOUTH: XUSB_GAMEPAD_A
  EAST: XUSB_GAMEPAD_B
  WEST: XUSB_GAMEPAD_X
  BACK: XUSB_GAMEPAD_BACK
  START: XUSB_GAMEPAD_START
  DPAD_UP: XUSB_GAMEPAD_DPAD_UP
  DPAD_DOWN: XUSB_GAMEPAD_DPAD_DOWN
  DPAD_LEFT: XUSB_GAMEPAD_DPAD_LEFT
  DPAD_RIGHT: XUSB_GAMEPAD_DPAD_RIGHT
  LEFT_SHOULDER: XUSB_GAMEPAD_LEFT_SHOULDER
  RIGHT_SHOULDER: XUSB_GAMEPAD_RIGHT_SHOULDER
  LEFT_STICK: XUSB_GAMEPAD_LEFT_THUMB
  RIGHT_STICK: XUSB_GAMEPAD_RIGHT_THUMB
  GUIDE: XUSB_GAMEPAD_GUIDE
```

## Development

* Clone the repo:  
 `git clone https://github.com/ForOhForError/PyroGyro`
* Install dependencies:  
 `poetry install --with=dev`  
 (should pull Windows DLLs in as necessary)
* Run from working tree:
 `poetry run pyrogyro`
* Build (to Windows executable):
 `poetry run dist`
