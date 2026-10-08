"""Structures describing a role of the catalogue.

A catalogue role is **data**, not code: each `RoleDefinition` carries at once the
questions asked of the user, the default values and the comment texts reused in
the generated Ansible files. The Jinja2 templates thus stay plain formatters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OptionKind(str, Enum):
    """Type of a role option, used by the interactive CLI and by validation."""

    TEXT = "text"
    BOOL = "bool"
    INT = "int"
    CHOICE = "choice"
    LIST = "list"
    RECORDS = "records"


@dataclass(frozen=True)
class RoleOption:
    """A configurable variable of a role.

    Attributes:
        name: name of the generated variable (prefixed with the role name).
        question: label displayed in interactive mode.
        description: what the variable is for, echoed as a comment in
            ``defaults/main.yml``.
        allowed: description of the accepted values, echoed as a comment.
        default: default value, which must be deterministic.
        kind: option type; drives the input widget and the validation.
        choices: possible values for ``kind == CHOICE``.
        item_kind: type of the items for ``kind == LIST``; avoids guessing the
            type from a default value that is sometimes empty.
        fields: sub-options for ``kind == RECORDS`` (a list of dictionaries).
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
    """A role offered in the catalogue.

    Attributes:
        name: identifier of the role, also the name of the ``roles/<name>``
            directory.
        summary: short description displayed in the questionnaire.
        options: configurable options of the role.
        collections: required Galaxy collections, added to ``requirements.yml``.
        handlers: names of the exposed handlers, quoted in the role README.
        os_families: supported OS families (empty = all of them).
    """

    name: str
    summary: str
    options: tuple[RoleOption, ...] = ()
    collections: tuple[str, ...] = ()
    handlers: tuple[str, ...] = ()
    os_families: tuple[str, ...] = ()
    tags: tuple[str, ...] = field(default_factory=tuple)

    def option(self, name: str) -> RoleOption | None:
        """Return the named option, or ``None`` when it does not exist."""
        for opt in self.options:
            if opt.name == name:
                return opt
        return None

    def default_options(self) -> dict[str, Any]:
        """Return the dictionary of the default values of every option."""
        return {opt.name: opt.default for opt in self.options}
