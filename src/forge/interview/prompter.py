"""Couche de saisie interactive (portage de `ansible_forge.prompts.prompter`).

L'entretien est ecrit contre le protocole `Prompter`, jamais contre
`questionary` : les tests rejouent donc un entretien complet avec des reponses
scriptees, et la logique des questions reste verifiable sans terminal. Les
plugins recoivent ce protocole via le hook `forge_interview`.
"""

from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable

from forge.errors import ForgeError

#: Fonction de validation : retourne None si la valeur est acceptable, sinon le
#: message d'erreur a afficher.
Validator = Callable[[str], "str | None"]


@runtime_checkable
class Prompter(Protocol):
    """Operations de saisie utilisees par les entretiens."""

    def text(self, message: str, default: str = "", validate: Validator | None = None) -> str:
        """Demande une chaine libre."""

    def confirm(self, message: str, default: bool = True) -> bool:
        """Demande une reponse oui/non."""

    def select(self, message: str, choices: list[tuple[str, str]], default: str) -> str:
        """Demande de choisir une valeur parmi `choices` (valeur, libelle)."""

    def checkbox(
        self, message: str, choices: list[tuple[str, str]], default: list[str]
    ) -> list[str]:
        """Demande de choisir zero ou plusieurs valeurs parmi `choices`."""

    def note(self, message: str) -> None:
        """Affiche une information sans attendre de reponse."""


class QuestionaryPrompter:
    """Implementation de `Prompter` fondee sur questionary."""

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
    """Adapte un validateur du projet a l'API de questionary."""
    if validate is None:
        return None

    def _validate(value: str) -> bool | str:
        error = validate(value)
        return True if error is None else error

    return _validate


def _require(answer):
    """Transforme une saisie interrompue (Ctrl+C) en erreur explicite."""
    if answer is None:
        raise ForgeError("Saisie interrompue : rien n'a ete genere.")
    return answer
