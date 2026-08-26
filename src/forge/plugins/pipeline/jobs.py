"""Derivation des jobs a partir de ce que les autres domaines declarent.

Le coeur de la phase 8. **Aucun nom de domaine n'apparait ici** : tout vient du
`GenerationContext`, qui ne parle que `DomainInfo`, `Command` et `Projection`.
Ajouter un domaine a forge ajoute donc un job a ce pipeline sans qu'une ligne de
ce module change — c'est la propriete a preserver.

Trois traductions non triviales sont faites ici, et elles meritent d'etre lues :

* **le chainage par stdin.** `forge validate` execute `kubeconform` sur la sortie
  de `helm template` en gardant celle-ci en memoire. Un fichier de CI n'a pas
  cette memoire : la source ecrit dans un fichier, le consommateur le relit. Une
  redirection plutot qu'un tube, parce que `pipefail` n'existe pas dans le
  `/bin/sh` d'une image Debian et qu'un tube y masquerait l'echec de la source.
* **le repertoire de travail.** `Command.cwd` est un chemin relatif a la racine
  du projet — le coeur le construit ainsi pour ce module. Il devient
  `working-directory` chez GitHub, un `cd` chez GitLab.
* **l'approbation humaine.** GitLab la declare dans le fichier (`when: manual`) ;
  GitHub la declare dans les reglages du depot, le fichier ne portant que le nom
  de l'environnement. Le gabarit GitHub le dit en commentaire plutot que de
  laisser croire que le fichier suffit.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import Any

from forge.plugins.pipeline import tools
from forge.plugins.pipeline.enums import JobKind
from forge.plugins_api.types import Command, DomainSummary, GenerationContext

#: Prefixe des fichiers intermediaires du chainage stdin.
STDIN_PREFIX = "/tmp/forge-"


@dataclass
class Step:
    """Une etape de job : un libelle, des lignes de shell, un contexte."""

    name: str
    run: list[str] = field(default_factory=list)
    workdir: str = ""
    env: dict[str, str] = field(default_factory=dict)

    def script(self) -> list[str]:
        """Lignes autonomes : repertoire et variables portes par la ligne elle-meme.

        GitLab n'a ni `working-directory` ni variables par etape — un job est un
        seul script. Le `cd` est enferme dans un sous-shell pour qu'il ne fuie
        pas sur la ligne suivante.
        """
        prefixe = "".join(f"{cle}={shlex.quote(valeur)} " for cle, valeur in sorted(self.env.items()))
        lignes = []
        for ligne in self.run:
            complete = prefixe + ligne
            if self.workdir:
                complete = f"(cd {shlex.quote(self.workdir)} && {complete})"
            lignes.append(complete)
        return lignes

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "run": self.run,
            "workdir": self.workdir,
            "env": self.env,
            "script": self.script(),
        }


@dataclass
class Job:
    """Un job du pipeline."""

    key: str
    name: str
    kind: str
    steps: list[Step] = field(default_factory=list)
    needs: list[str] = field(default_factory=list)
    environment: str = ""
    manual: bool = False
    default_branch_only: bool = False
    #: Outils que ce job installe, et ceux qu'il ne sait pas installer.
    tool_names: list[str] = field(default_factory=list)
    unknown_tools: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "kind": self.kind,
            "steps": [step.as_dict() for step in self.steps],
            "needs": self.needs,
            "environment": self.environment,
            "manual": self.manual,
            "default_branch_only": self.default_branch_only,
            "tools": self.tool_names,
            "unknown_tools": self.unknown_tools,
        }


# ---------------------------------------------------------------------------
# Traduction d'une Command en etape
# ---------------------------------------------------------------------------


def _slug(label: str) -> str:
    """Identifiant de fichier derive d'un libelle de commande."""
    garde = [c if c.isalnum() else "-" for c in label.lower()]
    return "".join(garde).strip("-").replace("---", "-").replace("--", "-")


def _shell(command: Command, redirection: str = "") -> str:
    """Ligne de shell equivalente a une commande, arguments cites au besoin."""
    morceaux = [command.tool, *command.argv]
    ligne = " ".join(shlex.quote(morceau) for morceau in morceaux)
    return f"{ligne} {redirection}".rstrip()


def portable_env(command: Command) -> dict[str, str]:
    """Variables d'environnement d'une commande, purgees de ce qui est local.

    `Command.env` configure une execution **sur le poste** : le chemin des
    collections Ansible, un cache de providers Terraform, un miroir de schemas
    Kubernetes. Ces valeurs sont lues dans l'environnement du processus au
    moment de la generation ; les recopier dans un fichier de CI y ecrirait le
    chemin d'un poste de developpement, et rendrait la sortie **dependante de la
    machine qui l'a engendree** — un fichier golden ne pourrait plus etre
    compare.

    Le critere est volontairement grossier — une valeur qui ressemble a un
    chemin est ecartee — mais il est sur dans le bon sens : ce qui reste
    (`NO_COLOR=1`, `TF_IN_AUTOMATION=1`) est du reglage de comportement, valable
    partout. Ce qu'un outil a besoin de trouver sur le runner est fourni par sa
    recette d'installation, ecrite pour le runner.
    """
    return {
        cle: valeur
        for cle, valeur in command.env
        if not _ressemble_a_un_chemin(valeur)
    }


def _ressemble_a_un_chemin(valeur: str) -> bool:
    """Vrai si la valeur designe un emplacement du systeme de fichiers."""
    return "/" in valeur or "\\" in valeur or (len(valeur) > 1 and valeur[1] == ":")


def _workdir(command: Command) -> str:
    """Repertoire de travail, relatif a la racine du projet."""
    if command.cwd is None:
        return ""
    chemin = command.cwd.as_posix()
    return "" if chemin in (".", "") else chemin


def steps_for(commands: tuple[Command, ...]) -> list[Step]:
    """Traduit une suite de `Command` en etapes, chainage stdin compris."""
    sources = {
        commande.stdin_from for commande in commands if commande.stdin_from
    }
    etapes: list[Step] = []
    for commande in commands:
        redirection = ""
        if commande.label in sources:
            redirection = f"> {STDIN_PREFIX}{_slug(commande.label)}.out"
        elif commande.stdin_from:
            redirection = f"< {STDIN_PREFIX}{_slug(commande.stdin_from)}.out"
        etapes.append(
            Step(
                name=commande.label,
                run=[_shell(commande, redirection)],
                workdir=_workdir(commande),
                env=portable_env(commande),
            )
        )
    return etapes


def install_step(
    noms: tuple[str, ...], provider: str
) -> tuple[Step | None, list[str], list[str]]:
    """Etape d'installation des outils, et le partage connus / inconnus.

    Les variables posees par une recette ne se transmettent pas de la meme
    facon : chaque `run:` de GitHub est un shell neuf, et seul un ecrit dans
    `$GITHUB_ENV` survit a l'etape suivante ; un job GitLab est un seul shell,
    ou un `export` suffit.
    """
    connus, inconnus = tools.resolve(noms)
    lignes: list[str] = []
    paquets = tools.system_packages(connus)
    if paquets:
        lignes.append(
            "if command -v apt-get >/dev/null; then apt-get update -qq && "
            f"apt-get install -y -qq --no-install-recommends {' '.join(paquets)}; fi"
        )
    exports: dict[str, str] = {}
    for recette in connus:
        lignes.extend(recette.steps)
        exports.update(recette.exports)
    for cle, valeur in sorted(exports.items()):
        if provider == "github":
            lignes.append(f'echo "{cle}={valeur}" >> "$GITHUB_ENV"')
        else:
            lignes.append(f'export {cle}="{valeur}"')
    for inconnu in inconnus:
        # Jamais devine : l'etape echoue en nommant l'outil manquant, plutot que
        # de laisser le job echouer plus loin sur un « command not found ».
        lignes.append(
            f'echo "forge ne sait pas installer {inconnu} : completez cette etape" >&2'
        )
        lignes.append("exit 1")
    if not lignes:
        return None, [recette.name for recette in connus], inconnus
    return (
        Step(name="Installer les outils", run=lignes),
        [recette.name for recette in connus],
        inconnus,
    )


# ---------------------------------------------------------------------------
# Construction des jobs
# ---------------------------------------------------------------------------


def _job_for_commands(
    key: str, name: str, kind: JobKind, commands: tuple[Command, ...], provider: str
) -> Job:
    """Job installant ce qu'il faut, puis lancant `commands` dans l'ordre."""
    noms = tuple(sorted({commande.tool for commande in commands}))
    installation, connus, inconnus = install_step(noms, provider)
    etapes = [installation] if installation else []
    etapes += steps_for(commands)
    return Job(
        key=key,
        name=name,
        kind=kind.value,
        steps=etapes,
        tool_names=connus,
        unknown_tools=inconnus,
    )


def validate_jobs(context: GenerationContext, provider: str) -> list[Job]:
    """Un job de validation par domaine demande, y compris le pipeline lui-meme.

    Le domaine `pipeline` valide sa propre sortie : c'est un domaine comme un
    autre du point de vue de ce module, et l'exclure serait le seul endroit ou
    il se traiterait a part.
    """
    jobs: list[Job] = []
    for sommaire in context.domains:
        if not sommaire.validators:
            continue
        jobs.append(
            _job_for_commands(
                key=f"valider-{sommaire.name}",
                name=f"Valider {sommaire.info.title}",
                kind=JobKind.VALIDATE,
                commands=sommaire.validators,
                provider=provider,
            )
        )
    return jobs


def build_job(build: Any, service_name: str, provider: str) -> Job:
    """Job de construction et de publication de l'image.

    Aucun identifiant n'est ecrit : la connexion au registre emploie le jeton que
    l'outil de CI fournit deja (`GITHUB_TOKEN`, `CI_REGISTRY_PASSWORD`).
    """
    image = build.image or service_name
    reference = f"{build.registry}/{image}"
    plateformes = ",".join(build.platforms)
    lignes = [
        "docker buildx create --use --name forge-builder 2>/dev/null || "
        "docker buildx use forge-builder",
        " ".join(
            [
                "docker buildx build",
                f"--platform {plateformes}",
                f"--file {shlex.quote(build.dockerfile)}",
                f"--tag {shlex.quote(reference)}:$FORGE_IMAGE_TAG",
                "--push" if build.push else "--load",
                shlex.quote(build.context),
            ]
        ),
    ]
    job = Job(
        key="construire",
        name="Construire l'image",
        kind=JobKind.BUILD.value,
        steps=[Step(name=f"docker buildx build ({reference})", run=lignes)],
        default_branch_only=build.push,
    )
    job.steps[0].env = {"FORGE_IMAGE_TAG": _tag_expression(provider)}
    return job


def _tag_expression(provider: str) -> str:
    """Expression donnant le tag de l'image, propre a chaque outil de CI.

    Le tag est l'empreinte du commit, jamais `latest` : deux constructions du
    meme `latest` produisent deux images differentes sous le meme nom, et rien
    ne dit laquelle tourne.
    """
    return "${{ github.sha }}" if provider == "github" else "$CI_COMMIT_SHA"


def deploy_jobs(
    context: GenerationContext,
    environments: tuple[str, ...],
    production: str,
    provider: str,
    *,
    manual_for_production: bool,
    sequential: bool,
    needs: list[str],
) -> list[Job]:
    """Un job de deploiement par environnement, tous domaines confondus.

    Un seul job par environnement plutot qu'un par couple (domaine,
    environnement) : dans un meme environnement, les domaines se deploient dans
    l'ordre qu'ils declarent eux-memes (`DomainInfo.deploy_order`) — le socle
    avant ce qui s'y pose. Trier par nom aurait fait partir un chart avant
    l'infrastructure qui cree son namespace, ce qu'aucun tri generique ne
    pouvait deviner.
    """
    ordonnes = sorted(context.domains, key=lambda s: (s.info.deploy_order, s.name))
    jobs: list[Job] = []
    precedent: str | None = None
    for nom in environments:
        commandes: list[Command] = []
        for sommaire in ordonnes:
            commandes.extend(_deployment_for(sommaire, nom))
        if not commandes:
            continue
        job = _job_for_commands(
            key=f"deployer-{nom}",
            # Libelle affiche par l'outil de CI : accentue, comme tout ce que
            # forge ecrit dans un fichier genere. La cle, elle, reste un
            # identifiant ASCII.
            name=f"Déployer {nom}",
            kind=JobKind.DEPLOY,
            commands=tuple(commandes),
            provider=provider,
        )
        job.environment = nom
        job.default_branch_only = True
        job.manual = manual_for_production and nom == production
        job.needs = list(needs) + ([precedent] if sequential and precedent else [])
        jobs.append(job)
        precedent = job.key
    return jobs


def _deployment_for(sommaire: DomainSummary, environment: str) -> tuple[Command, ...]:
    """Commandes de deploiement du domaine pour cet environnement, ou rien."""
    for nom, commandes in sommaire.deployments:
        if nom == environment:
            return commandes
    return ()


def undeployed(
    context: GenerationContext, environments: tuple[str, ...], self_name: str
) -> list[str]:
    """Domaines demandes qui ne disent pas comment se deployer.

    Le pipeline n'invente pas leur commande : il les nomme, pour que l'absence
    d'un job de deploiement soit un constat et non un oubli.

    Le domaine appelant s'exclut : un pipeline ne se deploie pas, il est le
    deploiement. C'est le **seul** endroit de ce module ou un domaine est traite
    autrement que les autres, et il ne le doit qu'a sa propre identite — jamais
    a la connaissance d'un autre.
    """
    if not environments:
        return []
    return sorted(
        sommaire.name
        for sommaire in context.domains
        if sommaire.name != self_name
        and not any(_deployment_for(sommaire, nom) for nom in environments)
    )
