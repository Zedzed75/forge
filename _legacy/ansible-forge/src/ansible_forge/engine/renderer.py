"""Fabrique de l'environnement Jinja2 et rendu des templates.

Tous les réglages sont choisis pour un rendu reproductible :

- ``StrictUndefined`` : une variable oubliée casse la génération au lieu de
  produire silencieusement un fichier incomplet ;
- ``trim_blocks`` / ``lstrip_blocks`` : les balises de contrôle ne laissent ni
  ligne vide ni indentation parasite ;
- ``keep_trailing_newline`` : les fichiers se terminent par un saut de ligne,
  comme l'exige yamllint.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from jinja2 import Environment, PackageLoader, StrictUndefined

from ansible_forge.engine.filters import FILTERS, GLOBALS

#: Répertoire des templates, relatif au package.
TEMPLATE_PACKAGE = "ansible_forge"
TEMPLATE_DIR = "templates"


@lru_cache(maxsize=1)
def get_environment() -> Environment:
    """Retourne l'environnement Jinja2 partagé, configuré pour un rendu déterministe."""
    env = Environment(
        loader=PackageLoader(TEMPLATE_PACKAGE, TEMPLATE_DIR),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        autoescape=False,
    )
    env.filters.update(FILTERS)
    env.globals.update(GLOBALS)
    return env


def render(template_name: str, context: dict[str, Any]) -> str:
    """Rend un template et normalise sa sortie.

    La normalisation supprime les espaces de fin de ligne, les lignes vides de
    début (que produisent les blocs ``raw``) et force une unique ligne vide
    finale : trois règles imposées par yamllint et respectées par l'ensemble
    des fichiers générés.
    """
    raw = get_environment().get_template(template_name).render(**context)
    lines = [line.rstrip() for line in raw.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n"


def list_templates() -> list[str]:
    """Retourne la liste triée des templates disponibles (diagnostic et tests)."""
    return sorted(get_environment().list_templates())
