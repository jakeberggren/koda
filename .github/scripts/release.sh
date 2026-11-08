#!/usr/bin/env bash
# Release checks shared by the release workflows.
#
#   release.sh versions VERSION   Version files in the working tree are VERSION.
#   release.sh commit VERSION     HEAD is a valid release commit for VERSION.
#
# A release commit is the main commit that Prepare Release branched from (its
# "Release-Base" trailer) plus version bumps only. Anything merged into main
# afterwards, or pulled into the release branch, fails the check.

set -euo pipefail

# Prints the string value of KEY in TOML table SECTION, e.g. "[project]".
toml_value() {
  local path="$1" section="$2" key="$3"
  awk -v section="${section}" -v key="${key}" '
    /^[[:space:]]*\[/ { in_section = ($0 == section); next }
    in_section && $0 ~ "^" key "[[:space:]]*=[[:space:]]*\"" {
      sub(/^[^"]*"/, ""); sub(/".*$/, ""); print; exit
    }
  ' "${path}"
}

check_versions() {
  local version="$1" path found failed=0

  found="$(toml_value pyproject.toml "[tool.bumpversion]" current_version)"
  if [[ "${found}" != "${version}" ]]; then
    echo "pyproject.toml: version is ${found:-missing}, expected ${version}" >&2
    failed=1
  fi

  for path in packages/*/pyproject.toml; do
    found="$(toml_value "${path}" "[project]" version)"
    if [[ "${found}" != "${version}" ]]; then
      echo "${path}: version is ${found:-missing}, expected ${version}" >&2
      failed=1
    fi
  done

  return "${failed}"
}

check_commit() {
  local version="$1" base unexpected
  base="$(git log -1 --format="%(trailers:key=Release-Base,valueonly)" \
    --grep="^release: bump version to ${version//./\\.}$" HEAD | tr -d '[:space:]')"

  if [[ -z "${base}" ]]; then
    echo "No 'release: bump version to ${version}' commit with a Release-Base trailer" >&2
    return 1
  fi
  if ! git merge-base --is-ancestor "${base}" origin/main; then
    echo "Release-Base ${base} is not on main" >&2
    return 1
  fi

  unexpected="$(git diff --name-only "${base}" HEAD -- . \
    ':!pyproject.toml' ':!uv.lock' ':(exclude,glob)packages/*/pyproject.toml')"
  if [[ -n "${unexpected}" ]]; then
    echo "Release changes files other than version files since ${base}:" >&2
    echo "${unexpected}" >&2
    return 1
  fi

  check_versions "${version}"
}

case "${1-}" in
  versions) check_versions "$2" ;;
  commit) check_commit "$2" ;;
  *)
    echo "usage: release.sh versions|commit VERSION" >&2
    exit 2
    ;;
esac
