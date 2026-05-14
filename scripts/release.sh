#!/usr/bin/env bash
set -euo pipefail

REPO_OWNER="jakeberggren"
REPO_NAME="koda"
REMOTE="${REMOTE:-origin}"
DEFAULT_RELEASE_ASSETS=(
  'koda-%s-linux-x86_64.tar.gz'
  'koda-%s-linux-arm64.tar.gz'
  'koda-%s-macos-x86_64.tar.gz'
  'koda-%s-macos-arm64.tar.gz'
)
WAIT_TIMEOUT_SECONDS="${WAIT_TIMEOUT_SECONDS:-1800}"
WAIT_INTERVAL_SECONDS="${WAIT_INTERVAL_SECONDS:-15}"

error() {
  printf 'error: %s\n' "$1" >&2
  exit 1
}

info() {
  printf '==> %s\n' "$1"
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || error "required command not found: $1"
}

usage() {
  cat <<'EOF'
Usage:
  ./ship.sh vX.Y.Z
  ./ship.sh --wait-only vX.Y.Z

Environment overrides:
  REMOTE=origin
  RELEASE_ASSET='koda-%s-linux-arm64.tar.gz'  # wait for one asset only
  WAIT_TIMEOUT_SECONDS=1800
  WAIT_INTERVAL_SECONDS=15
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

WAIT_ONLY=false
if [[ "${1:-}" == "--wait-only" ]]; then
  WAIT_ONLY=true
  shift
fi

VERSION_TAG="${1:-}"
[[ -n "${VERSION_TAG}" ]] || {
  usage
  exit 1
}
[[ "${VERSION_TAG}" == v* ]] || error "version must be a tag like vX.Y.Z"
VERSION="${VERSION_TAG#v}"

need_cmd git
need_cmd gh

[[ -z "$(git status --porcelain)" ]] || error "working tree is not clean"

for pyproject in packages/*/pyproject.toml; do
  if ! grep -q "^version = \"${VERSION}\"$" "${pyproject}"; then
    error "${pyproject} does not have version ${VERSION}"
  fi
done

if [[ "${WAIT_ONLY}" == false ]]; then
  if git rev-parse "${VERSION_TAG}" >/dev/null 2>&1; then
    error "local tag already exists: ${VERSION_TAG}"
  fi

  if git ls-remote --exit-code --tags "${REMOTE}" "refs/tags/${VERSION_TAG}" >/dev/null 2>&1; then
    error "remote tag already exists: ${VERSION_TAG}"
  fi

  info "Creating tag ${VERSION_TAG}"
  git tag "${VERSION_TAG}"

  info "Pushing tag ${VERSION_TAG}"
  git push "${REMOTE}" "${VERSION_TAG}"
fi

if [[ -n "${RELEASE_ASSET:-}" ]]; then
  RELEASE_ASSETS=("${RELEASE_ASSET}")
else
  RELEASE_ASSETS=("${DEFAULT_RELEASE_ASSETS[@]}")
fi

EXPECTED_ASSET_NAMES=()
for asset_template in "${RELEASE_ASSETS[@]}"; do
  EXPECTED_ASSET_NAMES+=("$(printf "${asset_template}" "${VERSION_TAG}")")
done

DEADLINE=$((SECONDS + WAIT_TIMEOUT_SECONDS))
info "Waiting for release assets"
while true; do
  UPLOADED_ASSET_NAMES=()
  while IFS= read -r uploaded_asset_name; do
    UPLOADED_ASSET_NAMES+=("${uploaded_asset_name}")
  done < <(gh release view "${VERSION_TAG}" \
    --repo "${REPO_OWNER}/${REPO_NAME}" \
    --json assets \
    --jq '.assets[].name' 2>/dev/null)

  missing_asset_names=()
  for expected_asset_name in "${EXPECTED_ASSET_NAMES[@]}"; do
    found=false
    for uploaded_asset_name in "${UPLOADED_ASSET_NAMES[@]}"; do
      if [[ "${uploaded_asset_name}" == "${expected_asset_name}" ]]; then
        found=true
        break
      fi
    done

    if [[ "${found}" == false ]]; then
      missing_asset_names+=("${expected_asset_name}")
    fi
  done

  if (( ${#missing_asset_names[@]} == 0 )); then
    break
  fi

  if (( SECONDS >= DEADLINE )); then
    error "timed out waiting for: ${missing_asset_names[*]}"
  fi

  info "Still waiting for: ${missing_asset_names[*]}"
  sleep "${WAIT_INTERVAL_SECONDS}"
done

info "Shipped ${VERSION_TAG}"
