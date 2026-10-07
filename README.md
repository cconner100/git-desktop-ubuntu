# Git Desktop for Ubuntu

A community Ubuntu GNOME port of [GitHub Desktop](https://github.com/desktop/desktop),
maintained in [cconner100/git-desktop-ubuntu](https://github.com/cconner100/git-desktop-ubuntu).
Manage local repositories, clone from GitHub, review changes, commit, create
branches, and push or pull using a desktop interface.

This fork keeps the upstream Electron, React, and TypeScript interface and adds
Ubuntu packaging and GNOME desktop integration. It is not an official GitHub
release or a rewrite using GTK/libadwaita widgets.

## Version and requirements

| Item | Current release |
| --- | --- |
| Application version | **3.6.7-beta2** (prerelease) |
| Ubuntu package version | **3.6.7~beta2-1** |
| Release tag | **ubuntu-v3.6.7-beta2** |
| Target desktops | Ubuntu **24.04 LTS** and **26.04 LTS**, with GNOME |
| Architecture | **amd64 / x86_64** (Intel or AMD 64-bit) |

ARM64 and older Ubuntu releases have not been validated. The application includes
Electron, Git, credential helpers, and the Copilot runtime. Installing a release
package does not require Node.js, Yarn, or build tools. Network access is needed
for missing Ubuntu dependencies, GitHub sign-in, and remote repository operations.
Copilot features require the appropriate account access.

## Install on Ubuntu with GNOME

1. Open the [Releases page](https://github.com/cconner100/git-desktop-ubuntu/releases)
   and select the newest Ubuntu release, including prereleases.
2. Download both `git-desktop_3.6.7~beta2-1_amd64.deb` and
   `git-desktop_3.6.7~beta2-1_amd64.deb.sha256` from its **Assets**.
3. Open a terminal in the download directory and run:

   ```bash
   sha256sum --check 'git-desktop_3.6.7~beta2-1_amd64.deb.sha256'
   sudo apt update
   sudo apt install './git-desktop_3.6.7~beta2-1_amd64.deb'
   ```

4. Launch **Git Desktop** from GNOME's application menu, or run:

   ```bash
   git-desktop
   ```

For later releases, substitute the filenames shown in that release's Assets.
Use `apt install` rather than opening the archive manually so Ubuntu installs
its declared runtime dependencies. The runtime is installed under
`/opt/git-desktop`; its launcher is `/usr/bin/git-desktop`.

### Upgrade or uninstall

Download the newer package and checksum, verify them, and install the new `.deb`
with the same APT command. Linux releases use package upgrades; the application
does not use the upstream Windows/macOS automatic updater.

```bash
sudo apt remove git-desktop
```

Uninstalling leaves your repositories and personal application data intact.

## GitHub sign-in and company repositories

Sign in through your browser from Git Desktop. Browser authentication callbacks
and **Open in Desktop** links are registered with Ubuntu. Credentials are stored
using libsecret and the GNOME keyring.

Without custom build credentials, this fork uses the development OAuth app
provided in upstream source. Company organizations may require approval for that
app even when the same repositories work in your browser or the official app.
If a company repository is missing or GitHub returns an OAuth access restriction:

1. Open [GitHub Settings → Applications → Authorized OAuth Apps](https://github.com/settings/applications).
2. Select the OAuth app used for this build and check **Organization access**.
3. Grant access if permitted, or request approval from an organization owner.
4. Refresh the repository list in Git Desktop after approval.

For organizations using SAML SSO, establish an active organization SSO session
before authorizing the app. See [GitHub's OAuth authorization guidance](https://docs.github.com/en/apps/oauth-apps/using-oauth-apps/authorizing-oauth-apps).
This port follows GitHub's repository permissions and organization policies.

Release maintainers can configure their own OAuth app with the repository secrets
`DESKTOP_OAUTH_CLIENT_ID` and `DESKTOP_OAUTH_CLIENT_SECRET`. These values are build
inputs for a desktop client, not a place to store personal access tokens. A
production OAuth app must use the `x-github-desktop-auth` callback scheme.

## What this port adds

- A self-contained Debian installer and SHA-256 checksum.
- A GNOME application launcher, desktop identity, icons, and URL handlers.
- Linux startup handling for browser authentication and clone links.
- GNOME keyring credential storage and package-based updates.
- An application-specific AppArmor user-namespace profile for Electron's sandbox.
- Linux packaging for Copilot's native runtime and FFI loader.
- Emoji packaging compatible with older and current gemoji data.
- Automated Ubuntu builds, package installation checks, and application smoke tests.

The desktop continues to use the upstream interface. Full GNOME Wayland/X11
integration and live GitHub authentication still require desktop testing; the CI
smoke test runs under a virtual X11 display. The AppArmor profile allows user
namespaces for the installed executable and is not a full confinement policy.

## Build from source

```bash
git clone --branch ubuntu --recurse-submodules https://github.com/cconner100/git-desktop-ubuntu.git
cd git-desktop-ubuntu
bash script/linux/build-and-install.sh
```

The helper runs from a normal Ubuntu terminal, installs prerequisites using sudo,
builds in a separate cache directory, installs the package, runs smoke tests,
and launches the application. It preserves the source checkout and copies the
installer into `dist/`. Use Ubuntu 24.04 for packages intended to run on both
24.04 and 26.04. A build made on 26.04 is intended for local testing on 26.04.

See [the Ubuntu build guide](docs/contributing/setup-linux.md) for manual build
steps, architecture limits, and desktop verification.

## Automated releases

[Ubuntu package and release](https://github.com/cconner100/git-desktop-ubuntu/actions/workflows/ubuntu.yml)
runs on changes to the `ubuntu` branch, pull requests, manual runs, and
`ubuntu-v*` tags. It builds native modules on Ubuntu 24.04, installs the actual
package, checks shared libraries, runs unit/regression tests and an installed
application smoke test, and checks installation on Ubuntu 26.04.

A tag whose name matches `ubuntu-v` plus the version in `app/package.json`
publishes a GitHub Release with the tested `.deb`, its SHA-256 checksum, and
installation notes. Publication waits for both Ubuntu jobs to succeed.
Versions containing a prerelease suffix are marked as prereleases. Ordinary
branch builds provide Actions artifacts without creating a release.

To publish the current version after committing changes:

```bash
git tag ubuntu-v3.6.7-beta2
git push origin ubuntu-v3.6.7-beta2
```

For a new release, update `app/package.json` and the version/installation examples
in this README before creating the corresponding new tag. Keep tags immutable.
The workflow uses the repository's built-in `GITHUB_TOKEN` to publish assets;
a personal access token is not required for release automation.

## Support and upstream

Report Ubuntu-port problems in [this fork's issues](https://github.com/cconner100/git-desktop-ubuntu/issues).
Include your Ubuntu version, whether you use Wayland or X11, the application
version, and relevant errors from **Help → Show logs in your File Manager** (or
`~/.config/Git Desktop/logs`). Remove credentials and private repository details
before sharing logs.

The original source is [desktop/desktop](https://github.com/desktop/desktop).
This port starts from upstream commit
[`bc09e9e8`](https://github.com/desktop/desktop/commit/bc09e9e8).
The [upstream README](docs/upstream-readme.md) and [contribution guide](.github/CONTRIBUTING.md)
are retained for background and development information.

## License

[MIT](LICENSE). Upstream copyright notices and bundled third-party license
information are preserved. GitHub's trademarks and logos remain owned by GitHub;
the MIT license does not grant trademark rights. This is a community project,
not an official GitHub product or endorsed Ubuntu release.
