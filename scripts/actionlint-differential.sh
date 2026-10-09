#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# What does this workflow change break? Clause C2 of decision D7.
# ---------------------------------------------------------------------------
# D6's exception exists because the matrix container is a reimplementation of
# `.github/workflows/ci.yml` and so says nothing about the workflow file
# itself. C2 is the clause that earns D7: `actionlint` does read it, and its
# shellcheck pass catches the one way a translation really breaks a workflow --
# quoting damage inside a string that was rewritten.
#
#   ./scripts/actionlint-differential.sh origin/master my-branch
#
#   exit 0  the head revision introduces no actionlint finding the base does
#           not already carry. Clause C2 passes.
#   exit 1  it introduces at least one. They are printed, with the file and the
#           rule, and the PR waits for billing.
#   exit 2  the witness could not run, and has therefore witnessed nothing.
#
# **Differential, never absolute.** The gate is "no *new* finding", not
# "actionlint clean": an absolute gate would be unsatisfiable through no fault
# of the pull request, which is the mistake D4's six-checks clause made once
# already. Line and column are deliberately ignored when findings are matched,
# because prose changes move every line below them; a finding counts as the
# same finding when its file, its rule and its message are the same.
#
# Pinned the same way the matrix is: actionlint comes from the matrix image
# itself, at the version `ci.yml` pins, and the run starts by re-checking that
# pin with `docker-matrix.sh --verify-pins-only`. The image adds one tool the
# matrix does not have -- `shellcheck`, pinned in
# `scripts/docker/Dockerfile.actionlint` -- because actionlint only runs its
# shell pass when it finds it.
#
# Exit 0 is a statement about C2 only. C1 (`workflow-diff-is-prose.sh`), C3
# (`docker-matrix.sh`) and C4 all still apply. See `D7` in `DECISIONS.md`.
# ---------------------------------------------------------------------------
set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
DOCKER_DIR="${SCRIPT_DIR}/docker"
MATRIX_IMAGE_NAME="forge-ci-matrix"
WITNESS_IMAGE_NAME="forge-actionlint-witness"

die() { printf 'actionlint-differential: %s\n' "$*" >&2; exit 2; }

case "${1:-}" in
  -h|--help) sed -n '2,35p' "${BASH_SOURCE[0]}"; exit 0 ;;
esac

[ $# -eq 2 ] || die "usage: actionlint-differential.sh <base> <head>"
base="$1"
head_rev="$2"

python_bin=""
for candidate in python3 python py; do
  if command -v "$candidate" >/dev/null 2>&1 \
     && "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' \
          >/dev/null 2>&1; then
    python_bin="$candidate"
    break
  fi
done
[ -n "$python_bin" ] || die "no Python 3.9+ on PATH"

base_sha="$(git -C "$REPO_ROOT" rev-parse --verify "${base}^{commit}" 2>/dev/null)" \
  || die "not a commit: ${base}"
head_sha="$(git -C "$REPO_ROOT" rev-parse --verify "${head_rev}^{commit}" 2>/dev/null)" \
  || die "not a commit: ${head_rev}"
# The merge base, not the tip of the base branch: a finding that master gained
# after this branch forked is not a finding the branch introduced.
merge_base="$(git -C "$REPO_ROOT" merge-base "$base_sha" "$head_sha" 2>/dev/null)" \
  || die "no merge base between ${base} and ${head_rev}"

# ---------------------------------------------------------------------------
# The same pins as the matrix
# ---------------------------------------------------------------------------
# actionlint's version lives in `Dockerfile.ci-matrix` and must match `ci.yml`;
# the matrix script is what checks that, so call it rather than re-implement it.
# A witness pinned to a different actionlint than CI would be a different
# witness wearing CI's name.
printf -- '--- D7 clause C2: does the change introduce an actionlint finding? ---\n'
"${SCRIPT_DIR}/docker-matrix.sh" --verify-pins-only >/dev/null \
  || die "pin drift between the container and .github/workflows/ci.yml; run
./scripts/docker-matrix.sh --verify-pins-only to see it"
actionlint_version="$(sed -n 's/^ARG ACTIONLINT_VERSION=\(.*\)$/\1/p' \
                        "${DOCKER_DIR}/Dockerfile.ci-matrix")"
shellcheck_version="$(sed -n 's/^ARG SHELLCHECK_VERSION=\(.*\)$/\1/p' \
                        "${DOCKER_DIR}/Dockerfile.actionlint")"

# ---------------------------------------------------------------------------
# A Linux engine, or nothing
# ---------------------------------------------------------------------------
command -v docker >/dev/null 2>&1 || die "docker is not on PATH"
engine_os="$(docker info --format '{{.OSType}}' 2>/dev/null)"
[ -n "$engine_os" ] || die "cannot reach a Docker daemon"
[ "$engine_os" = "linux" ] || \
  die "the Docker engine reports OSType=${engine_os}; the witness runs on Linux"

# ---------------------------------------------------------------------------
# The images
# ---------------------------------------------------------------------------
# The matrix image is tagged by the digest of its own two inputs -- the same
# computation as `docker-matrix.sh`, so the two scripts agree on which image is
# current without either of them owning the other.
matrix_tag="$( { cat "${DOCKER_DIR}/Dockerfile.ci-matrix" "${DOCKER_DIR}/run-matrix.sh"; } \
                 | sha256sum | cut -c1-12)"
matrix_image="${MATRIX_IMAGE_NAME}:${matrix_tag}"
if ! docker image inspect "$matrix_image" >/dev/null 2>&1; then
  printf 'building %s (the matrix image the witness derives from)\n' "$matrix_image"
  docker build --file "${DOCKER_DIR}/Dockerfile.ci-matrix" --tag "$matrix_image" \
    "${DOCKER_DIR}" >/dev/null 2>&1 || die "could not build ${matrix_image}"
fi

witness_tag="$( { cat "${DOCKER_DIR}/Dockerfile.actionlint" "${DOCKER_DIR}/actionlint-report.sh"; \
                  printf '%s\n' "$matrix_tag"; } | sha256sum | cut -c1-12)"
witness_image="${WITNESS_IMAGE_NAME}:${witness_tag}"
if ! docker image inspect "$witness_image" >/dev/null 2>&1; then
  printf 'building %s\n' "$witness_image"
  docker build --file "${DOCKER_DIR}/Dockerfile.actionlint" \
    --build-arg "BASE_IMAGE=${matrix_image}" --tag "$witness_image" \
    "${DOCKER_DIR}" >/dev/null 2>&1 || die "could not build ${witness_image}"
fi

# ---------------------------------------------------------------------------
# One run per revision
# ---------------------------------------------------------------------------
work="$(mktemp -d 2>/dev/null)" || die "cannot create a temporary directory"
cleanup() { rm -rf -- "$work"; }
trap cleanup EXIT

# `git archive` carries the revision's workflows and nothing else, on stdin, so
# nothing has to be mounted -- this repository lives on a mapped network drive
# on Windows, which Docker Desktop cannot bind-mount.
report() {
  local rev="$1" out="$2"
  git -C "$REPO_ROOT" archive --format=tar "$rev" -- .github/workflows \
    > "${work}/${rev}.tar" 2>/dev/null \
    || die "could not archive .github/workflows at ${rev}"
  docker run --rm --interactive "$witness_image" \
    < "${work}/${rev}.tar" > "$out" 2> "${work}/${rev}.err"
  local status=$?
  if [ "$status" -ne 0 ]; then
    printf 'actionlint-differential: the witness failed on %s:\n' "$rev" >&2
    cat "${work}/${rev}.err" >&2
    exit 2
  fi
}

printf 'base:    %s  %s\n' "${merge_base:0:12}" \
  "$(git -C "$REPO_ROOT" log -1 --format=%s "$merge_base")"
printf 'head:    %s  %s\n' "${head_sha:0:12}" \
  "$(git -C "$REPO_ROOT" log -1 --format=%s "$head_sha")"
printf 'witness: actionlint %s + shellcheck %s, %s\n' \
  "$actionlint_version" "$shellcheck_version" "$witness_image"

report "$merge_base" "${work}/base.json"
report "$head_sha" "${work}/head.json"

# ---------------------------------------------------------------------------
# The difference
# ---------------------------------------------------------------------------
"$python_bin" - "${work}/base.json" "${work}/head.json" <<'PYTHON'
import collections
import json
import sys


def findings(path):
    """actionlint's findings, keyed so that a prose change cannot move them.

    Line and column are dropped on purpose: inserting a comment shifts every
    finding below it, and a differential gate that counted those as new would
    refuse every diff. What identifies a finding is its file, its rule and its
    message.
    """
    with open(path, encoding="utf-8") as handle:
        text = handle.read().strip()
    if not text:
        return collections.Counter(), 0
    try:
        items = json.loads(text)
    except json.JSONDecodeError as error:
        sys.stderr.write(f"actionlint-differential: unreadable report {path}: {error}\n")
        raise SystemExit(2)
    counter = collections.Counter(
        (item.get("filepath", "?"), item.get("kind", "?"), item.get("message", "?"))
        for item in items
    )
    return counter, len(items)


base, base_total = findings(sys.argv[1])
head, head_total = findings(sys.argv[2])

introduced = head - base
resolved = base - head

print(f"findings: {base_total} on the base, {head_total} on the head")
if resolved:
    for (path, kind, message), count in sorted(resolved.items()):
        print(f"  resolved  {path}  [{kind}] {message}" + (f" (x{count})" if count > 1 else ""))
print("---")
if introduced:
    print(f"result:  C2 FAILS. {sum(introduced.values())} finding(s) introduced:")
    for (path, kind, message), count in sorted(introduced.items()):
        print(f"  NEW  {path}  [{kind}] {message}" + (f" (x{count})" if count > 1 else ""))
    print("         The D6 exception stands: this PR waits for Actions billing.")
    print("--- end ---")
    raise SystemExit(1)
print("result:  C2 PASSES. The head introduces no finding the base does not carry.")
print("         C1, C3 and C4 still apply.")
print("--- end ---")
PYTHON
exit $?
