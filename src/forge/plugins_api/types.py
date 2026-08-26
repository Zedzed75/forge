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

    #: Rang de deploiement : **le plus petit part le premier**. Le socle avant
    #: ce qui s'y pose — un namespace avant le chart qu'on y installe.
    #:
    #: Il existe parce qu'aucun tri generique ne pouvait le remplacer. L'ordre
    #: alphabetique deployait le chart avant l'infrastructure qui accueille son
    #: namespace ; l'ordre d'enregistrement aurait fait dependre un deploiement
    #: reel de l'ordre d'une liste de modules. C'est une propriete du domaine,
    #: donc le domaine la declare — le coeur se contente de trier.
    #:
    #: Le defaut place un domaine apres l'infrastructure et la configuration de
    #: machines : c'est le cas le plus frequent, celui d'une charge applicative.
    deploy_order: int = 50

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

    #: Variables d'environnement ajoutees a celles du processus, triees a
    #: l'execution pour rester deterministes. Certains outils ne se configurent
    #: que par ce canal — `ANSIBLE_COLLECTIONS_PATH`, `HELM_CACHE_HOME`… — et le
    #: plugin est le seul a savoir lesquelles lui sont necessaires.
    env: tuple[tuple[str, str], ...] = ()

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


@dataclass(frozen=True)
class DomainSummary:
    """Ce qu'un domaine demande par la specification declare de lui-meme.

    Assemble par le coeur a partir de hooks qui existaient deja — aucune
    nouvelle connaissance n'y entre. Sert au domaine `pipeline`, qui doit
    engendrer un job par domaine present **sans connaitre aucun domaine par son
    nom** : il ne lit ici que du vocabulaire du contrat (`DomainInfo`,
    `Command`, `Projection`).
    """

    #: Identite du domaine.
    info: DomainInfo

    #: Ce que le domaine affirme produire, ou None s'il ne le declare pas.
    projection: Projection | None = None

    #: Commandes de validation, chemins **relatifs a la racine du projet**.
    validators: tuple[Command, ...] = ()

    #: Commandes de deploiement, par environnement, dans l'ordre de la
    #: specification : `(("prod", (cmd, ...)), ...)`. Vide si le domaine ne
    #: declare pas comment se deployer — auquel cas le pipeline genere une
    #: etape a completer plutot que d'inventer une commande.
    deployments: tuple[tuple[str, tuple[Command, ...]], ...] = ()

    @property
    def name(self) -> str:
        """Nom du domaine."""
        return self.info.name

    def tools(self) -> tuple[str, ...]:
        """Outils externes cites par ce domaine, tries et dedoublonnes."""
        cites = {commande.tool for commande in self.validators}
        cites |= {
            commande.tool for _, commandes in self.deployments for commande in commandes
        }
        return tuple(sorted(cites))


@dataclass(frozen=True)
class GenerationContext:
    """Vue du coeur sur les domaines demandes, passee a `forge_answers`.

    Le coeur n'ordonnance rien : il transmet des faits qu'il calcule deja, dans
    le vocabulaire du contrat. C'est le plugin qui decide quoi en faire.
    """

    #: Domaines demandes par la specification, dans l'ordre d'enregistrement.
    domains: tuple[DomainSummary, ...] = ()

    def names(self) -> tuple[str, ...]:
        """Noms des domaines demandes."""
        return tuple(sommaire.name for sommaire in self.domains)

    def get(self, name: str) -> DomainSummary | None:
        """Sommaire du domaine `name`, ou None s'il n'est pas demande."""
        for sommaire in self.domains:
            if sommaire.name == name:
                return sommaire
        return None

    def others(self, name: str) -> tuple[DomainSummary, ...]:
        """Tous les domaines demandes sauf `name`."""
        return tuple(sommaire for sommaire in self.domains if sommaire.name != name)

    def tools(self) -> tuple[str, ...]:
        """Outils externes cites par l'ensemble des domaines, tries."""
        return tuple(sorted({outil for s in self.domains for outil in s.tools()}))
