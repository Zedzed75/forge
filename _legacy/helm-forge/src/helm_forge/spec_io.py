"""Lecture et écriture de ``forge.yml``, le fichier de spécification rejouable.

Le format retenu est un vidage complet du modèle : toutes les clés sont
écrites, y compris celles laissées à leur valeur par défaut. Le fichier est
ainsi auto-documenté et directement modifiable à la main, et l'aller-retour
spécification vers YAML vers spécification est fidèle par construction.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .constants import SPEC_SCHEMA_VERSION
from .errors import SpecError, SpecNotFoundError
from .models import ProjectSpec

#: En-tête déposé en tête de chaque forge.yml généré.
SPEC_HEADER = """\
# -----------------------------------------------------------------------------
# forge.yml — spécification du projet, générée par helm-forge
# -----------------------------------------------------------------------------
# Ce fichier décrit intégralement le projet Kubernetes/Helm à générer.
# Il est rejouable : `helm-forge generate --spec forge.yml` reproduit le projet
# à l'identique, octet pour octet, sans reposer aucune question.
#
# Toutes les clés sont écrites, y compris celles laissées à leur valeur par
# défaut, afin que le fichier serve aussi de documentation des réglages
# disponibles. Modifiez-le puis relancez la génération.
# -----------------------------------------------------------------------------
"""


def dumps(spec: ProjectSpec) -> str:
    """Sérialise une spécification en YAML, en-tête compris.

    L'ordre des clés suit l'ordre de déclaration des champs du modèle, jamais
    l'ordre alphabétique : c'est ce qui rend le fichier lisible et le rend
    identique d'une exécution à l'autre.
    """
    payload: dict[str, Any] = spec.model_dump(mode="json")
    body = yaml.safe_dump(
        payload,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=100,
        indent=2,
    )
    return SPEC_HEADER + body


def loads(text: str) -> ProjectSpec:
    """Charge une spécification depuis du YAML.

    Lève ``SpecError`` si le document est illisible, vide, ou d'une version de
    schéma que cette version de helm-forge ne sait pas interpréter.
    """
    try:
        payload = yaml.safe_load(text)
    except yaml.YAMLError as exc:  # YAML syntaxiquement invalide
        raise SpecError(f"forge.yml illisible : {exc}") from exc

    if payload is None:
        raise SpecError("forge.yml est vide")
    if not isinstance(payload, dict):
        raise SpecError("forge.yml doit contenir un objet YAML à sa racine")

    version = payload.get("schema_version", SPEC_SCHEMA_VERSION)
    if version != SPEC_SCHEMA_VERSION:
        raise SpecError(
            f"schema_version {version!r} non supportée par cette version de "
            f"helm-forge (attendu : {SPEC_SCHEMA_VERSION})"
        )

    try:
        return ProjectSpec.model_validate(payload)
    except Exception as exc:  # erreurs de validation pydantic
        raise SpecError(f"forge.yml invalide : {exc}") from exc


def load_spec(path: Path) -> ProjectSpec:
    """Charge une spécification depuis un fichier."""
    if not path.is_file():
        raise SpecNotFoundError(f"fichier de spécification introuvable : {path}")
    return loads(path.read_text(encoding="utf-8"))


def save_spec(spec: ProjectSpec, path: Path) -> None:
    """Écrit une spécification sur disque.

    Les fins de ligne sont forcées en LF et l'encodage en UTF-8 sans BOM, quelle
    que soit la plateforme, afin que le résultat soit identique partout.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(spec), encoding="utf-8", newline="\n")
