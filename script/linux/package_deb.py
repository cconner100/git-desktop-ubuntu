#!/usr/bin/env python3
"""Package a complete Linux Electron build; never substitute a stub application."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSETS = Path(__file__).resolve().parent / "assets"
APP_ID = "io.github.desktopcommunity.GitDesktop"
ARCHITECTURES = {"x64": ("amd64", 62), "arm64": ("arm64", 183)}

# The t64 alternatives cover Ubuntu 24.04+ while retaining standard Debian
# package names. Native code must be built on the oldest supported Ubuntu.
DEPENDENCIES = (
    "apparmor (>= 4.0), ca-certificates, xdg-utils, openssh-client, "
    "libc6 (>= 2.39), libstdc++6, libgcc-s1, libnss3, libnspr4, "
    "libsecret-1-0, libgtk-3-0t64 | libgtk-3-0, "
    "libglib2.0-0t64 | libglib2.0-0, libasound2t64 | libasound2, "
    "libatk1.0-0t64 | libatk1.0-0, libatk-bridge2.0-0t64 | libatk-bridge2.0-0, "
    "libatspi2.0-0t64 | libatspi2.0-0, libcups2t64 | libcups2, "
    "libdbus-1-3, libdrm2, libgbm1, libexpat1, "
    "libx11-6, libxcb1, libxcomposite1, libxdamage1, libxext6, "
    "libxfixes3, libxrandr2, libxkbcommon0, libxss1, libxtst6, "
    "libudev1, libcurl4t64 | libcurl4, libzstd1, zlib1g"
)


def debian_version(version):
    """Ensure prereleases sort before the corresponding stable version."""
    match = re.fullmatch(
        r"(\d+\.\d+\.\d+)(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?",
        version,
    )
    if match is None:
        raise ValueError(f"Invalid application version: {version!r}")
    base, prerelease, metadata = match.groups()
    return (
        base
        + (f"~{prerelease}" if prerelease else "")
        + (f"+{metadata}" if metadata else "")
        + "-1"
    )


def require_file(path):
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"Missing or empty application file: {path}")


def elf_machine(path):
    with path.open("rb") as stream:
        header = stream.read(20)
    if len(header) < 20 or header[:4] != b"\x7fELF" or header[4] != 2:
        raise ValueError(f"Expected a 64-bit ELF binary: {path}")
    if header[5] not in (1, 2):
        raise ValueError(f"Invalid ELF byte order: {path}")
    return struct.unpack("<H" if header[5] == 1 else ">H", header[18:20])[0]


def validate_app(app_dir, arch):
    """Check runtime resources and architecture before generating an installer."""
    app_root = app_dir / "resources/app"
    required = [
        "desktop", "chrome-sandbox", "icudtl.dat", "resources.pak",
        "resources/app/package.json", "resources/app/main.js",
        "resources/app/renderer.js", "resources/app/renderer.css",
        "resources/app/index.html", "resources/app/crash.js",
        "resources/app/crash.html", "resources/app/crash.css",
        "resources/app/highlighter.js", "resources/app/emoji.json",
        "resources/app/static/icon-logo.png", "resources/app/static/licenses.json",
        "resources/app/static/available-licenses.json",
        "resources/app/git/bin/git",
        "resources/app/git/libexec/git-core/git-credential-desktop",
        "resources/app/desktop-trampoline/desktop-askpass-trampoline",
        "resources/app/process-proxy", "resources/app/printenvz",
        f"resources/app/copilot/prebuilds/linux-{arch}/copilot-runtime",
        f"resources/app/copilot/prebuilds/linux-{arch}/runtime.node",
    ]
    for relative in required:
        require_file(app_dir / relative)
    if not list((app_dir / "locales").glob("*.pak")):
        raise ValueError("Electron locale files are missing")
    if not (app_root / "emoji").is_dir():
        raise ValueError("Emoji resources are missing")
    keytar_modules = list(app_root.glob("**/keytar.node"))
    if not keytar_modules:
        raise ValueError("The GNOME keyring credential module (keytar) is missing")

    # Do not ship links to the developer's node_modules or host libraries.
    for file in app_dir.rglob("*"):
        if file.is_symlink() and not file.resolve().is_relative_to(app_dir):
            raise ValueError(f"Symlink escapes application directory: {file}")

    binaries = [
        app_dir / "desktop", app_dir / "chrome-sandbox", app_root / "git/bin/git",
        app_root / "git/libexec/git-core/git-credential-desktop",
        app_root / "desktop-trampoline/desktop-askpass-trampoline",
        app_root / "process-proxy", app_root / "printenvz",
        app_root / f"copilot/prebuilds/linux-{arch}/copilot-runtime",
    ]
    expected = ARCHITECTURES[arch][1]
    for binary in binaries + list(app_dir.rglob("*.node")):
        require_file(binary)
        if elf_machine(binary) != expected:
            raise ValueError(f"Binary architecture does not match {arch}: {binary}")
        if binary in binaries and not os.access(binary, os.X_OK):
            raise ValueError(f"Binary is not executable: {binary}")

    manifest = json.loads((app_root / "package.json").read_text())
    if manifest.get("main") not in ("./main.js", "main.js"):
        raise ValueError("Application manifest must point to main.js")
    debian_version(manifest.get("version", ""))
    return manifest


def copy_asset(name, destination, executable=False):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ASSETS / name, destination)
    destination.chmod(0o755 if executable else 0o644)


def stage_package(app_dir, arch, stage):
    manifest = validate_app(app_dir, arch)
    version = debian_version(manifest["version"])
    app_destination = stage / "opt/git-desktop"
    app_destination.parent.mkdir(parents=True)
    shutil.copytree(app_dir, app_destination, symlinks=True)

    # Developer files may be group-writable; the installed runtime must not be.
    # The AppArmor userns profile allows Chromium's sandbox without setuid.
    for file in stage.rglob("*"):
        if file.is_symlink():
            continue
        executable = file.is_dir() or bool(file.stat().st_mode & stat.S_IXUSR)
        file.chmod(0o755 if executable else 0o644)

    copy_asset("git-desktop", stage / "usr/bin/git-desktop", executable=True)
    desktop = stage / f"usr/share/applications/{APP_ID}.desktop"
    copy_asset(f"{APP_ID}.desktop", desktop)
    copy_asset(
        "opt.git-desktop.desktop", stage / "etc/apparmor.d/opt.git-desktop.desktop"
    )
    icon = stage / f"usr/share/icons/hicolor/512x512/apps/{APP_ID}.png"
    icon.parent.mkdir(parents=True)
    shutil.copyfile(app_dir / "resources/app/static/icon-logo.png", icon)
    # Preserve upstream attribution and the generated third-party license dump.
    doc = stage / "usr/share/doc/git-desktop"
    doc.mkdir(parents=True)
    shutil.copyfile(PROJECT_ROOT / "LICENSE", doc / "copyright")
    shutil.copyfile(app_dir / "resources/app/static/licenses.json", doc / "licenses.json")

    if shutil.which("desktop-file-validate"):
        subprocess.run(["desktop-file-validate", str(desktop)], check=True)

    installed_size = sum(
        file.stat().st_size for file in stage.rglob("*")
        if file.is_file() and not file.is_symlink()
    )
    debian = stage / "DEBIAN"
    debian.mkdir()
    (debian / "control").write_text(
        f"Package: git-desktop\nVersion: {version}\n"
        f"Architecture: {ARCHITECTURES[arch][0]}\n"
        "Maintainer: cconner100 <942585+cconner100@users.noreply.github.com>\n"
        "Section: devel\nPriority: optional\n"
        f"Installed-Size: {(installed_size + 1023) // 1024}\n"
        f"Depends: {DEPENDENCIES}\n"
        "Recommends: gnome-keyring, gnome-terminal\n"
        "Homepage: https://github.com/cconner100/git-desktop-ubuntu\n"
        "Description: Community Ubuntu port of GitHub Desktop\n"
        " Manage local Git repositories, commits, branches, and GitHub collaboration.\n"
        " Includes the Electron runtime and Git; Node.js and Yarn are not required\n"
        " on the installed machine. Uses the GNOME keyring to store credentials.\n"
    )
    (debian / "conffiles").write_text("/etc/apparmor.d/opt.git-desktop.desktop\n")
    copy_asset("postinst", debian / "postinst", executable=True)
    copy_asset("postrm", debian / "postrm", executable=True)
    checksums = []
    for file in sorted(stage.rglob("*")):
        if file.is_file() and not file.is_symlink() and debian not in file.parents:
            with file.open("rb") as stream:
                digest = hashlib.file_digest(stream, "md5").hexdigest()
            checksums.append(f"{digest}  {file.relative_to(stage)}\n")
    (debian / "md5sums").write_text("".join(checksums))
    for file in debian.iterdir():
        if file.name not in ("postinst", "postrm"):
            file.chmod(0o644)
    return version


def build_package(app_dir, arch, output_dir):
    app_dir = Path(app_dir).resolve()
    output_dir = Path(output_dir).resolve()
    if output_dir == app_dir or output_dir.is_relative_to(app_dir):
        raise ValueError("Package output directory must be outside the application")
    if not shutil.which("dpkg-deb"):
        raise ValueError("dpkg-deb is required; install Ubuntu's dpkg package")
    # Fail before creating or replacing any output when the build is incomplete.
    validate_app(app_dir, arch)
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="git-desktop-deb-") as temporary:
        stage = Path(temporary) / "root"
        stage.mkdir()
        version = stage_package(app_dir, arch, stage)
        name = f"git-desktop_{version}_{ARCHITECTURES[arch][0]}.deb"
        candidate = Path(temporary) / name
        subprocess.run(
            ["dpkg-deb", "--root-owner-group", "--build", str(stage), str(candidate)],
            check=True,
        )
        result = output_dir / name
        # Copy across filesystems, then atomically replace the published filename.
        with tempfile.NamedTemporaryFile(dir=output_dir, suffix=".partial", delete=False) as stream:
            partial = Path(stream.name)
        try:
            shutil.copyfile(candidate, partial)
            partial.chmod(0o644)
            partial.replace(result)
        finally:
            partial.unlink(missing_ok=True)
    with result.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    result.with_suffix(".deb.sha256").write_text(f"{digest}  {result.name}\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices=ARCHITECTURES, default="x64")
    parser.add_argument("--app-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "dist")
    arguments = parser.parse_args()
    app_dir = arguments.app_dir or PROJECT_ROOT / f"dist/desktop-linux-{arguments.arch}"
    try:
        result = build_package(app_dir, arguments.arch, arguments.output_dir)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Cannot package Ubuntu application: {error}\n")
    print(f"Created {result}")
    print(f"Install with: sudo apt install ./{result.name}")


if __name__ == "__main__":
    main()
