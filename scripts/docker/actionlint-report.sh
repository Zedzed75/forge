#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# actionlint over one revision's workflows, as JSON (decision D7, clause C2).
# ---------------------------------------------------------------------------
# Reads a tar of `.github/workflows` on stdin -- `git archive <rev>` produces
# exactly that -- and prints actionlint's findings for that revision as a JSON
# array on stdout. Nothing else goes to stdout: the caller parses it.
#
# It prints findings; it does not judge them. Deciding which findings the pull
# request *introduces* is the caller's job, because the clause is differential:
# an absolute "actionlint clean" gate would be unsatisfiable through no fault of
# the pull request, which is the mistake D4's six-checks clause already made
# once.
#
#   exit 0  the run completed; stdout holds the findings (possibly none)
#   exit 2  the run did not complete, and stdout means nothing
# ---------------------------------------------------------------------------
set -uo pipefail

src=/src
rm -rf "$src"
mkdir -p "$src" || { printf 'actionlint-report: cannot create %s\n' "$src" >&2; exit 2; }

tar -x -C "$src" \
  || { printf 'actionlint-report: could not unpack the revision from stdin\n' >&2; exit 2; }
cd "$src" || exit 2

if [ ! -d .github/workflows ]; then
  printf 'actionlint-report: the revision has no .github/workflows directory\n' >&2
  printf '[]\n'
  exit 0
fi

# Sorted, so the two revisions are read in the same order and the comparison is
# not at the mercy of the filesystem.
files=()
while IFS= read -r file; do
  files+=("$file")
done < <(find .github/workflows -type f \( -name '*.yml' -o -name '*.yaml' \) | LC_ALL=C sort)

if [ "${#files[@]}" -eq 0 ]; then
  printf '[]\n'
  exit 0
fi

# `{{json .}}` prints the whole finding list as one JSON array, which keeps the
# caller out of the business of parsing actionlint's human format. actionlint
# finds shellcheck on PATH by itself; `-shellcheck` is passed explicitly so that
# an image without it fails loudly here instead of silently skipping the one
# pass C2 was built for.
actionlint \
  -format '{{json .}}' \
  -no-color \
  -shellcheck shellcheck \
  -- "${files[@]}"
status=$?

# actionlint exits 1 when it has findings, which is not a failure of this run.
# Anything above that is.
if [ "$status" -gt 1 ]; then
  printf 'actionlint-report: actionlint exited %s\n' "$status" >&2
  exit 2
fi
exit 0
