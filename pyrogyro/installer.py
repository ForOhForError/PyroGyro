import sys
from unittest.mock import patch


def install_win():
    import PyInstaller.__main__

    PyInstaller.__main__.run(["--clean", "app_win.spec"])
