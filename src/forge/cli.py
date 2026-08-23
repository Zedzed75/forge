"""Interface en ligne de commande de forge (DESIGN.md §7).

La CLI ne porte aucune logique : elle lit des arguments, appelle
`forge.pipeline` et met en forme des resultats. Toute erreur attendue derive de
`ForgeError` et sort en code 1 avec un message, jamais une trace Python.

La sortie n'est jamais coloree : elle est lue autant par des tests que par des
humains, et `NO_COLOR` n'a donc rien a desactiver.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from forge import __version__
from forge.errors import ForgeError
from forge.interview.prompter import Prompter, QuestionaryPrompter
from forge.interview.service_flow import ask_domains, ask_service
from forge.plugins_api.manager import ForgeManager, default_manager
from forge.render.copier_runner import DEFAULT_REF
from forge.spec.assembly import FORGE_VERSION, validate_spec
from forge.spec.io import SPEC_FILENAME, save_spec
from forge.validate.consistency import format_issues
from forge.validate.tools import probe
from forge import pipeline

app = typer.Typer(
    name="forge",
    help="Genere des projets IaC complets et commentes a partir d'un seul forge.yml.",
    add_completion=False,
    no_args_is_help=True,
)


def _split(value: str | None) -> list[str] | None:
    """Decoupe une option `--only a,b` en liste, ou None si absente."""
    if value is None:
        return None
    names = [part.strip() for part in value.split(",") if part.strip()]
    return names or None


def _fail(message: str) -> None:
    typer.echo(message, err=True)
    raise typer.Exit(code=1)


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(
        False, "--version", help="Affiche la version puis quitte."
    ),
) -> None:
    """Point d'entree commun a toutes les sous-commandes."""
    if version:
        typer.echo(f"forge {__version__}")
        raise typer.Exit()


# ---------------------------------------------------------------------------
# new
# ---------------------------------------------------------------------------


def run_new(
    target: Path,
    manager: ForgeManager,
    prompter: Prompter,
    *,
    spec_out: Path | None = None,
    only: list[str] | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> pipeline.GenerationResult:
    """Conduit l'entretien complet puis genere ; testable sans terminal."""
    service = ask_service(prompter)
    available = [
        (info.name, f"{info.title} — {info.summary}")
        for info in manager.domains()
        if only is None or info.name in only
    ]
    chosen = ask_domains(prompter, available)

    data: dict = {"forge_version": FORGE_VERSION, "service": service}
    validated_service = validate_spec(dict(data), manager).service
    for name in chosen:
        section = manager.domain(name).interview(prompter, validated_service)
        if section is not None:
            data[name] = section

    spec = validate_spec(data, manager)
    if spec_out is not None:
        save_spec(data, Path(spec_out), sections=list(spec.domain_names()))
    return pipeline.generate(
        data, spec, manager, target, force=force, dry_run=dry_run
    )


@app.command("new")
def cmd_new(
    out: Path = typer.Option(Path("."), "--out", "-o", help="Repertoire cible."),
    spec_out: Optional[Path] = typer.Option(
        None, "--spec-out", help="Ecrit aussi la spec a cet emplacement."
    ),
    only: Optional[str] = typer.Option(
        None, "--only", help="Restreint aux domaines cites (liste separee par des virgules)."
    ),
    force: bool = typer.Option(False, "--force", help="Ecrase les fichiers existants."),
    dry_run: bool = typer.Option(False, "--dry-run", help="N'ecrit rien."),
) -> None:
    """Entretien interactif, puis ecriture de forge.yml et generation."""
    manager = default_manager()
    try:
        result = run_new(
            out,
            manager,
            QuestionaryPrompter(),
            spec_out=spec_out,
            only=_split(only),
            force=force,
            dry_run=dry_run,
        )
    except ForgeError as exc:
        _fail(str(exc))
        return
    typer.echo(result.summary())


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------


@app.command("generate")
def cmd_generate(
    spec: Optional[Path] = typer.Option(
        None, "--spec", "-s", help=f"Specification a rejouer (defaut : {SPEC_FILENAME})."
    ),
    out: Path = typer.Option(Path("."), "--out", "-o", help="Repertoire cible."),
    only: Optional[str] = typer.Option(None, "--only", help="Restreint aux domaines cites."),
    ref: str = typer.Option(DEFAULT_REF, "--ref", help="Reference git du gabarit."),
    force: bool = typer.Option(False, "--force", help="Ecrase les fichiers existants."),
    dry_run: bool = typer.Option(False, "--dry-run", help="N'ecrit rien."),
) -> None:
    """Regenere les domaines depuis une specification existante."""
    manager = default_manager()
    try:
        spec_path = pipeline.find_spec_file(spec, out)
        data, model = pipeline.load_spec(spec_path, manager)
        result = pipeline.generate(
            data,
            model,
            manager,
            out,
            only=_split(only),
            ref=ref,
            force=force,
            dry_run=dry_run,
        )
    except ForgeError as exc:
        _fail(str(exc))
        return
    typer.echo(result.summary())


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


@app.command("validate")
def cmd_validate(
    spec: Optional[Path] = typer.Option(None, "--spec", "-s", help="Specification a lire."),
    out: Path = typer.Option(Path("."), "--out", "-o", help="Repertoire du projet genere."),
    only: Optional[str] = typer.Option(None, "--only", help="Restreint aux domaines cites."),
    skip_missing: bool = typer.Option(
        False, "--skip-missing", help="Saute les verifications dont l'outil est absent."
    ),
) -> None:
    """Lance les validateurs de chaque domaine, puis les controles inter-domaines."""
    manager = default_manager()
    try:
        spec_path = pipeline.find_spec_file(spec, out)
        _, model = pipeline.load_spec(spec_path, manager)
        result = pipeline.validate(
            model, manager, out, only=_split(only), skip_missing=skip_missing
        )
    except ForgeError as exc:
        _fail(str(exc))
        return

    for report in result.reports:
        typer.echo(report.summary())
        for check in report.checks:
            typer.echo(f"  {check.line()}")
            if check.detail:
                typer.echo(f"    {check.detail.splitlines()[0]}")
    typer.echo(format_issues(result.issues))
    if not result.ok:
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# update / diff
# ---------------------------------------------------------------------------


@app.command("update")
def cmd_update(
    out: Path = typer.Option(Path("."), "--out", "-o", help="Repertoire du projet genere."),
    only: Optional[str] = typer.Option(None, "--only", help="Restreint aux domaines cites."),
    ref: str = typer.Option(DEFAULT_REF, "--ref", help="Reference git du gabarit."),
    conflict: str = typer.Option(
        "inline", "--conflict", help="Strategie de conflit copier : inline ou rej."
    ),
) -> None:
    """Applique les evolutions de gabarit a un projet deja genere."""
    manager = default_manager()
    try:
        updated = pipeline.update(
            manager, out, only=_split(only), ref=ref, conflict=conflict
        )
    except ForgeError as exc:
        _fail(str(exc))
        return
    typer.echo(f"domaines mis a jour : {', '.join(updated) or 'aucun'}")


@app.command("diff")
def cmd_diff(
    spec: Optional[Path] = typer.Option(None, "--spec", "-s", help="Specification a lire."),
    out: Path = typer.Option(Path("."), "--out", "-o", help="Repertoire du projet genere."),
    only: Optional[str] = typer.Option(None, "--only", help="Restreint aux domaines cites."),
    ref: str = typer.Option(DEFAULT_REF, "--ref", help="Reference git du gabarit."),
) -> None:
    """Resume l'ecart entre la cible et un rendu neuf (jamais le diff integral)."""
    manager = default_manager()
    try:
        spec_path = pipeline.find_spec_file(spec, out)
        _, model = pipeline.load_spec(spec_path, manager)
        diffs = pipeline.diff(model, manager, out, only=_split(only), ref=ref)
    except ForgeError as exc:
        _fail(str(exc))
        return
    for entry in diffs:
        typer.echo(entry.summary())
        for name in entry.added:
            typer.echo(f"  + {name}")
        for name in entry.removed:
            typer.echo(f"  - {name}")
        for name, lines in entry.modified:
            typer.echo(f"  ~ {name} ({lines} ligne(s))")


# ---------------------------------------------------------------------------
# plugins / catalog
# ---------------------------------------------------------------------------


@app.command("plugins")
def cmd_plugins() -> None:
    """Liste les domaines enregistres et l'etat de leurs outils externes."""
    manager = default_manager()
    domains = manager.domains()
    if not domains:
        typer.echo("aucun domaine enregistre")
        return
    for info in domains:
        typer.echo(f"{info.name} — {info.title} : {info.summary}")
        typer.echo(f"  section forge.yml : {info.name}:    sortie : {info.outdir}/")
        hooks = manager.domain(info.name)
        seen: set[str] = set()
        try:
            # Sans specification, un plugin peut refuser de lister ses commandes :
            # l'etat des outils est alors simplement omis.
            commands = hooks.validators(None, Path(info.outdir))
        except Exception:  # noqa: BLE001 - diagnostic facultatif, jamais bloquant
            continue
        for command in commands:
            if command.tool in seen:
                continue
            seen.add(command.tool)
            typer.echo(f"  {probe(command.tool, command.requires_linux).describe()}")


@app.command("catalog")
def cmd_catalog(
    domain: str = typer.Argument(..., help="Domaine dont on consulte le catalogue."),
    entry: Optional[str] = typer.Argument(None, help="Element precis a detailler."),
) -> None:
    """Affiche le catalogue fourni par un plugin (roles, composants...)."""
    manager = default_manager()
    try:
        entries = manager.domain(domain).catalog()
    except ForgeError as exc:
        _fail(str(exc))
        return
    if not entries:
        typer.echo(f"le domaine {domain} ne publie pas de catalogue")
        return
    if entry is None:
        for item in entries:
            typer.echo(f"{item.name} — {item.summary}")
        return
    for item in entries:
        if item.name == entry:
            typer.echo(f"{item.name} — {item.summary}")
            if item.details:
                typer.echo(item.details)
            for option, description in sorted(item.options.items()):
                typer.echo(f"  {option} : {description}")
            return
    _fail(f"element inconnu dans le catalogue {domain} : {entry}")


if __name__ == "__main__":  # pragma: no cover
    app()
