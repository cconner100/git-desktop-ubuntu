#!/usr/bin/env bash
# Build this source snapshot and install a local test package from a normal
# Ubuntu terminal. Build tools live in a separate cache directory.
set -Eeuo pipefail

if [[ "${1:-}" == --help ]]; then
  cat <<'HELP'
Usage: bash script/linux/build-and-install.sh

Installs Ubuntu build prerequisites using sudo, downloads the pinned Node.js
version with checksum verification, builds this modified source in a separate
directory, creates and installs a Debian package, runs the installed application's
smoke test, and launches Git Desktop. Requires network access and a normal
Ubuntu desktop terminal. Builds on Ubuntu 26.04 are for local testing; use the
Ubuntu 24.04 workflow to produce packages for both supported releases.
HELP
  exit 0
fi
if [[ $# -ne 0 ]]; then
  echo 'Unexpected argument. Use --help for usage.' >&2
  exit 2
fi

if [[ $(awk '/^NoNewPrivs:/ { print $2 }' /proc/self/status) != 0 ]]; then
  echo 'This process cannot use sudo because no-new-privileges is enabled.' >&2
  echo 'Run this script in your normal Ubuntu terminal outside the restricted session.' >&2
  exit 1
fi
if [[ $EUID -eq 0 ]]; then
  echo 'Run as your desktop user. The script uses sudo only for system packages.' >&2
  exit 1
fi
if [[ $(uname -m) != x86_64 ]]; then
  echo 'The local installer currently supports x86_64 only.' >&2
  exit 1
fi

source /etc/os-release
if [[ $ID != ubuntu || ( $VERSION_ID != 24.04 && $VERSION_ID != 26.04 ) ]]; then
  echo 'This installer targets Ubuntu 24.04 and 26.04 LTS.' >&2
  exit 1
fi

if [[ $VERSION_ID == 26.04 ]]; then
  # The pinned Playwright release has no Ubuntu 26.04 ffmpeg download. Keep
  # application smoke tests and traces enabled, without optional video capture.
  export DESKTOP_E2E_RECORD_VIDEO=0
fi

TASK_PROJECT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
TASK_NODE_VERSION=$(tr -d '[:space:]' < "$TASK_PROJECT_DIR/.node-version")
if [[ ! $TASK_NODE_VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo 'Invalid pinned Node version in .node-version.' >&2
  exit 1
fi
TASK_CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/git-desktop"
mkdir -p "$TASK_CACHE_DIR" "$TASK_PROJECT_DIR/dist"
TASK_WORK_DIR=$(mktemp -d "$TASK_CACHE_DIR/build.XXXXXXXX")
TASK_SOURCE_DIR="$TASK_WORK_DIR/source"
TASK_TOOLS_DIR="$TASK_WORK_DIR/tools"
TASK_LOG="$TASK_WORK_DIR/build-and-install.log"
mkdir -p "$TASK_SOURCE_DIR" "$TASK_TOOLS_DIR/bin"
exec > >(tee -a "$TASK_LOG") 2>&1
trap 'echo "Build or installation stopped. Log: $TASK_LOG" >&2' ERR

echo "Building this source snapshot for local testing on Ubuntu $VERSION_ID."
echo "Build directory: $TASK_WORK_DIR"
sudo -v
sudo apt-get update
sudo apt-get install -y build-essential git python3 curl ca-certificates xz-utils \
  libsecret-1-dev libgtk-3-0t64 libnss3 libasound2t64 libgbm1 libxss1 libxtst6 \
  libcurl4t64 desktop-file-utils apparmor xvfb xauth dbus-x11 gnome-keyring

# Copy the user's actual modified files. The original source is not altered.
tar -C "$TASK_PROJECT_DIR" \
  --exclude='./.git' --exclude='./node_modules' --exclude='./app/node_modules' \
  --exclude='./out' --exclude='./dist' --exclude='./gemoji' \
  --exclude='./app/static/common/gitignore' \
  --exclude='./app/static/common/choosealicense.com' \
  --exclude='__pycache__' --exclude='build' \
  -cf - . | tar -C "$TASK_SOURCE_DIR" -xf -

TASK_NODE_ARCHIVE="node-v$TASK_NODE_VERSION-linux-x64.tar.xz"
TASK_NODE_URL="https://nodejs.org/dist/v$TASK_NODE_VERSION"
curl --fail --location --retry 3 "$TASK_NODE_URL/$TASK_NODE_ARCHIVE" \
  --output "$TASK_TOOLS_DIR/$TASK_NODE_ARCHIVE"
curl --fail --location --retry 3 "$TASK_NODE_URL/SHASUMS256.txt" \
  --output "$TASK_TOOLS_DIR/SHASUMS256.txt"
(
  cd "$TASK_TOOLS_DIR"
  awk -v archive="$TASK_NODE_ARCHIVE" '$2 == archive { print; found = 1 } END { if (!found) exit 1 }' \
    SHASUMS256.txt > node-checksum.txt
  sha256sum --check node-checksum.txt
  tar -xf "$TASK_NODE_ARCHIVE"
)
export PATH="$TASK_TOOLS_DIR/node-v$TASK_NODE_VERSION-linux-x64/bin:$TASK_TOOLS_DIR/bin:$PATH"
export GIT_DESKTOP_BUILD_YARN="$TASK_SOURCE_DIR/vendor/yarn-1.21.1.js"
cat > "$TASK_TOOLS_DIR/bin/yarn" <<'YARN'
#!/bin/sh
exec node "$GIT_DESKTOP_BUILD_YARN" "$@"
YARN
chmod 755 "$TASK_TOOLS_DIR/bin/yarn"

# Archives do not include the Git metadata required by the upstream build.
# Record a real commit of this snapshot in the disposable build directory.
git -C "$TASK_SOURCE_DIR" init -q
TASK_SUBMODULE_PATHS=(gemoji app/static/common/gitignore app/static/common/choosealicense.com)
TASK_SUBMODULE_URLS=(
  https://github.com/github/gemoji.git
  https://github.com/github/gitignore.git
  https://github.com/github/choosealicense.com.git
)
for TASK_INDEX in "${!TASK_SUBMODULE_PATHS[@]}"; do
  TASK_SUBMODULE_PATH="${TASK_SUBMODULE_PATHS[$TASK_INDEX]}"
  git -C "$TASK_SOURCE_DIR" submodule add --depth 1 \
    "${TASK_SUBMODULE_URLS[$TASK_INDEX]}" "$TASK_SUBMODULE_PATH"
  # Preserve pinned dependency revisions when the supplied source has Git data.
  TASK_SUBMODULE_REVISION=$(git -C "$TASK_PROJECT_DIR" ls-tree HEAD -- "$TASK_SUBMODULE_PATH" 2>/dev/null |
    awk '$1 == "160000" { print $3 }') || TASK_SUBMODULE_REVISION=''
  if [[ -n $TASK_SUBMODULE_REVISION ]]; then
    git -C "$TASK_SOURCE_DIR/$TASK_SUBMODULE_PATH" fetch --depth 1 origin "$TASK_SUBMODULE_REVISION"
    git -C "$TASK_SOURCE_DIR/$TASK_SUBMODULE_PATH" checkout --detach "$TASK_SUBMODULE_REVISION"
  fi
done
git -C "$TASK_SOURCE_DIR" add --all
git -C "$TASK_SOURCE_DIR" -c user.name='Git Desktop local build' \
  -c user.email='local-build@example.invalid' -c core.hooksPath=/dev/null \
  commit -q -m 'Local test build of the supplied source snapshot'

cd "$TASK_SOURCE_DIR"
# Production mode during dependency installation would omit Electron and the
# build/test tools. Select it only when compiling and packaging.
env -u NODE_ENV yarn install --frozen-lockfile
yarn compile:script
yarn test:ubuntu-package
export RELEASE_CHANNEL=production
yarn build:ubuntu

shopt -s nullglob
TASK_PACKAGES=("$TASK_SOURCE_DIR"/dist/git-desktop_*_amd64.deb)
if [[ ${#TASK_PACKAGES[@]} -ne 1 ]]; then
  echo 'Expected exactly one completed Debian package.' >&2
  exit 1
fi
TASK_PACKAGE="${TASK_PACKAGES[0]}"
(
  cd "$TASK_SOURCE_DIR/dist"
  sha256sum --check "$(basename "$TASK_PACKAGE").sha256"
)
cp -- "$TASK_PACKAGE" "$TASK_PACKAGE.sha256" "$TASK_PROJECT_DIR/dist/"
sudo apt-get install -y "$TASK_PACKAGE"
python3 script/linux/check_runtime.py /opt/git-desktop
DESKTOP_E2E_APP_PATH=/opt/git-desktop/desktop \
  xvfb-run -a dbus-run-session -- yarn test:e2e:run:packaged

echo "Installed Git Desktop. Installer: $TASK_PROJECT_DIR/dist/$(basename "$TASK_PACKAGE")"
echo "Build log: $TASK_LOG"
nohup /usr/bin/git-desktop > "$TASK_WORK_DIR/application.log" 2>&1 < /dev/null &
