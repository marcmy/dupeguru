# Downloadable CI builds

The [Build artifacts](../../actions/workflows/build-artifacts.yml) workflow produces
ready-to-extract preview builds on **Python 3.15.1** for these platforms:

| Runner | Artifact | Contents |
| --- | --- | --- |
| Windows x64 | `dupeguru-windows-x64-installer` | NSIS installer and checksum |
| Windows x64 | `dupeguru-windows-x64-portable` | Portable ZIP and checksum |
| Ubuntu x64 | `dupeguru-linux-x64-portable` | App tar.gz and checksum |
| macOS Apple Silicon | `dupeguru-macos-arm64-app-unsigned` | Unsigned .app ZIP and checksum |
| macOS Intel | `dupeguru-macos-x64-app-unsigned` | Unsigned .app ZIP and checksum |

From the repository's **Actions** tab, open a successful **Build artifacts**
run and select an artifact under **Artifacts**. GitHub wraps each download
in an additional ZIP; extract the outer ZIP first, then the archive inside.

Every downloadable file has a sibling `.sha256` containing a SHA-256 hash
in the format `<hash>  <filename>`. To verify after extracting the artifact:

- Windows PowerShell: `Get-FileHash -Algorithm SHA256 .\filename.zip`
- macOS/Linux: `shasum -a 256 -c filename.zip.sha256`
  (or `sha256sum -c filename.zip.sha256` on Linux)

The file names in the commands are examples; use the actual archive name.
All build archives have a **14-day retention period**.

These are **unsigned, unnotarized CI preview builds**, not official releases.
macOS Gatekeeper may require an exception. The Linux build targets GitHub's
Ubuntu runner, may require compatible libraries/glibc, and is not an AppImage.
All builds require a compatible OS and CPU architecture but do **not** require
users to install Python.
