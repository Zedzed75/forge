"""Filtres Jinja2 utilisés par les gabarits de génération.

Ces filtres ne servent qu'au rendu : ils ne portent aucune décision métier.
Leur seule contrainte forte est le déterminisme, deux appels identiques devant
produire exactement la même chaîne.
"""

from __future__ import annotations

import textwrap
from typing import Any

import yaml


def to_yaml(value: Any, indent: int = 0) -> str:
    """Rend une valeur Python en YAML, prête à être insérée dans un gabarit.

    Les scalaires sont rendus sur une ligne (``true``, ``null``, ``"1.36"``),
    les listes et dictionnaires en blocs indentés. L'ordre des clés suit
    l'ordre d'insertion, jamais l'ordre alphabétique, afin que le rendu reste
    identique d'une exécution à l'autre.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return yaml_scalar(value)
    if not value:
        # Collection vide : la forme en ligne est plus lisible qu'un bloc vide.
        return "[]" if isinstance(value, (list, tuple)) else "{}"

    text = yaml.safe_dump(
        _plain(value),
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=100,
    ).rstrip("\n")
    if indent:
        text = textwrap.indent(text, " " * indent)
    return text


def yaml_value(value: Any, indent: int = 0) -> str:
    """Rend une valeur destinée à figurer à droite d'une clé YAML.

    Une collection non vide ne peut pas rester sur la ligne de sa clé : YAML
    refuse ``drop: - ALL``. Le filtre bascule donc en bloc indenté, tandis que
    scalaires et collections vides restent en ligne.

    Le filtre produit lui-même le séparateur, espace ou saut de ligne. Le
    gabarit colle donc la balise au deux-points, sans espace :

        drop:[[ liste | yaml_value(8) ]]

    Ce détail évite qu'un passage en bloc laisse une espace en fin de ligne
    derrière le deux-points.
    """
    if isinstance(value, (list, tuple, dict)) and value:
        return "\n" + to_yaml(value, indent=indent)
    return " " + to_yaml(value)


def yaml_scalar(value: str) -> str:
    """Rend une chaîne en scalaire YAML, en la protégeant si nécessaire.

    ``api`` reste nu, tandis que ``1.36``, ``true``, ``""`` ou ``on`` sont
    protégés par des quotes, faute de quoi YAML les relirait comme un nombre
    ou un booléen.
    """
    dumped = yaml.safe_dump(
        [value], default_flow_style=True, allow_unicode=True, width=10_000
    ).strip()
    # safe_dump produit "[valeur]" : on retire les crochets englobants.
    return dumped[1:-1]


def comment(text: str, width: int = 76, prefix: str = "# ") -> str:
    """Reformate un texte en bloc de commentaire, une ligne par phrase coupée.

    Utilisé pour que les commentaires générés restent dans une largeur de page
    raisonnable sans avoir à les couper à la main dans les gabarits.
    """
    lines: list[str] = []
    for paragraph in text.strip().splitlines():
        paragraph = paragraph.strip()
        if not paragraph:
            lines.append(prefix.rstrip())
            continue
        lines.extend(
            textwrap.wrap(paragraph, width=width - len(prefix)) or [""]
        )
    return "\n".join(f"{prefix}{line}".rstrip() for line in lines)


def indent_block(text: str, spaces: int, first: bool = False) -> str:
    """Indente un bloc de texte déjà rendu.

    ``first`` à faux laisse la première ligne intacte, ce qui correspond au cas
    courant où le gabarit a déjà écrit l'indentation de départ.
    """
    if not text:
        return text
    indented = textwrap.indent(text, " " * spaces)
    if not first:
        indented = indented[spaces:]
    return indented


def camel(value: str) -> str:
    """Convertit ``liveness_path`` en ``livenessPath``.

    Les clés de values suivent la convention camelCase de l'écosystème Helm,
    alors que le modèle Python suit la convention snake_case de Python.
    """
    head, *rest = value.split("_")
    return head + "".join(part.capitalize() for part in rest)


def _plain(value: Any) -> Any:
    """Convertit récursivement les objets non natifs en types YAML sûrs."""
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float, str)):
        return value
    return str(value)


#: Table des filtres injectés dans l'environnement Jinja2.
FILTERS = {
    "to_yaml": to_yaml,
    "yaml_value": yaml_value,
    "yaml_scalar": yaml_scalar,
    "comment": comment,
    "indent_block": indent_block,
    "camel": camel,
}
