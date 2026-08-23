"""Lecture et écriture de la spécification ``forge.yml``.

La sérialisation est volontairement déterministe : ordre des clés figé par le
modèle (jamais alphabétique), pas de style de flux, fins de ligne LF, encodage
UTF-8. Sauvegarder puis recharger une spec doit redonner un objet identique.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ansible_forge.errors import SpecFileError
from ansible_forge.models.spec import ProjectSpec

#: En-tête écrit en tête de chaque ``forge.yml`` généré.
SPEC_HEADER = """\
---
# ---------------------------------------------------------------------------
# forge.yml - Spécification du projet Ansible
# ---------------------------------------------------------------------------
# Ce fichier décrit entièrement le projet à générer. Il est rejouable :
#   ansible-forge generate --spec forge.yml
# produit exactement la même arborescence, octet pour octet.
#
# Éditez-le à la main puis relancez la génération ; ne modifiez pas
# 'spec_version' manuellement.
# ---------------------------------------------------------------------------
"""


class _ForgeDumper(yaml.SafeDumper):
    """Dumper YAML avec indentation des listes, plus lisible pour un humain."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> Any:
        return super().increase_indent(flow, False)


def spec_to_dict(spec: ProjectSpec) -> dict[str, Any]:
    """Convertit la spec en structures Python simples, prêtes pour YAML."""
    return spec.model_dump(mode="json")


def dump_spec(spec: ProjectSpec, *, header: bool = True) -> str:
    """Sérialise la spec en texte YAML déterministe."""
    body = yaml.dump(
        spec_to_dict(spec),
        Dumper=_ForgeDumper,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=100,
    )
    return (SPEC_HEADER + body) if header else body


def save_spec(spec: ProjectSpec, path: Path, *, header: bool = True) -> Path:
    """Écrit la spec dans ``path`` (UTF-8, fins de ligne LF) et retourne le chemin."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_spec(spec, header=header), encoding="utf-8", newline="\n")
    return path


def parse_spec(text: str, *, source: str = "<chaine>") -> ProjectSpec:
    """Construit une :class:`ProjectSpec` à partir d'un texte YAML."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SpecFileError(f"YAML invalide dans {source} : {exc}") from None

    if data is None:
        raise SpecFileError(f"La specification {source} est vide.")
    if not isinstance(data, dict):
        raise SpecFileError(
            f"La specification {source} doit etre un dictionnaire YAML, "
            f"trouve : {type(data).__name__}."
        )

    try:
        return ProjectSpec.model_validate(data)
    except ValidationError as exc:
        raise SpecFileError(f"Specification invalide dans {source} :\n{_format(exc)}") from None


def load_spec(path: Path) -> ProjectSpec:
    """Charge et valide la spec située à ``path``."""
    path = Path(path)
    if not path.exists():
        raise SpecFileError(f"Fichier de specification introuvable : {path}")
    if not path.is_file():
        raise SpecFileError(f"Le chemin de specification n'est pas un fichier : {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SpecFileError(f"Lecture impossible de {path} : {exc}") from None
    return parse_spec(text, source=str(path))


def _format(exc: ValidationError) -> str:
    """Met en forme les erreurs pydantic en une liste lisible."""
    lines = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"]) or "(racine)"
        message = error["msg"].removeprefix("Value error, ")
        lines.append(f"  - {location} : {message}")
    return "\n".join(lines)
