"""Catalogue des rôles proposés par le plugin ``ansible``.

L'ordre du catalogue est figé : il détermine l'ordre d'affichage des questions,
l'ordre des rôles dans les playbooks générés et donc la reproductibilité de la
sortie. Ne jamais réordonner sans régénérer les références golden.

Portage de `ansible_forge.catalog.registry` (MIGRATION.md §3) : le `CatalogError`
de l'outil d'origine n'existe plus ; un rôle ou une option inconnus violent la
spécification, c'est donc `forge.errors.SpecValidationError` qui les signale.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from forge.errors import SpecValidationError
from forge.plugins.ansible.catalog.collections import CollectionRequirement, requirements_for
from forge.plugins.ansible.catalog.definition import OptionKind, RoleDefinition, RoleOption
from forge.plugins.ansible.catalog.roles import (
    common,
    docker,
    firewall,
    nginx,
    postgresql,
    ssh_hardening,
    users,
)

#: Ordre d'application des rôles : socle système d'abord, services ensuite.
_ORDERED_ROLES: tuple[RoleDefinition, ...] = (
    common.ROLE,
    users.ROLE,
    ssh_hardening.ROLE,
    firewall.ROLE,
    nginx.ROLE,
    docker.ROLE,
    postgresql.ROLE,
)

ROLE_CATALOG: dict[str, RoleDefinition] = {role.name: role for role in _ORDERED_ROLES}

# Un rôle ne peut pas nommer une collection absente de la table des versions :
# l'oubli casse l'import du plugin ici, et non le projet de l'utilisateur six
# mois plus tard. C'est le seul endroit où les deux tables se rencontrent.
requirements_for(name for role in _ORDERED_ROLES for name in role.collections)


def role_names() -> list[str]:
    """Retourne les noms des rôles du catalogue, dans l'ordre d'application."""
    return [role.name for role in _ORDERED_ROLES]


def all_roles() -> tuple[RoleDefinition, ...]:
    """Retourne les définitions du catalogue, dans l'ordre d'application.

    Ajout par rapport à `ansible_forge` : le hook `forge_catalog` du plugin a
    besoin des définitions elles-mêmes, pas seulement de leurs noms, et l'ordre
    d'application ne doit pas passer par la variable privée `_ORDERED_ROLES`.
    """
    return _ORDERED_ROLES


def get_role(name: str) -> RoleDefinition:
    """Retourne la définition du rôle demandé.

    Lève :class:`SpecValidationError` si le rôle n'existe pas.
    """
    try:
        return ROLE_CATALOG[name]
    except KeyError:
        known = ", ".join(role_names())
        raise SpecValidationError(
            f"Rôle inconnu : '{name}'. Rôles disponibles : {known}."
        ) from None


def sort_roles(names: list[str] | tuple[str, ...]) -> list[str]:
    """Trie des noms de rôles selon l'ordre d'application du catalogue."""
    order = {name: index for index, name in enumerate(role_names())}
    return sorted(names, key=lambda name: order[get_role(name).name])


def collections_for(names: list[str] | tuple[str, ...]) -> list[str]:
    """Retourne les collections Galaxy requises par les rôles donnés, triées et dédupliquées."""
    required: set[str] = set()
    for name in names:
        required.update(get_role(name).collections)
    return sorted(required)


def collection_requirements_for(
    names: list[str] | tuple[str, ...],
) -> list[CollectionRequirement]:
    """Idem `collections_for`, mais avec la contrainte de version de chaque collection.

    C'est cette forme que lisent les gabarits : une dépendance Galaxy n'est
    jamais écrite sans l'intervalle de versions qui la rend reproductible.
    """
    return requirements_for(collections_for(names))


def validate_options(role_name: str, options: dict[str, Any]) -> dict[str, Any]:
    """Valide et complète les options d'un rôle.

    Les clés inconnues déclenchent une :class:`SpecValidationError` ; les options
    absentes sont complétées par leur valeur par défaut. Le dictionnaire
    retourné est ordonné selon la définition du rôle, ce qui garantit une
    sérialisation stable dans ``forge.yml``.
    """
    role = get_role(role_name)
    known = {opt.name for opt in role.options}
    unknown = sorted(set(options) - known)
    if unknown:
        allowed = ", ".join(sorted(known)) or "(aucune)"
        raise SpecValidationError(
            f"Option(s) inconnue(s) pour le rôle '{role_name}' : {', '.join(unknown)}. "
            f"Options acceptées : {allowed}."
        )

    resolved: dict[str, Any] = {}
    for opt in role.options:
        value = options.get(opt.name, opt.default)
        resolved[opt.name] = _coerce(f"{role_name}.{opt.name}", opt, value)
    return resolved


def _coerce(label: str, option: RoleOption, value: Any) -> Any:
    """Vérifie qu'une valeur d'option est compatible avec son type déclaré."""
    kind = option.kind
    choices = option.choices

    if kind is OptionKind.BOOL:
        if not isinstance(value, bool):
            raise SpecValidationError(f"L'option '{label}' attend un booléen, reçu : {value!r}.")
        return value

    if kind is OptionKind.INT:
        if isinstance(value, bool) or not isinstance(value, int):
            raise SpecValidationError(f"L'option '{label}' attend un entier, reçu : {value!r}.")
        return value

    if kind is OptionKind.CHOICE:
        if value not in choices:
            raise SpecValidationError(
                f"L'option '{label}' attend une valeur parmi {', '.join(choices)}, reçu : {value!r}."
            )
        return value

    if kind is OptionKind.LIST:
        if not isinstance(value, list):
            raise SpecValidationError(f"L'option '{label}' attend une liste, reçu : {value!r}.")
        item_option = replace(option, kind=option.item_kind, name=option.name)
        return [
            _coerce(f"{label}[{index}]", item_option, item) for index, item in enumerate(value)
        ]

    if kind is OptionKind.RECORDS:
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise SpecValidationError(
                f"L'option '{label}' attend une liste de dictionnaires, reçu : {value!r}."
            )
        return [_coerce_record(f"{label}[{index}]", option, item) for index, item in enumerate(value)]

    if not isinstance(value, str):
        raise SpecValidationError(f"L'option '{label}' attend une chaîne, reçu : {value!r}.")
    return value


def _coerce_record(label: str, option: RoleOption, record: dict[str, Any]) -> dict[str, Any]:
    """Valide un dictionnaire d'une option de type RECORDS.

    Les clés inconnues sont refusées et les champs absents prennent leur valeur
    par défaut, exactement comme pour les options de premier niveau.
    """
    known = {field.name for field in option.fields}
    unknown = sorted(set(record) - known)
    if unknown:
        raise SpecValidationError(
            f"Champ(s) inconnu(s) dans '{label}' : {', '.join(unknown)}. "
            f"Champs acceptés : {', '.join(sorted(known))}."
        )
    return {
        field.name: _coerce(f"{label}.{field.name}", field, record.get(field.name, field.default))
        for field in option.fields
    }
