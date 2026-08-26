"""Comment installer les outils qu'un pipeline doit lancer.

`Command` dit **quoi lancer**, jamais comment provisionner la machine qui le
lance : un outil s'installe differemment sur un runner Ubuntu, dans une image
Debian ou sur un poste, et rien de cela n'appartient au domaine qui declare la
commande. Cette table est donc **propre au plugin pipeline** — arbitrage pris en
phase 8, l'autre branche etant d'elargir le contrat de `Command`.

Consequence assumee : ce module cite des noms d'outils. Ce n'est pas connaitre un
domaine — `helm` est un binaire, pas une section de forge.yml, et un domaine
tiers qui declarerait `helm` dans ses commandes serait servi sans rien changer
ici. Un outil **absent de la table** n'est jamais devine : le pipeline engendre
une etape a completer, nommement, et le README du domaine le signale.

Les versions sont figees. Un pipeline qui installe « la derniere version » de ses
outils change de comportement un matin sans qu'on ait rien commit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Versions figees des outils installes par telechargement direct.
VERSIONS: dict[str, str] = {
    "helm": "3.16.3",
    "kubeconform": "0.6.7",
    "terraform": "1.9.8",
    "tflint": "0.59.1",
    "actionlint": "1.7.7",
    "promtool": "3.6.0",
}


@dataclass(frozen=True)
class ToolInstall:
    """Comment obtenir un outil sur un runner Linux."""

    #: Nom du binaire, tel que `Command.tool` le nomme.
    name: str

    #: Ce que l'outil fait, en une ligne.
    summary: str

    #: Lignes de shell installant l'outil. Executees dans l'ordre.
    steps: tuple[str, ...]

    #: Paquets systeme necessaires a l'installation elle-meme.
    requires: tuple[str, ...] = ()

    #: Variables d'environnement a poser une fois l'outil installe.
    exports: dict[str, str] = field(default_factory=dict)


def _release(url: str, binaire: str, archive: str) -> tuple[str, ...]:
    """Telecharge une archive de release, en extrait un binaire, l'installe."""
    extraction = (
        f"unzip -qo /tmp/{archive} -d /tmp"
        if archive.endswith(".zip")
        else f"tar -xzf /tmp/{archive} -C /tmp {binaire}"
    )
    return (
        f"curl -fsSL -o /tmp/{archive} {url}",
        extraction,
        f"install -m 0755 /tmp/{binaire} /usr/local/bin/{binaire}",
    )


#: Table des outils connus. Les deux outils Ansible partagent une entree par
#: binaire : `Command.tool` nomme le binaire, pas la distribution.
INSTALLS: tuple[ToolInstall, ...] = (
    ToolInstall(
        name="ansible-playbook",
        summary="execute les playbooks Ansible",
        steps=(
            "python3 -m pip install --quiet ansible-core",
            "ansible-galaxy collection install community.general ansible.posix "
            'community.postgresql -p "$HOME/.ansible/collections"',
        ),
        requires=("python3-pip",),
        exports={"ANSIBLE_COLLECTIONS_PATH": "$HOME/.ansible/collections"},
    ),
    ToolInstall(
        name="ansible-lint",
        summary="verifie les bonnes pratiques Ansible",
        steps=("python3 -m pip install --quiet ansible-core ansible-lint",),
        requires=("python3-pip",),
        exports={"ANSIBLE_COLLECTIONS_PATH": "$HOME/.ansible/collections"},
    ),
    ToolInstall(
        name="helm",
        summary="empaquette et deploie les charts Kubernetes",
        steps=(
            "curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/"
            f"get-helm-3 | bash -s -- --version v{VERSIONS['helm']}",
        ),
        requires=("curl",),
    ),
    ToolInstall(
        name="kubeconform",
        summary="valide des manifestes contre les schemas de l'API Kubernetes",
        steps=_release(
            "https://github.com/yannh/kubeconform/releases/download/"
            f"v{VERSIONS['kubeconform']}/kubeconform-linux-amd64.tar.gz",
            "kubeconform",
            "kubeconform.tar.gz",
        ),
        requires=("curl",),
    ),
    ToolInstall(
        name="terraform",
        summary="decrit et applique l'infrastructure",
        steps=_release(
            f"https://releases.hashicorp.com/terraform/{VERSIONS['terraform']}/"
            f"terraform_{VERSIONS['terraform']}_linux_amd64.zip",
            "terraform",
            "terraform.zip",
        ),
        requires=("curl", "unzip"),
    ),
    ToolInstall(
        name="tflint",
        summary="verifie les bonnes pratiques Terraform",
        steps=_release(
            "https://github.com/terraform-linters/tflint/releases/download/"
            f"v{VERSIONS['tflint']}/tflint_linux_amd64.zip",
            "tflint",
            "tflint.zip",
        ),
        requires=("curl", "unzip"),
    ),
    ToolInstall(
        name="actionlint",
        summary="verifie les workflows GitHub Actions",
        steps=_release(
            "https://github.com/rhysd/actionlint/releases/download/"
            f"v{VERSIONS['actionlint']}/actionlint_{VERSIONS['actionlint']}"
            "_linux_amd64.tar.gz",
            "actionlint",
            "actionlint.tar.gz",
        ),
        requires=("curl",),
    ),
    ToolInstall(
        name="yamllint",
        summary="verifie la forme d'un fichier YAML",
        steps=("python3 -m pip install --quiet yamllint",),
        requires=("python3-pip",),
    ),
    ToolInstall(
        name="promtool",
        summary="valide les regles d'alerte Prometheus",
        steps=_release(
            "https://github.com/prometheus/prometheus/releases/download/"
            f"v{VERSIONS['promtool']}/prometheus-{VERSIONS['promtool']}"
            ".linux-amd64.tar.gz",
            "promtool",
            "prometheus.tar.gz",
        ),
        requires=("curl",),
    ),
)

#: Table indexee par nom de binaire.
BY_NAME: dict[str, ToolInstall] = {outil.name: outil for outil in INSTALLS}


def known(name: str) -> bool:
    """Vrai si le plugin sait installer `name`."""
    return name in BY_NAME


def install(name: str) -> ToolInstall | None:
    """Recette d'installation de `name`, ou None si l'outil est inconnu."""
    return BY_NAME.get(name)


def resolve(names: tuple[str, ...]) -> tuple[list[ToolInstall], list[str]]:
    """Separe les outils connus des inconnus, dans l'ordre de `names`.

    Les inconnus ne sont **pas** une erreur : un domaine tiers peut lancer un
    outil que forge ne connait pas. Ils deviennent une etape a completer, visible
    dans le pipeline genere, plutot qu'une commande devinee.
    """
    connus: list[ToolInstall] = []
    inconnus: list[str] = []
    for nom in names:
        recette = BY_NAME.get(nom)
        if recette is None:
            inconnus.append(nom)
        else:
            connus.append(recette)
    return connus, inconnus


def system_packages(recettes: list[ToolInstall]) -> tuple[str, ...]:
    """Paquets systeme necessaires a l'ensemble des recettes, tries."""
    return tuple(sorted({paquet for recette in recettes for paquet in recette.requires}))
