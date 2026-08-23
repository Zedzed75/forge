"""Interface en ligne de commande d'ansible-forge.

Cinq commandes :

* ``new``      — entretien interactif, écrit ``forge.yml`` puis génère le projet
* ``generate`` — rejoue une spécification existante
* ``validate`` — vérifie une spécification sans rien écrire
* ``check``    — passe --syntax-check et ansible-lint sur un projet généré
* ``catalog``  — liste les rôles disponibles et leurs options
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from ansible_forge import __version__
from ansible_forge.catalog.registry import get_role, role_names
from ansible_forge.engine.planner import plan
from ansible_forge.engine.role_planner import implemented_roles
from ansible_forge.engine.writer import build_tree, write_artifacts
from ansible_forge.errors import ForgeError
from ansible_forge.models.spec import ProjectSpec
from ansible_forge.prompts.flow import run_interview
from ansible_forge.prompts.prompter import QuestionaryPrompter
from ansible_forge.spec_io import load_spec, save_spec
from ansible_forge.verify import check_project

app = typer.Typer(
    name="ansible-forge",
    help="Génère un projet Ansible complet et commenté à partir d'une spécification.",
    # Sans sous-commande, le callback affiche l'aide et sort en code 0.
    add_completion=False,
)

#: Nom par défaut du fichier de spécification.
SPEC_FILENAME = "forge.yml"


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", help="Affiche la version puis quitte.", is_eager=True
    ),
) -> None:
    """Point d'entrée commun à toutes les commandes."""
    _configure_console()
    if version:
        typer.echo(f"ansible-forge {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@app.command()
def new(
    output: Path = typer.Option(
        None, "--output", "-o", help="Répertoire de sortie (défaut : ./<nom-du-projet>)."
    ),
    spec_file: Path = typer.Option(
        None, "--spec-out", help=f"Chemin d'écriture de la spécification (défaut : ./{SPEC_FILENAME})."
    ),
    force: bool = typer.Option(False, "--force", help="Écrase un répertoire de sortie non vide."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Affiche l'arborescence sans rien écrire."
    ),
) -> None:
    """Construit un projet en répondant à une série de questions."""
    with _handled():
        spec = run_interview(QuestionaryPrompter(), default_project_name=Path.cwd().name.lower())
        target = output or Path(spec.project_name)

        if dry_run:
            _preview(spec, target)
            return

        spec_path = spec_file or Path(SPEC_FILENAME)
        save_spec(spec, spec_path)
        typer.echo(f"\nSpécification enregistrée : {spec_path}")
        _generate(spec, target, force=force)


@app.command()
def generate(
    spec_file: Path = typer.Option(
        Path(SPEC_FILENAME), "--spec", "-s", help="Spécification à rejouer."
    ),
    output: Path = typer.Option(
        None, "--output", "-o", help="Répertoire de sortie (défaut : ./<nom-du-projet>)."
    ),
    force: bool = typer.Option(False, "--force", help="Écrase un répertoire de sortie non vide."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Affiche l'arborescence sans rien écrire."
    ),
) -> None:
    """Génère le projet décrit par une spécification, sans aucune question."""
    with _handled():
        spec = load_spec(spec_file)
        target = output or Path(spec.project_name)
        if dry_run:
            _preview(spec, target)
            return
        _generate(spec, target, force=force)


@app.command()
def validate(
    spec_file: Path = typer.Option(
        Path(SPEC_FILENAME), "--spec", "-s", help="Spécification à vérifier."
    ),
) -> None:
    """Vérifie qu'une spécification est valide et résume ce qu'elle produirait."""
    with _handled():
        spec = load_spec(spec_file)
        artifacts = plan(spec)
        typer.echo(f"Spécification valide : {spec_file}")
        typer.echo(f"  Projet         : {spec.project_name}")
        typer.echo(f"  Environnements : {', '.join(env.name for env in spec.environments)}")
        typer.echo(f"  Groupes        : {', '.join(group.name for group in spec.groups)}")
        typer.echo(f"  Rôles          : {', '.join(spec.ordered_used_roles())}")
        typer.echo(f"  Fichiers       : {len(artifacts)}")


@app.command()
def catalog(
    role: str = typer.Argument(None, help="Détaille les options d'un seul rôle."),
) -> None:
    """Liste les rôles disponibles et leurs options."""
    with _handled():
        names = [role] if role else role_names()
        available = set(implemented_roles())
        for name in names:
            definition = get_role(name)
            state = "" if name in available else "   (templates non encore disponibles)"
            typer.echo(f"\n{definition.name}{state}\n  {definition.summary}")
            if definition.collections:
                typer.echo(f"  Collections : {', '.join(definition.collections)}")
            for option in definition.options:
                typer.echo(f"    - {definition.name}_{option.name} = {option.default!r}")
                typer.echo(f"      {option.description}")
                typer.echo(f"      Valeurs admises : {option.allowed}")


@app.command()
def check(
    project: Path = typer.Argument(
        Path("."), help="Répertoire du projet généré à vérifier (défaut : répertoire courant)."
    ),
) -> None:
    """Contrôle un projet généré avec ansible-playbook --syntax-check et ansible-lint."""
    with _handled():
        results = check_project(project)
        for result in results:
            typer.echo(
                f"[{'OK   ' if result.ok else 'ÉCHEC'}] {result.label}"
                f"  ({' '.join(result.command)})"
            )
            if not result.ok and result.output:
                typer.echo(result.output)

        failed = [result.label for result in results if not result.ok]
        if failed:
            typer.secho(
                f"\n{len(failed)} vérification(s) en échec : {', '.join(failed)}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)
        typer.secho(f"\n{len(results)} vérification(s) réussie(s).", fg=typer.colors.GREEN)


def _configure_console() -> None:
    """Force une sortie UTF-8.

    La console Windows utilise cp1252 par défaut : les accents et les caractères
    de l'arborescence (``├``, ``└``) y provoquent sinon une erreur d'encodage.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):  # flux non reconfigurable (redirection, tests)
            continue


def _generate(spec: ProjectSpec, target: Path, *, force: bool) -> None:
    """Écrit le projet et affiche un résumé."""
    written = write_artifacts(plan(spec), target, force=force)
    typer.echo(f"Projet généré : {target.resolve()}  ({len(written)} fichiers)")
    default_env = spec.environments[0].name
    typer.echo("\nÉtapes suivantes :")
    typer.echo(f"  cd {target}")
    typer.echo("  ansible-galaxy collection install -r requirements.yml")
    typer.echo(f"  ansible-playbook -i inventories/{default_env} playbooks/ping.yml")


def _preview(spec: ProjectSpec, target: Path) -> None:
    """Affiche l'arborescence qui serait produite, sans rien écrire."""
    paths = [artifact.posix_path for artifact in plan(spec)]
    typer.echo(build_tree(paths, target.name or spec.project_name))
    typer.echo(f"\n{len(paths)} fichiers seraient générés dans {target}.")
    typer.echo("\nMode --dry-run : aucun fichier n'a été écrit.")


class _handled:
    """Convertit les :class:`ForgeError` en message d'erreur et code de sortie 1."""

    def __enter__(self) -> "_handled":
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        if exc_type is not None and issubclass(exc_type, ForgeError):
            typer.secho(f"Erreur : {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from None
        return False
