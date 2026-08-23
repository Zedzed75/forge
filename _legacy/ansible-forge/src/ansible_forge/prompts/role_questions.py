"""Saisie des options des rôles sélectionnés.

Chaque option du catalogue porte son type ; ce module se contente de traduire
ce type en question. Ajouter une option à un rôle suffit donc à la faire
apparaître dans le questionnaire, sans toucher à ce fichier.
"""

from __future__ import annotations

from typing import Any

from ansible_forge.catalog.definition import OptionKind, RoleDefinition, RoleOption
from ansible_forge.prompts.prompter import Prompter
from ansible_forge.validation import MAX_PORT, MIN_PORT


def ask_role_options(prompter: Prompter, role: RoleDefinition) -> dict[str, Any]:
    """Pose toutes les questions d'un rôle et retourne les valeurs saisies."""
    prompter.note(f"\nRôle « {role.name} » — {role.summary}")
    return {option.name: ask_option(prompter, option) for option in role.options}


def ask_option(prompter: Prompter, option: RoleOption) -> Any:
    """Pose la question correspondant à une option et retourne sa valeur."""
    if option.kind is OptionKind.BOOL:
        return prompter.confirm(option.question, default=bool(option.default))

    if option.kind is OptionKind.INT:
        return _ask_int(prompter, option)

    if option.kind is OptionKind.CHOICE:
        choices = [(value, value) for value in option.choices]
        return prompter.select(option.question, choices, default=str(option.default))

    if option.kind is OptionKind.LIST:
        return _ask_list(prompter, option)

    if option.kind is OptionKind.RECORDS:
        return _ask_records(prompter, option)

    return prompter.text(option.question, default=str(option.default))


def _ask_int(prompter: Prompter, option: RoleOption) -> int:
    """Demande un entier, en appliquant les bornes des ports le cas échéant."""
    is_port = "port" in option.name

    def validate(value: str) -> str | None:
        try:
            parsed = int(value.strip())
        except ValueError:
            return f"Un entier est attendu, reçu : « {value} »."
        if is_port and not MIN_PORT <= parsed <= MAX_PORT:
            return f"Le port doit être compris entre {MIN_PORT} et {MAX_PORT}."
        if not is_port and parsed < 0:
            return "Un entier positif est attendu."
        return None

    return int(prompter.text(option.question, default=str(option.default), validate=validate))


def _ask_list(prompter: Prompter, option: RoleOption) -> list[Any]:
    """Demande une liste saisie sous forme de valeurs séparées par des virgules."""
    default = ", ".join(str(item) for item in option.default)

    def validate(value: str) -> str | None:
        if option.item_kind is not OptionKind.INT:
            return None
        for item in _split(value):
            if not item.lstrip("-").isdigit():
                return f"« {item} » n'est pas un entier."
        return None

    raw = prompter.text(f"{option.question} [{option.allowed}]", default=default, validate=validate)
    items = _split(raw)
    if option.item_kind is OptionKind.INT:
        return [int(item) for item in items]
    return items


def _ask_records(prompter: Prompter, option: RoleOption) -> list[dict[str, Any]]:
    """Demande une liste de dictionnaires, un enregistrement à la fois."""
    records: list[dict[str, Any]] = []
    while prompter.confirm(
        f"{option.question} — ajouter une entrée ?" if records else f"{option.question} ?",
        default=not records,
    ):
        record = {field.name: ask_option(prompter, field) for field in option.fields}
        records.append(record)
    return records


def _split(value: str) -> list[str]:
    """Découpe une saisie « a, b , c » en liste, en ignorant les vides."""
    return [item.strip() for item in value.split(",") if item.strip()]
