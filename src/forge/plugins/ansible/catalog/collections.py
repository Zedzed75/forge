"""Version constraints of the Galaxy collections the catalogue requires.

A collection is described **here and nowhere else**. A `RoleDefinition` only ever
names a collection, never a version: two roles that depend on the same collection
therefore cannot contradict each other about the expected version.

The policy retained (DESIGN.md §8 Q9) is a **floor and a major ceiling**.

- The floor is the oldest version known to provide everything the templates emit.
  When nobody has checked, it is the version CI validates against: forge does not
  claim to know what it has not tested, and the floor comes down the day someone
  does the check.
- The ceiling is the major following the one CI validates against. Without it, a
  project generated today and installed in six months picks up the next major and
  breaks on a removed module — exactly what happened to forge's CI with
  `community.postgresql` 5.0.0.

The price of the ceiling is accepted: forge has to follow the majors of the
collections it names, otherwise the generated projects age. The bump procedure is
the same as for the tools pinned in `.github/workflows/ci.yml`: bump the version
validated in CI, bump `max_major` here, fix the templates when the major removed
something, and ship the bump in its own commit.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from forge.errors import SpecValidationError


@dataclass(frozen=True)
class CollectionRequirement:
    """A Galaxy collection and the version range forge accepts.

    Attributes:
        name: fully qualified name of the collection (`namespace.name`).
        floor: oldest accepted version, inclusive.
        max_major: first **refused** major; the ceiling is exclusive.
        validated: version forge's CI actually validates the generated projects
            against, quoted as a comment in ``requirements.yml``.
        reason: justification of the floor, echoed as-is as a comment in the
            generated file. One sentence, in the present tense.
    """

    name: str
    floor: str
    max_major: int
    validated: str
    reason: str

    @property
    def version(self) -> str:
        """Constraint in the format ``ansible-galaxy`` expects.

        For example ``>=3.13.0,<6.0.0``. Both bounds are always written: a
        constraint without a ceiling protects against nothing.
        """
        return f">={self.floor},<{self.max_major}.0.0"


#: Table of the collections the catalogue names. Sort by name: it is also the
#: order they are written in `requirements.yml`.
_REQUIREMENTS: tuple[CollectionRequirement, ...] = (
    CollectionRequirement(
        name="ansible.posix",
        floor="2.2.2",
        max_major=3,
        validated="2.2.2",
        reason=(
            "authorized_key and firewalld have existed since 1.0.0, but no version older "
            "than the one validated in CI has been checked: the floor stays high."
        ),
    ),
    CollectionRequirement(
        name="community.general",
        floor="13.4.0",
        max_major=14,
        validated="13.4.0",
        reason=(
            "timezone and ufw have existed since 1.0.0, but no version older than the "
            "one validated in CI has been checked: the floor stays high."
        ),
    ),
    CollectionRequirement(
        name="community.postgresql",
        floor="3.13.0",
        max_major=6,
        validated="5.0.0",
        reason=(
            "postgresql_alter_system, used by the postgresql role, appeared in 3.13.0; "
            "it replaced postgresql_set, removed in 5.0.0."
        ),
    ),
)

COLLECTION_REQUIREMENTS: dict[str, CollectionRequirement] = {
    requirement.name: requirement for requirement in _REQUIREMENTS
}


def requirement_for(name: str) -> CollectionRequirement:
    """Return the version constraint of a collection.

    Raises :class:`SpecValidationError` when the collection is not in the table:
    forge never generates a dependency without a version.
    """
    try:
        return COLLECTION_REQUIREMENTS[name]
    except KeyError:
        known = ", ".join(sorted(COLLECTION_REQUIREMENTS))
        raise SpecValidationError(
            f"Galaxy collection without a version constraint: '{name}'. "
            f"Declared collections: {known}."
        ) from None


def requirements_for(names: Iterable[str]) -> list[CollectionRequirement]:
    """Return the constraints of the given collections, sorted by name and deduplicated."""
    return [requirement_for(name) for name in sorted(set(names))]
