"""Verifications de nommage generiques, sans vocabulaire de domaine.

Portage de la partie domaine-agnostique de `ansible_forge.validation`
(MIGRATION.md §3) : les regex propres a Ansible restent dans son plugin.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

#: Label DNS (RFC 1123) : lettres minuscules, chiffres et tirets internes.
DNS_LABEL_RE = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")

#: Sous-domaine DNS : des labels separes par des points.
SUBDOMAIN_RE = re.compile(
    r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$"
)

#: Version semantique simplifiee : MAJEUR.MINEUR.CORRECTIF, pre-release optionnel.
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")


def check_pattern(value: str, pattern: re.Pattern[str], what: str) -> str:
    """Retourne `value` si elle respecte `pattern`, sinon leve `ValueError`.

    `what` decrit la contrainte en francais, il apparait tel quel dans le
    message d'erreur pydantic.
    """
    if not pattern.match(value):
        raise ValueError(f"{value!r} n'est pas {what}")
    return value


def find_duplicates(values: Iterable[str]) -> list[str]:
    """Liste, dans l'ordre de premiere apparition, les valeurs vues deux fois."""
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def require_unique(values: Iterable[str], what: str) -> None:
    """Leve `ValueError` si `values` contient des doublons."""
    duplicates = find_duplicates(values)
    if duplicates:
        raise ValueError(f"{what} en double : {', '.join(sorted(duplicates))}")
