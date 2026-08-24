"""Saisie des options des roles selectionnes.

Portage de `ansible_forge.prompts.role_questions` (MIGRATION.md §3), inchange
dans son principe : chaque option du catalogue porte son type, ce module se
contente de traduire ce type en question. Ajouter une option a un role suffit
donc a la faire apparaitre dans l'entretien, sans toucher a ce fichier.

Le module est separe de `interview.py` pour deux raisons : il ne parle que du
catalogue (pas d'inventaire, pas de connexion), et la limite de 600 lignes par
fichier du depot laisse ainsi de la place aux deux questionnaires.
"""

from __future__ import annotations

from typing import Any

from forge.interview.prompter import Prompter
from forge.plugins.ansible.catalog.definition import OptionKind, RoleDefinition, RoleOption
from forge.plugins.ansible.names import MAX_PORT, MIN_PORT


def ask_role_options(prompter: Prompter, role: RoleDefinition) -> dict[str, Any]:
    """Pose toutes les questions d'un role et retourne les valeurs saisies."""
    prompter.note(f"\nRôle « {role.name} » — {role.summary}")
    return {option.name: ask_option(prompter, option) for option in role.options}


def ask_option(prompter: Prompter, option: RoleOption) -> Any:
    """Pose la question correspondant a une option et retourne sa valeur."""
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
    """Demande un entier, en appliquant les bornes des ports le cas echeant."""
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
    """Demande une liste saisie sous forme de valeurs separees par des virgules."""
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
    """Demande une liste de dictionnaires, un enregistrement a la fois."""
    records: list[dict[str, Any]] = []
    while prompter.confirm(
        f"{option.question} — ajouter une entrée ?" if records else f"{option.question} ?",
        default=not records,
    ):
        record = {field.name: ask_option(prompter, field) for field in option.fields}
        records.append(record)
    return records


def _split(value: str) -> list[str]:
    """Decoupe une saisie « a, b , c » en liste, en ignorant les vides."""
    return [item.strip() for item in value.split(",") if item.strip()]
