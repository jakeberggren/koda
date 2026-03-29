#!/usr/bin/env bash
set -euo pipefail

REPO_OWNER="jakeberggren"
REPO_NAME="koda"
INSTALL_BASE="${HOME}/.local/share/koda"
BIN_DIR="${HOME}/.local/bin"
KODA_VERSION="${KODA_VERSION:-latest}"

info() {
  printf '==> %s\n' "$1"
}

error() {
  printf 'error: %s\n' "$1" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || error "required command not found: $1"
}

print_banner() {
  cat <<'EOF'
╔═══════════════════════════════════════╗
║   ██╗  ██╗ ██████╗ ██████╗  █████╗    ║
║   ██║ ██╔╝██╔═══██╗██╔══██╗██╔══██╗   ║
║   █████╔╝ ██║   ██║██║  ██║███████║   ║
║   ██╔═██╗ ██║   ██║██║  ██║██╔══██║   ║
║   ██║  ██╗╚██████╔╝██████╔╝██║  ██║   ║
║   ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═╝   ║
╚═══════════════════════════════════════╝
EOF
}

# Check required commands
need_cmd curl
need_cmd tar
need_cmd uname
need_cmd mktemp
need_cmd jq

if [[ "${REPO_OWNER}" == "YOUR_GITHUB_USER_OR_ORG" ]]; then
  error "please set REPO_OWNER in install.sh"
fi

# Detect OS and architecture
OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS" in
  Linux)
    PLATFORM="linux"
    ;;
  Darwin)
    PLATFORM="macos"
    ;;
  *)
    error "unsupported operating system: $OS"
    ;;
esac

case "$ARCH" in
  x86_64|amd64)
    ARCH_LABEL="x86_64"
    ;;
  arm64|aarch64)
    ARCH_LABEL="arm64"
    ;;
  *)
    error "unsupported architecture: $ARCH"
    ;;
esac

ARTIFACT_LABEL="${PLATFORM}-${ARCH_LABEL}"

# Resolve tag and construct download URL
if [[ "$KODA_VERSION" == "latest" ]]; then
  KODA_VERSION="$(curl -fsSL "https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/releases/latest" | jq -r '.tag_name')"
fi

if [[ -z "${KODA_VERSION}" || "${KODA_VERSION}" == "null" ]]; then
  error "failed to resolve latest release tag"
fi

ARCHIVE_NAME="koda-${KODA_VERSION}-${ARTIFACT_LABEL}.tar.gz"
DOWNLOAD_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}/releases/download/${KODA_VERSION}/${ARCHIVE_NAME}"

TMP_DIR="$(mktemp -d)"
ARCHIVE_PATH="${TMP_DIR}/${ARCHIVE_NAME}"
INSTALL_DIR="${INSTALL_BASE}/${KODA_VERSION}"
EXTRACTED_DIR="${INSTALL_DIR}/koda-${KODA_VERSION}-${ARTIFACT_LABEL}"

cleanup() {
  rm -rf "${TMP_DIR}"
}

trap cleanup EXIT

info "Downloading ${ARCHIVE_NAME}"
mkdir -p "${TMP_DIR}"
curl -fL "${DOWNLOAD_URL}" --progress-bar -o "${ARCHIVE_PATH}"

info "Preparing install directories"
mkdir -p "${INSTALL_DIR}"
mkdir -p "${BIN_DIR}"

info "Extracting archive"
tar -xzf "${ARCHIVE_PATH}" -C "${INSTALL_DIR}"

EXECUTABLE_PATH="${EXTRACTED_DIR}/koda"
LINK_PATH="${BIN_DIR}/koda"

if [[ ! -x "${EXECUTABLE_PATH}" ]]; then
  error "expected executable not found at ${EXECUTABLE_PATH}"
fi

info "Installing koda to ${LINK_PATH}"
ln -sfn "${EXECUTABLE_PATH}" "${LINK_PATH}"

printf '\n'
print_banner
printf '\n'
info "Installed koda ${KODA_VERSION}"
info "Run: koda"

case ":${PATH}:" in
  *":${BIN_DIR}:"*)
    ;;
  *)
    printf '\n'
    info "${BIN_DIR} is not on your PATH"
    printf 'Add this to your shell profile:\n'
    printf '  export PATH="%s:$PATH"\n' "${BIN_DIR}"
    ;;
esac
