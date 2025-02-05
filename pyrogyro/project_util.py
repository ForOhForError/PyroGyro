import sys
import zipfile
from pathlib import Path


def build_windows_dist():
    import PyInstaller.__main__

    print("Running PyInstaller")
    PyInstaller.__main__.run(["--clean", "app_win.spec"])

    with zipfile.ZipFile("dist/pyrogyro.zip", "w", zipfile.ZIP_BZIP2) as zip_file:
        dist_dir = Path("dist/pyrogyro")
        config_dir = Path("configs")
        for entry in config_dir.rglob("*"):
            zip_file.write(entry, entry.relative_to(config_dir.parent))
        for entry in dist_dir.rglob("*"):
            zip_file.write(entry, entry.relative_to(dist_dir))
