# Downloadable CI builds

The **Default CI/CD** workflow tests dupeGuru first, then builds downloadable GUI applications on Python **3.14.4**:

| Runner | Produced download |
| --- | --- |
| Windows 2025 x64 | `dupeguru-windows-x64-py3144.zip` |
| Ubuntu 24.04 x64 | `dupeguru-linux-x64-py3144.tar.gz` |
| macOS 15 Apple Silicon | `dupeguru-macos-arm64-py3144.zip` |
| macOS 15 Intel | `dupeguru-macos-x86_64-py3144.zip` |

Open **Actions → Default CI/CD → a successful run → Artifacts** to download a package. GitHub may wrap the archive in its own artifact download ZIP; extract that ZIP first, then extract the contained application archive.

The packages contain the frozen application, Qt runtime, compiled extensions, translations and generated help. **Python is not required to run them.** They are CI preview builds, not signed release packages. macOS may require a local Gatekeeper exception. Linux packages are built on Ubuntu 24.04 and may require compatible system libraries/glibc; they are not portable AppImages.

The CI workflow also supports manual runs with **Run workflow**. Build artifacts are kept for 14 days, and each archive includes a companion `.sha256` checksum file. Platform builds are uploaded only after the existing test matrix passes.

The legacy `package.py` packaging entry points have not been changed; the new build script uses PyInstaller 6 on Python 3.14.4 to avoid the repository's legacy PyInstaller 5 requirement.
