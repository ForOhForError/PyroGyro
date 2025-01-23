# PyroGyro

Yet Another (Gyro) Gamepad Mapper, written in Python for hackability.

## Usage

Requires [ViGEmBus](https://github.com/nefarius/ViGEmBus) installed on a Windows system. May do cross-platform, we'll see.

Currently just a framework. Doesn't do much yet.

## Development

* Clone the repo:  
 `git clone https://github.com/ForOhForError/PyroGyro`
* Install dependencies:  
 `poetry install --with=dev`  
 (should pull Windows DLLs in as necessary)
* Run from working tree with `poetry run pyrogyro`
* Build (to Windows executable) with `poetry run dist`
