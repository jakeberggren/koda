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
  ./scripts/release.sh [--dry-run] (--patch | --minor | --major)
  ./scripts/release.sh [--dry-run] vX.Y.Z
  ./scripts/release.sh --wait-only vX.Y.Z

Version selection (mutually exclusive):
  --patch      Bump patch version (e.g. 0.3.1 → 0.3.2)
  --minor      Bump minor version (e.g. 0.3.1 → 0.4.0)
  --major      Bump major version (e.g. 0.3.1 → 1.0.0)
  vX.Y.Z       Use explicit version instead of auto-bumping

Other flags:
  --dry-run    Validate and preview, do not create tag or release
  --wait-only  Skip bumping, only wait for release assets

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
DRY_RUN=false
BUMP_TYPE=""

while [[ "${1:-}" == --* ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=true
      ;;
    --wait-only)
      WAIT_ONLY=true
      ;;
    --patch)
      BUMP_TYPE="patch"
      ;;
    --minor)
      BUMP_TYPE="minor"
      ;;
    --major)
      BUMP_TYPE="major"
      ;;
    *)
      usage
      error "unknown option: $1"
      ;;
  esac
  shift
done

if [[ "${WAIT_ONLY}" == true && "${DRY_RUN}" == true ]]; then
  error "--dry-run cannot be combined with --wait-only"
fi

if [[ "${WAIT_ONLY}" == true ]]; then
  [[ -z "${BUMP_TYPE}" ]] || error "--wait-only cannot be combined with --${BUMP_TYPE}"
  VERSION_TAG="${1:-}"
  [[ -n "${VERSION_TAG}" ]] || error "--wait-only requires a tag like vX.Y.Z"
  [[ "${VERSION_TAG}" == v* ]] || error "version must be a tag like vX.Y.Z"
  shift || true
  [[ -z "${1:-}" ]] || error "unexpected extra argument: $1"

  need_cmd gh
else
  need_cmd git
  need_cmd gh
  need_cmd uv

  # Read current version from bump-my-version config
  CURRENT_VERSION=$(uv run bump-my-version show current_version 2>/dev/null) || {
    error "could not read current version from bump-my-version config"
  }
  [[ -n "${CURRENT_VERSION}" ]] || error "current version is empty"

  # Determine target version and bump-my-version part
  if [[ -n "${1:-}" ]]; then
    VERSION_TAG="${1}"
    [[ "${VERSION_TAG}" == v* ]] || error "version must be a tag like vX.Y.Z"
    VERSION="${VERSION_TAG#v}"

    if [[ -n "${BUMP_TYPE}" ]]; then
      error "cannot combine explicit version (${VERSION_TAG}) with --${BUMP_TYPE}"
    fi

    # For explicit versions, we still need a part for bump-my-version.
    # Pick the part that changed, or default to 'patch'.
    BUMP_TYPE=$(python3 -c "
def parse(v):
    return tuple(int(x) for x in v.split('.'))
c = parse('${CURRENT_VERSION}')
n = parse('${VERSION}')
if n[0] > c[0]:
    print('major')
elif n[1] > c[1]:
    print('minor')
else:
    print('patch')
")

    BUMP_ARGS=("${BUMP_TYPE}" "--new-version" "${VERSION}")
  elif [[ -n "${BUMP_TYPE}" ]]; then
    BUMP_ARGS=("${BUMP_TYPE}")
    VERSION=$(python3 -c "
def parse(v):
    return tuple(int(x) for x in v.split('.'))
current = parse('${CURRENT_VERSION}')
bump = '${BUMP_TYPE}'
parts = list(current)
if bump == 'patch':
    parts[2] += 1
elif bump == 'minor':
    parts[1] += 1
    parts[2] = 0
elif bump == 'major':
    parts[0] += 1
    parts[1] = 0
    parts[2] = 0
print('.'.join(str(x) for x in parts))
")
    VERSION_TAG="v${VERSION}"
  else
    usage
    exit 1
  fi

  # Validate new version is greater than current
  python3 -c "
def parse(v):
    return tuple(int(x) for x in v.split('.'))
current = parse('${CURRENT_VERSION}')
new = parse('${VERSION}')
if new <= current:
    print(f'error: {new} must be greater than current version {current}', file=__import__('sys').stderr)
    __import__('sys').exit(1)
" || error "version validation failed"

  if git rev-parse "${VERSION_TAG}" >/dev/null 2>&1; then
    error "local tag already exists: ${VERSION_TAG}"
  fi

  if git ls-remote --exit-code --tags "${REMOTE}" "refs/tags/${VERSION_TAG}" >/dev/null 2>&1; then
    error "remote tag already exists: ${VERSION_TAG}"
  fi

  [[ -z "$(git status --porcelain)" ]] || error "working tree is not clean"

  if [[ "${DRY_RUN}" == true ]]; then
    info "Previewing version bump to ${VERSION_TAG}"
    uv run bump-my-version bump --dry-run --no-commit --no-tag "${BUMP_ARGS[@]}"

    info "Checking uv.lock"
    uv lock --check
  else
    info "Bumping version to ${VERSION_TAG} with bump-my-version"
    uv run bump-my-version bump --no-commit --no-tag "${BUMP_ARGS[@]}"

    info "Refreshing uv.lock"
    uv lock

    info "Creating release commit and tag ${VERSION_TAG}"
    git add pyproject.toml packages/*/pyproject.toml uv.lock
    git commit -m "release: bump version to ${VERSION}"
    git tag -a "${VERSION_TAG}" -m "Release ${VERSION_TAG}"

    info "Pushing commit and tag ${VERSION_TAG}"
    git push "${REMOTE}" HEAD
    git push "${REMOTE}" "${VERSION_TAG}"
  fi
fi

if [[ -n "${RELEASE_ASSET:-}" ]]; then
  RELEASE_ASSETS=("${RELEASE_ASSET}")
else
  RELEASE_ASSETS=("${DEFAULT_RELEASE_ASSETS[@]}")
fi

EXPECTED_ASSET_NAMES=()
for asset_template in "${RELEASE_ASSETS[@]}"; do
  EXPECTED_ASSET_NAMES+=("${asset_template//%s/${VERSION_TAG}}")
done

if [[ "${DRY_RUN}" == true ]]; then
  info "Dry run passed for ${VERSION_TAG}"
  printf 'Current version: %s\n' "${CURRENT_VERSION}"
  printf 'Would bump to: %s\n' "${VERSION}"
  printf 'Previewed: uv run bump-my-version bump --dry-run --no-commit --no-tag %s\n' "${BUMP_ARGS[*]}"
  printf 'Checked: uv lock --check\n'
  printf 'Would create commit: release: bump version to %s\n' "${VERSION}"
  printf 'Would push tag: %s\n' "${VERSION_TAG}"
  printf 'Would wait for release assets:\n'
  for expected_asset_name in "${EXPECTED_ASSET_NAMES[@]}"; do
    printf '  %s\n' "${expected_asset_name}"
  done
  exit 0
fi

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
    if (( ${#UPLOADED_ASSET_NAMES[@]} > 0 )); then
      for uploaded_asset_name in "${UPLOADED_ASSET_NAMES[@]}"; do
        if [[ "${uploaded_asset_name}" == "${expected_asset_name}" ]]; then
          found=true
          break
        fi
      done
    fi

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
