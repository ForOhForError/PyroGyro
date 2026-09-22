# PyroGyro

Yet Another (Gyro) Gamepad Mapper, written in Python for hackability.

## Usage

Requires [ViGEmBus](https://github.com/nefarius/ViGEmBus) installed on a Windows system. May do cross-platform, we'll see.

At the moment, PyroGyro reads non-virtual gamepads using SDL3, and can output either to Virtual Xbox controllers or to keyboard/mouse.

It supports hotplugged devices, and autoloads configuration files as necessary.

## Config format

Configs are currently specified as a `.toml` file.

Each config has a name, autoload settings, button mappings, and gyro settings.

Some example config files are listed below.

Note that autoloading will only check files in the `configs/` directory (though it will check sub-directories)

Example: Map controller to xbox mappings, on any window

```toml
name = "Default Xbox Controller"
autoload = true
autoload_exe_name = ".*"
autoload_window_name = ".*"

[ pad ]
# match_controller_name = ".*" # Regex for controller name, defaults to accepting anything
# multi_pad_mode = "duplicate" # Determines how to handle multiple pads
TYPE = "PAD"
N = "xbox.Y"
S = "xbox.A"
E = "xbox.B"
W = "xbox.X"
UP = "xbox.UP"
DOWN = "xbox.DOWN"
LEFT = "xbox.LEFT"
RIGHT = "xbox.RIGHT"
BACK = "xbox.BACK"
START = "xbox.START"
GUIDE = "xbox.GUIDE"
R1 = "xbox.R1"
R2 = "xbox.R2"
R3 = "xbox.R3"
L1 = "xbox.L1"
L2 = "xbox.L2"
L3 = "xbox.L3"
RSTICK = "xbox.RSTICK"
LSTICK = "xbox.LSTICK"

[ xbox ]
TYPE = "XBOX"
RUMBLE = "pad.RUMBLE"
```

## Development

You'll need [uv](https://docs.astral.sh/uv/) and a working Python environment (3.11 and up)

* Clone the repo:  
 `git clone https://github.com/ForOhForError/PyroGyro`
* Install dependencies:  
 `uv sync`
 (should pull Windows DLLs in as necessary)
* Run from working tree:  
 `uv run pyrogyro`
* Build (to Windows executable):  
 `uv run dist`
