"""The `pipeline:` section of forge.yml.

The shortest section of the project, and deliberately so: **almost all the
content of the pipeline is deduced from the other sections**. What is left to
decide comes down to four points — which CI tool, what triggers it, whether an
image has to be built, whether a deployment happens and under what guard.

What this model does not decide, and must never decide:

* which domains to validate — they are the ones the specification asks for;
* which commands to run — each domain declares them (`forge_validators`,
  `forge_deploy`);
* in which directory to run them — each domain declares it (`DomainInfo`).

No secret value has its place here. Registry credentials and cluster accesses are
**CI secrets**: the generated pipeline reads them through `${{ secrets.* }}`
(GitHub) or through protected variables (GitLab), and forge never writes their
value.
"""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from forge.plugins.pipeline.enums import Provider
from forge.spec.names import require_unique
from forge.spec.types import ForgeModel

#: Default runner of each CI tool. GitHub names a machine, GitLab a container
#: image: the same field cannot have the same default.
DEFAULT_RUNNERS: dict[str, str] = {
    Provider.GITHUB.value: "ubuntu-latest",
    Provider.GITLAB.value: "debian:trixie-slim",
}


class TriggerSpec(ForgeModel):
    """What triggers the pipeline."""

    #: Branches a push on which triggers the pipeline.
    branches: list[str] = Field(default_factory=lambda: ["main"], min_length=1)

    #: Also triggers on merge requests. Leave it at `true`: it is the only moment
    #: when a validation still prevents anything.
    on_pull_request: bool = True

    #: Also triggers on version tags (v1.2.3).
    on_tag: bool = False

    @field_validator("branches")
    @classmethod
    def _unique(cls, value: list[str]) -> list[str]:
        require_unique(value, "trigger branches")
        return value


class BuildSpec(ForgeModel):
    """Build and publication of the service image."""

    #: Build directory, relative to the root of the repository.
    context: str = "."

    #: Path of the Dockerfile, relative to the root of the repository.
    dockerfile: str = "Dockerfile"

    #: Destination registry. `ghcr.io` on GitHub, `$CI_REGISTRY` on GitLab.
    registry: str = "ghcr.io"

    #: Repository of the image within the registry. Empty, it is the service name.
    image: str = ""

    #: Platforms built. Several values require buildx and lengthen the build
    #: markedly.
    platforms: list[str] = Field(default_factory=lambda: ["linux/amd64"], min_length=1)

    #: Publishes the image. At `false`, the image is built and thrown away —
    #: useful to check that the Dockerfile holds up without having a registry.
    push: bool = True


class DeploySpec(ForgeModel):
    """Deployment, environment by environment."""

    #: Environments the pipeline deploys. Empty, all of them are. The names are
    #: checked against `service.environments` by the cross-check.
    environments: list[str] = Field(default_factory=list)

    #: Requires a human approval before deploying production. Switching it to
    #: `false` sends an `apply` to production on the slightest accepted push.
    manual_for_production: bool = True

    #: Deploys the environments in the order of `service.environments`, each one
    #: waiting for the previous. At `false`, they go in parallel.
    sequential: bool = True

    @field_validator("environments")
    @classmethod
    def _unique(cls, value: list[str]) -> list[str]:
        require_unique(value, "deployment environments")
        return value


class PipelineSpec(ForgeModel):
    """The `pipeline:` section: the chain that validates, builds and deploys."""

    #: Targeted continuous integration tool.
    provider: Provider = Provider.GITHUB

    #: Machine (GitHub) or container image (GitLab) running the jobs. Empty, the
    #: default of the chosen tool applies.
    runner: str = ""

    #: What triggers the pipeline.
    trigger: TriggerSpec = Field(default_factory=TriggerSpec)

    #: Image build. Absent, no build job is generated — not every service is
    #: containerised.
    build: BuildSpec | None = None

    #: Deployment. Absent, the pipeline limits itself to validating; that is a
    #: legitimate choice, and the most common one until the chain is proven.
    deploy: DeploySpec | None = None

    @model_validator(mode="after")
    def _default_runner(self) -> PipelineSpec:
        """Apply the default specific to the chosen tool.

        Done here rather than at derivation time: the model is the source of
        truth, and a `forge.yml` read back must say what will really be used.
        """
        if not self.runner:
            object.__setattr__(self, "runner", DEFAULT_RUNNERS[self.provider.value])
        return self

    # -- lookups ------------------------------------------------------------

    @property
    def is_github(self) -> bool:
        """True when the targeted tool is GitHub Actions."""
        return self.provider is Provider.GITHUB

    @property
    def is_gitlab(self) -> bool:
        """True when the targeted tool is GitLab CI."""
        return self.provider is Provider.GITLAB

    def deployed_environments(self, declared: tuple[str, ...]) -> tuple[str, ...]:
        """Environments to deploy, in the order of `service.environments`.

        The order always comes from the shared block, never from the order
        `pipeline.deploy.environments` was written in: the dev -> staging -> prod
        promotion is a property of the service, not of the pipeline.
        """
        if self.deploy is None:
            return ()
        if not self.deploy.environments:
            return declared
        requested = set(self.deploy.environments)
        return tuple(name for name in declared if name in requested)
