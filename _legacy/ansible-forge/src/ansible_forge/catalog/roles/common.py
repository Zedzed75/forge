"""Définition du rôle ``common`` : socle appliqué à toutes les machines."""

from __future__ import annotations

from ansible_forge.catalog.definition import OptionKind, RoleDefinition, RoleOption

ROLE = RoleDefinition(
    name="common",
    summary="Socle système : paquets de base, fuseau horaire, synchronisation NTP, bannière MOTD.",
    collections=("community.general",),
    handlers=("Redémarrer le service de synchronisation horaire",),
    tags=("common", "base"),
    options=(
        RoleOption(
            name="timezone",
            question="Fuseau horaire des machines",
            description="Fuseau horaire appliqué à toutes les machines du groupe.",
            allowed="Identifiant de la base tz, par exemple 'Europe/Paris' ou 'UTC'.",
            default="Europe/Paris",
            kind=OptionKind.TEXT,
        ),
        RoleOption(
            name="packages",
            question="Paquets de base à installer (séparés par des virgules)",
            description="Paquets installés sur toutes les machines du groupe.",
            allowed="Liste de noms de paquets valides pour la famille d'OS ciblée.",
            default=["ca-certificates", "curl", "htop", "vim"],
            kind=OptionKind.LIST,
        ),
        RoleOption(
            name="manage_timezone",
            question="Gérer le fuseau horaire ?",
            description="Active la configuration du fuseau horaire par le rôle.",
            allowed="true ou false.",
            default=True,
            kind=OptionKind.BOOL,
        ),
        RoleOption(
            name="enable_ntp",
            question="Activer la synchronisation NTP ?",
            description="Installe et active la synchronisation horaire (systemd-timesyncd).",
            allowed="true ou false.",
            default=True,
            kind=OptionKind.BOOL,
        ),
        RoleOption(
            name="manage_motd",
            question="Générer une bannière MOTD ?",
            description="Déploie un fichier /etc/motd décrivant le rôle de la machine.",
            allowed="true ou false.",
            default=True,
            kind=OptionKind.BOOL,
        ),
    ),
)
