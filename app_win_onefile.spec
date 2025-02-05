# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

from pathlib import Path
import vgamepad
import sdl3
from ctypes import CDLL
import sys

import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--arch-bits", choices=(32, 64, ), default=64)
cmd_args = parser.parse_args()

hiddenimports = []
hiddenimports += collect_submodules('pyrogyro')

options = [ ('v', None, 'OPTION')]
block_cipher = None

from unittest.mock import patch

if cmd_args.arch_bits == 64:
    arch = "x64"
else:
    arch = "x86"

path_vigem_client = Path(vgamepad.__file__).parent.absolute() / "win" / "vigem" / "client" / arch / "ViGEmClient.dll"
path_sdl = Path(sdl3.__file__).parent.absolute() / "bin"

a = Analysis(
    ['pyrogyro/pyrogyro.py'],
    pathex=[Path(sdl3.__file__).parent.absolute()],
    binaries=[
        (path_vigem_client, '.'),
        (path_sdl / '*.dll', './sdl3/bin'),
    ],
    datas=[
        ('res/*', 'res'),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['pyrogyro/win_runtime_hook.py'],
    excludes=['pyrogyro/project_util.py'],
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
    icon='res/pyrogyro2.ico',
    )
