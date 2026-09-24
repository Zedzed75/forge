"""The semantic-equivalence harness, and the proof that it does what it claims.

Comments in this module are in English: new test infrastructure, no French
precedent, and no effect on generated output.

Two things are tested here, and the second matters as much as the first:

1. every golden tree still has the structural fingerprint stored for it, which
   is what lets a translation pull request prove in CI that it changed prose and
   nothing else;
2. the fingerprint is actually blind to prose and actually sensitive to
   structure. A harness that never fails is indistinguishable from a harness
   that works, so the sensitivity half is asserted explicitly -- notably the
   `notify:` / handler-name correspondence, the one silent breakage a
   translation can introduce that no validator would catch.

Re-blessing the stored fingerprints, after a change whose structural effect has
been reviewed and is intended:

    uv run pytest tests/test_fingerprint.py --regen-fingerprints

Reading the canonical form of one file, to find out *why* a fingerprint moved:

    python -m tests.fingerprint tests/golden/deux-domaines ansible/roles/common/tasks/main.yml
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from tests import fingerprint as fp
from tests.conftest import GOLDEN_DIR, render_all_plugins, spec_files, stable_text

#: One case per reference spec, as in the golden harness.
CASES = [path.stem for path in spec_files()]

#: Tree used by the sensitivity tests: the only reference case carrying both an
#: Ansible project (handlers and `notify:`) and a Helm chart (helpers).
MIXED_CASE = "deux-domaines"

#: Files of `MIXED_CASE` the sensitivity tests edit.
HANDLERS = "ansible/roles/postgresql/handlers/main.yml"
TASKS = "ansible/roles/postgresql/tasks/main.yml"
RULES = "ansible/roles/firewall/tasks/ufw.yml"
CHART_TEMPLATE = "helm/charts/boutique/templates/deployment-api.yaml"


# ---------------------------------------------------------------------------
# Stored references
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def rendered_trees(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Every reference spec rendered once: a copier run costs a few seconds."""
    root = tmp_path_factory.mktemp("empreintes")
    trees = {}
    for path in spec_files():
        trees[path.stem] = render_all_plugins(path, root / path.stem)
    return trees


@pytest.mark.parametrize("case", CASES)
def test_the_fingerprint_of_a_fresh_render_matches_the_stored_one(
    case, rendered_trees, regen_fingerprints
):
    """The claim a translation pull request has to make, checked in CI.

    Computed from a fresh render rather than from `tests/golden/`: the point is
    to compare what the generator produces *now* against a reference that was
    reviewed once, without depending on the golden trees being right.
    """
    obtained = fp.fingerprint(rendered_trees[case])

    if regen_fingerprints:
        fp.store(case, obtained)
        pytest.skip(f"fingerprint re-blessed: {case}")

    assert fp.stored_path(case).is_file(), (
        f"no stored fingerprint for {case}: run pytest --regen-fingerprints once "
        "the structural change has been reviewed."
    )
    report = fp.differences(fp.load(case), obtained)
    assert not report, "structure moved:\n  " + "\n  ".join(report)


def test_every_reference_spec_has_a_stored_fingerprint():
    """A domain added without its fingerprint must fail the suite, not pass it."""
    stored = sorted(path.stem for path in fp.FINGERPRINTS_DIR.glob("*.json"))
    assert stored == sorted(CASES)


@pytest.mark.parametrize("case", CASES)
def test_the_golden_tree_carries_the_stored_fingerprint(case):
    """Cheap counterpart of the render-based test: no copier, immediate feedback.

    `tests/test_golden.py` already proves that a fresh render equals the golden
    tree byte for byte, so the two fingerprints have to agree. When they do not,
    this test fails in a second instead of a minute.
    """
    report = fp.differences(fp.load(case), fp.fingerprint(GOLDEN_DIR / case))
    assert not report, "structure moved:\n  " + "\n  ".join(report)


@pytest.mark.parametrize("case", CASES)
def test_every_reference_resolves_in_every_golden_tree(case):
    """No dangling `notify:` and no dangling `include` anywhere, today."""
    data = fp.fingerprint(GOLDEN_DIR / case)
    dangling = [
        line
        for section in ("ansible_handler_links", "helm_helper_links")
        for line in data[section]
        if "UNRESOLVED" in line
    ]
    assert not dangling, "\n".join(dangling)


# ---------------------------------------------------------------------------
# Blind to prose
# ---------------------------------------------------------------------------


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """Writable copy of a golden tree, for the sensitivity tests to deface."""
    target = tmp_path / MIXED_CASE
    shutil.copytree(GOLDEN_DIR / MIXED_CASE, target)
    return target


def _edit(tree: Path, relative: str, before: str, after: str, *, count: int = 0) -> None:
    """Replace text in a generated file, failing loudly if it was not there."""
    path = tree / relative
    text = path.read_text(encoding="utf-8")
    assert before in text, f"{relative} no longer contains {before!r}: fix the test"
    path.write_text(
        text.replace(before, after) if count == 0 else text.replace(before, after, count),
        encoding="utf-8",
        newline="\n",
    )


def _unchanged(tree: Path, reference: dict) -> None:
    report = fp.differences(reference, fp.fingerprint(tree))
    assert not report, "the fingerprint should not have moved:\n  " + "\n  ".join(report)


def _changed(tree: Path, reference: dict) -> list[str]:
    report = fp.differences(reference, fp.fingerprint(tree))
    assert report, "the fingerprint should have moved, and did not"
    return report


def test_a_comment_only_edit_leaves_the_fingerprint_untouched(tree):
    """The heart of the harness: comments in five different syntaxes.

    One file per comment form the generated projects use, because each form goes
    through a different branch: a YAML comment disappears through the parser, a
    Go-template comment and a Jinja comment through the unambiguous-comment
    pass, a `#` line of an HCL or Makefile file through the line filter.
    """
    reference = fp.fingerprint(tree)

    _edit(tree, HANDLERS, "# roles/postgresql/handlers/main.yml", "# whatever, in English")
    _edit(
        tree,
        CHART_TEMPLATE,
        "===============================================================================",
        "=== a Go-template comment nobody reads ===",
        count=1,
    )
    _edit(
        tree,
        "ansible/roles/ssh_hardening/templates/hardening.conf.j2",
        "# Port d'écoute du serveur.",
        "# Listening port of the server.",
    )
    _edit(tree, "ansible/ansible.cfg", "# ansible.cfg", "# the Ansible configuration")

    _unchanged(tree, reference)


def test_an_added_comment_line_leaves_the_fingerprint_untouched(tree):
    """Translating often *adds* lines, it does not only replace them."""
    reference = fp.fingerprint(tree)
    for relative, marker in ((HANDLERS, "---\n"), ("ansible/ansible.cfg", "[defaults]")):
        path = tree / relative
        text = path.read_text(encoding="utf-8")
        assert marker in text
        path.write_text(
            text.replace(marker, f"# one more comment line\n{marker}", 1),
            encoding="utf-8",
            newline="\n",
        )
    _unchanged(tree, reference)


def test_a_prose_field_edit_leaves_the_fingerprint_untouched(tree):
    """`description`, `summary`, and an Ansible task name, in their own files."""
    reference = fp.fingerprint(tree)

    _edit(tree, "forge.yml", "description: Boutique", "description: Online shop")
    _edit(
        tree,
        "helm/charts/boutique/Chart.yaml",
        "description: Boutique",
        "description: Online shop",
    )
    _edit(
        tree,
        "ansible/roles/postgresql/meta/main.yml",
        "description: 'Serveur PostgreSQL",
        "description: 'PostgreSQL server",
    )
    # An Ansible task name with no handler behind it: pure prose.
    _edit(
        tree,
        TASKS,
        "- name: Installer PostgreSQL et ses dépendances",
        "- name: Install PostgreSQL and its dependencies",
    )
    _unchanged(tree, reference)


def test_a_handler_and_its_notify_translated_together_keep_the_fingerprint(tree):
    """The whole point of recording positions instead of names.

    A handler renamed on both sides is a prose change: the task still notifies
    the same handler. The fingerprint must see nothing.
    """
    reference = fp.fingerprint(tree)
    _edit(tree, HANDLERS, "- name: Recharger PostgreSQL", "- name: Reload PostgreSQL")
    _edit(tree, TASKS, "notify: Recharger PostgreSQL", "notify: Reload PostgreSQL")
    _unchanged(tree, reference)


# ---------------------------------------------------------------------------
# Sensitive to structure
# ---------------------------------------------------------------------------


def test_a_handler_translated_without_its_notify_breaks_the_fingerprint(tree):
    """The silent breakage this harness exists to catch.

    Ansible matches `notify:` to a handler by name string. Rename the handler
    and forget the `notify:`, and the handler simply never runs again -- no
    error, no warning, `ansible-lint` unbothered. The fingerprint has to say so,
    and it has to say so in the correspondence section, not merely as "some file
    changed".
    """
    reference = fp.fingerprint(tree)
    _edit(tree, HANDLERS, "- name: Recharger PostgreSQL", "- name: Reload PostgreSQL")

    report = _changed(tree, reference)
    assert any("UNRESOLVED" in line for line in report), report
    assert any("ansible_handler_links" in line for line in report), report


def test_a_notify_translated_without_its_handler_breaks_the_fingerprint(tree):
    """The same breakage from the other side."""
    reference = fp.fingerprint(tree)
    _edit(tree, RULES, "notify: Recharger le pare-feu", "notify: Reload the firewall")

    report = _changed(tree, reference)
    assert any("UNRESOLVED" in line for line in report), report


def test_two_handlers_swapped_break_only_the_correspondence(tree):
    """The clearest demonstration that positions, not names, are what is compared.

    Swapping the names of the two PostgreSQL handlers leaves the file's digest
    *identical* -- both names are prose, and everything around them is where it
    was. What moves is the correspondence: the task that asked for a reload now
    resolves to the handler that restarts. Nothing but this section could see it.
    """
    reference = fp.fingerprint(tree)
    _edit(tree, HANDLERS, "- name: Recharger PostgreSQL", "- name: PLACEHOLDER")
    _edit(tree, HANDLERS, "- name: Redémarrer PostgreSQL", "- name: Recharger PostgreSQL")
    _edit(tree, HANDLERS, "- name: PLACEHOLDER", "- name: Redémarrer PostgreSQL")

    report = _changed(tree, reference)
    assert all("ansible_handler_links" in line for line in report), report
    assert not any("UNRESOLVED" in line for line in report), report


def test_a_load_bearing_name_is_not_normalised(tree):
    """`name` as a module argument is behaviour, and must never be forgotten.

    This is the failure mode a loose prose list would produce: normalising every
    `name:` would also normalise the service a handler restarts.
    """
    reference = fp.fingerprint(tree)
    _edit(tree, HANDLERS, 'name: "{{ postgresql_service }}"', 'name: "postgres-elsewhere"')
    _changed(tree, reference)


def test_a_kubernetes_annotation_value_is_not_normalised(tree):
    """Annotation values are behaviour, not prose, and are compared verbatim."""
    reference = fp.fingerprint(tree)
    _edit(
        tree,
        "helm/charts/boutique/templates/ingress-api.yaml",
        "cert-manager.io/cluster-issuer",
        "cert-manager.io/cluster-issuer-typo",
    )
    _changed(tree, reference)


def test_a_dangling_helm_include_breaks_the_fingerprint(tree):
    """Helm helper names and `_helpers.tpl` definitions must stay in correspondence."""
    reference = fp.fingerprint(tree)
    _edit(
        tree,
        CHART_TEMPLATE,
        'include "boutique.api.labels"',
        'include "boutique.api.etiquettes"',
    )
    report = _changed(tree, reference)
    assert any("UNRESOLVED" in line and "helm_helper_links" in line for line in report), report


def test_a_renamed_helper_and_its_calls_break_the_fingerprint(tree):
    """Renaming a helper everywhere keeps the links, and still moves the digests.

    A helper name is an identifier, not prose: unlike a handler name, it is
    compared verbatim as well. Renaming it consistently is therefore visible --
    correctly so, because a reviewer has to see an identifier change.
    """
    reference = fp.fingerprint(tree)
    for relative in fp.tree_paths(tree):
        path = tree / relative
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:  # pragma: no cover
            continue
        if "boutique.api.labels" in text:
            path.write_text(
                text.replace("boutique.api.labels", "boutique.api.etiquettes"),
                encoding="utf-8",
                newline="\n",
            )
    report = _changed(tree, reference)
    assert not any("UNRESOLVED" in line for line in report), report


def test_a_value_change_breaks_the_fingerprint(tree):
    """The ordinary case: a real value moved in a parsed document."""
    reference = fp.fingerprint(tree)
    _edit(tree, "helm/charts/boutique/values.yaml", "replicaCount: 1", "replicaCount: 99")
    _changed(tree, reference)


def test_an_added_and_a_removed_file_are_both_reported(tree):
    reference = fp.fingerprint(tree)
    (tree / "ansible" / "extra.yml").write_text("---\nkey: value\n", encoding="utf-8")
    (tree / HANDLERS).unlink()
    report = _changed(tree, reference)
    assert any(line.startswith("added: ansible/extra.yml") for line in report), report
    assert any(line.startswith(f"removed: {HANDLERS}") for line in report), report


def test_a_terraform_variable_description_is_prose_but_its_default_is_not():
    """Both halves of the one normalisation applied to HCL, on the same file."""
    tree = GOLDEN_DIR / "terraform-complet"
    relative = Path("terraform/environments/dev/variables.tf")
    _, canonical = fp.canonical_text(tree, relative)
    assert f'description = "{fp.PROSE}"' in canonical
    assert "description = " in canonical  # the argument itself is still compared
    assert '"~/.kube/config"' in canonical  # a default value is untouched


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
    for relative in fp.tree_paths(root):
        if not (relative.suffix == ".tpl" or fp._is_chart_template(root, relative)):
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

    The reasoning in `tests/fingerprint.py` is that the only prose annotations
    reaching the parsed-YAML path are `summary` and `description`, already
    covered by the prose-key rule, while every other annotation value is
    behaviour. This test states that as a fact about the golden trees, so a new
    prose annotation forces the judgement call to be revisited.

    Only string values count. A Grafana dashboard has an `annotations: {list:
    [...]}` block of its own, unrelated to Kubernetes and not prose.
    """
    root = GOLDEN_DIR / case
    known = set(fp.PROSE_KEYS)
    unexpected: list[str] = []
    for relative in fp.tree_paths(root):
        if fp.classify(root, relative) != fp.STRUCTURED:
            continue
        documents = fp._parsed_documents(root, relative)
        if documents is None:
            continue
        for document in documents:
            for pointer, mapping in fp._walk_mappings(document, relative.as_posix()):
                annotations = mapping.get("annotations")
                if not isinstance(annotations, dict):
                    continue
                unexpected.extend(
                    f"{pointer}/annotations/{key}"
                    for key, value in annotations.items()
                    if key not in known and isinstance(value, str)
                )
    assert not unexpected, unexpected


def test_the_classification_covers_every_file_of_every_golden_tree():
    """No file falls through to `text` by accident because a suffix was missed."""
    seen: dict[str, set[str]] = {}
    for case in CASES:
        root = GOLDEN_DIR / case
        for relative in fp.tree_paths(root):
            seen.setdefault(fp.classify(root, relative), set()).add(
                relative.suffix or relative.name
            )
    assert set(seen) == {fp.STRUCTURED, fp.TEMPLATE, fp.PROSE_KIND, fp.TEXT}
    # The `text` kind is the fallback, so its membership is pinned: a new suffix
    # landing there has to be looked at rather than absorbed.
    assert seen[fp.TEXT] == {
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


def test_a_yaml_file_that_stops_parsing_is_reported_as_such(tmp_path):
    """The structured/template fallback is recorded, never silently absorbed."""
    tree = tmp_path / "tree"
    tree.mkdir()
    path = tree / "thing.yml"
    path.write_text("key: value\n", encoding="utf-8")
    assert fp.canonical_text(tree, Path("thing.yml"))[0] == fp.STRUCTURED

    path.write_text("key: value\n  bad: indentation\n", encoding="utf-8")
    kind, _ = fp.canonical_text(tree, Path("thing.yml"))
    assert kind == f"{fp.TEMPLATE}(unparsed-yaml)"


def test_an_ansible_task_name_is_normalised_but_a_manifest_name_is_not(tmp_path):
    """Unit check on the positional rule, away from any generated tree."""
    tree = tmp_path / "tree"
    (tree / "roles" / "x" / "tasks").mkdir(parents=True)
    (tree / "roles" / "x" / "tasks" / "main.yml").write_text(
        "---\n"
        "- name: Installer le paquet\n"
        "  ansible.builtin.package:\n"
        "    name: nginx\n"
        "  block: []\n",
        encoding="utf-8",
    )
    _, canonical = fp.canonical_text(tree, Path("roles/x/tasks/main.yml"))
    structure = yaml.safe_load(canonical)[0][0]
    assert structure["name"] == fp.PROSE
    assert structure["ansible.builtin.package"]["name"] == "nginx"

    # The same document outside a tasks/ directory keeps its `name`.
    (tree / "elsewhere.yml").write_text(
        "---\n- name: Installer le paquet\n  ansible.builtin.package:\n    name: nginx\n",
        encoding="utf-8",
    )
    _, canonical = fp.canonical_text(tree, Path("elsewhere.yml"))
    assert yaml.safe_load(canonical)[0][0]["name"] == "Installer le paquet"
