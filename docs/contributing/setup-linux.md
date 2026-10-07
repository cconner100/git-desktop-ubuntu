# Ubuntu desktop package

The Ubuntu port keeps the Electron/React interface and integrates with GNOME's
application launcher, native window decorations, file dialogs, terminal, system
appearance, and keyring. It does not replace the interface with GTK/libadwaita
widgets. The initial package target is Ubuntu 24.04 and 26.04 LTS on x86_64.
Compatibility with older releases and ARM64 has not been verified.

## Installing a release package

Once a tested release package has been built, install it with:

```sh
sudo apt install ./git-desktop_<version>_amd64.deb
```

Launch **Git Desktop** from GNOME's application menu, or run `git-desktop`.
Electron, Git, credential helpers, and the Copilot runtime are bundled; end users
do not need Node.js, Yarn, or development tools. APT installs the declared system
libraries. Package installation therefore needs access to Ubuntu's repositories
unless all dependencies are already installed. Network access is also required
for GitHub sign-in and remote Git operations.

Browser sign-in callbacks and “Open in Desktop” links are registered through the
desktop entry, including the development OAuth callback used by builds without
custom OAuth credentials. A running application receives callbacks through
Electron's second-instance handler. Credentials use libsecret and the GNOME
keyring; no personal access tokens are stored in the Debian package.

Install a newer `.deb` with the same APT command to upgrade. Remove the application
with `sudo apt remove git-desktop`. Repository files and application data in the
user's home directory are not removed. There is no APT repository or Linux
automatic update service configured by this package.

## Building on Ubuntu 24.04

For a local test build and installation, run this from your normal Ubuntu desktop
terminal as your desktop user:

```sh
bash script/linux/build-and-install.sh
```

The helper uses sudo for system dependencies and package installation. It
downloads the pinned Node runtime with checksum verification, copies the modified
source into a separate cache directory, populates its submodules, builds the
package, installs it, checks native libraries, runs the installed application's
smoke test, and launches Git Desktop. The completed `.deb` and checksum are copied
back to this project's `dist/` directory. The source directory is preserved.
The build directory and log are retained under `~/.cache/git-desktop/` (or
`$XDG_CACHE_HOME/git-desktop/`).

When the source is a Git checkout, its recorded submodule revisions are retained.
For an archive without Git metadata, dependency repositories are fetched at their
current revisions and a local source snapshot commit is created in the build
directory. The helper requires network access and an environment where sudo is
available; it exits early in restricted sessions that prohibit privilege changes.

Building on Ubuntu 26.04 produces a package for testing on that machine. Use the
Ubuntu 24.04 workflow for a release intended to run on both supported versions.
The helper disables optional test video on Ubuntu 26.04 because the pinned
Playwright release has no matching ffmpeg download. Smoke tests and traces stay
enabled. For manual builds on 26.04, set `DESKTOP_E2E_RECORD_VIDEO=0` before
installing dependencies and running tests.

Emoji packaging supports both older gemoji revisions with custom images and
current revisions containing only Unicode emoji. Copilot's FFI loader and its
matching native package are shipped outside the JavaScript bundle.

Build on the oldest supported Ubuntu release so compiled native modules remain
compatible with newer releases. Use the Node version in `.node-version` and
Yarn Classic. Start with a recursive Git clone so the emoji, gitignore, and
license submodules are populated.

```sh
sudo apt update
sudo apt install build-essential git python3 libsecret-1-dev libgtk-3-0t64 \
  libnss3 libasound2t64 libgbm1 libxss1 libxtst6 libcurl4t64 \
  desktop-file-utils apparmor
npm install --global yarn@1.22.22
yarn install --frozen-lockfile
yarn build:ubuntu
```

The output is `dist/git-desktop_<version>_amd64.deb` and its SHA-256 checksum.
To reuse an already downloaded Electron archive while packaging, set
`DESKTOP_ELECTRON_ZIP_DIR` to the directory containing the matching
`electron-v<version>-linux-x64.zip`. Otherwise the packager downloads the runtime.
SemVer prereleases are converted to Debian versions, e.g.
`3.6.7-beta2` becomes `3.6.7~beta2-1`, so stable versions upgrade correctly.
Package metadata identifies this fork and its maintainer. Third-party forks
should update the homepage and maintainer in `script/linux/package_deb.py`.

The package builder verifies that the application bundles, Electron resources,
bundled Git, credential module, native helpers, and Copilot runtime are present
and that native binaries match the requested architecture. An incomplete build
does not produce an installer. It preserves upstream and third-party licenses.

Ubuntu's AppArmor restrictions on user namespaces are handled by an application
profile installed at `/etc/apparmor.d/opt.git-desktop.desktop`. This keeps
Chromium's user namespace sandbox available without a `--no-sandbox` launcher
or system-wide security changes. The profile allows user namespaces specifically for the
installed Electron executable; it is not a full confinement policy.

## Validation

```sh
yarn test:ubuntu-package
python3 script/linux/check_runtime.py /opt/git-desktop
```

The Ubuntu workflow in `.github/workflows/ubuntu.yml` builds on Ubuntu 24.04,
installs the actual package, checks native library resolution, runs unit tests
and the installed application's launch/commit/branch smoke test, and uploads
the `.deb` after those checks pass. A second job checks package installation and
library resolution in an Ubuntu 26.04 container. The container check does not
verify a GNOME or Wayland session.

Before claiming a supported release, test a clean Ubuntu GNOME desktop on both
versions: launch from the application menu, clone, commit, branch, push/pull,
complete browser sign-in both with the app closed and running, restart and check
credential persistence, open a repository in the file manager and terminal,
change system appearance, upgrade, and uninstall. Verify both Wayland and X11
where available. The workflow does not establish full GNOME session compatibility
or live GitHub authentication by itself. Successful `ubuntu-v<app version>` tag
builds publish the tested package and checksum in this fork's GitHub Releases.

The desktop identity follows
[Electron's Linux application API](https://www.electronjs.org/docs/latest/api/app#appsetdesktopnamename-linux).
The sandbox profile follows
[Ubuntu's user namespace guidance](https://documentation.ubuntu.com/release-notes/24.04/),
and package upgrades follow
[Electron's Linux update guidance](https://www.electronjs.org/docs/latest/api/auto-updater#platform-notices).
