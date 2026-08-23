"""Filtres Jinja2 utilisés par les templates.

Ces filtres concentrent toute la mise en forme YAML et les commentaires : les
templates restent ainsi lisibles et le rendu est identique d'une exécution à
l'autre (aucun tri implicite, aucune dépendance à l'ordre d'un dictionnaire
Python).
"""

from __future__ import annotations

import textwrap
from typing import Any

import yaml

#: Largeur maximale d'une ligne de commentaire générée.
COMMENT_WIDTH = 88

#: Largeur des filets de séparation des en-têtes.
RULE_WIDTH = 75


class _BlockDumper(yaml.SafeDumper):
    """Dumper YAML indentant les listes sous leur clé parente."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> Any:
        return super().increase_indent(flow, False)


def to_yaml_scalar(value: Any) -> str:
    """Rend une valeur scalaire en YAML, avec les guillemets nécessaires.

    Passe par un dump d'une paire clé/valeur : c'est PyYAML qui décide de la
    citation, ce qui évite toute divergence avec le parseur Ansible.
    """
    dumped = yaml.dump(
        {"_": value},
        Dumper=_BlockDumper,
        default_flow_style=False,
        allow_unicode=True,
        width=10**6,
        sort_keys=False,
    )
    return dumped.rstrip("\n").removeprefix("_: ")


def to_yaml_assign(value: Any, indent: int = 0) -> str:
    """Rend la partie droite d'une affectation YAML, préfixe d'espace inclus.

    Les scalaires restent sur la ligne de la clé ; les listes et dictionnaires
    passent en bloc indenté de ``indent`` espaces. À utiliser ainsi dans un
    template : ``{{ name }}:{{ value | yaml_assign(2) }}``.
    """
    if isinstance(value, (list, tuple)) and not value:
        return " []"
    if isinstance(value, dict) and not value:
        return " {}"

    if not isinstance(value, (list, tuple, dict)):
        scalar = to_yaml_scalar(value)
        if "\n" not in scalar:
            return f" {scalar}"

    dumped = yaml.dump(
        list(value) if isinstance(value, tuple) else value,
        Dumper=_BlockDumper,
        default_flow_style=False,
        allow_unicode=True,
        width=10**6,
        sort_keys=False,
    ).rstrip("\n")
    pad = " " * indent
    return "\n" + "\n".join(f"{pad}{line}" if line else "" for line in dumped.splitlines())


def comment(text: str, indent: int = 0, width: int = COMMENT_WIDTH) -> str:
    """Transforme un texte en bloc de commentaires ``#``, replié à ``width``.

    Les lignes vides du texte source deviennent des lignes ``#`` isolées, ce qui
    permet d'écrire des paragraphes dans les descriptions du catalogue.
    """
    pad = " " * indent
    available = max(width - indent - 2, 20)
    lines: list[str] = []
    for paragraph in text.split("\n"):
        stripped = paragraph.strip()
        if not stripped:
            lines.append(f"{pad}#")
            continue
        # L'indentation de la ligne source est conservée : elle porte du sens
        # dans les exemples de commandes cités en en-tête de fichier.
        lead = paragraph[: len(paragraph) - len(paragraph.lstrip())]
        chunks = textwrap.wrap(
            stripped, width=available, initial_indent=lead, subsequent_indent=lead
        )
        lines.extend(f"{pad}# {chunk}" for chunk in chunks)
    return "\n".join(lines)


def lower_first(text: str) -> str:
    """Met la première lettre en minuscule, pour enchaîner après un deux-points.

    N'affecte pas les textes commençant par un sigle ou un nom propre en
    majuscules (``UTF8``, ``Ansible``), reconnus à leur deuxième lettre.
    """
    if len(text) >= 2 and text[1].isupper():
        return text
    return text[:1].lower() + text[1:]


def rule(width: int = RULE_WIDTH) -> str:
    """Retourne un filet de séparation en commentaire."""
    return "# " + "-" * width


def jinja_expr(expression: str) -> str:
    """Rend une expression Jinja destinée au projet généré.

    Les templates du générateur et les fichiers générés utilisent la même
    syntaxe ``{{ ... }}`` ; cette fonction évite d'avoir à échapper chaque
    expression Ansible dans un bloc ``raw``.
    """
    return "{{ " + expression + " }}"


def jinja_string(expression: str) -> str:
    """Comme :func:`jinja_expr`, mais entourée de guillemets.

    Ansible impose de citer toute valeur YAML commençant par ``{{``.
    """
    return '"' + jinja_expr(expression) + '"'



#: Filtres exposés aux templates, sous le nom utilisé dans les ``| filtre``.
FILTERS = {
    "yaml_scalar": to_yaml_scalar,
    "yaml_assign": to_yaml_assign,
    "comment": comment,
    "lower_first": lower_first,
}

#: Fonctions globales exposées aux templates.
GLOBALS = {
    "rule": rule,
    "j": jinja_expr,
    "jstr": jinja_string,
}
