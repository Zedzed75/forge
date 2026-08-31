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

from forge.errors import SpecFileError, SpecValidationError
from forge.plugins_api.manager import DomainHooks, ForgeManager
from forge.plugins_api.types import DomainInfo, Issue, Projection
from forge.render import copier_runner, scaffold
from forge.render.diff import DomainDiff, count_changed_lines, diff_trees
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

    #: Constats de niveau `warning` remontes par les plugins avant le rendu.
    #: Les erreurs, elles, ont deja arrete la generation.
    warnings: list[Issue] = field(default_factory=list)

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


def indexed_domains(spec: ForgeSpecBase, manager: ForgeManager) -> list[DomainInfo]:
    """Domaines que la specification demande, quel que soit le filtre `--only`.

    C'est cette liste — et non celle des domaines effectivement rendus — qui
    alimente l'index de niveau depot : un `--only ansible` ne doit pas faire
    disparaitre `helm/` du README d'un projet ou la section `helm:` existe.
    """
    return [manager.domain(name).info for name in spec.domain_names()]


def check_spec(spec: ForgeSpecBase, manager: ForgeManager, names: list[str]) -> list[Issue]:
    """Interroge chaque domaine sur la coherence de la specification.

    Appele **avant tout rendu** : un sous-modele de plugin ne voit que sa
    propre section, il ne peut donc pas verifier seul ce qui touche au bloc
    partage `service:`. Sans ce controle, une specification incoherente serait
    generee sans broncher et l'erreur ne sortirait qu'au `forge validate`
    suivant (arbitrage R2 de la revue d'interface).
    """
    issues: list[Issue] = []
    for name in names:
        issues.extend(manager.domain(name).check_spec(spec))
    return issues


def raise_on_errors(issues: list[Issue]) -> list[Issue]:
    """Arrete sur les erreurs, retourne les avertissements a afficher."""
    erreurs = [issue for issue in issues if issue.level == "error"]
    if erreurs:
        detail = "\n".join(
            f"  - {issue.message}" + (f"\n    -> {issue.hint}" if issue.hint else "")
            for issue in erreurs
        )
        raise SpecValidationError(
            f"specification incoherente ({len(erreurs)} erreur(s)) :\n{detail}"
        )
    return [issue for issue in issues if issue.level == "warning"]


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
    spec_path: Path | None = None,
) -> GenerationResult:
    """Rend tous les domaines demandes sous `target/<outdir>`."""
    target = Path(target)
    names = resolve_domains(spec, manager, only)
    result = GenerationResult(target=target, domains=names, dry_run=dry_run)
    # Les controles croises passent AVANT le rendu : mieux vaut ne rien ecrire
    # que d'ecrire un projet qu'on sait incoherent.
    result.warnings = raise_on_errors(check_spec(spec, manager, names))
    if dry_run:
        return result

    copier_runner.ensure_directory(target, "repertoire cible")
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
    # Les fichiers de niveau depot sont ecrits en dernier : un echec de rendu ne
    # doit pas laisser derriere lui l'index d'un projet qui n'existe pas.
    result.repo_files = scaffold.write_repo_files(
        target,
        spec_data,
        indexed_domains(spec, manager),
        force=force,
        spec_path=spec_path,
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
    """Rejoue `copier update` sur chaque domaine deja genere sous `target`.

    `update` ne lit pas de `forge.yml` : le filtre `--only` est donc valide
    contre les domaines **enregistres**, pas contre une specification. Un nom
    inconnu doit echouer ici, sinon une faute de frappe dans un script de CI
    produirait « aucun domaine mis a jour » et un code de retour 0.
    """
    target = Path(target)
    updated: list[str] = []
    if only is not None:
        unknown = [name for name in only if name not in manager.domain_names()]
        if unknown:
            known = ", ".join(manager.domain_names()) or "aucun"
            raise SpecValidationError(
                f"domaine(s) inconnu(s) : {', '.join(unknown)} (enregistres : {known})"
            )
    src = copier_runner.template_root()
    for info in manager.domains():
        if only is not None and info.name not in only:
            continue
        outdir = target / info.outdir
        if not (outdir / copier_runner.ANSWERS_FILENAME).is_file():
            if only is not None:
                # Domaine nomme explicitement mais jamais genere : le silence
                # ferait passer une CI au vert sans rien mettre a jour. Le
                # message est celui, deja formule, de `run_update`.
                copier_runner.run_update(dst=outdir, src=src, ref=ref, conflict=conflict)
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


#: Nom donne, dans un rapport de comparaison, aux fichiers de niveau depot.
ROOT_LABEL = "(racine)"


def foreign_paths(
    spec_data: dict[str, Any],
    spec: ForgeSpecBase,
    manager: ForgeManager,
    name: str,
) -> frozenset[str]:
    """Ce qu'un domaine ecrivant a la racine du depot ne doit pas comparer.

    Un domaine dont `DomainInfo.outdir` vaut `.` — le domaine `pipeline`, dont
    les fichiers n'ont de sens que la ou l'outil de CI les lit — partage sa
    racine avec les autres domaines et avec les fichiers de niveau depot.
    Comparer sa cible a un rendu neuf sans les ecarter les declarerait tous
    supprimes.

    Retourne un ensemble vide pour tout domaine ecrivant dans son propre
    sous-repertoire : le cas normal ne paie rien.
    """
    info = manager.domain(name).info
    if info.outdir not in (".", ""):
        return frozenset()
    autres = {
        autre.outdir
        for autre in indexed_domains(spec, manager)
        if autre.name != name and autre.outdir not in (".", "")
    }
    return frozenset(autres | set(scaffold.repo_files_content(spec_data, [])))


def diff_repo_files(
    spec_data: dict[str, Any],
    spec: ForgeSpecBase,
    manager: ForgeManager,
    target: Path,
    *,
    spec_path: Path | None = None,
) -> DomainDiff:
    """Compare les fichiers de niveau depot a ce que forge produirait.

    Ils ne passent pas par copier (cf. `render/scaffold`) : sans cette
    comparaison, `forge diff` annoncerait « a jour » sur des fichiers qu'il
    n'aurait jamais regardes.
    """
    wanted = scaffold.repo_files_content(spec_data, indexed_domains(spec, manager))
    if spec_path is not None:
        try:
            if Path(spec_path).resolve() == (target / SPEC_FILENAME).resolve():
                # Source de verite editee a la main : sa mise en forme n'a pas a
                # correspondre a une reserialisation.
                wanted.pop(SPEC_FILENAME, None)
        except OSError:  # pragma: no cover - chemin invalide sur ce poste
            pass

    result = DomainDiff(domain=ROOT_LABEL)
    for name in sorted(wanted):
        path = target / name
        if not path.is_file():
            result.added.append(name)
            continue
        try:
            current = path.read_bytes().decode("utf-8")
        except (UnicodeDecodeError, OSError):
            result.modified.append((name, -1))
            continue
        if current != wanted[name]:
            result.modified.append(
                (name, count_changed_lines(current, wanted[name]))
            )
    return result


def diff(
    spec_data: dict[str, Any],
    spec: ForgeSpecBase,
    manager: ForgeManager,
    target: Path,
    *,
    only: list[str] | None = None,
    ref: str = copier_runner.DEFAULT_REF,
    spec_path: Path | None = None,
) -> list[DomainDiff]:
    """Compare la cible a un rendu neuf, domaine par domaine (resume seul)."""
    target = Path(target)
    names = resolve_domains(spec, manager, only)
    src = copier_runner.template_root()
    diffs: list[DomainDiff] = []
    if only is None:
        diffs.append(
            diff_repo_files(spec_data, spec, manager, target, spec_path=spec_path)
        )
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
            diffs.append(
                diff_trees(
                    name,
                    target / hooks.info.outdir,
                    fresh,
                    ignore=foreign_paths(spec_data, spec, manager, name),
                )
            )
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

    result.issues.extend(check_spec(spec, manager, names))
    result.issues.extend(compare_projections(projections))
    result.issues.extend(manager.consistency(spec, outdirs))
    return result
