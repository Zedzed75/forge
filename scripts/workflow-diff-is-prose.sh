#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Is a workflow diff prose? Clause C1 of decision D7, as an exit code.
# ---------------------------------------------------------------------------
# D6 parks any pull request that touches `.github/workflows/**` until Actions
# runs again, because a container cannot exercise `uses:` pins, Actions caching,
# OIDC or trigger behaviour. D7 reads that exception as the list of behaviours
# it is written as: a diff that reaches none of them was never what the
# exception was protecting against. This script decides whether a given diff is
# such a diff -- with an exit code, so that nobody has to read the diff and
# judge.
#
#   ./scripts/workflow-diff-is-prose.sh origin/master my-branch
#   ./scripts/workflow-diff-is-prose.sh origin/master pr61
#
#   exit 0  every changed line in every `.github/workflows/**` file is a YAML
#           comment, a step-level `name:` value, or literal text inside an
#           already-quoted string in a `run:` block. Clause C1 passes.
#   exit 1  something behavioural changed, or the diff could not be classified.
#           The PR waits for billing. The report names the lines.
#   exit 2  the script could not run at all (bad revision, no Python).
#
# Exit 0 is a statement about C1 only. It is not a merge authorisation: C2
# (`scripts/actionlint-differential.sh`), C3 (`scripts/docker-matrix.sh`) and C4
# all still have to pass. See `D7` in `DECISIONS.md`.
#
# How it decides: `scripts/workflow_prose_skeleton.py` normalises each file at
# each revision, erasing exactly what C1 permits and copying everything else,
# then the two skeletons are compared. A key the normaliser has never heard of
# is copied, so a change to it fails -- the test is fail-closed by construction
# rather than by keeping a list of forbidden keys up to date.
# ---------------------------------------------------------------------------
set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
NORMALISER="${SCRIPT_DIR}/workflow_prose_skeleton.py"
WORKFLOW_PATHSPEC='.github/workflows'

die() { printf 'workflow-diff-is-prose: %s\n' "$*" >&2; exit 2; }

case "${1:-}" in
  -h|--help) sed -n '2,32p' "${BASH_SOURCE[0]}"; exit 0 ;;
esac

[ $# -eq 2 ] || die "usage: workflow-diff-is-prose.sh <base> <head>"
base="$1"
head_rev="$2"

[ -r "$NORMALISER" ] || die "cannot read ${NORMALISER}"

# Any Python 3 will do -- the normaliser is standard library only, on purpose:
# the witness must run on a developer machine and inside the matrix container
# without a project environment having been created first.
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

base_sha="$(git rev-parse --verify "${base}^{commit}" 2>/dev/null)" \
  || die "not a commit: ${base}"
head_sha="$(git rev-parse --verify "${head_rev}^{commit}" 2>/dev/null)" \
  || die "not a commit: ${head_rev}"

# `A...B` is the diff from the merge base to B, which is what a pull request
# shows. Comparing B against the tip of A would report master's own advance as
# the PR's doing.
merge_base="$(git merge-base "$base_sha" "$head_sha" 2>/dev/null)" \
  || die "no merge base between ${base} and ${head_rev}"

work="$(mktemp -d 2>/dev/null)" || die "cannot create a temporary directory"
cleanup() { rm -rf -- "$work"; }
trap cleanup EXIT

printf -- '--- D7 clause C1: is the workflow diff prose? ---\n'
printf 'base:    %s  %s\n' "${merge_base:0:12}" "$(git log -1 --format=%s "$merge_base")"
printf 'head:    %s  %s\n' "${head_sha:0:12}" "$(git log -1 --format=%s "$head_sha")"

changed="$(git diff --name-status "${merge_base}..${head_sha}" -- "$WORKFLOW_PATHSPEC")" \
  || die "git diff failed"

if [ -z "$changed" ]; then
  printf 'result:  no file under %s/ changed; C1 does not apply.\n' "$WORKFLOW_PATHSPEC"
  printf '         This PR is inside plain D6 and needs no D7 reading.\n'
  printf -- '--- end ---\n'
  exit 0
fi

failures=0
examined=0

# `skeleton_of <rev> <path> <output>` -- the normalised form of one file at one
# revision. A file that is absent at that revision yields an empty skeleton,
# which is what makes an added or deleted workflow show up as a difference.
skeleton_of() {
  local rev="$1" path="$2" out="$3" blob="${work}/blob"
  # `MSYS_NO_PATHCONV` only around the `<rev>:<path>` arguments: MSYS on Windows
  # rewrites them into a Windows path and git then reports an unknown
  # revision. Exporting it for the whole script instead would hand the *Python
  # interpreter* an unconverted POSIX path, which fails just as hard.
  if MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' git cat-file -e "${rev}:${path}" 2>/dev/null
  then
    MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' git show "${rev}:${path}" > "$blob" 2>/dev/null \
      || return 1
  else
    : > "$blob"
  fi
  "$python_bin" "$NORMALISER" "$blob" > "$out"
}

printf 'files:\n'
while IFS=$'\t' read -r status path rest; do
  [ -n "${status:-}" ] || continue

  # A rename or a copy is not a prose change: the file name is part of what
  # GitHub resolves, and `rest` holds the new path. Fail rather than guess.
  case "$status" in
    R*|C*) printf '  %-12s FAIL  renamed or copied (%s -> %s)\n' \
             "$path" "$path" "${rest:-?}"; failures=$((failures + 1)); continue ;;
    A*)    printf '  %-12s FAIL  added; a new workflow file is never prose\n' \
             "$path"; failures=$((failures + 1)); continue ;;
    D*)    printf '  %-12s FAIL  deleted; removing a workflow is behavioural\n' \
             "$path"; failures=$((failures + 1)); continue ;;
    M*|T*) : ;;
    *)     printf '  %-12s FAIL  unclassifiable git status %s\n' \
             "$path" "$status"; failures=$((failures + 1)); continue ;;
  esac

  case "$path" in
    *.yml|*.yaml) : ;;
    *) printf '  %-12s FAIL  not a YAML workflow; C1 classifies workflow syntax only\n' \
         "$path"; failures=$((failures + 1)); continue ;;
  esac

  examined=$((examined + 1))
  if ! skeleton_of "$merge_base" "$path" "${work}/base.skel"; then
    printf '  %-12s FAIL  could not normalise the base revision\n' "$path"
    failures=$((failures + 1))
    continue
  fi
  if ! skeleton_of "$head_sha" "$path" "${work}/head.skel"; then
    printf '  %-12s FAIL  could not normalise the head revision\n' "$path"
    failures=$((failures + 1))
    continue
  fi

  changed_lines="$(git diff --numstat "${merge_base}..${head_sha}" -- "$path" \
                     | awk 'NR == 1 { printf "+%s/-%s", $1, $2 }')"
  if diff -u "${work}/base.skel" "${work}/head.skel" > "${work}/skel.diff" 2>&1; then
    printf '  %-12s prose (%s lines, none of them behavioural)\n' \
      "$path" "${changed_lines:-?}"
  else
    printf '  %-12s FAIL  behavioural change (%s lines)\n' \
      "$path" "${changed_lines:-?}"
    # The skeleton difference *is* the explanation: every line printed here is a
    # line C1 does not allow to move.
    sed -n '4,$p' "${work}/skel.diff" | grep -E '^[-+]' | head -20 | sed 's/^/      /'
    failures=$((failures + 1))
  fi
done <<< "$changed"

printf -- '---\n'
if [ "$failures" -gt 0 ]; then
  printf 'result:  C1 FAILS on %s file(s) of %s examined.\n' "$failures" "$examined"
  printf '         The D6 exception stands: this PR waits for Actions billing.\n'
  printf -- '--- end ---\n'
  exit 1
fi
printf 'result:  C1 PASSES. Every changed line in %s workflow file(s) is a comment,\n' "$examined"
printf '         a step-level name, or text inside an already-quoted run: string.\n'
printf '         C2, C3 and C4 still apply.\n'
printf -- '--- end ---\n'
exit 0
