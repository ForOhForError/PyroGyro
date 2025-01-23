

from unittest.mock import patch
import sys

def install_win():
    import PyInstaller.__main__
    
    PyInstaller.__main__.run([
        '--clean',
        'app_win.spec'
    ])

