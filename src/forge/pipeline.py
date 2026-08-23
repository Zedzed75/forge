"""Enchainement des operations de forge, independamment de la CLI.

La CLI ne fait que lire des arguments et afficher des resultats ; tout ce qui
suit est appelable depuis les tests sans terminal. Chaque operation part d'un
`forge.yml` deja charge et d'un gestionnaire de plugins, jamais d'un etat global.
"""

from __future__ import annotations

import importlib.util
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from forge.errors import SpecFileError
from forge.plugins_api.manager import DomainHooks, ForgeManager
from forge.plugins_api.types import DomainInfo, Issue, Projection
from forge.render import copier_runner, scaffold
from forge.render.diff import DomainDiff, diff_trees
from forge.spec.assembly import ForgeSpecBase, resolve_domains, validate_spec
from forge.spec.io import SPEC_FILENAME, load_spec_data
from forge.validate.consistency import compare_projections
from forge.validate.runner import Report, run_commands


@dataclass
class GenerationResult:
    """Ce qu'une generation a produit."""

    target: Path
    domains: list[str] = field(default_factory=list)
    repo_files: list[Path] = field(default_factory=list)
    dry_run: bool = False

    def summary(self) -> str:
        """Resume d'une ligne — jamais l'arborescence complete."""
        prefix = "simulation : " if self.dry_run else ""
        listed = ", ".join(self.domains) or "aucun"
        return f"{prefix}{self.target} — domaines : {listed}"


@dataclass
class ValidationResult:
    """Rapports par domaine et constats inter-domaines."""

    reports: list[Report] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Vrai si aucun rapport n'echoue et aucun constat n'est une erreur."""
        return all(report.ok for report in self.reports) and not any(
            issue.level == "error" for issue in self.issues
        )


def load_spec(spec_path: Path, manager: ForgeManager) -> tuple[dict[str, Any], ForgeSpecBase]:
    """Charge `forge.yml` et retourne (dict brut, instance validee)."""
    data = load_spec_data(spec_path)
    return data, validate_spec(data, manager)


def find_spec_file(spec_path: Path | None, target: Path) -> Path:
    """Resout le chemin du `forge.yml` : celui demande, sinon celui de la cible."""
    if spec_path is not None:
        return Path(spec_path)
    candidate = Path(target) / SPEC_FILENAME
    if candidate.is_file():
        return candidate
    local = Path(SPEC_FILENAME)
    if local.is_file():
        return local
    raise SpecFileError(
        f"aucune specification trouvee : ni {candidate}, ni ./{SPEC_FILENAME}. "
        "Precisez --spec."
    )


def plugin_jinja_module(hooks: DomainHooks) -> str:
    """Module de filtres du plugin, s'il en fournit un (convention `jinja_ext`).

    Un plugin enrichit ainsi l'environnement Jinja sans toucher au copier.yml
    racine ni au coeur.
    """
    module_name = getattr(hooks.plugin, "__name__", "")
    if not module_name:
        return ""
    package = module_name.rsplit(".", 1)[0]
    candidate = f"{package}.jinja_ext"
    try:
        if importlib.util.find_spec(candidate) is not None:
            return candidate
    except (ImportError, ValueError):  # pragma: no cover - depend de l'installation
        return ""
    return ""


def domain_data(spec: ForgeSpecBase, hooks: DomainHooks) -> dict[str, Any]:
    """Assemble les reponses copier d'un domaine."""
    return copier_runner.build_data(
        plugin=hooks.name,
        template_subdir=hooks.template_subdir(),
        forge_version=spec.forge_version,
        service=spec.service.model_dump(mode="json"),
        domain=hooks.answers(spec),
    )


def generate(
    spec_data: dict[str, Any],
    spec: ForgeSpecBase,
    manager: ForgeManager,
    target: Path,
    *,
    only: list[str] | None = None,
    ref: str = copier_runner.DEFAULT_REF,
    force: bool = False,
    dry_run: bool = False,
) -> GenerationResult:
    """Rend tous les domaines demandes sous `target/<outdir>`."""
    target = Path(target)
    names = resolve_domains(spec, manager, only)
    infos: list[DomainInfo] = [manager.domain(name).info for name in names]
    result = GenerationResult(target=target, domains=names, dry_run=dry_run)
    if dry_run:
        return result

    result.repo_files = scaffold.write_repo_files(target, spec_data, infos)
    src = copier_runner.template_root()
    for name in names:
        hooks = manager.domain(name)
        copier_runner.run_copy(
            dst=target / hooks.info.outdir,
            data=domain_data(spec, hooks),
            src=src,
            ref=ref,
            force=force,
            plugin_jinja=plugin_jinja_module(hooks),
        )
    return result


def update(
    manager: ForgeManager,
    target: Path,
    *,
    only: list[str] | None = None,
    ref: str = copier_runner.DEFAULT_REF,
    conflict: str = "inline",
) -> list[str]:
    """Rejoue `copier update` sur chaque domaine deja genere sous `target`."""
    target = Path(target)
    updated: list[str] = []
    src = copier_runner.template_root()
    for info in manager.domains():
        if only is not None and info.name not in only:
            continue
        outdir = target / info.outdir
        if not (outdir / copier_runner.ANSWERS_FILENAME).is_file():
            continue
        copier_runner.run_update(
            dst=outdir,
            src=src,
            ref=ref,
            conflict=conflict,
            plugin_jinja=plugin_jinja_module(manager.domain(info.name)),
        )
        updated.append(info.name)
    return updated


def diff(
    spec: ForgeSpecBase,
    manager: ForgeManager,
    target: Path,
    *,
    only: list[str] | None = None,
    ref: str = copier_runner.DEFAULT_REF,
) -> list[DomainDiff]:
    """Compare la cible a un rendu neuf, domaine par domaine (resume seul)."""
    target = Path(target)
    names = resolve_domains(spec, manager, only)
    src = copier_runner.template_root()
    diffs: list[DomainDiff] = []
    for name in names:
        hooks = manager.domain(name)
        with tempfile.TemporaryDirectory(prefix="forge-diff-") as tmp:
            fresh = Path(tmp) / hooks.info.outdir
            copier_runner.run_copy(
                dst=fresh,
                data=domain_data(spec, hooks),
                src=src,
                ref=ref,
                force=True,
                plugin_jinja=plugin_jinja_module(hooks),
            )
            diffs.append(diff_trees(name, target / hooks.info.outdir, fresh))
    return diffs


def validate(
    spec: ForgeSpecBase,
    manager: ForgeManager,
    target: Path,
    *,
    only: list[str] | None = None,
    skip_missing: bool = False,
) -> ValidationResult:
    """Lance les validateurs de chaque domaine puis les controles inter-domaines."""
    target = Path(target)
    names = resolve_domains(spec, manager, only)
    result = ValidationResult()
    projections: dict[str, Projection] = {}
    outdirs: dict[str, Path] = {}

    for name in names:
        hooks = manager.domain(name)
        outdir = target / hooks.info.outdir
        outdirs[name] = outdir
        commands = hooks.validators(spec, outdir)
        result.reports.append(
            run_commands(name, commands, outdir, skip_missing=skip_missing)
        )
        projection = hooks.projection(spec)
        if projection is not None:
            projections[name] = projection

    result.issues.extend(compare_projections(projections))
    result.issues.extend(manager.consistency(spec, outdirs))
    return result
