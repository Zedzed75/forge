"""Golden tests: same specification, same output, byte for byte.

Harness taken from ansible-forge (MIGRATION.md §3) and adapted to output written
by copier. Every file under `tests/specs/` is rendered then compared against
`tests/golden/<spec-name>/`.

Re-blessing after an **intended** template change:

    uv run pytest tests/test_golden.py --regen-golden

The two volatile lines of the copier answers file (`_commit`, `_src_path`) are
neutralised before comparison: they depend on the machine and on the temporary
clone, not on the template.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import (
    GOLDEN_DIR,
    REPO_ROOT,
    bless,
    render_all_plugins,
    spec_files,
    stable_text,
    tree_files,
)

#: Test cases: one per reference specification.
CASES = spec_files()

#: Reference case of the demonstration domain, targeted by the focused tests.
DEMO_CASE = next(path for path in CASES if path.stem == "demo-complet")

#: File of the demo template deliberately stored with CRLF (cf. .gitattributes).
CRLF_WITNESS = "fins-de-ligne.txt"


def _render(spec_path: Path, target: Path) -> Path:
    # The demonstration plugin AND the shipped domains: a specification that does
    # not declare a section simply does not generate that domain. The render
    # lives in conftest: the fingerprint harness must observe exactly the same.
    return render_all_plugins(spec_path, target)


@pytest.mark.parametrize("spec_path", CASES, ids=[path.stem for path in CASES])
def test_the_output_matches_the_reference(spec_path, tmp_path, regen_golden):
    rendered = _render(spec_path, tmp_path / "rendered")
    reference = GOLDEN_DIR / spec_path.stem

    if regen_golden:
        bless(rendered, reference)
        pytest.skip(f"reference re-blessed: {reference.name}")

    assert reference.is_dir(), (
        f"missing reference: {reference}. Run pytest --regen-golden after "
        "checking that the output is correct."
    )

    expected = tree_files(reference)
    obtained = tree_files(rendered)
    assert obtained == expected, (
        f"different tree: extra {sorted(set(obtained) - set(expected))}, "
        f"missing {sorted(set(expected) - set(obtained))}"
    )

    # Compare on bytes: `read_text` would translate CRLF while reading and blind
    # the harness to a line-ending regression.
    different = [
        name
        for name in expected
        if stable_text(rendered / name).encode("utf-8") != (reference / name).read_bytes()
    ]
    assert not different, f"different content: {', '.join(different)}"


@pytest.mark.parametrize("spec_path", CASES, ids=[path.stem for path in CASES])
def test_two_successive_renders_are_identical(spec_path, tmp_path):
    """Determinism depends neither on dict ordering nor on the clock."""
    first = tree_files(_render(spec_path, tmp_path / "one"))
    second = tree_files(_render(spec_path, tmp_path / "two"))
    assert first == second
    for name in first:
        assert stable_text(tmp_path / "one" / name) == stable_text(tmp_path / "two" / name)


def test_filtering_a_file_with_if_really_removes_the_file(tmp_path):
    """A path segment rendered empty makes the file disappear (MIGRATION §2.1)."""
    rendered = _render(DEMO_CASE, tmp_path)
    assert (rendered / "demo" / "widgets" / "cpu" / "detail.yml").is_file()
    assert not (rendered / "demo" / "widgets" / "requetes").exists()


def test_nested_yields_produce_the_cartesian_product(tmp_path):
    """One yield per segment: environments x widgets, the parent variable still read."""
    rendered = _render(DEMO_CASE, tmp_path)
    files = tree_files(rendered / "demo" / "environments")
    assert files == [
        "dev/cpu.yml",
        "dev/requetes.yml",
        "prod/cpu.yml",
        "prod/requetes.yml",
    ]


def test_the_normalisation_applies_to_a_real_copier_render(tmp_path):
    """End-to-end proof: a template stored in CRLF comes out in LF.

    The witness file carries an exception in the repository's `.gitattributes`;
    without it git would normalise it at checkout and the test would silently
    cancel itself. So we first check that it really kept its CRLF.
    """
    source = REPO_ROOT / "src" / "forge" / "plugins" / "demo" / "template" / CRLF_WITNESS
    assert source.is_file(), f"missing witness file: {source}"
    if b"\r\n" not in source.read_bytes():
        pytest.fail(
            f"{source} lost its CRLF: the .gitattributes exception has gone, "
            "the test no longer proves anything."
        )

    rendered = _render(DEMO_CASE, tmp_path)
    delivered = rendered / "demo" / CRLF_WITNESS
    assert delivered.is_file()
    assert b"\r" not in delivered.read_bytes()


def test_a_plugin_filter_is_really_applied(tmp_path):
    """Proof that `FORGE_PLUGIN_JINJA` really loads the domain's filters."""
    rendered = _render(DEMO_CASE, tmp_path)
    readme = (rendered / "demo" / "README.md").read_text(encoding="utf-8")
    assert "BOUTIQUE" in readme          # shout filter
    assert "== boutique ==" in readme    # demo_banner global
