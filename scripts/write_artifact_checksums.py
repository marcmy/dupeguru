"""Generate .sha256 sidecars for CI build archives and installers."""

from __future__ import annotations

import glob
import hashlib
import sys
from pathlib import Path


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: write_artifact_checksums.py <path-or-glob> [...]")
        return 2

    for pattern in sys.argv[1:]:
        matched = sorted(glob.glob(pattern))
        if not matched:
            raise FileNotFoundError(f"No build artifact matches {pattern!r}")
        for filename in matched:
            path = Path(filename)
            if not path.is_file():
                raise ValueError(f"Not a file: {path}")
            sidecar = path.with_name(path.name + ".sha256")
            sidecar.write_text(f"{checksum(path)}  {path.name}\n", encoding="utf-8")
            print(f"SHA-256: {sidecar}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
