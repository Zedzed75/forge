"""Rendering tests: normalisation, repository-level files, comparison."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from forge.errors import RenderError
from forge.plugins_api.types import DomainInfo
from forge.render import scaffold
from forge.render import copier_runner
from forge.render.copier_runner import (
    ANSWERS_FILENAME,
    DEFAULT_REF,
    PACKAGE_RELPATH,
    normalise_text,
    normalise_tree,
    package_root,
    repository_root,
    resolve_subdir,
    rewrite_src_path,
    run_update,
    template_ref,
    template_root,
)
from forge.render.diff import diff_trees

# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("a\r\nb\r\n", "a\nb\n"),
        ("a\rb", "a\nb\n"),
        ("a", "a\n"),
        ("a\n\n\n", "a\n"),
        ("", ""),
    ],
)
def test_normalise_text_converts_line_endings_and_ends_with_one_newline(raw, expected):
    assert normalise_text(raw) == expected


@pytest.mark.parametrize(
    "content",
    [
        "conf: |\n  trailing = ok   \n  other\n",   # meaningful trailing spaces
        "desc: 'para1\n\n\n  para2'\n",             # blank line = literal newline
        "block: |\n  a\n\n\n  b\n",                 # blank lines inside a block
    ],
)
def test_normalise_text_does_not_touch_the_content(content):
    """Normalisation must change nothing but the line endings.

    The per-line rstrip and the collapsing of blank lines, inherited from the
    legacy tools, modified the VALUE of YAML scalars: in a quoted scalar a blank
    line encodes a newline, and in a `|` block the trailing spaces are part of
    the data.
    """
    assert normalise_text(content) == content


def test_normalise_text_preserves_the_reparsed_yaml_value():
    """End-to-end check: what YAML reads back must not change."""
    content = "note: 'para1\n\n\n  para2'\n"
    assert yaml.safe_load(normalise_text(content)) == yaml.safe_load(content)


def test_normalise_tree_spares_the_answers_file(tmp_path):
    (tmp_path / ".copier-answers.yml").write_bytes(b"a\r\nb\r\n")
    (tmp_path / "file.yml").write_bytes(b"a\r\nb\r\n")
    assert normalise_tree(tmp_path) == 1
    assert (tmp_path / ".copier-answers.yml").read_bytes() == b"a\r\nb\r\n"
    assert (tmp_path / "file.yml").read_bytes() == b"a\nb\n"


def test_normalise_tree_really_converts_crlf(tmp_path):
    """Trap avoided: `read_text` already translates CRLF, the read must be binary."""
    target = tmp_path / "file.txt"
    target.write_bytes(b"line 1\r\nline 2\r\n")
    assert normalise_tree(tmp_path) == 1
    assert b"\r" not in target.read_bytes()


def test_normalise_tree_leaves_an_already_clean_file_alone(tmp_path):
    (tmp_path / "file.yml").write_bytes(b"key: value   \n\n\nother: 1\n")
    assert normalise_tree(tmp_path) == 0


def test_normalise_tree_ignores_a_binary_file(tmp_path):
    (tmp_path / "image.bin").write_bytes(b"\x00\x01\x02\xff")
    assert normalise_tree(tmp_path) == 0
    assert (tmp_path / "image.bin").read_bytes() == b"\x00\x01\x02\xff"


# ---------------------------------------------------------------------------
# Template root
# ---------------------------------------------------------------------------


def test_the_template_root_carries_the_copier_yml():
    assert (template_root() / "copier.yml").is_file()


def test_a_forced_root_without_copier_yml_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_TEMPLATE_SRC", str(tmp_path))
    with pytest.raises(RenderError, match="copier.yml"):
        template_root()


def test_the_package_sits_where_this_prefix_says():
    """`PACKAGE_RELPATH` is the hinge between the two root shapes; it must be true.

    If it ever stops describing the layout, `resolve_subdir` silently stops
    shortening anything and an installed forge is broken again -- with no other
    test able to notice, since a checkout never needs the shortened form.
    """
    assert repository_root() / PACKAGE_RELPATH == package_root()
    assert (repository_root() / "copier.yml").is_file()
    assert (repository_root() / "partials" / "header.jinja").is_file()


def test_the_repository_root_wins_over_the_package(monkeypatch):
    """From a checkout the root must stay the repository, not the package.

    Preferring the package would cost every checkout user `copier update` and the
    `_commit` line in their projects, because only a git repository root is a
    versioned template to copier (DESIGN.md §8 Q2-bis).
    """
    monkeypatch.delenv("FORGE_TEMPLATE_SRC", raising=False)
    assert template_root() == repository_root()
    assert template_root() != package_root()


def test_a_root_without_a_repository_above_it_falls_back_to_the_package(
    tmp_path, monkeypatch
):
    """The installed case: `site-packages/forge` is the root, and it carries the template.

    Simulated with the two layouts side by side -- a "repository" with no
    copier.yml, a "package" with one -- which is what a wheel install looks like
    from `template_root()`'s point of view. That the wheel really carries the file
    is asserted separately, against a built wheel, in
    `test_cli.py::test_the_wheel_ships_the_whole_template_root`.
    """
    monkeypatch.delenv("FORGE_TEMPLATE_SRC", raising=False)
    site_packages = tmp_path / "site-packages" / "forge"
    site_packages.mkdir(parents=True)
    (site_packages / "copier.yml").write_text("", encoding="utf-8")
    monkeypatch.setattr(copier_runner, "repository_root", lambda: tmp_path / "no-repo")
    monkeypatch.setattr(copier_runner, "package_root", lambda: site_packages)

    assert template_root() == site_packages


def test_no_root_at_all_names_both_places_it_looked(monkeypatch):
    monkeypatch.delenv("FORGE_TEMPLATE_SRC", raising=False)
    monkeypatch.setattr(copier_runner, "repository_root", lambda: Path("/nowhere"))
    monkeypatch.setattr(copier_runner, "package_root", lambda: Path("/nowhere-either"))
    with pytest.raises(RenderError, match="nowhere-either"):
        template_root()


# ---------------------------------------------------------------------------
# Resolving a plugin's template against the root in use
# ---------------------------------------------------------------------------


def test_a_repository_root_keeps_the_declared_subdir(tmp_path):
    declared = f"{PACKAGE_RELPATH}/plugins/demo/template"
    (tmp_path / declared).mkdir(parents=True)
    assert resolve_subdir(tmp_path, declared) == declared


def test_a_package_root_drops_the_repository_prefix(tmp_path):
    """The installed shape: the package *is* what `src/forge/` became."""
    (tmp_path / "plugins" / "demo" / "template").mkdir(parents=True)
    assert (
        resolve_subdir(tmp_path, f"{PACKAGE_RELPATH}/plugins/demo/template")
        == "plugins/demo/template"
    )


def test_a_subdir_that_exists_nowhere_is_refused_with_both_forms(tmp_path):
    """Failing loudly beats handing copier a path that is not there."""
    with pytest.raises(RenderError, match="plugins/demo/template"):
        resolve_subdir(tmp_path, f"{PACKAGE_RELPATH}/plugins/demo/template")


# ---------------------------------------------------------------------------
# Template reference
# ---------------------------------------------------------------------------


def test_an_unversioned_root_has_no_reference(tmp_path):
    """copier would ignore `vcs_ref` in silence: forge says so by returning None."""
    assert template_ref(tmp_path) is None


def test_a_repository_root_keeps_its_reference(tmp_path):
    """Only the EXACT root of a repository is a versioned template to copier."""
    (tmp_path / ".git").mkdir()
    assert template_ref(tmp_path) == DEFAULT_REF
    assert template_ref(tmp_path, "v1.2.3") == "v1.2.3"
    # A subdirectory of that same work tree is not one -- which is why the package
    # directory cannot be the root in a checkout without losing `update`.
    inner = tmp_path / PACKAGE_RELPATH
    inner.mkdir(parents=True)
    assert template_ref(inner) is None


def test_the_checkout_keeps_its_reference():
    """The AC that matters: a checkout renders exactly as it did before."""
    assert template_ref(template_root()) == DEFAULT_REF


def test_update_refuses_an_unversioned_root(tmp_path):
    """The message has to name the TEMPLATE root, not the target project.

    This is the situation of every installed forge: `site-packages/forge` is the
    root of no repository, so `copier update` is impossible there.
    """
    target = tmp_path / "project"
    target.mkdir()
    (target / ANSWERS_FILENAME).write_text("_src_path: x\n", encoding="utf-8")

    with pytest.raises(RenderError, match="is not the root of a git repository"):
        run_update(dst=target, src=tmp_path / "template-without-git")


def test_rewrite_src_path_unties_the_project_from_its_original_machine(tmp_path):
    answers = tmp_path / ".copier-answers.yml"
    answers.write_text(
        "_commit: v1\n_src_path: C:\\elsewhere\\forge\ndomain: {}\n", encoding="utf-8"
    )
    rewrite_src_path(answers, Path("/new/root"))
    content = answers.read_text(encoding="utf-8")
    assert "_src_path: /new/root" in content
    assert "_commit: v1" in content


def test_rewrite_src_path_touches_nothing_if_the_root_is_already_right(tmp_path):
    """Rewriting an equivalent value would dirty the target, and copier refuses a dirty repository."""
    answers = tmp_path / ".copier-answers.yml"
    original = f"_src_path: {tmp_path}\n"
    answers.write_text(original, encoding="utf-8")
    rewrite_src_path(answers, tmp_path)
    assert answers.read_text(encoding="utf-8") == original


def test_rewrite_src_path_ignores_a_missing_file(tmp_path):
    rewrite_src_path(tmp_path / "absent.yml", Path("/x"))  # must not raise


# ---------------------------------------------------------------------------
# Repository-level files
# ---------------------------------------------------------------------------


def test_the_core_writes_the_non_domain_minimum(tmp_path, spec_data):
    infos = [DomainInfo(name="demo", title="Demo", summary="demonstration domain")]
    written = scaffold.write_repo_files(tmp_path, spec_data, infos)
    names = {path.name for path in written}
    assert names == {"forge.yml", "README.md", ".gitattributes"}
    assert "eol=lf" in (tmp_path / ".gitattributes").read_text(encoding="utf-8")


def test_the_core_refuses_to_overwrite_a_modified_repository_file(tmp_path, spec_data):
    """Same rule copier applies to domain files: no silent overwrite."""
    infos = [DomainInfo(name="demo", title="Demo", summary="demonstration domain")]
    scaffold.write_repo_files(tmp_path, spec_data, infos)
    (tmp_path / "README.md").write_text("written by hand\n", encoding="utf-8")

    with pytest.raises(RenderError, match="README.md"):
        scaffold.write_repo_files(tmp_path, spec_data, infos)
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == "written by hand\n"

    scaffold.write_repo_files(tmp_path, spec_data, infos, force=True)
    assert "Generated domains" in (tmp_path / "README.md").read_text(encoding="utf-8")


def test_the_target_s_source_forge_yml_is_not_rewritten(tmp_path, spec_data):
    """Re-serialising the spec would destroy the comments the team put in it."""
    infos = [DomainInfo(name="demo", title="Demo", summary="demonstration domain")]
    spec_path = tmp_path / "forge.yml"
    original = "# HOUSE NOTE: do not touch\nforge_version: 1\n"
    spec_path.write_text(original, encoding="utf-8")

    written = scaffold.write_repo_files(
        tmp_path, spec_data, infos, spec_path=spec_path
    )
    assert spec_path not in written
    assert spec_path.read_text(encoding="utf-8") == original


def test_a_target_that_is_a_file_gives_a_readable_error(tmp_path, spec_data):
    file_path = tmp_path / "report.txt"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(RenderError, match="is not a directory"):
        scaffold.write_repo_files(file_path, spec_data, [])


def test_the_readme_indexes_the_domains(tmp_path, spec_data):
    infos = [DomainInfo(name="demo", title="Demo", summary="demonstration domain")]
    scaffold.write_repo_files(tmp_path, spec_data, infos)
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "| Demo | `demo/` | demonstration domain |" in readme
    assert "storefront" in readme
    assert "dev, prod" in readme


# ---------------------------------------------------------------------------
# Tree comparison
# ---------------------------------------------------------------------------


def _write(root: Path, paths: dict[str, str]) -> Path:
    for name, content in paths.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    return root


def test_two_identical_trees_show_no_difference(tmp_path):
    a = _write(tmp_path / "a", {"x.yml": "1\n"})
    b = _write(tmp_path / "b", {"x.yml": "1\n"})
    difference = diff_trees("demo", a, b)
    assert difference.empty
    assert difference.summary().endswith("up to date")


def test_the_diff_sorts_additions_removals_and_modifications(tmp_path):
    a = _write(tmp_path / "a", {"kept.yml": "1\n", "gone.yml": "x\n"})
    b = _write(tmp_path / "b", {"kept.yml": "2\n", "new.yml": "y\n"})
    difference = diff_trees("demo", a, b)
    assert difference.added == ["new.yml"]
    assert difference.removed == ["gone.yml"]
    assert difference.modified == [("kept.yml", 1)]
    assert not difference.empty


def test_the_diff_ignores_the_answers_file(tmp_path):
    a = _write(tmp_path / "a", {".copier-answers.yml": "_commit: 1\n"})
    b = _write(tmp_path / "b", {".copier-answers.yml": "_commit: 2\n"})
    assert diff_trees("demo", a, b).empty


def test_the_diff_never_quotes_the_content_of_the_files(tmp_path):
    a = _write(tmp_path / "a", {"secret.yml": "password\n"})
    b = _write(tmp_path / "b", {"secret.yml": "other\n"})
    summary = diff_trees("demo", a, b).summary()
    assert "password" not in summary and "other" not in summary
