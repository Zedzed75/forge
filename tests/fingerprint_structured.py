"""The `structured` reduction: YAML and JSON documents that parse.

One of the two halves of "what counts as structure, and what counts as prose",
split out of `tests/fingerprint.py` (ZED-223); the other is
`tests/fingerprint_textual.py`. The contract both of them serve -- what the
fingerprint promises a reviewer, and why every judgement call here is resolved
towards strictness -- is in the docstring of `tests/fingerprint.py`. Read that
first: *normalising away a field that carries real meaning* is the one failure
mode this harness must not have, and this module is where that risk lives.

The kind covers every data document of a generated tree: `forge.yml`,
`values.yaml`, Prometheus rules, Ansible tasks, `.copier-answers.yml`,
`.ansible-lint`... The parsed structure is compared, so every comment
disappears for free and no comment-stripping heuristic can get it wrong. On top
of that:

* a mapping key named `description`, `summary` or `project_description` has its
  string value replaced by a constant. In this project those keys are prose
  everywhere they occur: `service.description`, `Chart.yaml`, Ansible
  `galaxy_info`, Terraform-facing answers, and the `annotations` of every
  Prometheus alert. Nothing reads them.

  `project_description` is in that set because it is an *alias*: the Ansible
  `group_vars/all.yml` carries the `service.description` value under that name,
  and nothing else ever uses the key. Leaving it out made one and the same
  prose string normalised away in `forge.yml` under `description` and compared
  verbatim one file away under `project_description`, so a service description
  reworded in the spec moved the fingerprint of exactly one file of one tree
  and read as a structural regression. The audit behind this is in `PROSE_KEYS`
  below, together with the keys deliberately left out.
* an Ansible task `name` is replaced by a constant -- but only at task
  positions, never as a generic key. `name` is load-bearing almost everywhere
  else: `metadata.name` in a manifest, `name:` as an argument to
  `ansible.builtin.user` or a container port. So a `name` is normalised only
  when it is the name of a play, of a task, or of a handler, recognised by
  *position*: the items of the top-level sequence of a file under `tasks/` or
  `handlers/`, the items of a playbook's `tasks`/`pre_tasks`/`post_tasks`/
  `handlers`, and recursively the items of `block`, `rescue` and `always`.
* a GitHub Actions step label -- `jobs.<id>.steps[].name` in a file sitting
  directly in `.github/workflows/` -- is replaced by a constant, for the same
  reason and under the same discipline: it is recognised by *position*, never
  as a key called `name` somewhere under `.github/`. A step label is pure
  display text; nothing in a workflow can reference a step by it, since
  `steps.<id>.outputs` and `needs:` go through the step `id:` and the job key.
  Rewording a label therefore cannot change what the workflow runs. The two
  `name:` keys standing right next to it are left verbatim, and are
  load-bearing: `jobs.<id>.name` is the check name a branch-protection rule
  matches a required status check against, and the workflow-level `name:` is
  what `github.workflow`, a `workflow_run` trigger and a README badge URL refer
  to.

  GitLab CI deliberately gets nothing equivalent, because it has nothing
  equivalent. A `.gitlab-ci.yml` has no display-label key at all: a job *is*
  its top-level mapping key, and `stage:`, `needs:` and `extends:` reference
  jobs by that key. The closest thing to a label is the key itself, an
  identifier that must stay verbatim. Translating a GitLab pipeline touches its
  comments and nothing else, so there is nothing to loosen -- the absence is
  the decision, not an oversight.
* an Ansible `notify:` or handler `listen:` value is replaced by a constant
  too. It is not data: it is the handler name repeated, so leaving it verbatim
  would make a *correctly* translated handler pair trip the fingerprint and the
  whole check would be useless on exactly the files it was written for. The
  reference itself is not lost -- it moves to `ansible_handler_links` in
  `tests/fingerprint.py`, where it is compared by position, which is what
  catches the half-translated case.
* Kubernetes `annotations` are **not** normalised wholesale, despite being the
  obvious candidate. Annotation values are frequently behaviour:
  `nginx.ingress.kubernetes.io/rewrite-target`, `cert-manager.io/cluster-issuer`,
  `checksum/config`. Blanket-normalising them would hide exactly the kind of
  change this harness exists to catch. In this project's parseable YAML the only
  prose annotations are `summary` and `description`, which the key rule above
  already covers; the `annotations:` mappings of the Helm chart are Go-template
  text and never reach this path. `tests/test_fingerprint_rules.py` guards that
  statement, so the decision gets revisited if a new prose annotation appears
  rather than rotting silently.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from tests.conftest import stable_text
from tests.fingerprint_kinds import PROSE

#: Mapping keys whose value is prose everywhere in this project's YAML.
#:
#: The set is keyed on the key *name*, not on where the value came from, so an
#: alias -- a prose spec field emitted under a different key -- has to be listed
#: explicitly or it is compared verbatim. Every template emitting a prose field
#: into parseable YAML was audited for that; `project_description` in
#: `ansible/group_vars/all.yml` is the only alias, and it is here. The others
#: all emit under `description` or `summary` already (`Chart.yaml`, Ansible role
#: `meta/main.yml` from `role.summary`, Prometheus alert annotations from
#: `alert.summary`, `forge.yml` and the `.copier-answers.yml`), or land in a
#: comment, which parsing drops anyway, or in a `.md`, which is the `prose` kind.
#:
#: Deliberately **not** here: `owner`, `galaxy_info.author`, `maintainers[].name`
#: and `maintainer_name`, the four keys carrying `service.owner`. Adding them
#: would make the fingerprint blind to a change of owner, and a change of owner
#: is a real change to a structured document -- an identifier a person looks up,
#: not a sentence a reader skims. When renaming the owner of the nine reference
#: specs moved 31 fingerprint entries, the guard was right and the entries were
#: reviewed; the alternative was to buy that quiet at the price of never seeing
#: it again. `test_the_prose_key_set_is_pinned` keeps this a decision.
PROSE_KEYS = frozenset({"description", "summary", "project_description"})

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


# ---------------------------------------------------------------------------
# Where a document sits, and what that says about its keys
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


# ---------------------------------------------------------------------------
# The normalisations
# ---------------------------------------------------------------------------


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
                # position -- see the docstring of `tests/fingerprint.py`.
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


# ---------------------------------------------------------------------------
# Canonical form
# ---------------------------------------------------------------------------


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


def structured_canonical(text: str, relative: Path) -> str | None:
    """Canonical form of a data document, or None when it does not parse."""
    try:
        documents = list(yaml.safe_load_all(text))
    except yaml.YAMLError:
        return None
    position = _document_position(relative)
    normalised = [_normalise_document(document, position) for document in documents]
    return json.dumps(_plain(normalised), indent=2, sort_keys=True, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Reading a document for something other than its digest
# ---------------------------------------------------------------------------
# The correspondences in `tests/fingerprint.py` need the parsed document
# itself, un-normalised: a `notify:` has to be read before it is replaced.


def parsed_documents(root: Path, relative: Path) -> list[Any] | None:
    try:
        return list(yaml.safe_load_all(stable_text(root / relative)))
    except yaml.YAMLError:
        return None


def walk_mappings(node: Any, pointer: str) -> list[tuple[str, dict[Any, Any]]]:
    """Every mapping of a parsed document, with a positional pointer."""
    found: list[tuple[str, dict[Any, Any]]] = []
    if isinstance(node, dict):
        found.append((pointer, node))
        for key, value in node.items():
            found.extend(walk_mappings(value, f"{pointer}/{key}"))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            found.extend(walk_mappings(item, f"{pointer}[{index}]"))
    return found
