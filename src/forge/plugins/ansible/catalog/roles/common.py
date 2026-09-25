"""Definition of the ``common`` role: baseline applied to every machine."""

from __future__ import annotations

from forge.plugins.ansible.catalog.definition import OptionKind, RoleDefinition, RoleOption

ROLE = RoleDefinition(
    name="common",
    summary="System baseline: base packages, time zone, NTP synchronisation, MOTD banner.",
    collections=("community.general",),
    handlers=("Restart the time synchronisation service",),
    tags=("common", "base"),
    options=(
        RoleOption(
            name="timezone",
            question="Time zone of the machines",
            description="Time zone applied to every machine of the group.",
            allowed="Identifier from the tz database, for instance 'Europe/Paris' or 'UTC'.",
            default="Europe/Paris",
            kind=OptionKind.TEXT,
        ),
        RoleOption(
            name="packages",
            question="Base packages to install (comma-separated)",
            description="Packages installed on every machine of the group.",
            allowed="List of package names valid for the targeted OS family.",
            default=["ca-certificates", "curl", "htop", "vim"],
            kind=OptionKind.LIST,
        ),
        RoleOption(
            name="manage_timezone",
            question="Manage the time zone?",
            description="Enables the configuration of the time zone by the role.",
            allowed="true or false.",
            default=True,
            kind=OptionKind.BOOL,
        ),
        RoleOption(
            name="enable_ntp",
            question="Enable NTP synchronisation?",
            description="Installs and enables time synchronisation (systemd-timesyncd).",
            allowed="true or false.",
            default=True,
            kind=OptionKind.BOOL,
        ),
        RoleOption(
            name="manage_motd",
            question="Generate a MOTD banner?",
            description="Deploys an /etc/motd file describing the purpose of the machine.",
            allowed="true or false.",
            default=True,
            kind=OptionKind.BOOL,
        ),
    ),
)
