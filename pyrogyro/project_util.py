import base64
import shutil
import subprocess
import tempfile
import zipfile
import os
from pathlib import Path

import urllib.request

VAR_B64_ENCODED_CERT = "B64_ENCODED_CERT"
VAR_CERT_PASSWORD = "CERT_PASSWORD"

SDL_BINARY_PATH = os.path.join("bin", "sdl3")


def setup_pysdl_env_vars():
    os.environ["SDL_DISABLE_METADATA"] = "1"
    os.environ["SDL_BINARY_PATH"] = SDL_BINARY_PATH
    os.environ["SDL_CHECK_BINARY_VERSION"] = "0"
    os.environ["SDL_FIND_BINARIES"] = "0"


def download_sdl_binary(
    version: str,
    sdl_binary_path: str = SDL_BINARY_PATH,
    library: str = "",
    platform: str = "win32",
    arch: str = "x64",
    binary_filetype: str = ".dll",
    force_overwrite: bool = False,
):
    if library and (not library.startswith("_")):
        library = "_" + library
    if force_overwrite or (
        not os.path.exists(
            os.path.join(sdl_binary_path, f"SDL3{library}{binary_filetype}")
        )
    ):
        download_url = f"https://github.com/libsdl-org/SDL{library}/releases/download/release-{version}/SDL3{library}-{version}-{platform}-{arch}.zip"
        print(f"Downloading SDL{library} {version} ({platform}/{arch})")
        local_filename, _ = urllib.request.urlretrieve(download_url)
        with zipfile.ZipFile(local_filename) as libzip:
            libzip.extract(f"SDL3{library}{binary_filetype}", path=sdl_binary_path)


SDL_LIBRARIES = [
    ("", "3.4.16"),
    ("image", "3.4.6"),
    ("mixer", "3.2.4"),
    ("net", "3.2.0"),
    ("ttf", "3.2.2"),
]


def download_sdl_binaries(
    sdl_binary_path: str = SDL_BINARY_PATH,
    platform: str = "win32",
    arch: str = "x64",
    binary_filetype: str = ".dll",
    force_overwrite: bool = False,
):
    os.makedirs(SDL_BINARY_PATH, exist_ok=True)
    for library_entry in SDL_LIBRARIES:
        library, version = library_entry
        download_sdl_binary(
            version,
            library=library,
            sdl_binary_path=sdl_binary_path,
            platform=platform,
            arch=arch,
            binary_filetype=binary_filetype,
            force_overwrite=force_overwrite,
        )
    urllib.request.urlcleanup()


def download_sdl():
    download_sdl_binaries(force_overwrite=True)


def build_windows_dist():
    setup_pysdl_env_vars()
    download_sdl_binaries(force_overwrite=True)
    import PyInstaller.__main__

    print("Running PyInstaller")
    PyInstaller.__main__.run(["--clean", "--noconfirm", "app_win.spec"])

    b64_cert, cert_pw = os.getenv(VAR_B64_ENCODED_CERT), os.getenv(VAR_CERT_PASSWORD)
    if b64_cert and cert_pw:
        fp = tempfile.NamedTemporaryFile(suffix=".pfx", delete=False)
        fp.write(base64.standard_b64decode(b64_cert))
        fp.close()
        subprocess.run(
            [
                "signtool",
                "sign",
                "/f",
                fp.name,
                "/p",
                cert_pw,
                "/fd",
                "SHA256",
                "/tr",
                "http://timestamp.digicert.com",
                "/td",
                "SHA256",
                "dist/pyrogyro/pyrogyro.exe",
            ]
        )
        os.unlink(fp.name)

    with zipfile.ZipFile("dist/pyrogyro.zip", "w", zipfile.ZIP_BZIP2) as zip_file:
        dist_dir = Path("dist/pyrogyro")
        config_dir = Path("configs")
        sdl3_dir = Path("sdl3/bin")
        for entry in config_dir.rglob("*"):
            zip_file.write(entry, entry.relative_to(config_dir.parent))
        for entry in sdl3_dir.rglob("*"):
            zip_file.write(entry, entry.relative_to(sdl3_dir.parent.parent))
        for entry in dist_dir.rglob("*"):
            zip_file.write(entry, entry.relative_to(dist_dir))
    shutil.copytree("configs", "dist/pyrogyro/configs", dirs_exist_ok=True)


def build_and_copy_frontend():
    cwd = Path.cwd().joinpath("pyrogyro-web/")
    print(cwd)
    subprocess.run(["npm", "run", "build"], cwd=cwd, shell=True)
    shutil.copytree("pyrogyro-web/dist", "res/web/static", dirs_exist_ok=True)
