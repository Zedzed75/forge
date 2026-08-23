"""Lecture et ecriture de `forge.yml`.

Portage de `ansible_forge.spec_io` (MIGRATION.md §3, doublon §5.2) rendu
domaine-agnostique : la validation appartient a `assembly`, ce module ne fait
que du YAML deterministe — ordre des cles figé par le modele (jamais
alphabetique), pas de style de flux, fins de ligne LF, encodage UTF-8.
Sauvegarder puis recharger une spec doit redonner un objet identique.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from forge.errors import SpecFileError

#: Nom de fichier de specification par defaut.
SPEC_FILENAME = "forge.yml"

_HEADER_TOP = """\
---
# ---------------------------------------------------------------------------
# forge.yml - Specification du service
# ---------------------------------------------------------------------------
# Ce fichier decrit entierement ce qui doit etre genere. Il est rejouable :
#   forge generate --spec forge.yml
# produit exactement la meme arborescence, octet pour octet.
#
# Editez-le a la main puis relancez la generation ; ne modifiez pas
# 'forge_version' manuellement.
"""

_HEADER_BOTTOM = """\
# ---------------------------------------------------------------------------
"""


class _ForgeDumper(yaml.SafeDumper):
    """Dumper YAML avec indentation des listes, plus lisible pour un humain."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> Any:
        return super().increase_indent(flow, False)


def build_header(sections: list[str]) -> str:
    """En-tete commente, enrichi de la liste des domaines presents."""
    lines = [_HEADER_TOP]
    if sections:
        lines.append("#\n# Domaines generes par cette specification :\n")
        for name in sections:
            lines.append(f"#   - {name}\n")
    lines.append(_HEADER_BOTTOM)
    return "".join(lines)


def dump_yaml(data: dict[str, Any]) -> str:
    """Serialise `data` en YAML deterministe, sans en-tete."""
    return yaml.dump(
        data,
        Dumper=_ForgeDumper,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=100,
    )


def dump_spec(data: dict[str, Any], *, sections: list[str] | None = None) -> str:
    """Serialise une spec complete, en-tete comprise."""
    header = build_header(sections if sections is not None else [])
    return header + dump_yaml(data)


def save_spec(
    data: dict[str, Any], path: Path, *, sections: list[str] | None = None
) -> Path:
    """Ecrit la spec dans `path` (UTF-8, fins de ligne LF) et retourne le chemin."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_spec(data, sections=sections), encoding="utf-8", newline="\n")
    return path


def parse_spec(text: str, *, source: str = "<chaine>") -> dict[str, Any]:
    """Analyse un texte YAML et retourne le dict brut, sans le valider."""
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
    return data


def load_spec_data(path: Path) -> dict[str, Any]:
    """Charge le dict brut de la spec situee a `path`."""
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
