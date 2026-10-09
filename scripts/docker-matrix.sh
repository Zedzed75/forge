#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Produce the CI matrix locally, in Linux containers (decision D6).
# ---------------------------------------------------------------------------
# While GitHub Actions is unavailable, a pull request may merge on evidence from
# this script instead of on the six green checks. That is a change of *host*,
# not of standard: same suite, same three interpreters, same pinned validators,
# same `FORGE_REQUIRE_TOOLS=1`. Anything weaker than this -- a Windows-local
# run, a single interpreter, a run with validators missing -- is not D6 evidence
# and must not be reported as such.
#
#   ./scripts/docker-matrix.sh                       # HEAD of the current worktree
#   ./scripts/docker-matrix.sh --ref my-branch       # a named local branch
#   ./scripts/docker-matrix.sh --python 3.12         # one cell, for a quick look
#   ./scripts/docker-matrix.sh --verify-pins-only    # drift check, no containers
#
# Requires a Docker daemon with a **Linux** engine (`docker info` must report
# `OSType: linux`); the script refuses to run against a Windows engine rather
# than produce a result that proves nothing about `ubuntu-24.04` -- the explicit
# label D10 requires the workflows to name, and what `ubuntu-latest` resolved to
# when D6 was taken. From 2026-10-19 `ubuntu-latest` no longer means 24.04
# (`actions/runner-images#14748`), so the host this run stands in for is named
# by its version here, never by the floating label.
#
# Exit status is the evidence: 0 only if every requested cell passed.
# ---------------------------------------------------------------------------
set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
DOCKER_DIR="${SCRIPT_DIR}/docker"
WORKFLOW="${REPO_ROOT}/.github/workflows/ci.yml"
VERSION_TABLE="${REPO_ROOT}/tests/tool_versions.py"
# Where CI declares its toolchain. Two files since the `ubuntu-26.04` canary
# needed a second job: the install steps moved into a composite action so that
# the gating job and the canary could share one definition, and the pinned
# versions moved with them. `verify_pins` greps this set rather than `$WORKFLOW`
# alone, because a pin is "declared by CI" wherever in CI it is written -- and
# the alternative was this gate reporting fourteen phantom drifts the moment the
# steps moved, which is a gate that has to be switched off to be believed.
#
# The matrix itself is still read from `$WORKFLOW` only: `python-version` names a
# matrix axis there and an action input here, and those are different claims.
CI_PIN_FILES=(
  "$WORKFLOW"
  "${REPO_ROOT}/.github/actions/forge-ci-setup/action.yml"
)

IMAGE_NAME="forge-ci-matrix"
UV_CACHE_VOLUME="forge-ci-matrix-uv-cache"

# The matrix of `.github/workflows/ci.yml`. Checked against the workflow by
# `verify_pins`, so a version added there without a change here fails loudly.
DEFAULT_PYTHONS=(3.11 3.12 3.13)

ref="HEAD"
pythons=()
jobs=0
do_build=1
use_cache=1
verify_only=0
log_dir=""

die() { printf 'docker-matrix: %s\n' "$*" >&2; exit 2; }

while [ $# -gt 0 ]; do
  case "$1" in
    --ref)              ref="${2:?--ref needs a value}"; shift 2 ;;
    --python)           pythons+=("${2:?--python needs a value}"); shift 2 ;;
    --jobs)             jobs="${2:?--jobs needs a value}"; shift 2 ;;
    --log-dir)          log_dir="${2:?--log-dir needs a value}"; shift 2 ;;
    --no-build)         do_build=0; shift ;;
    --no-cache)         use_cache=0; shift ;;
    --verify-pins-only) verify_only=1; shift ;;
    -h|--help)          sed -n '2,24p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *)                  die "unknown argument: $1" ;;
  esac
done

[ "${#pythons[@]}" -gt 0 ] || pythons=("${DEFAULT_PYTHONS[@]}")
# Serial by default would triple the wall clock for no gain: the cells are
# independent, as they are in CI where `fail-fast: false` lets all three finish.
[ "$jobs" -gt 0 ] 2>/dev/null || jobs="${#pythons[@]}"

# ---------------------------------------------------------------------------
# Pin drift
# ---------------------------------------------------------------------------
# The container declares the toolchain a second time, and a second declaration
# rots. Rather than trust the duplication, extract every pinned version out of
# the two container files and require each one to appear verbatim somewhere in
# CI's own declaration -- `$CI_PIN_FILES`, the workflow plus the composite
# action it gets its toolchain from. A bump on either side breaks the match,
# which is the point: D6
# evidence from a container pinned to other versions than CI would be a
# different environment wearing CI's name.
verify_pins() {
  local failures=0 pin
  # Every one of them, not just the workflow: a file this gate cannot read is a
  # file whose pins it silently stops checking, and "no drift found" would then
  # mean "nowhere left to look".
  local pin_file
  for pin_file in "${CI_PIN_FILES[@]}"; do
    [ -r "$pin_file" ] || die "cannot read ${pin_file}"
  done

  # `ARG NAME=value` in the Dockerfile: the five domains' binaries, plus uv and
  # its checksum.
  local dockerfile_pins
  dockerfile_pins="$(sed -n 's/^ARG [A-Z0-9_]*=\(.*\)$/\1/p' "${DOCKER_DIR}/Dockerfile.ci-matrix")"

  # `'package==version'` and `namespace.collection:version` in the run script:
  # the Ansible tooling, the Galaxy collections and yamllint.
  local runner_pins
  runner_pins="$(grep -oE "'[a-z0-9_-]+==[0-9][0-9a-z.]*'|[a-z]+\.[a-z]+:[0-9][0-9.]*" \
                   "${DOCKER_DIR}/run-matrix.sh" | tr -d "'" | sort -u)"

  while IFS= read -r pin; do
    [ -n "$pin" ] || continue
    if ! grep -qF -- "$pin" "${CI_PIN_FILES[@]}"; then
      printf 'pin drift: %s is pinned in the container but nowhere in CI (%s)\n' \
        "$pin" "${CI_PIN_FILES[*]#"${REPO_ROOT}/"}" >&2
      failures=$((failures + 1))
    fi
  done <<< "${dockerfile_pins}
${runner_pins}"

  # The interpreter list is the matrix itself, so compare it as a set rather
  # than one member at a time: CI gaining a fourth Python must fail here, and a
  # missing-member check would not notice.
  local workflow_pythons
  workflow_pythons="$(sed -n 's/^ *python-version: *\[\(.*\)\] *$/\1/p' "$WORKFLOW" \
                        | tr -d ' "' | tr ',' '\n' | sort -u | paste -sd, -)"
  local declared_pythons
  declared_pythons="$(printf '%s\n' "${DEFAULT_PYTHONS[@]}" | sort -u | paste -sd, -)"
  if [ "$workflow_pythons" != "$declared_pythons" ]; then
    printf 'pin drift: workflow matrix is [%s], this script declares [%s]\n' \
      "$workflow_pythons" "$declared_pythons" >&2
    failures=$((failures + 1))
  fi

  # The third declaration: `tests/tool_versions.py`. The two checks above keep
  # the container and the workflow honest about what gets *requested*; that
  # table is what the suite asserts the installed binaries actually *report*
  # (`tests/conftest.py::require_expected_versions`). It is one more copy of
  # the same nine numbers, so it goes through the same verbatim loop -- in both
  # directions, against CI's declaration and against the container files. A bump
  # that lands in two of the three places fails here instead of silently
  # asserting a version nothing installs.
  [ -r "$VERSION_TABLE" ] || die "cannot read ${VERSION_TABLE}"
  local container_files=("${DOCKER_DIR}/Dockerfile.ci-matrix" "${DOCKER_DIR}/run-matrix.sh")

  # `"name": ExpectedVersion("1.2.3", ...)` -> `name 1.2.3`.
  local table_rows
  table_rows="$(sed -n 's/^ *"\([a-z0-9-]*\)": *ExpectedVersion("\([0-9][0-9a-z.]*\)".*/\1 \2/p' \
                  "$VERSION_TABLE")"

  # A row this loop cannot read is a row it silently stops checking, which is
  # the failure mode the table exists to close one level up. So account for
  # every row: those with a version, plus those explicitly marked UNPINNED.
  # A reformatting or a renamed constant then fails loudly rather than
  # shrinking the gate to nothing.
  local all_rows versioned_rows unpinned_rows
  all_rows="$(grep -cE '^ *"[a-z0-9-]*": *ExpectedVersion\(' "$VERSION_TABLE")"
  versioned_rows="$(printf '%s\n' "$table_rows" | grep -c '[^[:space:]]')"
  unpinned_rows="$(grep -cE '^ *"[a-z0-9-]*": *ExpectedVersion\(UNPINNED' "$VERSION_TABLE")"
  if [ "$all_rows" -eq 0 ] || [ "$all_rows" -ne $((versioned_rows + unpinned_rows)) ]; then
    printf 'pin drift: %s has %s row(s), of which this gate can read %s pinned and %s unpinned\n' \
      "${VERSION_TABLE#"${REPO_ROOT}/"}" "$all_rows" "$versioned_rows" "$unpinned_rows" >&2
    failures=$((failures + 1))
  fi

  local tool version
  while read -r tool version; do
    [ -n "${version:-}" ] || continue
    if ! grep -qF -- "$version" "${CI_PIN_FILES[@]}"; then
      printf 'pin drift: %s is expected at %s by the test table but CI pins no such version (%s)\n' \
        "$tool" "$version" "${CI_PIN_FILES[*]#"${REPO_ROOT}/"}" >&2
      failures=$((failures + 1))
    fi
    if ! grep -qF -- "$version" "${container_files[@]}"; then
      printf 'pin drift: %s is expected at %s by the test table but the container pins no such version\n' \
        "$tool" "$version" >&2
      failures=$((failures + 1))
    fi
  done <<< "$table_rows"

  if [ "$failures" -gt 0 ]; then
    printf '\n%s pinned value(s) differ between the container, CI and %s.\n' \
      "$failures" "${VERSION_TABLE#"${REPO_ROOT}/"}" >&2
    printf 'Reconcile them before trusting a matrix run as D6 evidence.\n' >&2
    return 1
  fi
  printf 'pins: container, %s and %s agree (%s tool version(s) asserted)\n' \
    "${CI_PIN_FILES[*]#"${REPO_ROOT}/"}" "${VERSION_TABLE#"${REPO_ROOT}/"}" "$versioned_rows"
  return 0
}

verify_pins || exit 1
[ "$verify_only" -eq 1 ] && exit 0

# ---------------------------------------------------------------------------
# A Linux engine, or nothing
# ---------------------------------------------------------------------------
command -v docker >/dev/null 2>&1 || die "docker is not on PATH"
engine_os="$(docker info --format '{{.OSType}}' 2>/dev/null)"
[ -n "$engine_os" ] || die "cannot reach a Docker daemon"
[ "$engine_os" = "linux" ] || \
  die "the Docker engine reports OSType=${engine_os}; D6 evidence requires a Linux engine"

# ---------------------------------------------------------------------------
# The sources
# ---------------------------------------------------------------------------
# A bundle of a dirty worktree quietly omits the uncommitted part, and a matrix
# result that does not correspond to a commit cannot be recorded against a PR.
# Refuse rather than mislead.
dirty="$(git -C "$REPO_ROOT" status --porcelain --untracked-files=no)"
[ -z "$dirty" ] || die "the worktree has uncommitted changes; commit them first
(a git bundle carries commits only, so the matrix would test something other
than what you are looking at)"

sha="$(git -C "$REPO_ROOT" rev-parse --verify "${ref}^{commit}" 2>/dev/null)" \
  || die "not a commit in this repository: ${ref}"

: "${log_dir:=${TMPDIR:-/tmp}/forge-ci-matrix-${sha:0:12}-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$log_dir" || die "cannot create log directory ${log_dir}"
bundle="${log_dir}/repo.bundle"

# `git bundle` wants a ref name, not a bare sha, and it must carry the full
# history: the workflow checks out with `fetch-depth: 0` because copier resolves
# a template by git reference.
bundle_branch=""
if [ "$ref" != "HEAD" ]; then
  git -C "$REPO_ROOT" rev-parse --verify --quiet "refs/heads/${ref}" >/dev/null \
    || die "--ref must name a local branch or be HEAD (got: ${ref})"
  # Bundling a branch produces a bundle with that branch and no `HEAD`, which a
  # bare clone cannot check out; the container is told which name to ask for.
  bundle_branch="$ref"
fi
git -C "$REPO_ROOT" bundle create "$bundle" "${bundle_branch:-HEAD}" >/dev/null 2>&1 \
  || die "could not bundle ${bundle_branch:-HEAD}"

# ---------------------------------------------------------------------------
# The image
# ---------------------------------------------------------------------------
# Tagged by the digest of its own two inputs, so editing either file produces a
# different tag and a stale image can never be mistaken for the current one.
image_tag="$( { cat "${DOCKER_DIR}/Dockerfile.ci-matrix" "${DOCKER_DIR}/run-matrix.sh"; } \
                | sha256sum | cut -c1-12)"
image="${IMAGE_NAME}:${image_tag}"

if [ "$do_build" -eq 1 ]; then
  printf 'building %s\n' "$image"
  docker build --file "${DOCKER_DIR}/Dockerfile.ci-matrix" --tag "$image" "${DOCKER_DIR}" \
    > "${log_dir}/build.log" 2>&1 || {
      printf 'image build failed; last 40 lines of %s:\n' "${log_dir}/build.log" >&2
      tail -40 "${log_dir}/build.log" >&2
      exit 1
    }
else
  docker image inspect "$image" >/dev/null 2>&1 \
    || die "--no-build was given but ${image} does not exist locally"
fi

# ---------------------------------------------------------------------------
# The cells
# ---------------------------------------------------------------------------
cache_args=()
if [ "$use_cache" -eq 1 ]; then
  # A named volume, not a bind mount: it needs no host path translation (this
  # repository lives on a mapped network drive on Windows, which Docker Desktop
  # cannot share) and it is the local equivalent of the workflow's
  # `enable-cache: true`. `--no-cache` drops it when a run must start cold.
  cache_args=(--volume "${UV_CACHE_VOLUME}:/root/.cache/uv")
fi

printf 'commit:  %s  %s\n' "${sha:0:12}" "$(git -C "$REPO_ROOT" log -1 --format=%s "$sha")"
printf 'matrix:  %s (%s at a time)\n' "${pythons[*]}" "$jobs"
printf 'logs:    %s\n\n' "$log_dir"

run_cell() {
  local py="$1"
  docker run --rm --interactive \
    --name "forge-ci-matrix-${sha:0:8}-${py//./}" \
    --env "FORGE_MATRIX_BRANCH=${bundle_branch}" \
    "${cache_args[@]}" \
    "$image" "$py" \
    < "$bundle" > "${log_dir}/python-${py}.log" 2>&1
  printf '%s\n' "$?" > "${log_dir}/python-${py}.status"
}

running=0
for py in "${pythons[@]}"; do
  run_cell "$py" &
  running=$((running + 1))
  if [ "$running" -ge "$jobs" ]; then
    wait -n 2>/dev/null || wait
    running=$((running - 1))
  fi
done
wait

# ---------------------------------------------------------------------------
# The verdict
# ---------------------------------------------------------------------------
# Printed in the shape that goes onto the PR's issue, so that recording the
# evidence is a copy rather than a retelling.
printf '\n--- D6 local matrix: %s ---\n' "${sha:0:12}"
overall=0
for py in "${pythons[@]}"; do
  status="$(cat "${log_dir}/python-${py}.status" 2>/dev/null || echo 1)"
  summary="$(grep -aoE '[0-9]+ (passed|failed)[^=]*' "${log_dir}/python-${py}.log" | tail -1)"
  # `grep -c` always prints a count, and exits 1 on zero matches; an `|| echo 0`
  # here would append a second line and make "0" compare unequal to itself.
  skipped="$(grep -ac '^SKIPPED' "${log_dir}/python-${py}.log" 2>/dev/null)"
  if [ "$status" = "0" ]; then
    printf 'Python %-5s PASS  %s\n' "$py" "${summary:-(no pytest summary found)}"
  else
    overall=1
    printf 'Python %-5s FAIL  (exit %s) %s\n' "$py" "$status" "${summary:-}"
    printf '  first failure:\n'
    grep -aE '^(FAILED|ERROR) ' "${log_dir}/python-${py}.log" | head -3 | sed 's/^/    /'
  fi
  [ "$skipped" = "0" ] || printf '  %s skip line(s) reported -- read %s\n' \
    "$skipped" "${log_dir}/python-${py}.log"
done
printf 'engine: Docker %s, OSType=linux, image %s\n' \
  "$(docker version --format '{{.Server.Version}}' 2>/dev/null)" "$image"
printf -- '--- end ---\n'

exit "$overall"
