#!/usr/bin/env bash
set -euo pipefail

REPO_OWNER="jakeberggren"
REPO_NAME="koda"
REMOTE="${REMOTE:-origin}"
DOCKER_IMAGE="${DOCKER_IMAGE:-docker.io/jakeberggren/koda-sandbox}"
RELEASE_ASSET="${RELEASE_ASSET:-koda-%s-linux-arm64.tar.gz}"
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
  ./ship.sh --image-only vX.Y.Z

Environment overrides:
  REMOTE=origin
  DOCKER_IMAGE=docker.io/jakeberggren/koda-sandbox
  RELEASE_ASSET='koda-%s-linux-arm64.tar.gz'
  WAIT_TIMEOUT_SECONDS=1800
  WAIT_INTERVAL_SECONDS=15
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

IMAGE_ONLY=false
if [[ "${1:-}" == "--image-only" ]]; then
  IMAGE_ONLY=true
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
need_cmd docker

[[ -z "$(git status --porcelain)" ]] || error "working tree is not clean"

for pyproject in packages/*/pyproject.toml; do
  if ! grep -q "^version = \"${VERSION}\"$" "${pyproject}"; then
    error "${pyproject} does not have version ${VERSION}"
  fi
done

if [[ "${IMAGE_ONLY}" == false ]]; then
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

ASSET_NAME="$(printf "${RELEASE_ASSET}" "${VERSION_TAG}")"
DEADLINE=$((SECONDS + WAIT_TIMEOUT_SECONDS))
info "Waiting for release asset ${ASSET_NAME}"
while true; do
  if gh release view "${VERSION_TAG}" \
    --repo "${REPO_OWNER}/${REPO_NAME}" \
    --json assets \
    --jq '.assets[].name' 2>/dev/null | grep -Fxq "${ASSET_NAME}"; then
    break
  fi

  if (( SECONDS >= DEADLINE )); then
    error "timed out waiting for ${ASSET_NAME}"
  fi

  sleep "${WAIT_INTERVAL_SECONDS}"
done

info "Building Docker Sandbox image"
docker build \
  --build-arg "KODA_VERSION=${VERSION_TAG}" \
  -t "${DOCKER_IMAGE}:${VERSION_TAG}" \
  -t "${DOCKER_IMAGE}:latest" \
  -f docker/sandbox/Dockerfile .

info "Pushing ${DOCKER_IMAGE}:${VERSION_TAG}"
docker push "${DOCKER_IMAGE}:${VERSION_TAG}"

info "Pushing ${DOCKER_IMAGE}:latest"
docker push "${DOCKER_IMAGE}:latest"

info "Shipped ${VERSION_TAG}"
