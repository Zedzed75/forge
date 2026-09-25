"""Interactive input layer (port of `ansible_forge.prompts.prompter`).

The interview is written against the `Prompter` protocol, never against
`questionary`: the tests therefore replay a complete interview with scripted
answers, and the question logic stays verifiable without a terminal. Plugins
receive this protocol through the `forge_interview` hook.
"""

from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable

from forge.errors import ForgeError

#: Validation function: returns None when the value is acceptable, otherwise the
#: error message to display.
Validator = Callable[[str], "str | None"]


@runtime_checkable
class Prompter(Protocol):
    """Input operations used by the interviews."""

    def text(self, message: str, default: str = "", validate: Validator | None = None) -> str:
        """Ask for a free-form string."""

    def confirm(self, message: str, default: bool = True) -> bool:
        """Ask a yes/no question."""

    def select(self, message: str, choices: list[tuple[str, str]], default: str) -> str:
        """Ask to pick one value among `choices` (value, label)."""

    def checkbox(
        self, message: str, choices: list[tuple[str, str]], default: list[str]
    ) -> list[str]:
        """Ask to pick zero or more values among `choices`."""

    def note(self, message: str) -> None:
        """Print information without waiting for an answer."""


class QuestionaryPrompter:
    """Implementation of `Prompter` built on questionary."""

    def text(self, message: str, default: str = "", validate: Validator | None = None) -> str:
        import questionary

        answer = questionary.text(
            message,
            default=default,
            validate=_as_questionary_validator(validate),
        ).ask()
        return _require(answer)

    def confirm(self, message: str, default: bool = True) -> bool:
        import questionary

        return _require(questionary.confirm(message, default=default).ask())

    def select(self, message: str, choices: list[tuple[str, str]], default: str) -> str:
        import questionary

        options = [questionary.Choice(title=label, value=value) for value, label in choices]
        return _require(questionary.select(message, choices=options, default=default).ask())

    def checkbox(
        self, message: str, choices: list[tuple[str, str]], default: list[str]
    ) -> list[str]:
        import questionary

        options = [
            questionary.Choice(title=label, value=value, checked=value in default)
            for value, label in choices
        ]
        return _require(questionary.checkbox(message, choices=options).ask())

    def note(self, message: str) -> None:
        import questionary

        questionary.print(message)


def _as_questionary_validator(validate: Validator | None):
    """Adapt one of the project's validators to questionary's API."""
    if validate is None:
        return None

    def _validate(value: str) -> bool | str:
        error = validate(value)
        return True if error is None else error

    return _validate


def _require(answer):
    """Turn an interrupted input (Ctrl+C) into an explicit error."""
    if answer is None:
        raise ForgeError("Input interrupted: nothing was generated.")
    return answer
