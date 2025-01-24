from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent


def icon_location():
    return (ROOT_DIR / "res" / "pyrogyro.ico").as_posix()
