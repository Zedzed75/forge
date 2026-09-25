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
judgement call below is resolved towards *strictness*, and the list of
normalised fields is deliberately short. Do not extend it to make a failing
translation pass: if a translation trips the fingerprint, the default assumption
is that the translation is wrong.

WHAT IS NORMALISED, AND WHY
===========================
Files are classified into four kinds, and each kind keeps a different thing.

`structured` -- YAML and JSON documents that parse (`forge.yml`, `values.yaml`,
    Prometheus rules, Ansible tasks, `.copier-answers.yml`, `.ansible-lint`...).
    The parsed structure is compared, so every comment disappears for free and
    no comment-stripping heuristic can get it wrong. On top of that:

    * a mapping key named `description` or `summary` has its string value
      replaced by a constant. In this project those two keys are prose
      everywhere they occur: `service.description`, `Chart.yaml`, Ansible
      `galaxy_info`, Terraform-facing answers, and the `annotations` of every
      Prometheus alert. Nothing reads them.
    * an Ansible task `name` is replaced by a constant -- but only at task
      positions, never as a generic key. `name` is load-bearing almost
      everywhere else: `metadata.name` in a manifest, `name:` as an argument to
      `ansible.builtin.user` or a container port. So a `name` is normalised only
      when it is the name of a play, of a task, or of a handler, recognised by
      *position*: the items of the top-level sequence of a file under `tasks/`
      or `handlers/`, the items of a playbook's `tasks`/`pre_tasks`/
      `post_tasks`/`handlers`, and recursively the items of `block`, `rescue`
      and `always`.
    * a GitHub Actions step label -- `jobs.<id>.steps[].name` in a file sitting
      directly in `.github/workflows/` -- is replaced by a constant, for the
      same reason and under the same discipline: it is recognised by *position*,
      never as a key called `name` somewhere under `.github/`. A step label is
      pure display text; nothing in a workflow can reference a step by it, since
      `steps.<id>.outputs` and `needs:` go through the step `id:` and the job
      key. Rewording a label therefore cannot change what the workflow runs. The
      two `name:` keys standing right next to it are left verbatim, and are
      load-bearing: `jobs.<id>.name` is the check name a branch-protection rule
      matches a required status check against, and the workflow-level `name:` is
      what `github.workflow`, a `workflow_run` trigger and a README badge URL
      refer to.

      GitLab CI deliberately gets nothing equivalent, because it has nothing
      equivalent. A `.gitlab-ci.yml` has no display-label key at all: a job *is*
      its top-level mapping key, and `stage:`, `needs:` and `extends:` reference
      jobs by that key. The closest thing to a label is the key itself, an
      identifier that must stay verbatim. Translating a GitLab pipeline touches
      its comments and nothing else, so there is nothing to loosen -- the
      absence is the decision, not an oversight.
    * an Ansible `notify:` or handler `listen:` value is replaced by a constant
      too. It is not data: it is the handler name repeated, so leaving it
      verbatim would make a *correctly* translated handler pair trip the
      fingerprint and the whole check would be useless on exactly the files it
      was written for. The reference itself is not lost -- it moves to
      `ansible_handler_links` below, where it is compared by position, which is
      what catches the half-translated case.
    * Kubernetes `annotations` are **not** normalised wholesale, despite being
      the obvious candidate. Annotation values are frequently behaviour:
      `nginx.ingress.kubernetes.io/rewrite-target`,
      `cert-manager.io/cluster-issuer`, `checksum/config`. Blanket-normalising
      them would hide exactly the kind of change this harness exists to catch.
      In this project's parseable YAML the only prose annotations are `summary`
      and `description`, which the key rule above already covers; the
      `annotations:` mappings of the Helm chart are Go-template text and never
      reach this path. `tests/test_fingerprint.py` guards that statement, so the
      decision gets revisited if a new prose annotation appears rather than
      rotting silently.

`template` -- Helm chart templates (anything under a chart's `templates/`
    directory, plus `.tpl` helpers). These are Go templates, not YAML: they do
    not parse, so there is no structure to compare and the text is kept. Only
    `{{/* ... */}}` Go-template comments and `{# ... #}` Jinja comments are
    removed, because those two forms are unambiguous -- they cannot mean
    anything but a comment. Full-line `#` comments are deliberately **not**
    stripped here: in an unparseable YAML file a `#` line may be a manifest
    comment or data inside a block scalar, and the two cannot be told apart
    without a parser. That costs nothing today (the generated chart templates
    carry no `#` comments at all, and a test asserts it) and it avoids a
    silently loose rule if they ever do.

`prose` -- `.md` and `.txt` files. These are documentation: their body is prose
    from the first line to the last, so a digest of the whole content would trip
    on every translation and the harness would be useless for exactly the files
    the translation touches most. What is kept is the part that is *not* prose:
    * every template expression (`{{ ... }}`, `{% ... %}`), in order. This is
      what makes Helm's `NOTES.txt` still checkable -- a broken expression there
      breaks `helm template`.
    * for Markdown: the verbatim content of fenced code blocks with their info
      string, every inline code span, every link destination, and the sequence
      of heading levels. Commands a reader copy-pastes, paths a link points at,
      and document shape are structure; the sentences around them are not.
    This is the loosest normalisation in the module, and it is loose on purpose:
    a generated README has no effect on any validator or on any deployed system.
    Its consequence is explicit -- the prose of a generated `.md`/`.txt` is
    unchecked, and a change confined to it is invisible here.

`text` -- everything else: `.tf`, `.tfvars`, `.hcl`, `Makefile`, `ansible.cfg`,
    `.gitignore`, `.gitattributes`, `.helmignore`, Jinja `.j2` templates
    deposited on managed hosts. Full-line comments are removed using the syntax
    of the file type (`#` everywhere, plus `//` and `/* ... */` for HCL), blank
    lines are dropped and trailing whitespace is stripped; the rest is kept
    verbatim. One prose field is normalised: a `description = "..."` argument
    inside a top-level `variable` or `output` block of an HCL file. Terraform
    variable and output descriptions are documentation, and nothing else in
    these files is. A `description` anywhere else -- a resource attribute sent
    to a provider API, for instance -- is left alone.

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
  `BoutiqueLatenceElevee`, a role named `ssh_hardening` -- are compared
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

import yaml

from tests.conftest import REPO_ROOT, stable_text

#: Stored references, one JSON file per golden tree.
FINGERPRINTS_DIR = REPO_ROOT / "tests" / "fingerprints"

#: Schema version of a stored fingerprint. Bump it when the canonical form
#: changes, so a stale reference fails loudly instead of comparing apples to
#: oranges.
FINGERPRINT_VERSION = 1

#: Replaces the value of every field this module treats as prose.
PROSE = "<prose>"

#: Mapping keys whose value is prose everywhere in this project's YAML.
PROSE_KEYS = frozenset({"description", "summary"})

#: Keys of an Ansible task whose value is itself a sequence of tasks.
_TASK_SEQUENCE_KEYS = frozenset({"block", "rescue", "always"})

#: Keys whose value is a handler name rather than data: normalised as prose,
#: with `ansible_handler_links` carrying the reference itself.
_HANDLER_REFERENCE_KEYS = frozenset({"notify", "listen"})

#: Keys of an Ansible play whose value is a sequence of tasks.
_PLAY_TASK_KEYS = frozenset({"tasks", "pre_tasks", "post_tasks", "handlers"})

#: Where GitHub reads workflows. It does not recurse into subdirectories, so a
#: workflow is a file sitting *directly* in `.github/workflows/` -- which is
#: exactly the positional precision the `steps[].name` rule needs.
_GITHUB_WORKFLOW_DIRECTORY = (".github", "workflows")

#: Dotfiles that hold YAML without saying so in a suffix.
_STRUCTURED_NAMES = frozenset({".yamllint", ".ansible-lint"})

#: Suffixes parsed as data documents. JSON is a subset of YAML, so one loader
#: covers both.
_STRUCTURED_SUFFIXES = frozenset({".yml", ".yaml", ".json"})

#: Suffixes whose body is prose from beginning to end.
_PROSE_SUFFIXES = frozenset({".md", ".txt"})

#: Suffixes using HCL comment syntax on top of `#`.
_HCL_SUFFIXES = frozenset({".tf", ".tfvars", ".hcl"})

#: Suffixes with no comment syntax at all.
_NO_COMMENT_SUFFIXES = frozenset({".json"})

# The four kinds a file can be reduced to.
STRUCTURED = "structured"
TEMPLATE = "template"
PROSE_KIND = "prose"
TEXT = "text"

#: Not a classification: what a file that does not decode as UTF-8 falls back to.
BINARY = "binary"

#: Comment forms that cannot mean anything else, and are therefore safe to
#: remove from any file type: Go-template comments and Jinja comments.
#: Both Go-template spellings occur in the generated charts: `{{/* ... */}}` and
#: `{{- /* ... */}}` with the whitespace-trim marker and a space.
_UNAMBIGUOUS_COMMENTS = (
    re.compile(r"\{\{-?\s*/\*.*?\*/\s*-?\}\}", re.DOTALL),
    re.compile(r"\{#.*?#\}", re.DOTALL),
)

#: Template expressions, kept in order for prose files: they are the only
#: load-bearing thing a `.txt` deliverable contains.
_EXPRESSIONS = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.DOTALL)

#: An HCL top-level block header, e.g. `variable "namespace" {`. Generated HCL
#: is formatted by `terraform fmt`, so a top-level block always starts in
#: column 0 and closes with a `}` in column 0 -- no brace counting needed, and
#: no risk of miscounting a brace inside a string.
_HCL_BLOCK_HEADER = re.compile(r"^([a-z_]+)\b.*\{\s*$")

#: A one-line HCL `description` argument. A multi-line form is left untouched:
#: conservative is the safe direction here.
_HCL_DESCRIPTION = re.compile(r'^(\s*description\s*=\s*)".*"\s*$')

#: HCL blocks whose `description` is documentation and nothing else.
_HCL_DOCUMENTED_BLOCKS = frozenset({"variable", "output"})

#: Markdown pieces that are structure rather than prose.
_MD_FENCE = re.compile(r"^\s*(?:```|~~~)(.*)$")
_MD_HEADING = re.compile(r"^(#{1,6})\s")
_MD_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_MD_LINK = re.compile(r"\]\(([^)\s]+)")

#: Helm helper definitions and the two ways of calling them.
_HELM_DEFINE = re.compile(r'\bdefine\s+"([^"]+)"')
_HELM_CALL = re.compile(r'\b(?:include|template)\s+"([^"]+)"')


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def _is_chart_template(root: Path, relative: Path) -> bool:
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
    if suffix == ".tpl" or _is_chart_template(root, relative):
        return TEMPLATE
    if suffix in _STRUCTURED_SUFFIXES:
        return STRUCTURED
    return TEXT


# ---------------------------------------------------------------------------
# Structured documents
# ---------------------------------------------------------------------------


def _document_position(relative: Path) -> str | None:
    """What the path says about how to read this document, or None for nothing.

    The three answers are the three places in this project where a `name` is a
    label rather than an identifier. The GitHub one is tested first because it
    is the most specific: it pins two consecutive path segments and the file's
    own suffix, where the Ansible ones only look for a segment anywhere.
    """
    parts = relative.parts
    if parts[-3:-1] == _GITHUB_WORKFLOW_DIRECTORY and relative.suffix in (".yml", ".yaml"):
        return "github_workflow"
    names = set(parts)
    if {"tasks", "handlers"} & names:
        return "tasks"
    if "playbooks" in names:
        return "plays"
    return None


def _normalise_any(node: Any) -> Any:
    """Generic walk: prose keys only. `name` is never touched here."""
    if isinstance(node, dict):
        return {
            key: PROSE if key in PROSE_KEYS and isinstance(value, str) else _normalise_any(value)
            for key, value in node.items()
        }
    if isinstance(node, list):
        return [_normalise_any(item) for item in node]
    return node


def _normalise_tasks(items: Any) -> Any:
    """Sequence of Ansible tasks: `name` is prose, `block`/`rescue`/`always` recurse."""
    if not isinstance(items, list):
        return _normalise_any(items)
    result = []
    for item in items:
        if not isinstance(item, dict):
            result.append(_normalise_any(item))
            continue
        task: dict[Any, Any] = {}
        for key, value in item.items():
            if key in ("name", *PROSE_KEYS) and isinstance(value, str):
                task[key] = PROSE
            elif key in _HANDLER_REFERENCE_KEYS:
                # A handler reference is the prose it points at, so its literal
                # text is normalised like the handler name itself. What replaces
                # it is `ansible_handler_links`, which compares the reference by
                # position -- see the module docstring.
                task[key] = PROSE if isinstance(value, str) else _normalise_reference(value)
            elif key in _TASK_SEQUENCE_KEYS:
                task[key] = _normalise_tasks(value)
            else:
                task[key] = _normalise_any(value)
        result.append(task)
    return result


def _normalise_reference(node: Any) -> Any:
    """A `notify:`/`listen:` value: a string, or a list of strings."""
    if isinstance(node, list):
        return [PROSE if isinstance(item, str) else _normalise_any(item) for item in node]
    return _normalise_any(node)


def _normalise_plays(items: Any) -> Any:
    """Sequence of Ansible plays: `name` is prose, task sequences recurse."""
    if not isinstance(items, list):
        return _normalise_any(items)
    result = []
    for item in items:
        if not isinstance(item, dict):
            result.append(_normalise_any(item))
            continue
        play: dict[Any, Any] = {}
        for key, value in item.items():
            if key in ("name", *PROSE_KEYS) and isinstance(value, str):
                play[key] = PROSE
            elif key in _PLAY_TASK_KEYS:
                play[key] = _normalise_tasks(value)
            else:
                play[key] = _normalise_any(value)
        result.append(play)
    return result


def _normalise_step(item: Any) -> Any:
    """One step of a GitHub Actions job: its `name` is a display label."""
    if not isinstance(item, dict):
        return _normalise_any(item)
    step: dict[Any, Any] = {}
    for key, value in item.items():
        if key in ("name", *PROSE_KEYS) and isinstance(value, str):
            step[key] = PROSE
        else:
            # `with:` is descended into generically, so a `name:` passed as an
            # argument to an action -- `actions/upload-artifact`, for one -- is
            # compared verbatim like any other input.
            step[key] = _normalise_any(value)
    return step


def _normalise_job(job: Any) -> Any:
    """One job of a workflow: only the items of its `steps` sequence are steps."""
    if not isinstance(job, dict):
        return _normalise_any(job)
    result: dict[Any, Any] = {}
    for key, value in job.items():
        if key == "steps" and isinstance(value, list):
            result[key] = [_normalise_step(item) for item in value]
        else:
            # `jobs.<id>.name` lands here on purpose: it is the check name, and
            # a branch-protection rule matches it as a string.
            result[key] = _normalise_any(value)
    return result


def _normalise_workflow(document: Any) -> Any:
    """A GitHub Actions workflow: descend to `jobs.<id>.steps[]` and nowhere else."""
    if not isinstance(document, dict):
        return _normalise_any(document)
    result: dict[Any, Any] = {}
    for key, value in document.items():
        if key == "jobs" and isinstance(value, dict):
            result[key] = {job_id: _normalise_job(job) for job_id, job in value.items()}
        else:
            # Including the workflow-level `name:`, which is an identifier.
            result[key] = _normalise_any(value)
    return result


def _normalise_document(document: Any, position: str | None) -> Any:
    if position == "tasks":
        return _normalise_tasks(document)
    if position == "plays":
        return _normalise_plays(document)
    if position == "github_workflow":
        return _normalise_workflow(document)
    return _normalise_any(document)


def _plain_key(key: Any) -> str:
    """JSON-safe rendering of a mapping key, tagged so types stay distinct."""
    return key if isinstance(key, str) else f"!{type(key).__name__}:{key!r}"


def _plain(node: Any) -> Any:
    """JSON-safe rendering of a parsed document (YAML dates, for instance)."""
    if isinstance(node, dict):
        return {_plain_key(key): _plain(value) for key, value in node.items()}
    if isinstance(node, (list, tuple)):
        return [_plain(item) for item in node]
    if node is None or isinstance(node, (bool, int, float, str)):
        return node
    return f"!{type(node).__name__}:{node!r}"


def _structured_canonical(text: str, relative: Path) -> str | None:
    """Canonical form of a data document, or None when it does not parse."""
    try:
        documents = list(yaml.safe_load_all(text))
    except yaml.YAMLError:
        return None
    position = _document_position(relative)
    normalised = [_normalise_document(document, position) for document in documents]
    return json.dumps(_plain(normalised), indent=2, sort_keys=True, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Text and template documents
# ---------------------------------------------------------------------------


def _strip_unambiguous_comments(text: str) -> str:
    for pattern in _UNAMBIGUOUS_COMMENTS:
        text = pattern.sub("", text)
    return text


def _tidy(lines: list[str]) -> str:
    """Drop blank lines and trailing whitespace: neither is behaviour here."""
    kept = [line.rstrip() for line in lines]
    return "\n".join(line for line in kept if line)


def _template_canonical(text: str) -> str:
    """Go/Jinja template text: only its own comment forms are removed."""
    return _tidy(_strip_unambiguous_comments(text).splitlines())


def _text_canonical(text: str, relative: Path) -> str:
    """Config or code: full-line comments removed, one prose field normalised."""
    suffix = relative.suffix
    if suffix == ".example":
        suffix = Path(relative.stem).suffix

    body = _strip_unambiguous_comments(text)
    hcl = suffix in _HCL_SUFFIXES
    if hcl:
        body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)

    hashes = suffix not in _NO_COMMENT_SUFFIXES
    block: str | None = None
    kept: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if hashes and stripped.startswith("#"):
            continue
        if hcl:
            if stripped.startswith("//"):
                continue
            if line.startswith("}"):
                block = None
            else:
                header = _HCL_BLOCK_HEADER.match(line)
                if header:
                    block = header.group(1)
            if block in _HCL_DOCUMENTED_BLOCKS:
                line = _HCL_DESCRIPTION.sub(rf'\1"{PROSE}"', line)
        kept.append(line)
    return _tidy(kept)


# ---------------------------------------------------------------------------
# Prose documents
# ---------------------------------------------------------------------------


def _prose_canonical(text: str, relative: Path) -> str:
    """Documentation: keep the parts that are not prose, forget the rest."""
    # Comments first: `{{/* ... */}}` would otherwise be collected as an
    # expression, and Helm's NOTES.txt opens with exactly that.
    text = _strip_unambiguous_comments(text)
    pieces: list[str] = [
        f"expression: {match.group(0).strip()}" for match in _EXPRESSIONS.finditer(text)
    ]
    if relative.suffix != ".md":
        return "\n".join(pieces)

    fence: str | None = None
    fenced: list[str] = []
    for line in text.splitlines():
        marker = _MD_FENCE.match(line)
        if marker and fence is None:
            fence = marker.group(1).strip()
            fenced = []
            pieces.append(f"fence-open: {fence}")
            continue
        if marker and fence is not None:
            pieces.append("fence-body: " + "\n".join(fenced))
            pieces.append("fence-close")
            fence = None
            continue
        if fence is not None:
            fenced.append(line.rstrip())
            continue
        heading = _MD_HEADING.match(line)
        if heading:
            pieces.append(f"heading: level {len(heading.group(1))}")
        pieces.extend(f"code: {span}" for span in _MD_INLINE_CODE.findall(line))
        pieces.extend(f"link: {target}" for target in _MD_LINK.findall(line))
    if fence is not None:  # unterminated fence: keep what was read
        pieces.append("fence-body: " + "\n".join(fenced))
    return "\n".join(pieces)


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
        canonical = _structured_canonical(text, relative)
        if canonical is not None:
            return kind, canonical
        # A `.yml` that does not parse is a template in disguise. Record the
        # fallback in the kind: a file that stops (or starts) parsing is a
        # change worth seeing, not something to absorb silently.
        return f"{TEMPLATE}(unparsed-yaml)", _template_canonical(text)
    if kind == TEMPLATE:
        return kind, _template_canonical(text)
    if kind == PROSE_KIND:
        return kind, _prose_canonical(text, relative)
    return kind, _text_canonical(text, relative)


def _mode(path: Path) -> str:
    """POSIX executable bit, the only mode bit git records and copier carries."""
    return "x" if path.stat().st_mode & 0o111 else "-"


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Correspondences
# ---------------------------------------------------------------------------


def _walk_mappings(node: Any, pointer: str) -> list[tuple[str, dict[Any, Any]]]:
    """Every mapping of a parsed document, with a positional pointer."""
    found: list[tuple[str, dict[Any, Any]]] = []
    if isinstance(node, dict):
        found.append((pointer, node))
        for key, value in node.items():
            found.extend(_walk_mappings(value, f"{pointer}/{key}"))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            found.extend(_walk_mappings(item, f"{pointer}[{index}]"))
    return found


def _parsed_documents(root: Path, relative: Path) -> list[Any] | None:
    try:
        return list(yaml.safe_load_all(stable_text(root / relative)))
    except yaml.YAMLError:
        return None


def _ansible_links(root: Path, files: list[Path]) -> list[str]:
    """`notify:` against handler names, recorded as positions instead of strings."""
    definitions: list[tuple[str, str]] = []  # (location, resolvable name)
    locations: list[str] = []
    for relative in files:
        if "handlers" not in relative.parts or classify(root, relative) != STRUCTURED:
            continue
        documents = _parsed_documents(root, relative)
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
        documents = _parsed_documents(root, relative)
        if documents is None:
            continue
        for number, document in enumerate(documents):
            for pointer, mapping in _walk_mappings(document, f"{relative.as_posix()}#{number}"):
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
        if relative.suffix != ".tpl" and not _is_chart_template(root, relative):
            continue
        text = _strip_unambiguous_comments(stable_text(root / relative))
        for rank, match in enumerate(_HELM_DEFINE.finditer(text)):
            location = f"{relative.as_posix()}#{rank}"
            resolve.setdefault(match.group(1), len(locations))
            locations.append(location)

    lines = [f"D{number} = {location}" for number, location in enumerate(locations)]
    for relative in files:
        # Comments are stripped first: a `{{/* ... */}}` block that happens to
        # mention `include "x"` in prose is not a call.
        text = _strip_unambiguous_comments(stable_text(root / relative))
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
