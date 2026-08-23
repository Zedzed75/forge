"""Types echanges entre le coeur et les plugins (DESIGN.md §2.1).

Tous immuables : un plugin ne peut pas modifier apres coup ce qu'il a declare,
et le coeur peut les comparer / les hacher sans surprise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class DomainInfo:
    """Identite d'un domaine generable."""

    #: Cle de section dans forge.yml et nom du plugin (ex. "ansible").
    name: str

    #: Libelle d'affichage (ex. "Ansible").
    title: str

    #: Resume d'une ligne, affiche par `forge plugins`.
    summary: str

    #: Sous-repertoire de sortie dans la cible ; par defaut identique a `name`.
    outdir: str = ""

    def __post_init__(self) -> None:
        if not self.outdir:
            object.__setattr__(self, "outdir", self.name)


@dataclass(frozen=True)
class Command:
    """Une commande externe de validation declaree par un plugin."""

    #: Libelle repris tel quel dans le rapport (ex. "helm lint (prod)").
    label: str

    #: Binaire a localiser (ex. "helm", "ansible-lint").
    tool: str

    #: Arguments, sans le binaire.
    argv: tuple[str, ...] = ()

    #: Repertoire d'execution ; defaut : le repertoire du domaine.
    cwd: Path | None = None

    #: Libelle d'une commande dont stdout alimente le stdin de celle-ci.
    stdin_from: str | None = None

    #: Delai maximal d'execution, en secondes.
    timeout: int = 300

    #: Message affiche si le binaire est absent du PATH.
    install_hint: str = ""

    #: Autorise le repli WSL sous Windows (outil qui ne tourne pas nativement).
    requires_linux: bool = False


@dataclass(frozen=True)
class Issue:
    """Un constat de validation inter-domaines."""

    #: "error" fait echouer `forge validate` ; "warning" est seulement signale.
    level: Literal["error", "warning"]

    #: Phrase actionnable decrivant le probleme.
    message: str

    #: Correction suggeree.
    hint: str = ""

    #: Domaines concernes, pour situer le constat.
    domains: tuple[str, ...] = ()


@dataclass(frozen=True)
class Projection:
    """Ce qu'un domaine affirme produire, sans vocabulaire de domaine.

    Le coeur compare les projections entre elles : deux domaines qui declarent
    la meme facette doivent declarer la meme valeur. C'est ce mecanisme — et non
    des regles « si ansible alors… » — qui implemente les controles
    inter-domaines (DESIGN.md §2.1, decision Q4).
    """

    #: Nom du service tel que ce domaine l'emploie.
    service_name: str

    #: Environnements que ce domaine materialise, dans l'ordre.
    environments: tuple[str, ...]

    #: Labels que ce domaine appose sur ce qu'il produit.
    labels: dict[str, str] = field(default_factory=dict)

    #: Facettes libres ; comparees seulement si deux domaines les declarent.
    facets: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class CatalogEntry:
    """Un element du catalogue d'un domaine (role Ansible, composant Helm...)."""

    #: Identifiant employe dans forge.yml.
    name: str

    #: Resume d'une ligne.
    summary: str

    #: Description longue, affichee par `forge catalog <domaine> <element>`.
    details: str = ""

    #: Options reconnues : nom -> description.
    options: dict[str, str] = field(default_factory=dict)
