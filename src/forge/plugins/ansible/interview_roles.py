"""Entry of the options of the selected roles.

Port of `ansible_forge.prompts.role_questions` (MIGRATION.md §3), unchanged in
principle: each catalog option carries its type, and this module merely
translates that type into a question. Adding an option to a role is therefore
enough to make it appear in the interview, without touching this file.

The module is separate from `interview.py` for two reasons: it speaks only of
the catalog (no inventory, no connection), and the repository's 600-line limit
per file thus leaves room for both questionnaires.
"""

from __future__ import annotations

from typing import Any

from forge.interview.prompter import Prompter
from forge.plugins.ansible.catalog.definition import OptionKind, RoleDefinition, RoleOption
from forge.plugins.ansible.names import MAX_PORT, MIN_PORT


def ask_role_options(prompter: Prompter, role: RoleDefinition) -> dict[str, Any]:
    """Ask every question of a role and return the entered values."""
    prompter.note(f"\nRole '{role.name}' — {role.summary}")
    return {option.name: ask_option(prompter, option) for option in role.options}


def ask_option(prompter: Prompter, option: RoleOption) -> Any:
    """Ask the question matching an option and return its value."""
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
    """Ask for an integer, applying the port bounds where relevant."""
    is_port = "port" in option.name

    def validate(value: str) -> str | None:
        try:
            parsed = int(value.strip())
        except ValueError:
            return f"An integer is expected, got: '{value}'."
        if is_port and not MIN_PORT <= parsed <= MAX_PORT:
            return f"The port must be between {MIN_PORT} and {MAX_PORT}."
        if not is_port and parsed < 0:
            return "A positive integer is expected."
        return None

    return int(prompter.text(option.question, default=str(option.default), validate=validate))


def _ask_list(prompter: Prompter, option: RoleOption) -> list[Any]:
    """Ask for a list entered as comma-separated values."""
    default = ", ".join(str(item) for item in option.default)

    def validate(value: str) -> str | None:
        if option.item_kind is not OptionKind.INT:
            return None
        for item in _split(value):
            if not item.lstrip("-").isdigit():
                return f"'{item}' is not an integer."
        return None

    raw = prompter.text(f"{option.question} [{option.allowed}]", default=default, validate=validate)
    items = _split(raw)
    if option.item_kind is OptionKind.INT:
        return [int(item) for item in items]
    return items


def _ask_records(prompter: Prompter, option: RoleOption) -> list[dict[str, Any]]:
    """Ask for a list of dictionaries, one record at a time."""
    records: list[dict[str, Any]] = []
    while prompter.confirm(
        f"{option.question} — add an entry?" if records else f"{option.question}?",
        default=not records,
    ):
        record = {field.name: ask_option(prompter, field) for field in option.fields}
        records.append(record)
    return records


def _split(value: str) -> list[str]:
    """Split an entry such as 'a, b , c' into a list, ignoring empty parts."""
    return [item.strip() for item in value.split(",") if item.strip()]
