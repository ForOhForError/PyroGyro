import distutils.dir_util
import sys
import zipfile
import tempfile
import subprocess
from pathlib import Path
from os import getenv, unlink, environ
import base64

VAR_B64_ENCODED_CERT = "B64_ENCODED_CERT"
VAR_CERT_PASSWORD = "CERT_PASSWORD"

def build_windows_dist():
    import PyInstaller.__main__

    print("Running PyInstaller")
    PyInstaller.__main__.run(["--clean", "--noconfirm", "app_win.spec"])

    b64_cert, cert_pw = getenv(VAR_B64_ENCODED_CERT), getenv(VAR_CERT_PASSWORD)
    if b64_cert and cert_pw:
        fp = tempfile.NamedTemporaryFile(suffix=".pfx", delete=False)
        fp.write(base64.standard_b64decode(b64_cert))
        fp.close()
        subprocess.run(["signtool", "sign", "/f", fp.name, "/p", cert_pw, "/fd", "SHA256", "/tr", "http://timestamp.digicert.com", "/td", "SHA256", "dist/pyrogyro/pyrogyro.exe"])
        unlink(fp.name)

    with zipfile.ZipFile("dist/pyrogyro.zip", "w", zipfile.ZIP_BZIP2) as zip_file:
        dist_dir = Path("dist/pyrogyro")
        config_dir = Path("configs")
        for entry in config_dir.rglob("*"):
            zip_file.write(entry, entry.relative_to(config_dir.parent))
        for entry in dist_dir.rglob("*"):
            zip_file.write(entry, entry.relative_to(dist_dir))
    distutils.dir_util.copy_tree("configs", "dist/pyrogyro/configs")
