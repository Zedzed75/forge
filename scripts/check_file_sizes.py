#!/usr/bin/env python3
"""SRP file-size gate: warn at 601-700 lines, fail above 700.

forge had no such gate, which is how `tests/fingerprint.py` reached 857 lines
and `tests/test_fingerprint.py` 713 without anyone noticing (ZED-223). JARVIS
has had one for a while and it caught its own equivalents at 695 and 610 lines,
early enough that the split was a choice rather than a rescue. This is that gate.

Two scopes, for two reasons:

* **Python under `src/` and `tests/`.** Swept by directory, because the cap is a
  property of hand-written code in general and a new module must not be able to
  opt out by existing.
* **The prose registers we wrote and cap deliberately**, named one at a time.
  A glob over `*.md` would widen and narrow the gate on its own as files come
  and go, and JARVIS learned the cost of the other mistake: its gate globbed
  `*.py` only, so `MEMORY.md` sat at 1116 lines through every green run.

What is deliberately *not* here:

* `tests/golden/**` is generated output. Six files there are over 600 lines and
  all six should be - they are byte-exact generator fixtures, and a gate that
  pushed back on them would be the rule editing the product.
* `README.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md` are
  community and user documentation rather than registers we chose to cap.
* `DECISIONS.md` is **exempt**, and that is D18 rather than a waiver below. It
  is an append-only register cited by number: nobody edits its middle, a
  decision number is an address, and splitting it would make the duplicate-number
  failure it has already produced once *more* likely rather than less. Its own
  preamble states the exemption, so neither end can re-litigate it alone. The
  exemption's form is exactly this - absence from TRACKED_PROSE - and it is
  deliberately *not* a KNOWN_OVERSIZE entry, because that table is a ratchet for
  debt that will be paid and an exemption is not debt.

`DESIGN.md` was the other half of ZED-226 and got the opposite answer, for the
reason that it is a design document rather than a ledger: it was split (D18).
Its `Q` register is now `docs/ARBITRATIONS.md`, its observed-tree record
`docs/REPOSITORY-TREE.md`, and its `forge.yml` schema reference
`docs/FORGE-YML.md` - that last one by ZED-236, because the first split left it
598 lines from a 600-line warning and a two-line margin on a file still being
edited is not a margin. All four files are named below. `docs/` is
outside SCAN_DIRS, so a register there is capped only because it is listed.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

WARN_THRESHOLD = 600
FAIL_THRESHOLD = 700

SCAN_DIRS = ("src", "tests")

# Generated generator output: fixtures, not files anybody wrote by hand.
EXCLUDED_PREFIXES = ("tests/golden/",)

# Registers that cap themselves. Each one named, so a rename is a deliberate
# edit of this tuple rather than a silent change of scope - a path listed here
# that does not exist is a failure.
# `DECISIONS.md` is absent on purpose and that absence is the exemption - see the
# module docstring and D18. Do not add it.
TRACKED_PROSE = (
    "CLAUDE.md",
    "PLAN.md",
    "MIGRATION.md",
    "CHANGELOG.md",
    "DESIGN.md",
    "docs/ARBITRATIONS.md",
    "docs/FORGE-YML.md",
    "docs/PLUGIN-CONTRACT.md",
    "docs/REPOSITORY-TREE.md",
)

# Debt frozen rather than waived: `{repo-relative path: line count measured}`.
#
# The gate enforces **both directions** against each entry, which is what makes
# this a ratchet and not a hole:
#
# * a file here that has grown past its recorded count fails, so the debt
#   cannot quietly get worse while it waits for its issue;
# * a file here that now fits under FAIL_THRESHOLD *also* fails, telling you to
#   delete the entry - so the table cannot outlive the problem and start
#   silently exempting a file that no longer needs it.
#
# Adding an entry is therefore a deliberate act with a visible cost, and the
# table shrinks to empty on its own as the issues land.
#
# It is empty because that happened. The gate shipped holding the two files of
# ZED-223 at 857 and 713 lines; the split landed, both dropped under the cap,
# and the second rule above is what turned their entries from a waiver into a
# failing build until they were deleted. Every branch of the mechanism is still
# tested, against synthetic tables, in `tests/test_file_size_gate.py`.
KNOWN_OVERSIZE: dict[str, int] = {}


def count_lines(path: Path) -> int:
    with path.open(encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def targets(root: Path) -> Iterator[tuple[str, Path]]:
    """Every file under the gate, as (repo-relative path, path)."""
    for scan_dir in SCAN_DIRS:
        for path in sorted((root / scan_dir).rglob("*.py")):
            rel = path.relative_to(root).as_posix()
            if rel.startswith(EXCLUDED_PREFIXES):
                continue
            yield rel, path

    for rel in TRACKED_PROSE:
        yield rel, root / rel


def check(root: Path) -> tuple[list[str], list[str]]:
    """Returns (failures, warnings), each a list of ready-to-print lines."""
    failures: list[str] = []
    warnings: list[str] = []
    seen: set[str] = set()

    for rel, path in targets(root):
        if not path.exists():
            failures.append(f"{rel} is listed in the gate but does not exist")
            continue

        seen.add(rel)
        lines = count_lines(path)
        frozen = KNOWN_OVERSIZE.get(rel)

        if frozen is not None:
            if lines > frozen:
                failures.append(
                    f"{rel} has {lines} lines, up from the {frozen} recorded in "
                    "KNOWN_OVERSIZE. Known debt may not grow; split it instead."
                )
            elif lines <= FAIL_THRESHOLD:
                failures.append(
                    f"{rel} has {lines} lines and now fits the cap - remove its "
                    "KNOWN_OVERSIZE entry so the gate enforces it again."
                )
            continue

        if lines > FAIL_THRESHOLD:
            failures.append(f"{rel} has {lines} lines (hard limit {FAIL_THRESHOLD})")
        elif lines > WARN_THRESHOLD:
            warnings.append(
                f"WARNING: {rel} has {lines} lines "
                f"({WARN_THRESHOLD + 1}-{FAIL_THRESHOLD} range, consider refactoring)"
            )

    for rel in KNOWN_OVERSIZE:
        if rel not in seen:
            failures.append(
                f"{rel} is in KNOWN_OVERSIZE but the gate never scanned it - "
                "the path is wrong, or it now sits outside SCAN_DIRS."
            )

    return failures, warnings


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    failures, warnings = check(root)

    for line in warnings:
        print(line)
    for line in failures:
        print(f"FAIL: {line}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
