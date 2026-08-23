"""Définition du rôle ``docker`` : moteur Docker CE et plugin Compose."""

from __future__ import annotations

from ansible_forge.catalog.definition import OptionKind, RoleDefinition, RoleOption

ROLE = RoleDefinition(
    name="docker",
    summary="Moteur Docker CE : dépôt officiel, service, plugin Compose et options du démon.",
    collections=(),
    handlers=("Redémarrer Docker",),
    tags=("docker", "container"),
    options=(
        RoleOption(
            name="channel",
            question="Canal du dépôt Docker",
            description="Canal du dépôt officiel Docker utilisé pour l'installation.",
            allowed="stable ou test.",
            default="stable",
            kind=OptionKind.CHOICE,
            choices=("stable", "test"),
        ),
        RoleOption(
            name="install_compose_plugin",
            question="Installer le plugin docker compose ?",
            description="Installe le paquet docker-compose-plugin.",
            allowed="true ou false.",
            default=True,
            kind=OptionKind.BOOL,
        ),
        RoleOption(
            name="users_in_docker_group",
            question="Comptes ajoutés au groupe docker (séparés par des virgules)",
            description="Comptes locaux autorisés à piloter Docker sans sudo.",
            allowed="Liste de noms de comptes existants sur la machine.",
            default=[],
            kind=OptionKind.LIST,
        ),
        RoleOption(
            name="log_driver",
            question="Pilote de journalisation du démon",
            description="Valeur de log-driver dans /etc/docker/daemon.json.",
            allowed="json-file, local, journald ou syslog.",
            default="json-file",
            kind=OptionKind.CHOICE,
            choices=("json-file", "local", "journald", "syslog"),
        ),
        RoleOption(
            name="log_max_size",
            question="Taille maximale d'un fichier de journal",
            description="Valeur de log-opts.max-size dans /etc/docker/daemon.json.",
            allowed="Taille Docker, par exemple '10m' ou '100m'.",
            default="10m",
            kind=OptionKind.TEXT,
        ),
        RoleOption(
            name="log_max_file",
            question="Nombre de fichiers de journal conservés",
            description="Valeur de log-opts.max-file dans /etc/docker/daemon.json.",
            allowed="Entier positif.",
            default=3,
            kind=OptionKind.INT,
        ),
        RoleOption(
            name="service_enabled",
            question="Activer le service docker au démarrage ?",
            description="Active et démarre le service docker.",
            allowed="true ou false.",
            default=True,
            kind=OptionKind.BOOL,
        ),
    ),
)
