"""Generic naming checks, free of any domain vocabulary.

Port of the domain-agnostic part of `ansible_forge.validation`
(MIGRATION.md §3): the Ansible-specific regexes stay in its plugin.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

#: DNS label (RFC 1123): lowercase letters, digits and internal hyphens.
DNS_LABEL_RE = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")

#: DNS subdomain: labels separated by dots.
SUBDOMAIN_RE = re.compile(
    r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$"
)

#: Simplified semantic version: MAJOR.MINOR.PATCH, optional pre-release.
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")


def check_pattern(value: str, pattern: re.Pattern[str], what: str) -> str:
    """Return `value` if it matches `pattern`, otherwise raise `ValueError`.

    `what` describes the constraint and appears verbatim in the pydantic error
    message.
    """
    if not pattern.match(value):
        raise ValueError(f"{value!r} is not {what}")
    return value


def find_duplicates(values: Iterable[str]) -> list[str]:
    """List, in order of first appearance, the values seen twice."""
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def require_unique(values: Iterable[str], what: str) -> None:
    """Raise `ValueError` if `values` contains duplicates."""
    duplicates = find_duplicates(values)
    if duplicates:
        raise ValueError(f"duplicate {what}: {', '.join(sorted(duplicates))}")
