"""Definition of the ``docker`` role: Docker CE engine and Compose plugin."""

from __future__ import annotations

from forge.plugins.ansible.catalog.definition import OptionKind, RoleDefinition, RoleOption

ROLE = RoleDefinition(
    name="docker",
    summary="Docker CE engine: official repository, service, Compose plugin and daemon options.",
    collections=(),
    handlers=("Restart Docker",),
    tags=("docker", "container"),
    options=(
        RoleOption(
            name="channel",
            question="Channel of the Docker repository",
            description="Channel of the official Docker repository used for the installation.",
            allowed="stable or test.",
            default="stable",
            kind=OptionKind.CHOICE,
            choices=("stable", "test"),
        ),
        RoleOption(
            name="install_compose_plugin",
            question="Install the docker compose plugin?",
            description="Installs the docker-compose-plugin package.",
            allowed="true or false.",
            default=True,
            kind=OptionKind.BOOL,
        ),
        RoleOption(
            name="users_in_docker_group",
            question="Accounts added to the docker group (comma-separated)",
            description="Local accounts allowed to drive Docker without sudo.",
            allowed="List of account names existing on the machine.",
            default=[],
            kind=OptionKind.LIST,
        ),
        RoleOption(
            name="log_driver",
            question="Logging driver of the daemon",
            description="Value of log-driver in /etc/docker/daemon.json.",
            allowed="json-file, local, journald or syslog.",
            default="json-file",
            kind=OptionKind.CHOICE,
            choices=("json-file", "local", "journald", "syslog"),
        ),
        RoleOption(
            name="log_max_size",
            question="Maximum size of a log file",
            description="Value of log-opts.max-size in /etc/docker/daemon.json.",
            allowed="A Docker size, for instance '10m' or '100m'.",
            default="10m",
            kind=OptionKind.TEXT,
        ),
        RoleOption(
            name="log_max_file",
            question="Number of log files kept",
            description="Value of log-opts.max-file in /etc/docker/daemon.json.",
            allowed="Positive integer.",
            default=3,
            kind=OptionKind.INT,
        ),
        RoleOption(
            name="service_enabled",
            question="Enable the docker service at boot?",
            description="Enables and starts the docker service.",
            allowed="true or false.",
            default=True,
            kind=OptionKind.BOOL,
        ),
    ),
)
