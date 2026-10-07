"""Exercise real Debian archives using disposable test-only application fixtures."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import tempfile
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "package_deb.py"
SPEC = importlib.util.spec_from_file_location("package_deb", MODULE_PATH)
package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package)


class VersionTests(unittest.TestCase):
    def test_prerelease_sorts_before_stable(self):
        beta = package.debian_version("3.6.7-beta2")
        stable = package.debian_version("3.6.7")
        self.assertEqual(beta, "3.6.7~beta2-1")
        subprocess.run(["dpkg", "--compare-versions", beta, "lt", stable], check=True)

    def test_metadata_and_invalid_versions(self):
        self.assertEqual(package.debian_version("1.2.3+ubuntu.1"), "1.2.3+ubuntu.1-1")
        for value in ("", "../1.2.3", "1.2.3\nArchitecture: all", "1.2"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                package.debian_version(value)


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="git-desktop-package-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.app = self.root / "app"
        self.app_root = self.app / "resources/app"
        self.output = self.root / "packages"
        binaries = [
            "desktop", "chrome-sandbox", "resources/app/git/bin/git",
            "resources/app/git/libexec/git-core/git-credential-desktop",
            "resources/app/desktop-trampoline/desktop-askpass-trampoline",
            "resources/app/process-proxy", "resources/app/printenvz",
            "resources/app/copilot/prebuilds/linux-x64/copilot-runtime",
            "resources/app/copilot/prebuilds/linux-x64/runtime.node",
            "resources/app/build/Release/keytar.node",
        ]
        # Minimal ELF headers are exclusively validator fixtures, never runtime
        # artifacts. Archive tests verify packaging, not application behavior.
        header = bytearray(64)
        header[:6] = b"\x7fELF\x02\x01"
        struct.pack_into("<H", header, 18, 62)
        for relative in binaries:
            path = self.app / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(header)
            path.chmod(0o775)
        resources = [
            "icudtl.dat", "resources.pak", "locales/en-US.pak",
            "resources/app/main.js", "resources/app/renderer.js",
            "resources/app/renderer.css", "resources/app/index.html",
            "resources/app/crash.js", "resources/app/crash.html",
            "resources/app/crash.css", "resources/app/highlighter.js",
            "resources/app/emoji.json", "resources/app/static/icon-logo.png",
            "resources/app/static/licenses.json",
            "resources/app/static/available-licenses.json",
        ]
        for relative in resources:
            path = self.app / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("test fixture\n")
        (self.app_root / "emoji").mkdir()
        (self.app_root / "package.json").write_text(json.dumps({
            "name": "git-desktop", "main": "./main.js", "version": "3.6.7-beta2",
        }))

    def test_missing_runtime_refuses_to_create_an_installer(self):
        (self.app_root / "renderer.js").unlink()
        with self.assertRaisesRegex(ValueError, "renderer.js"):
            package.build_package(self.app, "x64", self.output)
        self.assertFalse(self.output.exists())

    def test_wrong_architecture_is_rejected(self):
        binary = self.app / "desktop"
        header = bytearray(binary.read_bytes())
        struct.pack_into("<H", header, 18, 183)
        binary.write_bytes(header)
        with self.assertRaisesRegex(ValueError, "architecture"):
            package.validate_app(self.app, "x64")

    def test_native_module_with_wrong_architecture_is_rejected(self):
        binary = self.app_root / "build/Release/keytar.node"
        header = bytearray(binary.read_bytes())
        struct.pack_into("<H", header, 18, 183)
        binary.write_bytes(header)
        with self.assertRaisesRegex(ValueError, "architecture"):
            package.validate_app(self.app, "x64")

    def test_non_elf_executable_is_rejected(self):
        (self.app / "desktop").write_text("#!/bin/sh\nexit 0\n")
        with self.assertRaisesRegex(ValueError, "ELF"):
            package.validate_app(self.app, "x64")

    def test_missing_gnome_credential_storage_is_rejected(self):
        (self.app_root / "build/Release/keytar.node").unlink()
        with self.assertRaisesRegex(ValueError, "keytar"):
            package.validate_app(self.app, "x64")

    def test_host_symlinks_are_rejected(self):
        (self.app_root / "host-library").symlink_to("/usr/lib")
        with self.assertRaisesRegex(ValueError, "Symlink escapes"):
            package.validate_app(self.app, "x64")

    def test_output_cannot_be_inside_payload(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            package.build_package(self.app, "x64", self.app / "dist")

    def test_archive_contains_launcher_runtime_integration_and_checksums(self):
        result = package.build_package(self.app, "x64", self.output)
        self.assertEqual(result.name, "git-desktop_3.6.7~beta2-1_amd64.deb")
        metadata = subprocess.check_output(
            ["dpkg-deb", "--field", str(result)], text=True
        )
        self.assertIn("Architecture: amd64", metadata)
        self.assertIn("libsecret-1-0", metadata)
        self.assertIn("apparmor (>= 4.0)", metadata)
        self.assertNotIn("Depends: node", metadata)

        extract = self.root / "extracted"
        subprocess.run(["dpkg-deb", "--raw-extract", str(result), str(extract)], check=True)
        runtime = extract / "opt/git-desktop"
        self.assertTrue((runtime / "resources/app/git/bin/git").exists())
        self.assertTrue((runtime / "resources/app/build/Release/keytar.node").exists())
        self.assertEqual(stat.S_IMODE((runtime / "desktop").stat().st_mode), 0o755)
        self.assertEqual(stat.S_IMODE((runtime / "chrome-sandbox").stat().st_mode), 0o755)
        launcher = extract / "usr/bin/git-desktop"
        self.assertIn('"$@"', launcher.read_text())
        self.assertNotIn("--no-sandbox", launcher.read_text())
        desktop = extract / f"usr/share/applications/{package.APP_ID}.desktop"
        self.assertIn("%U", desktop.read_text())
        self.assertIn("x-github-desktop-dev-auth", desktop.read_text())
        self.assertIn("userns,", (extract / "etc/apparmor.d/opt.git-desktop.desktop").read_text())
        self.assertTrue((extract / "usr/share/doc/git-desktop/copyright").is_file())

        for entry in (extract / "DEBIAN/md5sums").read_text().splitlines():
            digest, relative = entry.split("  ", 1)
            self.assertEqual(digest, hashlib.md5((extract / relative).read_bytes()).hexdigest())
        digest = hashlib.sha256(result.read_bytes()).hexdigest()
        self.assertEqual(result.with_suffix(".deb.sha256").read_text(), f"{digest}  {result.name}\n")
        listing = subprocess.check_output(["dpkg-deb", "--contents", str(result)], text=True)
        self.assertIn("root/root", listing)
        self.assertNotIn("--no-sandbox", (extract / "DEBIAN/postinst").read_text())
        for name in ("postinst", "postrm"):
            self.assertEqual(stat.S_IMODE((extract / "DEBIAN" / name).stat().st_mode), 0o755)
            subprocess.run(["sh", "-n", str(extract / "DEBIAN" / name)], check=True)

    def test_launcher_preserves_spaces_and_callback_arguments(self):
        # Replace only the fixture path to avoid executing or installing in /opt.
        recorder = self.root / "record-arguments"
        arguments_file = self.root / "arguments"
        recorder.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$ARGUMENTS_FILE"\n')
        recorder.chmod(0o755)
        launcher = self.root / "launcher"
        launcher.write_text((package.ASSETS / "git-desktop").read_text().replace(
            "/opt/git-desktop/desktop", f'"{recorder}"'
        ))
        args = ["--cli-open=/tmp/repository with spaces", "x-github-desktop-dev-auth://oauth?code=a&state=b"]
        subprocess.run(["sh", str(launcher), *args], check=True,
                       env={**os.environ, "ARGUMENTS_FILE": str(arguments_file)})
        self.assertEqual(arguments_file.read_text().splitlines(), args)


if __name__ == "__main__":
    unittest.main()
