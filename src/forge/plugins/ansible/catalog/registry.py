"""Catalogue of the roles offered by the ``ansible`` plugin.

The order of the catalogue is frozen: it determines the display order of the
questions, the order of the roles in the generated playbooks, and therefore the
reproducibility of the output. Never reorder it without regenerating the golden
references.

Port of `ansible_forge.catalog.registry` (MIGRATION.md §3): the `CatalogError` of
the original tool no longer exists; an unknown role or option violates the
specification, so `forge.errors.SpecValidationError` is what reports them.
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

#: Order the roles are applied in: the system base first, the services next.
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

# A role cannot name a collection that is absent from the version table: the
# omission breaks the import of the plugin here, and not the user's project six
# months later. This is the only place where the two tables meet.
requirements_for(name for role in _ORDERED_ROLES for name in role.collections)


def role_names() -> list[str]:
    """Return the names of the catalogue roles, in application order."""
    return [role.name for role in _ORDERED_ROLES]


def all_roles() -> tuple[RoleDefinition, ...]:
    """Return the catalogue definitions, in application order.

    An addition compared with `ansible_forge`: the plugin's `forge_catalog` hook
    needs the definitions themselves, not just their names, and the application
    order must not go through the private `_ORDERED_ROLES` variable.
    """
    return _ORDERED_ROLES


def get_role(name: str) -> RoleDefinition:
    """Return the definition of the requested role.

    Raises :class:`SpecValidationError` when the role does not exist.
    """
    try:
        return ROLE_CATALOG[name]
    except KeyError:
        known = ", ".join(role_names())
        raise SpecValidationError(
            f"Unknown role: '{name}'. Available roles: {known}."
        ) from None


def sort_roles(names: list[str] | tuple[str, ...]) -> list[str]:
    """Sort role names according to the application order of the catalogue."""
    order = {name: index for index, name in enumerate(role_names())}
    return sorted(names, key=lambda name: order[get_role(name).name])


def collections_for(names: list[str] | tuple[str, ...]) -> list[str]:
    """Return the Galaxy collections the given roles require, sorted and deduplicated."""
    required: set[str] = set()
    for name in names:
        required.update(get_role(name).collections)
    return sorted(required)


def collection_requirements_for(
    names: list[str] | tuple[str, ...],
) -> list[CollectionRequirement]:
    """Same as `collections_for`, but with each collection's version constraint.

    This is the form the templates read: a Galaxy dependency is never written
    without the version range that makes it reproducible.
    """
    return requirements_for(collections_for(names))


def validate_options(role_name: str, options: dict[str, Any]) -> dict[str, Any]:
    """Validate and complete the options of a role.

    Unknown keys raise a :class:`SpecValidationError`; missing options are filled
    in with their default value. The returned dictionary is ordered according to
    the role definition, which guarantees a stable serialisation in ``forge.yml``.
    """
    role = get_role(role_name)
    known = {opt.name for opt in role.options}
    unknown = sorted(set(options) - known)
    if unknown:
        allowed = ", ".join(sorted(known)) or "(none)"
        raise SpecValidationError(
            f"Unknown option(s) for role '{role_name}': {', '.join(unknown)}. "
            f"Accepted options: {allowed}."
        )

    resolved: dict[str, Any] = {}
    for opt in role.options:
        value = options.get(opt.name, opt.default)
        resolved[opt.name] = _coerce(f"{role_name}.{opt.name}", opt, value)
    return resolved


def _coerce(label: str, option: RoleOption, value: Any) -> Any:
    """Check that an option value is compatible with its declared type."""
    kind = option.kind
    choices = option.choices

    if kind is OptionKind.BOOL:
        if not isinstance(value, bool):
            raise SpecValidationError(f"Option '{label}' expects a boolean, got: {value!r}.")
        return value

    if kind is OptionKind.INT:
        if isinstance(value, bool) or not isinstance(value, int):
            raise SpecValidationError(f"Option '{label}' expects an integer, got: {value!r}.")
        return value

    if kind is OptionKind.CHOICE:
        if value not in choices:
            raise SpecValidationError(
                f"Option '{label}' expects one of {', '.join(choices)}, got: {value!r}."
            )
        return value

    if kind is OptionKind.LIST:
        if not isinstance(value, list):
            raise SpecValidationError(f"Option '{label}' expects a list, got: {value!r}.")
        item_option = replace(option, kind=option.item_kind, name=option.name)
        return [
            _coerce(f"{label}[{index}]", item_option, item) for index, item in enumerate(value)
        ]

    if kind is OptionKind.RECORDS:
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise SpecValidationError(
                f"Option '{label}' expects a list of dictionaries, got: {value!r}."
            )
        return [_coerce_record(f"{label}[{index}]", option, item) for index, item in enumerate(value)]

    if not isinstance(value, str):
        raise SpecValidationError(f"Option '{label}' expects a string, got: {value!r}.")
    return value


def _coerce_record(label: str, option: RoleOption, record: dict[str, Any]) -> dict[str, Any]:
    """Validate one dictionary of a RECORDS option.

    Unknown keys are refused and missing fields take their default value, exactly
    as for the top-level options.
    """
    known = {field.name for field in option.fields}
    unknown = sorted(set(record) - known)
    if unknown:
        raise SpecValidationError(
            f"Unknown field(s) in '{label}': {', '.join(unknown)}. "
            f"Accepted fields: {', '.join(sorted(known))}."
        )
    return {
        field.name: _coerce(f"{label}.{field.name}", field, record.get(field.name, field.default))
        for field in option.fields
    }
