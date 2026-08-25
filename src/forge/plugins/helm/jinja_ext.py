"""Filtres et globals Jinja2 propres au domaine Helm.

Charges par `forge.jinja_ext.ForgeExtension` (MIGRATION.md §5) : un plugin
ajoute ses fabriques d'identifiants sans que le `copier.yml` racine soit touche.

Ce module ne contient que du **nommage**. Tout ce qui releve de la mise en forme
YAML ou des commentaires vit dans le coeur (`forge.jinja_ext`), ou les deux
implementations legacy ont ete fusionnees.

Le point critique est :func:`values_ref` (MIGRATION.md §4, portage de
`engine/naming.py`) : la notation pointee de Go refuse le tiret, donc
`.Values.mon-api` est une **erreur de syntaxe Helm**. Sans ce global, un
composant nomme avec un tiret produit un chart qui ne compile pas.

Les contextes de composant exposes par `derive.py` portent deja `values_ref` et
`helper` pre-calcules : dans le contenu d'un gabarit on ecrit donc plutot
`[[ c.values_ref ]]`. Ces globals restent necessaires pour les expressions
construites a la volee (une cle de values qui n'est pas un composant, par
exemple) et pour rester fidele au contrat legacy.
"""

from __future__ import annotations

import re
from typing import Any, Final

#: Identifiant acceptable dans la notation pointee des gabarits Go/Helm.
#: Portage litteral de `helm_forge.engine.naming._GO_FIELD`.
_GO_FIELD: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def values_ref(name: str, prefix: str = ".Values") -> str:
    """Expression Helm d'acces a une cle de values.

    `values_ref("api")` rend `.Values.api` ; `values_ref("mon-api")` rend
    `(index .Values "mon-api")`, seule forme acceptee par Go pour une cle
    contenant un tiret.
    """
    if _GO_FIELD.match(name):
        return f"{prefix}.{name}"
    return f'(index {prefix} "{name}")'


def helper_name(chart: str, *parts: str) -> str:
    """Nom d'un helper Helm : `helper_name("shop", "api", "labels")` rend
    `shop.api.labels`."""
    return ".".join([chart, *parts])


def resource_filename(resource: str, component: Any) -> str:
    """Nom de fichier d'une ressource, toujours suffixe par le composant.

    Portage de `helm_forge.engine.planner.resource_filename`. Le suffixe est
    systematique, y compris pour un chart mono-composant : la regle reste ainsi
    identique quel que soit le projet, et ajouter un second composant ne renomme
    aucun fichier existant.

    `component` accepte le contexte de composant produit par `derive.py` (un
    dict portant `name`) ou directement un nom, ce qui evite au gabarit de
    connaitre la forme exacte du contexte.
    """
    name = component["name"] if isinstance(component, dict) else str(component)
    return f"{resource}-{name}.yaml"


def camel(value: str) -> str:
    """Convertit `liveness_path` en `livenessPath`.

    Portage de `helm_forge.engine.filters.camel` : les cles de values suivent la
    convention camelCase de l'ecosysteme Helm, alors que le modele Python suit
    la convention snake_case.
    """
    head, *rest = value.split("_")
    return head + "".join(part.capitalize() for part in rest)


#: Filtres ajoutes par le domaine Helm (`| camel`).
FILTERS = {
    "camel": camel,
}

#: Fonctions globales ajoutees par le domaine Helm.
GLOBALS = {
    "values_ref": values_ref,
    "helper_name": helper_name,
    "resource_filename": resource_filename,
}
