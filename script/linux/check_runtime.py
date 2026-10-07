#!/usr/bin/env python3
"""Check the installed Linux payload for unresolved native shared libraries."""

import argparse
from pathlib import Path
import subprocess


def check_runtime(root):
    checked = 0
    errors = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        with path.open("rb") as stream:
            if stream.read(4) != b"\x7fELF":
                continue
        checked += 1
        result = subprocess.run(["ldd", str(path)], capture_output=True, text=True)
        output = result.stdout + result.stderr
        # Static executables have no dependency list and ldd returns nonzero.
        static = "not a dynamic executable" in output or "statically linked" in output
        if "not found" in output or (result.returncode != 0 and not static):
            errors.append(f"{path}:\n{output.strip()}")
    if checked == 0:
        errors.append(f"No ELF binaries found in {root}")
    return checked, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app_dir", type=Path)
    arguments = parser.parse_args()
    try:
        checked, errors = check_runtime(arguments.app_dir.resolve())
    except (OSError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Runtime check failed: {error}\n")
    if errors:
        parser.exit(1, "\n".join(errors) + "\n")
    print(f"Checked shared libraries for {checked} native binaries.")


if __name__ == "__main__":
    main()
