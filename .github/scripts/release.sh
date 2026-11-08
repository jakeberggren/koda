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

base_trailer="Release-Base"

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

is_version_file() {
  case "$1" in
    pyproject.toml | uv.lock) return 0 ;;
    packages/*/*/*) return 1 ;;
    packages/*/pyproject.toml) return 0 ;;
    *) return 1 ;;
  esac
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

release_base() {
  local version="$1" subject commit base bases=()
  subject="release: bump version to ${version}"

  while read -r commit; do
    [[ "$(git log -1 --format=%s "${commit}")" == "${subject}" ]] || continue
    base="$(git log -1 --format="%(trailers:key=${base_trailer},valueonly)" "${commit}")"
    base="${base//[[:space:]]/}"
    if [[ -z "${base}" ]]; then
      echo "${commit} '${subject}' has no ${base_trailer} trailer" >&2
      return 1
    fi
    [[ " ${bases[*]-} " == *" ${base} "* ]] || bases+=("${base}")
  done < <(git log --format=%H --fixed-strings --grep="${subject}" HEAD)

  if [[ "${#bases[@]}" -ne 1 ]]; then
    echo "Expected one '${subject}' commit with a ${base_trailer} trailer, found ${#bases[@]} bases" >&2
    return 1
  fi
  echo "${bases[0]}"
}

check_commit() {
  local version="$1" base path unexpected=()
  base="$(release_base "${version}")"

  if ! git merge-base --is-ancestor "${base}" origin/main; then
    echo "${base_trailer} ${base} is not on main" >&2
    return 1
  fi
  if ! git merge-base --is-ancestor "${base}" HEAD; then
    echo "Release commit is not built on ${base_trailer} ${base}" >&2
    return 1
  fi

  while read -r path; do
    is_version_file "${path}" || unexpected+=("${path}")
  done < <(git diff --name-only "${base}" HEAD)

  if [[ "${#unexpected[@]}" -gt 0 ]]; then
    echo "Release changes files other than version files since ${base}:" >&2
    printf '%s\n' "${unexpected[@]}" >&2
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
