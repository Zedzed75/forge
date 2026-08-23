"""Prompter scripté permettant de rejouer un entretien complet dans les tests.

Les réponses sont indexées par fragment de question : un test ne décrit que ce
qu'il veut changer, tout le reste prend la valeur par défaut proposée par le
questionnaire. Ajouter une question au flux ne casse donc pas les tests
existants.

Chaque réponse est passée au validateur de la question : un test qui fournit
une valeur invalide échoue immédiatement, comme le ferait l'utilisateur.
"""

from __future__ import annotations

from typing import Any

from ansible_forge.prompts.prompter import Validator


class ScriptedPrompter:
    """Implémentation de :class:`Prompter` pilotée par un dictionnaire."""

    def __init__(self, answers: dict[str, Any] | None = None) -> None:
        #: Fragment de question -> réponse. Le premier fragment trouvé gagne.
        self.answers: dict[str, Any] = dict(answers or {})
        #: Historique des questions posées, utile pour les assertions.
        self.asked: list[str] = []
        #: Messages informatifs affichés par le questionnaire.
        self.notes: list[str] = []

    def text(self, message: str, default: str = "", validate: Validator | None = None) -> str:
        value = str(self._lookup(message, default))
        if validate is not None:
            error = validate(value)
            if error is not None:
                raise AssertionError(f"Réponse invalide pour « {message} » : {error}")
        return value

    def confirm(self, message: str, default: bool = True) -> bool:
        return bool(self._lookup(message, default))

    def select(self, message: str, choices: list[tuple[str, str]], default: str) -> str:
        value = str(self._lookup(message, default))
        valid = [item[0] for item in choices]
        assert value in valid, f"« {value} » n'est pas un choix de « {message} » ({valid})"
        return value

    def checkbox(
        self, message: str, choices: list[tuple[str, str]], default: list[str]
    ) -> list[str]:
        value = list(self._lookup(message, default))
        valid = {item[0] for item in choices}
        unknown = sorted(set(value) - valid)
        assert not unknown, f"Choix inconnus pour « {message} » : {unknown}"
        return value

    def note(self, message: str) -> None:
        self.notes.append(message)

    def _lookup(self, message: str, default: Any) -> Any:
        """Retourne la réponse scriptée correspondant à la question, sinon le défaut."""
        self.asked.append(message)
        for fragment, answer in self.answers.items():
            if fragment in message:
                return answer
        return default


#: Réponses minimales permettant à un entretien d'aboutir (adresses des machines).
BASE_ANSWERS: dict[str, Any] = {
    "Adresse IP": "10.0.0.10",
    "Nombre de machines": "1",
}
