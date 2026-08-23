"""Couche de saisie interactive.

Le questionnaire est écrit contre le protocole :class:`Prompter`, pas contre
``questionary``. Les tests peuvent donc rejouer un entretien complet avec des
réponses scriptées, et la logique des questions reste vérifiable sans terminal.
"""

from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable

import questionary

from ansible_forge.errors import ForgeError

#: Fonction de validation : retourne ``None`` si la valeur est acceptable,
#: sinon le message d'erreur à afficher.
Validator = Callable[[str], "str | None"]


@runtime_checkable
class Prompter(Protocol):
    """Opérations de saisie utilisées par le questionnaire."""

    def text(self, message: str, default: str = "", validate: Validator | None = None) -> str:
        """Demande une chaîne libre."""

    def confirm(self, message: str, default: bool = True) -> bool:
        """Demande une réponse oui/non."""

    def select(self, message: str, choices: list[tuple[str, str]], default: str) -> str:
        """Demande de choisir une valeur parmi ``choices`` (valeur, libellé)."""

    def checkbox(
        self, message: str, choices: list[tuple[str, str]], default: list[str]
    ) -> list[str]:
        """Demande de choisir zéro ou plusieurs valeurs parmi ``choices``."""

    def note(self, message: str) -> None:
        """Affiche une information sans attendre de réponse."""


class QuestionaryPrompter:
    """Implémentation de :class:`Prompter` fondée sur ``questionary``."""

    def text(self, message: str, default: str = "", validate: Validator | None = None) -> str:
        answer = questionary.text(
            message,
            default=default,
            validate=_as_questionary_validator(validate),
        ).ask()
        return _require(answer)

    def confirm(self, message: str, default: bool = True) -> bool:
        return _require(questionary.confirm(message, default=default).ask())

    def select(self, message: str, choices: list[tuple[str, str]], default: str) -> str:
        options = [questionary.Choice(title=label, value=value) for value, label in choices]
        return _require(questionary.select(message, choices=options, default=default).ask())

    def checkbox(
        self, message: str, choices: list[tuple[str, str]], default: list[str]
    ) -> list[str]:
        options = [
            questionary.Choice(title=label, value=value, checked=value in default)
            for value, label in choices
        ]
        return _require(questionary.checkbox(message, choices=options).ask())

    def note(self, message: str) -> None:
        questionary.print(message)


def _as_questionary_validator(validate: Validator | None):
    """Adapte un validateur du projet à l'API de questionary."""
    if validate is None:
        return None

    def _validate(value: str) -> bool | str:
        error = validate(value)
        return True if error is None else error

    return _validate


def _require(answer):
    """Transforme une saisie interrompue (Ctrl+C) en erreur explicite."""
    if answer is None:
        raise ForgeError("Saisie interrompue : aucun projet n'a été généré.")
    return answer
