"""Comparison between an existing target and a fresh render (DESIGN.md §5.5).

`pretend` writes nothing at all, so it is unusable here: forge renders into a
temporary directory then compares the trees. The output is a **summary** — files
added / removed / modified and the number of changed lines — never a full diff
(context economy rule from CLAUDE.md).
"""

from __future__ import annotations

import difflib
from collections.abc import Collection
from dataclasses import dataclass, field
from pathlib import Path

#: Files ignored by the comparison: copier's own bookkeeping, whose `_commit`
#: changes on every render.
IGNORED_NAMES = frozenset({".copier-answers.yml"})


@dataclass
class DomainDiff:
    """Difference found on one domain."""

    domain: str
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    modified: list[tuple[str, int]] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        """True if the target matches the fresh render exactly."""
        return not (self.added or self.removed or self.modified)

    def summary(self) -> str:
        """One-line summary, never quoting file contents."""
        if self.empty:
            return f"{self.domain}: up to date"
        return (
            f"{self.domain}: {len(self.added)} addition(s), "
            f"{len(self.removed)} removal(s), {len(self.modified)} modification(s)"
        )


def _relative_files(root: Path, ignore: Collection[str] = ()) -> dict[str, Path]:
    """Files under `root`, indexed by relative path.

    `ignore` carries **top-level names** to leave out: that is what makes a
    domain whose output is the repository root comparable. Without it, such a
    domain would see the other domains' directories as files removed from its
    template.
    """
    files: dict[str, Path] = {}
    if not root.is_dir():
        return files
    excluded = set(ignore)
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.name in IGNORED_NAMES:
            continue
        relative = path.relative_to(root)
        if relative.parts[0] in excluded:
            continue
        files[relative.as_posix()] = path
    return files


def count_changed_lines(left: str, right: str) -> int:
    """Number of lines differing between two already loaded texts."""
    matcher = difflib.SequenceMatcher(
        None, left.splitlines(), right.splitlines(), autojunk=False
    )
    changed = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            changed += max(i2 - i1, j2 - j1)
    return changed


def _changed_lines(left: Path, right: Path) -> int:
    """Number of lines differing between two files; -1 if binary."""
    try:
        # Read as bytes: `read_text` would hide a line-ending divergence.
        a = left.read_bytes().decode("utf-8")
        b = right.read_bytes().decode("utf-8")
    except (UnicodeDecodeError, OSError):
        return -1
    return count_changed_lines(a, b)


def diff_trees(
    domain: str, current: Path, fresh: Path, *, ignore: Collection[str] = ()
) -> DomainDiff:
    """Compare the `current` target against the `fresh` render.

    "added" means: present in the fresh render, absent from the target.

    `ignore` is only filled in for a domain whose output **is** the repository
    root: there it leaves out what belongs to the other domains and to the
    repository-level files, compared elsewhere.
    """
    result = DomainDiff(domain=domain)
    current_files = _relative_files(current, ignore)
    fresh_files = _relative_files(fresh)

    for name in sorted(set(fresh_files) - set(current_files)):
        result.added.append(name)
    for name in sorted(set(current_files) - set(fresh_files)):
        result.removed.append(name)
    for name in sorted(set(current_files) & set(fresh_files)):
        left, right = current_files[name], fresh_files[name]
        if left.read_bytes() == right.read_bytes():
            continue
        result.modified.append((name, _changed_lines(left, right)))
    return result
