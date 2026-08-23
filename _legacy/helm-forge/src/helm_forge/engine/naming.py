"""Fabrique des identifiants utilisés dans les charts générés.

Deux pièges de l'écosystème Helm sont traités ici une fois pour toutes :

- un nom de composant peut contenir un tiret (``mon-api``), or la notation
  pointée de Go refuse les tirets : ``.Values.mon-api`` est une erreur de
  syntaxe. Il faut alors écrire ``(index .Values "mon-api")`` ;
- les noms de helpers Helm sont de simples chaînes, les tirets y sont donc
  acceptés sans précaution particulière.
"""

from __future__ import annotations

import re

#: Identifiant acceptable dans la notation pointée des gabarits Go/Helm.
_GO_FIELD = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def values_ref(name: str, prefix: str = ".Values") -> str:
    """Renvoie l'expression Helm d'accès à une clé de values.

    ``values_ref("api")`` donne ``.Values.api`` tandis que
    ``values_ref("mon-api")`` donne ``(index .Values "mon-api")``.
    """
    if _GO_FIELD.match(name):
        return f"{prefix}.{name}"
    return f'(index {prefix} "{name}")'


def helper_name(chart: str, *parts: str) -> str:
    """Compose un nom de helper Helm : ``helper_name("shop", "api", "labels")``
    donne ``shop.api.labels``."""
    return ".".join([chart, *parts])
