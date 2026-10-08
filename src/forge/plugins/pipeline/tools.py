"""How to install the tools a pipeline has to run.

`Command` says **what to run**, never how to provision the machine that runs it:
a tool installs differently on an Ubuntu runner, inside a Debian image or on a
workstation, and none of that belongs to the domain declaring the command. This
table is therefore **specific to the pipeline plugin** — an arbitration taken in
phase 8, the other branch being to widen the `Command` contract.

An accepted consequence: this module quotes tool names. That is not knowing a
domain — `helm` is a binary, not a section of forge.yml, and a third-party domain
declaring `helm` in its commands would be served without changing anything here.
A tool **absent from the table** is never guessed: the pipeline generates a step
to complete, by name, and the README of the domain reports it.

The versions are frozen. A pipeline that installs "the latest version" of its
tools changes behaviour one morning without anything having been committed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Frozen versions of the tools installed by direct download.
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
    """How to obtain a tool on a Linux runner."""

    #: Name of the binary, as `Command.tool` names it.
    name: str

    #: What the tool does, in one line.
    summary: str

    #: Shell lines installing the tool. Run in order.
    steps: tuple[str, ...]

    #: System packages the installation itself needs.
    requires: tuple[str, ...] = ()

    #: Environment variables to set once the tool is installed.
    exports: dict[str, str] = field(default_factory=dict)


def _release(url: str, binary: str, archive: str) -> tuple[str, ...]:
    """Download a release archive, extract a binary from it, install it."""
    extraction = (
        f"unzip -qo /tmp/{archive} -d /tmp"
        if archive.endswith(".zip")
        else f"tar -xzf /tmp/{archive} -C /tmp {binary}"
    )
    return (
        f"curl -fsSL -o /tmp/{archive} {url}",
        extraction,
        f"install -m 0755 /tmp/{binary} /usr/local/bin/{binary}",
    )


#: Table of the known tools. The two Ansible tools share one entry per binary:
#: `Command.tool` names the binary, not the distribution.
INSTALLS: tuple[ToolInstall, ...] = (
    ToolInstall(
        name="ansible-playbook",
        summary="runs the Ansible playbooks",
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
        summary="checks the Ansible good practices",
        steps=("python3 -m pip install --quiet ansible-core ansible-lint",),
        requires=("python3-pip",),
        exports={"ANSIBLE_COLLECTIONS_PATH": "$HOME/.ansible/collections"},
    ),
    ToolInstall(
        name="helm",
        summary="packages and deploys the Kubernetes charts",
        steps=(
            "curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/"
            f"get-helm-3 | bash -s -- --version v{VERSIONS['helm']}",
        ),
        requires=("curl",),
    ),
    ToolInstall(
        name="kubeconform",
        summary="validates manifests against the Kubernetes API schemas",
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
        summary="describes and applies the infrastructure",
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
        summary="checks the Terraform good practices",
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
        summary="checks the GitHub Actions workflows",
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
        summary="checks the form of a YAML file",
        steps=("python3 -m pip install --quiet yamllint",),
        requires=("python3-pip",),
    ),
    ToolInstall(
        name="promtool",
        summary="validates the Prometheus alerting rules",
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

#: Table indexed by binary name.
BY_NAME: dict[str, ToolInstall] = {tool.name: tool for tool in INSTALLS}


def known(name: str) -> bool:
    """True when the plugin knows how to install `name`."""
    return name in BY_NAME


def install(name: str) -> ToolInstall | None:
    """Installation recipe of `name`, or None when the tool is unknown."""
    return BY_NAME.get(name)


def resolve(names: tuple[str, ...]) -> tuple[list[ToolInstall], list[str]]:
    """Split the known tools from the unknown ones, in the order of `names`.

    The unknown ones are **not** an error: a third-party domain may run a tool
    forge does not know. They become a step to complete, visible in the generated
    pipeline, rather than a guessed command.
    """
    known_tools: list[ToolInstall] = []
    unknown: list[str] = []
    for name in names:
        recipe = BY_NAME.get(name)
        if recipe is None:
            unknown.append(name)
        else:
            known_tools.append(recipe)
    return known_tools, unknown


def system_packages(recipes: list[ToolInstall]) -> tuple[str, ...]:
    """System packages the whole set of recipes needs, sorted."""
    return tuple(sorted({package for recipe in recipes for package in recipe.requires}))
