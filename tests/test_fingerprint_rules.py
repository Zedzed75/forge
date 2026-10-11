"""The rules the fingerprint rests on, driven directly rather than through a tree.

Comments in this module are in English: new test infrastructure, no French
precedent, and no effect on generated output.

`tests/test_fingerprint.py` proves what the fingerprint *does*: it defaces a
real generated tree and watches the digest move, or not move. That is the right
shape for the claim a translation pull request makes, and the wrong one for the
reasoning underneath it, because a tree-shaped test can only see a rule through
whatever the generator happens to emit today.

So this module tests the other half, in two flavours:

* **guards on the assumptions.** Three reductions are loose only because
  something is true of the generated trees -- no `#` comment in a chart
  template, no prose annotation in parsed YAML, no prose value emitted under a
  key outside `PROSE_KEYS`. Each of those is asserted as a fact about the
  golden trees, so the day it stops being true the judgement call is made again
  deliberately instead of going silently loose.
* **unit checks on the positional rules.** The `name` of an Ansible task and
  the `name` of a GitHub Actions step are prose; the four `name:` keys sitting
  next to them are identifiers. Those are told apart by *position*, and a
  synthetic one-file tree puts all of them in one document, which no reference
  spec does.

Split out of `tests/test_fingerprint.py` in ZED-223, where the two halves were
one 713-line module.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tests.conftest import GOLDEN_DIR, spec_files, stable_text
from tests.fingerprint import canonical_text, tree_paths
from tests.fingerprint_cases import CASES, TERRAFORM_CASE
from tests.fingerprint_kinds import (
    PROSE,
    PROSE_KIND,
    STRUCTURED,
    TEMPLATE,
    TEXT,
    classify,
    is_chart_template,
)
from tests.fingerprint_structured import PROSE_KEYS, parsed_documents, walk_mappings


# ---------------------------------------------------------------------------
# Guards on the assumptions the reductions rest on
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES)
def test_chart_templates_carry_no_full_line_hash_comment(case):
    """Justifies not stripping `#` comments from Helm templates.

    Those files do not parse as YAML, so a `#` line cannot be told apart from
    data inside a block scalar. Today the generated chart templates put all
    their commentary in `{{/* ... */}}`, so nothing is lost by leaving `#` lines
    alone. The day a template gains one, this test fails and the decision gets
    made deliberately instead of silently going loose.
    """
    root = GOLDEN_DIR / case
    offenders = []
    for relative in tree_paths(root):
        if not (relative.suffix == ".tpl" or is_chart_template(root, relative)):
            continue
        lines = stable_text(root / relative).splitlines()
        offenders.extend(
            f"{relative.as_posix()}:{number}" for number, line in enumerate(lines, 1)
            if line.strip().startswith("#")
        )
    assert not offenders, offenders


@pytest.mark.parametrize("case", CASES)
def test_annotation_mappings_in_parsed_yaml_hold_no_unknown_prose(case):
    """Justifies not normalising Kubernetes annotation values wholesale.

    The reasoning in `tests/fingerprint_structured.py` is that the only prose
    annotations reaching the parsed-YAML path are `summary` and `description`,
    already covered by the prose-key rule, while every other annotation value is
    behaviour. This test states that as a fact about the golden trees, so a new
    prose annotation forces the judgement call to be revisited.

    Only string values count. A Grafana dashboard has an `annotations: {list:
    [...]}` block of its own, unrelated to Kubernetes and not prose.

    The two names are spelled out rather than read from `PROSE_KEYS`. That set
    holds the prose keys of the whole project, including ones that exist
    nowhere near an `annotations:` mapping -- `project_description` lives in an
    Ansible `group_vars` file. Deriving the tolerated names from it would let a
    key added for some other file quietly widen this guard, which is the
    opposite of what it is for.
    """
    root = GOLDEN_DIR / case
    known = {"description", "summary"}
    unexpected: list[str] = []
    for relative in tree_paths(root):
        if classify(root, relative) != STRUCTURED:
            continue
        documents = parsed_documents(root, relative)
        if documents is None:
            continue
        for document in documents:
            for pointer, mapping in walk_mappings(document, relative.as_posix()):
                annotations = mapping.get("annotations")
                if not isinstance(annotations, dict):
                    continue
                unexpected.extend(
                    f"{pointer}/annotations/{key}"
                    for key, value in annotations.items()
                    if key not in known and isinstance(value, str)
                )
    assert not unexpected, unexpected


def test_the_prose_key_set_is_pinned():
    """Widening `PROSE_KEYS` has to be a decision, not a way to get to green.

    Every name in this set is a field the fingerprint stops looking at, so the
    set is the one place in the harness where adding a line *removes* a claim a
    reviewer would otherwise have had to examine. The cheapest way to make a
    tripped fingerprint go away is to add the key that tripped it, and nothing
    about that edit looks like a weakening of the harness when it arrives in a
    diff of translated templates.

    So the membership is stated here, where changing it is visibly a change to
    what the suite asserts. The reasoning for each name, and for the four
    `service.owner` keys deliberately left out, is next to `PROSE_KEYS` itself.
    """
    assert set(PROSE_KEYS) == {"description", "summary", "project_description"}


def _prose_values(node: object) -> set[str]:
    """Every non-empty string a spec puts under a prose key, at any depth."""
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key in PROSE_KEYS and isinstance(value, str) and value.strip():
                found.add(value)
            else:
                found |= _prose_values(value)
    elif isinstance(node, list):
        for item in node:
            found |= _prose_values(item)
    return found


def test_every_prose_alias_in_a_parsed_document_is_a_known_prose_key():
    """The audit behind `project_description`, kept honest across the trees.

    `PROSE_KEYS` matches on the key name, so a prose spec field emitted under a
    *different* name is compared verbatim until someone notices. That is the
    defect this set was widened to fix, and noticing it took a selective revert
    of nine specs. This test does the noticing instead: it takes the prose
    values out of each reference spec and looks for them in the parsed documents
    of the matching golden tree, under any key that is not a prose key.

    A hit is not necessarily a bug -- it is a place where rewording the spec
    moves a structural fingerprint. Either the key belongs in `PROSE_KEYS`, or
    the value is load-bearing there and the exception has to be argued.

    Scope: values the *spec* already calls prose, by sitting under a prose key
    at any depth -- `service.description`, `role.summary`, `alert.summary`.
    `service.owner` is not among them and is not meant to be; it is an
    identifier, and the reasoning is next to `PROSE_KEYS`.
    """
    unexpected: list[str] = []
    for path in spec_files():
        prose = _prose_values(yaml.safe_load(path.read_text(encoding="utf-8")))
        if not prose:
            continue
        root = GOLDEN_DIR / path.stem
        for relative in tree_paths(root):
            if classify(root, relative) != STRUCTURED:
                continue
            documents = parsed_documents(root, relative)
            if documents is None:
                continue
            for document in documents:
                for pointer, mapping in walk_mappings(document, relative.as_posix()):
                    unexpected.extend(
                        f"{path.stem}: {pointer}/{key}"
                        for key, value in mapping.items()
                        if isinstance(value, str)
                        and value in prose
                        and key not in PROSE_KEYS
                    )
    assert not unexpected, unexpected


def test_the_classification_covers_every_file_of_every_golden_tree():
    """No file falls through to `text` by accident because a suffix was missed."""
    seen: dict[str, set[str]] = {}
    for case in CASES:
        root = GOLDEN_DIR / case
        for relative in tree_paths(root):
            seen.setdefault(classify(root, relative), set()).add(
                relative.suffix or relative.name
            )
    assert set(seen) == {STRUCTURED, TEMPLATE, PROSE_KIND, TEXT}
    # The `text` kind is the fallback, so its membership is pinned: a new suffix
    # landing there has to be looked at rather than absorbed.
    assert seen[TEXT] == {
        ".cfg",
        ".gitattributes",
        ".gitignore",
        ".helmignore",
        ".hcl",
        ".j2",
        ".tf",
        ".tfvars",
        "Makefile",
    }


# ---------------------------------------------------------------------------
# The one normalisation applied to a `text` file
# ---------------------------------------------------------------------------


def test_a_terraform_variable_description_is_prose_but_its_default_is_not():
    """Both halves of the one normalisation applied to HCL, on the same file."""
    tree = GOLDEN_DIR / TERRAFORM_CASE
    relative = Path("terraform/environments/dev/variables.tf")
    _, canonical = canonical_text(tree, relative)
    assert f'description = "{PROSE}"' in canonical
    assert "description = " in canonical  # the argument itself is still compared
    assert '"~/.kube/config"' in canonical  # a default value is untouched


# ---------------------------------------------------------------------------
# The positional `name` rules, on synthetic documents
# ---------------------------------------------------------------------------


def test_a_yaml_file_that_stops_parsing_is_reported_as_such(tmp_path):
    """The structured/template fallback is recorded, never silently absorbed."""
    tree = tmp_path / "tree"
    tree.mkdir()
    path = tree / "thing.yml"
    path.write_text("key: value\n", encoding="utf-8")
    assert canonical_text(tree, Path("thing.yml"))[0] == STRUCTURED

    path.write_text("key: value\n  bad: indentation\n", encoding="utf-8")
    kind, _ = canonical_text(tree, Path("thing.yml"))
    assert kind == f"{TEMPLATE}(unparsed-yaml)"


def test_an_ansible_task_name_is_normalised_but_a_manifest_name_is_not(tmp_path):
    """Unit check on the positional rule, away from any generated tree."""
    tree = tmp_path / "tree"
    (tree / "roles" / "x" / "tasks").mkdir(parents=True)
    (tree / "roles" / "x" / "tasks" / "main.yml").write_text(
        "---\n"
        "- name: Install the package\n"
        "  ansible.builtin.package:\n"
        "    name: nginx\n"
        "  block: []\n",
        encoding="utf-8",
    )
    _, canonical = canonical_text(tree, Path("roles/x/tasks/main.yml"))
    structure = yaml.safe_load(canonical)[0][0]
    assert structure["name"] == PROSE
    assert structure["ansible.builtin.package"]["name"] == "nginx"

    # The same document outside a tasks/ directory keeps its `name`.
    (tree / "elsewhere.yml").write_text(
        "---\n- name: Install the package\n  ansible.builtin.package:\n    name: nginx\n",
        encoding="utf-8",
    )
    _, canonical = canonical_text(tree, Path("elsewhere.yml"))
    assert yaml.safe_load(canonical)[0][0]["name"] == "Install the package"


#: A workflow carrying all four `name:` keys the positional rule has to tell
#: apart: the workflow's own, a job's, a step's, and an action argument's.
_WORKFLOW = """---
name: Integration
on: [push]
jobs:
  check:
    name: Check the repository
    steps:
      - name: Check out the repository
        uses: actions/checkout@v4
      - name: Publish the report
        uses: actions/upload-artifact@v4
        with:
          name: report
"""


def _workflow_structure(tree: Path, relative: str) -> dict:
    path = tree / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_WORKFLOW, encoding="utf-8", newline="\n")
    _, canonical = canonical_text(tree, Path(relative))
    return yaml.safe_load(canonical)[0]


def test_a_github_actions_step_name_is_normalised_but_its_neighbours_are_not(tmp_path):
    """Unit check on the positional rule, away from any generated tree.

    One document, four `name:` keys, one of them prose. The rule is positional
    and not "a key called `name` under `.github/`" precisely so the other three
    survive: a file elsewhere in `.github/` -- `dependabot.yml`, an issue
    template -- would otherwise be normalised too, and there a `name` is an
    identifier again.
    """
    tree = tmp_path / "tree"
    tree.mkdir()

    structure = _workflow_structure(tree, ".github/workflows/ci.yml")
    job = structure["jobs"]["check"]
    assert job["steps"][0]["name"] == PROSE
    assert job["steps"][1]["name"] == PROSE
    # The three neighbours, all identifiers, all compared verbatim.
    assert structure["name"] == "Integration"
    assert job["name"] == "Check the repository"
    assert job["steps"][1]["with"]["name"] == "report"

    # Same bytes, one directory away: nothing is normalised at all.
    elsewhere = _workflow_structure(tree, ".github/dependabot.yml")
    assert elsewhere["jobs"]["check"]["steps"][0]["name"] == "Check out the repository"

    # And a workflow-shaped file in a subdirectory of `.github/workflows/`,
    # which GitHub does not read either.
    nested = _workflow_structure(tree, ".github/workflows/parked/ci.yml")
    assert nested["jobs"]["check"]["steps"][0]["name"] == "Check out the repository"
