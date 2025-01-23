# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

from pathlib import Path
import vgamepad
import sdl3
import platform
from ctypes import CDLL
import sys

hiddenimports = []
hiddenimports += collect_submodules('pyrogyro')

options = [ ('v', None, 'OPTION')]
block_cipher = None

from unittest.mock import patch

if platform.architecture()[0] == "64bit":
    arch = "x64"
else:
    arch = "x86"
path_vigem_client = Path(vgamepad.__file__).parent.absolute() / "win" / "vigem" / "client" / arch / "ViGEmClient.dll"
path_sdl = Path(sdl3.__file__).parent.absolute() / "bin" / f"windows-amd{arch[1:]}"

print(Path(sdl3.__file__).parent.absolute())


a = Analysis(
    ['pyrogyro/pyrogyro.py'],
    pathex=[Path(sdl3.__file__).parent.absolute()],
    binaries=[
        (path_vigem_client, '.'),
        (path_sdl / '*.dll', '.'),
    ],
    datas=[
        ('res/*', 'res'),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['pyrogyro/runtime_hook.py'],
    excludes=[''],
    noarchive=False,
    optimize=0,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='pyrogyro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    clean=True,
    icon='res/pyrogyro.ico',
    )
