"""Section `pipeline:` de forge.yml.

La section la plus courte du projet, et c'est voulu : **presque tout le contenu
du pipeline se deduit des autres sections**. Ce qui reste a decider tient en
quatre points — quel outil de CI, sur quoi il se declenche, faut-il construire
une image, faut-il deployer et sous quelle garde.

Ce que ce modele ne decide pas, et ne doit jamais decider :

* quels domaines valider — ce sont ceux que la specification demande ;
* quelles commandes lancer — chaque domaine les declare (`forge_validators`,
  `forge_deploy`) ;
* dans quel repertoire les lancer — chaque domaine le declare (`DomainInfo`).

Aucune valeur secrete n'a sa place ici. Les identifiants de registre et les
acces aux clusters sont des **secrets de la CI** : le pipeline genere les lit
par `${{ secrets.* }}` (GitHub) ou par des variables protegees (GitLab), et
forge n'en ecrit jamais la valeur.
"""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from forge.plugins.pipeline.enums import Provider
from forge.spec.names import require_unique
from forge.spec.types import ForgeModel

#: Runner par defaut de chaque outil de CI. GitHub nomme une machine, GitLab une
#: image de conteneur : le meme champ ne peut pas avoir le meme defaut.
DEFAULT_RUNNERS: dict[str, str] = {
    Provider.GITHUB.value: "ubuntu-latest",
    Provider.GITLAB.value: "debian:trixie-slim",
}


class TriggerSpec(ForgeModel):
    """Ce qui declenche le pipeline."""

    #: Branches dont un push declenche le pipeline.
    branches: list[str] = Field(default_factory=lambda: ["main"], min_length=1)

    #: Declenche aussi sur les propositions de fusion. Laissez a `true` : c'est
    #: le seul moment ou une validation empeche encore quelque chose.
    on_pull_request: bool = True

    #: Declenche aussi sur les etiquettes de version (v1.2.3).
    on_tag: bool = False

    @field_validator("branches")
    @classmethod
    def _unique(cls, value: list[str]) -> list[str]:
        require_unique(value, "branches de declenchement")
        return value


class BuildSpec(ForgeModel):
    """Construction et publication de l'image du service."""

    #: Repertoire de construction, relatif a la racine du depot.
    context: str = "."

    #: Chemin du Dockerfile, relatif a la racine du depot.
    dockerfile: str = "Dockerfile"

    #: Registre de destination. `ghcr.io` sur GitHub, `$CI_REGISTRY` sur GitLab.
    registry: str = "ghcr.io"

    #: Depot de l'image dans le registre. Vide, il vaut le nom du service.
    image: str = ""

    #: Plateformes construites. Plusieurs valeurs exigent buildx et allongent
    #: nettement la construction.
    platforms: list[str] = Field(default_factory=lambda: ["linux/amd64"], min_length=1)

    #: Publie l'image. A `false`, l'image est construite et jetee — utile pour
    #: verifier que le Dockerfile tient sans avoir de registre.
    push: bool = True


class DeploySpec(ForgeModel):
    """Deploiement, environnement par environnement."""

    #: Environnements deployes par le pipeline. Vide, ils le sont tous. Les noms
    #: sont verifies contre `service.environments` par le controle croise.
    environments: list[str] = Field(default_factory=list)

    #: Exige une approbation humaine avant de deployer la production. Le
    #: passer a `false` fait partir un `apply` sur la production au moindre
    #: push accepte.
    manual_for_production: bool = True

    #: Deploie les environnements dans l'ordre de `service.environments`, chacun
    #: attendant le precedent. A `false`, ils partent en parallele.
    sequential: bool = True

    @field_validator("environments")
    @classmethod
    def _unique(cls, value: list[str]) -> list[str]:
        require_unique(value, "environnements de deploiement")
        return value


class PipelineSpec(ForgeModel):
    """Section `pipeline:` : la chaine qui valide, construit et deploie."""

    #: Outil d'integration continue vise.
    provider: Provider = Provider.GITHUB

    #: Machine (GitHub) ou image de conteneur (GitLab) executant les jobs.
    #: Vide, le defaut de l'outil choisi s'applique.
    runner: str = ""

    #: Ce qui declenche le pipeline.
    trigger: TriggerSpec = Field(default_factory=TriggerSpec)

    #: Construction d'image. Absent, aucun job de construction n'est engendre —
    #: tous les services ne sont pas conteneurises.
    build: BuildSpec | None = None

    #: Deploiement. Absent, le pipeline se limite a valider ; c'est un choix
    #: legitime, et le plus courant tant que la chaine n'est pas eprouvee.
    deploy: DeploySpec | None = None

    @model_validator(mode="after")
    def _runner_par_defaut(self) -> PipelineSpec:
        """Applique le defaut propre a l'outil choisi.

        Fait ici plutot qu'a la derivation : le modele est la source de verite,
        et `forge.yml` relu doit dire ce qui sera reellement employe.
        """
        if not self.runner:
            object.__setattr__(self, "runner", DEFAULT_RUNNERS[self.provider.value])
        return self

    # -- lecture ------------------------------------------------------------

    @property
    def is_github(self) -> bool:
        """Vrai si l'outil vise est GitHub Actions."""
        return self.provider is Provider.GITHUB

    @property
    def is_gitlab(self) -> bool:
        """Vrai si l'outil vise est GitLab CI."""
        return self.provider is Provider.GITLAB

    def deployed_environments(self, declared: tuple[str, ...]) -> tuple[str, ...]:
        """Environnements a deployer, dans l'ordre de `service.environments`.

        L'ordre vient toujours du bloc partage, jamais de l'ordre d'ecriture de
        `pipeline.deploy.environments` : la promotion dev -> staging -> prod est
        une propriete du service, pas du pipeline.
        """
        if self.deploy is None:
            return ()
        if not self.deploy.environments:
            return declared
        demandes = set(self.deploy.environments)
        return tuple(nom for nom in declared if nom in demandes)
