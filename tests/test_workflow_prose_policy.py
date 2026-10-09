# ---------------------------------------------------------------------------
# Tests for `scripts/workflow-diff-is-prose.sh` (decision D7, clause C1).
# ---------------------------------------------------------------------------
# The script answers one question with an exit code: is every changed line of
# every `.github/workflows/**` file a comment, a step-level `name:` value, or
# literal text inside an already-quoted string in a `run:` block? These tests
# are the proof that the answer is not simply "yes" -- half of them are diffs
# that must be refused, including the two exclusions D7 names explicitly:
#
#   * a **job-level** `name:`, because check-run identity derives from it and
#     D4's six-checks clause depends on that identity;
#   * shell structure *outside* the quotes, including `>> "$GITHUB_OUTPUT"` and
#     the key side of any `key=value` written to one.
#
# The fixtures are not invented syntax: the prose cases are the real changed
# lines of PR #61 and the refused ones are the real changed lines of PR #59 and
# PR #50, which is what makes this file a test of the policy rather than of the
# regular expressions.
#
# The script is shell, so each case is a real two-commit git repository and a
# real invocation. Nothing here imports forge: the policy is repository
# plumbing, not part of the published distribution.
# ---------------------------------------------------------------------------

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "workflow-diff-is-prose.sh"

BASH = shutil.which("bash")
GIT = shutil.which("git")

pytestmark = pytest.mark.skipif(
    BASH is None or GIT is None,
    reason="the C1 witness is a shell script; it needs bash and git on PATH",
)

WORKFLOW = ".github/workflows/ci.yml"

# A workflow small enough to read whole and complete enough to be representative:
# a top-level name, a trigger, a job with its own name, a `uses:` with a pinned
# SHA, a `with:` block whose input happens to be called `name`, a block `run:`
# with a comment and a quoted log line, and a write to `$GITHUB_OUTPUT`.
BASE = """\
# ---------------------------------------------------------------------------
# The continuous integration of forge.
# ---------------------------------------------------------------------------
name: CI

on:
  push:
    branches: ["**"]

permissions:
  contents: read

jobs:
  matrix:
    name: tests (python 3.13)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0

      - uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1
        with:
          name: distributions
          path: dist/

      # `python-version` is handed to uv.
      - name: Install the Ansible domain tools
        run: |
          uv pip install 'ansible-core==2.19.13'
          # galaxy.ansible.com drops the connection now and then.
          echo "ansible-galaxy failed (try ${attempt}/3), new try in 15 s"
          echo "collections=$HOME/.ansible/collections" >> "$GITHUB_OUTPUT"
          echo hello

      - name: Launch the test suite
        env:
          FORGE_REQUIRE_TOOLS: "1"
        run: uv run pytest -rs
"""


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        [
            GIT,
            "-c",
            "user.name=forge-test",
            "-c",
            "user.email=test@example.invalid",
            *args,
        ],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def run_policy(tmp_path: Path, head_files: dict[str, str | None]) -> tuple[int, str]:
    """Build a two-commit repository and run the C1 witness over it.

    `head_files` maps a path to its content at the head commit; `None` deletes
    the file. The base commit always holds `BASE` as `ci.yml`.
    """
    repo = tmp_path / "repo"
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / WORKFLOW).write_text(BASE, encoding="utf-8", newline="\n")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")

    for path, content in head_files.items():
        target = repo / path
        if content is None:
            target.unlink()
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "head", "--allow-empty")

    completed = subprocess.run(
        [BASH, str(SCRIPT), "HEAD~1", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.returncode, completed.stdout + completed.stderr


def prose(tmp_path: Path, before: str, after: str) -> tuple[int, str]:
    """Run the witness over a one-line substitution in `ci.yml`."""
    assert before in BASE, "the fixture no longer contains the line under test"
    return run_policy(tmp_path, {WORKFLOW: BASE.replace(before, after)})


# ---------------------------------------------------------------------------
# What C1 lets through
# ---------------------------------------------------------------------------


def test_no_workflow_change_is_outside_c1(tmp_path: Path) -> None:
    """A PR that touches no workflow is inside plain D6 and needs no reading."""
    code, out = run_policy(tmp_path, {"README.md": "whatever\n"})
    assert code == 0, out
    assert "C1 does not apply" in out


def test_a_yaml_comment_is_prose(tmp_path: Path) -> None:
    code, out = prose(
        tmp_path,
        "# The continuous integration of forge.",
        "# Continuous integration for forge.",
    )
    assert code == 0, out


def test_a_comment_may_be_reflowed(tmp_path: Path) -> None:
    """Translating prose changes its line count; that is not a diff to refuse."""
    code, out = prose(
        tmp_path,
        "      # `python-version` is handed to uv.\n",
        "      # `python-version` is handed to uv: without it the matrix would\n"
        "      # be mere decoration and the three jobs would run on the same\n"
        "      # interpreter.\n",
    )
    assert code == 0, out


def test_a_shell_comment_inside_a_run_block_is_prose(tmp_path: Path) -> None:
    code, out = prose(
        tmp_path,
        "          # galaxy.ansible.com drops the connection now and then.",
        "          # galaxy.ansible.com sometimes drops the connection.",
    )
    assert code == 0, out


def test_a_step_level_name_is_prose(tmp_path: Path) -> None:
    code, out = prose(
        tmp_path,
        "      - name: Install the Ansible domain tools",
        "      - name: Install the Ansible domain tooling",
    )
    assert code == 0, out


def test_text_inside_an_already_quoted_run_string_is_prose(tmp_path: Path) -> None:
    """PR #61's `ci.yml` log line: the true positive."""
    code, out = prose(
        tmp_path,
        'echo "ansible-galaxy failed (try ${attempt}/3), new try in 15 s"',
        'echo "ansible-galaxy failed (attempt ${attempt}/3), retrying in 15 s"',
    )
    assert code == 0, out


# ---------------------------------------------------------------------------
# The two exclusions D7 names
# ---------------------------------------------------------------------------


def test_a_job_level_name_is_not_prose(tmp_path: Path) -> None:
    """First deliberate exclusion: check-run identity derives from this name."""
    code, out = prose(
        tmp_path,
        "    name: tests (python 3.13)",
        "    name: suite (python 3.13)",
    )
    assert code == 1, out
    assert "name: suite (python 3.13)" in out


def test_the_key_side_of_a_github_output_write_is_not_prose(tmp_path: Path) -> None:
    """Second deliberate exclusion: inside those quotes is an interface."""
    code, out = prose(
        tmp_path,
        'echo "collections=$HOME/.ansible/collections" >> "$GITHUB_OUTPUT"',
        'echo "ansible_collections=$HOME/.ansible/collections" >> "$GITHUB_OUTPUT"',
    )
    assert code == 1, out


def test_a_redirection_is_not_prose(tmp_path: Path) -> None:
    """Shell structure outside the quotes, even with the text left alone."""
    code, out = prose(
        tmp_path,
        'echo "ansible-galaxy failed (try ${attempt}/3), new try in 15 s"',
        'echo "ansible-galaxy failed (try ${attempt}/3), new try in 15 s" >> /tmp/log',
    )
    assert code == 1, out


def test_an_input_called_name_is_not_a_step_name(tmp_path: Path) -> None:
    """`with: name:` is an artifact name, not a label; only `steps` loosen it."""
    code, out = prose(tmp_path, "          name: distributions", "          name: dists")
    assert code == 1, out


# ---------------------------------------------------------------------------
# What C1 refuses -- the true negatives, from the PRs that stay parked
# ---------------------------------------------------------------------------


def test_a_trigger_change_is_not_prose(tmp_path: Path) -> None:
    """PR #59's first hunk: `on:` narrowed from every branch to `master`."""
    code, out = prose(tmp_path, '    branches: ["**"]', '    branches: ["master"]')
    assert code == 1, out
    assert 'branches: ["master"]' in out


def test_adding_concurrency_is_not_prose(tmp_path: Path) -> None:
    """PR #59's second hunk, comment block and all."""
    code, out = prose(
        tmp_path,
        "permissions:\n",
        "# One run per git reference, and never two at once.\n"
        "concurrency:\n"
        "  group: ci-${{ github.workflow }}-${{ github.ref }}\n"
        "  cancel-in-progress: ${{ github.ref != 'refs/heads/master' }}\n"
        "\n"
        "permissions:\n",
    )
    assert code == 1, out
    assert "concurrency:" in out


def test_a_with_input_is_not_prose(tmp_path: Path) -> None:
    """PR #50 changes `enable-cache` on the publish path; C1 fails on `with:`."""
    code, out = prose(tmp_path, "          fetch-depth: 0", "          fetch-depth: 1")
    assert code == 1, out


def test_a_pinned_version_is_not_prose(tmp_path: Path) -> None:
    code, out = prose(tmp_path, "'ansible-core==2.19.13'", "'ansible-core==2.20.0'")
    assert code == 1, out


def test_a_pin_comment_is_not_prose(tmp_path: Path) -> None:
    """The comment on a `uses:` line is the readable half of the pin."""
    code, out = prose(tmp_path, "# v7.0.1", "# v7.0.2")
    assert code == 1, out


def test_an_env_change_is_not_prose(tmp_path: Path) -> None:
    code, out = prose(tmp_path, 'FORGE_REQUIRE_TOOLS: "1"', 'FORGE_REQUIRE_TOOLS: "0"')
    assert code == 1, out


def test_unquoted_run_text_is_not_prose(tmp_path: Path) -> None:
    """C1 says *already-quoted*: a bare word in a `run:` block is a command."""
    code, out = prose(tmp_path, "echo hello", "echo bonjour")
    assert code == 1, out


def test_requoting_a_string_is_not_prose(tmp_path: Path) -> None:
    """Single to double quotes changes what the shell expands, not the text."""
    code, out = prose(tmp_path, "'ansible-core==2.19.13'", '"ansible-core==2.19.13"')
    assert code == 1, out


# ---------------------------------------------------------------------------
# Fail closed
# ---------------------------------------------------------------------------


def test_a_new_workflow_file_is_not_prose(tmp_path: Path) -> None:
    code, out = run_policy(
        tmp_path, {".github/workflows/nightly.yml": "name: Nightly\non: schedule\n"}
    )
    assert code == 1, out
    assert "added" in out


def test_deleting_a_workflow_is_not_prose(tmp_path: Path) -> None:
    code, out = run_policy(tmp_path, {WORKFLOW: None})
    assert code == 1, out
    assert "deleted" in out


def test_an_unterminated_quote_fails_closed(tmp_path: Path) -> None:
    """A line the normaliser cannot classify is compared verbatim, so it fails."""
    code, out = prose(
        tmp_path,
        'echo "ansible-galaxy failed (try ${attempt}/3), new try in 15 s"',
        "echo \"ansible-galaxy didn't answer (attempt ${attempt}/3)' ",
    )
    assert code == 1, out


def test_a_bad_revision_is_an_error_not_a_verdict(tmp_path: Path) -> None:
    """Exit 2, never 0: a witness that could not run has witnessed nothing."""
    repo = tmp_path / "repo"
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / WORKFLOW).write_text(BASE, encoding="utf-8", newline="\n")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    completed = subprocess.run(
        [BASH, str(SCRIPT), "no-such-ref", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2, completed.stdout + completed.stderr


# ---------------------------------------------------------------------------
# The real pull requests, when the refs are at hand
# ---------------------------------------------------------------------------
# These two are the cases the policy was written for, run against the actual
# commits rather than against an extract of them. They skip where the refs are
# absent -- in the matrix container, which is cloned from a bundle of one
# branch, and in any clone that has not fetched the pull request heads:
#
#   git fetch origin pull/61/head:pr61 pull/59/head:pr59
# ---------------------------------------------------------------------------


def _resolve(ref: str) -> str | None:
    completed = subprocess.run(
        [GIT, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() or None


@pytest.mark.parametrize(
    ("candidates", "expected"),
    [
        (("pr61", "refs/pull/61/head"), 0),
        (("pr59", "refs/pull/59/head"), 1),
    ],
    ids=["pr61-is-prose", "pr59-is-not"],
)
def test_the_real_pull_requests(candidates: tuple[str, ...], expected: int) -> None:
    base = _resolve("origin/master") or _resolve("master")
    if base is None:
        pytest.skip("neither origin/master nor master is present in this clone")
    head = next((sha for ref in candidates if (sha := _resolve(ref))), None)
    if head is None:
        pytest.skip(f"none of {candidates} is present; fetch the pull request head")
    completed = subprocess.run(
        [BASH, str(SCRIPT), base, head],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert completed.returncode == expected, completed.stdout + completed.stderr
