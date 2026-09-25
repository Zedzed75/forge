"""Scripted prompter: replays a complete interview without a terminal.

Port of ansible-forge's `tests/scripted_prompter.py` (MIGRATION.md §3). The
answers are consumed in order; a missing answer, or one of an unexpected type,
raises — which turns a drift in the questionnaire into an explicit test failure
rather than a hang.
"""

from __future__ import annotations

from typing import Any

from forge.interview.prompter import Validator


class ScriptedPrompter:
    """Implementation of `Prompter` fed from a list of answers."""

    def __init__(self, answers: list[Any]) -> None:
        self.answers = list(answers)
        self.asked: list[str] = []
        self.notes: list[str] = []

    def _next(self, message: str, expected: type | tuple[type, ...]) -> Any:
        self.asked.append(message)
        if not self.answers:
            raise AssertionError(f"missing answer for question: {message!r}")
        answer = self.answers.pop(0)
        if not isinstance(answer, expected):
            raise AssertionError(
                f"answer of type {type(answer).__name__} for {message!r}, "
                f"expected {expected}"
            )
        return answer

    def text(self, message: str, default: str = "", validate: Validator | None = None) -> str:
        answer = self._next(message, str)
        if validate is not None:
            error = validate(answer)
            if error is not None:
                raise AssertionError(f"answer refused for {message!r}: {error}")
        return answer

    def confirm(self, message: str, default: bool = True) -> bool:
        return self._next(message, bool)

    def select(self, message: str, choices: list[tuple[str, str]], default: str) -> str:
        answer = self._next(message, str)
        values = [value for value, _ in choices]
        if answer not in values:
            raise AssertionError(f"{answer!r} is not one of {values}")
        return answer

    def checkbox(
        self, message: str, choices: list[tuple[str, str]], default: list[str]
    ) -> list[str]:
        answer = self._next(message, list)
        values = [value for value, _ in choices]
        unknown = [item for item in answer if item not in values]
        if unknown:
            raise AssertionError(f"unknown choices {unknown} among {values}")
        return answer

    def note(self, message: str) -> None:
        self.notes.append(message)

    @property
    def exhausted(self) -> bool:
        """True when every scripted answer has been consumed."""
        return not self.answers
