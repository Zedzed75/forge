"""Assembly of the root model from the plugins' sub-models.

The core only knows about `forge_version` and `service:`; every plugin brings
its own, optional section. An absent section means "domain not generated"
(DESIGN.md §3). The core knows nothing about the content.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ValidationError, create_model

from forge.errors import SpecValidationError
from forge.spec.service import ServiceSpec
from forge.spec.types import ForgeModel

if TYPE_CHECKING:  # pragma: no cover
    from forge.plugins_api.manager import ForgeManager

#: Version of the `forge.yml` format this core can read.
FORGE_VERSION = 1

#: Fields of the root model that belong to no domain.
CORE_FIELDS = frozenset({"forge_version", "service"})


class ForgeSpecBase(ForgeModel):
    """The part of the root model the core knows; plugins add the rest."""

    #: Version of the specification format.
    forge_version: int = FORGE_VERSION

    #: Shared block, visible to every domain.
    service: ServiceSpec

    def domain_names(self) -> tuple[str, ...]:
        """Domains the spec actually asks for, sorted."""
        return tuple(
            sorted(
                name
                for name in type(self).model_fields
                if name not in CORE_FIELDS and getattr(self, name) is not None
            )
        )

    def section(self, domain: str) -> Any:
        """Sub-model of the domain, or None if the spec does not ask for it."""
        if domain in CORE_FIELDS or domain not in type(self).model_fields:
            raise KeyError(domain)
        return getattr(self, domain)


def build_spec_model(manager: ForgeManager) -> type[ForgeSpecBase]:
    """Build `ForgeSpec`: one optional section per registered domain.

    The model is rebuilt on every call: it depends on which plugins are present,
    so it cannot be defined statically.
    """
    fields: dict[str, Any] = {}
    for info in manager.domains():
        model = manager.domain(info.name).spec_model()
        if not (isinstance(model, type) and issubclass(model, BaseModel)):
            raise SpecValidationError(
                f"forge_spec_model() of domain '{info.name}' must return a "
                "pydantic model"
            )
        if info.name in ForgeSpecBase.model_fields:
            # Defence in depth: `ForgeManager.register` already refuses these
            # names. create_model would silently overwrite the inherited field.
            raise SpecValidationError(
                f"domain '{info.name}' carries the name of a root model field; "
                "it would shadow the core of the specification"
            )
        fields[info.name] = (model | None, None)
    return create_model("ForgeSpec", __base__=ForgeSpecBase, **fields)


def _format_errors(exc: ValidationError) -> str:
    lines = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"]) or "<root>"
        lines.append(f"  - {location}: {error['msg']}")
    return "\n".join(lines)


def validate_spec(data: dict[str, Any], manager: ForgeManager) -> ForgeSpecBase:
    """Validate `data` against the assembled model and return the instance."""
    model = build_spec_model(manager)
    version = data.get("forge_version", FORGE_VERSION)
    if version != FORGE_VERSION:
        raise SpecValidationError(
            f"unsupported forge_version {version!r}: this forge reads version "
            f"{FORGE_VERSION}"
        )
    unknown = sorted(set(data) - set(model.model_fields))
    if unknown:
        known = ", ".join(sorted(model.model_fields))
        raise SpecValidationError(
            f"unknown section(s) in forge.yml: {', '.join(unknown)}\n"
            f"  recognised sections: {known}\n"
            "  a domain absent from that list has no registered plugin."
        )
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise SpecValidationError(
            f"invalid specification ({exc.error_count()} error(s)):\n"
            f"{_format_errors(exc)}"
        ) from exc


def resolve_domains(
    spec: ForgeSpecBase, manager: ForgeManager, only: list[str] | None = None
) -> list[str]:
    """Domains to process: those of the spec, filtered by `--only`.

    Explicit error if `--only` names a domain that is unknown or absent from the
    spec.
    """
    present = list(spec.domain_names())
    if only is None:
        return present
    unknown = [name for name in only if name not in manager.domain_names()]
    if unknown:
        known = ", ".join(manager.domain_names()) or "none"
        raise SpecValidationError(
            f"unknown domain(s): {', '.join(unknown)} (registered: {known})"
        )
    missing = [name for name in only if name not in present]
    if missing:
        raise SpecValidationError(
            f"domain(s) absent from the specification: {', '.join(missing)}\n"
            f"  sections present: {', '.join(present) or 'none'}"
        )
    return [name for name in present if name in only]
