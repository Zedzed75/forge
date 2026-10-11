"""`scripts/check_file_sizes.py` - the gate, tested rather than trusted.

A gate is the one kind of code whose green run says nothing about it: a check
that never fires and a check that cannot fire look identical from a passing
build. forge learned the cost of the second on `tests/french_baseline.txt`,
where a stale data file went through because the tests were picked from the
diff rather than from the gate the diff touched.

So every branch of `check()` is driven here against synthetic trees, including
the two that make the KNOWN_OVERSIZE table a ratchet rather than a waiver, and
one case asserts against the real repository.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE_PATH = REPO_ROOT / "scripts" / "check_file_sizes.py"


def _load_gate():
    """Import the script by path: `scripts/` is not a package."""
    spec = importlib.util.spec_from_file_location("check_file_sizes", GATE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _load_gate()


def write(root: Path, rel: str, lines: int) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x\n" * lines, encoding="utf-8")


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty repository with the gate scoped to it and nothing waived."""
    monkeypatch.setattr(gate, "SCAN_DIRS", ("src", "tests"))
    monkeypatch.setattr(gate, "TRACKED_PROSE", ())
    monkeypatch.setattr(gate, "KNOWN_OVERSIZE", {})
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    return tmp_path


class TestTheThresholds:
    def test_a_small_module_is_silent(self, tree: Path) -> None:
        write(tree, "src/small.py", 120)

        assert gate.check(tree) == ([], [])

    def test_the_warning_band_warns_and_does_not_fail(self, tree: Path) -> None:
        """601-700 is a nudge, not a build break: the file is still shippable
        and the person who tripped it is usually not the person who grew it."""
        write(tree, "src/middling.py", 650)

        failures, warnings = gate.check(tree)

        assert failures == []
        assert len(warnings) == 1
        assert "650 lines" in warnings[0]

    def test_exactly_the_warn_threshold_is_still_silent(self, tree: Path) -> None:
        """The boundary, pinned: 600 is the cap, so 600 passes and 601 warns.
        An off-by-one here would either nag about every compliant file or let
        the first 100 lines of debt through unremarked."""
        write(tree, "src/at_cap.py", gate.WARN_THRESHOLD)

        assert gate.check(tree) == ([], [])

    def test_one_line_over_the_warn_threshold_warns(self, tree: Path) -> None:
        write(tree, "src/over_cap.py", gate.WARN_THRESHOLD + 1)

        failures, warnings = gate.check(tree)

        assert failures == []
        assert warnings

    def test_exactly_the_fail_threshold_only_warns(self, tree: Path) -> None:
        write(tree, "src/at_limit.py", gate.FAIL_THRESHOLD)

        failures, warnings = gate.check(tree)

        assert failures == []
        assert warnings

    def test_one_line_over_the_fail_threshold_fails(self, tree: Path) -> None:
        write(tree, "src/too_big.py", gate.FAIL_THRESHOLD + 1)

        failures, _ = gate.check(tree)

        assert len(failures) == 1
        assert "hard limit" in failures[0]


class TestWhatIsOutOfScope:
    def test_generated_golden_output_is_not_gated(self, tree: Path) -> None:
        """`tests/golden/**` is byte-exact generator output. A gate pushing back
        on it would be the rule editing the product rather than the code."""
        write(tree, "tests/golden/demo/conftest.py", 900)

        assert gate.check(tree) == ([], [])

    def test_a_non_python_file_outside_the_prose_list_is_not_gated(self, tree: Path) -> None:
        """README.md and friends are user documentation, not registers we chose
        to cap. Only TRACKED_PROSE names prose, one file at a time."""
        write(tree, "src/notes.md", 900)

        assert gate.check(tree) == ([], [])


class TestTrackedProse:
    def test_a_tracked_register_over_the_limit_fails(
        self, tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gate, "TRACKED_PROSE", ("LEDGER.md",))
        write(tree, "LEDGER.md", 900)

        failures, _ = gate.check(tree)

        assert len(failures) == 1
        assert "LEDGER.md" in failures[0]

    def test_a_tracked_register_that_does_not_exist_fails(
        self, tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Naming them one at a time is only safe if a rename cannot silently
        narrow the gate. JARVIS's gate globbed `*.py` and `MEMORY.md` sat at
        1116 lines through every green run; this is the other half of not
        repeating that."""
        monkeypatch.setattr(gate, "TRACKED_PROSE", ("GONE.md",))

        failures, _ = gate.check(tree)

        assert len(failures) == 1
        assert "does not exist" in failures[0]


class TestKnownOversizeIsARatchet:
    """The table freezes existing debt; it does not forgive it.

    Both directions are enforced, and each of the two tests below is the reason
    the other is not enough. Without the first, waived debt grows for free.
    Without the second, the table outlives the problem and starts exempting a
    file that no longer needs it - which is how a waiver becomes a hole.
    """

    def test_a_waived_file_at_its_recorded_size_passes(
        self, tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gate, "KNOWN_OVERSIZE", {"src/legacy.py": 857})
        write(tree, "src/legacy.py", 857)

        assert gate.check(tree) == ([], [])

    def test_a_waived_file_that_grew_fails(
        self, tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gate, "KNOWN_OVERSIZE", {"src/legacy.py": 857})
        write(tree, "src/legacy.py", 858)

        failures, _ = gate.check(tree)

        assert len(failures) == 1
        assert "may not grow" in failures[0]

    def test_a_waived_file_that_shrank_under_the_cap_fails(
        self, tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """So the entry has to be deleted when its issue lands, rather than
        sitting there quietly exempting a compliant file forever."""
        monkeypatch.setattr(gate, "KNOWN_OVERSIZE", {"src/legacy.py": 857})
        write(tree, "src/legacy.py", 400)

        failures, _ = gate.check(tree)

        assert len(failures) == 1
        assert "remove its KNOWN_OVERSIZE entry" in failures[0]

    def test_a_waived_file_that_shrank_but_is_still_over_the_cap_passes(
        self, tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Partial progress is not a failure. 857 -> 720 is the right direction
        and the entry stays until the split finishes."""
        monkeypatch.setattr(gate, "KNOWN_OVERSIZE", {"src/legacy.py": 857})
        write(tree, "src/legacy.py", 720)

        assert gate.check(tree) == ([], [])

    def test_a_waived_path_the_gate_never_scans_fails(
        self, tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A typo in the table would otherwise be invisible: the entry matches
        nothing, so nothing is waived and nothing complains."""
        monkeypatch.setattr(gate, "KNOWN_OVERSIZE", {"src/typo.py": 857})

        failures, _ = gate.check(tree)

        assert len(failures) == 1
        assert "never scanned it" in failures[0]


class TestTheRealRepository:
    def test_master_passes_its_own_gate(self) -> None:
        """Shipping a gate that is already red would make the first unrelated
        PR look broken."""
        failures, _ = gate.check(REPO_ROOT)

        assert failures == [], failures

    def test_every_waived_count_matches_the_file_today(self) -> None:
        """The recorded numbers are evidence, not decoration. If one drifts, the
        ratchet above is measuring against a figure nobody checked."""
        for rel, recorded in gate.KNOWN_OVERSIZE.items():
            actual = gate.count_lines(REPO_ROOT / rel)
            assert actual == recorded, f"{rel}: recorded {recorded}, actually {actual}"
