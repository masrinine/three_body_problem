"""Build distributable zips for the Three Body Problem add-on.

Creates two archives in ``dist/``:

* ``three_body_problem-<version>-extension.zip``
  Layout expected by ``blender --command extension`` (manifest at the root).
  This is the recommended install path for Blender 5.2 LTS+.
* ``three_body_problem-<version>-legacy.zip``
  Legacy "Install from Disk" layout with a top-level ``three_body_problem/``
  folder containing ``bl_info``.

Usage::

    python tools/build_addon.py
"""
from __future__ import annotations

import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"

# Directories that are never part of the shipped add-on.
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "test_folder",
    "tests",
    "tools",
    "dist",
}

# Root files that are documentation for contributors, not users.
EXCLUDED_FILES = {"AGENTS.md", "TASKS.md"}

PACKAGE_NAME = "three_body_problem"


def read_manifest() -> dict:
    with open(ROOT / "blender_manifest.toml", "rb") as handle:
        return tomllib.load(handle)


def collect_files() -> list[Path]:
    files = []
    for path in sorted(ROOT.iterdir()):
        if path.is_dir():
            continue
        if path.name in EXCLUDED_FILES or path.name.startswith("."):
            continue
        if path.suffix == ".py" or path.name in {"blender_manifest.toml", "LICENSE", "README.md"}:
            files.append(path)
    return files


def build_extension(files: list[Path], output: Path) -> None:
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.name)


def build_legacy(files: list[Path], output: Path) -> None:
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, f"{PACKAGE_NAME}/{path.name}")


def main() -> int:
    manifest = read_manifest()
    version = manifest["version"]
    files = collect_files()
    if not any(path.name == "__init__.py" for path in files):
        print("ERROR: __init__.py not found in package root.", file=sys.stderr)
        return 1

    DIST.mkdir(exist_ok=True)
    extension_zip = DIST / f"{PACKAGE_NAME}-{version}-extension.zip"
    legacy_zip = DIST / f"{PACKAGE_NAME}-{version}-legacy.zip"

    build_extension(files, extension_zip)
    build_legacy(files, legacy_zip)

    print(f"Built {extension_zip.relative_to(ROOT)}")
    print(f"Built {legacy_zip.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
