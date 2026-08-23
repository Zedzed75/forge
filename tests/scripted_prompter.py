"""Prompter scripte : rejoue un entretien complet sans terminal.

Portage de `tests/scripted_prompter.py` d'ansible-forge (MIGRATION.md §3). Les
reponses sont consommees dans l'ordre ; une reponse manquante ou d'un type
inattendu leve, ce qui transforme une derive du questionnaire en echec de test
explicite plutot qu'en blocage.
"""

from __future__ import annotations

from typing import Any

from forge.interview.prompter import Validator


class ScriptedPrompter:
    """Implementation de `Prompter` alimentee par une liste de reponses."""

    def __init__(self, answers: list[Any]) -> None:
        self.answers = list(answers)
        self.asked: list[str] = []
        self.notes: list[str] = []

    def _next(self, message: str, expected: type | tuple[type, ...]) -> Any:
        self.asked.append(message)
        if not self.answers:
            raise AssertionError(f"reponse manquante pour la question : {message!r}")
        answer = self.answers.pop(0)
        if not isinstance(answer, expected):
            raise AssertionError(
                f"reponse de type {type(answer).__name__} pour {message!r}, "
                f"attendu {expected}"
            )
        return answer

    def text(self, message: str, default: str = "", validate: Validator | None = None) -> str:
        answer = self._next(message, str)
        if validate is not None:
            error = validate(answer)
            if error is not None:
                raise AssertionError(f"reponse refusee pour {message!r} : {error}")
        return answer

    def confirm(self, message: str, default: bool = True) -> bool:
        return self._next(message, bool)

    def select(self, message: str, choices: list[tuple[str, str]], default: str) -> str:
        answer = self._next(message, str)
        values = [value for value, _ in choices]
        if answer not in values:
            raise AssertionError(f"{answer!r} ne fait pas partie de {values}")
        return answer

    def checkbox(
        self, message: str, choices: list[tuple[str, str]], default: list[str]
    ) -> list[str]:
        answer = self._next(message, list)
        values = [value for value, _ in choices]
        unknown = [item for item in answer if item not in values]
        if unknown:
            raise AssertionError(f"choix inconnus {unknown} parmi {values}")
        return answer

    def note(self, message: str) -> None:
        self.notes.append(message)

    @property
    def exhausted(self) -> bool:
        """Vrai si toutes les reponses scriptees ont ete consommees."""
        return not self.answers
