"""Fichiers de niveau depot ecrits par le coeur (decision DESIGN.md §8 Q6).

En monorepo, `forge.yml`, l'index `README.md` et `.gitattributes` n'appartiennent
a aucun domaine : le coeur les ecrit lui-meme, en minimum non-domaine. Tout le
reste — y compris le `Makefile` de Helm ou le `.gitignore` d'Ansible — reste dans
le sous-repertoire de son domaine, qui doit rester autonome et supprimable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge.plugins_api.types import DomainInfo
from forge.spec.io import SPEC_FILENAME, save_spec

#: Contenu du `.gitattributes` de la cible : les comparaisons golden se font
#: octet pour octet, aucune conversion de fin de ligne n'est tolerable.
GITATTRIBUTES = """\
# Fins de ligne normalisees : la sortie de forge est comparee octet pour octet.
* text=auto eol=lf
"""


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
        lines.append(f"| {info.title} | `{info.outdir}/` | {info.summary} |")
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


def write_repo_files(
    target: Path, spec_data: dict[str, Any], domains: list[DomainInfo]
) -> list[Path]:
    """Ecrit les fichiers de niveau depot et retourne la liste des chemins ecrits."""
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    spec_path = target / SPEC_FILENAME
    save_spec(spec_data, spec_path, sections=[info.name for info in domains])
    written.append(spec_path)

    readme = target / "README.md"
    readme.write_text(
        _readme(spec_data.get("service", {}), domains), encoding="utf-8", newline="\n"
    )
    written.append(readme)

    gitattributes = target / ".gitattributes"
    gitattributes.write_text(GITATTRIBUTES, encoding="utf-8", newline="\n")
    written.append(gitattributes)

    return written
