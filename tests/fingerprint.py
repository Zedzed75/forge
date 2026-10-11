"""Structural fingerprint of a generated tree: "this changed prose, and nothing else".

Comments in this module are in English: new test infrastructure, no French
precedent, and no effect on generated output.

WHY THIS EXISTS
===============
`tests/test_golden.py` asserts byte equality. That is the right check for a
deterministic generator, and the wrong tool for reviewing a translation: a pass
that rewrites the text of every template regenerates every golden fixture, so
byte equality goes red on all of them and says nothing about whether *behaviour*
changed. A reviewer needs to check exactly one claim -- "this pull request
changed prose and nothing else" -- and no human can check it by reading 2.6 MB
of diff.

The fingerprint is that check, mechanised. It reduces a generated tree to what a
validator, a Kubernetes API server or an Ansible run would actually care about,
and deliberately forgets the rest. Two trees with the same fingerprint differ
only in prose; two trees with different fingerprints differ somewhere that
matters, and the difference names the file.

THE DIRECTION OF ERROR MATTERS
==============================
Normalising away a field that carries real meaning would let a genuine
behavioural change through invisibly -- the one failure mode this harness must
not have. Normalising too little only produces a false alarm: the fingerprint
trips, a human looks, and confirms the change was intentional. So every
judgement call in the reduction modules is resolved towards *strictness*, and
the list of normalised fields is deliberately short. Do not extend it to make a
failing translation pass: if a translation trips the fingerprint, the default
assumption is that the translation is wrong.

WHERE THE RULES LIVE
====================
This module owns the contract above, the tree, the two correspondences and the
stored form. *What* is normalised, and why, lives one module away from each
reduction, because that is where it has to be read:

    tests/fingerprint_kinds.py       which of the four kinds a file is, and the
                                     `PROSE` token they all substitute
    tests/fingerprint_structured.py  the `structured` kind: YAML and JSON that
                                     parse, compared as parsed structure
    tests/fingerprint_textual.py     the `template`, `prose` and `text` kinds:
                                     no parser, so a text filter each

The split is ZED-223; before it, all four were one 857-line module.

THE TWO CORRESPONDENCES
=======================
Normalising a name away would also hide a broken *reference* to that name, and
two such references exist in this project. Both are recorded as relationships
between positions instead of strings, which makes them invariant under a
consistent translation and sensitive to an inconsistent one.

`ansible_handler_links` -- Ansible matches `notify:` to a handler **by name
    string**. A translated handler name with an untranslated `notify:` (or the
    reverse) is a real, silent breakage: the handler simply never runs. Each
    handler gets an index from its position (file path, then order of definition
    in the file -- both structural, neither prose), and each `notify:` is
    recorded as the index of the handler it resolves to, or `UNRESOLVED`.
    Translate both sides together and the indices are unchanged; translate one
    side and the link goes `UNRESOLVED`. Handler `listen:` topics resolve the
    same way.

`helm_helper_links` -- the same relationship for Helm: `{{ include
    "chart.labels" . }}` against the `{{- define "chart.labels" }}` in
    `_helpers.tpl`. Helper names are identifiers rather than prose, so they are
    already compared verbatim; recording the correspondence makes a dangling
    `include` show up as a named field instead of being buried inside a content
    digest.

WHAT THE FINGERPRINT DOES NOT PROMISE
=====================================
* It compares the POSIX executable bit, which Windows cannot represent. Every
  file of every golden tree is `0644` today, so the recorded value is the same
  on both platforms; the day a template needs to be executable, the stored
  fingerprint has to be regenerated on Linux.
* Blank lines and trailing whitespace are dropped in the `text` and `template`
  kinds. Neither is behaviour in any file type generated here.
* Identifiers derived from French words -- a Prometheus alert named
  `HighLatency`, a role named `ssh_hardening` -- are compared
  verbatim. Renaming them *will* trip the fingerprint. That is correct: they are
  not prose, they are referenced elsewhere (a promtool test asserts on
  `alertname`), and renaming them is a structural change a reviewer must see.

USAGE
=====
    python -m tests.fingerprint tests/golden/ansible-ci
    python -m tests.fingerprint tests/golden/ansible-ci ansible/roles/common/tasks/main.yml
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from tests.conftest import REPO_ROOT, stable_text
from tests.fingerprint_kinds import (
    BINARY,
    PROSE_KIND,
    STRUCTURED,
    TEMPLATE,
    classify,
    is_chart_template,
)
from tests.fingerprint_structured import parsed_documents, structured_canonical, walk_mappings
from tests.fingerprint_textual import (
    prose_canonical,
    strip_unambiguous_comments,
    template_canonical,
    text_canonical,
)

#: Stored references, one JSON file per golden tree.
FINGERPRINTS_DIR = REPO_ROOT / "tests" / "fingerprints"

#: Schema version of a stored fingerprint. Bump it when the canonical form
#: changes, so a stale reference fails loudly instead of comparing apples to
#: oranges.
#:
#: 2 -- `project_description` joined `PROSE_KEYS`, which changes the digest of
#: every `group_vars/all.yml`. A reference blessed under 1 is not comparable
#: there, and with a dozen branches carrying blessed fingerprints at the time,
#: the difference had to announce itself as a form change rather than as a
#: structural move in that one file.
FINGERPRINT_VERSION = 2

#: Helm helper definitions and the two ways of calling them.
_HELM_DEFINE = re.compile(r'\bdefine\s+"([^"]+)"')
_HELM_CALL = re.compile(r'\b(?:include|template)\s+"([^"]+)"')


# ---------------------------------------------------------------------------
# One file
# ---------------------------------------------------------------------------


def canonical_text(root: Path, relative: Path) -> tuple[str, str]:
    """Canonical form of one file, and the kind it was reduced as."""
    try:
        text = stable_text(root / relative)
    except UnicodeDecodeError:
        # No generated file is binary today. If one ever is, nothing in it is
        # prose, so its bytes are compared -- rather than the whole fingerprint
        # dying on a decoding error.
        return BINARY, hashlib.sha256((root / relative).read_bytes()).hexdigest()
    kind = classify(root, relative)
    if kind == STRUCTURED:
        canonical = structured_canonical(text, relative)
        if canonical is not None:
            return kind, canonical
        # A `.yml` that does not parse is a template in disguise. Record the
        # fallback in the kind: a file that stops (or starts) parsing is a
        # change worth seeing, not something to absorb silently.
        return f"{TEMPLATE}(unparsed-yaml)", template_canonical(text)
    if kind == TEMPLATE:
        return kind, template_canonical(text)
    if kind == PROSE_KIND:
        return kind, prose_canonical(text, relative)
    return kind, text_canonical(text, relative)


def _mode(path: Path) -> str:
    """POSIX executable bit, the only mode bit git records and copier carries."""
    return "x" if path.stat().st_mode & 0o111 else "-"


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Correspondences
# ---------------------------------------------------------------------------


def _ansible_links(root: Path, files: list[Path]) -> list[str]:
    """`notify:` against handler names, recorded as positions instead of strings."""
    definitions: list[tuple[str, str]] = []  # (location, resolvable name)
    locations: list[str] = []
    for relative in files:
        if "handlers" not in relative.parts or classify(root, relative) != STRUCTURED:
            continue
        documents = parsed_documents(root, relative)
        if documents is None:
            continue
        for document in documents:
            if not isinstance(document, list):
                continue
            for index, item in enumerate(document):
                if not isinstance(item, dict):
                    continue
                location = f"{relative.as_posix()}[{index}]"
                locations.append(location)
                name = item.get("name")
                if isinstance(name, str):
                    definitions.append((location, name))
                listen = item.get("listen")
                for topic in [listen] if isinstance(listen, str) else (listen or []):
                    if isinstance(topic, str):
                        definitions.append((location, topic))

    index_of = {location: number for number, location in enumerate(locations)}
    resolve = {name: index_of[location] for location, name in definitions}

    lines = [f"H{index_of[location]} = {location}" for location in locations]
    for relative in files:
        if classify(root, relative) != STRUCTURED:
            continue
        documents = parsed_documents(root, relative)
        if documents is None:
            continue
        for number, document in enumerate(documents):
            for pointer, mapping in walk_mappings(document, f"{relative.as_posix()}#{number}"):
                notify = mapping.get("notify")
                if notify is None:
                    continue
                targets = [notify] if isinstance(notify, str) else notify
                for rank, target in enumerate(targets if isinstance(targets, list) else []):
                    resolved = resolve.get(target, None) if isinstance(target, str) else None
                    label = "UNRESOLVED" if resolved is None else f"H{resolved}"
                    lines.append(f"{pointer}/notify[{rank}] -> {label}")
    return sorted(lines)


def _helm_links(root: Path, files: list[Path]) -> list[str]:
    """`include`/`template` calls against the `define` they resolve to."""
    locations: list[str] = []
    resolve: dict[str, int] = {}
    for relative in files:
        if relative.suffix != ".tpl" and not is_chart_template(root, relative):
            continue
        text = strip_unambiguous_comments(stable_text(root / relative))
        for rank, match in enumerate(_HELM_DEFINE.finditer(text)):
            location = f"{relative.as_posix()}#{rank}"
            resolve.setdefault(match.group(1), len(locations))
            locations.append(location)

    lines = [f"D{number} = {location}" for number, location in enumerate(locations)]
    for relative in files:
        # Comments are stripped first: a `{{/* ... */}}` block that happens to
        # mention `include "x"` in prose is not a call.
        text = strip_unambiguous_comments(stable_text(root / relative))
        for rank, match in enumerate(_HELM_CALL.finditer(text)):
            resolved = resolve.get(match.group(1))
            label = "UNRESOLVED" if resolved is None else f"D{resolved}"
            lines.append(f"{relative.as_posix()}#{rank} -> {label}")
    return sorted(lines)


# ---------------------------------------------------------------------------
# One tree
# ---------------------------------------------------------------------------


def tree_paths(root: Path) -> list[Path]:
    """Every file of the tree, sorted, `.git` excluded."""
    return sorted(
        (
            path.relative_to(root)
            for path in root.rglob("*")
            if path.is_file() and ".git" not in path.parts
        ),
        key=lambda relative: relative.as_posix(),
    )


def fingerprint(root: Path) -> dict[str, Any]:
    """Structural fingerprint of a generated tree."""
    files = tree_paths(root)
    entries: dict[str, str] = {}
    for relative in files:
        kind, canonical = canonical_text(root, relative)
        entries[relative.as_posix()] = f"{_mode(root / relative)} {kind} {_digest(canonical)}"
    return {
        "fingerprint_version": FINGERPRINT_VERSION,
        "files": entries,
        "ansible_handler_links": _ansible_links(root, files),
        "helm_helper_links": _helm_links(root, files),
    }


def dumps(data: dict[str, Any]) -> str:
    """Stored form: one line per file, so a diff names what moved."""
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def stored_path(case: str) -> Path:
    return FINGERPRINTS_DIR / f"{case}.json"


def load(case: str) -> dict[str, Any]:
    return json.loads(stored_path(case).read_text(encoding="utf-8"))


def store(case: str, data: dict[str, Any]) -> None:
    FINGERPRINTS_DIR.mkdir(parents=True, exist_ok=True)
    stored_path(case).write_text(dumps(data), encoding="utf-8", newline="\n")


def differences(expected: dict[str, Any], obtained: dict[str, Any]) -> list[str]:
    """Human-readable differences between two fingerprints, most useful first."""
    report: list[str] = []
    if expected.get("fingerprint_version") != obtained.get("fingerprint_version"):
        report.append(
            "fingerprint_version: "
            f"{expected.get('fingerprint_version')} -> {obtained.get('fingerprint_version')}"
        )

    before, after = expected.get("files", {}), obtained.get("files", {})
    for path in sorted(set(after) - set(before)):
        report.append(f"added: {path}")
    for path in sorted(set(before) - set(after)):
        report.append(f"removed: {path}")
    for path in sorted(set(before) & set(after)):
        if before[path] != after[path]:
            report.append(f"changed: {path} ({before[path]} -> {after[path]})")

    for section in ("ansible_handler_links", "helm_helper_links"):
        was, now = set(expected.get(section, [])), set(obtained.get(section, []))
        for line in sorted(now - was):
            report.append(f"{section} added: {line}")
        for line in sorted(was - now):
            report.append(f"{section} removed: {line}")
    return report


def main(argv: list[str]) -> int:
    """`python -m tests.fingerprint <tree> [relative-path]`."""
    if not argv:
        print(main.__doc__, file=sys.stderr)
        return 2
    root = Path(argv[0]).resolve()
    if len(argv) > 1:
        kind, canonical = canonical_text(root, Path(argv[1]))
        print(f"# kind: {kind}")
        print(canonical)
        return 0
    print(dumps(fingerprint(root)), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
