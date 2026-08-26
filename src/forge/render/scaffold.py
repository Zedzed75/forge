"""Fichiers de niveau depot ecrits par le coeur (decision DESIGN.md §8 Q6).

En monorepo, `forge.yml`, l'index `README.md` et `.gitattributes` n'appartiennent
a aucun domaine : le coeur les ecrit lui-meme, en minimum non-domaine. Tout le
reste — y compris le `Makefile` de Helm ou le `.gitignore` d'Ansible — reste dans
le sous-repertoire de son domaine, qui doit rester autonome et supprimable.

Ces trois fichiers sont les seuls que forge ecrit **sans passer par copier**.
Consequence assumee, a connaitre : ils ne sont pas suivis par `copier update`,
donc `forge update` ne les rafraichit pas — c'est `forge generate` qui le fait.
`forge diff` les compare explicitement, pour ne jamais annoncer « a jour » sur
quelque chose qu'il n'aurait pas regarde.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge.errors import RenderError
from forge.plugins_api.types import DomainInfo
from forge.spec.io import SPEC_FILENAME, dump_spec

#: Contenu du `.gitattributes` de la cible : les comparaisons golden se font
#: octet pour octet, aucune conversion de fin de ligne n'est tolerable.
GITATTRIBUTES = """\
# Fins de ligne normalisees : la sortie de forge est comparee octet pour octet.
* text=auto eol=lf
"""

#: Fichiers de niveau depot que le coeur produit, dans l'ordre d'ecriture.
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
        # Un domaine dont la sortie est la racine du depot — un pipeline de CI,
        # que son outil ne lit qu'a un emplacement impose — n'a pas de
        # sous-repertoire a montrer.
        emplacement = (
            "racine du depot" if info.outdir in (".", "") else f"`{info.outdir}/`"
        )
        lines.append(f"| {info.title} | {emplacement} | {info.summary} |")
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
    """Contenu attendu des fichiers de niveau depot, sans rien ecrire.

    Sert a la fois a l'ecriture et a la comparaison (`forge diff`), pour que les
    deux ne puissent pas diverger.
    """
    names = [info.name for info in domains]
    return {
        SPEC_FILENAME: dump_spec(spec_data, sections=names),
        "README.md": _readme(spec_data.get("service", {}), domains),
        ".gitattributes": GITATTRIBUTES,
    }


def _existing_conflicts(target: Path, wanted: dict[str, str]) -> list[str]:
    """Fichiers deja presents dont le contenu differe de ce qui serait ecrit."""
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
    """Ecrit les fichiers de niveau depot et retourne la liste des chemins ecrits.

    `spec_path` designe la specification source. Quand elle **est** le
    `forge.yml` de la cible, il n'est pas reecrit : c'est la source de verite,
    editee a la main, et une reserialisation detruirait ses commentaires.

    Sans `force`, un fichier existant dont le contenu differe n'est pas ecrase :
    le coeur applique aux fichiers de niveau depot la meme regle que copier
    applique aux fichiers de domaine.
    """
    from forge.render.copier_runner import ensure_directory

    target = Path(target)
    ensure_directory(target, "repertoire cible")

    wanted = repo_files_content(spec_data, domains)
    if spec_path is not None:
        try:
            same = Path(spec_path).resolve() == (target / SPEC_FILENAME).resolve()
        except OSError:  # pragma: no cover - chemin invalide sur ce poste
            same = False
        if same:
            wanted.pop(SPEC_FILENAME, None)

    if not force:
        conflicts = _existing_conflicts(target, wanted)
        if conflicts:
            listing = "\n".join(f"    {name}" for name in conflicts)
            raise RenderError(
                f"{len(conflicts)} fichier(s) de niveau depot different(s) de ce que "
                f"forge produirait dans {target} :\n{listing}\n"
                "  relancez avec --force pour les ecraser, ou mettez vos "
                "modifications de cote."
            )

    written: list[Path] = []
    for name in REPO_FILENAMES:
        if name not in wanted:
            continue
        path = target / name
        try:
            path.write_text(wanted[name], encoding="utf-8", newline="\n")
        except OSError as exc:
            raise RenderError(f"ecriture impossible de {path} : {exc}") from exc
        written.append(path)
    return written
