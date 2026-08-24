"""Assemblage du modele racine a partir des sous-modeles de plugins.

Le coeur ne connait que `forge_version` et `service:` ; chaque plugin apporte sa
section, optionnelle. Une section absente signifie « domaine non genere »
(DESIGN.md §3). Aucune connaissance du contenu cote coeur.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ValidationError, create_model

from forge.errors import SpecValidationError
from forge.spec.service import ServiceSpec
from forge.spec.types import ForgeModel

if TYPE_CHECKING:  # pragma: no cover
    from forge.plugins_api.manager import ForgeManager

#: Version de format de `forge.yml` que ce coeur sait lire.
FORGE_VERSION = 1

#: Champs du modele racine qui n'appartiennent a aucun domaine.
CORE_FIELDS = frozenset({"forge_version", "service"})


class ForgeSpecBase(ForgeModel):
    """Partie du modele racine connue du coeur ; les plugins ajoutent le reste."""

    #: Version du format de specification.
    forge_version: int = FORGE_VERSION

    #: Bloc partage, visible de tous les domaines.
    service: ServiceSpec

    def domain_names(self) -> tuple[str, ...]:
        """Domaines effectivement demandes par la spec, tries."""
        return tuple(
            sorted(
                name
                for name in type(self).model_fields
                if name not in CORE_FIELDS and getattr(self, name) is not None
            )
        )

    def section(self, domain: str) -> Any:
        """Sous-modele du domaine, ou None si la spec ne le demande pas."""
        if domain in CORE_FIELDS or domain not in type(self).model_fields:
            raise KeyError(domain)
        return getattr(self, domain)


def build_spec_model(manager: ForgeManager) -> type[ForgeSpecBase]:
    """Construit `ForgeSpec` : une section optionnelle par domaine enregistre.

    Le modele est reconstruit a chaque appel : il depend des plugins presents,
    donc il ne peut pas etre defini statiquement.
    """
    fields: dict[str, Any] = {}
    for info in manager.domains():
        model = manager.domain(info.name).spec_model()
        if not (isinstance(model, type) and issubclass(model, BaseModel)):
            raise SpecValidationError(
                f"forge_spec_model() du domaine '{info.name}' doit retourner un "
                "modele pydantic"
            )
        if info.name in ForgeSpecBase.model_fields:
            # Defense en profondeur : `ForgeManager.register` refuse deja ces noms.
            # create_model ecraserait silencieusement le champ herite.
            raise SpecValidationError(
                f"le domaine '{info.name}' porte le nom d'un champ du modele racine ; "
                "il masquerait le coeur de la specification"
            )
        fields[info.name] = (model | None, None)
    return create_model("ForgeSpec", __base__=ForgeSpecBase, **fields)


def _format_errors(exc: ValidationError) -> str:
    lines = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"]) or "<racine>"
        lines.append(f"  - {location} : {error['msg']}")
    return "\n".join(lines)


def validate_spec(data: dict[str, Any], manager: ForgeManager) -> ForgeSpecBase:
    """Valide `data` contre le modele assemble et retourne l'instance."""
    model = build_spec_model(manager)
    version = data.get("forge_version", FORGE_VERSION)
    if version != FORGE_VERSION:
        raise SpecValidationError(
            f"forge_version {version!r} non supportee : ce forge lit la version "
            f"{FORGE_VERSION}"
        )
    unknown = sorted(set(data) - set(model.model_fields))
    if unknown:
        known = ", ".join(sorted(model.model_fields))
        raise SpecValidationError(
            f"section(s) inconnue(s) dans forge.yml : {', '.join(unknown)}\n"
            f"  sections reconnues : {known}\n"
            "  un domaine absent de cette liste n'a pas de plugin enregistre."
        )
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise SpecValidationError(
            f"specification invalide ({exc.error_count()} erreur(s)) :\n"
            f"{_format_errors(exc)}"
        ) from exc


def resolve_domains(
    spec: ForgeSpecBase, manager: ForgeManager, only: list[str] | None = None
) -> list[str]:
    """Domaines a traiter : ceux de la spec, filtres par `--only`.

    Erreur explicite si `--only` cite un domaine inconnu ou absent de la spec.
    """
    present = list(spec.domain_names())
    if only is None:
        return present
    unknown = [name for name in only if name not in manager.domain_names()]
    if unknown:
        known = ", ".join(manager.domain_names()) or "aucun"
        raise SpecValidationError(
            f"domaine(s) inconnu(s) : {', '.join(unknown)} (enregistres : {known})"
        )
    missing = [name for name in only if name not in present]
    if missing:
        raise SpecValidationError(
            f"domaine(s) absent(s) de la specification : {', '.join(missing)}\n"
            f"  sections presentes : {', '.join(present) or 'aucune'}"
        )
    return [name for name in present if name in only]
