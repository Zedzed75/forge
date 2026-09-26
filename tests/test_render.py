"""Rendering tests: normalisation, repository-level files, comparison."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from forge.errors import RenderError
from forge.plugins_api.types import DomainInfo
from forge.render import scaffold
from forge.render.copier_runner import (
    normalise_text,
    normalise_tree,
    rewrite_src_path,
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
    infos = [DomainInfo(name="demo", title="Demo", summary="domaine de demonstration")]
    written = scaffold.write_repo_files(tmp_path, spec_data, infos)
    names = {path.name for path in written}
    assert names == {"forge.yml", "README.md", ".gitattributes"}
    assert "eol=lf" in (tmp_path / ".gitattributes").read_text(encoding="utf-8")


def test_the_core_refuses_to_overwrite_a_modified_repository_file(tmp_path, spec_data):
    """Same rule copier applies to domain files: no silent overwrite."""
    infos = [DomainInfo(name="demo", title="Demo", summary="domaine de demonstration")]
    scaffold.write_repo_files(tmp_path, spec_data, infos)
    (tmp_path / "README.md").write_text("written by hand\n", encoding="utf-8")

    with pytest.raises(RenderError, match="README.md"):
        scaffold.write_repo_files(tmp_path, spec_data, infos)
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == "written by hand\n"

    scaffold.write_repo_files(tmp_path, spec_data, infos, force=True)
    assert "Generated domains" in (tmp_path / "README.md").read_text(encoding="utf-8")


def test_the_target_s_source_forge_yml_is_not_rewritten(tmp_path, spec_data):
    """Re-serialising the spec would destroy the comments the team put in it."""
    infos = [DomainInfo(name="demo", title="Demo", summary="domaine de demonstration")]
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
    infos = [DomainInfo(name="demo", title="Demo", summary="domaine de demonstration")]
    scaffold.write_repo_files(tmp_path, spec_data, infos)
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "| Demo | `demo/` | domaine de demonstration |" in readme
    assert "boutique" in readme
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
