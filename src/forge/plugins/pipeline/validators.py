"""Validation commands for the generated pipeline.

One validator per CI tool, and they are not equivalent — saying so is more useful
than pretending otherwise:

* **GitHub** — `actionlint` knows the schema of the workflows, the `${{ }}`
  expressions, the actions and their inputs. It finds a misplaced key, a
  reference to a job that does not exist, an expression that does not compile.
* **GitLab** — there is no offline equivalent. The only reliable linter is the
  server one (`/ci/lint`), which requires a URL, a token and the project already
  created: none of that has its place in `forge validate`. We therefore fall back
  on `yamllint`, which checks the form of the document and nothing of its
  semantics.

This asymmetry is **deliberate and documented**: the README of the domain
mentions it, so that "validation green" does not mean two different things
depending on the tool.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge.plugins.pipeline import tree
from forge.plugins_api.types import Command

#: Maximum time granted to a command, in seconds.
TIMEOUT = 120

#: Shared installation message.
INSTALL_HINT = (
    "install actionlint (https://github.com/rhysd/actionlint) for GitHub, or "
    "yamllint (pip install yamllint) for GitLab. On Windows, the WSL bridge looks "
    "for them in /opt/forge-tools/bin and /opt/forge-venv/bin."
)

#: yamllint rules applied to the GitLab file. Line length is disabled: a complete
#: deployment command exceeds any reasonable limit, and splitting it would make it
#: less readable, not more.
YAMLLINT_RULES = (
    "{extends: default, rules: {line-length: disable, comments-indentation: disable, "
    "document-start: disable, truthy: {check-keys: false}}}"
)


def commands(spec: Any, outdir: Path) -> list[Command]:
    """Command validating the generated pipeline file."""
    path = tree.workflow_path(spec)
    if spec.pipeline.is_github:
        return [
            Command(
                label="actionlint",
                tool="actionlint",
                argv=("-no-color", "-oneline", path),
                cwd=outdir,
                timeout=TIMEOUT,
                env=(("NO_COLOR", "1"),),
                install_hint=INSTALL_HINT,
                requires_linux=True,
            )
        ]
    return [
        Command(
            label="yamllint",
            tool="yamllint",
            argv=("--format", "parsable", "-d", YAMLLINT_RULES, path),
            cwd=outdir,
            timeout=TIMEOUT,
            env=(("NO_COLOR", "1"),),
            install_hint=INSTALL_HINT,
            requires_linux=True,
        )
    ]
