"""Which reduction a file gets, and the token that stands in for prose.

Split out of `tests/fingerprint.py` (ZED-223), which had grown to 857 lines by
answering three questions at once. This module answers the first of them --
*what kind of thing is this file?* -- for the two that reduce a file:

* `tests/fingerprint_structured.py` -- the documents that parse,
* `tests/fingerprint_textual.py` -- the ones that do not,

and for `tests/fingerprint.py`, which assembles a whole tree out of either and
holds the contract the three of them serve.

What each kind keeps, and why, is documented where its reduction lives. What is
here is only the mapping from a path to one of them -- plus `PROSE`, the
constant every reduction substitutes for a field it has decided is prose, held
here because all of them write it and none of them owns it.
"""

from __future__ import annotations

from pathlib import Path

#: Replaces the value of every field this harness treats as prose.
PROSE = "<prose>"

#: Dotfiles that hold YAML without saying so in a suffix.
_STRUCTURED_NAMES = frozenset({".yamllint", ".ansible-lint"})

#: Suffixes parsed as data documents. JSON is a subset of YAML, so one loader
#: covers both.
_STRUCTURED_SUFFIXES = frozenset({".yml", ".yaml", ".json"})

#: Suffixes whose body is prose from beginning to end.
_PROSE_SUFFIXES = frozenset({".md", ".txt"})

# The four kinds a file can be reduced to.
STRUCTURED = "structured"
TEMPLATE = "template"
PROSE_KIND = "prose"
TEXT = "text"

#: Not a classification: what a file that does not decode as UTF-8 falls back to.
BINARY = "binary"


def is_chart_template(root: Path, relative: Path) -> bool:
    """True for a file inside a Helm chart's `templates/` directory.

    Recognised by the chart itself rather than by a hardcoded path: the segment
    must be called `templates` *and* its parent must hold a `Chart.yaml`. An
    Ansible role's `templates/` directory therefore does not match.
    """
    parts = relative.parts
    for index, part in enumerate(parts[:-1]):
        if part == "templates" and (root.joinpath(*parts[:index], "Chart.yaml")).is_file():
            return True
    return False


def classify(root: Path, relative: Path) -> str:
    """Kind of reduction applied to one file."""
    name = relative.name
    suffix = relative.suffix

    # `vault.yml.example` is a YAML document wearing a second suffix.
    if suffix == ".example":
        return classify(root, relative.with_name(relative.stem))

    if name in _STRUCTURED_NAMES:
        return STRUCTURED
    if suffix in _PROSE_SUFFIXES:
        return PROSE_KIND
    if suffix == ".tpl" or is_chart_template(root, relative):
        return TEMPLATE
    if suffix in _STRUCTURED_SUFFIXES:
        return STRUCTURED
    return TEXT
