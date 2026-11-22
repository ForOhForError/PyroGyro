# PyroGyro

Node-based controller remapper, written in Python for hackability.

## Usage

Requires [ViGEmBus](https://github.com/nefarius/ViGEmBus) installed on a Windows system. May do cross-platform, we'll see.

At the moment, PyroGyro reads non-virtual gamepads using SDL3, and can output either to Virtual Xbox controllers or to keyboard/mouse.

It supports hotplugged devices, and autoloads configuration files as necessary.

## Config format

Configs are currently specified as a `.toml` file.

The top level specifies some config-wide options:
`name`: The name of the config, for display purposes.
`autoload`: If set to `true`, the config will be checked when doing auto-loading; defaults to `false`
`autoload_exe_name`: A regex for matching against the executable name for autoloading; defaults to `.*` (match everything)
`autoload_window_name`: A regex for matching against the executable name for autoloading; defaults to `.*` (match everything)

Input can be mapped through specifying nodes/blocks as entries below the top level.

These blocks all must specify the `TYPE` field, to specify what type of block they are.

Other fields will depend on the type of the block; by convention, configuration fields are given in lower_snake_case and mapping fields are given in UPPER_SNAKE_CASE.

Configuration fields are set on a block by setting:

```toml
name = "SomeStringValue" # Raw toml value; can be int, float, string, etc
```

Output field destinations are set on a block by setting:

```toml
OUT_FIELD = "destination.IN_FIELD" # Dotted string; maps the output OUT_FIELD to the IN_FIELD input of the block named "destination"
```

Multiple destinations can be used by setting an array for the field value:

```toml
OUT_FIELD = ["destination.IN_FIELD", "destination2.IN_FIELD_2"] # Just an array of the same format strings
```

Availible block types can be found by entering the `block` command into the console window.

Configuration for a given block can be found by entering the `block BLOCK_NAME_HERE` command into the console window.

Note that autoloading will only check files in the `configs/` directory (though it will check sub-directories)

Example: Map controller to xbox mappings, on any window

```toml
name = "Default Xbox Controller"
autoload = true
autoload_exe_name = ".*"
autoload_window_name = ".*"

[ pad ]
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

## AI Policy

AI (Currently being defined here as LLMs in any form, I am not interested in discussing semantics) has not and will not be used in the development of this project.

PRs with AI-generated or AI-consulted code will be closed without discussion. Attempts to circumvent this policy will result in being permanently blocked from contributing to this repository.

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
