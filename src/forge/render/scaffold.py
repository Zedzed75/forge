"""Repository-level files written by the core (decision DESIGN.md §8 Q6).

In a monorepo, `forge.yml`, the `README.md` index and `.gitattributes` belong to
no domain: the core writes them itself, as a non-domain minimum. Everything else
— including Helm's `Makefile` or Ansible's `.gitignore` — stays in its domain's
subdirectory, which must remain self-contained and deletable.

These three files are the only ones forge writes **without going through
copier**. That has a known, accepted consequence: they are not tracked by
`copier update`, so `forge update` does not refresh them — `forge generate`
does. `forge diff` compares them explicitly, so that it never reports "up to
date" about something it did not look at.

The strings written into the target below are generated output, not source
prose: they stay French until the templates and the golden fixtures are
translated together.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge.errors import RenderError
from forge.plugins_api.types import DomainInfo
from forge.spec.io import SPEC_FILENAME, dump_spec

#: Content of the target's `.gitattributes`: the golden comparisons are made
#: byte for byte, no line-ending conversion is tolerable.
GITATTRIBUTES = """\
# Fins de ligne normalisees : la sortie de forge est comparee octet pour octet.
* text=auto eol=lf
"""

#: Repository-level files the core produces, in writing order.
REPO_FILENAMES = (SPEC_FILENAME, "README.md", ".gitattributes")


def _readme(service: dict[str, Any], domains: list[DomainInfo]) -> str:
    name = service.get("name", "service")
    description = service.get("description", "")
    owner = service.get("owner", "")
    environments = [env.get("name", "") for env in service.get("environments", [])]

    lines = [
        f"# {name}",
        "",
        description,
        "",
        "Projet genere par **forge** a partir de `forge.yml`. Toute modification",
        "structurelle passe par ce fichier : editez-le puis relancez",
        "`forge generate`, ou recuperez les evolutions de gabarit avec",
        "`forge update`.",
        "",
        "## Identite",
        "",
        f"- **Service** : `{name}`",
    ]
    if owner:
        lines.append(f"- **Responsable** : {owner}")
    if environments:
        lines.append(f"- **Environnements** : {', '.join(environments)}")
    lines += [
        "",
        "## Domaines generes",
        "",
        "| Domaine | Repertoire | Role |",
        "| --- | --- | --- |",
    ]
    for info in domains:
        # A domain whose output is the repository root — a CI pipeline, which its
        # tool only reads at an imposed location — has no subdirectory to show.
        location = (
            "racine du depot" if info.outdir in (".", "") else f"`{info.outdir}/`"
        )
        lines.append(f"| {info.title} | {location} | {info.summary} |")
    lines += [
        "",
        "Chaque domaine est autonome : son `.copier-answers.yml` permet de le",
        "mettre a jour seul (`forge update --only <domaine>`), et le supprimer",
        "n'affecte pas les autres.",
        "",
        "## Commandes utiles",
        "",
        "```bash",
        "forge generate          # regenere tous les domaines depuis forge.yml",
        "forge validate          # validateurs de chaque domaine + coherence",
        "forge diff              # ecart entre la cible et un rendu neuf",
        "forge update            # applique les evolutions de gabarit",
        "```",
        "",
    ]
    return "\n".join(lines)


def repo_files_content(
    spec_data: dict[str, Any], domains: list[DomainInfo]
) -> dict[str, str]:
    """Expected content of the repository-level files, writing nothing.

    Serves both the writing and the comparison (`forge diff`), so the two cannot
    diverge.
    """
    names = [info.name for info in domains]
    return {
        SPEC_FILENAME: dump_spec(spec_data, sections=names),
        "README.md": _readme(spec_data.get("service", {}), domains),
        ".gitattributes": GITATTRIBUTES,
    }


def _existing_conflicts(target: Path, wanted: dict[str, str]) -> list[str]:
    """Files already present whose content differs from what would be written."""
    conflicts: list[str] = []
    for name, content in wanted.items():
        path = target / name
        if not path.is_file():
            continue
        try:
            current = path.read_bytes().decode("utf-8")
        except (UnicodeDecodeError, OSError):
            conflicts.append(name)
            continue
        if current != content:
            conflicts.append(name)
    return conflicts


def write_repo_files(
    target: Path,
    spec_data: dict[str, Any],
    domains: list[DomainInfo],
    *,
    force: bool = False,
    spec_path: Path | None = None,
) -> list[Path]:
    """Write the repository-level files and return the list of written paths.

    `spec_path` designates the source specification. When it **is** the target's
    `forge.yml`, it is not rewritten: it is the source of truth, hand-edited, and
    re-serialising it would destroy its comments.

    Without `force`, an existing file whose content differs is not overwritten:
    the core applies to repository-level files the same rule copier applies to
    domain files.
    """
    from forge.render.copier_runner import ensure_directory

    target = Path(target)
    ensure_directory(target, "target directory")

    wanted = repo_files_content(spec_data, domains)
    if spec_path is not None:
        try:
            same = Path(spec_path).resolve() == (target / SPEC_FILENAME).resolve()
        except OSError:  # pragma: no cover - invalid path on this machine
            same = False
        if same:
            wanted.pop(SPEC_FILENAME, None)

    if not force:
        conflicts = _existing_conflicts(target, wanted)
        if conflicts:
            listing = "\n".join(f"    {name}" for name in conflicts)
            raise RenderError(
                f"{len(conflicts)} repository-level file(s) differ from what forge "
                f"would produce in {target}:\n{listing}\n"
                "  rerun with --force to overwrite them, or set your changes "
                "aside."
            )

    written: list[Path] = []
    for name in REPO_FILENAMES:
        if name not in wanted:
            continue
        path = target / name
        try:
            path.write_text(wanted[name], encoding="utf-8", newline="\n")
        except OSError as exc:
            raise RenderError(f"cannot write {path}: {exc}") from exc
        written.append(path)
    return written
