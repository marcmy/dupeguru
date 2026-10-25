"""Build full dupeGuru desktop bundles for GitHub Actions on Python 3.14.4."""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
OUTPUT = ROOT / "artifacts"


def run(*args):
    print("+", " ".join(map(str, args)), flush=True)
    subprocess.run(args, cwd=ROOT, check=True)


def require(path):
    if not path.exists():
        raise RuntimeError(f"Expected build output is missing: {path}")
    return path


def sha256(path):
    checksum = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(chunk)
    (path.parent / (path.name + ".sha256")).write_text(f"{checksum.hexdigest()}  {path.name}\n", encoding="utf-8")


def main():
    if sys.version_info[:3] != (3, 14, 4):
        raise RuntimeError("Packaging requires Python 3.14.4")
    OUTPUT.mkdir(exist_ok=True)

    # The project's own build prepares its native extensions, .mo translations,
    # embedded Qt resources and all language documentation.
    run(sys.executable, "build.py")
    require(ROOT / "qt" / "dg_rc.py")
    require(ROOT / "build" / "help" / "en" / "index.html")
    require(ROOT / "build" / "locale")

    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name=dupeGuru",
        f"--specpath={ROOT / 'build' / 'pyinstaller-spec'}",
        f"--workpath={ROOT / 'build' / 'pyinstaller-work'}",
        f"--distpath={DIST}",
        "--paths=.",
        "--add-data=" + str(ROOT / "build" / "locale") + os.pathsep + "locale",
        "--add-data=" + str(ROOT / "build" / "help") + os.pathsep + "help",
    ]
    if sys.platform == "win32":
        args.append("--icon=images/dgse_logo.ico")
    elif sys.platform == "darwin":
        args.extend(
            [
                "--icon=images/dupeguru.icns",
                "--osx-bundle-identifier=com.hardcoded-software.dupeguru",
            ]
        )
    args.append("run.py")
    run(*args)

    import platform

    if sys.platform == "darwin":
        arch = platform.machine().lower()
        app = require(DIST / "dupeGuru.app")
        require(app / "Contents" / "MacOS" / "dupeGuru")
        archive = OUTPUT / f"dupeguru-macos-{arch}-py3144.zip"
        # ditto preserves app bundle symlinks and extended attributes.
        run("ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(app), str(archive))
    elif sys.platform == "win32":
        require(DIST / "dupeGuru" / "dupeGuru.exe")
        archive = OUTPUT / "dupeguru-windows-x64-py3144.zip"
        shutil.make_archive(str(archive.with_suffix("")), "zip", root_dir=DIST, base_dir="dupeGuru")
    else:
        require(DIST / "dupeGuru" / "dupeGuru")
        archive = OUTPUT / "dupeguru-linux-x64-py3144.tar.gz"
        with tarfile.open(archive, "w:gz") as archive_file:
            archive_file.add(DIST / "dupeGuru", arcname="dupeGuru")
    require(archive)
    sha256(archive)
    print(f"Created: {archive} ({archive.stat().st_size:,} bytes)", flush=True)


if __name__ == "__main__":
    main()
