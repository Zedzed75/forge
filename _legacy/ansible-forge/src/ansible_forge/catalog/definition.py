"""Structures décrivant un rôle du catalogue.

Un rôle du catalogue est **de la donnée**, pas du code : chaque `RoleDefinition`
porte à la fois les questions posées à l'utilisateur, les valeurs par défaut et
les textes de commentaire réutilisés dans les fichiers Ansible générés. Les
templates Jinja2 restent ainsi de simples formateurs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OptionKind(str, Enum):
    """Type d'une option de rôle, utilisé par la CLI interactive et la validation."""

    TEXT = "text"
    BOOL = "bool"
    INT = "int"
    CHOICE = "choice"
    LIST = "list"
    RECORDS = "records"


@dataclass(frozen=True)
class RoleOption:
    """Une variable configurable d'un rôle.

    Attributs :
        name: nom de la variable générée (préfixée par le nom du rôle).
        question: libellé affiché en mode interactif.
        description: rôle de la variable, repris en commentaire dans
            ``defaults/main.yml``.
        allowed: description des valeurs admises, reprise en commentaire.
        default: valeur par défaut, doit être déterministe.
        kind: type d'option, pilote le widget de saisie et la validation.
        choices: valeurs possibles pour ``kind == CHOICE``.
        item_kind: type des éléments pour ``kind == LIST`` ; évite de deviner
            le type à partir d'une valeur par défaut parfois vide.
        fields: sous-options pour ``kind == RECORDS`` (liste de dictionnaires).
    """

    name: str
    question: str
    description: str
    allowed: str
    default: Any
    kind: OptionKind = OptionKind.TEXT
    choices: tuple[str, ...] = ()
    item_kind: OptionKind = OptionKind.TEXT
    fields: tuple["RoleOption", ...] = ()


@dataclass(frozen=True)
class RoleDefinition:
    """Un rôle proposé dans le catalogue.

    Attributs :
        name: identifiant du rôle, aussi nom du répertoire ``roles/<name>``.
        summary: description courte affichée dans le questionnaire.
        options: options configurables du rôle.
        collections: collections Galaxy requises, ajoutées à ``requirements.yml``.
        handlers: noms des handlers exposés, cités dans le README du rôle.
        os_families: familles d'OS supportées (vide = toutes).
    """

    name: str
    summary: str
    options: tuple[RoleOption, ...] = ()
    collections: tuple[str, ...] = ()
    handlers: tuple[str, ...] = ()
    os_families: tuple[str, ...] = ()
    tags: tuple[str, ...] = field(default_factory=tuple)

    def option(self, name: str) -> RoleOption | None:
        """Retourne l'option nommée, ou ``None`` si elle n'existe pas."""
        for opt in self.options:
            if opt.name == name:
                return opt
        return None

    def default_options(self) -> dict[str, Any]:
        """Retourne le dictionnaire des valeurs par défaut de toutes les options."""
        return {opt.name: opt.default for opt in self.options}
