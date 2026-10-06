"""Paths the pipeline domain writes.

The only domain of the project whose output is the **root of the repository**: a
CI file only exists where its tool reads it, and neither GitHub nor GitLab looks
for it anywhere else. `DomainInfo.outdir` is therefore `.`, which the core has
known how to handle since phase 8 (`pipeline.foreign_paths`).

A consequence not to forget: this domain shares its root with the
repository-level files forge writes itself (`README.md`, `forge.yml`,
`.gitattributes`). It must therefore **never** produce a file carrying one of
those names — a test checks it.
"""

from __future__ import annotations

from typing import Any, Final

#: Location GitHub Actions imposes.
GITHUB_WORKFLOW: Final[str] = ".github/workflows/ci.yml"

#: Location GitLab CI imposes.
GITLAB_CONFIG: Final[str] = ".gitlab-ci.yml"

#: Repository-level files forge writes itself, with which this domain shares its
#: root.
REPO_LEVEL_FILES: Final[frozenset[str]] = frozenset(
    {"README.md", "forge.yml", ".gitattributes"}
)


def workflow_path(spec: Any) -> str:
    """Path of the pipeline file, relative to the root of the repository."""
    return GITHUB_WORKFLOW if spec.pipeline.is_github else GITLAB_CONFIG


def expected_paths(spec: Any) -> list[str]:
    """Every path the domain writes, sorted."""
    return sorted([workflow_path(spec), ".copier-answers.yml"])


def provider_slots(spec: Any) -> dict[str, list[dict[str, str]]]:
    """File slots per CI tool: `[{...}]` for one, `[]` for the other.

    The same pattern as the two other domains (arbitration R4): the template path
    carries a `yield` tag, and copier decides whether to write or not — including
    the `.github/` directory, which has no business existing on GitLab.
    """
    retained = spec.pipeline.provider.value
    return {
        name: ([{"name": name}] if name == retained else [])
        for name in ("github", "gitlab")
    }
